# 与文献 RC11 / C11 的子集对齐（S4）

本文供博士论文第 2–3 章扩写：把本原型语义**定位**到 C/C++11 与 RC11 文献中的对象，写清包含、简化与故意省略。  
**不宣称**实现完整 C11 或完整 Lahav et al. RC11。

主要文献锚点：

- Batty et al.，C/C++11 公理化 concurrency 语义（执行图、`sb`/`rf`/`mo`、`sw`/`hb` 等）。  
- Lahav, Vafeiadis, Kang, Hur, Dreyer，*Repairing Sequential Consistency in C/C++11*（PLDI’17），即 **RC11**（修复 SC 相关缺陷后的模型）。  

本仓库实现入口见 [ARCHITECTURE.md](../ARCHITECTURE.md)；约简理论见 [THEORY-v1.md](THEORY-v1.md)。

---

## 1. 一句话定位

本原型实现的是：

> **面向教学与约简研究的 RC11 风格核心子集**：  
> 原子顺序 + fence +（简化）release sequence +（简化）RMW + 存在性 per-loc `mo`（Co*）+ 存在性 SC 全序（含 `fr`/`rb`）+ 简化 DRF；  
> **外加**本课题的性质感知约简（T2⁺⁺）。

它回答的问题是：「在该子集下，给定 JSON 小程序的观察结局 / race / 断言是否成立，以及约简是否保持。」  
它不回答：「任意 C++ 程序是否符合完整 RC11。」

---

## 2. 关系与对象对照表

文献符号按 RC11/C11 常用写法；本器列对应实现。

| 文献对象 | 文献含义（简述） | 本原型 | 对齐程度 |
| --- | --- | --- | --- |
| 事件 \(E\) | 访问 / fence / RMW 等 | `Event`（load/store/rmw/fence/assert） | **部分**：无 CAS 失败路径、无混合宽度、无 lock |
| `sb` / `po` | 同线程顺序 | `_program_order_edges` | **对齐**（含 fence） |
| `rf` | 读从哪次写取值 | `_reads_from_candidates` + 赋值 | **对齐意图**：枚举候选；初值写为虚拟 init |
| `mo` | 每地址写的修改序 | `_modification_order`（**存在性**拓扑） | **简化**：不枚举全部 `mo`，只检查 Co* 强制边可扩展为全序 |
| `rb` / `fr` | \(\mathrm{rf}^{-1};\mathrm{mo}\)（除自环） | SC 检查中的 fr 边；Co* 里用 hb/rf 推 mo | **部分**：用于 SC 与 coherence，未单独导出全局 `rb` 关系对象 |
| `rs` | release sequence | `_release_sequence_heads` 等 | **简化子集**：同线程后续写 + 沿 rf 的 RMW 延长；未覆盖文献中全部 RS 细则 |
| `sw` | 同步 | `_compute_sync_with` | **核心 RA + fence 模式**；见 §3 |
| `hb` | \((\mathrm{sb}\cup\mathrm{sw})^+\) | `_transitive_closure(po ∪ sw)` | **对齐定义形状** |
| `eco` | 扩展一致性序 | 未显式构造 | **省略**（coherence 用 Co* 存在性代替） |
| SC 全序 \(S\) / `psc` | SC 事件约束 | `_check_sc_order`（存在性全序） | **简化**：强制 po/hb/mo/rf/fr 边可扩展；**非**完整 `pscbase ∪ pscfence` 逐条边集 |
| DRF / race | 数据竞争 | 简化「非原子冲突且无 hb」 | **简化教学定义** |
| no-thin-air | 禁止无中生有 | 无 | **未做** |
| consume / `dob` | 依赖序 | 无 | **未做** |

---

## 3. `sw` 覆盖范围

文献 RC11：`sw` 由 release/`rs` 与 acquire 读（及 fence 变体）等定义。

本器显式支持的模式（见 `_compute_sync_with` 注释与实现）：

1. release/SC **写** 被 acquire/SC **读** 读到（含读到 RS 成员）。  
2. release **fence** 与其后写、acquire 读的组合。  
3. 写与其后 acquire **fence**。  
4. release fence 与 acquire fence。  

**相对文献的简化**：

- RS 规则取「同线程同址后续原子写 + RMW 沿 rf 延长」的可实现子集。  
- 未机械翻译论文中每条 fence-SC 边的全部 `psc` 侧面。  
- 无 consume，故无 `dob` 导出的同步。

---

## 4. Coherence / `mo`：存在性 vs 全称枚举

文献：一致执行带一条（每地址）`mo` 全序，并满足 COHERENCE-WW/WR/RW/RR 等。

本器：

- 从 hb/`rf`/RMW 相邻收集**强制**写→写边；  
- 用拓扑排序求一条见证 `mo`；失败则拒绝该 `rf` 赋值。  

因此：

- **健全方向（相对本器）**：留下的执行都存在满足强制边的 `mo`。  
- **与「枚举所有 mo」不等价**：不探索「同一 rf、不同 mo」的乘积；对约简研究足够，且避免状态爆炸。  
- 并发写「先读到 2 再读到 1」在存在性 `mo` 下可合法（定向 `mo`），与 C11 叙述一致；见 ARCHITECTURE。

论文中应写明：本课题一致性谓词是 **「rf 赋值 + 存在 mo/SC 见证」**，不是「(rf, mo) 全空间」。

---

## 5. SC：RC11 修复意图 vs 本器简化

RC11 动机之一是修复原 C11 中 SC 原子/`fence` 的缺陷，并给出更干净的 SC 约束（与 Power 编译等结果相关）。

本器 SC：

- 仅在出现 `seq_cst` 访问/fence 时启用；  
- 要求 SC 事件上存在全序，强制包含相关 `po`/`hb`/`mo`/`rf` 以及由「读到较旧写」导出的 `fr`；  
- 用于杀掉教具级 SB (0,0) 等。  

**对齐说法（推荐论文措辞）**：

> 本器采用 **RC11 风格的存在性 SC 全序检查**（含 fr），以支撑 litmus 级 SC/fence 教具；  
> 不声称实现 Lahav et al. 全文的 `psc` 公理集合，也不做架构映射正确性证明。

---

## 6. 操作子集（语言层面）

| 构造 | 本原型 | 相对完整 C11 |
| --- | --- | --- |
| `memory_order_relaxed/acquire/release/acq_rel/seq_cst` | 有 | 有 |
| `atomic_thread_fence` | 有（JSON `fence`） | 有 |
| RMW（固定新值） | 有，简化 | 完整 CAS/FAA 等更富 |
| CAS 失败 / strong–weak | 无 | 有 |
| `memory_order_consume` | 无 | 有（RC11 亦弱化其角色） |
| 非原子 + race | 简化检测 | 完整 UB 叙事 |
| 混合大小 / 位域 | 无 | 有 |

输入为 JSON 事件序列，不是 C 源经编译器降低后的全部行为。

---

## 7. 与约简贡献的接口（为何子集够用）

博士贡献主线是 **性质感知约简（T2⁺⁺）**，不是「再实现一个完整 RC11 检查器」。

子集选取原则：

1. **足够**：MP/SB/LB、RA、fence、RS、RMW、SC 教具与约简实验可陈述。  
2. **可证明相对本器**：一致性谓词固定后，约简健全/相对完备可写（THEORY-v1）。  
3. **可扩展**：`RelevanceClosure` / SyncDep / 值维剪枝不绑死完整 `psc`。  

完整 RC11 机械化或与 `cpp11_simp` 等工具的互模拟，列作**后续工作**，不作为本阶段验收。

---

## 8. 论文第 2–3 章建议结构

1. **相关工作**：C11 公理化、RC11 修复、执行图探索与约简。  
2. **本课题语义**：用本节对照表定义「RC11 核心子集」；附「未覆盖清单」。  
3. **一致性谓词**：`Exec(P)` = rf 赋值且存在 mo/SC 见证。  
4. **导向第 4 章**：在该谓词上陈述 T2⁺⁺。  

可引用句（可直接改写进正文）：

> 本文不重新提出内存模型，而在 Lahav et al. RC11 所代表的公理化传统下，固定一个可实现的核心子集，并在该子集上研究观察结局保持的状态空间约简。

---

## 9. 修订记录

| 版本 | 内容 |
| --- | --- |
| **S4** | 首版文献对齐表与论文写作接口 |
