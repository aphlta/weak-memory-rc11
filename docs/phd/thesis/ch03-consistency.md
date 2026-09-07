# 论文第 3 章草稿：执行图与一致性谓词

> 扩写自 [`RC11-ALIGNMENT.md`](../RC11-ALIGNMENT.md) §4–5 与 [`THEORY-v1.md`](../THEORY-v1.md) §1。  
> 状态：**可粘贴进正文的初稿**。

---

## 3.1 程序与事件

程序 \(P\) 由若干线程的事件序列组成。事件类型包括：原子/非原子 load、store、简化 RMW、fence、断言 `assert_eq`。每个访问带内存顺序标注；程序可声明观察变量集合 \(\mathsf{Obs}\)（实现字段 `observe`），用于定义观察结局。

记事件集合为 \(E\)。同线程事件按出现顺序给出程序序边集合 \(\mathsf{po}\subseteq E\times E\)（含与 fence 的序约束，实现中由程序序边构造）。

---

## 3.2 候选赋值与导出关系

一次**候选赋值** \(\sigma\) 为每个读事件指定同址写事件，即选定 \(\mathsf{rf}\) 关系的一个实例。在 \(\sigma\) 上按本器定义依次得到：

\[
\mathsf{po},\;
\mathsf{sw}(\sigma),\;
\mathsf{hb}=\mathsf{tc}(\mathsf{po}\cup\mathsf{sw}),\;
\mathsf{mo}\text{ 的存在性见证},\;
\mathsf{sc}\text{ 的存在性见证（若需要）}.
\]

其中 \(\mathsf{tc}\) 表示传递闭包。\(\mathsf{sw}\) 由第 2 章所列 release–acquire 与 fence 模式在 \(\sigma\) 下实例化；release sequence 取同线程后续写及 RMW 沿 `rf` 延长的简化规则。

---

## 3.3 存在性修改序（Co*）

文献要求一致执行带每地址一条 `mo` 全序并满足 COHERENCE 族约束。本文采用**存在性**判定：

1. 从 \(\mathsf{hb}\)、\(\mathsf{rf}\)、RMW 相邻等收集写→写的**强制**边；  
2. 对每地址做拓扑排序，若得到一条全序见证则接受，否则拒绝该 \(\sigma\)。

因此：

- **健全（相对本器）**：留下的执行均存在满足强制边的 `mo`。  
- **与「枚举所有 mo」不等价**：不探索「同一 `rf`、不同 `mo`」的乘积；对约简研究足够，并避免状态爆炸。

论文中应明确：一致性谓词是「`rf` 赋值 + 存在 `mo`/`SC` 见证」，不是 \((\mathsf{rf},\mathsf{mo})\) 全空间。

---

## 3.4 存在性 SC 全序

当程序含 `seq_cst` 访问或 fence 时，启用 SC 检查：要求 SC 事件上存在全序，强制包含相关 \(\mathsf{po}/\mathsf{hb}/\mathsf{mo}/\mathsf{rf}\) 以及由「读到较旧写」导出的 \(\mathsf{fr}\) 边。该检查用于排除教具级 SB \((0,0)\) 等弱态。

**措辞建议**：采用 RC11 **风格**的存在性 SC 全序检查（含 `fr`），以支撑 litmus 级 SC/fence 教具；不声称实现 Lahav et al. 全文的 `psc` 公理集合，也不做架构映射正确性证明。

---

## 3.5 一致执行、观察结局与布尔性质

定义：

\[
\mathsf{Exec}(P)
=
\{\,\sigma \mid
\sigma\text{ 为合法 rf 赋值，且存在 mo（及必要时 SC）见证}\,\}.
\]

对 \(e\in\mathsf{Exec}(P)\)，观察投影 \(\pi_{\mathsf{Obs}}(e)\) 取观察变量上的终值元组；观察结局集合

\[
\mathsf{Out}(P)=\{\,\pi_{\mathsf{Obs}}(e)\mid e\in\mathsf{Exec}(P)\,\}.
\]

布尔性质 \(\mathsf{Prop}(P)=(\mathsf{racy},\mathsf{assert\_fail})\)：是否存在含数据竞争的执行、是否存在断言失败的执行。数据竞争采用简化定义：冲突的非原子访问对之间不存在 \(\mathsf{hb}\)。

实现对应：`analyze_program(..., reduction="none")` 枚举 \(\mathsf{Exec}(P)\)；`outcome_set` 与 `summarize` 给出 \(\mathsf{Out}\) 与 \(\mathsf{Prop}\)。

---

## 3.6 与约简章的接口

第 4 章在固定 \(\mathsf{Exec}/\mathsf{Out}/\mathsf{Prop}\) 之上定义相关闭包 \(\mathsf{Cl}(P)\) 与约简执行集 \(\mathsf{Exec}_R(P)\)，并证明

\[
\mathsf{Out}(P)=\mathsf{Out}_R(P)
\quad\text{且}\quad
\mathsf{Prop}(P)=\mathsf{Prop}_R(P)
\]

（定理 T2⁺ / T2⁺⁺）。一致性谓词的任何后续收紧或放宽，都必须同步修订约简证明与 `compare_reduction` 守门实验。

---

## 3.7 本章小结

本章固定了本文的执行对象与一致性谓词：**存在性 `mo`/`SC` 见证下的 `rf` 枚举**。该选择使语义可实现、可实验，并为性质感知约简提供清晰的正确性接口。
