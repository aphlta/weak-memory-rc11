# weak-memory-rc11

面向 **RC11 核心子集** 的弱内存自动验证与状态空间约简研究原型。

用 JSON 描述小型并发程序，枚举 `reads-from` 候选执行，并检查：

- RA 风格 `synchronizes-with` / `happens-before`
- 存在性 `modification order`（CoWW/CoWR/CoRW/CoRR）
- `fence`（acquire/release/acq_rel/seq_cst）同步
- release sequence
- 简化 RMW（读写合一 + mo 相邻）
- 存在性 `seq_cst` 全序（含 fr）
- 简化 data race 与 `assert_eq`
- 可解释的 relevant-load 约简（`--explain-relevant`）

研究主线：**面向 assertion / synchronization / race / outcome 的性质感知约简**（R3：观察结局集合保持；主定理 T2 见 [`docs/REDUCTION.md`](docs/REDUCTION.md)）。

当前覆盖的是 RC11 **核心子集**，不是完整 C/C++11（无 consume / thin-air / CAS 失败路径等）。与文献的对照见 [`docs/phd/RC11-ALIGNMENT.md`](docs/phd/RC11-ALIGNMENT.md)。

## 怎么跑

只需 Python 3。在本目录执行：

```bash
python3 weak_memory_verifier.py examples/message_passing.json
python3 weak_memory_verifier.py examples/mp_sc_fence.json --show-executions
python3 weak_memory_verifier.py examples/message_passing_with_irrelevant_load.json \
  --reduction relevant --explain-relevant
python3 smoke_check.py
python3 benchmark_compare.py --write-results
python3 scripts/bench_timing.py --repeats 5 --write-results
python3 scripts/herd_landing.py --write-results
python3 scripts/herd_compare.py --write-results
python3 scripts/phd_experiment_table.py --write-results
python3 scripts/phd_eval_suite.py --write-results
```

## 例子（节选）

| 程序 | 作用 |
| --- | --- |
| `message_passing.json` | RA 消息传递应安全 |
| `mp_relaxed.json` / `mp_sc_fence.json` | 无 fence 弱态在；两侧 SC fence 后弱态没了 |
| `rs_message_passing.json` | 读到 release 后的 relaxed 写仍经 RS 同步 |
| `rmw_adjacent.json` | RMW 与其 rf 源在 mo 上相邻 |
| `sb_relaxed.json` / `sb_seq_cst.json` | SB (0,0) 在 relaxed 允许、在 SC 禁止 |
| `lb_relaxed.json` | LB (1,1) 允许 |
| `coherence_rr.json` / `coherence_rw.json` | 存在性 mo 约束 |
| `*_with_irrelevant_load.json` / `scale_*` | 约简组合数与规模曲线 |
| `mp_relaxed_with_noise` / `racy_counter_with_noise` | 噪声下仍检出弱态 assert / race |

| `mp_ra_dup_writes` | S3：同值多写，相关枚举 8→4 |

实验汇总：[`docs/benchmark_summary.md`](docs/benchmark_summary.md)。  
博士表：[`results/phd_experiment_table.md`](results/phd_experiment_table.md)。  
S5 评测套件：[`results/phd_eval_suite.md`](results/phd_eval_suite.md) / [`docs/phd/EVALUATION.md`](docs/phd/EVALUATION.md)。  
与 herdtools 落地验收：[`docs/HERD-COMPARISON.md`](docs/HERD-COMPARISON.md) / [`results/herd_landing.md`](results/herd_landing.md)。  
现行档期 B：[`docs/phd/ROADMAP-B.md`](docs/phd/ROADMAP-B.md)（P2 路线图已冻结）。

## JSON 输入

支持 `store` / `load` / `rmw` / `fence` / `assert_eq`。字段说明见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。

```json
{"op": "fence", "order": "seq_cst"}
{"op": "rmw", "loc": "x", "value": 2, "target": "old", "atomic": true, "order": "acq_rel"}
```

## 目录

```
weak_memory_verifier.py
smoke_check.py
benchmark_compare.py
examples/
scripts/
docs/          # 约简证明、架构、开题与答辩
results/       # benchmark / 时间曲线 / herd 对照快照
```

## 文档入口

| 文档 | 用途 |
| --- | --- |
| [docs/REDUCTION.md](docs/REDUCTION.md) | 约简规则与主定理 T2 |
| [docs/phd/THEORY-v1.md](docs/phd/THEORY-v1.md) | 博士理论稿（相关闭包 / T2⁺⁺） |
| [docs/phd/RC11-ALIGNMENT.md](docs/phd/RC11-ALIGNMENT.md) | 与文献 RC11/C11 子集对齐（第 2–3 章） |
| [docs/phd/ROADMAP-B.md](docs/phd/ROADMAP-B.md) | **现行**档期 B（herd 外部验收） |
| [docs/phd/ROADMAP.md](docs/phd/ROADMAP.md) | 冻结的 P2/A 路线图 |
| [docs/phd/EVALUATION.md](docs/phd/EVALUATION.md) | 第 6 章评测骨架（S5） |
| [docs/phd/thesis/](docs/phd/thesis/) | 学位论文第 2–6 章正文草稿 |
| [formal/](formal/) | S6a Coq 机械化（引理 1 + T2⁺ 结局工作定理） |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 语义与流水线 |
| [docs/benchmark_summary.md](docs/benchmark_summary.md) | 实验结果摘要 |
| [docs/HERD-COMPARISON.md](docs/HERD-COMPARISON.md) | herd 落地验收入口（主表 herd_landing） |
| [docs/opening/formal.md](docs/opening/formal.md) | 开题报告 |
| [docs/CURSOR_HANDOFF.md](docs/CURSOR_HANDOFF.md) | 工程接手说明 |
