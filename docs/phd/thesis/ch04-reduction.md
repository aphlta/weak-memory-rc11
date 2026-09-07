# 论文第 4 章草稿：性质感知约简

> 扩写自 [`THEORY-v1.md`](../THEORY-v1.md) 与 [`REDUCTION.md`](../../REDUCTION.md)。  
> 状态：**可粘贴进正文的初稿**；证明为结构纲要，机械化见 S6。

---

## 4.1 问题陈述

全量搜索对程序中**每一个**读事件枚举全部同址写候选，组合规模随无关「噪声」读指数增长，而观察结局 \(\mathsf{Out}(P)\) 与布尔性质 \(\mathsf{Prop}(P)\) 往往仅依赖少数读维与同步形状。

本章给出**性质感知约简**：构造相关闭包 \(\mathsf{Cl}(P)\)，仅对闭包中的读维（及值维压缩后的候选）做细粒度枚举，其余读维以存在性扩展恢复一致性，并证明观察结局与布尔性质保持（T2⁺）；进一步在相关读内部区分 identity / value 维，得到 T2⁺⁺。

---

## 4.2 符号与实现对应

| 符号 | 含义 | 实现 |
| --- | --- | --- |
| \(P\) | 程序 | JSON / `Program` |
| \(\mathsf{Obs}\) | 观察变量 | `observe` |
| \(\mathsf{Exec}(P)\) | 全量一致执行 | `reduction="none"` |
| \(\mathsf{Out}(P)\) | 观察结局集合 | `outcome_set` |
| \(\mathsf{Prop}(P)\) | \((\mathsf{racy},\mathsf{assert})\) | `summarize` 布尔字段 |
| \(R_0(P)\) | 基础相关读 | `explain_relevant_loads(..., ind_mode="off")` |
| \(\mathsf{Cl}(P)\) | 相关闭包 | `compute_relevance_closure` |
| \(\mathsf{SyncDep}\) | 潜在同步依赖边 | `RelevanceClosure.sync_deps` |
| \(\mathsf{Exec}_R\) | 约简执行集 | `reduction="relevant"` |

---

## 4.3 相关闭包

### 定义 4.1（基础相关读 \(R_0\)）

读 \(r\) 属于 \(R_0(P)\)，当且仅当至少一条成立：

1. **outcome**：\(r\) 的目标变量 \(\in\mathsf{Obs}\)；  
2. **assertion**：目标流入 assert/guard；  
3. **synchronization**：acquire/SC 读（或可延长 RS 的 RMW）可能影响后续 \(\mathsf{hb}\)/SC；  
4. **race**：非原子读。

### 定义 4.2（IND 提升）

静态独立性违例集 \(\mathsf{Viol}(P,R)\)：若某读虽不在当前相关集，但其取值可能经数据/控制影响相关事件，则构成违例。\(\mathsf{Cl}_{\mathsf{read}}(P)\) 为对 \(R_0\) 迭代加入 \(\mathsf{Viol}\) 的不动点（实现默认 `ind_mode=promote`；`refuse` 则回退全枚举）。

### 定义 4.3（潜在同步依赖边）

\[
\mathsf{SyncDep}(P)
=
\{
(w,r)\mid
r\in\mathsf{Cl}_{\mathsf{read}}(P),\;
r\text{ 为 acquire/SC 读},\;
w\text{ 为同址 release/SC 写候选}
\}.
\]

这是静态上界（可能产生 \(\mathsf{sw}\) 的边），而非某次执行中的真实 \(\mathsf{sw}\)。

### 定义 4.4（相关闭包）

\[
\mathsf{Cl}(P)
=
\big(
\mathsf{Cl}_{\mathsf{read}}(P),\;
\mathsf{SyncDep}(P),\;
\mathsf{RfDim}(P)
\big),
\]

其中基础情形 \(\mathsf{RfDim}=\mathsf{Cl}_{\mathsf{read}}\)；引入值维剪枝后，\(\mathsf{RfDim}\) 上的枚举边集可为真子集。

---

## 4.4 约简语义

固定 \(\mathsf{Cl}(P)\)：

1. 对每个 \(r\in\mathsf{RfDim}\) 枚举其 rf 候选（或值类，见 §4.6）；  
2. 对 \(r\notin\mathsf{Cl}_{\mathsf{read}}\) 做存在性扩展（`extend_mode=exists`）；  
3. 通过 `mo`/`SC` 者进入 \(\mathsf{Exec}_R(P)\)。

记 \(\mathsf{Out}_R=\pi_{\mathsf{Obs}}(\mathsf{Exec}_R)\)，\(\mathsf{Prop}_R\) 为约简执行集上的布尔性质。

---

## 4.5 引理与主定理 T2⁺

以下均设扩展为存在性搜索。

**引理 1（观察功能依赖）**  
若 \(\{r\mid r.\mathsf{target}\in\mathsf{Obs}\}\subseteq\mathsf{Cl}_{\mathsf{read}}\)，则 \(\pi_{\mathsf{Obs}}(e)\) 由 \(e\) 在 \(\mathsf{Cl}_{\mathsf{read}}\) 上的 `rf` 完全决定。

**引理 2（可扩展性）**  
任意 \(e\in\mathsf{Exec}(P)\) 在 \(\mathsf{Cl}_{\mathsf{read}}\) 上的限制均可被存在性扩展恢复为某一致执行（至少 \(e\) 自身）。

**引理 3（健全）** \(\mathsf{Out}_R(P)\subseteq\mathsf{Out}(P)\)。

**引理 4（相对完备）** \(\mathsf{Out}(P)\subseteq\mathsf{Out}_R(P)\)。

**引理 5（布尔性质）** \(\mathsf{Prop}(P)=\mathsf{Prop}_R(P)\)（见证条数不必相等）。

**引理 6（IND 静态充分性）**  
若 \(\mathsf{Viol}(P,R_0)=\emptyset\)，则噪声读不落入 \(\mathsf{Cl}_{\mathsf{read}}\) 与引理 1–5 相容；若违例非空，`promote` 扩大闭包后恢复相容性，`refuse` 退回 \(\mathsf{Exec}(P)\)。

**定理 T2⁺（相关闭包约简）**  
在存在性扩展下，

\[
\mathsf{Out}(P)=\mathsf{Out}_R(P)
\quad\text{且}\quad
\mathsf{Prop}(P)=\mathsf{Prop}_R(P).
\]

*证明结构*：引理 3+4 得结局；引理 5 得布尔；引理 1–2 支撑相对完备；引理 6 说明 IND 策略。□

**推论（SyncDep 的角色）**  
当前枚举维仍由相关读决定；\(\mathsf{SyncDep}\) 给出边级剪枝的合法搜索空间上界：可能改变相关读上 \(\mathsf{sw}/\mathsf{hb}\) 形状的 `rf` 边不可删。

---

## 4.6 值维边级剪枝与 T2⁺⁺

### 定义 4.5（维分类）

- **identity 维**：RMW，或 acquire/SC 读 → 必须按写**事件身份**枚举（身份进入 \(\mathsf{sw}\)/SC/相邻）。  
- **value 维**：其余相关读 → 枚举可能读值集合，对每个值在同值写类上存在性选写。

**引理 7（值维观察依赖）**  
对 value 维读 \(r\)，\(\pi_{\mathsf{Obs}}\) 中由 \(r\) 贡献的分量只依赖所读值，不依赖写事件身份。

**引理 8（值类可扩展性）**  
若全量执行以值为 \(v\) 的写 \(W\) 为 \(r\) 的源，则固定其余 identity 赋值后，值类内存在性搜索能找到一致扩展（至少 \(W\)）。

**定理 T2⁺⁺**  
在 `edge_prune=value` 与存在性扩展下，仍有 \(\mathsf{Out}=\mathsf{Out}_R\) 且 \(\mathsf{Prop}=\mathsf{Prop}_R\)。

*证明梗概*：identity 维保持同步可区分性；value 维由引理 7–8 归约到「按值枚举 + 类内存在性」，同引理 2–4。□

**展示例**：`mp_ra_dup_writes` 三笔同值写使朴素相关积 \(2\times 4=8\)，值维压缩为 \(2\times 2=4\)。

**不可做**：将 acquire/SC/RMW 标为 value 维（会丢失 \(\mathsf{sw}\) 区分）。

---

## 4.7 可检查性与反例

实现通过 `compare_reduction` 检查 `props_ok ∧ outcomes_ok`。IND 边界例 `cex_entangled_after_acquire`、`cex_shared_loc` 说明：默认提升相关读；`refuse` 时回退全枚举，避免静默错误。

---

## 4.8 本章小结

本章给出相关闭包、存在性扩展下的 T2⁺，以及值维剪枝下的 T2⁺⁺。下一章（实现）可对应代码结构；第 6 章用分类基准与失败谱验证有效性与不漏报。机械化证明路线见 [`s6-mechanization.md`](s6-mechanization.md)。
