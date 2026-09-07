# 审查：按 HANDOFF 现在做最小 mo/coherence

- 审查角色：独立审查员，不写验证器逻辑
- 日期：2026-09-07
- 对照基准：磁盘当时最新代码（落地 agent **尚未**改 `weak_memory_verifier.py` / `examples/`；`writes_by_loc` 已存在，无 `modification_order`）
- 必读：`docs/CURSOR_HANDOFF.md`、`docs/ARCHITECTURE.md`、`docs/research_work_breakdown.md`、`weak_memory_verifier.py`、`examples/`、`smoke_check.py`
- **落地复核（同日稍后）**：见文末「落地复核」。结论 **有条件通过**。上一份「必做第三条并发写 CoRR」已更正为不该拒绝。

## 总评：**勉强**

- **方向合理**：在「先做 fence / 先重写约简 / 先对接香山」三者里，现在补最小 mo/coherence 更对。
- **HANDOFF 任务 1 的写法会带偏**：验收太弱，最后一条检查几乎是现有 `_consistent_reads` 的换皮；若不改设计，很容易做出「字段叫 mo、语义仍是 hb 极大写」的假完成，并对外说成「已有显式 mo」。

下面按审查问题逐条回答。

---

## 1. 现在做 mo/coherence，是否比先做 fence / 先重写约简 / 先对接香山更合理？

**是，比那三条都更合理。** 但「按 HANDOFF 字面做任务 1」不等于「合理地做 mo」。

| 备选 | 为什么现在不该先做 |
| --- | --- |
| 先做 fence | `fence` 已能解析、语义占位。RA 教具（`message_passing`）靠 `sw ⊆ hb` 已能区分。`seq_cst fence` 的真正约束常要和 `mo`/`sc` 一起才说得清；先做 fence 会把「屏障效果」和「还没有 coherence」缠在一起。 |
| 先重写约简 | 研究主线确是 relevant-load。但约简的正确性是相对「一致执行集合」而言的。现在一致执行 = rf 笛卡尔积 − `_consistent_reads`。先把约简规则写漂亮，再改一致执行集合，等于把「为什么这个 load 相关」作废一遍。`ARCHITECTURE.md` / HANDOFF 阶段 A 都把 mo 放在约简升级前面，这点对。 |
| 先对接香山 | `ARCHITECTURE.md` 已写死分层：本仓库是语言级 RC11/RA 片段，`xs-am-verify` 是 ISA/RVWMO。RC11 的 `release/acquire` ≠ RISC-V `fence`。从第 6 步倒着做会把 Event IR 和验证器语义一起写脏。 |

开题稿（`docs/opening/formal.md`）把 `modification order` 写进「程序执行表示」，约简才是创新点。先把执行对象补到「至少有 mo 这个关系」，后面约简实验才有资格说自己约的是 RC11 风格图，而不是 hb 可见性启发式。

HANDOFF 内部有一处过时话术：文首「本轮不要加 mo」和 §11「先重构再 mo」与「任务 1 现在就做 mo」并列。以 `ARCHITECTURE.md` §7 为准：**函数边界已切开，不必再为 mo 做拆文件重构**；也不要借 mo 之机加 `die_id`。

---

## 2. HANDOFF 对 mo 的验收够不够当「显式 mo」？本轮不该假装已有什么？

**不够。** 现在的最低验收是：

1. 至少 2 个覆盖 mo/coherence 的例子
2. 相关逻辑有单独函数
3. README 更新语义范围

这三件事可以在 **零新增拒绝能力** 的情况下全部勾掉：把 `_consistent_reads` 改个名、用现有 MP 变体当例子、README 写上「已支持 mo」。

任务 1「建议做法」还有两处已经过时或有害：

- 「在 Program 或 Execution 层增加 `writes_by_loc`」——**已经在 `Program` 上**（含 `init:*` 虚拟写）。再加一份只会造成双源。
- 「检查 load 是否读取了一个被更晚 **hb 可见写** 遮蔽的值」——这就是 `_consistent_reads` 现在做的事，**不是**显式 mo。

### 本轮要做到才配叫「最小显式 mo」

- `mo` 是 **每个地址上写事件的全序**，且是 **每条候选执行上的关系**（挂 `Execution`，不挂 `Program`，不进 JSON）。
- 一致性是 **存在性**：给定 rf 与 hb，是否 **存在** 一条 mo 同时满足 CoWW / CoWR / CoRW / CoRR（或等价地 `hb ∪ mo ∪ fr` 在同址上无环）。
- 至少 1 个例子是 **当前 `_consistent_reads` 放行、加上 mo 后应拒绝**（典型：CoRR，两路并发写、同线程先读新再读旧）。
- 文档写清：这是 coherence 四条的存在性检查，不是完整 RC11。

### RC11 真正需要、本轮不该假装已有

不要在 README / 函数名 / 注释里写成「已实现 RC11」。本轮做完 mo 之后，下面这些仍然没有：

| 缺失 | 为什么本轮不该顺手宣称 |
| --- | --- |
| release sequence | 现在 `sw` 只认「release/SC 写被 acquire/SC 读到」的直接 rf，中间 relaxed 写不延长 release |
| `seq_cst` 全序 / psc | `order=seq_cst` 只是当 RA 用，没有 SC 原子的全序 |
| fence 语义 | 仍是占位事件 |
| RMW / CAS 与 mo 相邻 | 输入语言没有 rmw |
| consume / dob / 依赖定序 | 不在范围 |
| no-thin-air / promising | 公理枚举本来就不管 |
| 非原子与原子混合的完整 C11 条款 | race 仍是简化 DRF |
| 多芯片 `visible@scope` | 另一层，见 §5 |

---

## 3. `_consistent_reads`（hb 极大写）和「显式 mo」是什么关系？补 mo 是必要增强还是重复？

**设计对了是必要增强；按 HANDOFF 最后一条做就是重复。**

当前实现（`_consistent_reads`）：

- 若存在 `W -hb-> R` 的同址写，则 rf 必须落在这些写里的 **hb 极大元**。
- 同址两写 **互不 hb** 时，这里剪不动。注释自己也写了：这是「还没有 mo」时的替身。

因此：

- **重叠**：MP 里「acquire 看到 flag 之后还读到 x 的初值」已被 hb 极大写杀掉。再用 mo 杀一遍，没有新信息。
- **缺口（这才是 mo 的存在理由）**：两写并发、读方与写方无 hb 时的 **CoRR / 部分 CoWR·CoRW**。例如 T1:`Wx=1`，T2:`Wx=2`，T3:`Rx=2; Rx=1`。当前器会留下，RC11 不允许。

还有一个 **反向风险**：`_consistent_reads` 比 RC11 **更强**。一旦已有任意 hb 可见写，它禁止读「未 hb 到该 load 的并发写」。RC11 里这是允许的（只要能排一条 mo，让所有 `W -hb-> R` 的写都 mo-先于被读的写）。现有三例都是每址至多一个程序写，测不出这一点。

所以：

- 保留 `_consistent_reads` 再叠一层同名检查 = **重复 + 继续过强**。
- 用 Co* 存在性 **替换**（或明确降级）`_consistent_reads` = **必要增强**。
- 两套同时生效还自称「显式 mo」= **漏检真实 coherence、误杀合法并发读**。

---

## 4. 有没有语义过度宣称风险？

**有，而且是本轮最大的文档风险。**

已经偏大的叫法：

- 目录名 `weak-memory-rc11`，README「面向 RC11/RA」
- 开题/答辩材料把「面向 RC11 的程序执行表示」写成研究内容
- HANDOFF §12 仍说「已经能跑的 RC11/RA 风格研究原型」

`ARCHITECTURE.md` 现在的刹车是对的：缺 mo 时不得称完整 RC11；`message_passing` 安全只说明「这个简化模型能区分这两个例子」。

任务 1 若只改 README 一句「已支持 mo/coherence」，刹车会立刻失效。实现者很容易把「有一个叫 `modification_order` 的字段」写成「已实现 RC11 coherence」。

本轮允许的表述：

> 在原有 RA 风格 sw/hb 上，对每个地址做 **coherence 四条的存在性 mo 检查**。仍不是完整 RC11。

禁止的表述：完整 RC11、C11 公理化、已覆盖 coherence 全模型、已可当香山/C11 oracle。

---

## 5. 对后续多芯片 / 异构可见性，这一步会不会把数据模型堵死？

**按下面做不会堵死；按 HANDOFF §6 顺手加字段会堵死。**

语言级 C11/RC11：每个地址一条 **全局** mo。这和「写在哪个 die 上何时对另一 die 可见」不是同一关系。本仓库继续用「单地址空间、mo 的 key 只有 `loc`」，等于把语言层钉死，**给后面的 visibility 层留出独立挂钩**，这是对的。

会堵死的做法：

1. 把 `mo` 建在 `Program` 上（程序写死写序，执行不能选）。
2. 把 `die_id` / `scope` 编进 mo 的 key（变成「每 die 一条 mo」），把硬件传播序和语言 mo 焊在一起。
3. 本轮就给 `Event` 加上 `core_id` / `cluster_id` / `die_id` / `socket_id`（`ARCHITECTURE.md` 明确说先不要写死；字段一出现，人会以为已经有跨片模型）。
4. 对 rf × mo 做笛卡尔积，并把约简死绑在「load 组合数」上——后面要约的是 propagation / visibility，统计口径会断。

`writes_by_loc` 留在 `Program`（静态索引）没问题。`modification_order` 只能是 `Execution` 上的 **witness**（检查器用的那条存在性证据），并在 `--show-executions` 里打印。

---

## 必须改 vs 可以后做

### 必须改（否则任务 1 算带偏 / 假完成）

1. **mo 挂 `Execution`，做存在性检查，禁止和 rf 笛卡尔积。** 找不到合法 mo 就丢执行；找到则存一条 witness。不要写进 JSON，不要挂 `Program`。
2. **至少 1 个例子区分「仅 hb 极大写」和「显式 mo」。** 推荐 CoRR（两写者 + 同线程读 2 再读 1）。禁止两个新例子都是 MP / hb 遮蔽的变体。
3. **不要把 `_consistent_reads` 换皮成 `_check_mo_consistency`。** 必须二选一写进 `ARCHITECTURE.md`：(a) 用 CoWW/CoWR/CoRW/CoRR 替换它；或 (b) 本轮故意保留「有 hb 可见写就必须读 hb 极大写」，并写明这比 RC11 更强。不能两套一起跑还叫 mo。
4. **README + `ARCHITECTURE.md` 同步改语义边界**，只写「最小 coherence（存在性 mo）」，并列未做清单（release sequence、SC 全序、fence、RMW、consume）。原三例 `smoke_check.py` 必须继续过。
5. **本轮不加层级字段，mo 的 key 只有 `loc`。**

### 可以后做

- `fence` 最小语义（任务 2）
- relevant-load 三类拆分与「为什么相关」输出（任务 3）
- benchmark 批处理（任务 4）
- 拆文件 / package（函数已切开）
- release sequence、SC 全序、RMW
- 与 `xs-am-verify` 共享 Event IR、`visible@scope`
- 把 `_consistent_reads` 的过强行为改成标准 CoWR（若本轮选了 (b) 故意保留）

---

## 给实现者的修正建议（可执行）

1. **存在性 mo，禁止 rf×mo 枚举。** 在 `evaluate_execution` 里、hb 算完后，对每个 `loc` 求一条全序：CoWW（写之间的 hb ⊆ mo）、CoWR（`W-hb->R` 且 `R-rf->W'` ⇒ `W-mo->W'`）、CoRW（`R-rf->W` 且 `R-hb->W'` ⇒ `W-mo->W'`）、CoRR（同址两读有 hb 时，它们的源写在 mo 上单调）。失败则丢弃该执行。`Execution` 增加 `modification_order: Dict[str, List[str]]` 存 witness。笛卡尔积仍然只枚举 rf。

2. **例子必须打在 `_consistent_reads` 杀不死的点上。**  
   - 必做：`examples/coherence_rr.json`（两线程各 `Wx=1`/`Wx=2`，第三线程连续两读，断言「允许读到 2 然后 1」应失败 / 该 rf 组合应被 mo 丢掉）。先跑旧器确认该组合今天会被留下。  
   - 第二例用 CoRW 或「同址两写已有 hb、mo 必须延伸」，不要再做一条 MP。  
   - 两个新例子都纳入 `smoke_check.py`，约简前后性质一致。

3. **先处理与 `_consistent_reads` 的关系，再写函数。** 若走标准 Co*：删掉（或让它不再作为拒绝条件）hb 极大写规则，避免误杀「acquire 之后读到并发写」。若故意保留过强规则：函数名不要带 `mo`，文档写「非 RC11」。禁止 `if not _consistent_reads: return False` 后面再抄一遍同样循环。

4. **文档只升一档，不升到 RC11。** README「本仓库不做什么」改为「有最小存在性 mo / 无完整 RC11」。`ARCHITECTURE.md` §4 把 mo 从「没做」挪到「做了」，并写四条 Co* 与未做清单。CLI 的 `consistency` 失败信息不要再只写 `hb-visible write`。

5. **输出 witness，便于查漏检。** `_format_execution` 打印每个 loc 的 mo 链。不要加 `die_id`。不要改 JSON schema。不要动现有三例的预期（MP 不 racy、racy_counter 有竞争）。

---

## 对照落地实现时的检查单

落地 agent 交活后，用这张表打「夸大 / 漏检」，不要看函数名：

- [x] 新例子里是否存在「旧 `_consistent_reads` 为 True、新检查为 False」的 rf 赋值？没有则本轮没有真 mo。
- [x] `itertools.product` 是否仍只扫 load 的 rf？若 product 了 mo，算带偏。
- [x] `modification_order` 是否只在 `Execution`？出现在 `Program` / JSON 则算堵死。
- [x] `_consistent_reads` 是否被换皮保留？是则重复。
- [x] README 是否出现「完整 RC11」或删掉未做清单？是则过度宣称。
- [x] `Event` 是否多了 `die_id` / `scope`？是则违反本轮边界。
- [x] `python3 smoke_check.py` 是否仍过原三例？

复核过程与结论见下一节。上一份「必做第三条并发写 CoRR」按存在性 mo **不该拒绝**，已更正。

---

## 落地复核（2026-09-07）

对照磁盘最新代码（`weak_memory_verifier.py`、`examples/coherence_*.json`、`smoke_check.py`、`README.md`、`docs/ARCHITECTURE.md`）。本复核 **不改验证器**。本机已跑 `python3 smoke_check.py` 与 `python3 benchmark_compare.py`，均通过。

**结论：有条件通过。** 五项「必须改」在实现与主文档上均已落地；不采用「两路完全并发写 + 先 2 后 1」作为反例是对的，不是漏检。条件是：HANDOFF / 实验说明等旁路文档仍把 mo 标成未做，不修则下一任会把任务 1 再做一遍。

### 检查单打分（不要看函数名）

| 项 | 结果 | 证据 |
| --- | --- | --- |
| 旧规则放行、mo 丢掉的 rf | **有，真 mo** | `coherence_rr` 9 组 rf 里 3 组区分：`(r1,r2)=(1,0)/(2,0)/(2,1)`。`coherence_rw` 4 组里 1 组：`(b,c)=(2,1)`。旧 hb 极大写对这 4 组全为 True（读者与写者无 hb，`visible` 为空）。MP 上旧/新一致，不充当区分例，这是对的。 |
| `product` 只扫 rf | **是** | `analyze_program` 仍 `product(*candidates_per_load)`，候选来自 `_reads_from_candidates`。mo 在 `evaluate_execution` 里事后求 witness。 |
| `modification_order` 只在 Execution | **是** | `Execution` 有该字段；`Program` / JSON schema / `Event` 都没有。`--show-executions` 打印 `loc: e1 < e2 < …`。 |
| `_consistent_reads` 换皮 | **否** | 函数已删。拒绝条件改为 `_check_mo_consistency` → 强制边 + 拓扑序。`_pick_default_write` 仍用 hb 极大写，只给无关 load 填默认 rf，evaluate 仍会用 mo 丢掉不合法默认值。 |
| 宣称完整 RC11 | **无** | README / ARCHITECTURE 写「最小存在性 mo / 无完整 RC11」，并列 release sequence、SC 全序、fence、RMW、consume。CLI 失败信息是 `no consistent modification order (CoWW/CoWR/CoRW/CoRR)`，不再写 `hb-visible write`。 |
| `die_id` / `scope` | **无** | `Event` 字段仍是 eid/thread/index/kind/loc/value/target/right/atomic/order/guard。mo 的 key 只有 `loc`。 |
| 原三例 smoke | **过** | MP 不 racy、断言不败；racy_counter 有竞争且断言可败。约简不改性质。`message_passing` 全枚举 4、留下 3（看到 flag 仍读 x 初值被 mo 杀掉，与旧规则同一组）。 |

### 1. 「必须改」是否都落地

| 必须改 | 落地？ |
| --- | --- |
| mo 挂 Execution，存在性检查，禁止 rf×mo 笛卡尔积 | 是。`_forced_mo_edges` + `_linear_extension`；找不到全序则 `failed_assertions` 标 `consistency`，`analyze_program` 丢掉。 |
| 至少 1 个例子区分 hb 极大写 vs 显式 mo | 是。两例都不是 MP 变体；读者全是 relaxed，无 acquire。 |
| 不用 `_consistent_reads` 换皮；ARCHITECTURE 写明选 (a) | 是。§3/§4 写「已替换 hb 极大写拒绝规则」。 |
| README + ARCHITECTURE 只升一档；原三例继续过 | 是。 |
| 不加层级字段，mo key 只有 loc | 是。 |

另：`init` 被写成该地址 mo 的最小元。这是工程补丁（`init` 不进 hb，单靠标准 CoWR 杀不掉 MP 的「看到 flag 仍读 x 初值」），ARCHITECTURE §4 已写明，不算偷渡完整 RC11。

### 2. 不采用「两写完全并发 + 同线程先 2 后 1」是否成立？会不会漏检？

**成立，不是漏检。上一份审查把这条当成「必杀 CoRR」是错的。**

存在性 mo 下，CoRR 是 **给 mo 定向**，不是单独否定一份 rf：`R1 -hb-> R2` 且源写不同 ⇒ `src(R1) -mo-> src(R2)`。两路写互不 hb 时，读到 2 再读 1 只是强制 `W2 < W1`（可配 `init < W2 < W1`），无环，**C11/RC11 允许**。C++ `[intro.races]`：后一次读必须读到同一个写、或 mo 上更晚的写；先 2 后 1 等于选定 `W2` 在 mo 上先于 `W1`。

本复核用临时程序（不入库）跑了「T0:`Wx=1`，T1:`Wx=2`，T2: 两读」：`(r1,r2)=(2,1)` 被留下，witness 为 `init:x < t1:0 < t0:0`。旧 hb 极大写也同样留下。把它当反例会 **误杀合法执行**。

他们的反例打在 **另一条 mo 边已经存在** 时的成环：

- `coherence_rr`：同线程 `Wx=1; Wx=2`，CoWW 固定 `1 mo 2`；再先读 2 后读 0/1，CoRR 反向，环。
- `coherence_rw`：故意不放 x 初值，让 T1 只能 `rf` 到 `Wx=1` 再写 2，CoRW 固定 `1 mo 2`；T2 先 2 后 1 成环。不是 MP。

这才是「旧器杀不死、存在性 mo 该杀」的点。

### 3. 有没有仍把简化模型说成完整 RC11？

**主文档没有。** 过度宣称刹车还在。风险改成 **文档家族不同步**（说少了，不是说多了）：

- `docs/CURSOR_HANDOFF.md` §2 / §11 / §12 仍把显式 mo 列在「尚未实现」
- `docs/HETEROGENEOUS-SCOPE.md` 仍写「现在缺 mo」「以后的 mo」
- `docs/experiment_notes.md`、`docs/benchmark_summary.md`、`docs/research_work_breakdown.md` 未列入新例 / 仍写下一步才加 mo

README 表格数字与本机 `benchmark_compare.py` 一致（含 coherence 两例 9/9、4/4）。

### 剩余问题（最多 5 条，不挡本轮实现验收）

1. 把 HANDOFF / HETEROGENEOUS-SCOPE / experiment_notes / benchmark_summary 改成「最小存在性 mo 已做」，避免任务 1 被重做。
2. 建议补一个 **应保留** 的并发写 2-then-1 正例（或只写进文档），防止下一任再按上一份审查的过时 CoRR 去「补漏」。
3. ARCHITECTURE §2 金标准仍写「本器枚举 + 简化 hb」；§4「杀不死两写互不 hb 时的 CoRR」容易让人以为并发写 2-then-1 该杀。应改成「两写已有 hb/CoRW 边时，先新后旧才成环」。
4. `init` 最小元保持写在边界里即可，不要再包装成标准 CoWR。
5. 仍无回归覆盖「acquire 之后读到并发写」——旧规则会误杀、新规则应放行。可以后做。
