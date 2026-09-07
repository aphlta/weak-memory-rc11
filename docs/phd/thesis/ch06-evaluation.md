# 论文第 6 章草稿：实验评测

> 数据来源：[`results/phd_eval_suite.md`](../../../results/phd_eval_suite.md)、[`timing_curve.md`](../../../results/timing_curve.md)、[`herd_comparison.md`](../../../results/herd_comparison.md)。  
> 方法说明：[`EVALUATION.md`](../EVALUATION.md)。再生：`python3 scripts/phd_eval_suite.py --write-results`。  
> 状态：**可粘贴进正文的初稿**；表格数字以仓库最新结果为准。

---

## 6.1 评测问题

在本文 **RC11 核心子集**（第 2–3 章）上，验证性质感知约简（第 4 章，含值维剪枝）的以下问题：

1. **有效性**：相对全枚举，`rf` 组合规模下降多少？  
2. **正确性**：约简是否保持 \(\mathsf{Out}\) 与 \(\mathsf{Prop}\)（T2⁺⁺）？  
3. **不漏报**：弱态 / race / 断言失败在噪声程序上约简后是否仍可检出？  
4. **S3 边际收益**：相对「只做相关读约简、不做值维」再降多少？

---

## 6.2 实验设置

- **语义与实现**：第 3 章一致性谓词；验证器 `weak_memory_verifier.py`；默认 `edge_prune=value`、`ind_mode=promote`、存在性扩展。  
- **基线**：`full` = 全部读的 `rf` 笛卡尔积规模。  
- **对照**：`reduced_no_s3`（相关读 × 写身份）；`reduced_s3`（再按值维压缩）。  
- **正确性守门**：`compare_reduction` 要求 `props_ok ∧ outcomes_ok`。  
- **基准**：`examples/manifest.json` + `examples/taxonomy.json` 分类；共 37 个程序（本快照）。  
- **辅助**：墙钟中位数（`bench_timing.py`，重复 5 次）；herdtools 弱态定性对照。

主指标为**组合数缩减**；时间为辅助（教具解释器开销会部分抵消组合收益）。

---

## 6.3 基准分类

| 类别 | 作用 | \(n\)（本快照） |
| --- | --- | ---: |
| `MP_RA` | RA / RS 消息传递 | 5 |
| `MP_fence_SC` | relaxed 弱态 vs fence/SC | 5 |
| `SB_LB` | SB/LB 弱态与 SC 禁止 | 5 |
| `coherence_RMW` | 存在性 mo / RMW | 3 |
| `scale_noise` | 噪声规模曲线（主有效性） | 15 |
| `bug_finding` | race / assert | 2 |
| `ind_boundary` | IND 提升边界 | 2 |

---

## 6.4 有效性结果

### 6.4.1 分类汇总

| 类别 | 均 saved(vs full) | 均 S3 额外↓ | max full | T2⁺⁺ |
| --- | ---: | ---: | ---: | --- |
| `MP_RA` | 0.30 | 0.10 | 12 | ✓ |
| `MP_fence_SC` | 0.425 | 0.0 | 32 | ✓ |
| `SB_LB` | 0.20 | 0.0 | 8 | ✓ |
| `coherence_RMW` | 0.0 | 0.0 | 9 | ✓ |
| `scale_noise` | **0.9016** | 0.0 | **512** | ✓ |
| `bug_finding` | 0.375 | 0.0 | 8 | ✓ |
| `ind_boundary` | 0.0 | 0.0 | 8 | ✓ |

全集相对全枚举平均缩减约 **0.51**；相对无 S3 约简平均再降约 **0.014**。

### 6.4.2 噪声规模曲线

固定相关读维，在独立地址叠噪声 relaxed 读时，全枚举按 \(2^{n}\) 级增长，约简后组合数近似常数（本例多为 4）。

| 程序 | full | S3 | saved |
| --- | ---: | ---: | ---: |
| `mp_two_noise` | 16 | 4 | 0.75 |
| `mp_triple_noise` | 32 | 4 | 0.875 |
| `scale_mp_ra_noise_4` | 64 | 4 | 0.9375 |
| `scale_mp_ra_noise_5` | 128 | 4 | 0.9688 |
| `scale_mp_ra_noise_6` | 256 | 4 | 0.9844 |
| `scale_mp_ra_noise_7` | 512 | 4 | **0.9922** |

SB/LB 噪声族呈现相同趋势（16/32/64 → 4）。无噪声的 litmus（如纯 `message_passing`、`coherence_*`）saved 为 0，符合预期：无可剪无关维。

### 6.4.3 时间曲线（辅助）

| 程序 | full | reduced | full 中位 ms | reduced 中位 ms | 加速比 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `scale_mp_ra_noise_4` | 64 | 4 | 14.6 | 6.9 | 2.1× |
| `scale_mp_ra_noise_5` | 128 | 4 | 44.8 | 18.6 | 2.4× |
| `scale_mp_ra_noise_6` | 256 | 4 | 133.3 | 51.5 | 2.6× |
| `scale_mp_ra_noise_7` | 512 | 4 | 400.0 | 142.6 | 2.8× |

随噪声增大，组合缩减与墙钟加速比同步上升（本机教具解释器约 2～3×）。论文主结论仍以组合数 + T2⁺⁺ 为准。

---

## 6.5 正确性与不漏报

- **T2⁺⁺**：37 程序全部 `props_ok ∧ outcomes_ok`。  
- **可 race**：`racy_counter`、`racy_counter_with_noise`。  
- **断言可败**：含 `mp_relaxed*` 与 racy 族共 5 例。  
- **MP 弱态** \(f=1,r=0\)：出现在 relaxed MP 族；RA/fence 族禁止。  
- **不漏报抽检**（约简后仍检出）：

| 性质 | 代表程序 |
| --- | --- |
| race | `racy_counter_with_noise` |
| assert 弱态 | `mp_relaxed_with_noise` |
| SB \((0,0)\) | `sb_with_noise` |

---

## 6.6 S3 消融

多数无同值冗余写的 litmus 上，S3 额外↓ 为 0（值类大小=写身份数）。同值多写例 `mp_ra_dup_writes`：`noS3=8` → `S3=4`（额外↓ **0.5**），说明值维剪枝在冗余写场景下有独立收益，且不破坏结局集合。

---

## 6.7 与 herdtools 的弱态对照（定性）

| 模式 | 弱态 | herdtools | 本原型 | 同向 |
| --- | --- | --- | --- | --- |
| MP 无 fence | \(f=1,r=0\) | 允许 | `mp_relaxed` 允许 | 是 |
| MP + 双侧 fence | 同上 | 禁止 | `mp_sc_fence` 禁止 | 是 |
| SB 无 fence | \((0,0)\) | 允许 | `sb_relaxed` 允许 | 是 |
| SB + 双侧 fence | \((0,0)\) | 禁止 | `sb_seq_cst` 禁止 | 是 |
| LB 无 fence | \((1,1)\) | 允许 | `lb_relaxed` 允许 | 是 |

说明：编码不必相同（如 `fence.rw.rw` vs 本器 `seq_cst` fence）；「同向」≠ 语义等价。约简有效性以内部 T2 实验为准。

---

## 6.8 讨论与威胁效度

1. 输入为教具 JSON，非完整 C 程序。  
2. 一致性为存在性 `mo`/`SC`，非完整 RC11。  
3. 缩减主指标为组合数；时间受解释器实现影响。  
4. 失败谱覆盖典型模式，非工业缺陷库。  
5. `coherence_RMW` / `ind_boundary` 上 saved≈0：前者读均相关，后者闭包已含全部相关维——不削弱「噪声场景下约简有效」的主张。

---

## 6.9 本章小结

实验表明：在 RC11 核心子集上，性质感知约简（含 S3）相对全枚举显著削减噪声场景组合数，全程保持 T2⁺⁺，且弱态/race/断言失败不漏报；S3 在同值多写上提供额外收益；与 herdtools 在经典弱态上结论同向。完整明细见仓库 `results/phd_eval_suite.md`。
