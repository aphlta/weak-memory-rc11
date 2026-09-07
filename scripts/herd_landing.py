#!/usr/bin/env python3
"""B1：07 规格 8 条 RVWMO litmus 的 herd 外部验收表。

外部 oracle = herd7 + riscv.cat；本器给出全枚举 / 约简弱态布尔 + 组合数。
同结论 ≠ 语义等价；每行必须写清编码差。UNPAIRED 不计入通过率。

  python3 scripts/herd_landing.py --write-results

旧「同向」表仍由 scripts/herd_compare.py 维护，降为附录。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from weak_memory_verifier import analyze_program

DEFAULT_HERD = "/ssdhome/maoweiming/xiangshan/.opam-root/default/bin/herd7"
DEFAULT_CAT = (
    "/ssdhome/maoweiming/xiangshan/.opam-root/default/share/herdtools7/herd/riscv.cat"
)
# 07 规格路径相对 litmus-tests-riscv/tests/non-mixed-size/
DEFAULT_LITMUS_ROOT = (
    "/ssdhome/maoweiming/xiangshan/litmus-tests-riscv/tests/non-mixed-size"
)

WeakPred = Callable[[Any], bool]


def _run_herd(herd: Path, cat: Path, litmus: Path) -> Dict[str, Any]:
    """跑 herd7；Observation Sometimes/Never 对应弱态允/禁。"""
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
    m_wit = re.search(r"Positive:\s*(\d+)\s+Negative:\s*(\d+)", out)
    m_states = re.search(r"States\s+(\d+)", out)
    allowed_weak = None
    if m_obs:
        # Sometimes/Always → 允许 exists 弱态；Never → 禁止
        allowed_weak = m_obs.group(1) != "Never"
    elif m_wit:
        allowed_weak = int(m_wit.group(1)) > 0
    return {
        "ok": proc.returncode == 0,
        "observation": m_obs.group(1) if m_obs else None,
        "positive": int(m_wit.group(1)) if m_wit else None,
        "negative": int(m_wit.group(2)) if m_wit else None,
        "states": int(m_states.group(1)) if m_states else None,
        "weak_allowed": allowed_weak,
        "raw_head": "\n".join(out.splitlines()[:20]),
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


def _cowr0_weak(result) -> bool:
    """CoWR0：kept 中存在 r!=1（对应 Never 禁非 0:x7=1）。"""
    return any(exe.envs.get(0, {}).get("r") != 1 for exe in result.executions)


def _corr_official_weak(result) -> bool:
    """官方 CoRR：kept 中存在 r1=1∧r2=0。不用 coherence_rr.json。"""
    return any(
        exe.envs.get(1, {}).get("r1") == 1 and exe.envs.get(1, {}).get("r2") == 0
        for exe in result.executions
    )


def _tool_both(example: str, pred: WeakPred) -> Dict[str, Any]:
    path = ROOT / "examples" / example
    none = analyze_program(path, reduction="none")
    rel = analyze_program(path, reduction="relevant")
    return {
        "example": example,
        "full_candidates": none.stats["full_candidate_assignments"],
        "reduced_candidates": rel.stats["explored_candidate_assignments"],
        # 全枚举路径上的 explored 应等于 full；约简路径用 explored
        "none_explored": none.stats["explored_candidate_assignments"],
        "weak_none": bool(pred(none)),
        "weak_relevant": bool(pred(rel)),
        "kept_none": len(none.executions),
        "kept_relevant": len(rel.executions),
    }


# status: PAIRED | UNPAIRED | NO-RVWMO-PEER
# litmus_rel: 相对 DEFAULT_LITMUS_ROOT；None 表示无 litmus
ROWS_SPEC: List[Dict[str, Any]] = [
    {
        "id": "MP",
        "litmus_rel": "BASIC_2_THREAD/MP.litmus",
        "herd_expect": "Sometimes",
        "status": "PAIRED",
        "example": "mp_relaxed.json",
        "weak_name": "f=1 ∧ r=0",
        "pred": _mp_weak,
        "encoding_gap": "教具双侧 relaxed store/load；非 RISC-V 汇编逐条翻译",
    },
    {
        "id": "SB",
        "litmus_rel": "BASIC_2_THREAD/SB.litmus",
        "herd_expect": "Sometimes",
        "status": "PAIRED",
        "example": "sb_relaxed.json",
        "weak_name": "(a,b)=(0,0)",
        "pred": _sb_weak,
        "encoding_gap": "教具 SB；寄存器名 a/b 对应 litmus 两线程读结果",
    },
    {
        "id": "LB",
        "litmus_rel": "BASIC_2_THREAD/LB.litmus",
        "herd_expect": "Sometimes",
        "status": "PAIRED",
        "example": "lb_relaxed.json",
        "weak_name": "(a,b)=(1,1)",
        "pred": _lb_weak,
        "encoding_gap": "教具 LB；非汇编翻译",
    },
    {
        "id": "MP+fence.rw.rws",
        "litmus_rel": "SAFE/MP+fence.rw.rws.litmus",
        "herd_expect": "Never",
        "status": "PAIRED",
        "example": "mp_sc_fence.json",
        "weak_name": "f=1 ∧ r=0",
        "pred": _mp_weak,
        "encoding_gap": "litmus 双侧 fence.rw.rw ≠ 本器 seq_cst fence；仅弱态允/禁同向，非公理等价",
    },
    {
        "id": "LB+addrs",
        "litmus_rel": "SAFE/LB+addrs.litmus",
        "herd_expect": "Never",
        "status": "UNPAIRED",
        "example": None,
        "weak_name": "(1,1) via addr dep",
        "pred": None,
        "encoding_gap": "本器无地址依赖；禁止用普通 LB 冒充",
    },
    {
        "id": "CoWW",
        "litmus_rel": "CO/CoWW.litmus",
        "herd_expect": "Never",
        "status": "UNPAIRED",
        "example": None,
        "weak_name": "[x]≠2（官方）",
        "pred": None,
        "encoding_gap": (
            "官方 exists (not ([x]=2))，States 仅 [x]=2；"
            "本器无最终内存投影；mo 末写≠2 与 po/eid 同向，删掉 CoWW 边也常仍为 2，测不出公理缺失；"
            "coww_stores_only.json 保留作教具，不计入 paired"
        ),
    },
    {
        "id": "CoRR",
        "litmus_rel": "CO/CoRR.litmus",
        "herd_expect": "Never",
        "status": "PAIRED",
        "example": "corr_official.json",
        "weak_name": "r1=1 ∧ r2=0",
        "pred": _corr_official_weak,
        "encoding_gap": (
            "官方 exists (not ([x]=1 /\\ (1:x5=0 /\\ (1:x7=0 \\/ 1:x7=1) "
            "\\/ 1:x5=1 /\\ 1:x7=1)))；States (0,0)(0,1)(1,1) 无 (1,0)；"
            "本器 weak=r1=1∧r2=0；非 coherence_rr.json"
        ),
    },
    {
        "id": "CoWR0",
        "litmus_rel": "CO/CoWR0.litmus",
        "herd_expect": "Never",
        "status": "PAIRED",
        "example": "cowr0_self_read.json",
        "weak_name": "r≠1",
        "pred": _cowr0_weak,
        "encoding_gap": (
            "官方 exists (not (0:x7=1 /\\ [x]=1))；States 仅 0:x7=1;[x]=1；"
            "本器 weak=kept 中 r≠1"
        ),
    },
    {
        "id": "MP-RA-tool",
        "litmus_rel": None,
        "herd_expect": None,
        "status": "NO-RVWMO-PEER",
        "example": "message_passing.json",
        "weak_name": "f=1 ∧ r=0",
        "pred": _mp_weak,
        "encoding_gap": "本器 release/acquire；无对等 RVWMO fence litmus 行",
    },
]


def build_rows(herd: Path, cat: Path, litmus_root: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for spec in ROWS_SPEC:
        herd_info: Optional[Dict[str, Any]] = None
        litmus_name = None
        if spec["litmus_rel"]:
            litmus_path = litmus_root / str(spec["litmus_rel"])
            litmus_name = litmus_path.name
            if not litmus_path.is_file():
                raise SystemExit(f"缺少 litmus: {litmus_path}")
            herd_info = _run_herd(herd, cat, litmus_path)
            if not herd_info["ok"]:
                raise SystemExit(
                    f"herd 失败: {litmus_path}\n{herd_info['raw_head']}"
                )

        tool: Optional[Dict[str, Any]] = None
        if spec["status"] in {"PAIRED", "NO-RVWMO-PEER"} and spec["example"]:
            tool = _tool_both(str(spec["example"]), spec["pred"])

        herd_weak = None if herd_info is None else herd_info["weak_allowed"]
        herd_obs = None if herd_info is None else herd_info["observation"]

        # 期望：PAIRED 行用规格中的 Sometimes/Never；并与 herd 实测交叉核对
        expect = spec["herd_expect"]
        expect_weak = None if expect is None else (expect != "Never")
        if herd_obs is not None and expect is not None and herd_obs != expect:
            # 不静默：规格写错或 litmus 路径错时应失败
            raise SystemExit(
                f"{spec['id']}: herd Observation={herd_obs} 与规格期望 {expect} 不符"
            )

        agree = None
        reduction_ok = None
        if spec["status"] == "PAIRED" and tool is not None and herd_weak is not None:
            # 落地版 T2：herd ↔ none ↔ relevant 弱态布尔一致
            reduction_ok = tool["weak_none"] == tool["weak_relevant"]
            agree = (
                herd_weak == tool["weak_none"]
                and herd_weak == tool["weak_relevant"]
                and reduction_ok
            )
        elif spec["status"] == "NO-RVWMO-PEER" and tool is not None:
            reduction_ok = tool["weak_none"] == tool["weak_relevant"]
            agree = None  # 无 herd 对，不计入 paired_agree

        rows.append(
            {
                "id": spec["id"],
                "status": spec["status"],
                "litmus": litmus_name,
                "litmus_rel": spec["litmus_rel"],
                "herd_expect": expect,
                "herd_observation": herd_obs,
                "herd_weak_allowed": herd_weak,
                "herd_states": None if herd_info is None else herd_info["states"],
                "example": spec["example"],
                "weak_name": spec["weak_name"],
                "tool_weak_none": None if tool is None else tool["weak_none"],
                "tool_weak_relevant": None if tool is None else tool["weak_relevant"],
                "full_candidates": None if tool is None else tool["full_candidates"],
                "reduced_candidates": None if tool is None else tool["reduced_candidates"],
                "reduction_weak_agree": reduction_ok,
                "agree": agree,
                "encoding_gap": spec["encoding_gap"],
            }
        )
    return rows


def _yn(v: Optional[bool]) -> str:
    if v is None:
        return "—"
    return "是" if v else "否"


def _allow(v: Optional[bool]) -> str:
    if v is None:
        return "—"
    return "允许" if v else "禁止"


def to_markdown(rows: List[Dict[str, Any]], meta: Dict[str, str]) -> str:
    paired = [r for r in rows if r["status"] == "PAIRED"]
    paired_agree = [r for r in paired if r["agree"] is True]
    unpaired = [r for r in rows if r["status"] == "UNPAIRED"]
    peers = [r for r in rows if r["status"] == "NO-RVWMO-PEER"]

    lines = [
        "# herd 落地验收（B1 / 07 规格）",
        "",
        "## 文首指标",
        "",
        f"- **paired_n** = {len(paired)}",
        f"- **paired_agree_n** = {len(paired_agree)}（herd 与本器 none/relevant 弱态布尔一致）",
        f"- **unpaired_n** = {len(unpaired)}",
        f"- **no_rvwmo_peer_n** = {len(peers)}（不计入配对通过率）",
        "",
        "外部 oracle：**herd7 + riscv.cat**。本器不是 DUT oracle，也不是完整 RC11/RVWMO。",
        "落地主表**不含** scale_noise。同结论 ≠ 语义等价。",
        "",
        f"- herd：`{meta['herd']}`",
        f"- model：`{meta['cat']}`",
        f"- litmus 根：`{meta['litmus_root']}`",
        f"- 规格：`xs-am-verify/docs/specs/07-rv64-mm-litmus.md`",
        "",
        "## 对照表",
        "",
        "| id | status | herd | 本器 none | 本器 relevant | 一致 | full | reduced | 例子 | 编码差 |",
        "| --- | --- | --- | --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for r in rows:
        herd_cell = "—"
        if r["herd_observation"] is not None:
            herd_cell = f"{r['herd_observation']}（{_allow(r['herd_weak_allowed'])}）"
        elif r["status"] == "NO-RVWMO-PEER":
            herd_cell = "（无 litmus）"
        ex = f"`{r['example']}`" if r["example"] else "—"
        full = r["full_candidates"] if r["full_candidates"] is not None else "—"
        red = r["reduced_candidates"] if r["reduced_candidates"] is not None else "—"
        lines.append(
            f"| `{r['id']}` | {r['status']} | {herd_cell} | "
            f"{_allow(r['tool_weak_none'])} | {_allow(r['tool_weak_relevant'])} | "
            f"{_yn(r['agree'])} | {full} | {red} | {ex} | {r['encoding_gap']} |"
        )

    lines += [
        "",
        "## 已配对行组合数",
        "",
        "| id | full | reduced | saved |",
        "| --- | ---: | ---: | ---: |",
    ]
    for r in paired:
        full = int(r["full_candidates"])
        red = int(r["reduced_candidates"])
        saved = 0.0 if full == 0 else (full - red) / full
        lines.append(f"| `{r['id']}` | {full} | {red} | {saved:.4f} |")

    lines += [
        "",
        "## 守门说明",
        "",
        "- PAIRED ∧ herd Never → none/relevant 均须禁止弱态。",
        "- PAIRED ∧ herd Sometimes → none/relevant 均须检出弱态。",
        "- none 与 relevant 弱态布尔须一致（落地版 T2；oracle 是 herd）。",
        "- UNPAIRED / NO-RVWMO-PEER 不计入 paired_agree_n。",
        "",
        "生成：`python3 scripts/herd_landing.py --write-results`",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="B1 herd 落地验收表")
    parser.add_argument("--herd", type=Path, default=Path(os.environ.get("HERD7", DEFAULT_HERD)))
    parser.add_argument("--cat", type=Path, default=Path(os.environ.get("RISCV_CAT", DEFAULT_CAT)))
    parser.add_argument(
        "--litmus-root",
        type=Path,
        default=Path(os.environ.get("LITMUS_ROOT", DEFAULT_LITMUS_ROOT)),
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
        "litmus_root": str(args.litmus_root),
    }
    rows = build_rows(args.herd, args.cat, args.litmus_root)
    md = to_markdown(rows, meta)
    print(md)

    paired = [r for r in rows if r["status"] == "PAIRED"]
    bad = [r for r in paired if r["agree"] is not True]
    if bad:
        raise SystemExit(
            "PAIRED 行未与 herd/约简对齐: " + ", ".join(r["id"] for r in bad)
        )

    if args.write_results:
        out = ROOT / "results"
        out.mkdir(exist_ok=True)
        payload = {
            "meta": meta,
            "summary": {
                "paired_n": len(paired),
                "paired_agree_n": sum(1 for r in paired if r["agree"] is True),
                "unpaired_n": sum(1 for r in rows if r["status"] == "UNPAIRED"),
                "no_rvwmo_peer_n": sum(
                    1 for r in rows if r["status"] == "NO-RVWMO-PEER"
                ),
            },
            "rows": rows,
        }
        (out / "herd_landing.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (out / "herd_landing.md").write_text(md, encoding="utf-8")
        print(f"已写入 {out / 'herd_landing.md'} 与 {out / 'herd_landing.json'}")


if __name__ == "__main__":
    main()
