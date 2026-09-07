# 原型实验说明（R3）

1. 语义对照：安全 / 竞争 / fence / RS / RMW / SC / mo  
2. 约简：在 **观察结局集合保持** 下减少 rf 组合（见 [REDUCTION.md](REDUCTION.md)）

## 约简实验要点

- JSON 用 `"observe": [...]` 声明弱态关心的变量；噪声 load 的 target 不要放进 observe  
- `compare_reduction` / `smoke_check` 要求 `props_ok` 且 `outcomes_ok`  
- 缩减梯度：`mp_two_noise` 16→4（75%），`mp_triple_noise` 32→4（87.5%）

## 命令

```bash
python3 smoke_check.py
python3 benchmark_compare.py --write-results
python3 weak_memory_verifier.py examples/mp_triple_noise.json \
  --reduction relevant --explain-relevant
```
