# Cursor 接手说明

> **冻结声明（档期 B）**  
> **现行档期是 B（工程落地 / herd 外部验收）**，见 [phd/ROADMAP-B.md](phd/ROADMAP-B.md)。  
> **本文大量章节是历史设计（P2 / 异构视线），不授权按「下一优先 = fence / 多芯片 / S6c」推进实现。**  
> B0/B1 已落地；缺口修复见 [phd/ROADMAP-B.md](phd/ROADMAP-B.md)；禁止再按本文推进实现；禁止对接 `events.jsonl`。

这份文档帮助在最少上下文损失下理解仓库历史状态；**现行优先以 ROADMAP-B 为准**。

> 语义见 [ARCHITECTURE.md](ARCHITECTURE.md)。
> **核心子集与约简（R3/T2）已落地**；见 [REDUCTION.md](REDUCTION.md)。
> **历史博士主线 P2（已冻结）**：[phd/ROADMAP.md](phd/ROADMAP.md)。  
> **现行验收表**：`python3 scripts/herd_landing.py --write-results` → `results/herd_landing.md`。

---

## 1. 项目目标

面向 RC11 核心子集的研究原型，支撑：

- 程序执行表示与候选执行枚举
- 数据竞争 / 断言违例检测
- **面向性质的相关性约简**（主创新点）

---

## 2. 当前仓库状态

核心目录（相对仓库根）：

- `weak_memory_verifier.py`：核心验证器
- `examples/` + `examples/manifest.json`
- `benchmark_compare.py` / `smoke_check.py`
- `docs/ARCHITECTURE.md`、本文件、`HETEROGENEOUS-SCOPE.md`
- `results/benchmark_results.*`

**已经实现（单芯片核心）：**

- `load` / `store` / `rmw` / `fence` / `assert_eq`
- `reads-from` 枚举（笛卡尔积只扫 rf）
- RA `sw` + release sequence + fence 同步
- `happens-before`
- 存在性 `mo`（Co* + RMW 相邻）
- 存在性 SC 全序（含 fr）
- 简化 data race / `assert_eq`
- 可解释 relevant-load（`--explain-relevant`）
- 批量 benchmark

**仍未实现（本课题范围外）：**

- consume / dob / no-thin-air / CAS 失败路径

---

## 3–5. 历史任务状态

| 任务 | 状态 |
| --- | --- |
| 1 存在性 mo | **已完成** |
| 2 fence 语义 | **已完成**（`mp_relaxed` / `mp_sc_fence`） |
| 3 可解释约简 | **已完成**（三类原因 + 缩减例） |
| 4 批量 benchmark | **已完成**（manifest + `--write-results`） |
| RS / RMW / SC | **已完成**（随核心收尾一并落地） |

细节与验收例子见 `examples/` 与 `smoke_check.py`。旧的「建议做法」段落保留在下方作历史参考，**以 ARCHITECTURE 与 README 为准**。

---

## 3. 代码当前的核心思路

### 3.1 输入模型

程序由 JSON 描述，含：

- `initial_memory`
- `threads`
- 每个线程中一串操作

支持的主要操作：

- `store`
- `load`
- `assert_eq`

### 3.2 验证流程

当前流程大致是：

1. 解析 JSON，生成 `Program`
2. 为每个 `load` 找到同地址的候选 `write`
3. 对所有 `load` 的候选集合做笛卡尔积，得到候选执行
4. 对每个候选执行：
   - 计算 `synchronizes-with`
   - 计算 `happens-before`
   - 存在性 mo 检查（每个 loc 一条 Co* 全序；失败丢执行）
   - 解释线程内变量
   - 检查 `assert_eq`
   - 检查 `data race`

### 3.3 当前约简策略

当前 `relevant_loads(program)` 的思路是反向扫描线程，保留：

- 会直接影响断言变量的 `load`
- 会影响 guard 条件的 `load`
- 对未来同步有影响的 `acquire/seq_cst load`

这是一个“雏形方法”，但还不是完整论文方法。后续可以继续提升为：

- 更严格的性质保持定义
- 更清晰的依赖传播规则
- 更系统的实验验证

---

## 4. Cursor 需要先理解的约束

Cursor 接手时，不要把项目目标误判成“实现完整内存模型”。当前更合理的目标是：

### 阶段目标 A：把单芯片研究原型做扎实

优先级最高：

1. 存在性 `mo/coherence`（**已落地**，见 ARCHITECTURE；不要重做）
2. 最小 `fence` 语义
3. 让约简策略有更明确的语义边界
4. 完善 benchmark 与统计输出

### 阶段目标 B：为多芯片扩展预留接口

不要直接一口气做完整多芯片模型。先做接口设计：

- 事件上增加层级位置字段
- 预留 propagation / visibility 事件表示
- 给同步关系增加 scope 扩展点

---

## 5. 接下来最实际要做的工作

建议 Cursor 按下面顺序推进。

### 任务 1：补 `mo/coherence`（已落地，不要重做）

**已落地：存在性 mo，见 [ARCHITECTURE.md](ARCHITECTURE.md) §3–§4。**

实现要点（供对照，不要再按旧验收重写一遍）：

- 笛卡尔积只扫 rf；每个 loc 求一条满足 CoWW/CoWR/CoRW/CoRR 的写全序，失败丢执行
- `modification_order` 挂在 `Execution` 上当 witness，不挂 `Program`，不进 JSON
- 例子：`coherence_rr.json`（两写已有 hb 时先新后旧成环）、`coherence_rw.json`（CoRW 边 + 先 2 后 1）
- 并发写的 2-then-1 在存在性 mo 下**合法**，不是漏检

下一优先从任务 2 开始。

### 任务 2：把 `fence` 从占位变成语义对象

目标：

- 支持最小化的 `fence` 语义
- 让 `fence` 参与 `hb` 或相关约束

建议做法：

- 先只支持一种简化 fence，例如 `seq_cst fence`
- 明确 fence 前后的程序序屏障效果
- 不要一开始引入过多 fence 类型

最低验收标准：

- 新增 fence 示例
- fence 会影响某些执行可行性或断言结果

### 任务 3：升级相关性约简

目标：

- 把当前 `relevant_loads` 从“启发式”推进到“更可解释的性质感知约简”

建议做法：

- 把相关性按三类拆开：
  - `assertion relevance`
  - `synchronization relevance`
  - `race relevance`
- 给每类相关性写清楚规则
- 生成调试输出，显示某个 `load` 为什么被判 relevant

最低验收标准：

- 命令行支持打印 relevant 判定原因
- benchmark 输出约简前后组合数变化
- 至少 3 个例子验证“结论不变但组合减少”

### 任务 4：加实验批处理

目标：

- 自动跑一组 benchmark
- 输出摘要统计

建议做法：

- 新建一个 benchmark manifest
- 统计：
  - 程序名
  - loads 数量
  - 原始组合数
  - 约简后组合数
  - race 数
  - assertion failure 数
  - 运行时间

最低验收标准：

- 输出 `json` + `md`
- 实验结果可直接写进论文

---

## 6. 如果要为多芯片做准备，应如何改数据结构

现在不要完整实现多芯片，但可以设计成容易扩展。

### 6.1 事件结构建议增加

在 `Event` 中考虑预留这些字段：

- `core_id`
- `cluster_id`
- `die_id`
- `socket_id`
- `scope`

当前阶段允许默认值统一为 `0` 或 `global`。

### 6.2 未来可能新增的事件类型

- `propagate`
- `invalidate`
- `visible`
- `fence`

当前不必全部实现，但数据模型不要把这条路堵死。

### 6.3 未来的约简对象不止是 load

Cursor 需要知道：后面真正可能研究的不是单纯 `relevant load reduction`，而是：

- `relevant propagation`
- `relevant visibility state`
- `relevant synchronization edge`

所以当前代码设计应尽量模块化，不要把约简逻辑死绑在 `load` 上。

---

## 7. 代码改造建议

### 7.1 优先做的重构

- 把“程序解析”“候选生成”“关系计算”“性质检查”“约简判断”拆成更清晰的函数层
- 为 `Execution` 添加更多显式字段，不要把所有逻辑揉在一个函数里
- 给一致性检查加独立函数，例如：
  - `_compute_rf(...)`
  - `_compute_sw(...)`
  - `_compute_hb(...)`
  - `_check_mo_consistency(...)`
  - `_detect_races(...)`
  - `_evaluate_assertions(...)`

### 7.2 输出层建议

增加更适合研究调试的输出：

- 为什么某个执行被判不一致
- 哪些 load 被判 relevant
- 每个 execution 的关键边摘要
- 每个 benchmark 的统计表

---

## 8. 交给 Cursor 的验收标准

Cursor 每次推进都应该满足下面的工作方式：

1. 先说明当前理解的语义边界
2. 再改代码
3. 改完后补示例
4. 最后跑验证脚本

建议每次任务至少给出：

- 改了哪些文件
- 新增了什么语义/约束
- 有哪些限制没覆盖
- 用什么命令验证

---

## 9. 可以直接粘给 Cursor 的提示词

下面这段可以直接作为 Cursor 的接手提示词。

```text
你现在接手的是一个 Python 写的弱内存研究原型，目录在 weak-memory-prototype。

项目定位：
- 不是完整的 C/C++11 验证器
- 是一个面向 RC11 / RA 风格弱内存验证的最小研究原型
- 当前研究主线是“自动验证 + 状态空间约简”
- 当前最有潜力的方法点是：面向 assertion / synchronization / race 的 relevant-load reduction

你需要先阅读这些文件并保持它们的一致性：
- weak_memory_verifier.py
- README.md
- research_work_breakdown.md
- benchmark_compare.py
- examples/

当前已经实现：
- JSON 程序输入
- Event / Program / Execution 数据结构
- reads-from 候选枚举
- synchronizes-with / happens-before
- 存在性 mo / coherence 四条（见 ARCHITECTURE）
- 简化 race 检测
- assert_eq 检测
- 初步的 relevant load reduction

当前未完成：
- 真正语义化的 fence
- 更系统的 benchmark
- 更强的 reduction 正确性说明

你的工作原则：
1. 不要试图一次实现完整 RC11/C11
2. 优先做小步、可验证、可解释的增强
3. 每加一个语义点，都要补示例和验证命令
4. 不要破坏现有 examples 和 smoke_check.py
5. 如果做重构，保持命令行接口尽量稳定

本轮请优先完成以下任务：
- [在这里填你当前要它做的那一项，例如：给 fence 加最小语义 / 升级 relevant_loads]

输出要求：
- 先说明设计思路
- 再展示改动文件
- 最后给出验证命令和结果摘要
```

---

## 10. 你自己在用 Cursor 时最好补充的信息

你每次发任务时，最好明确这 5 点：

1. `目标边界`
   - 例如：这次只做最小 `fence`，不碰多芯片，不要重做 mo

2. `不能动什么`
   - 例如：保持 JSON 输入格式兼容

3. `验收方式`
   - 例如：必须新增示例并通过 `smoke_check.py`

4. `优先保证什么`
   - 例如：先保证解释性，不追求性能

5. `这次的研究意图`
   - 例如：这次不是单纯修 bug，而是为了把“相关性约简”的语义边界说清楚

---

## 11. 最推荐的接手顺序

如果只选一条最稳路线，建议 Cursor 按这个顺序做：

1. 重构 `weak_memory_verifier.py` 的模块边界（已基本切开）
2. 加最小存在性 `mo/coherence`（**已落地**，见 ARCHITECTURE）
3. 给 `fence` 加最小语义  ← **下一优先**
4. 重写并解释 `relevant_loads`  ← 与 fence 并列的下一优先
5. 加 benchmark 批处理
6. 再考虑多芯片扩展接口

---

## 12. 一句话总结

你要让 Cursor 接手的，不是“随便改一个弱内存脚本”，而是：

`在一个已经能跑、且已有存在性 mo 的 RC11/RA 风格研究原型上，继续把“自动验证 + 性质感知约简”这条路线做扎实（下一优先：fence / 约简升级），并为未来的多芯片扩展预留结构。`
