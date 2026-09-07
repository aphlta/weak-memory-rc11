# formal/ — S6a 机械化证明

## 目标（已完成部分）

| 项 | 文件 | 状态 |
| --- | --- | --- |
| 迷你事件 / rf / 观察投影 | `MiniGraph.v` | 已证 **引理 1** |
| 约简扩展与结局工作定理 | `Reduction.v` | 已证 sound/complete + `T2_plus_outcome_workhorse` |
| Prop / IND / promote | `IndProp.v` | 已证 **引理 5–6**（S6b） |
| 集合版 \(\mathsf{Out}=\mathsf{Out}_R\) | — | 可选包装 |
| mo/SC / sw 展开 | — | Consistency / Bad / RP 为参数 |
| 值维 T2⁺⁺ | — | S6c |

## 编译

```bash
export OPAMROOT=/ssdhome/maoweiming/xiangshan/.opam-root
eval $(opam env)   # 需本机 opam；或直接用 switch 里的 coqc
cd formal && make
```

可选 Docker：`make docker`（需能拉取 `coqorg/coq:8.18.0`）。

## 与 Python / 论文的信任边界

| 声明 | 机器证明 | 仍靠实验/`compare_reduction` |
| --- | --- | --- |
| 观察只依赖 Obs 相关读上的 rf | ✓ 引理 1 | |
| 相关集覆盖 Obs 时，扩展代表与具体 rf 观察相同 | ✓ `T2_plus_outcome_workhorse` | |
| 具体 `sw`/`mo`/`SC` 实现正确 | | ✓ |
| IND promote 策略完备 | | ✓（S6b） |
| 值维剪枝 T2⁺⁺ | | ✓（S6c） |

理论源：[`docs/phd/THEORY-v1.md`](../docs/phd/THEORY-v1.md)。  
附录说明：[`docs/phd/thesis/s6a-appendix.md`](../docs/phd/thesis/s6a-appendix.md)。
