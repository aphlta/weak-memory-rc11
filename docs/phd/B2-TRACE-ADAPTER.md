# B2：单向轨迹对接（设计 only，未实现）

> 状态：**设计已写、代码未写**。禁止本文件授权解析 `events.jsonl` 或改本器 Event。  
> 现行档期：[ROADMAP-B.md](ROADMAP-B.md)。外部 oracle 仍是 **herd exists**，不是本器 `assert_eq`。

---

## 1. 输入在哪（xs-am-verify 侧）

| 对象 | 含义（对照用） |
| --- | --- |
| `events.jsonl` | 仿真/轨迹事件流（在 **xs-am-verify**，不进本仓库 JSON） |
| `W` vs `Wg` | 写提交 vs 写对其他观察者可见（可见性分层） |
| `commit_cycle` | 锚定同线程程序序（po）时间线 |
| `visible_cycle` | 参与一致性 / co 可见序讨论 |

关系构造参考（只读、不接入本器）：`xs-am-verify/tools/rvwmo/build_relations.py`。

---

## 2. 本器边界（永远）

- **不吃** `events.jsonl`。  
- **不加** `commit_cycle` / `visible_cycle` / `die_id` / `propagate` 到 `Event`。  
- 输入保持 **JSON 教具**（load/store/rmw/fence/assert + observe）。

---

## 3. 若将来做：只能单向

```text
轨迹 (xs-am-verify)
  → 关系 / 允许态对照（仍在 xs-am-verify，对照 herd exists）
  ✗ 禁止反向：不得把轨迹字段灌进 weak-memory-rc11 JSON
```

本器角色最多是：教具级弱态谓词 + 约简后布尔不漂；**不是** DUT oracle。

---

## 4. 对照物

- 芯片 / 轨迹验收：DUT 观察态 ⊆ Allowed(herd7, riscv.cat)，exists 采到。  
- 本器 B1 表：herd Observation ↔ 本器 weak 谓词（exists 里被 Never/Sometimes 的观察）。  
- **不是**用本器 `assert_eq` 判定硅前对错。

---

## 5. 与 B3 的分界

| 阶段 | 做什么 |
| --- | --- |
| **B2**（本文） | 只定接口与方向；**零代码** |
| **B3**（未开始） | 约简对象从「无关 load」转向「影响 exists 的读 / 同步边」；**那时**才允许改 `relevant_loads` 公式 |

本轮与 B2 实现轮均 **禁止**改 `weak_memory_verifier` 约简公式去迁就轨迹。
