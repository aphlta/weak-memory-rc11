# 架构与语义边界

> **冻结声明（档期 B）**  
> **现行档期是 B**；外部验收见 [phd/ROADMAP-B.md](phd/ROADMAP-B.md) 与 [`results/herd_landing.md`](../results/herd_landing.md)。  
> **本文只描述本器语义，不是 DUT oracle。**

这份文档说明：本原型实际在算什么，以及故意缩小的语义范围。

## 1. 定位

本项目是 **语言级、公理风格的执行图枚举器**，覆盖 **RC11 核心子集**
（RA + fence + RS + RMW + 简化 SC + 存在性 mo），并实现性质感知约简（见 [REDUCTION.md](REDUCTION.md)）。

适合：开题与论文中的方法展示、约简实验、小型并发程序案例分析。

当前**不是**完整 C/C++11 内存模型实现（见 §4「没做」）。

## 2. 验证流水线

```text
JSON 程序
  → Event / Program（含 fence / rmw）
  → 每个读的 rf 候选（笛卡尔积只扫 rf）
  → sw（RA + RS + fence）→ hb
  → 存在性 mo（Co* + RMW 相邻）
  → 存在性 SC 全序（po/hb/mo/rf/fr）
  → assert / race
```

| 步骤 | 函数 | 备注 |
| --- | --- | --- |
| 解析 | `load_program` | init 虚拟写；RMW 同时进 loads 与 writes |
| po | `_program_order_edges` | 含 fence |
| rf | `_reads_from_candidates` | 不含 rf×mo 枚举 |
| sw | `_compute_sync_with` | RS + fence 四种同步模式 |
| hb | `_transitive_closure(po ∪ sw)` | |
| mo | `_modification_order` | Co* + RMW 与源写相邻 |
| SC | `_check_sc_order` | 含 fr；无 SC 事件则空 |
| 约简 | `explain_relevant_loads` | outcome / assertion / synchronization / race；默认 IND `promote` |

## 3. 当前语义：做了 / 没做

**做了**

- 原子顺序：`relaxed` / `acquire` / `release` / `acq_rel` / `seq_cst`
- fence：`acquire` / `release` / `acq_rel` / `seq_cst`（参与 sw）
- release sequence：同线程后续写；RMW 可延长
- 简化 RMW：读出旧值写入 `target`，再写固定 `value`；mo 上与 rf 源相邻
- 存在性 mo：CoWW/CoWR/CoRW/CoRR；初值写为 mo 最小元
- 存在性 SC 全序：SC 事件上 po/hb/mo/rf，以及读到旧写后对较新 SC 写的 fr
- 简化 DRF race、`assert_eq`（可带 `when`）
- 可解释 relevant-load（`--explain-relevant`）

**没做（本课题范围外）**

- consume / dob / no-thin-air
- CAS 失败路径、混合宽度
- 完整 Batty/Lahav psc 全部边

并发写的「先 2 后 1」在存在性 mo 下**合法**；只有两写已有 hb/CoRW 边时先新后旧才成环。

## 4. 约简

见 [REDUCTION.md](REDUCTION.md)（R3 / 主定理 T2；默认 `ind_mode=promote`）。文献子集对齐见 [phd/RC11-ALIGNMENT.md](phd/RC11-ALIGNMENT.md)。

`--reduction relevant` 只展开相关读；无关读做**存在性一致扩展**。
`compare_reduction` 核对布尔性质与 observe 结局集合。

与 herdtools 经典 litmus 的弱态对照见 [HERD-COMPARISON.md](HERD-COMPARISON.md)。

## 5. CLI

```bash
python3 weak_memory_verifier.py <json> [--reduction none|relevant] \
  [--ind-mode promote|refuse|off] [--show-executions] [--explain-relevant] [--json]
python3 smoke_check.py
python3 benchmark_compare.py [--write-results]
python3 scripts/bench_timing.py --repeats 5 --write-results
python3 scripts/herd_compare.py --write-results
```
