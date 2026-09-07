# 实验评测说明（S5，论文第 6 章骨架）

> **冻结声明（档期 B）**  
> **现行外部验收是 herd_landing（herd7+riscv.cat）**，见 [ROADMAP-B.md](ROADMAP-B.md) 与 `results/herd_landing.md`。  
> **本文是历史 P2/S5 自比评测骨架（scale_noise 主证据），不授权把噪声曲线当现行落地主表。**

再生数据：

```bash
python3 scripts/phd_eval_suite.py --write-results
python3 scripts/bench_timing.py --repeats 5 --write-results   # 可选时间曲线
python3 scripts/herd_compare.py --write-results               # 可选弱态对照
```

结果快照：[`results/phd_eval_suite.md`](../../results/phd_eval_suite.md)、[`results/timing_curve.md`](../../results/timing_curve.md)、[`results/herd_comparison.md`](../../results/herd_comparison.md)。

分类定义：[`examples/taxonomy.json`](../../examples/taxonomy.json)。

---

## 1. 评测问题

在本课题 **RC11 核心子集**（见 [RC11-ALIGNMENT.md](RC11-ALIGNMENT.md)）上回答：

1. **有效性**：性质感知约简（含 S3 值维）相对全枚举，rf 组合规模下降多少？  
2. **正确性**：约简是否保持观察结局集合与 race/assert 布尔结论（T2⁺⁺）？  
3. **不漏报**：弱态 / race / 断言失败在噪声程序上约简后是否仍可检出？  
4. **S3 边际收益**：相对「只做相关读约简、不做值维」再降多少？

---

## 2. 基准分类

| 类别 | 作用 |
| --- | --- |
| `MP_RA` | RA / RS 消息传递正确性 |
| `MP_fence_SC` | relaxed 弱态 vs fence/SC |
| `SB_LB` | SB/LB 弱态与 SC 禁止 |
| `coherence_RMW` | 存在性 mo / RMW |
| `scale_noise` | 噪声规模曲线（主有效性证据） |
| `bug_finding` | race / assert 可败 |
| `ind_boundary` | IND 提升边界 |

同一程序可只归属一类（taxonomy 首次命中）；`bug_finding` 中与 MP 重叠的条目以 MP 类为主统计，失败谱仍单独列出。

---

## 3. 指标

| 符号 | 含义 |
| --- | --- |
| `full` | 全部读 rf 笛卡尔积规模（全枚举基线） |
| `reduced_no_s3` | 相关读 × 写身份（`edge_prune=off`） |
| `reduced_s3` | 相关读 + 值维压缩（默认） |
| `saved_vs_full` | \((\mathrm{full}-\mathrm{reduced\_s3})/\mathrm{full}\) |
| `s3_extra` | \((\mathrm{noS3}-\mathrm{S3})/\mathrm{noS3}\) |
| T2⁺⁺ | `props_ok ∧ outcomes_ok` |

时间曲线（辅助）：`scripts/bench_timing.py` 对规模例取中位数墙钟。

---

## 4. 主要结论（快照：`phd_eval_suite`，37 程序）

1. **T2⁺⁺ 全部通过**（`props_ok ∧ outcomes_ok`）。  
2. **`scale_noise`（15）**：均 saved≈0.90；full 最大 512 → reduced 恒为 4（saved 达 0.992）。  
3. **失败谱不漏报**：可 race 2、断言可败 5；抽检 `racy_counter_with_noise` / `mp_relaxed_with_noise` / `sb_with_noise` 全量均检出。  
4. **S3 边际**：全集均再降≈0.014；`mp_ra_dup_writes` 上 noS3=8→S3=4（S3↓=0.5）；多数无同值冗余 litmus 上 S3↓=0。  
5. herdtools 弱态对照仅作定性同向，见 [HERD-COMPARISON.md](../HERD-COMPARISON.md)。

---

## 5. 威胁效度

- 输入为教具 JSON，非完整 C 程序。  
- 一致性为存在性 mo/SC，非完整 RC11。  
- 缩减主指标为组合数；时间受解释器实现影响。  
- 失败谱覆盖典型模式，非工业缺陷库。

---

## 6. 第 6 章建议小节

正文草稿已扩写为 [`thesis/ch06-evaluation.md`](thesis/ch06-evaluation.md)。

建议结构：实验设置 → 基准分类 → 有效性 → 正确性与不漏报 → S3 消融 → herdtools 对照 → 讨论与局限。