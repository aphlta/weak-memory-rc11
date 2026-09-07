# weak-memory-prototype

这是一个面向 `RC11 / RA` 风格弱内存验证的最小研究原型。

它不是完整的 C/C++11 验证器，而是一个适合开题、论文原型和后续扩展的起点。当前版本重点支持：

- 事件建模
- `reads-from` 枚举
- `release/acquire` 风格同步
- `happens-before` 推导
- `data race` 检测
- `assert_eq` 检测
- 基于相关性分析的 `load` 约简

## 目录

- `weak_memory_verifier.py`：核心验证器
- `examples/`：示例程序
- `research_work_breakdown.md`：研究工作拆解

## 输入格式

程序使用 JSON 描述。

示例：

```json
{
  "name": "message-passing",
  "initial_memory": {
    "x": 0,
    "flag": 0
  },
  "threads": [
    [
      {"op": "store", "loc": "x", "value": 1, "atomic": true, "order": "relaxed"},
      {"op": "store", "loc": "flag", "value": 1, "atomic": true, "order": "release"}
    ],
    [
      {"op": "load", "loc": "flag", "target": "f", "atomic": true, "order": "acquire"},
      {"op": "load", "loc": "x", "target": "r", "atomic": true, "order": "relaxed"},
      {"op": "assert_eq", "left": "r", "right": 1, "when": {"f": 1}}
    ]
  ]
}
```

## 支持的操作

### `store`

```json
{"op": "store", "loc": "x", "value": 1, "atomic": true, "order": "release"}
```

字段：

- `loc`：地址名
- `value`：写入值
- `atomic`：是否原子
- `order`：可选，支持 `relaxed`、`release`、`seq_cst`

### `load`

```json
{"op": "load", "loc": "x", "target": "r", "atomic": true, "order": "acquire"}
```

字段：

- `loc`：地址名
- `target`：读到的值写入哪个线程内变量
- `atomic`：是否原子
- `order`：可选，支持 `relaxed`、`acquire`、`seq_cst`

### `assert_eq`

```json
{"op": "assert_eq", "left": "r", "right": 1}
```

可选带条件：

```json
{"op": "assert_eq", "left": "r", "right": 1, "when": {"f": 1}}
```

含义是：如果线程内变量 `f == 1`，则要求 `r == 1`。

### `fence`

当前版本先保留语法位置，但尚未对 fence 单独建模；后续可扩展。

## 运行方法

### 1. 直接查看摘要

```bash
python3 weak_memory_verifier.py examples/message_passing.json
```

### 2. 打印候选执行

```bash
python3 weak_memory_verifier.py examples/message_passing.json --show-executions
```

### 3. 使用约简模式

```bash
python3 weak_memory_verifier.py examples/message_passing_with_irrelevant_load.json --reduction relevant
```

### 4. 输出 JSON 摘要

```bash
python3 weak_memory_verifier.py examples/message_passing.json --json
```

### 5. 比较约简前后

```bash
python3 benchmark_compare.py
```

### 6. 冒烟检查

```bash
python3 smoke_check.py
```

## 当前语义范围

这份原型是“研究起点”，不是完整标准实现。当前做了这些简化：

1. 主要围绕 `reads-from` 关系枚举候选执行
2. 用 `program order + synchronizes-with` 构造 `happens-before`
3. `data race` 采用简化判定规则
4. 已实现一种面向断言 / 同步 / race 的 `load` 相关性约简
5. 尚未显式建模完整 `modification order / coherence`
6. 尚未覆盖完整 RC11/C11 边界规则

## 最适合怎么用

它最适合做三件事：

1. 作为开题与中期汇报时的“已有工作”展示
2. 作为论文中工具原型的初始版本
3. 作为后续加入状态空间约简算法的实验底座

## 后续扩展建议

- 增加 `mo/coherence` 显式约束
- 加入 `fence` 真正语义
- 增加 `assert` 表达式类型
- 批量 benchmark
- 比较约简前后的候选执行数量
