# benchmark 结果摘要（R3 / T2）

组合数表：[`results/benchmark_results.md`](../results/benchmark_results.md)（`python3 benchmark_compare.py --write-results`）。

S5 分类评测：[`results/phd_eval_suite.md`](../results/phd_eval_suite.md)（`python3 scripts/phd_eval_suite.py --write-results`）；说明见 [`phd/EVALUATION.md`](phd/EVALUATION.md)。

时间曲线：[`results/timing_curve.md`](../results/timing_curve.md)（`python3 scripts/bench_timing.py --repeats 5 --write-results`）。

方法见 [`REDUCTION.md`](REDUCTION.md)。规模用例：`python3 scripts/gen_scale_benchmarks.py`。

## 约简主展示（有缩减且结局保持）

| 程序 | full | reduced | ratio | outcomes |
| --- | ---: | ---: | ---: | ---: |
| `message_passing_with_irrelevant_load` | 8 | 4 | 50% | 3 |
| `mp_sc_fence_with_irrelevant_load` | 8 | 4 | 50% | 3 |
| `mp_two_noise` | 16 | 4 | 75% | 3 |
| `mp_triple_noise` | 32 | 4 | 87.5% | 3 |
| `sb_with_noise` | 8 | 4 | 50% | 4（含 (0,0)） |
| `sb_sc_with_irrelevant_load` | 8 | 4 | 50% | 3 |
| `rs_mp_with_noise` | 12 | 6 | 50% | 4 |

## E2 规模曲线（噪声地址数 ↑，relevant 固定为 2）

固定 `observe`，在独立噪声地址上叠 relaxed 读；全枚举按 \(2^{n}\) 级增长，约简后组合数恒为 4。

### MP（RA）噪声规模

| n | full | reduced | ratio | ~ms（旧单次） |
| ---: | ---: | ---: | ---: | ---: |
| 4 | 64 | 4 | 93.8% | 23 |
| 5 | 128 | 4 | 96.9% | 68 |
| 6 | 256 | 4 | 98.4% | 188 |
| 7 | 512 | 4 | 99.2% | 539 |

### SB / LB 噪声规模

| 族 | n=2 | n=3 | n=4 |
| --- | --- | --- | --- |
| SB | 16→4 (75%) | 32→4 (87.5%) | 64→4 (93.8%) |
| LB | 16→4 (75%) | 32→4 (87.5%) | 64→4 (93.8%) |

## 时间曲线（全量 vs 约简，重复 5 次中位数）

摘自 `results/timing_curve.md`（本机一次跑数，论文可重跑）：

| 程序 | full组合 | reduced | full中位ms | reduced中位ms | 加速比 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `scale_mp_ra_noise_4` | 64 | 4 | 14.6 | 6.9 | **2.1×** |
| `scale_mp_ra_noise_5` | 128 | 4 | 44.8 | 18.6 | **2.4×** |
| `scale_mp_ra_noise_6` | 256 | 4 | 133.3 | 51.5 | **2.6×** |
| `scale_mp_ra_noise_7` | 512 | 4 | 400.0 | 142.6 | **2.8×** |

随 n 增大，组合缩减与墙钟加速比同步上升（教具解释器下约 2～3×）。

## 错误发现（约简不漏报）

| 程序 | full→reduced | 性质 | 约简后仍检出 |
| --- | --- | --- | --- |
| `mp_relaxed_with_noise` | 16→4 | assert 可败（弱态 f=1,r=0） | 是 |
| `mp_relaxed_noise_assert` | 32→4 | 同上（3 噪声） | 是 |
| `racy_counter_with_noise` | 8→2 | race + assert 可败 | 是 |

`compare_reduction`：`props_ok`（布尔）且 `outcomes_ok`；弱态/race 在 smoke 中显式核对。

## IND 边界反例

`cex_entangled_after_acquire`、`cex_shared_loc`：默认 `promote` 提升相关读；`refuse` 回退全枚举。见 [`REDUCTION.md`](REDUCTION.md)。

## herdtools 弱态对照

见 [`docs/HERD-COMPARISON.md`](HERD-COMPARISON.md) / [`results/herd_comparison.md`](../results/herd_comparison.md)。

```bash
python3 scripts/herd_compare.py --write-results
```

MP/SB/LB 无 fence：弱态均允许；双侧 `fence.rw.rw` 与本原型 `mp_sc_fence` / `sb_seq_cst`：弱态均禁止（结论同向；编码不必相同）。

## 边界

- 须声明或能推导 `observe`；噪声 load 的 target 不能进 observe
- 无关读做一致扩展搜索，不是单默认写
- 覆盖 RC11 核心子集，不是完整 C11
- 规模实验主指标是 **rf 候选组合**；时间曲线为辅助
