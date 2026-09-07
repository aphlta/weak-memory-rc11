# 本原型 ↔ herdtools 对照

> **现行外部验收是 B1 `herd_landing`（07 规格 8 条）**，不是本页旧「同向」表。  
> 再生落地主表：`python3 scripts/herd_landing.py --write-results`  
> 快照：[`results/herd_landing.md`](../results/herd_landing.md) / [`results/herd_landing.json`](../results/herd_landing.json)  
> 档期：[phd/ROADMAP-B.md](phd/ROADMAP-B.md)

外部 oracle：**herd7 + riscv.cat**。本器是 RC11 风格教具枚举器；同结论 ≠ 语义等价（尤其 `fence.rw.rw` ≠ `seq_cst` fence）。

芯片验收仍在 `xs-am-verify`：DUT 观察态 ⊆ Allowed(herd7, riscv.cat)。本器不做 DUT oracle。

---

## 附录：历史「弱态同向」表

旧脚本 `python3 scripts/herd_compare.py --write-results` 仍可运行，输出仅写入 `results/herd_comparison.*`（不再覆盖本文）。  
该表是定性同向附录，**不是**现行配对通过率口径；缺 07 的 UNPAIRED 行与 full/reduced 列。

见 [`results/herd_comparison.md`](../results/herd_comparison.md)。
