# 约简理论稿 THEORY-v1（博士 P2）

本文是 [REDUCTION.md](../REDUCTION.md)（R3/T2）的**加强版定理骨架**，供博士论文第 3–4 章扩写。  
结论仍相对本原型一致性判定（rf 枚举 + 存在性 mo/SC + 本器 sw/hb），并给出与代码的符号对应。

实现入口：`compute_relevance_closure` / `compare_reduction`（`weak_memory_verifier.py`）。

---

## 0. 符号与代码对应

文献定位见 [RC11-ALIGNMENT.md](RC11-ALIGNMENT.md)。下表为约简理论符号与代码。

| 理论符号 | 含义 | 代码 |
| --- | --- | --- |
| \(P\) | 程序 | `Program` / JSON |
| \(\mathsf{Obs}\) | 观察变量 | `program.observe` |
| \(\mathsf{Exec}(P)\) | 全量一致执行 | `analyze_program(..., reduction="none")` |
| \(\pi_{\mathsf{Obs}}\) | 观察投影 | `outcome_tuple` / `outcome_set` |
| \(\mathsf{Out}(P)\) | 观察结局集合 | `outcome_set` |
| \(\mathsf{Prop}(P)\) | \((\mathsf{racy},\mathsf{assert})\) 布尔 | `summarize` 中布尔字段 |
| \(R_0(P)\) | 基础相关读 | `explain_relevant_loads(..., ind_mode="off")` |
| \(\mathsf{Cl}(P)\) | 相关闭包（含 IND） | `compute_relevance_closure` |
| \(\mathsf{SyncDep}\) | 潜在同步依赖边 | `RelevanceClosure.sync_deps` |
| \(\mathsf{Exec}_R\) | 约简执行集 | `analyze_program(..., reduction="relevant")` |

---

## 1. 执行图对象（本课题子集）

一次**候选赋值** \(\sigma\) 为每个读事件指定同址写事件（rf）。  
在 \(\sigma\) 上按本器定义依次得到：

\[
\mathsf{po},\;
\mathsf{sw}(\sigma),\;
\mathsf{hb}=\mathsf{tc}(\mathsf{po}\cup\mathsf{sw}),\;
\mathsf{mo}\text{ 存在性},\;
\mathsf{sc}\text{ 存在性}.
\]

若 mo/SC 存在性检查通过，则 \(\sigma\) 对应 \(e\in\mathsf{Exec}(P)\)（再附带 race/assert 解释）。

**本子集包含**：relaxed/acquire/release/acq_rel/seq_cst、fence、release sequence、简化 RMW、存在性 mo（Co*）、存在性 SC（含 fr）、简化 DRF。  
**本子集不包含**：consume、thin-air、CAS 失败、混合宽度、完整 psc 全部分支。

> 与文献的包含关系见 [RC11-ALIGNMENT.md](RC11-ALIGNMENT.md)；不宣称全模型。

---

## 2. 相关闭包（从相关读到同步依赖）

### 定义 2.1（基础相关读 \(R_0\)）

读 \(r\) 属于 \(R_0(P)\)，当且仅当至少一条成立：

1. **outcome**：\(r.\mathsf{target}\in\mathsf{Obs}\)  
2. **assertion**：\(r.\mathsf{target}\) 流入 assert/guard  
3. **synchronization**：acquire/SC 读（或可延长 RS 的 RMW）可能影响后续 hb/SC  
4. **race**：非原子读  

### 定义 2.2（IND 提升）

静态 IND 违例集 \(\mathsf{Viol}(P,R)\) 同 REDUCTION.md §2。  
\(\mathsf{Cl}_{\mathsf{read}}(P)\) 为对 \(R_0\) 迭代加入 \(\mathsf{Viol}\) 的不动点（实现：`ind_mode=promote`）。

### 定义 2.3（潜在同步依赖边）

\[
\mathsf{SyncDep}(P)=
\{
\,(w,r)\mid
r\in\mathsf{Cl}_{\mathsf{read}}(P),\;
r\text{ 为 acquire/SC 读},\;
w\text{ 为同址 release/SC 写（含 init 以外的候选）}
\,\}.
\]

说明：这是**静态上界**（可能 sw 的边），不是某次执行里真实的 \(\mathsf{sw}\)。  
博士 S3 将把「真实可能影响 \(\mathsf{Out}\) 的 rf 边」从该上界中再截断。

### 定义 2.4（相关闭包）

\[
\mathsf{Cl}(P)=
\big(
\mathsf{Cl}_{\mathsf{read}}(P),\;
\mathsf{SyncDep}(P),\;
\mathsf{RfDim}(P)=\mathsf{Cl}_{\mathsf{read}}(P)
\big).
\]

当前枚举维 \(\mathsf{RfDim}\) 仍等于相关读集合；S3 起允许 \(\mathsf{RfDim}\) 上的**边集**真子集。

---

## 3. 约简语义

固定 \(\mathsf{Cl}(P)\)。约简模式：

1. 对每个 \(r\in\mathsf{RfDim}\) 枚举其 rf 候选；  
2. 对 \(r\notin\mathsf{Cl}_{\mathsf{read}}\) 做存在性扩展（`extend_mode=exists`）；  
3. 通过 mo/SC 者进入 \(\mathsf{Exec}_R(P)\)。

---

## 4. 引理与主定理

以下均设扩展为存在性搜索；\(\mathsf{Cl}\) 按定义 2.4。

### 引理 1（观察功能依赖）

若 \(\{r\mid r.\mathsf{target}\in\mathsf{Obs}\}\subseteq\mathsf{Cl}_{\mathsf{read}}\)，则 \(\pi_{\mathsf{Obs}}(e)\) 由 \(e\) 在 \(\mathsf{Cl}_{\mathsf{read}}\) 上的 rf 完全决定。

### 引理 2（可扩展性）

任意 \(e\in\mathsf{Exec}(P)\) 在 \(\mathsf{Cl}_{\mathsf{read}}\) 上的限制均可被存在性扩展恢复为某一致执行（至少 \(e\) 自身）。

### 引理 3（健全）

\(\mathsf{Out}(\mathsf{Exec}_R(P))\subseteq\mathsf{Out}(P)\)。

### 引理 4（相对完备）

\(\mathsf{Out}(P)\subseteq\mathsf{Out}(\mathsf{Exec}_R(P))\)。

### 引理 5（布尔性质）

\(\mathsf{Prop}(P)=\mathsf{Prop}_R(P)\)（见证条数不必相等）。

### 引理 6（IND 静态充分性）

若 \(\mathsf{Viol}(P,R_0)=\emptyset\)，则噪声读不落入 \(\mathsf{Cl}_{\mathsf{read}}\) 的构造与引理 1–5 的前提相容；若违例非空，`promote` 扩大 \(\mathsf{Cl}_{\mathsf{read}}\) 后恢复该相容性，`refuse` 则退回 \(\mathsf{Exec}(P)\)。

### 主定理 T2⁺（相关闭包约简）

在存在性扩展下，对 \(\mathsf{Cl}(P)\) 有：

\[
\mathsf{Out}(P)=\mathsf{Out}_R(P)
\quad\text{且}\quad
\mathsf{Prop}(P)=\mathsf{Prop}_R(P).
\]

*证明结构*：引理 3+4 ⇒ 结局；引理 5 ⇒ 布尔；引理 1–2 支撑 4；引理 6 说明实现侧 IND 策略。□

### 推论（同步依赖边的角色）

\(\mathsf{SyncDep}\) 不改变当前 \(\mathsf{Exec}_R\) 的枚举维，但给出 S3 边级剪枝的**合法搜索空间上界**：任何被删 rf 边若可能改变某 \(r\in\mathsf{Cl}_{\mathsf{read}}\) 的 sw/hb 形状，则不可删。

---

## 5. S3：值维边级剪枝（已落地）

**目标**：对 \(r\in\mathsf{Cl}_{\mathsf{read}}\)，若写身份不影响同步形状，则按**读值**压缩枚举维，值类内存在性选写。

### 定义 5.1（维分类）

- **identity 维**：RMW，或 acquire/SC 读 → 必须按写事件枚举（身份进入 \(\mathsf{sw}\)/SC/相邻）。  
- **value 维**：其余相关读 → 枚举 \(\mathrm{vals}(r)=\{w.\mathsf{value}\mid w\in W_r\}\)，对选定值 \(v\) 在 \(\{w\in W_r: w.\mathsf{value}=v\}\) 上存在性扩展。

实现：`is_identity_rf_dimension` / `is_value_rf_dimension`；`edge_prune="value"|"off"`。

### 引理 7（值维观察依赖）

对 value 维读 \(r\)，\(\pi_{\mathsf{Obs}}\) 中由 \(r\) 贡献的分量只依赖所读**值**，不依赖写事件身份。

### 引理 8（值类可扩展性）

若某全量执行以写 \(W\)（值为 \(v\)）为 \(r\) 的 rf 源，则在固定其余 identity 赋值后，值类 \(\{w: w.\mathsf{value}=v\}\) 上的存在性搜索能找到某一致扩展（至少 \(W\) 自身在该类中）。

### 定理 T2⁺⁺（含 S3）

在 `edge_prune=value` 与存在性扩展下，仍有 \(\mathsf{Out}=\mathsf{Out}_R\) 且 \(\mathsf{Prop}=\mathsf{Prop}_R\)。

*证明梗概*：identity 维保持同步可区分性；value 维由引理 7–8 归约到「按值枚举 + 类内存在性」，同引理 2–4。□

**展示例**：`mp_ra_dup_writes.json`（三笔同值 `x=1`）相关写积 \(2\times 4=8\) → 值维 \(2\times 2=4\)。

**不可做**：把 acquire/SC/RMW 标成 value 维（会丢 sw 区分，破坏弱态判定）。

---

## 6. 与实验的接口

- 组合缩减：`full` / `naive_relevant_product` / `explored`（含 S3）  
- 正确性：`props_ok` ∧ `outcomes_ok`  
- 弱态对照：herdtools litmus（教学同向）  
- 闭包可解释：`--explain-relevant` + `sync_deps` + identity/value 划分  

---

## 7. 修订记录

| 版本 | 内容 |
| --- | --- |
| T2 / REDUCTION.md | 观察保持 + IND |
| THEORY-v1 | 相关闭包、SyncDep、T2⁺ |
| **S3** | 值维边级剪枝、T2⁺⁺、引理 7–8 |
| **S4** | [RC11-ALIGNMENT.md](RC11-ALIGNMENT.md) 文献子集对齐 |
