# 架构设计

chunkweave 采用 Policy 驱动的分层架构：

```
YAML Policy → Compiler → Execution IR → Runtime → ChunkResult
```

调用方只接触两端：加载 Policy（声明式配置）与 `ChunkEngine.execute`
（统一执行入口）。Context 提供运行期数据（动态元数据取值），Provider
按次注入（语义相似度服务），二者都不进入 Policy 或 IR。

## 分层

```
caller
  └─ ChunkEngine            公共入口：validate / compile / execute / register
       ├─ Policy            policy.py：YAML 加载 + 结构校验（Pydantic）
       ├─ compiler.py       Policy → ExecutionPlan（语义校验 + Policy Hash）
       ├─ Registry          engine.py：StrategySpec（name/factory/params_model/requires_provider）
       └─ Runtime
            ├─ metadata.py        Context 解析 + 逐块 metadata 组装
            ├─ strategies.py      Chunker 协议 + 三个内置策略 → ChunkSpan
            └─ organization.py    逐父块下切 + 组织字段 + 排序 → Chunk
```

## 扁平模块布局

包内不建子包（延续 448d132 的刻意扁平化）：

| 模块 | 职责 |
| --- | --- |
| `models.py` | 异常体系、`ChunkSpan`、`Chunk`、`ChunkResult`、`RESERVED_METADATA_KEYS` |
| `strategies.py` | `Chunker`/`SimilarityProvider` 协议、参数模型、`SeparatorSpec`、三个内置 Chunker |
| `policy.py` | `Policy` 模型与 YAML 安全加载、`API_VERSION` |
| `compiler.py` | `ExecutionPlan`/`PlanLevel`/`PlanField`、`policy_hash`、`compile_policy` |
| `metadata.py` | Metadata Builder：`resolve_fields` + `build_metadata` |
| `organization.py` | Runtime 下切执行：`run` |
| `engine.py` | `Registry`/`StrategySpec`、`ChunkEngine` 公共 API |

## 契约

- **Policy** — 声明式配置。`api_version` 固定 `chunkweave/v1`；
  `pipeline.levels` 非空；未知字段处处拒绝；`metadata.fields` 声明
  `value`/`source` 二选一来源。加载错误为 `PolicyLoadError`，校验错误
  为 `PolicyValidationError`（带字段路径）。
- **ExecutionPlan（IR）** — 编译产物：Policy 身份、`policy_hash`、按序
  层（补全缺省值的声明式 `params`、`requires_provider` 布尔声明）、
  metadata 字段解析计划、include 选项。可 `model_dump_json()` 往返，
  不含任何运行期对象（Provider、Chunker、Context 都不在内）。
- **ChunkSpan** — 策略输出的中间类型：`content`、相对输入文本的
  `start_offset`/`end_offset`、`strategy_metadata`。策略不产生组织
  字段，也不知道全局 Offset。
- **Chunk** — 最终模型：全部系统字段（`chunk_id`/`content`/
  `parent_id`/`level`/`sequence`/`start_offset`/`end_offset`）+
  `strategy` + `strategy_metadata` + `metadata`（业务字段 + include
  启用的保留键副本）。
- **ChunkResult** — `chunks` + 追溯字段（`policy_id`/`policy_version`/
  `policy_hash`/`execution_id`/`engine_version`/`execution_time_ms`），
  `total` 为进序列化的计算字段。
- **策略协议** — `register(name, factory, *, params_model,
  requires_provider=False, replace=False)`；`factory(params, provider)`
  收已校验参数模型与 Provider（不需要时为 `None`），返回
  `chunk(text) -> list[ChunkSpan]` 的 Chunker。

## 关键行为

- **编译先于切块**：`execute` 先 `compile_policy`（策略名注册检查 +
  params 语义校验），再检查 `requires_provider` 缺 Provider、再
  `resolve_fields` 解析 Context——这三步全都在任何 Chunker 调用前
  完成，失败即整体失败。
- **Runtime 逐父块下切**：第 0 层切全文；第 i 层对每个父块 `content`
  独立切块；子块全局 Offset = 局部 Offset + `parent.start_offset`；
  空 span 丢弃；分支无产出即终止；`chunk_id` 广度优先编号；结果按
  `(start_offset, level)` 稳定排序。
- **Policy Hash**：`sha256:` + 规范化 JSON（键排序、`model_dump`、
  字段配置只输出实际声明的来源键）的十六进制；与 Context、text、
  Provider 无关，与 Registry 无关。

更完整的设计取舍、备选方案与已知限制见
`openspec/changes/refactor-to-policy-driven-engine/design.md`。
