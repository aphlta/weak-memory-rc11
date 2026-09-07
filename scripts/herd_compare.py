#!/usr/bin/env python3
"""本原型 vs herdtools 弱态对照表生成。

比较经典 litmus 与本课题 JSON 例子在「弱态是否允许」上是否同向。
同向 ≠ 语义等价。

  python3 scripts/herd_compare.py --write-results
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from weak_memory_verifier import analyze_program, outcome_set


DEFAULT_HERD = "/ssdhome/maoweiming/xiangshan/.opam-root/default/bin/herd7"
DEFAULT_CAT = (
    "/ssdhome/maoweiming/xiangshan/.opam-root/default/share/herdtools7/herd/riscv.cat"
)
DEFAULT_LITMUS = (
    "/ssdhome/maoweiming/xiangshan/litmus-tests-riscv/tests/non-mixed-size/BASIC_2_THREAD"
)


def _run_herd(herd: Path, cat: Path, litmus: Path) -> Dict[str, object]:
    proc = subprocess.run(
        [str(herd), "-model", str(cat), str(litmus)],
        capture_output=True,
        text=True,
        check=False,
    )
    out = proc.stdout + proc.stderr
    m_obs = re.search(
        r"Observation\s+\S+\s+(Sometimes|Never|Always)\s+(\d+)\s+(\d+)", out
    )
    m_states = re.search(r"States\s+(\d+)", out)
    # Witnesses Positive: P Negative: N — Positive>0 表示 exists 弱态被允许
    m_wit = re.search(r"Positive:\s*(\d+)\s+Negative:\s*(\d+)", out)
    allowed_weak = None
    if m_obs:
        allowed_weak = m_obs.group(1) != "Never"
    elif m_wit:
        allowed_weak = int(m_wit.group(1)) > 0
    return {
        "litmus": litmus.name,
        "ok": proc.returncode == 0,
        "observation": m_obs.group(1) if m_obs else None,
        "positive": int(m_wit.group(1)) if m_wit else None,
        "negative": int(m_wit.group(2)) if m_wit else None,
        "states": int(m_states.group(1)) if m_states else None,
        "weak_allowed": allowed_weak,
        "raw_head": "\n".join(out.splitlines()[:16]),
    }


def _tool_row(example: str, weak_pred) -> Dict[str, object]:
    path = ROOT / "examples" / example
    result = analyze_program(path, reduction="none")
    outs = outcome_set(result.program, result.executions)
    weak = weak_pred(result)
    return {
        "example": example,
        "outcome_count": len(outs),
        "kept_executions": len(result.executions),
        "weak_allowed": weak,
        "observe": list(result.program.observe),
    }


def _mp_weak(result) -> bool:
    return any(
        exe.envs.get(1, {}).get("f") == 1 and exe.envs.get(1, {}).get("r") == 0
        for exe in result.executions
    )


def _sb_weak(result) -> bool:
    return any(
        exe.envs.get(0, {}).get("a") == 0 and exe.envs.get(1, {}).get("b") == 0
        for exe in result.executions
    )


def _lb_weak(result) -> bool:
    return any(
        exe.envs.get(0, {}).get("a") == 1 and exe.envs.get(1, {}).get("b") == 1
        for exe in result.executions
    )


# 对照行：herd litmus ↔ 本器 JSON；agree 指「弱态允许与否」是否同向
PAIRS: List[Dict[str, object]] = [
    {
        "pattern": "MP（无 fence）",
        "litmus": "MP.litmus",
        "example": "mp_relaxed.json",
        "weak_name": "flag=1 ∧ data=0",
        "pred": _mp_weak,
        "note": "双侧 plain store/load；两侧均允许弱态",
    },
    {
        "pattern": "MP + 双侧 fence.rw.rw",
        "litmus": "MP+fence.rw.rws.litmus",
        "example": "mp_sc_fence.json",
        "weak_name": "flag=1 ∧ data=0",
        "pred": _mp_weak,
        "note": "均禁止弱态；fence 编码不同（litmus fence.rw.rw vs 本原型 seq_cst fence）",
    },
    {
        "pattern": "SB（无 fence）",
        "litmus": "SB.litmus",
        "example": "sb_relaxed.json",
        "weak_name": "(0,0)",
        "pred": _sb_weak,
        "note": "均允许 (0,0)",
    },
    {
        "pattern": "SB + 双侧 fence.rw.rw",
        "litmus": "SB+fence.rw.rws.litmus",
        "example": "sb_seq_cst.json",
        "weak_name": "(0,0)",
        "pred": _sb_weak,
        "note": "均禁止 (0,0)；本原型用存在性 SC",
    },
    {
        "pattern": "LB（无 fence）",
        "litmus": "LB.litmus",
        "example": "lb_relaxed.json",
        "weak_name": "(1,1)",
        "pred": _lb_weak,
        "note": "均允许 (1,1)",
    },
    {
        "pattern": "MP + RA（本原型）",
        "litmus": None,
        "example": "message_passing.json",
        "weak_name": "flag=1 ∧ data=0",
        "pred": _mp_weak,
        "note": "release/acquire；无对等汇编 litmus 行；弱态禁止",
    },
]


def build_rows(herd: Path, cat: Path, litmus_dir: Path) -> List[Dict[str, object]]:
    rows = []
    for spec in PAIRS:
        herd_info: Optional[Dict[str, object]] = None
        if spec["litmus"]:
            litmus_path = litmus_dir / str(spec["litmus"])
            if not litmus_path.is_file():
                raise SystemExit(f"缺少 litmus: {litmus_path}")
            herd_info = _run_herd(herd, cat, litmus_path)
            if not herd_info["ok"]:
                raise SystemExit(f"herd 失败: {litmus_path}\n{herd_info['raw_head']}")

        tool = _tool_row(str(spec["example"]), spec["pred"])
        if herd_info is None:
            agree = None
        else:
            agree = bool(herd_info["weak_allowed"]) == bool(tool["weak_allowed"])
        rows.append(
            {
                "pattern": spec["pattern"],
                "weak_name": spec["weak_name"],
                "litmus": spec["litmus"],
                "herd_observation": None if herd_info is None else herd_info["observation"],
                "herd_weak_allowed": None if herd_info is None else herd_info["weak_allowed"],
                "herd_states": None if herd_info is None else herd_info["states"],
                "example": spec["example"],
                "tool_weak_allowed": tool["weak_allowed"],
                "tool_outcomes": tool["outcome_count"],
                "agree_on_weak": agree,
                "note": spec["note"],
            }
        )
    return rows


def to_markdown(rows: List[Dict[str, object]], meta: Dict[str, str]) -> str:
    lines = [
        "# 本原型 ↔ herdtools 弱态对照",
        "",
        "## 说明",
        "",
        "本表比较经典 litmus（经 herd7 与 `riscv.cat` 判定）与本原型 JSON 例子在"
        "**同一类弱态是否允许**上的结论是否同向。",
        "",
        "两套对象不同：一侧是 herdtools 的汇编 litmus；一侧是本课题的 RC11 核心子集枚举器。"
        "「同向」不等于语义等价（例如 `fence.rw.rw` 与本器 `seq_cst` fence / SC 不是同一公理）。",
        "",
        f"- herd：`{meta['herd']}`",
        f"- model：`{meta['cat']}`",
        f"- litmus 目录：`{meta['litmus_dir']}`",
        "",
        "## 弱态允许对照",
        "",
        "| 模式 | 弱态 | herdtools | 本原型例子 | 本原型弱态 | 同向? | 说明 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        herd_cell = "—"
        if row["litmus"]:
            flag = "允许" if row["herd_weak_allowed"] else "禁止"
            herd_cell = f"`{row['litmus']}` / {row['herd_observation']}（{flag}）"
        tool_flag = "允许" if row["tool_weak_allowed"] else "禁止"
        if row["agree_on_weak"] is None:
            agree = "—"
        else:
            agree = "是" if row["agree_on_weak"] else "否"
        lines.append(
            f"| {row['pattern']} | {row['weak_name']} | {herd_cell} | "
            f"`{row['example']}` | {tool_flag} | {agree} | {row['note']} |"
        )
    lines += [
        "",
        "## 论文中的用法",
        "",
        "1. 用 MP/SB/LB（无 fence）说明本原型能给出与 litmus 常见弱态一致的允许结论。",
        "2. 用双侧 fence / SC 说明同步加强后弱态消失，与 herdtools 同向。",
        "3. 约简有效性（组合数、时间、不漏报）以本原型内部 T2 实验为准。",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 herd 对照表")
    parser.add_argument("--herd", type=Path, default=Path(os.environ.get("HERD7", DEFAULT_HERD)))
    parser.add_argument("--cat", type=Path, default=Path(os.environ.get("RISCV_CAT", DEFAULT_CAT)))
    parser.add_argument(
        "--litmus-dir",
        type=Path,
        default=Path(os.environ.get("LITMUS_BASIC", DEFAULT_LITMUS)),
    )
    parser.add_argument("--write-results", action="store_true")
    args = parser.parse_args()

    if not args.herd.is_file():
        raise SystemExit(f"找不到 herd7: {args.herd}")
    if not args.cat.is_file():
        raise SystemExit(f"找不到 riscv.cat: {args.cat}")

    meta = {
        "herd": str(args.herd),
        "cat": str(args.cat),
        "litmus_dir": str(args.litmus_dir),
    }
    rows = build_rows(args.herd, args.cat, args.litmus_dir)
    md = to_markdown(rows, meta)
    print(md)

    disagrees = [r for r in rows if r["agree_on_weak"] is False]
    if disagrees:
        raise SystemExit(
            "对照出现不同向行（需检查映射）: "
            + ", ".join(r["pattern"] for r in disagrees)
        )

    if args.write_results:
        out = ROOT / "results"
        out.mkdir(exist_ok=True)
        (out / "herd_comparison.json").write_text(
            json.dumps({"meta": meta, "rows": rows}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (out / "herd_comparison.md").write_text(md, encoding="utf-8")
        # 文档入口已改为 herd_landing；旧同向表只留在 results/，避免覆盖 docs/HERD-COMPARISON.md
        print(f"已写入 {out / 'herd_comparison.md'}（附录快照；现行验收见 herd_landing）")


if __name__ == "__main__":
    main()
