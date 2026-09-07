#!/usr/bin/env python3
"""教具例子的性质回归（R3/T2：观察结局集合 + IND 可检查）。"""
from pathlib import Path

from weak_memory_verifier import (
    analyze_program,
    compare_reduction,
    compute_relevance_closure,
    explain_relevant_loads,
    load_program,
    outcome_set,
    relevant_loads,
    summarize,
)


ROOT = Path(__file__).resolve().parent


def _has_env(exe, tid: int, expected: dict) -> bool:
    env = exe.envs.get(tid, {})
    return all(env.get(name) == value for name, value in expected.items())


def _has_pair(exe, t0: dict, t1: dict) -> bool:
    return _has_env(exe, 0, t0) and _has_env(exe, 1, t1)


def main() -> None:
    expectations = {
        "message_passing.json": {"is_racy": False, "assertion_can_fail": False},
        "message_passing_with_irrelevant_load.json": {
            "is_racy": False,
            "assertion_can_fail": False,
        },
        "racy_counter.json": {"is_racy": True, "assertion_can_fail": True},
        "coherence_rr.json": {"is_racy": False, "assertion_can_fail": False},
        "coherence_rw.json": {"is_racy": False, "assertion_can_fail": False},
        "mp_relaxed.json": {"is_racy": False, "assertion_can_fail": True},
        "mp_sc_fence.json": {"is_racy": False, "assertion_can_fail": False},
        "rs_message_passing.json": {"is_racy": False, "assertion_can_fail": False},
        "rmw_adjacent.json": {"is_racy": False, "assertion_can_fail": False},
        "sb_relaxed.json": {"is_racy": False, "assertion_can_fail": False},
        "sb_seq_cst.json": {"is_racy": False, "assertion_can_fail": False},
        "mp_sc_fence_with_irrelevant_load.json": {
            "is_racy": False,
            "assertion_can_fail": False,
        },
        "sb_sc_with_irrelevant_load.json": {
            "is_racy": False,
            "assertion_can_fail": False,
        },
        "mp_two_noise.json": {"is_racy": False, "assertion_can_fail": False},
        "mp_triple_noise.json": {"is_racy": False, "assertion_can_fail": False},
        "sb_with_noise.json": {"is_racy": False, "assertion_can_fail": False},
        "rs_mp_with_noise.json": {"is_racy": False, "assertion_can_fail": False},
        # E2 规模实验：由 scripts/gen_scale_benchmarks.py 生成
        "scale_mp_ra_noise_4.json": {"is_racy": False, "assertion_can_fail": False},
        "scale_mp_ra_noise_5.json": {"is_racy": False, "assertion_can_fail": False},
        "scale_mp_ra_noise_6.json": {"is_racy": False, "assertion_can_fail": False},
        "scale_mp_ra_noise_7.json": {"is_racy": False, "assertion_can_fail": False},
        "scale_mp_fence_noise_4.json": {"is_racy": False, "assertion_can_fail": False},
        "scale_mp_fence_noise_5.json": {"is_racy": False, "assertion_can_fail": False},
        "scale_mp_fence_noise_6.json": {"is_racy": False, "assertion_can_fail": False},
        "scale_sb_noise_2.json": {"is_racy": False, "assertion_can_fail": False},
        "scale_sb_noise_3.json": {"is_racy": False, "assertion_can_fail": False},
        "scale_sb_noise_4.json": {"is_racy": False, "assertion_can_fail": False},
        "scale_lb_noise_2.json": {"is_racy": False, "assertion_can_fail": False},
        "scale_lb_noise_3.json": {"is_racy": False, "assertion_can_fail": False},
        "scale_lb_noise_4.json": {"is_racy": False, "assertion_can_fail": False},
        # T2/C：IND 违例例（promote 后仍保持结局；不要求 shrink）
        "cex_entangled_after_acquire.json": {"is_racy": False, "assertion_can_fail": False},
        "cex_shared_loc.json": {"is_racy": False, "assertion_can_fail": False},
        # 错误发现：噪声下仍能报 assert/race
        "mp_relaxed_with_noise.json": {"is_racy": False, "assertion_can_fail": True},
        "mp_relaxed_noise_assert.json": {"is_racy": False, "assertion_can_fail": True},
        "racy_counter_with_noise.json": {"is_racy": True, "assertion_can_fail": True},
        "lb_relaxed.json": {"is_racy": False, "assertion_can_fail": False},
        "mp_ra_dup_writes.json": {"is_racy": False, "assertion_can_fail": False},
    }

    shrink_examples = {
        "message_passing_with_irrelevant_load.json",
        "mp_sc_fence_with_irrelevant_load.json",
        "sb_sc_with_irrelevant_load.json",
        "mp_two_noise.json",
        "mp_triple_noise.json",
        "sb_with_noise.json",
        "rs_mp_with_noise.json",
        "scale_mp_ra_noise_4.json",
        "scale_mp_ra_noise_5.json",
        "scale_mp_ra_noise_6.json",
        "scale_mp_ra_noise_7.json",
        "scale_mp_fence_noise_4.json",
        "scale_mp_fence_noise_5.json",
        "scale_mp_fence_noise_6.json",
        "scale_sb_noise_2.json",
        "scale_sb_noise_3.json",
        "scale_sb_noise_4.json",
        "scale_lb_noise_2.json",
        "scale_lb_noise_3.json",
        "scale_lb_noise_4.json",
        "mp_relaxed_with_noise.json",
        "mp_relaxed_noise_assert.json",
        "racy_counter_with_noise.json",
        "mp_ra_dup_writes.json",
    }

    for name, expected in expectations.items():
        path = ROOT / "examples" / name
        cmp = compare_reduction(path)
        if not cmp["props_ok"]:
            raise SystemExit(f"R3 props 失败: {name} {cmp}")
        if not cmp["outcomes_ok"]:
            raise SystemExit(
                f"R3 outcomes 失败: {name} missing={cmp['missing_outcomes']} "
                f"extra={cmp['extra_outcomes']}"
            )

        full = analyze_program(path, reduction="none")
        reduced = analyze_program(path, reduction="relevant")
        full_summary = summarize(full.program, full.executions)

        for key, value in expected.items():
            if full_summary[key] != value:
                raise SystemExit(
                    f"smoke check failed for {name}: {key}={full_summary[key]}, expected={value}"
                )

        if name == "coherence_rr.json":
            if any(
                _has_env(exe, 1, {"r1": 2, "r2": 1}) or _has_env(exe, 1, {"r1": 2, "r2": 0})
                for exe in full.executions
            ):
                raise SystemExit("coherence_rr 仍留下先读 2 再读旧值")
        if name == "coherence_rw.json":
            if any(_has_env(exe, 2, {"b": 2, "c": 1}) for exe in full.executions):
                raise SystemExit("coherence_rw 仍留下先读 2 再读 1")
        if name == "mp_relaxed.json":
            if not any(_has_env(exe, 1, {"f": 1, "r": 0}) for exe in full.executions):
                raise SystemExit("mp_relaxed 应留下 flag=1 且 x=0 的弱态")
        if name == "mp_sc_fence.json":
            if any(_has_env(exe, 1, {"f": 1, "r": 0}) for exe in full.executions):
                raise SystemExit("mp_sc_fence 仍留下 fence 应杀掉的弱态")
        if name == "rs_message_passing.json":
            if any(_has_env(exe, 1, {"f": 2, "r": 0}) for exe in full.executions):
                raise SystemExit("rs_message_passing：读到 flag=2 仍应经 RS 同步看到 x=1")
        if name == "rmw_adjacent.json":
            for exe in full.executions:
                chain = exe.modification_order.get("x", [])
                for load_eid, write_eid in exe.read_from.items():
                    ev = full.program.events_by_eid[load_eid]
                    if ev.kind != "rmw":
                        continue
                    if chain.index(load_eid) != chain.index(write_eid) + 1:
                        raise SystemExit(f"rmw_adjacent: 不相邻 {chain}")
        if name == "sb_relaxed.json":
            if not any(_has_pair(exe, {"a": 0}, {"b": 0}) for exe in full.executions):
                raise SystemExit("sb_relaxed 应允许 (0,0) 弱态")
        if name == "sb_seq_cst.json":
            if any(_has_pair(exe, {"a": 0}, {"b": 0}) for exe in full.executions):
                raise SystemExit("sb_seq_cst 不应允许 (0,0)")
        if name == "sb_with_noise.json":
            if not any(_has_pair(exe, {"a": 0}, {"b": 0}) for exe in full.executions):
                raise SystemExit("sb_with_noise 应保留 (0,0)")
            if not any(_has_pair(exe, {"a": 0}, {"b": 0}) for exe in reduced.executions):
                raise SystemExit("sb_with_noise 约简后丢失 (0,0)")
        if name.startswith("scale_sb_noise_"):
            if not any(_has_pair(exe, {"a": 0}, {"b": 0}) for exe in full.executions):
                raise SystemExit(f"{name} 应保留 SB (0,0)")
            if not any(_has_pair(exe, {"a": 0}, {"b": 0}) for exe in reduced.executions):
                raise SystemExit(f"{name} 约简后丢失 SB (0,0)")
        if name.startswith("scale_lb_noise_"):
            # LB 弱态：两端都读到 1
            if not any(_has_pair(exe, {"a": 1}, {"b": 1}) for exe in full.executions):
                raise SystemExit(f"{name} 应允许 LB (1,1)")
            if not any(_has_pair(exe, {"a": 1}, {"b": 1}) for exe in reduced.executions):
                raise SystemExit(f"{name} 约简后丢失 LB (1,1)")
        if name.startswith("scale_mp_") and "noise" in name:
            if any(_has_env(exe, 1, {"f": 1, "r": 0}) for exe in full.executions):
                raise SystemExit(f"{name} RA/fence MP 不应留下 f=1,r=0")
        if name in {"mp_relaxed_with_noise.json", "mp_relaxed_noise_assert.json"}:
            if not any(_has_env(exe, 1, {"f": 1, "r": 0}) for exe in full.executions):
                raise SystemExit(f"{name} 全量应保留弱态 f=1,r=0")
            if not any(_has_env(exe, 1, {"f": 1, "r": 0}) for exe in reduced.executions):
                raise SystemExit(f"{name} 约简后漏报弱态 f=1,r=0")
        if name == "racy_counter_with_noise.json":
            if not any(exe.races for exe in full.executions):
                raise SystemExit("racy_counter_with_noise 全量应有 race")
            if not any(exe.races for exe in reduced.executions):
                raise SystemExit("racy_counter_with_noise 约简后漏报 race")
        if name == "lb_relaxed.json":
            if not any(_has_pair(exe, {"a": 1}, {"b": 1}) for exe in full.executions):
                raise SystemExit("lb_relaxed 应允许 (1,1)")
        if name == "mp_ra_dup_writes.json":
            if any(_has_env(exe, 1, {"f": 1, "r": 0}) for exe in full.executions):
                raise SystemExit("mp_ra_dup_writes 不应留下 f=1,r=0")
            if (
                reduced.stats["explored_candidate_assignments"]
                >= reduced.stats["naive_relevant_product"]
            ):
                raise SystemExit(
                    "mp_ra_dup_writes: S3 值维应小于按写枚举 "
                    f"{reduced.stats['explored_candidate_assignments']} vs "
                    f"{reduced.stats['naive_relevant_product']}"
                )

        if name in shrink_examples:
            if (
                reduced.stats["explored_candidate_assignments"]
                >= full.stats["full_candidate_assignments"]
            ):
                raise SystemExit(
                    f"{name}: 期望约简减少组合数 "
                    f"{full.stats['full_candidate_assignments']} -> "
                    f"{reduced.stats['explored_candidate_assignments']}"
                )

        print(
            f"[ok] {name}: full={full.stats['full_candidate_assignments']} "
            f"reduced={reduced.stats['explored_candidate_assignments']} "
            f"outcomes={cmp['full_outcomes']} observe={cmp['observe']}"
        )

    _check_ind_counterexamples()


def _check_ind_counterexamples() -> None:
    """T2/C：违例可检测；错误扩展会丢结局；refuse 回退全枚举。"""
    entangled = ROOT / "examples" / "cex_entangled_after_acquire.json"
    shared = ROOT / "examples" / "cex_shared_loc.json"

    prog = load_program(entangled)
    reasons = explain_relevant_loads(prog, ind_mode="promote")
    if not any(any(r.startswith("ind:") for r in rs) for rs in reasons.values()):
        raise SystemExit("cex_entangled：promote 应产生 ind: 理由")

    # off + first_candidate：丢掉 a=1（演示为何必须 exists 扩展 / IND 提升）
    full_out = outcome_set(
        prog, analyze_program(entangled, reduction="none").executions
    )
    naive = analyze_program(
        entangled, reduction="relevant", ind_mode="off", extend_mode="first_candidate"
    )
    naive_out = outcome_set(prog, naive.executions)
    if full_out <= naive_out:
        raise SystemExit(
            f"cex_entangled：期望 first_candidate 丢失结局，full={full_out} naive={naive_out}"
        )
    if (("a", 1),) not in (full_out - naive_out):
        raise SystemExit(f"cex_entangled：应丢失 a=1，missing={full_out - naive_out}")

    refused = analyze_program(entangled, reduction="relevant", ind_mode="refuse")
    if not refused.stats.get("ind_refused"):
        raise SystemExit("cex_entangled：refuse 应 ind_refused")
    if refused.stats.get("reduction") != "none":
        raise SystemExit("cex_entangled：refuse 应回退 reduction=none")

    shared_prog = load_program(shared)
    shared_reasons = explain_relevant_loads(shared_prog, ind_mode="promote")
    if not any(
        "shared with a base-relevant read" in r
        for rs in shared_reasons.values()
        for r in rs
    ):
        raise SystemExit("cex_shared_loc：promote 应提升同址伪噪声")

    print("[ok] ind-counterexamples: promote / refuse / first_candidate")
    _check_relevance_closure()


def _check_relevance_closure() -> None:
    """THEORY-v1：闭包读集合与 relevant_loads 一致；MP 含同步依赖边。"""
    path = ROOT / "examples" / "message_passing.json"
    program = load_program(path)
    closure = compute_relevance_closure(program, ind_mode="promote")
    rel = relevant_loads(program, ind_mode="promote")
    if closure.relevant_reads != rel:
        raise SystemExit(
            f"闭包读集合不一致: {sorted(closure.relevant_reads)} vs {sorted(rel)}"
        )
    if set(closure.rf_dimensions) != rel:
        raise SystemExit("rf_dimensions 应等于相关读集合（S2）")
    if not closure.sync_deps:
        raise SystemExit("message_passing 应有潜在 SyncDep 边")
    if "t1:0" not in closure.identity_reads:
        raise SystemExit("acquire 读应属 identity 维")
    if "t1:1" not in closure.value_reads:
        raise SystemExit("relaxed 数据读应属 value 维（S3）")
    # S3 守门：若错误把 acquire 当 value 维，会破坏结局；对照 edge_prune=off 应更大
    from weak_memory_verifier import analyze_program as _ap

    pruned = _ap(path, reduction="relevant", edge_prune="value")
    naive = _ap(path, reduction="relevant", edge_prune="off")
    if pruned.stats["explored_candidate_assignments"] > naive.stats["explored_candidate_assignments"]:
        raise SystemExit("S3 value 剪枝不应增大枚举")
    print(
        f"[ok] relevance-closure: |Cl_read|={len(closure.relevant_reads)} "
        f"|SyncDep|={len(closure.sync_deps)} "
        f"id={closure.identity_reads} val={closure.value_reads}"
    )


if __name__ == "__main__":
    main()
