#!/usr/bin/env python3
"""约简前后的组合数对比与批量统计。

读 examples/manifest.json（若存在），否则扫 examples/*.json。
输出表格，并可写入 results/benchmark_results.{json,md}。
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Dict, List

from weak_memory_verifier import compare_reduction


ROOT = Path(__file__).resolve().parent


def compare_one(path: Path) -> Dict[str, object]:
    t0 = time.perf_counter()
    from weak_memory_verifier import compare_reduction

    cmp = compare_reduction(path)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    if not cmp["props_ok"] or not cmp["outcomes_ok"]:
        raise SystemExit(
            f"R3 约简不保持性质/结局: {path.name} "
            f"props_ok={cmp['props_ok']} outcomes_ok={cmp['outcomes_ok']} "
            f"missing={cmp['missing_outcomes']}"
        )

    full_total = int(cmp["full_stats"]["full_candidate_assignments"])
    reduced_total = int(cmp["reduced_stats"]["explored_candidate_assignments"])
    saved = full_total - reduced_total
    saved_ratio = 0.0 if full_total == 0 else saved / full_total
    full_summary = cmp["full_summary"]

    return {
        "program": path.name,
        "total_loads": cmp["full_stats"]["total_loads"],
        "relevant_loads": cmp["reduced_stats"]["relevant_loads"],
        "full_candidate_assignments": full_total,
        "reduced_candidate_assignments": reduced_total,
        "saved_assignments": saved,
        "saved_ratio": round(saved_ratio, 4),
        "kept_executions": cmp["reduced_stats"]["kept_executions"],
        "is_racy": full_summary["is_racy"],
        "assertion_can_fail": full_summary["assertion_can_fail"],
        "executions_with_race": full_summary["executions_with_race"],
        "executions_with_assertion_failure": full_summary[
            "executions_with_assertion_failure"
        ],
        "observe": cmp["observe"],
        "outcome_count": cmp["full_outcomes"],
        "outcomes_ok": cmp["outcomes_ok"],
        "elapsed_ms": round(elapsed_ms, 3),
    }


def print_table(rows: List[Dict[str, object]]) -> None:
    headers = [
        ("program", 42),
        ("total_loads", 11),
        ("relevant", 10),
        ("full", 10),
        ("reduced", 10),
        ("saved", 10),
        ("ratio", 8),
        ("racy", 6),
        ("assert", 8),
        ("ms", 8),
    ]
    line = " ".join(name.ljust(width) for name, width in headers)
    print(line)
    print("-" * len(line))
    for row in rows:
        print(
            f"{row['program'][:42].ljust(42)} "
            f"{str(row['total_loads']).ljust(11)} "
            f"{str(row['relevant_loads']).ljust(10)} "
            f"{str(row['full_candidate_assignments']).ljust(10)} "
            f"{str(row['reduced_candidate_assignments']).ljust(10)} "
            f"{str(row['saved_assignments']).ljust(10)} "
            f"{str(row['saved_ratio']).ljust(8)} "
            f"{str(row['is_racy']).ljust(6)} "
            f"{str(row['assertion_can_fail']).ljust(8)} "
            f"{str(row['elapsed_ms']).ljust(8)}"
        )


def to_markdown(rows: List[Dict[str, object]]) -> str:
    lines = [
        "# benchmark 结果（R3）",
        "",
        "| 程序 | loads | relevant | full | reduced | saved | ratio | outcomes | racy | assert | ms |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['program']}` | {row['total_loads']} | {row['relevant_loads']} | "
            f"{row['full_candidate_assignments']} | {row['reduced_candidate_assignments']} | "
            f"{row['saved_assignments']} | {row['saved_ratio']} | {row['outcome_count']} | "
            f"{row['is_racy']} | {row['assertion_can_fail']} | {row['elapsed_ms']} |"
        )
    lines.append("")
    lines.append(
        "R3/T2：约简前后 `props_ok` 与观察结局集合一致（见 `docs/REDUCTION.md`）。"
        "时间曲线见 `results/timing_curve.md`。仍是单芯片 RC11 核心子集。"
    )
    lines.append("")
    return "\n".join(lines)


def resolve_inputs(inputs: List[Path]) -> List[Path]:
    if inputs:
        return inputs
    manifest = ROOT / "examples" / "manifest.json"
    if manifest.is_file():
        names = json.loads(manifest.read_text(encoding="utf-8"))
        return [ROOT / "examples" / name for name in names]
    return sorted((ROOT / "examples").glob("*.json"))


def main() -> None:
    parser = argparse.ArgumentParser(description="比较弱内存原型在约简前后的组合数差异")
    parser.add_argument(
        "inputs",
        nargs="*",
        type=Path,
        help="待比较的 JSON 程序；不传则用 manifest 或 examples 全部",
    )
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    parser.add_argument(
        "--write-results",
        action="store_true",
        help="写入 results/benchmark_results.json 与 .md",
    )
    args = parser.parse_args()

    paths = resolve_inputs(args.inputs)
    rows = [compare_one(path) for path in paths]

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        print_table(rows)

    if args.write_results:
        out_dir = ROOT / "results"
        out_dir.mkdir(exist_ok=True)
        (out_dir / "benchmark_results.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (out_dir / "benchmark_results.md").write_text(to_markdown(rows), encoding="utf-8")
        print(f"\n已写入 {out_dir / 'benchmark_results.json'} 与 benchmark_results.md")


if __name__ == "__main__":
    main()
