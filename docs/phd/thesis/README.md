# 学位论文正文草稿索引

本目录由仓库理论/评测文档扩写，供粘贴进学校模板。数字以 `results/` 最新快照为准。

## 档期变更（必读）

**现行档期是 B**（工程落地 / herd 外部验收），见 [ROADMAP-B.md](../ROADMAP-B.md)。  
第 2–6 章草稿（`ch02`–`ch06`）以及 S6 附录仍是 **P2 / A 叙事**（子集 + 自比 T2 + scale_noise），**尚未按 B 重写**。引用路线与验收口径时以 **ROADMAP-B** 与 `results/herd_landing.md` 为准；不要把本章草稿当成现行贡献声明。

| 章 | 文件 | 源材料 |
| --- | --- | --- |
| 第 2 章 相关工作与语义定位 | [ch02-semantics.md](ch02-semantics.md) | RC11-ALIGNMENT |
| 第 3 章 执行图与一致性谓词 | [ch03-consistency.md](ch03-consistency.md) | RC11-ALIGNMENT + THEORY §1 |
| 第 4 章 性质感知约简 | [ch04-reduction.md](ch04-reduction.md) | THEORY-v1 |
| 第 5 章 原型实现 | [ch05-implementation.md](ch05-implementation.md) | ARCHITECTURE / REDUCTION |
| 第 6 章 实验评测 | [ch06-evaluation.md](ch06-evaluation.md) | EVALUATION + phd_eval_suite |
| S6 机械化范围 | [s6-mechanization.md](s6-mechanization.md) | THEORY + ROADMAP |
| S6a 附录 | [s6a-appendix.md](s6a-appendix.md) | `formal/` 已证内容 |

再生实验表（历史自比，非 B 落地主表）：

```bash
python3 scripts/phd_eval_suite.py --write-results
```

现行外部验收：

```bash
python3 scripts/herd_landing.py --write-results
```
