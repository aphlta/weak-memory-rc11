# S6a/S6b 附录：机械化编码与假设（论文附录草稿）

对应仓库 [`formal/`](../../../formal/)。编译：`cd formal && make`（Coq 8.18）。

---

## A.1 编码范围

| 已编码 | 未编码（有意） |
| --- | --- |
| 读/写、`rf`、观察投影 | 完整 `sw` / fence |
| Obs 相关读；抽象 `Consistent` | 存在性 `mo`/`SC` 展开 |
| 存在性扩展；T2⁺ 结局工作定理 | 集合论 \(\mathsf{Out}=\mathsf{Out}_R\) 包装 |
| **Prop 存在性口径（引理 5）** | 具体 race/assert 算法 |
| **IND / Viol / promote1 / 闭包⇒IND（引理 6）** | release-prefix 的具体计算 |
| 值维剪枝 | **S6c** |

---

## A.2 已机器检查的陈述

### S6a（`MiniGraph.v` / `Reduction.v`）

1. **`lemma1_obs_depends_on_relevant_rf`** — 观察由 Obs 相关读上的 rf 决定。  
2. **`T2_plus_outcome_workhorse`** — 覆盖 Obs 时，扩展代表与具体 rf 观察相同。

### S6b（`IndProp.v`）

3. **`lemma5_prop_equiv`** — \(\mathsf{Prop}_{\mathsf{full}}\leftrightarrow\mathsf{Prop}_{\mathsf{reduced}}\)（存在性口径；任意相关集 \(R\)）。  
4. **`lemma6_closed_implies_ind`** — 对 \(\mathsf{Viol}\) 封闭 ⇒ \(\mathsf{IND}\)。  
5. **`lemma6_ind_allows_noise_exclusion`** — \(\mathsf{IND}(R_0)\) 下非相关读不触及 CritLoc / 非「acquire 后读 RP」。  
6. **`lemma6_promote1_absorbs_violators`** — 单步 promote 吸收违例读。  
7. **`lemma6_refuse_all_is_ind`** — refuse 回退「全体读相关」时 IND 平凡成立。

---

## A.3 信任边界

| 由 Coq 承担 | 仍信任实现 / 实验 |
| --- | --- |
| 引理 1、T2⁺ 结局工作形式 | `sw` / mo / SC 实现 |
| Prop 存在性等价（引理 5） | 具体 Bad（race/assert）判定代码 |
| IND 封闭性与 promote/refuse 接口（引理 6） | `_release_prefix_locations` 等静态分析细节 |
| | 全集 `compare_reduction` / `phd_eval_suite` |

说明：引理 5 证明的是「是否存在 Bad 一致执行」在全量与「相关代表+扩展」口径下等价；**不**证明 Python 的 race 检测器本身正确。

---

## A.4 与正文交叉引用

- 第 4 章：引理 1、5、6；T2⁺  
- 第 5 章：`ind_mode=promote|refuse` ↔ promote1 / relevant_all  
- 第 6 章：实验覆盖未机械化的 Bad / RP 计算  

---

## A.5 复现

```bash
export OPAMROOT=/ssdhome/maoweiming/xiangshan/.opam-root
eval $(opam env)
cd formal && make clean && make
```
