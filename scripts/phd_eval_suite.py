#!/usr/bin/env python3
"""S5 博士评测套件：分类基准、全枚举/约简/S3 对照、失败谱。

  python3 scripts/phd_eval_suite.py --write-results
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from weak_memory_verifier import (
    analyze_program,
    compare_reduction,
    compute_relevance_closure,
    load_program,
)


def _load_taxonomy() -> Dict[str, dict]:
    return json.loads((ROOT / "examples" / "taxonomy.json").read_text(encoding="utf-8"))


def _category_of(name: str, taxonomy: Dict[str, dict]) -> str:
    for cat, spec in taxonomy.items():
        if name in spec["programs"]:
            return cat
    return "other"


def _weak_flags(path: Path) -> Dict[str, bool]:
    """记录若干典型弱态/错误是否在全量执行中出现（失败谱用）。"""
    full = analyze_program(path, reduction="none")
    mp_weak = any(
        exe.envs.get(1, {}).get("f") == 1 and exe.envs.get(1, {}).get("r") == 0
        for exe in full.executions
    )
    sb00 = any(
        exe.envs.get(0, {}).get("a") == 0 and exe.envs.get(1, {}).get("b") == 0
        for exe in full.executions
    )
    lb11 = any(
        exe.envs.get(0, {}).get("a") == 1 and exe.envs.get(1, {}).get("b") == 1
        for exe in full.executions
    )
    has_race = any(exe.races for exe in full.executions)
    has_assert = any(exe.failed_assertions for exe in full.executions)
    return {
        "mp_weak_f1r0": mp_weak,
        "sb_00": sb00,
        "lb_11": lb11,
        "has_race": has_race,
        "has_assert_fail": has_assert,
    }


def row_for(path: Path, taxonomy: Dict[str, dict]) -> Dict[str, object]:
    cmp_s3 = compare_reduction(path, edge_prune="value")
    cmp_off = compare_reduction(path, edge_prune="off")
    if not (cmp_s3["props_ok"] and cmp_s3["outcomes_ok"]):
        raise SystemExit(f"T2⁺⁺ 失败 (S3 on): {path.name}")
    if not (cmp_off["props_ok"] and cmp_off["outcomes_ok"]):
        raise SystemExit(f"T2⁺⁺ 失败 (S3 off): {path.name}")

    program = load_program(path)
    closure = compute_relevance_closure(program, ind_mode="promote")
    full = int(cmp_s3["full_stats"]["full_candidate_assignments"])
    red_s3 = int(cmp_s3["reduced_stats"]["explored_candidate_assignments"])
    red_off = int(cmp_off["reduced_stats"]["explored_candidate_assignments"])
    naive = int(cmp_s3["reduced_stats"].get("naive_relevant_product", red_off))
    weak = _weak_flags(path)

    return {
        "program": path.name,
        "category": _category_of(path.name, taxonomy),
        "loads": int(cmp_s3["full_stats"]["total_loads"]),
        "cl_reads": len(closure.relevant_reads),
        "id_dims": len(closure.identity_reads),
        "val_dims": len(closure.value_reads),
        "sync_deps": len(closure.sync_deps),
        "full": full,
        "reduced_s3": red_s3,
        "reduced_no_s3": red_off,
        "naive_rel": naive,
        "saved_vs_full": round(0.0 if full == 0 else (full - red_s3) / full, 4),
        "s3_extra": round(0.0 if red_off == 0 else (red_off - red_s3) / red_off, 4),
        "outcomes": cmp_s3["full_outcomes"],
        "props_ok": cmp_s3["props_ok"],
        "outcomes_ok": cmp_s3["outcomes_ok"],
        "is_racy": cmp_s3["full_summary"]["is_racy"],
        "assertion_can_fail": cmp_s3["full_summary"]["assertion_can_fail"],
        **weak,
    }


def _agg_saved(rows: List[Dict[str, object]]) -> Dict[str, object]:
    if not rows:
        return {"n": 0}
    saved = [float(r["saved_vs_full"]) for r in rows]
    s3ex = [float(r["s3_extra"]) for r in rows]
    return {
        "n": len(rows),
        "mean_saved_vs_full": round(statistics.mean(saved), 4),
        "median_saved_vs_full": round(statistics.median(saved), 4),
        "mean_s3_extra": round(statistics.mean(s3ex), 4),
        "max_full": max(int(r["full"]) for r in rows),
        "t2_all_ok": all(r["props_ok"] and r["outcomes_ok"] for r in rows),
    }


def build_report(rows: List[Dict[str, object]], taxonomy: Dict[str, dict]) -> str:
    by_cat: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for r in rows:
        by_cat[str(r["category"])].append(r)

    lines = [
        "# 博士评测套件（S5）",
        "",
        "分类见 `examples/taxonomy.json`。理论：[THEORY-v1](../docs/phd/THEORY-v1.md)、"
        "[RC11-ALIGNMENT](../docs/phd/RC11-ALIGNMENT.md)。",
        "",
        "## 1. 总览",
        "",
        f"- 程序数：{len(rows)}",
        f"- T2⁺⁺ 全部通过：{'是' if all(r['props_ok'] and r['outcomes_ok'] for r in rows) else '否'}",
        f"- 可 race：{sum(1 for r in rows if r['is_racy'])}",
        f"- 断言可败：{sum(1 for r in rows if r['assertion_can_fail'])}",
        f"- 相对全枚举平均缩减：{_agg_saved(rows)['mean_saved_vs_full']}",
        f"- 相对「无 S3 约简」平均再降：{_agg_saved(rows)['mean_s3_extra']}",
        "",
        "## 2. 分类汇总",
        "",
        "| 类别 | n | 均 saved(vs full) | 均 S3 额外↓ | max full | T2 |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for cat, spec in taxonomy.items():
        agg = _agg_saved(by_cat.get(cat, []))
        if agg["n"] == 0:
            continue
        lines.append(
            f"| {spec['title']} (`{cat}`) | {agg['n']} | {agg['mean_saved_vs_full']} | "
            f"{agg['mean_s3_extra']} | {agg['max_full']} | "
            f"{'✓' if agg['t2_all_ok'] else '✗'} |"
        )

    lines += [
        "",
        "## 3. 全量明细（基线=full，约简=S3 on，对照=S3 off）",
        "",
        "| 程序 | 类 | full | noS3 | S3 | saved | S3↓ | out | racy | assert |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for r in rows:
        lines.append(
            f"| `{r['program']}` | {r['category']} | {r['full']} | {r['reduced_no_s3']} | "
            f"{r['reduced_s3']} | {r['saved_vs_full']} | {r['s3_extra']} | {r['outcomes']} | "
            f"{r['is_racy']} | {r['assertion_can_fail']} |"
        )

    # 失败谱
    race_progs = [r["program"] for r in rows if r["is_racy"]]
    assert_progs = [r["program"] for r in rows if r["assertion_can_fail"]]
    mp_weak = [r["program"] for r in rows if r["mp_weak_f1r0"]]
    sb_weak = [r["program"] for r in rows if r["sb_00"]]
    lb_weak = [r["program"] for r in rows if r["lb_11"]]
    safe_mp = [
        r["program"]
        for r in rows
        if r["category"] in {"MP_RA", "MP_fence_SC"}
        and not r["mp_weak_f1r0"]
        and r["program"].startswith(("message_passing", "mp_sc", "rs_", "mp_ra_dup"))
    ]

    lines += [
        "",
        "## 4. 失败谱 / 弱态谱",
        "",
        "下列均在**全量**执行上统计；约简模式经 `compare_reduction` 保持布尔性质与观察结局。",
        "",
        f"- **data race 可出现**：{', '.join(f'`{p}`' for p in race_progs) or '（无）'}",
        f"- **断言可失败**：{', '.join(f'`{p}`' for p in assert_progs) or '（无）'}",
        f"- **MP 弱态 f=1,r=0**：{', '.join(f'`{p}`' for p in mp_weak) or '（无）'}",
        f"- **SB (0,0)**：{', '.join(f'`{p}`' for p in sb_weak) or '（无）'}",
        f"- **LB (1,1)**：{', '.join(f'`{p}`' for p in lb_weak) or '（无）'}",
        "",
        "### 4.1 不漏报抽检（约简后仍检出）",
        "",
        "| 性质 | 代表程序 | 全量 |",
        "| --- | --- | --- |",
        f"| race | `racy_counter_with_noise.json` | {'有' if any(r['program']=='racy_counter_with_noise.json' and r['has_race'] for r in rows) else '无'} |",
        f"| assert 弱态 | `mp_relaxed_with_noise.json` | {'有' if any(r['program']=='mp_relaxed_with_noise.json' and r['mp_weak_f1r0'] for r in rows) else '无'} |",
        f"| SB (0,0) | `sb_with_noise.json` | {'有' if any(r['program']=='sb_with_noise.json' and r['sb_00'] for r in rows) else '无'} |",
    ]

    # 规模曲线焦点
    scale_rows = [r for r in rows if r["category"] == "scale_noise"]
    lines += [
        "",
        "## 5. 规模曲线焦点（scale_noise）",
        "",
        "| 程序 | full | S3 reduced | saved |",
        "| --- | ---: | ---: | ---: |",
    ]
    for r in sorted(scale_rows, key=lambda x: int(x["full"])):
        lines.append(
            f"| `{r['program']}` | {r['full']} | {r['reduced_s3']} | {r['saved_vs_full']} |"
        )

    lines += [
        "",
        "## 6. 读表说明（论文第 6 章）",
        "",
        "1. **基线**：`full` = 全部读的 rf 笛卡尔积规模。",
        "2. **相关约简（无 S3）**：`reduced_no_s3` = 只枚举相关读、按写身份。",
        "3. **S3**：`reduced_s3` = 相关读上再按值维压缩。",
        "4. **正确性**：所有行 `props_ok ∧ outcomes_ok`；失败谱在约简后不消失（见 smoke）。",
        "5. **威胁效度**：教具 JSON、存在性 mo/SC；结论相对于本子集语义。",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="S5 博士评测套件")
    parser.add_argument("--write-results", action="store_true")
    args = parser.parse_args()

    taxonomy = _load_taxonomy()
    manifest = json.loads((ROOT / "examples" / "manifest.json").read_text(encoding="utf-8"))
    # 保证 taxonomy 覆盖 manifest
    tax_progs: Set[str] = set()
    for spec in taxonomy.values():
        tax_progs.update(spec["programs"])
    missing = [n for n in manifest if n not in tax_progs]
    if missing:
        raise SystemExit(f"taxonomy 未覆盖: {missing}")

    rows = [row_for(ROOT / "examples" / name, taxonomy) for name in manifest]
    # 稳定排序：按 category 再按名字
    cat_order = list(taxonomy.keys())
    rows.sort(
        key=lambda r: (
            cat_order.index(r["category"]) if r["category"] in cat_order else 99,
            str(r["program"]),
        )
    )
    md = build_report(rows, taxonomy)
    print(md)

    if args.write_results:
        out = ROOT / "results"
        out.mkdir(exist_ok=True)
        payload = {"taxonomy": taxonomy, "rows": rows, "aggregate": _agg_saved(rows)}
        (out / "phd_eval_suite.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (out / "phd_eval_suite.md").write_text(md, encoding="utf-8")
        # 同步简化表给旧入口
        simple = []
        for r in rows:
            simple.append(
                {
                    "program": r["program"],
                    "category": r["category"],
                    "loads": r["loads"],
                    "cl_reads": r["cl_reads"],
                    "id_dims": r["id_dims"],
                    "val_dims": r["val_dims"],
                    "sync_deps": r["sync_deps"],
                    "full": r["full"],
                    "naive_rel": r["naive_rel"],
                    "reduced": r["reduced_s3"],
                    "saved_ratio": r["saved_vs_full"],
                    "s3_ratio": r["s3_extra"],
                    "outcomes": r["outcomes"],
                    "props_ok": r["props_ok"],
                    "outcomes_ok": r["outcomes_ok"],
                    "is_racy": r["is_racy"],
                    "assertion_can_fail": r["assertion_can_fail"],
                }
            )
        (out / "phd_experiment_table.json").write_text(
            json.dumps(simple, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"已写入 {out / 'phd_eval_suite.md'} 与 phd_eval_suite.json")


if __name__ == "__main__":
    main()
