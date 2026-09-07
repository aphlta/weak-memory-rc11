#!/usr/bin/env python3
"""全量 vs 约简的墙钟时间曲线（重复取中位数）。

论文实验用：固定程序列表上分别计时 reduction=none / relevant，
默认重复 5 次，写 results/timing_curve.{json,md}。

  python3 scripts/bench_timing.py
  python3 scripts/bench_timing.py --repeats 7 --write-results
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from weak_memory_verifier import analyze_program, compare_reduction


# 默认：规模曲线 + 会失败的噪声例（错误发现不漏报）
DEFAULT_CASES = [
    "scale_mp_ra_noise_4.json",
    "scale_mp_ra_noise_5.json",
    "scale_mp_ra_noise_6.json",
    "scale_mp_ra_noise_7.json",
    "mp_relaxed_with_noise.json",
    "mp_relaxed_noise_assert.json",
    "racy_counter_with_noise.json",
]


def _median_ms(samples: List[float]) -> float:
    return round(statistics.median(samples), 3)


def time_one(path: Path, reduction: str, repeats: int) -> Dict[str, object]:
    samples: List[float] = []
    last_stats = None
    for _ in range(repeats):
        t0 = time.perf_counter()
        result = analyze_program(path, reduction=reduction)
        samples.append((time.perf_counter() - t0) * 1000.0)
        last_stats = result.stats
    assert last_stats is not None
    return {
        "median_ms": _median_ms(samples),
        "min_ms": round(min(samples), 3),
        "max_ms": round(max(samples), 3),
        "samples_ms": [round(x, 3) for x in samples],
        "explored": last_stats["explored_candidate_assignments"],
        "full_candidates": last_stats["full_candidate_assignments"],
        "relevant_loads": last_stats["relevant_loads"],
        "kept_executions": last_stats["kept_executions"],
    }


def run_case(path: Path, repeats: int) -> Dict[str, object]:
    cmp = compare_reduction(path)
    if not cmp["props_ok"] or not cmp["outcomes_ok"]:
        raise SystemExit(
            f"T2 失败: {path.name} props={cmp['props_ok']} outcomes={cmp['outcomes_ok']}"
        )
    full = time_one(path, "none", repeats)
    reduced = time_one(path, "relevant", repeats)
    speedup = None
    if reduced["median_ms"] and full["median_ms"]:
        speedup = round(float(full["median_ms"]) / float(reduced["median_ms"]), 3)
    return {
        "program": path.name,
        "repeats": repeats,
        "props_ok": cmp["props_ok"],
        "outcomes_ok": cmp["outcomes_ok"],
        "is_racy": cmp["full_summary"]["is_racy"],
        "assertion_can_fail": cmp["full_summary"]["assertion_can_fail"],
        "outcome_count": cmp["full_outcomes"],
        "full": full,
        "reduced": reduced,
        "speedup_median": speedup,
        "saved_ratio": cmp["full_stats"]["full_candidate_assignments"]
        and round(
            1
            - int(cmp["reduced_stats"]["explored_candidate_assignments"])
            / int(cmp["full_stats"]["full_candidate_assignments"]),
            4,
        ),
    }


def to_markdown(rows: List[Dict[str, object]]) -> str:
    lines = [
        "# 全量 vs 约简时间曲线",
        "",
        f"重复次数 = 各行 `repeats`；时间为 `analyze_program` 墙钟中位数（ms）。",
        "",
        "| 程序 | full组合 | reduced组合 | saved | full中位ms | reduced中位ms | 加速比 | racy | assert可败 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['program']}` | {row['full']['full_candidates']} | "
            f"{row['reduced']['explored']} | {row['saved_ratio']} | "
            f"{row['full']['median_ms']} | {row['reduced']['median_ms']} | "
            f"{row['speedup_median']} | {row['is_racy']} | {row['assertion_can_fail']} |"
        )
    lines.append("")
    lines.append(
        "说明：加速比 = full中位 / reduced中位。"
        "教具规模下约简开销（存在性扩展）有时会抵消组合收益；"
        "主结论仍以组合数缩减 + T2 保持为准。"
    )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="约简前后时间曲线")
    parser.add_argument("--repeats", type=int, default=5, help="每配置重复次数")
    parser.add_argument(
        "--write-results",
        action="store_true",
        help="写入 results/timing_curve.json 与 .md",
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        type=Path,
        help="可选：指定 JSON；默认用内置规模+漏报检查列表",
    )
    args = parser.parse_args()

    if args.inputs:
        paths = [p if p.is_absolute() else ROOT / p for p in args.inputs]
    else:
        paths = [ROOT / "examples" / name for name in DEFAULT_CASES]

    rows = [run_case(path, args.repeats) for path in paths]
    print(to_markdown(rows))

    if args.write_results:
        out = ROOT / "results"
        out.mkdir(exist_ok=True)
        (out / "timing_curve.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (out / "timing_curve.md").write_text(to_markdown(rows), encoding="utf-8")
        print(f"已写入 {out / 'timing_curve.json'} 与 timing_curve.md")


if __name__ == "__main__":
    main()
