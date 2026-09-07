# 多 CPU / 多芯片 / 异构设备：本原型该怎么接

> **冻结声明（档期 B）**  
> **现行档期是 B（工程落地 / herd 外部验收）**，见 [phd/ROADMAP-B.md](phd/ROADMAP-B.md)。  
> **本文是历史设计，不授权按本文推进实现**（含 fence 扩语义、多芯片、异构、下一优先条目）。  
> **本论文不使用本文档。** 论文/落地只做 RC11 风格教具 + herd 对照。  
> 正文于 2026-09-07 从本机 agent-transcript 中的文件快照恢复（约 410 行；原 IDE 显示 411，差 1 行级，未人工改写章节）。

> 设计笔记，**不改代码**。和 [ARCHITECTURE.md](ARCHITECTURE.md) §2、[CURSOR_HANDOFF.md](CURSOR_HANDOFF.md) §4 / §6 对齐：本仓库近期只做单芯片 RA + 以后的 `mo`；多芯片先留接口，异构更后。
>
> 为什么单独成文：接手时最容易把三件事混成「线程变多」。它们不是一个模型，金标准也不一样。把档位写死，避免以后把 GPU 核、NPU DMA、跨 die 传播都塞进现在的 JSON `load` / `store` / `assert_eq`。

对照仓库：

| 层 | 仓库 | 现在实际在算什么 |
| --- | --- | --- |
| 语言 / RC11-RA | **本仓库** | JSON 事件图，`rf` 枚举，简化 `sw` / `hb`，relevant-load |
| ISA / RVWMO | `xs-am-verify` | 双核 litmus + herd7/`riscv.cat`；轨迹里 **W（提交）** vs **Wg（sbuffer 全局可见）** |
| 互连 / 多芯片 | 尚无 | 写在本 die 何时对另一 die 可见；**没有官方 cat** |
| 异构设备 | 尚无 | 地址空间、一致性域、拷贝完成；**不是 RC11** |

`Event` 现状（`weak_memory_verifier.py`，2026-09）：`eid` / `thread` / `index` / `kind` / `loc` / `value` / `target` / `right` / `atomic` / `order` / `guard`。故意没加 `die_id` / `scope` / `device_kind`：过早加字段会让人以为已经有跨片或跨设备模型。本文只谈**以后该加什么、默认必须等价于今天的单全局可见**。

---

## 0. 先把三档拆开

判定标准不是「硬件盒子有几个」，而是：**有几个地址空间、几个一致性域、可见性是全局的还是按 scope 传播、跨域靠什么事件接通**。

```text
A. 同构多 CPU     一个共享地址空间 + 一个一致性域（RVWMO 或 RC11）
                  核多、socket 多，但写对所有观察者最终按同一套公理可见

B. 多芯片 / 多 die 同一 ISA，仍谈 load/store，但可见性按 scope 传播
                  片内仍是 A；片间是 propagate / visible@scope，不是「线程++」

C. CPU+GPU+NPU    通常多个地址空间、多个内存模型、显式拷贝或专用 fabric
                  不是「一个 RC11 堆上更多线程」
```

三条禁令（后面表里还会出现）：

1. 不要把 B/C 的程序写成今天的 JSON 线程列表，然后声称本器已经覆盖。
2. 不要把 `xs-am-verify` 的 `events.jsonl` 喂给本器；也不要把本器的 `assert_eq` 当香山 oracle。
3. RC11 的 `release/acquire` ≠ RISC-V `fence` ≠ PTX `fence.sc` ≠ NPU barrier。名字像，公理不是一套。

---

## 1. 三档分别：能复用什么 / 必须新增什么 / 不能假装是 RC11

### 1.A 同构多 CPU（多核 / 多 socket，仍是共享内存）

**场景**：同一 ISA、硬件宣称单一共享内存（香山双核 / 多核、cache-coherent 多 socket）。程序员眼里仍是「若干线程 + 原子 + fence」。语言级是 RC11/RA；ISA 级是 RVWMO。

**能复用**

- 现有 Event IR：`load` / `store` / `assert_eq` / 占位 `fence`。
- `po` / `rf` / `sw` / `hb`、以后的 `mo` / coherence。
- relevant-load：性质仍是 assert / sync / race，对象仍是同地址空间上的读。
- `xs-am-verify` 的 herd7 + `riscv.cat`：ISA 金标准不变。双核已经在 [07-rv64-mm-litmus.md](../../xs-am-verify/docs/specs/07-rv64-mm-litmus.md)；核数变多只是 litmus 规模变大，不是换模型。
- 轨迹侧的 W vs Wg：仍是**单一致性域内**「提交 ≠ 全局可见」。`build_relations.py` 里 `commit_cycle` 锚 `po`，`visible_cycle` 定 `co`。这是 A 的微架构细化，不是 B。

**必须新增（语义上很少，标注上可以有）**

- 语言级：**不必**为「多核」加新事件。`thread` 已经是并发单元。
- 对接硬件时加**标注**，默认不改变语义：`core_id` / `hart` / `socket_id`。用途是「这条事件在哪颗核上」，不是「这个写只对某个 socket 可见」。
- 多 socket 若仍 cache-coherent：socket 只是拓扑，不是 scope。NUMA 延迟不是内存模型。
- 本仓库补齐 `mo` / 真 `fence` 之后，A 的多线程例子才站得住；现在缺 `mo`，连单芯片都不能称完整 RC11。

**不能假装是 RC11 / 不能假装已经覆盖**

- 「线程数变多」≠ 已经做过多 socket 可见性。若某条写对 socket0 可见、对 socket1 还不可见，那已经滑进 **B**。
- 本器的 `thread` ≠ RISC-V `hart`。JSON 没有 PC、宽度、mixed-size、AMO；不能当 litmus 输入。
- 香山手册里的 RVWMO 允许态，不能用本器的 RA `sw` 去判。
- 多核 store buffer 合并（`xs-am-verify` 的 `S-NO-VISIBLE`）是轨迹重建问题，不是本器该吸收的 JSON 形态。

**一句话**：A 是「把现在的单芯片原型做扎实，再多跑几个线程 / 接到双核 litmus」。不是新模型。

### 1.B 多芯片 / 多 die（同一 ISA，可见性按 scope 传播）

**场景**：同一套 RISC-V 核，片内 cache 一致，片间靠互连传播。ARCHITECTURE 已写死：片内仍是 RVWMO，片间是传播 / 可见性；官方没有 inter-die cat。

这和 CURSOR_HANDOFF §6 的预留是同一档：`core_id` / `cluster_id` / `die_id` / `socket_id` / `scope`，以及 `propagate` / `invalidate` / `visible`。

**能复用**

- 片内子图：A 的全部（`po` / `rf` / `sw` / `hb` / `mo`，以及 relevant-load）。
- 「事件图 + 性质感知约简」这条研究主线。约简对象从 load 升级到 **propagation**（§3）。
- `xs-am-verify` 的 W/Wg **作为片内半边**：一次 store 仍先 commit，再在本 die 上变成 Wg。B 要做的是把「全局可见」改写成「在某个 scope 可见」。
- 性质种类：assert / race 的*想法*还在，但 race 必须带 scope（「在 die1 上无 hb」不等于「在系统里无 hb」）。

**必须新增的事件 / 关系**

| 对象 | 为什么现有 load/store 不够 |
| --- | --- |
| `propagate` | 一次写从较小 scope 走到较大 scope 的显式步骤。没有它，rf 只能假装「全世界立刻看见」 |
| `visible`（或 `visible@scope`） | 某观察者（核 / die）承认看见了某写。对应把 Wg 从「唯一全局时刻」拆成「每个 scope 一个时刻」 |
| `invalidate` | 可选。有的互连是推入可见，有的是拉入失效；不建模就会把两种协议都压成同一种 rf |
| 带 `scope` 的 fence | 片内 `fence` 推不出去；跨 die 同步是另一条边 |
| 分层位置字段 | 见 §2。默认值必须退化成今天的「单全局可见」 |

关系上：片内 `rf` 仍是「读到哪个写的值」；跨 die 的「能不能读到」不再只由同地址写集合决定，而由 **该写是否已 `visible` 于读所在 scope** 决定。`sw` 也必须带 scope：die0 上的 release 被 die1 的 acquire 读到，只有传播边存在时才成立。

**不能假装是 RC11**

- 多芯片 **不是** 把 `threads` 加长。同一程序、两个 die 上各一个线程，合法执行集可以严格大于「两线程单芯片 RC11」。
- herd7 + `riscv.cat` **不是** 片间金标准。`riscv.cat` 假定单一 RVWMO 域。用它判跨 die 会把「尚未传播」的弱态误判成违规，或把互连允许的延迟当成 bug。
- 本器今天的 `_reads_from_candidates`（同地址、去掉同线程 po 之后的写）在 B 上是错的：它默认每个写对每个读都是候选。
- 不要把 `die_id` 写进 JSON 却仍用现在的 `evaluate_execution`。字段在、语义不在，比没字段更糟。

**一句话**：B 是「同一 ISA 上的 scoped visibility」。复用片内 RC11/RVWMO，新增传播事件；金标准要另写，不能蹭 herd。

### 1.C 异构 CPU + GPU + NPU

**场景**：主机 CPU 旁还有 GPU、NPU。常见并不是一个共享 RC11 堆，而是：

| 机制 | 地址空间 | 一致性域 | 跨设备怎么看见数据 |
| --- | --- | --- | --- |
| 独立显存 + `memcpy` / DMA | 不共享 | 各算各的 | **拷贝完成** 之后，目的空间出现新写 |
| CUDA Unified Memory / HMM | 逻辑共享，物理可迁移 | 依平台：软件维护或硬件一致 | 缺页、prefetch、还是系统级 atom |
| GPU 共享主机内存（部分 SoC / NVLink-C2C） | 可共享 | 仍可能是 PTX `.sys` 而不是 RC11 | 设备 fence + 系统 scope atom |
| NPU 私有 SRAM | 不共享 | 核内顺序 + 厂商 barrier | DMA / 信箱 / 完成队列 |
| PCIe MMIO + 门铃 | 窗口映射，不是缓存行共享 | 主机一侧、设备一侧 | posted write + completion |
| CXL.mem / CXL.cache | 可接近 NUMA 或设备缓存主机 | 看 CXL 类型与主机协议 | 有的可当 B，有的仍要显式 flush |

**能复用（只有研究骨架，不是语义）**

- **事件图**：节点 + 带标签的边 + 公理检查。这是本仓库真正该带走的东西。
- **性质感知约简**：不要枚举所有候选边，只留影响 assert / 同步 / 竞争（以及跨设备的「拷贝是否完成」）的那些。对象从 load 换成 propagation / transfer，规则形状类似（§3）。
- 分层金标准的*做法*：每一层找自己的 oracle，不把本器当万能裁判。
- CPU 侧子图：若某段纯 CPU、单一地址空间，仍可用 A（语言）或 `xs-am-verify`（ISA）。

**必须新增：不能再假装是 load/store**

1. **地址空间 `aspace`**。`loc` 只在一个 aspace 里有意义。跨 aspace 的「同名变量」不是同一个位置。
2. **`device_kind` / `device_id`**。事件落在哪种设备上，决定用哪套公理，而不是只用 `thread`。
3. **拷贝 / 传输事件**：`copy` + `copy_complete`（或 DMA 描述符 + 完成）。跨空间的 rf **只能**经过完成事件，不能直接 `load` 连到另一设备的 `store`。
4. **设备内同步**：PTX `fence` / `bar.sync` / `atom.acq_rel`（带 `.cta` / `.gpu` / `.sys`）；NPU barrier、命令队列 `sync`。这些不是 C11 `order`。
5. **映射事件**（可选）：`map` / `unmap` / `publish`。PCIe BAR、IOMMU、CUDA mapping 先打开窗口，才谈得上后续 load。
6. **跨设备 fence / flush**：主机 `fence` + 设备 `membar` + PCIe completion，常常是**三拍**，压成一个 `seq_cst` 会漏掉「拷贝已发、对端还没看见」。

**不能假装是 RC11；现在的 JSON 覆盖不了**

- 现在的输入是：一份 `initial_memory` + 若干 CPU 风格线程 + 全局 `loc`。没有 aspace，没有设备，没有 copy。**把 GPU kernel 拆成两个 `threads` 写进 JSON，结论无意义。**
- CUDA/PTX 默认比 RC11 更弱，且带 **cta / gpu / sys** 作用域；系统级 atom 才接近「和主机说话」。这不是把 `order` 改成 `relaxed` 能模拟的。
- NPU 私有 SRAM 上的「写」对 CPU 不可见，直到 DMA 完成。本器的 `_reads_from_candidates` 会错误地让 CPU load 读到 NPU store。
- PCIe posted write 没有「release 被 acquire 读到」这种 sw。门铃 + 轮询是另一套 producer-consumer。
- CXL 若对软件呈现为 cache-coherent 主机内存，可**降级讨论成 A 或 B**；在没写清协议之前，不要当 RC11。
- 没有 GPU/NPU 版的 `riscv.cat`。herd 的 GPU 模型、厂商 PTX 文档、NPU 手册是**另一套金标准**（§4）。

**一句话**：C 复用「图 + 性质约简」，不复用 RC11 公理，不复用当前 JSON。跨设备的关键事件是 **transfer 完成** 和 **跨域 fence**，不是多几个 `thread`。

---

## 2. 建议的 Event 扩展（只设计，代码先不要加）

原则（与现有注释一致）：**缺省必须语义等于今天**。字段出现而默认不是「单全局可见」，就会污染 A 的例子和 smoke。

### 2.1 现有字段保持

`eid` / `thread` / `index` / `kind` / `loc` / `value` / `target` / `right` / `atomic` / `order` / `guard` 不动。`thread` 仍表示**同一设备内**的程序序主体。初值继续用 `thread=-1` 的虚拟 store，但要标明它属于哪个 `aspace`（默认 `host`）。

### 2.2 位置与设备（A 标注，B 语义，C 必填）

| 字段 | 类型（建议） | 默认 | 哪一档开始有语义 |
| --- | --- | --- | --- |
| `core_id` | int | `0` | A 对接轨迹时的标注；B 起参与 scope |
| `cluster_id` | int | `0` | B |
| `die_id` | int | `0` | B |
| `socket_id` | int | `0` | 仅当 socket 不是全局可见时才升为 B |
| `device_id` | int | `0` | C；A/B 恒为 0 |
| `device_kind` | `cpu` \| `gpu` \| `npu` \| `host` | `cpu` | C；A/B 恒为 `cpu` |
| `aspace` | 字符串 | `"host"` | C；A/B 恒为 `"host"` |
| `scope` | 见下 | `"system"` | B 起；A 恒为 `system` ≡ 今天 |

建议 `scope` 枚举（由小到大，不必一次用齐）：

```text
thread ⊂ core ⊂ cluster ⊂ die ⊂ socket ⊂ device ⊂ system
```

GPU 侧若要对齐 PTX，**不要**把 `.cta` / `.gpu` / `.sys` 强行塞进上面这棵 CPU 树。另用设备内枚举，或 `scope="device"` + `device_scope="cta|gpu|sys"`。混成一棵树会假装 PTX 就是 RC11 的分层。

### 2.3 可见性（对接 W / Wg，不要过早写进本器 JSON）

语言级 JSON **不要**抄 `commit_cycle` / `visible_cycle`。那是 `xs-am-verify` 轨迹层的时间锚点。本器若要表达「提交 ≠ 可见」，用事件种类，不用仿真周期：

| 概念 | 本器（未来 IR） | `xs-am-verify` 轨迹 |
| --- | --- | --- |
| 指令 / 写在本线程提交 | `store`（或拆出 `commit`） | `W` + `commit_cycle` |
| 写在某 scope 对观察者可见 | `visible`，带 `scope` | 单芯片：`Wg` + `visible_cycle`；多芯片：尚无 |
| 读发生 | `load` | `R` + `commit_cycle`（读没有 Wg） |

A 单芯片：一个 `store` 仍可当成「提交后即对 system 可见」，与今天兼容。需要对接轨迹时，在**对接层**把 `(W, Wg)` 合成一个带两种时刻的写，而不是让本器 JSON 长出 `cycle` 字段。

B：`Wg` 泛化成 `visible@scope`。同一 `store` 可对应多条 `visible`（先 `die`，再 `system`）。`propagate` 是连接两条 `visible` 的边或中间事件。

C：另一设备上的「可见」常常根本不是 cache 可见，而是 **aspace 里多了一个写**（copy 完成）。不要复用 `Wg` 这个名字去表示 DMA 完成。

### 2.4 建议新增的 `kind`（按档位启用）

| `kind` | 启用档 | 作用 | 为什么不能用现有 kind 冒充 |
| --- | --- | --- | --- |
| `fence` | A（语义化之后） | 本一致性域屏障 | 今天只是占位 |
| `propagate` | B | 写的可见范围扩大一档 | 不是 store，不写新值 |
| `visible` | B | 记录「该写在该 scope 已可见」 | 不是 load |
| `invalidate` | B（可选） | 某 scope 丢掉过时副本 | 不是 fence |
| `copy` | C | 在两个 aspace 之间启动传输 | 两端 `loc` 甚至宽度都不同 |
| `copy_complete` | C | 传输对目的 aspace 生效 | **跨空间 rf 的唯一合法来源** |
| `device_fence` | C | 设备私有屏障（PTX / NPU） | `order` 字段解释不了 `.cta` |
| `map` / `unmap` | C（可选） | 打开 / 关掉跨空间窗口 | 没有它，MMIO 只能假装是 host `loc` |

`assert_eq` 仍只解释**同一设备、同一 aspace** 的线程局部变量。跨设备断言必须先有 `copy_complete` 或系统级可见，再在目的侧 `load`。不要发明「直接 assert 远端 SRAM」。

### 2.5 同步边的扩展点（给以后的 `sw`，现在不要实现）

今天：`release/seq_cst` 写 × `acquire/seq_cst` 读，且 `rf` 连上 → `sw`。

以后按档：

- A：维持；补 `mo` 后按 RC11 收紧。
- B：`sw` 额外要求写已 `visible` 于读的 `die`/`scope`。
- C：CPU 的 `sw` 与 GPU 的 `sw` **不要共用一个函数**。跨设备同步走 `copy_complete` 或成对的 `device_fence` + 主机 fence，单独叫 `sync_xfer` / `sync_scope`，避免和 RA 的 `sw` 同名。

### 2.6 默认值契约（以后加字段时的验收）

对现有三个 examples，下列赋值必须得到**与今天逐执行相同**的 `rf` / `sw` / race / assert：

```text
device_kind=cpu, device_id=0, aspace=host,
core_id=cluster_id=die_id=socket_id=0,
scope=system
```

做不到这一点，就不许把字段写进 `Event`。

---

## 3. 约简：从 relevant-load 到 relevant-propagation / relevant-transfer

研究主线不变：[CURSOR_HANDOFF](CURSOR_HANDOFF.md) 说的不是「做一个能跑的验证器」，而是**面向性质的相关性约简**。变的是被判定 relevant 的对象。

### 3.1 今天：relevant-load（A 的雏形）

`relevant_loads` 从线程尾部反向扫，保留：

- 非原子 load（race 规则吃访问集合）
- 结果流入 assert / guard 的 load
- 后面还有同步效果时的 acquire / seq_cst load

无关 load 事后用 `_pick_default_write` 填 rf。这是启发式；`smoke_check.py` 只保证三个例子上结论不变。

A 的升级仍按接手说明：拆成 assertion / synchronization / race 三类，并打印「为什么相关」。**对象还是 load。** 多核不改变这一档。

### 3.2 B：relevant-propagation

跨 die 之后，组合爆炸的主因不再只是「每个 load 读谁」，而是「每条写要不要、以及何时传播到哪个 scope」。

一条 `propagate` / `visible` 边 **relevant**，当且仅当去掉它可能改变下面之一（设计目标，不是已证定理）：

1. **assertion relevance**：某条 assert 所依赖的 load，其合法 rf 集合会变（少一条传播，就少一个能读到的写，或反过来让过时写仍可见）。
2. **synchronization relevance**：某条 scope 内的 `sw` 会因此少掉或假造，并影响到 1 或 3。
3. **race relevance**：两个访问是否在同一观察 scope 里有 hb。

其余传播可以坍缩成「默认：沿程序需要的最小 scope 立刻可见 / 或永远不传到无关 die」——具体默认要在写 B 的公理时选定，并像今天的 `_pick_default_write` 一样**可解释**。错误的默认是「所有写都立刻 `visible@system`」：那会直接退回 A，约简掉的是整个 B。

实现时约简模块不要死绑 `is_read`。接口形状建议：

```text
relevant(program, property) -> Set[eid]
  A: eid 来自 load
  B: eid 来自 load ∪ propagate ∪ visible
  C: eid 再并上 copy / copy_complete / device_fence
```

### 3.3 C：relevant-transfer

异构里，真正贵的是 DMA / memcpy / 映射窗口，不是 GPU 上又一个 relaxed load。

一条 `copy` / `copy_complete` **relevant**，当且仅当：

1. 目的 aspace 上存在一条相关 load / assert，其值可能来自这次传输；或
2. 传输完成是跨设备同步链的一环（例如「NPU 写 SRAM → DMA → 主机 acquire」）；或
3. 竞争定义跨了窗口（CPU 还在写 host buffer 时 DMA 已读走）。

无关内核里的私有 SRAM 往返、与断言无关的调试拷贝，不应进入笛卡尔积。

`device_fence` 的相关性类似今天的 acquire load：后面没有跨域观察者时，设备内屏障不必展开所有交错。

### 3.4 三档约简对照

| 档 | 枚举主对象 | 可坍缩的对象 | 性质仍是什么 |
| --- | --- | --- | --- |
| A | 相关 `load` 的 rf | 无关 load 的默认 rf | assert / RA-sw / 同域 race |
| B | 相关 load 的 rf **加上** 相关 propagate | 传到无关 die 的可见性 | 同上，但 hb/race 带 scope |
| C | 相关 transfer / 跨域 fence，再加各域内部的相关 load | 私有 aspace 里的内部往返 | assert 在指定 aspace；竞争必须先定义是否共享 |

无论哪一档，约简都要能回答「这个事件为什么 relevant」。做不到就不要宣称性质保持。

---

## 4. 和 `xs-am-verify` 怎么接：何时用 herd/RVWMO，何时换金标准

分层已经写在 ARCHITECTURE。这里只补「接到哪一层、谁说了算」。

```text
语言 JSON（本仓库）     —— 金标准：本器枚举（将来 + mo），只对 A 的 RC11-RA 片段负责
    不直接吃 events.jsonl

ISA 轨迹（xs-am-verify）—— 金标准：herd7 + riscv.cat
    W/Wg 重建 po/rf/co/fr；DUT 观察态 ⊆ Allowed(herd)

片间互连（尚无）        —— 金标准：自写公理 / 将来的 cat；不是 riscv.cat

GPU / NPU / PCIe       —— 金标准：PTX/厂商手册、操作模型、或专用 herd 模型
    不是本器，也不是 riscv.cat
```

### 4.1 继续用 herd / RVWMO 的时候

- **A，片内，RISC-V 核**：`xs-am-verify` 现有闭环。规格见 `07-rv64-mm-litmus.md`：`Allowed(herd7, riscv.cat)`，允许态要采到 `exists`。
- 核数从 2 增到 N：仍是 RVWMO，仍用同一 cat。成本是仿真和轨迹，不是换理论。
- 本仓库 **不** 替代这条链。语言级 MP 安全，推不出香山 MP 符合 RVWMO。

轨迹细节（对接 B 时要记得，但不要抄进本器）：

- `commit_cycle`：提交，给 `po` 用。
- `visible_cycle`：sbuffer 全局可见，给 `co` 用。
- 读只有 commit，没有 Wg。
- 同行写合并会导致某 W 没有 Wg（`S-NO-VISIBLE`）。这是单芯片实现噪声，升到 B 时「某 die 上看不见」必须和「被 sbuffer 合并」分开记账。

### 4.2 完全是另一套金标准的时候

| 对象 | 为什么 herd/`riscv.cat` 不够 | 该用什么（方向） |
| --- | --- | --- |
| B 跨 die / 跨 socket 非全局可见 | cat 没有 `visible@die` | 自写传播公理；或扩展 cat，但那是新论文/新工具，不是本器一行 JSON |
| C GPU kernel | PTX 作用域与 RC11/RVWMO 不同 | NVIDIA PTX 内存模型；研究侧可用 herd 的 GPU 模型，**单独**跑 |
| C NPU SRAM + DMA | 往往没有公开 cat | 厂商手册 + 操作语义（队列、完成、flush） |
| C PCIe / 非 CXL.mem | posted + completion，不是缓存协议 | PCI 事务序 + 门铃协议 |
| C CXL | 视类型接近 NUMA 或设备缓存 | CXL + 主机内存模型；先归类再决定能不能降级成 A/B |
| 本仓库语言级程序 | 本器不是 ISA oracle | 继续用本器；不要用 herd 跑 JSON |

### 4.3 明确的对接顺序（和「不要从第 6 步倒着做」一致）

1. 本仓库：单芯片 `mo` / fence / 可解释 relevant-load。
2. 共享 Event IR **设计**（本文 §2），字段默认退化到今天。
3. 对接层（新模块或 `xs-am-verify` 一侧）：`(W, Wg)` → 软件 Event；**单向**，本器仍不读 jsonl。
4. A 多核：只加 hart 标注 + 更多 litmus，金标准仍是 herd。
5. B：先写传播公理和 2-die 教具，再谈工具；herd 只负责每个 die 内部。
6. C：另开文档 / 另开检查器。本仓库最多提供「图 + 约简」接口，不提供 RC11 结论。

禁止的接法见 §6。

---

## 5. 分阶段：近期只做单芯片 mo；多 CPU 何时开始；异构更后

与 CURSOR_HANDOFF §11、ARCHITECTURE §7 同一条路，**不要倒着做**。

| 阶段 | 做什么 | 不做什么 | 建议触发条件 |
| --- | --- | --- | --- |
| **P0 现在** | 单芯片 RA 原型保持可跑；文档把档位写清（本文） | 不改 `Event`，不加 `mo` 以外的跨片字段 | 已满足 |
| **P1 本仓库近期** | 显式 `mo` / coherence → 最小 `fence` → 可解释 relevant-load → benchmark | 不实现 propagate；不读 `events.jsonl`；不加 `device_kind` | 开题主线；P0 稳定 |
| **P2 接口设计** | 按 §2 把字段和 `kind` 写进设计（可更新本文）；代码仍可不加 | 不把默认值做成「非全局可见」 | P1 的 mo 有独立函数和至少 2 个例子 |
| **P3 同构多 CPU 可开始** | 语言级：更多线程的 RC11 例子。ISA 级：在 `xs-am-verify` 扩核数 / 加用例。本器语义仍是 A | 不把 `socket_id` 当 scope；不宣称多 socket 可见性 | P1 完成，且需要和双核 litmus 对照时 |
| **P4 多芯片 / 多 die** | `visible@scope`、`propagate`、relevant-propagation；片间自写公理 | 不用 `riscv.cat` 判跨片；不在本器里仿真互连周期 | P2 契约写清；有具体 2-die 研究问题（不是「先把字段加了」） |
| **P5 异构 CPU+GPU+NPU** | 另套 IR：aspace、copy_complete、device_fence；relevant-transfer；各自金标准 | 不把 kernel 写成当前 JSON threads；本器不输出「该 GPU 程序 RC11 安全」 | P4 的约简接口已经不绑死 `load`；有明确设备模型来源 |

**「多 CPU 何时开始」的可操作回答**：

- **语言级多线程**：P1 之后随时可以加 examples，不必等新字段。这仍是 A。
- **和香山双核对照**：在 `xs-am-verify` 做，本仓库只保持分层叙述。P3。
- **多 socket 若 cache-coherent**：仍是 P3 / A。
- **多 socket / 多 die 若可见性分裂**：P4 / B，不要提前。

**异构列为更后的原因**（避免「顺手也做了 GPU」）：

- 当前 JSON 和 `evaluate_execution` 假定单一 `loc` 名空间、单一 `sw` 规则。
- 开题范围是 RC11 子模型 + 约简；答辩材料已写「不直接做 GPU」。
- 没有可引用的统一 cat；每接一种设备就要接一份手册和一份 oracle。
- 约简创新在 A/B 上就能写论文；C 是推广，不是近期验收项。

---

## 6. 错误接法 vs 正确接法

| # | 错误接法 | 为什么错 | 正确接法 |
| --- | --- | --- | --- |
| 1 | 把 GPU/NPU 核写成当前 JSON 的 `threads`，用本器跑 assert | 单一 aspace、单一 RC11 `sw`；结论不对应任何真实模型 | C 用独立 IR；跨设备只经 `copy_complete` / 系统级同步 |
| 2 | 给 `Event` 加上 `die_id` 却继续用 `_reads_from_candidates` | 字段暗示跨片，语义仍是全局 rf，比没字段更误导 | 没实现传播之前就不加字段；加上时默认必须退化成今天（§2.6） |
| 3 | 「多芯片 = 线程数 × die 数」 | 忽略 propagate；合法执行集不对 | 片内线程保持 A；片间显式 `visible@scope` |
| 4 | 用 herd7/`riscv.cat` 判跨 die 或 GPU | cat 只有单一 RVWMO 域 | 片内 / A：herd。B/C：自写或厂商模型 |
| 5 | 把 `events.jsonl` 喂给 `weak_memory_verifier.py` | 本器是语言级枚举器，不是轨迹检查器；W/Wg 也不是 JSON `store` | 单向对接层：轨迹 → 关系在 `xs-am-verify`；本器保持 JSON 程序 |
| 6 | 用本器 race/assert 当香山正确性 oracle | ARCHITECTURE 已禁止 | 香山：`xs-am-verify` + herd。本器：教具与约简实验 |
| 7 | 把 RC11 `release/acquire` 当成 RISC-V `fence` 或 PTX `fence.sc` | 三套公理 | 各层用各层的同步事件；对照只做「类似教具」，不做等价声称 |
| 8 | 把 Wg 直接改名叫 `visible` 就声称完成多芯片 | 单芯片 Wg 是**一个**全局时刻；B 需要**每个 scope** 一次可见 | 单芯片：W/Wg 留在轨迹层。多芯片：一条写多条 `visible@scope` |
| 9 | 用 `seq_cst` store 冒充 `cudaMemcpy` / DMA 完成 | 完成是跨 aspace 的新写，不是同 loc 的 SC | `copy` + `copy_complete`；目的侧再 `load` |
| 10 | 把 CXL/PCIe 一律当共享 RC11 内存 | PCIe 默认非缓存一致；CXL 分类型 | 先归类：能降级 A/B 的才降级；否则走 C 的 transfer |
| 11 | 约简模块写死 `if event.kind == "load"` | B/C 的爆炸点在 propagate/copy | 约简接口对「候选边」工作，load 只是 A 的一种边 |
| 12 | 从 P5 倒着做，先堆异构字段再补 `mo` | 默认值会污染三个 examples；研究主线被冲掉 | P1 → P2 → P3 → P4 → P5 |
| 13 | 在本器 JSON 里加 `commit_cycle` | 把仿真时钟做成语言语义 | 周期留在 `build_relations.py`；本器只保留因果事件 |
| 14 | 声称「当前 load/store/assert 已覆盖 GPU/NPU」 | 输入语言没有 aspace/设备/拷贝 | 明确：**没有覆盖**。C 是更后阶段 |

---

## 7. 给接手的检查清单

动手之前先对号入座：

1. 是不是还在单一 `host` 地址空间、单一一致性域？**是 → A**，用本器 +（ISA 时）herd。
2. ISA 相同，但存在「写在这边已可见、那边还没有」？**是 → B**，先写传播公理，不要加线程。
3. 出现 GPU/NPU/DMA/PCIe 映射？**是 → C**，换 IR 和金标准，本器 JSON 停用。
4. 想加的字段默认能否让现有 examples 逐执行不变？**否 → 先别加进代码。**
5. 约简对象是 load、propagate 还是 copy？**不要混在一个 `relevant_loads` 里却改语义。**

本仓库当前唯一该推进的实现工作仍是：**单芯片 `mo/coherence`，然后是 fence 与可解释 relevant-load。** 本文只回答「以后三档怎么接」，不授权现在改 `weak_memory_verifier.py`。
