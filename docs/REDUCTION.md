# 性质感知约简（R3 / T2）

本文给出可写入论文的**相对本器语义**的约简定义、假设、引理与主定理。
实现：`explain_relevant_loads` / `ind_violation_reasons` / `compare_reduction`
（见 `weak_memory_verifier.py`）。

博士加强稿（相关闭包 / SyncDep / 值维剪枝 T2⁺⁺）：[`phd/THEORY-v1.md`](phd/THEORY-v1.md)；路线图：[`phd/ROADMAP.md`](phd/ROADMAP.md)。

> **不是**完整 C11/RC11 机械化定理；结论相对于本仓库的一致执行判定
> （rf 枚举 + 存在性 mo/SC + 本器 sw/hb）。

---

## 1. 预备定义

**程序** \(P\)：JSON 线程事件序列；观察变量集合 \(\mathsf{Obs}=\mathsf{observe}(P)\)。

**全量一致执行集** \(\mathsf{Exec}(P)\)：对所有读（load/rmw）做 rf 笛卡尔积，经本器
`evaluate_execution` 后无 `consistency` 失败的执行。

**观察投影** \(\pi_{\mathsf{Obs}}(e)\)：把执行 \(e\) 的线程环境合并后限制到 \(\mathsf{Obs}\)
（本教具假定观察名跨线程不冲突）。

**观察结局集合**
\[
\mathsf{Out}(P)=\{\,\pi_{\mathsf{Obs}}(e)\mid e\in\mathsf{Exec}(P)\,\}.
\]

**布尔性质** \(\mathsf{Prop}(P)=(\mathsf{is\_racy},\mathsf{assertion\_can\_fail})\)，
由 \(\mathsf{Exec}(P)\) 是否存在竞争 / 断言失败决定（**不**要求见证条数相等）。

**基础相关读** \(R_0(P)\)：由 outcome / assertion / synchronization / race 四类规则标出
（`explain_relevant_loads(..., ind_mode="off")`）。

**约简执行集** \(\mathsf{Exec}_R(P;R)\)：只对 \(R\) 中的读做笛卡尔积；对其余读做
**存在性扩展**（`extend_mode="exists"`）：任意找到一组使 mo/SC 通过的 rf 即可保留该相关赋值。

---

## 2. 独立噪声假设（IND）

令 \(R\supseteq R_0(P)\)。写 \(\mathsf{CritLoc}(R)\) 为 \(R\) 中读事件的地址集合。

**静态 IND 违例**（实现中的充分检查，见 `ind_violation_reasons`）：读 \(r\notin R_0\) 违例，若

1. **同址**：\(r.\mathsf{loc}\in\mathsf{CritLoc}(R_0)\)；或
2. **acquire 后读 release-prefix 地址**：存在某线程上 release/SC 写（或相应 fence）之前
   写过的地址集合 \(L_{\mathsf{rp}}\)（`_release_prefix_locations`），且
   \(r.\mathsf{loc}\in L_{\mathsf{rp}}\)，并且 \(r\) 同线程程序序上已有 acquire/SC 读或 fence。

**假设 IND(\(P\))**：基础相关下无上述违例，即 `ind_violation_reasons(P,R_0)=∅`。

典型满足：独立 `noise` 地址上的 relaxed 读，且位于 acquire **之前**（如 `scale_mp_*`）。

典型违例：acquire **之后**再读曾写入 release-prefix 的地址（`cex_entangled_after_acquire.json`）；
或与观察相关读同址的「伪噪声」（`cex_shared_loc.json`）。

**实现策略（可检查）**

| `ind_mode` | 行为 |
| --- | --- |
| `promote`（默认） | 把违例读提升为相关（闭包），恢复「有效相关集上的 IND」 |
| `refuse` | 若有违例则拒绝约简，回退全枚举 |
| `off` | 不提升（仅实验 / 反例） |

---

## 3. 引理

以下均相对本器语义；扩展模式为 `exists`。

### 引理 A（观察由相关读决定）

若一切 \(\mathsf{target}\in\mathsf{Obs}\) 的读都属于相关集 \(R\)，则对任意一致执行 \(e\)，
\(\pi_{\mathsf{Obs}}(e)\) 完全由 \(e\) 在 \(R\) 上的 rf 赋值 \(\sigma_R\) 决定。

*证明梗概*：观察变量只由 target∈Obs 的读写入环境；这些读∈\(R\)，其 rf 即 \(\sigma_R\)。□

### 引理 B（相关赋值的可扩展性）

设 \(e\in\mathsf{Exec}(P)\)，\(\sigma_R\) 为其在 \(R\) 上的限制。则存在对 \(P\setminus R\) 的 rf 扩展
使合并后的赋值通过本器 mo/SC（至少 \(e\) 自身即为一证）。因此存在性搜索在「该 \(\sigma_R\)
曾出现于某全量执行」时不会误拒。□

### 引理 C（健全：约简不制造新观察结局）

若 \(e'\in\mathsf{Exec}_R(P;R)\)，则存在 \(e\in\mathsf{Exec}(P)\) 与 \(e'\) 在全部读上 rf 相同
（约简得到的赋值本身就是一份合法全量 rf）。故 \(\mathsf{Out}_R\subseteq\mathsf{Out}\)。□

### 引理 D（相对完备：不丢观察结局）

对任意 \(e\in\mathsf{Exec}(P)\)，令 \(\sigma_R\) 为限制。由引理 B，存在性扩展找到某 \(e'\)，
且由引理 A，\(\pi_{\mathsf{Obs}}(e')=\pi_{\mathsf{Obs}}(e)\)。故 \(\mathsf{Out}\subseteq\mathsf{Out}_R\)。□

### 引理 E（布尔性质）

`is_racy` / `assertion_can_fail` 只依赖：是否存在竞争对、是否存在断言失败执行。
竞争检测保留全部非原子访问（race 类相关）；断言变量由 assertion/outcome 类相关覆盖。
在 \(R\supseteq R_0\) 且扩展为 exists 时，布尔性质与全枚举一致。□

> 见证**条数**可以减少（多个无关 rf 坍缩为一次扩展）。T2 **不**要求
> `executions_with_*` 计数相等；`compare_reduction` 另给 `witness_counts_ok` 诊断。

---

## 4. 主定理 T2

**定理（T2：IND 下的观察保持约简）**  
设扩展为存在性搜索。若 \(\mathsf{IND}(P)\) 成立，取 \(R=R_0(P)\)；或更一般地取
\(R\) 为 `promote` 闭包后的相关集（此时对有效 \(R\) 无静态 IND 违例）。则

1. \(\mathsf{Out}(P)=\mathsf{Out}_R(P)\)；
2. \(\mathsf{Prop}(P)=\mathsf{Prop}_R(P)\)。

*证明*：引理 C+D ⇒ (1)；引理 E ⇒ (2)。□

**推论（promote 健全性）**  
默认 `ind_mode=promote` 时，即或源程序违反 IND，提升后对有效相关集仍适用 T2；
代价是相关读变多、约简比下降。

**推论（refuse 安全性）**  
`ind_mode=refuse` 在违例时回退 \(\mathsf{Exec}(P)\)，平凡保持；无违例时同 T2。

---

## 5. 反例与反模式（C）

| 例子 | 说明 |
| --- | --- |
| `cex_entangled_after_acquire.json` | acquire 后读 release-prefix 地址 `n`：基础规则当无关；`promote` 加 `ind:`；`off`+`first_candidate` 丢掉 `a=1` |
| `cex_shared_loc.json` | 与观察读同址的伪噪声：`promote` 提升；独立噪声用例不受影响 |

**为何不能 `first_candidate` / 单默认写**：固定 \(\sigma_R\) 后，错误的无关 rf 可使 mo 失败，
整份相关赋值被丢弃，从而丢失观察结局（反例见 smoke 中对 `cex_entangled_after_acquire` 的检查）。

**本论证不覆盖**：CAS 失败路径、consume/thin-air、多芯片可见性、观察变量声明错误
（用户把该观察的变量漏出 `observe`）。

---

## 6. 如何验收

```bash
python3 smoke_check.py
python3 benchmark_compare.py --write-results
python3 -c "
from pathlib import Path
from weak_memory_verifier import compare_reduction, analyze_program, explain_relevant_loads, load_program
p=Path('examples/cex_entangled_after_acquire.json')
print(compare_reduction(p))
print(explain_relevant_loads(load_program(p), ind_mode='promote'))
print(analyze_program(p, 'relevant', ind_mode='refuse').stats['ind_refused'])
"
```

`compare_reduction`：`props_ok` ∧ `outcomes_ok`（T2）；`witness_counts_ok` 仅供参考。
