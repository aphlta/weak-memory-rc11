#!/usr/bin/env python3
"""单芯片 RC11 核心子集的执行图枚举器。

覆盖：RA sw、存在性 mo、fence 同步、release sequence、简化 RMW、
SC 存在性全序、可解释 relevant-load。仍不是完整 C11（无 consume / thin-air）。

CLI 约定保持根目录 `python3 weak_memory_verifier.py ...`。
语义边界见 docs/ARCHITECTURE.md。
"""
from __future__ import annotations

import argparse
import itertools
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple


ATOMIC_ORDERS = {"relaxed", "acquire", "release", "acq_rel", "seq_cst"}
FENCE_ORDERS = {"acquire", "release", "acq_rel", "seq_cst"}
RELEASE_ORDERS = {"release", "acq_rel", "seq_cst"}
ACQUIRE_ORDERS = {"acquire", "acq_rel", "seq_cst"}


@dataclass(frozen=True)
class Event:
    """一条程序事件。

    不加 die_id / scope 等扩展字段：当前模型是单一共享内存上的线程事件。
    RMW 同时是读和写；fence 无 loc，只参与 po / sw / SC。
    """

    eid: str
    thread: int
    index: int
    kind: str
    loc: Optional[str] = None
    value: Optional[int] = None
    target: Optional[str] = None
    right: Optional[object] = None
    atomic: bool = False
    order: Optional[str] = None
    guard: Optional[Dict[str, int]] = None

    @property
    def is_memory(self) -> bool:
        return self.kind in {"load", "store", "rmw"}

    @property
    def is_write(self) -> bool:
        return self.kind in {"store", "rmw"}

    @property
    def is_read(self) -> bool:
        return self.kind in {"load", "rmw"}

    @property
    def is_fence(self) -> bool:
        return self.kind == "fence"

    @property
    def is_initial(self) -> bool:
        return self.thread < 0

    @property
    def is_release(self) -> bool:
        return bool(self.order and self.order in RELEASE_ORDERS)

    @property
    def is_acquire(self) -> bool:
        return bool(self.order and self.order in ACQUIRE_ORDERS)

    @property
    def is_seq_cst(self) -> bool:
        return self.order == "seq_cst"


@dataclass
class Program:
    """已展开的程序。writes_by_loc 含 initial 虚拟写。

    observe：结局投影用的线程局部变量名。约简的 R3 目标是
    全枚举与 relevant 约简在 observe 上的取值集合一致。
    """

    name: str
    initial_memory: Dict[str, int]
    threads: List[List[Event]]
    loads: List[Event]
    writes_by_loc: Dict[str, List[Event]]
    accesses: List[Event]
    events_by_eid: Dict[str, Event] = field(default_factory=dict)
    fences: List[Event] = field(default_factory=list)
    observe: List[str] = field(default_factory=list)
    observe_source: str = "all-load-targets"


@dataclass
class Execution:
    """一份 rf 赋值及其派生关系。

    modification_order / sc_order 都是存在性见证，不进 JSON 摘要。
    """

    read_from: Dict[str, str]
    envs: Dict[int, Dict[str, int]]
    synchronizes_with: Set[Tuple[str, str]]
    happens_before: Set[Tuple[str, str]]
    races: List[Tuple[str, str]]
    failed_assertions: List[Tuple[str, str]]
    modification_order: Dict[str, List[str]]
    sc_order: List[str] = field(default_factory=list)


@dataclass
class AnalysisResult:
    program: Program
    executions: List[Execution]
    stats: Dict[str, object]
    relevant_reasons: Dict[str, List[str]] = field(default_factory=dict)


def _normalize_order(kind: str, atomic: bool, order: Optional[str]) -> Optional[str]:
    """非原子无顺序；缺省原子当 relaxed。fence 必须带 acquire/release/acq_rel/seq_cst。"""
    if kind == "fence":
        if order is None:
            raise ValueError("fence 必须指定 order（acquire/release/acq_rel/seq_cst）")
        if order not in FENCE_ORDERS:
            raise ValueError(f"fence 不支持的顺序: {order}")
        return order
    if not atomic:
        return None
    if order is None:
        return "relaxed"
    if order not in ATOMIC_ORDERS:
        raise ValueError(f"不支持的原子顺序: {order}")
    if kind == "load" and order in {"release", "acq_rel"}:
        raise ValueError(f"load 不能使用顺序 {order}")
    if kind == "store" and order in {"acquire", "acq_rel"}:
        raise ValueError(f"store 不能使用顺序 {order}")
    if kind == "rmw" and order not in ATOMIC_ORDERS:
        raise ValueError(f"rmw 不支持的顺序: {order}")
    return order


def _derive_observe(spec: dict, threads: List[List[Event]], loads: List[Event]) -> Tuple[List[str], str]:
    """决定结局观察变量。

    优先级：
    1. JSON 显式 observe
    2. 否则从 assert_eq 的 left / right / when 收集
    3. 否则全部 load/rmw 的 target（保守：几乎无法约掉结局相关读）
    """
    if "observe" in spec:
        names = [str(x) for x in spec["observe"]]
        return names, "explicit"
    asserted: Set[str] = set()
    for events in threads:
        for event in events:
            if event.kind != "assert_eq":
                continue
            if event.target:
                asserted.add(event.target)
            if isinstance(event.right, str):
                asserted.add(event.right)
            if event.guard:
                asserted.update(event.guard.keys())
    if asserted:
        return sorted(asserted), "from-asserts"
    targets = sorted({load.target for load in loads if load.target})
    return targets, "all-load-targets"


def load_program(path: Path) -> Program:
    """JSON → Program。

    初值写成 thread=-1 的 store，让「读到 0」与「读到程序写」走同一套 rf。
    RMW 同时登记为 load 与 write。
    """
    spec = json.loads(path.read_text(encoding="utf-8"))
    name = spec.get("name", path.stem)
    initial_memory = spec.get("initial_memory", {})
    raw_threads = spec["threads"]

    threads: List[List[Event]] = []
    loads: List[Event] = []
    accesses: List[Event] = []
    fences: List[Event] = []
    writes_by_loc: Dict[str, List[Event]] = {}
    events_by_eid: Dict[str, Event] = {}

    for loc, value in initial_memory.items():
        init_event = Event(
            eid=f"init:{loc}",
            thread=-1,
            index=-1,
            kind="store",
            loc=loc,
            value=value,
            atomic=True,
            order="seq_cst",
        )
        writes_by_loc.setdefault(loc, []).append(init_event)
        events_by_eid[init_event.eid] = init_event

    for tid, raw_ops in enumerate(raw_threads):
        events: List[Event] = []
        for index, raw in enumerate(raw_ops):
            kind = raw["op"]
            atomic = bool(raw.get("atomic", kind in {"fence", "rmw"}))
            if kind == "fence":
                atomic = True
            if kind == "rmw":
                atomic = True
            order = _normalize_order(kind, atomic, raw.get("order"))
            event = Event(
                eid=f"t{tid}:{index}",
                thread=tid,
                index=index,
                kind=kind,
                loc=raw.get("loc"),
                value=raw.get("value"),
                target=raw.get("target") if kind != "assert_eq" else raw.get("left"),
                right=raw.get("right"),
                atomic=atomic,
                order=order,
                guard=raw.get("when"),
            )
            events.append(event)
            events_by_eid[event.eid] = event
            if event.kind == "load":
                if not event.loc or not event.target:
                    raise ValueError(f"{event.eid} 是 load，但缺少 loc 或 target")
                loads.append(event)
                accesses.append(event)
            elif event.kind == "store":
                if event.loc is None or event.value is None:
                    raise ValueError(f"{event.eid} 是 store，但缺少 loc 或 value")
                writes_by_loc.setdefault(event.loc, []).append(event)
                accesses.append(event)
            elif event.kind == "rmw":
                # 简化 RMW：读出旧值写入 target，再写入固定 value；不做 CAS 失败路径。
                if event.loc is None or event.value is None or not event.target:
                    raise ValueError(f"{event.eid} 是 rmw，但缺少 loc / value / target")
                loads.append(event)
                writes_by_loc.setdefault(event.loc, []).append(event)
                accesses.append(event)
            elif event.kind == "assert_eq":
                if event.target is None or event.right is None:
                    raise ValueError(f"{event.eid} 是 assert_eq，但缺少 left 或 right")
            elif event.kind == "fence":
                fences.append(event)
            else:
                raise ValueError(f"不支持的操作类型: {kind}")
        threads.append(events)

    observe, observe_source = _derive_observe(spec, threads, loads)

    return Program(
        name=name,
        initial_memory=initial_memory,
        threads=threads,
        loads=loads,
        writes_by_loc=writes_by_loc,
        accesses=accesses,
        events_by_eid=events_by_eid,
        fences=fences,
        observe=observe,
        observe_source=observe_source,
    )


def _program_order_edges(program: Program) -> Set[Tuple[str, str]]:
    edges: Set[Tuple[str, str]] = set()
    for events in program.threads:
        for left, right in itertools.combinations(events, 2):
            if left.index < right.index:
                edges.add((left.eid, right.eid))
    return edges


def _transitive_closure(edges: Iterable[Tuple[str, str]]) -> Set[Tuple[str, str]]:
    closure = set(edges)
    changed = True
    while changed:
        changed = False
        new_edges = {
            (a, d)
            for (a, b) in closure
            for (c, d) in closure
            if b == c and a != d and (a, d) not in closure
        }
        if new_edges:
            closure.update(new_edges)
            changed = True
    return closure


def _reads_from_candidates(program: Program, load: Event) -> List[Event]:
    """同地址写，去掉同线程里发生在该读之后的写。笛卡尔积只扫 rf。"""
    candidates = []
    for write in program.writes_by_loc.get(load.loc or "", []):
        if write.thread == load.thread and write.index > load.index:
            continue
        # RMW 不能读自己
        if write.eid == load.eid:
            continue
        candidates.append(write)
    return candidates


def _same_thread_po_before(a: Event, b: Event) -> bool:
    return a.thread == b.thread and a.thread >= 0 and a.index < b.index


def _release_sequence_heads(
    program: Program,
    write: Event,
) -> List[Event]:
    """写出 write 所属的 release sequence 的头（可能多个，通常一个）。

    简化 RC11 RS：
    - 每个 release/SC 写是自己的 RS 头
    - 同线程同址、po 之后的写属于该头的 RS
    - RMW 若读到某 RS 成员，也延长该 RS（在 sw 计算里用 rf 判定）
    """
    if write.is_initial:
        return []
    heads: List[Event] = []
    if write.is_write and write.atomic and write.is_release and write.kind != "fence":
        heads.append(write)

    # 同线程同址、po 之前的 release 写：write 落在其 RS 上
    for other in program.writes_by_loc.get(write.loc or "", []):
        if other.eid == write.eid or other.is_initial:
            continue
        if not (other.atomic and other.is_release and other.kind in {"store", "rmw"}):
            continue
        if _same_thread_po_before(other, write):
            heads.append(other)
    return heads


def _release_heads_for_write(
    program: Program,
    rf_map: Dict[str, Event],
    write: Event,
) -> List[Event]:
    """写出 write 能同步回的 release 头：自身 RS 头 + RMW 链延长的头。"""
    heads = list(_release_sequence_heads(program, write))
    seen = {h.eid for h in heads}
    if write.kind != "rmw":
        return heads

    # 沿 rf 回溯：RMW 读到 RS 成员时延长该 RS
    cur: Optional[Event] = write
    visited: Set[str] = set()
    while cur is not None and cur.eid not in visited:
        visited.add(cur.eid)
        for head in _release_sequence_heads(program, cur):
            if head.eid not in seen:
                seen.add(head.eid)
                heads.append(head)
        if cur.eid not in rf_map:
            break
        src = rf_map[cur.eid]
        for head in _release_sequence_heads(program, src):
            if head.eid not in seen:
                seen.add(head.eid)
                heads.append(head)
        cur = src if src.kind == "rmw" else None
    return heads


def _write_in_release_sequence(
    program: Program,
    rf_map: Dict[str, Event],
    head: Event,
    write: Event,
) -> bool:
    """write 是否落在以 head 为头的 release sequence 上。"""
    if write.eid == head.eid:
        return True
    if write.is_initial or head.is_initial:
        return False
    if write.loc != head.loc:
        return False
    if _same_thread_po_before(head, write):
        return True
    # RMW 读到 head 或其同线程后续写时，也算在 RS 上
    if write.kind == "rmw" and write.eid in rf_map:
        cur: Optional[Event] = write
        visited: Set[str] = set()
        while cur is not None and cur.eid not in visited:
            visited.add(cur.eid)
            if cur.eid == head.eid:
                return True
            if cur.loc == head.loc and _same_thread_po_before(head, cur):
                return True
            if cur.eid not in rf_map:
                break
            src = rf_map[cur.eid]
            if src.eid == head.eid:
                return True
            if src.loc == head.loc and _same_thread_po_before(head, src):
                return True
            cur = src if src.kind == "rmw" else None
    return False


def _compute_sync_with(
    program: Program,
    rf_map: Dict[str, Event],
) -> Set[Tuple[str, str]]:
    """RA + fence + release sequence 的 synchronizes-with。

    初值写不参与 sw（否则 hb 被撑成几乎全序）。
    """
    sync_with: Set[Tuple[str, str]] = set()
    po = _program_order_edges(program)

    # 1) release 写 / RS → acquire 读
    for load in program.loads:
        if load.eid not in rf_map or not (load.atomic and load.is_acquire):
            continue
        source = rf_map[load.eid]
        if source.is_initial:
            continue
        for head in _release_heads_for_write(program, rf_map, source):
            if _write_in_release_sequence(program, rf_map, head, source):
                sync_with.add((head.eid, load.eid))

    # 2) release fence FA -sw-> acquire 读 A：∃ 写 X，FA-po->X 且 A-rf->X
    for fence in program.fences:
        if not fence.is_release:
            continue
        for load in program.loads:
            if load.eid not in rf_map or not (load.atomic and load.is_acquire):
                continue
            source = rf_map[load.eid]
            if source.is_initial:
                continue
            if (fence.eid, source.eid) in po:
                sync_with.add((fence.eid, load.eid))

    # 3) release 写 R -sw-> acquire fence FB：∃ 读 Y，Y-rf 到 R（或 RS）且 Y-po->FB
    for fence in program.fences:
        if not fence.is_acquire:
            continue
        for load in program.loads:
            if load.eid not in rf_map or (load.eid, fence.eid) not in po:
                continue
            source = rf_map[load.eid]
            if source.is_initial:
                continue
            for head in _release_heads_for_write(program, rf_map, source):
                if _write_in_release_sequence(program, rf_map, head, source):
                    sync_with.add((head.eid, fence.eid))

    # 4) release fence FA -sw-> acquire fence FB：∃ X,Y FA-po->X, Y-rf->X, Y-po->FB
    for fa in program.fences:
        if not fa.is_release:
            continue
        for fb in program.fences:
            if not fb.is_acquire or fa.eid == fb.eid:
                continue
            for load in program.loads:
                if load.eid not in rf_map:
                    continue
                if (load.eid, fb.eid) not in po:
                    continue
                source = rf_map[load.eid]
                if source.is_initial:
                    continue
                if (fa.eid, source.eid) in po:
                    sync_with.add((fa.eid, fb.eid))

    return {(a, b) for a, b in sync_with if a != b}


def _release_prefix_locations(program: Program) -> Set[str]:
    """各线程上、某个 release/SC 写或 fence *之前*（含当时）写过的地址。

    这些写可能经 sw 进入 hb，从而约束同址后续读的 mo（T2 的 CritLoc 静态上近似）。
    """
    locs: Set[str] = set()
    for events in program.threads:
        prefix: Set[str] = set()
        for event in events:
            if event.is_write and event.loc:
                prefix.add(event.loc)
            commits = False
            if event.is_write and (event.is_release or event.is_seq_cst):
                commits = True
            if event.is_fence and (
                event.is_release or event.is_acquire or event.is_seq_cst
            ):
                commits = True
            if commits:
                locs |= prefix
    return locs


def _has_prior_acquire(events: Sequence[Event], index: int) -> bool:
    """同线程上、该下标之前是否已有 acquire/SC 读或 fence（可能已建立 sw）。"""
    for event in events[:index]:
        if event.is_read and (event.is_acquire or event.is_seq_cst):
            return True
        if event.is_fence and (event.is_acquire or event.is_seq_cst):
            return True
    return False


def ind_violation_reasons(
    program: Program, base_relevant: Set[str]
) -> Dict[str, List[str]]:
    """相对「仅四类基础相关」的 IND 违例：这些读若仍当无关，T2 假设不成立。

    静态规则（充分但不必要）：
    1. 与已相关读同址；
    2. 地址落入 release-prefix，且同线程先前已有 acquire/SC。
    """
    release_prefix = _release_prefix_locations(program)
    crit_locs = {
        program.events_by_eid[eid].loc
        for eid in base_relevant
        if program.events_by_eid[eid].loc
    }
    violations: Dict[str, List[str]] = {}
    for events in program.threads:
        for event in events:
            if not event.is_read or event.eid in base_relevant:
                continue
            reasons: List[str] = []
            if event.loc and event.loc in crit_locs:
                reasons.append(
                    f"ind: loc '{event.loc}' shared with a base-relevant read"
                )
            if (
                event.loc
                and event.loc in release_prefix
                and _has_prior_acquire(events, event.index)
            ):
                reasons.append(
                    f"ind: loc '{event.loc}' may gain hb from release-prefix "
                    "writes via a prior acquire on this thread"
                )
            if reasons:
                violations[event.eid] = reasons
    return violations


def explain_relevant_loads(
    program: Program, *, ind_mode: str = "promote"
) -> Dict[str, List[str]]:
    """相关性：outcome / assertion / synchronization / race，外加可选 IND 闭包。

    R3：target ∈ observe 的读必须展开，否则约简会丢掉弱态。
    T2：默认 ind_mode=promote，把 IND 违例读提升为相关，使定理假设在实现里可检查。
    """
    if ind_mode not in {"promote", "refuse", "off"}:
        raise ValueError(f"不支持的 ind_mode: {ind_mode}")

    reasons: Dict[str, List[str]] = {ev.eid: [] for tid in program.threads for ev in tid}
    observe = set(program.observe)

    for events in program.threads:
        needed_vars: Set[str] = set(observe)
        has_future_effect = False
        for event in reversed(events):
            if event.kind == "assert_eq":
                if event.target:
                    needed_vars.add(event.target)
                if isinstance(event.right, str):
                    needed_vars.add(event.right)
                if event.guard:
                    needed_vars.update(event.guard.keys())
                has_future_effect = True
                continue

            if event.kind in {"store", "fence", "rmw"}:
                if event.kind == "fence" and event.is_release:
                    has_future_effect = True
                elif event.kind == "store":
                    has_future_effect = True
                elif event.kind == "rmw":
                    has_future_effect = True
                if event.kind == "fence":
                    has_future_effect = True

            if event.is_read:
                if not event.atomic:
                    reasons[event.eid].append("race: non-atomic read must stay for DRF")
                if event.target and event.target in observe:
                    reasons[event.eid].append(
                        f"outcome: target '{event.target}' is in observe set"
                    )
                elif event.target and event.target in needed_vars:
                    reasons[event.eid].append(
                        f"assertion: value flows to assert/guard via '{event.target}'"
                    )
                if event.is_acquire and has_future_effect:
                    reasons[event.eid].append(
                        "synchronization: acquire/seq_cst read may enable later hb"
                    )
                if event.is_seq_cst:
                    reasons[event.eid].append(
                        "synchronization: seq_cst read participates in SC order / fr"
                    )
                if event.kind == "rmw" and has_future_effect:
                    reasons[event.eid].append(
                        "synchronization: rmw may extend release sequence / mo adjacency"
                    )
                if event.target and event.target in needed_vars and event.target not in observe:
                    needed_vars.discard(event.target)
                has_future_effect = True

            if event.kind == "store" and event.is_release:
                has_future_effect = True

    if ind_mode == "promote":
        # 闭包：新提升的相关读会扩大 crit_locs，需迭代到不动点。
        changed = True
        while changed:
            changed = False
            base_rel = {
                eid
                for eid, rs in reasons.items()
                if rs and program.events_by_eid[eid].is_read
            }
            for eid, ind_rs in ind_violation_reasons(program, base_rel).items():
                for msg in ind_rs:
                    if msg not in reasons[eid]:
                        reasons[eid].append(msg)
                        changed = True

    return {eid: rs for eid, rs in reasons.items() if rs}


def relevant_loads(program: Program, *, ind_mode: str = "promote") -> Set[str]:
    """有任一相关性理由的读事件（load/rmw）。"""
    explained = explain_relevant_loads(program, ind_mode=ind_mode)
    return {
        eid
        for eid, rs in explained.items()
        if rs and program.events_by_eid[eid].is_read
    }


@dataclass
class RelevanceClosure:
    """相关闭包（THEORY-v1 定义 2.4 + S3 维分类）。

    identity_reads：按「写事件身份」枚举 rf（acquire/SC/RMW）。
    value_reads：按「读值」枚举，值类内存在性选写（S3）。
    sync_deps：潜在 (release/SC 写 → acquire/SC 读) 上界。
    """

    relevant_reads: Set[str]
    reasons: Dict[str, List[str]]
    sync_deps: List[Tuple[str, str]]
    rf_dimensions: List[str]
    identity_reads: List[str]
    value_reads: List[str]
    ind_promoted: Set[str]
    ind_mode: str


def _potential_sync_deps(program: Program, relevant_reads: Set[str]) -> List[Tuple[str, str]]:
    """静态潜在 sw 依赖边：(写 eid, 读 eid)。"""
    deps: List[Tuple[str, str]] = []
    for eid in sorted(relevant_reads):
        load = program.events_by_eid[eid]
        if not (load.is_read and (load.is_acquire or load.is_seq_cst) and load.loc):
            continue
        for write in program.writes_by_loc.get(load.loc, []):
            if write.is_initial:
                continue
            if write.is_release or write.is_seq_cst:
                deps.append((write.eid, load.eid))
    return deps


def is_identity_rf_dimension(load: Event) -> bool:
    """写身份可能改变 sw / SC / RMW 相邻，必须按写枚举。"""
    if load.kind == "rmw":
        return True
    if load.is_acquire or load.is_seq_cst:
        return True
    return False


def is_value_rf_dimension(load: Event) -> bool:
    """观察/断言只依赖读值时，可按值压缩枚举维（S3）。"""
    return load.is_read and not is_identity_rf_dimension(load)


def _writes_grouped_by_value(
    program: Program, load: Event
) -> Dict[int, List[Event]]:
    groups: Dict[int, List[Event]] = {}
    for write in _reads_from_candidates(program, load):
        groups.setdefault(write.value, []).append(write)
    return groups


def compute_relevance_closure(
    program: Program, *, ind_mode: str = "promote"
) -> RelevanceClosure:
    """计算 THEORY-v1 相关闭包；并划分 identity / value 枚举维（S3）。"""
    reasons = explain_relevant_loads(program, ind_mode=ind_mode)
    relevant = {
        eid
        for eid, rs in reasons.items()
        if rs and program.events_by_eid[eid].is_read
    }
    ind_promoted = {
        eid
        for eid in relevant
        if any(r.startswith("ind:") for r in reasons.get(eid, []))
    }
    sync_deps = _potential_sync_deps(program, relevant)
    identity_reads = sorted(
        eid for eid in relevant if is_identity_rf_dimension(program.events_by_eid[eid])
    )
    value_reads = sorted(
        eid for eid in relevant if is_value_rf_dimension(program.events_by_eid[eid])
    )
    return RelevanceClosure(
        relevant_reads=relevant,
        reasons={eid: reasons[eid] for eid in relevant},
        sync_deps=sync_deps,
        rf_dimensions=sorted(relevant),
        identity_reads=identity_reads,
        value_reads=value_reads,
        ind_promoted=ind_promoted,
        ind_mode=ind_mode,
    )


def _resolve_right(env: Dict[str, int], expr: object) -> int:
    if isinstance(expr, int):
        return expr
    if isinstance(expr, str):
        if expr not in env:
            raise KeyError(f"变量 {expr} 尚未定义")
        return env[expr]
    raise TypeError(f"不支持的断言右值: {expr!r}")


def _forced_mo_edges(
    program: Program,
    rf_map: Dict[str, Event],
    hb: Set[Tuple[str, str]],
) -> Dict[str, Set[Tuple[str, str]]]:
    """每个地址上必须进入 mo 的写→写边 + RMW 相邻。"""
    edges: Dict[str, Set[Tuple[str, str]]] = {}
    for loc, writes in program.writes_by_loc.items():
        loc_edges: Set[Tuple[str, str]] = set()
        inits = [write for write in writes if write.is_initial]
        others = [write for write in writes if not write.is_initial]
        for init in inits:
            for other in others:
                loc_edges.add((init.eid, other.eid))

        for write_a in writes:
            for write_b in writes:
                if write_a.eid == write_b.eid:
                    continue
                if (write_a.eid, write_b.eid) in hb:
                    loc_edges.add((write_a.eid, write_b.eid))

        loads_here = [load for load in program.loads if load.loc == loc]
        for load in loads_here:
            source = rf_map[load.eid]
            for write in writes:
                if (write.eid, load.eid) in hb and write.eid != source.eid:
                    loc_edges.add((write.eid, source.eid))
                if (load.eid, write.eid) in hb:
                    if source.eid == write.eid:
                        loc_edges.add((source.eid, source.eid))
                    else:
                        loc_edges.add((source.eid, write.eid))

        for read_a in loads_here:
            for read_b in loads_here:
                if read_a.eid == read_b.eid or (read_a.eid, read_b.eid) not in hb:
                    continue
                source_a = rf_map[read_a.eid]
                source_b = rf_map[read_b.eid]
                if source_a.eid != source_b.eid:
                    loc_edges.add((source_a.eid, source_b.eid))

        # RMW 原子性：rf 到 W ⇒ W 与 RMW 在 mo 上相邻。
        # 用「禁止中间插入」编码：对任意其他写 Z，要么 Z mo W，要么 RMW mo Z。
        # 存在性检查时加边 W→RMW；相邻性在 _modification_order 里验证。
        for load in loads_here:
            if load.kind != "rmw":
                continue
            source = rf_map[load.eid]
            loc_edges.add((source.eid, load.eid))

        edges[loc] = loc_edges
    return edges


def _linear_extension(nodes: Sequence[str], forced: Set[Tuple[str, str]]) -> Optional[List[str]]:
    """确定性拓扑序。有环则不存在合法序。"""
    succ: Dict[str, Set[str]] = {node: set() for node in nodes}
    indeg: Dict[str, int] = {node: 0 for node in nodes}
    for src, dst in forced:
        if src not in indeg or dst not in indeg:
            continue
        if src == dst:
            return None
        if dst not in succ[src]:
            succ[src].add(dst)
            indeg[dst] += 1

    ready = sorted(node for node, degree in indeg.items() if degree == 0)
    order: List[str] = []
    while ready:
        node = ready.pop(0)
        order.append(node)
        for nxt in sorted(succ[node]):
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                ready.append(nxt)
                ready.sort()
    if len(order) != len(nodes):
        return None
    return order


def _rmw_adjacency_ok(
    program: Program,
    rf_map: Dict[str, Event],
    mo: Dict[str, List[str]],
) -> bool:
    """RMW 读到的写必须在 mo 上紧邻该 RMW（中间无其他写）。"""
    for load in program.loads:
        if load.kind != "rmw":
            continue
        source = rf_map[load.eid]
        chain = mo.get(load.loc or "", [])
        if source.eid not in chain or load.eid not in chain:
            return False
        if chain.index(load.eid) != chain.index(source.eid) + 1:
            return False
    return True


def _modification_order(
    program: Program,
    rf_map: Dict[str, Event],
    hb: Set[Tuple[str, str]],
) -> Optional[Dict[str, List[str]]]:
    forced = _forced_mo_edges(program, rf_map, hb)
    witness: Dict[str, List[str]] = {}
    for loc, writes in program.writes_by_loc.items():
        extension = _linear_extension([write.eid for write in writes], forced.get(loc, set()))
        if extension is None:
            return None
        witness[loc] = extension
    if not _rmw_adjacency_ok(program, rf_map, witness):
        return None
    return witness


def _sc_events(program: Program) -> List[Event]:
    events: List[Event] = []
    for thread in program.threads:
        for ev in thread:
            if ev.is_seq_cst and ev.kind in {"load", "store", "rmw", "fence"}:
                events.append(ev)
    return events


def _forced_sc_edges(
    program: Program,
    rf_map: Dict[str, Event],
    hb: Set[Tuple[str, str]],
    mo: Dict[str, List[str]],
) -> Set[Tuple[str, str]]:
    """简化 psc：po、hb、同址 SC 写的 mo、SC 读的 rf，以及 fr。

    为什么要 fr：SB 的 (0,0) 在只有 po 时构不成环；
    Ry 读到 init 而 Wy 在 mo 上更晚 ⇒ Ry -fr-> Wy，再加 po 才杀掉交叉弱态。
    """
    forced: Set[Tuple[str, str]] = set()
    sc = {ev.eid: ev for ev in _sc_events(program)}
    if not sc:
        return forced

    for a_eid, b_eid in _program_order_edges(program):
        if a_eid in sc and b_eid in sc:
            forced.add((a_eid, b_eid))

    for a_eid, b_eid in hb:
        if a_eid in sc and b_eid in sc:
            forced.add((a_eid, b_eid))

    for loc, chain in mo.items():
        sc_writes = [eid for eid in chain if eid in sc and program.events_by_eid[eid].is_write]
        for left, right in zip(sc_writes, sc_writes[1:]):
            forced.add((left, right))
        # 非 SC 的 init 写仍在 mo 链上：SC 读若读到 init，对后续 SC 写有 fr
        for load in program.loads:
            if load.eid not in sc or load.loc != loc or load.eid not in rf_map:
                continue
            source = rf_map[load.eid]
            if source.eid not in chain:
                continue
            src_idx = chain.index(source.eid)
            for later in chain[src_idx + 1 :]:
                if later in sc and program.events_by_eid[later].is_write:
                    forced.add((load.eid, later))

    for load in program.loads:
        if load.eid not in sc or load.eid not in rf_map:
            continue
        source = rf_map[load.eid]
        if source.eid in sc and not source.is_initial:
            forced.add((source.eid, load.eid))

    return forced


def _check_sc_order(
    program: Program,
    rf_map: Dict[str, Event],
    hb: Set[Tuple[str, str]],
    mo: Dict[str, List[str]],
) -> Optional[List[str]]:
    """存在性 SC 全序；无 SC 事件时返回空表。"""
    nodes = [ev.eid for ev in _sc_events(program)]
    if not nodes:
        return []
    forced = _forced_sc_edges(program, rf_map, hb, mo)
    return _linear_extension(nodes, forced)


def evaluate_execution(program: Program, rf_map: Dict[str, Event]) -> Execution:
    """固定 rf → sw/hb → 存在性 mo → 存在性 SC → race / assert。"""
    sync_with = _compute_sync_with(program, rf_map)
    hb = _transitive_closure(_program_order_edges(program) | sync_with)
    mo = _modification_order(program, rf_map, hb)
    if mo is None:
        return Execution(
            read_from={load_eid: write.eid for load_eid, write in rf_map.items()},
            envs={},
            synchronizes_with=sync_with,
            happens_before=hb,
            races=[],
            failed_assertions=[
                ("consistency", "no consistent modification order (Co*/RMW-adjacent)")
            ],
            modification_order={},
            sc_order=[],
        )

    sc = _check_sc_order(program, rf_map, hb, mo)
    if sc is None:
        return Execution(
            read_from={load_eid: write.eid for load_eid, write in rf_map.items()},
            envs={},
            synchronizes_with=sync_with,
            happens_before=hb,
            races=[],
            failed_assertions=[("consistency", "no consistent seq_cst total order")],
            modification_order=mo,
            sc_order=[],
        )

    races: List[Tuple[str, str]] = []
    accesses = program.accesses
    for i in range(len(accesses)):
        for j in range(i + 1, len(accesses)):
            left = accesses[i]
            right = accesses[j]
            if left.thread == right.thread:
                continue
            if left.loc != right.loc:
                continue
            if not (left.is_write or right.is_write):
                continue
            if left.atomic and right.atomic:
                continue
            if (left.eid, right.eid) in hb or (right.eid, left.eid) in hb:
                continue
            races.append((left.eid, right.eid))

    envs: Dict[int, Dict[str, int]] = {}
    failed_assertions: List[Tuple[str, str]] = []
    for tid, events in enumerate(program.threads):
        env: Dict[str, int] = {}
        for event in events:
            if event.kind in {"load", "rmw"}:
                source_write = rf_map[event.eid]
                env[event.target or "_"] = int(source_write.value or 0)
            if event.kind == "assert_eq":
                left_name = event.target
                if left_name is None:
                    raise ValueError(f"{event.eid} 缺少待比较变量")
                if event.guard:
                    if any(env.get(name) != value for name, value in event.guard.items()):
                        continue
                actual = env.get(left_name)
                expected = _resolve_right(env, event.right)
                if actual != expected:
                    failed_assertions.append(
                        (event.eid, f"{left_name}={actual}, expected={expected}")
                    )
        envs[tid] = dict(env)

    return Execution(
        read_from={load_eid: write.eid for load_eid, write in rf_map.items()},
        envs=envs,
        synchronizes_with=sync_with,
        happens_before=hb,
        races=races,
        failed_assertions=failed_assertions,
        modification_order=mo,
        sc_order=sc,
    )


def _pick_default_write(program: Program, load: Event, hb: Set[Tuple[str, str]]) -> Event:
    candidates = _reads_from_candidates(program, load)
    if not candidates:
        raise ValueError(f"{load.eid} 没有 rf 候选")
    visible = [write for write in candidates if (write.eid, load.eid) in hb]
    if visible:
        maximal = []
        for write in visible:
            if not any(
                write.eid != other.eid and (write.eid, other.eid) in hb
                for other in visible
            ):
                maximal.append(write)
        return sorted(maximal, key=lambda w: (w.thread, w.index, w.eid))[-1]

    thread_local = [write for write in candidates if write.thread == load.thread]
    if thread_local:
        return sorted(thread_local, key=lambda w: (w.index, w.eid))[-1]
    return candidates[0]


def _extend_rf_slots(
    program: Program,
    partial_rf: Dict[str, Event],
    slots: Sequence[Tuple[Event, Sequence[Event]]],
    *,
    extend_mode: str = "exists",
) -> Optional[Dict[str, Event]]:
    """为若干 (读 → 允许写列表) 槽位寻找使 mo/SC 通过的扩展。

    用于：S3 值类内选写、以及无关读扩展。槽位应保持很小。
    """
    if extend_mode not in {"exists", "first_candidate"}:
        raise ValueError(f"不支持的 extend_mode: {extend_mode}")

    if not slots:
        rf_map = dict(partial_rf)
        exe = evaluate_execution(program, rf_map)
        if any(eid == "consistency" for eid, _ in exe.failed_assertions):
            return None
        return rf_map

    candidate_lists = [list(writes) for _, writes in slots]
    loads = [load for load, _ in slots]

    if extend_mode == "first_candidate":
        rf_map = dict(partial_rf)
        for load, cands in zip(loads, candidate_lists):
            rf_map[load.eid] = cands[0]
        exe = evaluate_execution(program, rf_map)
        if any(eid == "consistency" for eid, _ in exe.failed_assertions):
            return None
        return rf_map

    sync_with = _compute_sync_with(program, partial_rf)
    hb = _transitive_closure(_program_order_edges(program) | sync_with)
    preferred = []
    for load, cands in zip(loads, candidate_lists):
        # 在槽位限制下做启发式：先试 _pick_default，若不在槽内则取槽内首个
        default = _pick_default_write(program, load, hb)
        if default in cands:
            preferred.append(default)
        else:
            preferred.append(cands[0])

    for writes in itertools.chain(
        [tuple(preferred)],
        itertools.product(*candidate_lists) if candidate_lists else [()],
    ):
        rf_map = dict(partial_rf)
        for load, write in zip(loads, writes):
            rf_map[load.eid] = write
        exe = evaluate_execution(program, rf_map)
        if any(eid == "consistency" for eid, _ in exe.failed_assertions):
            continue
        return rf_map
    return None


def _extend_irrelevant_consistently(
    program: Program,
    partial_rf: Dict[str, Event],
    irrelevant_loads: Sequence[Event],
    *,
    extend_mode: str = "exists",
    value_slots: Optional[Sequence[Tuple[Event, Sequence[Event]]]] = None,
) -> Optional[Dict[str, Event]]:
    """为无关读（及 S3 值类槽位）寻找使 mo/SC 通过的扩展。"""
    slots: List[Tuple[Event, Sequence[Event]]] = []
    if value_slots:
        slots.extend(list(value_slots))
    for load in irrelevant_loads:
        slots.append((load, _reads_from_candidates(program, load)))
    return _extend_rf_slots(
        program, partial_rf, slots, extend_mode=extend_mode
    )


def outcome_tuple(
    program: Program,
    exe: Execution,
) -> Tuple[Tuple[str, Optional[int]], ...]:
    """把一次执行投影到 observe：跨线程合并同名变量（教具里变量名不冲突）。"""
    merged: Dict[str, int] = {}
    for env in exe.envs.values():
        merged.update(env)
    return tuple((name, merged.get(name)) for name in program.observe)


def outcome_set(
    program: Program, executions: Sequence[Execution]
) -> Set[Tuple[Tuple[str, Optional[int]], ...]]:
    return {outcome_tuple(program, exe) for exe in executions}


def analyze_program(
    program_path: Path,
    reduction: str = "none",
    *,
    ind_mode: str = "promote",
    extend_mode: str = "exists",
    edge_prune: str = "value",
) -> AnalysisResult:
    """入口：枚举 rf，丢掉无合法 mo/SC 的图。

    ind_mode: promote（默认，T2）| refuse（有 IND 违例则不做约简）| off（不检查，实验用）
    extend_mode: exists（默认）| first_candidate（反例用）
    edge_prune: value（S3：值维压缩）| off（相关读仍按写身份全枚举）
    """
    program = load_program(program_path)
    if reduction not in {"none", "relevant"}:
        raise ValueError(f"不支持的约简模式: {reduction}")
    if edge_prune not in {"value", "off"}:
        raise ValueError(f"不支持的 edge_prune: {edge_prune}")

    base_reasons = explain_relevant_loads(program, ind_mode="off")
    base_relevant = {
        eid
        for eid, rs in base_reasons.items()
        if rs and program.events_by_eid[eid].is_read
    }
    violations = ind_violation_reasons(program, base_relevant)

    effective_reduction = reduction
    ind_refused = False
    if reduction == "relevant" and ind_mode == "refuse" and violations:
        effective_reduction = "none"
        ind_refused = True

    # refuse 回退时仍用 promote 视图解释「本应提升哪些读」
    reason_mode = "promote" if ind_refused else ind_mode
    reasons = explain_relevant_loads(program, ind_mode=reason_mode)

    if effective_reduction != "relevant":
        relevant = {load.eid for load in program.loads}
    elif ind_mode == "promote":
        relevant = relevant_loads(program, ind_mode="promote")
    elif ind_mode == "off":
        relevant = base_relevant
    else:
        relevant = base_relevant

    relevant_load_events = [load for load in program.loads if load.eid in relevant]
    irrelevant_load_events = [load for load in program.loads if load.eid not in relevant]

    use_value_prune = effective_reduction == "relevant" and edge_prune == "value"
    if use_value_prune:
        identity_events = [
            load for load in relevant_load_events if is_identity_rf_dimension(load)
        ]
        value_events = [
            load for load in relevant_load_events if is_value_rf_dimension(load)
        ]
    else:
        identity_events = list(relevant_load_events)
        value_events = []

    id_candidate_lists = [_reads_from_candidates(program, load) for load in identity_events]
    # 每个 value 读：按值列出 (value, writes)
    value_choice_lists: List[List[Tuple[int, List[Event]]]] = []
    for load in value_events:
        grouped = _writes_grouped_by_value(program, load)
        value_choice_lists.append(
            [(value, writes) for value, writes in sorted(grouped.items())]
        )

    executions: List[Execution] = []
    seen_signatures: Set[Tuple[Tuple[str, str], ...]] = set()
    total_full_candidates = 1
    for load in program.loads:
        total_full_candidates *= max(1, len(_reads_from_candidates(program, load)))

    # 未做值压缩时的相关写枚举量（对照）
    naive_relevant_product = 1
    for load in relevant_load_events:
        naive_relevant_product *= max(1, len(_reads_from_candidates(program, load)))

    explored_candidate_assignments = 1
    for cands in id_candidate_lists:
        explored_candidate_assignments *= max(1, len(cands))
    for choices in value_choice_lists:
        explored_candidate_assignments *= max(1, len(choices))

    id_product = list(
        itertools.product(*id_candidate_lists) if id_candidate_lists else [()]
    )
    val_product = list(
        itertools.product(*value_choice_lists) if value_choice_lists else [()]
    )

    for id_writes in id_product:
        partial_rf = {
            load.eid: write for load, write in zip(identity_events, id_writes)
        }
        for value_picks in val_product:
            value_slots: List[Tuple[Event, Sequence[Event]]] = [
                (load, writes)
                for load, (_value, writes) in zip(value_events, value_picks)
            ]
            if effective_reduction == "relevant":
                rf_map = _extend_irrelevant_consistently(
                    program,
                    partial_rf,
                    irrelevant_load_events,
                    extend_mode=extend_mode,
                    value_slots=value_slots,
                )
                if rf_map is None:
                    continue
            else:
                # 全量枚举：identity_events 已含全部相关=全部读；value_events 为空
                rf_map = dict(partial_rf)

            signature = tuple(sorted((k, v.eid) for k, v in rf_map.items()))
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            execution = evaluate_execution(program, rf_map)
            if any(eid == "consistency" for eid, _ in execution.failed_assertions):
                continue
            executions.append(execution)

    outcomes = outcome_set(program, executions)
    closure = compute_relevance_closure(program, ind_mode=reason_mode)
    stats = {
        "reduction": effective_reduction,
        "requested_reduction": reduction,
        "ind_mode": ind_mode,
        "extend_mode": extend_mode,
        "edge_prune": edge_prune if effective_reduction == "relevant" else "off",
        "ind_refused": ind_refused,
        "ind_violations": sorted(violations.keys()),
        "total_loads": len(program.loads),
        "relevant_loads": len(relevant_load_events),
        "irrelevant_loads": len(irrelevant_load_events),
        "identity_rf_dims": len(identity_events),
        "value_rf_dims": len(value_events),
        "naive_relevant_product": naive_relevant_product,
        "full_candidate_assignments": total_full_candidates,
        "explored_candidate_assignments": explored_candidate_assignments,
        "kept_executions": len(executions),
        "observe": list(program.observe),
        "observe_source": program.observe_source,
        "outcome_count": len(outcomes),
        "sync_deps": len(closure.sync_deps),
        "ind_promoted": sorted(closure.ind_promoted),
        "rf_dimensions": list(closure.rf_dimensions),
        "identity_reads": list(closure.identity_reads),
        "value_reads": list(closure.value_reads),
    }
    return AnalysisResult(
        program=program,
        executions=executions,
        stats=stats,
        relevant_reasons={eid: reasons[eid] for eid in relevant if eid in reasons},
    )


def compare_reduction(
    program_path: Path,
    *,
    ind_mode: str = "promote",
    extend_mode: str = "exists",
    edge_prune: str = "value",
) -> Dict[str, object]:
    """T2/R3 核对：约简前后布尔性质与 observe 结局集合必须一致。

    见证执行条数不必相等（无关组合被坍缩）；另给 witness_counts_ok 供诊断。
    """
    full = analyze_program(
        program_path,
        reduction="none",
        ind_mode=ind_mode,
        extend_mode=extend_mode,
        edge_prune=edge_prune,
    )
    reduced = analyze_program(
        program_path,
        reduction="relevant",
        ind_mode=ind_mode,
        extend_mode=extend_mode,
        edge_prune=edge_prune,
    )
    full_sum = summarize(full.program, full.executions)
    red_sum = summarize(reduced.program, reduced.executions)
    full_out = outcome_set(full.program, full.executions)
    red_out = outcome_set(reduced.program, reduced.executions)
    props_ok = (
        full_sum["is_racy"] == red_sum["is_racy"]
        and full_sum["assertion_can_fail"] == red_sum["assertion_can_fail"]
    )
    witness_counts_ok = (
        full_sum["executions_with_race"] == red_sum["executions_with_race"]
        and full_sum["executions_with_assertion_failure"]
        == red_sum["executions_with_assertion_failure"]
    )
    outcomes_ok = full_out == red_out
    return {
        "program": program_path.name,
        "props_ok": props_ok,
        "outcomes_ok": outcomes_ok,
        "witness_counts_ok": witness_counts_ok,
        "observe": list(full.program.observe),
        "observe_source": full.program.observe_source,
        "full_outcomes": len(full_out),
        "reduced_outcomes": len(red_out),
        "missing_outcomes": sorted(full_out - red_out),
        "extra_outcomes": sorted(red_out - full_out),
        "full_stats": full.stats,
        "reduced_stats": reduced.stats,
        "full_summary": full_sum,
        "reduced_summary": red_sum,
        "ind_violations": full.stats.get("ind_violations", []),
    }


def enumerate_executions(program_path: Path, reduction: str = "none") -> Tuple[Program, List[Execution]]:
    result = analyze_program(program_path, reduction=reduction)
    return result.program, result.executions


def summarize(program: Program, executions: Sequence[Execution]) -> Dict[str, object]:
    bad_assertions = [exe for exe in executions if exe.failed_assertions]
    racy = [exe for exe in executions if exe.races]
    return {
        "program": program.name,
        "threads": len(program.threads),
        "loads": len(program.loads),
        "candidate_executions": len(executions),
        "executions_with_race": len(racy),
        "executions_with_assertion_failure": len(bad_assertions),
        "is_racy": bool(racy),
        "assertion_can_fail": bool(bad_assertions),
    }


def _format_execution(exe: Execution) -> str:
    lines = []
    lines.append("  read-from:")
    for load_eid, write_eid in sorted(exe.read_from.items()):
        lines.append(f"    {load_eid} <- {write_eid}")
    if exe.modification_order:
        lines.append("  modification-order:")
        for loc in sorted(exe.modification_order):
            chain = " < ".join(exe.modification_order[loc])
            lines.append(f"    {loc}: {chain}")
    if exe.sc_order:
        lines.append("  seq-cst-order:")
        lines.append("    " + " < ".join(exe.sc_order))
    if exe.synchronizes_with:
        lines.append("  synchronizes-with:")
        for left, right in sorted(exe.synchronizes_with):
            lines.append(f"    {left} -> {right}")
    if exe.races:
        lines.append("  races:")
        for left, right in exe.races:
            lines.append(f"    {left} || {right}")
    if exe.failed_assertions:
        lines.append("  failed assertions:")
        for eid, msg in exe.failed_assertions:
            lines.append(f"    {eid}: {msg}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="单芯片 RC11 核心子集验证原型")
    parser.add_argument("program", type=Path, help="JSON 格式程序描述文件")
    parser.add_argument("--show-executions", action="store_true", help="打印每个候选执行")
    parser.add_argument("--max-executions", type=int, default=20, help="最多打印多少个执行")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出摘要")
    parser.add_argument(
        "--explain-relevant",
        action="store_true",
        help="打印每个相关读的判定原因",
    )
    parser.add_argument(
        "--reduction",
        choices=["none", "relevant"],
        default="none",
        help="状态空间约简模式",
    )
    parser.add_argument(
        "--ind-mode",
        choices=["promote", "refuse", "off"],
        default="promote",
        help="IND 假设：提升违例读 / 拒绝约简 / 关闭检查",
    )
    parser.add_argument(
        "--edge-prune",
        choices=["value", "off"],
        default="value",
        help="S3：相关读值维压缩 / 关闭",
    )
    args = parser.parse_args()

    result = analyze_program(
        args.program,
        reduction=args.reduction,
        ind_mode=args.ind_mode,
        edge_prune=args.edge_prune,
    )
    program, executions = result.program, result.executions
    summary = summarize(program, executions)
    summary.update(result.stats)

    if args.json:
        payload = dict(summary)
        if args.explain_relevant:
            closure = compute_relevance_closure(program, ind_mode=args.ind_mode)
            payload["relevant_reasons"] = closure.reasons
            payload["sync_deps"] = closure.sync_deps
            payload["ind_promoted"] = sorted(closure.ind_promoted)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print(f"程序: {summary['program']}")
    print(f"线程数: {summary['threads']}")
    print(f"load 数: {summary['loads']}")
    print(f"候选执行数: {summary['candidate_executions']}")
    print(f"约简模式: {summary['reduction']}")
    print(f"相关 load 数: {summary['relevant_loads']} / {summary['total_loads']}")
    print(f"组合数(全枚举): {summary['full_candidate_assignments']}")
    print(f"组合数(当前展开): {summary['explored_candidate_assignments']}")
    print(f"观察变量: {summary.get('observe', program.observe)} ({program.observe_source})")
    print(f"存在 data race: {'是' if summary['is_racy'] else '否'}")
    print(f"断言可失败: {'是' if summary['assertion_can_fail'] else '否'}")
    print(f"含 race 的执行数: {summary['executions_with_race']}")
    print(f"含断言失败的执行数: {summary['executions_with_assertion_failure']}")
    print(f"观察结局数: {result.stats.get('outcome_count')}")

    if args.explain_relevant:
        print("相关判定:")
        closure = compute_relevance_closure(program, ind_mode=args.ind_mode)
        for eid in sorted(closure.reasons):
            for reason in closure.reasons[eid]:
                print(f"  {eid}: {reason}")
        print(f"潜在同步依赖边 |SyncDep|={len(closure.sync_deps)}")
        print(
            f"S3 维：identity={closure.identity_reads} value={closure.value_reads}"
        )
        for write_eid, load_eid in closure.sync_deps[:30]:
            print(f"  sw?: {write_eid} -> {load_eid}")
        if len(closure.sync_deps) > 30:
            print(f"  ... ({len(closure.sync_deps) - 30} more)")
        if args.json:
            pass  # json 分支已提前 return

    if args.show_executions:
        for idx, exe in enumerate(executions[: args.max_executions], start=1):
            print()
            print(f"[执行 {idx}]")
            print(_format_execution(exe))


if __name__ == "__main__":
    main()
