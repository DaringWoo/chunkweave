# Metadata 模型

`Chunk` 上有两类元数据，职责边界清晰：

- **`strategy_metadata`（Chunk 属性）**：策略执行产生的信息，由策略
  Chunker 写入 `ChunkSpan`、Runtime 原样搬到 `Chunk` 上。
- **`metadata`（Chunk 属性）**：业务元数据映射 = Policy
  `metadata.fields` 声明的字段 + `metadata.include` 启用的保留键副本。

`metadata` 中的值只读、不影响任何 Chunk 属性。

## 系统字段（保留键）

以下字段是 Chunk 属性或组织/策略信息，被称为保留键：

`chunk_id`、`content`、`start_offset`、`end_offset`、`parent_id`、
`level`、`sequence`、`strategy`、`strategy_metadata`、`metadata`、
`level_name`

`metadata.fields` 声明同名字段会在加载时被拒绝（与 include 开关无关）。

## metadata.fields：Policy 定义字段

```yaml
metadata:
  fields:
    doc_kind: {value: novel}                  # 固定值
    chapter_title: {source: context.chapter.title}  # Context 解析
```

- `value` 固定值：直接写入每个 Chunk 的 `metadata`（`value: null`
  合法）；值必须可无损表示为 JSON：数值有限，对象键为字符串。
- `source` 动态值：执行时沿 `context.` 后的路径在调用方提供的
  Context 映射中逐级取值，取到的值也必须满足同一 JSON 规则。

**Context 只提供值**：它不提供字段声明——字段集完全由 Policy 决定。
Context 中未被 `source` 引用的键一律不读、不会出现在 `metadata` 中。

## Metadata Builder 的职责

Runtime 内的 `metadata.py` 做两件事：

1. **切块前解析**（`resolve_fields`）：在调用任何 Chunker 之前把所有
   `source` 字段解析成 `field_values`。此时失败即整个执行失败，
   不返回部分结果——空文本也照样解析。
2. **逐块组装**（`build_metadata`）：对每个 Chunk，先深拷贝
   `field_values`，再按 include 选项附加保留键副本。每个 Chunk 的
   `metadata` 是独立副本，修改一个不影响其他。

## Context 解析错误（`ContextResolutionError`）

| 情形 | 结果 |
| --- | --- |
| `context=None` 而字段声明了 `source` | 报错（`no context provided`） |
| 路径中某键缺失，或中间节点不是映射 | 报错，reason 指明缺失的键或非映射位置 |
| 取到的值不可 JSON 序列化 | 报错 `value is not JSON-serializable` |

错误对象带 `.field`（字段名）、`.path`（`context.a.b` 形式）、`.reason`。

## include 复制语义

```yaml
metadata:
  include: {strategy: true, organization: true}   # 缺省均 true
```

- `include.organization`：把 `parent_id`、`level`、`sequence`、
  `level_name` 四个键复制进 `metadata`；
- `include.strategy`：把 `strategy` 与 `strategy_metadata`（含嵌套
  映射的深拷贝）两个键复制进 `metadata`。

关闭某个开关只影响 `metadata` 中的副本——Chunk 的对应属性（如
`chunk.strategy_metadata`、`chunk.level`）始终完整存在。复制语义
的理由：向量库通常只存 `metadata`，组织与策略信息需要进入 `metadata`
才能用于过滤检索。

## 策略元数据键

| 策略 | `strategy_metadata` 键 |
| --- | --- |
| `sliding_window` | `window_index`（0 起）、`overlap_size`（首块 0，之后为 overlap） |
| `recursive` | `separator_used`（字面量/正则源/`""` 兜底/`null` 未切分）、`separator_level`（在 separators 中的下标；合并块取首个叶子的值） |
| `semantic` | `boundary_score`（开启本块边界的分数；首块与兜底边界为 `null`） |

## 示例

Policy 声明 `doc_kind`（value）与 `chapter_title`（source），include
缺省全开时，一个 Chunk 形如：

```json
{
  "chunk_id": "chunk-0003",
  "content": "…",
  "parent_id": "chunk-0001",
  "level": 1,
  "sequence": 0,
  "start_offset": 16,
  "end_offset": 30,
  "strategy": "sliding_window",
  "strategy_metadata": {"window_index": 0, "overlap_size": 0},
  "metadata": {
    "doc_kind": "novel",
    "chapter_title": "风起",
    "parent_id": "chunk-0001",
    "level": 1,
    "sequence": 0,
    "level_name": "window",
    "strategy": "sliding_window",
    "strategy_metadata": {"window_index": 0, "overlap_size": 0}
  }
}
```

## YAML 隐式类型提醒

`2024-01-01`（日期）、`yes/no/on/off`（布尔）、`1.0`（浮点）都会在
解析时被转换——表达字符串请加引号；不可 JSON 序列化的 `value`
会在校验时报错。详见 `docs/configuration.md`。
