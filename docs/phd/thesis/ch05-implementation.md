# 论文第 5 章草稿：原型实现

> 扩写自 [`ARCHITECTURE.md`](../../ARCHITECTURE.md)、[`REDUCTION.md`](../../REDUCTION.md)。  
> 状态：**短章初稿**；细节以代码为准。

---

## 5.1 系统定位

原型是**语言级、公理风格的执行图枚举器**：输入 JSON 小程序，枚举 `rf` 赋值，检查存在性 `mo`/`SC`，判定观察结局、数据竞争与断言；并实现第 4 章的性质感知约简。代码入口：`weak_memory_verifier.py`。

---

## 5.2 验证流水线

```text
JSON 程序
  → Event / Program（含 fence / rmw / observe）
  → 相关闭包 Cl（可选）
  → rf 候选（全量或约简维）
  → sw（RA + RS + fence）→ hb
  → 存在性 mo（Co* + RMW 相邻）
  → 存在性 SC（po/hb/mo/rf/fr）
  → assert / race / 观察投影
```

| 步骤 | 主要函数 |
| --- | --- |
| 解析 | `load_program` |
| 程序序 | `_program_order_edges` |
| rf 候选 | `_reads_from_candidates` |
| 同步 | `_compute_sync_with` |
| hb | `_transitive_closure` |
| mo / SC | `_modification_order` / `_check_sc_order` |
| 相关闭包 | `compute_relevance_closure` / `explain_relevant_loads` |
| 约简枚举 | `analyze_program(..., reduction=...)` |
| 正确性对比 | `compare_reduction` |

---

## 5.3 约简实现要点

1. **相关读**：outcome / assertion / synchronization / race；默认 `ind_mode=promote`。  
2. **无关读**：`extend_mode=exists`，不扫全笛卡尔积。  
3. **S3 值维**：`edge_prune=value` 时，非 identity 相关读按值类压缩；identity（acquire/SC/RMW）仍按写身份。  
4. **可解释性**：`--explain-relevant` 输出闭包、SyncDep、维划分。  
5. **守门**：`props_ok ∧ outcomes_ok`；见证条数允许不等。

---

## 5.4 实验与回归脚本

| 脚本 | 作用 |
| --- | --- |
| `smoke_check.py` | 正确性 / IND / S3 烟雾 |
| `benchmark_compare.py` | 组合数对比 |
| `scripts/phd_eval_suite.py` | 分类评测套件（第 6 章） |
| `scripts/bench_timing.py` | 时间曲线 |
| `scripts/herd_compare.py` | herdtools 弱态同向 |

---

## 5.5 本章小结

实现与第 3–4 章符号一一对应，并以差分测试守门。下一章报告有效性、正确性与不漏报实验结果。
