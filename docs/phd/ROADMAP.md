# 博士阶段路线图（P2：理论 + 工具）

> **冻结声明（档期 B）**  
> **现行档期是 B（工程落地 / herd 外部验收）**，见 [ROADMAP-B.md](ROADMAP-B.md)。  
> **本文是历史设计（A / P2：子集 + 自比 T2 + scale_noise 主证据），不授权按本文推进实现。**  
> 外部 oracle 是 herd7+riscv.cat，不是本文的噪声曲线。

---

**选定（历史）**：P2 + 真博士主线。  
**课题内核（历史）**：RC11 核心子集上的性质感知约简（观察结局保持）及其可执行实现。

## 1. 贡献主张（写作时钉死）

1. **语义对象**：给出本课题使用的 RC11 核心子集执行图与一致性谓词（相对文献可定位的子集）。  
2. **约简理论**：相关闭包（读 / 同步依赖 / rf 维）上的健全与相对完备（T2 → THEORY-v1 → 后续可机械化）。  
3. **可执行工具**：约简实现与定理编号对应；IND 可检查；实验支撑有效性与不漏报。

非贡献（明确不做进博士主叙事）：处理器实现、多芯片互连、异构设备。

## 2. 阶段

| 阶段 | 目标 | 主要交付 | 状态 |
| --- | --- | --- | --- |
| **S0** 底座 | 硕士级原型可用 | 验证器、R3/T2、实验、herdtools 弱态对照 | **已完成** |
| **S1** 定理稿 | 博士理论章骨架 | [THEORY-v1.md](THEORY-v1.md) | **已完成（本轮）** |
| **S2** 相关闭包 API | 约简对象从「相关读」升到「相关闭包含同步依赖边」 | `RelevanceClosure` / `compute_relevance_closure` | **已完成（本轮）** |
| **S3** 边级剪枝 | 在相关读内部按值压缩 rf 维 | 值维 + 存在性选写 + T2⁺⁺ | **已完成** |
| **S4** 语义对齐文 | 与 Batty/Lahav RC11 子集对照表 | [RC11-ALIGNMENT.md](RC11-ALIGNMENT.md) | **已完成** |
| **S5** 系统评测深化 | 全枚举基线、分类基准、失败谱 | [EVALUATION.md](EVALUATION.md) + `phd_eval_suite` | **已完成** |
| **S6** 机械化（可选） | 核心引理 Coq | [formal/](../../formal/) + [s6a-appendix](thesis/s6a-appendix.md) | **S6a+S6b 已落地；S6c 待续** |



## 3. S1–S5 验收

- [x] THEORY-v1 / T2⁺ / T2⁺⁺  
- [x] `RelevanceClosure` + SyncDep  
- [x] S3 值维剪枝（`edge_prune=value`）+ `mp_ra_dup_writes`  
- [x] smoke / phd 实验表不回归  
- [x] [RC11-ALIGNMENT.md](RC11-ALIGNMENT.md) 文献子集对齐  
- [x] [EVALUATION.md](EVALUATION.md) + [`results/phd_eval_suite.md`](../../results/phd_eval_suite.md)（分类 / full vs S3 / 失败谱）  
- [x] 正文草稿 [thesis/](thesis/)（第 2–6 章 + S6 范围）  
- [x] **S6a**：`formal/` 可 `make`；引理 1 + T2⁺ 结局工作定理；[s6a-appendix](thesis/s6a-appendix.md)  
- [x] **S6b**：`IndProp.v` 引理 5（Prop）+ 引理 6（IND/promote/refuse）  

## 4. 风险

- 边级剪枝若做错会静默丢弱态 → 必须先有 THEORY，再改枚举，并用 `compare_reduction` 守门。  
- 「完整 RC11」不可作为短期目标；博士贡献写在**子集 + 约简理论**上。  

## 5. 近期写作顺序

1. ~~用 RC11-ALIGNMENT 扩写第 2–3 章~~ → [thesis/ch02](thesis/ch02-semantics.md)、[ch03](thesis/ch03-consistency.md)  
2. ~~用 THEORY-v1 扩写第 4 章~~ → [thesis/ch04](thesis/ch04-reduction.md)  
3. ~~用 EVALUATION 扩写第 6 章~~ → [thesis/ch06](thesis/ch06-evaluation.md)  
4. 粘贴进学校模板、补引用与图表编号；第 1/7 章（绪论/总结）另起  
5. S6a+S6b 已完成（`formal/`）；S6c 或正文第 1/7 章按需  

