# 现行档期 B：工程落地（herd 外部验收）

> **一句话**：外部 oracle 是 **herd7 + riscv.cat（公开 RVWMO litmus）**，不是本器自比的 `scale_noise` / 512→4。

**选定**：档期 **B（工程落地）**。旧 **A / P2**（子集 + 自比 T2 + 噪声曲线当主证据）**已冻结**，见 [ROADMAP.md](ROADMAP.md) 文首声明；不得再按其「下一优先」堆理论章或噪声主表。

---

## 1. 贡献主张（B）

1. 在 **RC11 风格教具**（JSON 事件）上实现性质感知约简（观察结局 / 弱态布尔保持）。  
2. 用 **公开 RVWMO litmus** 的 **herd7 + `riscv.cat` 判定**做外部验收：同一弱态谓词下，herd 允/禁 ↔ 本器全枚举 ↔ 本器约简 三者布尔对齐；并报告配对行上的组合数 full / reduced。  
3. 诚实标注 **编码差**（如 `fence.rw.rw` ≠ 本器 `seq_cst` fence）；无诚实配对标 `UNPAIRED`，不假装覆盖。

### 非贡献

- 完整 RC11 / 完整 RVWMO / 与 herd 语义互模拟  
- 处理器实现、多芯片、异构、GPU、`die_id` / `propagate`  
- 本器作为 DUT / 香山正确性 oracle（芯片验收仍是：DUT 观察态 ⊆ Allowed(herd7, riscv.cat)）  
- 本器 `assert_eq` / race 当作硅前对错标准  

---

## 2. 阶段

| 阶段 | 目标 | 交付 | 状态 |
| --- | --- | --- | --- |
| **B0** 文档对齐 | 只剩一只眼：现行=B，A/P2 冻结 | 本文 + 旧文档冻结框 | **已完成**（冻结框在；HETEROGENEOUS-SCOPE 正文已从本机 transcript 快照恢复） |
| **B1** herd 定量对照 | 07 规格 8 条 litmus 可复现表 | `scripts/herd_landing.py`、`results/herd_landing.*` | **已完成**（B1c：CoWR0/官方 CoRR 已按 herd States 配对；CoWW 已按「见证空转」降为 UNPAIRED；真配对 6；LB+addrs 仍 UNPAIRED） |
| **B2** 单向轨迹对接 | 只设计、不实现 | [B2-TRACE-ADAPTER.md](B2-TRACE-ADAPTER.md) + §4 | **设计已写、未实现** |
| **B3** 约简对象转向 | 从噪声 load 转向「影响 exists 弱态的读/同步边」 | 后轮 | **未开始** |

落地主表：**不要**把 `scale_noise` / 512→4 写进 `herd_landing`。旧 `phd_eval_suite` 可保留作历史自比，不是现行外部验收。

---

## 3. B1 验收口径（落地版 T2）

对 **已配对** 行：

- herd = Never → 本器 `none` 与 `relevant` 均**禁止**该弱态  
- herd = Sometimes → 本器 `none` 与 `relevant` 均**仍能检出**该弱态  
- `none` 与 `relevant` 对弱态布尔一致  

`UNPAIRED` / `NO-RVWMO-PEER` **不计入**通过率，但必须出现在表中。

再生：

```bash
python3 scripts/herd_landing.py --write-results
```

---

## 4. B2 单向对接（设计已写、未实现）

详见 **[B2-TRACE-ADAPTER.md](B2-TRACE-ADAPTER.md)**。要点：

1. 输入在 **xs-am-verify** 的 `events.jsonl`；`W`/`Wg`；`commit_cycle` 锚 po，`visible_cycle` 定 co。  
2. **本器永远不吃 jsonl**，不加 `commit_cycle` 等字段。  
3. 将来若做，只能**单向**：轨迹→关系留在 xs-am-verify；本器仍是 JSON 教具。  
4. 对照物是 **herd 的 exists**，不是本器 `assert_eq`。  
5. 约简对象升到「影响 exists 的读/同步边」是 **B3**；本阶段不改 `relevant_loads`。  

**禁止**：解析 jsonl、加 Event 字段、写适配器 Python、改约简公式。

---

## 5. 与旧材料的关系

| 材料 | 地位 |
| --- | --- |
| [ROADMAP.md](ROADMAP.md)（P2/S0–S6） | **冻结的 A 叙事** |
| [EVALUATION.md](EVALUATION.md)、`phd_eval_suite`、`scale_noise` | 历史自比；非现行外部 oracle |
| [thesis/](thesis/) ch02–ch06 | P2 草稿，**尚未按 B 重写** |
| [HERD-COMPARISON.md](../HERD-COMPARISON.md) | 现行入口指向 `herd_landing`；旧「同向」表降为附录 |
| `formal/` S6a/b | 可选理论附件；不替代 herd 验收 |

---

## 6. 芯片侧提醒（本仓库不实现）

DUT 验收继续在 `xs-am-verify`：观察态 ⊆ Allowed(herd7, riscv.cat)。  
本器最多：教具级配对 + 约简后弱态结论不漂。
