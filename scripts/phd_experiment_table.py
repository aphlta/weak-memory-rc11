#!/usr/bin/env python3
"""博士阶段实验总表（P2）：T2⁺ 保持 + 闭包规模 + 组合缩减。

  python3 scripts/phd_experiment_table.py --write-results
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from weak_memory_verifier import (
    compare_reduction,
    compute_relevance_closure,
    load_program,
)


def row_for(path: Path) -> Dict[str, object]:
    cmp = compare_reduction(path)
    if not cmp["props_ok"] or not cmp["outcomes_ok"]:
        raise SystemExit(f"T2⁺ 失败: {path.name}")
    program = load_program(path)
    closure = compute_relevance_closure(program, ind_mode="promote")
    full = int(cmp["full_stats"]["full_candidate_assignments"])
    reduced = int(cmp["reduced_stats"]["explored_candidate_assignments"])
    return {
        "program": path.name,
        "loads": cmp["full_stats"]["total_loads"],
        "cl_reads": len(closure.relevant_reads),
        "id_dims": len(closure.identity_reads),
        "val_dims": len(closure.value_reads),
        "sync_deps": len(closure.sync_deps),
        "ind_promoted": len(closure.ind_promoted),
        "full": full,
        "naive_rel": int(cmp["reduced_stats"].get("naive_relevant_product", reduced)),
        "reduced": reduced,
        "saved_ratio": round(0.0 if full == 0 else (full - reduced) / full, 4),
        "s3_ratio": round(
            0.0
            if int(cmp["reduced_stats"].get("naive_relevant_product", reduced)) == 0
            else 1
            - reduced / int(cmp["reduced_stats"].get("naive_relevant_product", reduced)),
            4,
        ),
        "outcomes": cmp["full_outcomes"],
        "props_ok": cmp["props_ok"],
        "outcomes_ok": cmp["outcomes_ok"],
        "is_racy": cmp["full_summary"]["is_racy"],
        "assertion_can_fail": cmp["full_summary"]["assertion_can_fail"],
    }


def to_markdown(rows: List[Dict[str, object]]) -> str:
    lines = [
        "# 博士实验表（P2 / T2⁺⁺ / S3）",
        "",
        "理论：[`docs/phd/THEORY-v1.md`](../docs/phd/THEORY-v1.md)。",
        "`naive_rel`：相关读按写身份的积；`reduced`：S3 值维压缩后的枚举积。",
        "",
        "| 程序 | loads | Cl | id | val | Sync | full | naive_rel | reduced | S3↓ | saved | out | T2 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for r in rows:
        t2 = "✓" if r["props_ok"] and r["outcomes_ok"] else "✗"
        lines.append(
            f"| `{r['program']}` | {r['loads']} | {r['cl_reads']} | {r['id_dims']} | "
            f"{r['val_dims']} | {r['sync_deps']} | {r['full']} | {r['naive_rel']} | "
            f"{r['reduced']} | {r['s3_ratio']} | {r['saved_ratio']} | {r['outcomes']} | {t2} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-results", action="store_true")
    args = parser.parse_args()

    manifest = json.loads((ROOT / "examples" / "manifest.json").read_text(encoding="utf-8"))
    paths = [ROOT / "examples" / name for name in manifest]
    rows = [row_for(p) for p in paths]
    md = to_markdown(rows)
    print(md)

    if args.write_results:
        out = ROOT / "results"
        out.mkdir(exist_ok=True)
        (out / "phd_experiment_table.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (out / "phd_experiment_table.md").write_text(md, encoding="utf-8")
        print(f"已写入 {out / 'phd_experiment_table.md'}")


if __name__ == "__main__":
    main()
