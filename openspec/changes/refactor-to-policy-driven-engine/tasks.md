# Tasks

## 1. OpenSpec 正式 Spec 迁移

- [x] 1.1 执行 `openspec sync` 将本 Change 的 delta 合并进 `openspec/specs/` 正式 Spec；验收：`openspec list --specs` 出现 `policy-engine` 与 `policy-compiler`，六份既有 Spec 内容已更新
- [x] 1.2 更新受影响正式 Spec 的 Purpose（`chunk-model`/`chunk-organization`/`chunking-api` 的 Purpose 不再提及四组元数据、Flat/Hierarchical 或结果视图）；验收：Purpose 与新术语一致
- [x] 1.3 运行 `openspec validate --strict --all`；验收：全部通过无错误与警告

## 2. Policy DSL 与 Schema

- [x] 2.1 定义异常体系：`ChunkweaveError` 基类；`PolicyLoadError`（文件读取、YAML 语法、根节点非映射、不安全标签）；`PolicyValidationError`（结构与语义校验，携带字段路径）及子类 `UnregisteredStrategyError`；保留 `RegistryConflictError`、`ProviderMissingError`；新增 `ContextResolutionError`；删除 `ConfigError`、`MetadataConflictError`；验收：各错误路径抛出对应类型，相关 pytest 断言通过
- [x] 2.2 在 `pyproject.toml` 加核心依赖 `pydantic>=2`、`PyYAML`，开发依赖加 `types-PyYAML`；验收：干净环境 `pip install .` 后 `import chunkweave` 成功，mypy 通过
- [x] 2.3 用 Pydantic V2 实现 Policy 模型（`api_version`、`policy` 身份信息、`pipeline.levels`、`metadata.fields`/`include`），`policy.id`/`name`/`version`/`pipeline.levels`/`metadata.fields` 可直接属性访问，且 `policy.policy.id` 等嵌套路径可用；验收：对应 `policy-engine` 的「Policy 顶层结构」「Policy 对象访问」Scenario 测试通过
- [x] 2.4 实现 `Policy.from_file(path)`（UTF-8）与 `Policy.from_yaml(yaml_text)`，文件不存在、YAML 语法错误、根节点非映射报 `PolicyLoadError`；安全解析，`!!python/object` 等对象构造标签被拒绝；验收：「从文件与字符串加载」全部 Scenario（含不安全标签）测试通过
- [x] 2.5 实现结构校验：必填项、类型检查、错误信息含字段路径（如 `pipeline.levels[1].strategy`），`api_version` 固定 `chunkweave/v1`；验收：「结构校验」「API 版本识别」Scenario 测试通过
- [x] 2.6 实现未知字段拒绝（顶层/`policy`/`pipeline`/level/`metadata`/`metadata.include`/字段配置；`value` 内容豁免）与 `policy.version` 的 `MAJOR.MINOR.PATCH` 格式校验；验收：「未知字段拒绝」「Policy 版本格式」Scenario 测试通过
- [x] 2.7 实现 Metadata 字段声明校验：`value`/`source` 互斥（`value: null` 合法）、`value` JSON 可序列化、`source` 为 `context.` 前缀合法路径、include 布尔缺省 true、字段名不得使用保留键（`chunk_id`/`content`/`parent_id`/`level`/`sequence`/`start_offset`/`end_offset`/`strategy`/`strategy_metadata`/`metadata`/`level_name`）；验收：对应 Scenario 测试通过

## 3. Chunk 数据模型

- [x] 3.1 用 Pydantic V2 实现 `Chunk`（全部系统字段 + `strategy_metadata` + `metadata`）与 `ChunkResult`（`chunks` + 追溯字段 + `total` 计算字段进序列化）；验收：`chunk-model`「统一 Chunk 结果模型」「ChunkResult 执行结果模型」「系统字段、策略元数据与业务元数据分离」Scenario 测试通过
- [x] 3.2 实现 `model_dump()`/`model_dump_json()` 及从输出重建，`chunks` 按 `start_offset` 升序、同起点父先于子；验收：「序列化稳定性」「ChunkResult 顺序」Scenario 测试通过

## 4. ChunkSpan 与策略输出协议

- [x] 4.1 定义 `ChunkSpan`（`content`、相对输入文本的 `start_offset`/`end_offset`、`strategy_metadata`）与策略协议（工厂经已校验 `params` 与需要时的 Provider 创建 Chunker，`chunk(text)` 返回 ChunkSpan 序列、声明参数 Schema、无 `metadata_keys`），Registry 提供参数 Schema 供校验；验收：`strategy-registry`「策略协议」「Registry 职责边界」Scenario 测试通过
- [x] 4.2 改造 `sliding_window`、`recursive`、`semantic` 三策略输出 ChunkSpan（局部 `start_offset`/`end_offset`），算法行为不变；验收：既有算法测试全部通过且 `chunking-strategies`「结果顺序与元数据归属」Scenario 通过
- [x] 4.3 改造 Semantic Provider 为按次注入协议（不在 Policy/IR/序列化中出现）；验收：「Semantic Provider 注入协议」Scenario 测试通过
- [x] 4.4 自定义 Chunker 注册条件为「符合协议、提供参数 Schema 并声明是否需要 Provider」；验收：「自定义 Chunker 注册」Scenario 测试通过

## 5. Compiler / IR

- [x] 5.1 实现 `ExecutionPlan`（Execution IR）：Policy 身份、`policy_hash`、按序层（索引/name/strategy/补全缺省的 params）、Metadata 字段解析计划、include 选项；验收：`policy-compiler`「编译产出 Execution IR」「IR 补全而非复制」Scenario 测试通过
- [x] 5.2 实现 Policy Hash：规范化模型（字段配置只输出实际声明的来源键，`value: null` 与 `source` 不混淆）→ 键排序 JSON → UTF-8 → sha256；验收：「Policy Hash 稳定」全部 Scenario 测试通过
- [x] 5.3 实现 IR 的 `model_dump()`/`model_dump_json()` 往返（正则分隔符可判别、无 Provider/可调用对象）；验收：「IR 可序列化且不含运行时对象」Scenario 测试通过

## 6. Runtime / Organization

- [x] 6.1 实现 Runtime 按 IR 执行：单层即平铺、多层逐父块下切、局部 Offset 换算全局、`chunk_id` 广度优先 `chunk-NNNN` 编号；验收：`chunk-organization`「单层 Pipeline 即平铺」「多层 Pipeline 执行」「组织元数据填充」「全局 Offset 换算」Scenario 测试通过
- [x] 6.2 实现终止行为：空输入空结果、分支无产出终止、不产生空 Chunk、不死循环；验收：「层级边界与终止行为」「子块边界约束」Scenario 测试通过
- [x] 6.3 语义校验接入执行路径：未注册策略、非法 params 在切块前报错（含层位置与参数名）；验收：`policy-engine`「语义校验」Scenario 测试通过

## 7. Metadata Builder

- [x] 7.1 实现按 `metadata.fields` 生成 `metadata`：`value` 固定值、`source` 经 Context 路径解析，所有层级相同字段集、独立副本；验收：「业务 Metadata 生成」Scenario 测试通过
- [x] 7.2 实现执行期校验：路径缺失或 `context=None` 报 `ContextResolutionError`（含字段名与路径，不返回部分结果）、值不可 JSON 序列化报错、未引用键不写入；验收：「Context 只提供值」「Context 路径缺失」「Context 值可序列化」Scenario 测试通过
- [x] 7.3 实现 include 复制语义：`include.organization` 控制 `parent_id`/`level`/`sequence`/`level_name` 四键、`include.strategy` 控制 `strategy`/`strategy_metadata` 两键是否复制进 `metadata`（独立副本），两者缺省 true，Chunk 属性始终完整保留；验收：「Metadata 输出选项」全部 Scenario 测试通过

## 8. 公共 API

- [x] 8.1 实现 `ChunkEngine.validate(policy)`/`compile(policy)`/`execute(text, policy, context=None, provider=None)`：execute 只接受 Policy 对象、内部自动校验编译、各类失败不返回部分结果；验收：`chunking-api`「统一公共入口」「执行入口」「validate 校验 Policy」Scenario 测试通过
- [x] 8.2 实现 `ChunkEngine.register(name, factory, *, params_model, requires_provider=False, replace=False)` 委托 Registry：按 `params_model` 校验并拒绝未定义键，`factory(params, provider)` 返回 Chunker，`requires_provider=True` 的策略缺 Provider 时在切块开始前报错；内置策略经同一机制注册（`semantic` 为 `requires_provider=True`）；验收：`chunking-api`「扩展入口」Scenario 测试通过
- [x] 8.3 实现执行追溯字段（`policy_id`/`policy_version`/`policy_hash`/`execution_id`/`engine_version`/`execution_time_ms`）；验收：「执行追溯信息」Scenario 测试通过
- [x] 8.4 移除旧公共 API：`engine.chunk()`、`FlatConfig`/`HierarchicalConfig`、`set_provider`、Custom 元数据参数、`tree()`；验收：全仓 grep 无残留引用，旧 API 调用报错
- [x] 8.5 导出新公共面 `Policy`、`ChunkEngine`、`Chunk`、`ChunkResult`、`Chunker`、`ExecutionPlan`；验收：`from chunkweave import ...` 可导入，`chunkweave.__version__` 可用

## 9. 测试与文档

- [x] 9.1 为每份 delta 中的全部 Scenario 建立对应测试，含安全解析拒绝不安全标签、保留键拒绝（含 include 全关）、include 复制语义、`requires_provider` 提前报错；验收：`openspec show refactor-to-policy-driven-engine --json --deltas-only` 的每个 Scenario 可映射到至少一个 pytest 用例，`pytest` 全绿
- [x] 9.2 迁移或删除绑定旧 API 的测试：`tests/test_flat.py`、`test_hierarchical.py`、`test_assembly.py`、`test_metadata.py`、`test_config.py`、`test_engine.py`；算法相关测试（`test_sliding_window`、`test_recursive`、`test_semantic`、`test_chunk`、`test_registry`、`test_errors`）改写到新接口，断言不得放宽；验收：`pytest` 全绿且无绑定旧 API 的测试残留
- [x] 9.3 移植 `benchmarks/bench.py`、`benchmarks/fingerprint.py` 到新 API；验收：`package-distribution`「可重复 Benchmark」满足
- [x] 9.4 更新文档：`README.md`、`docs/configuration.md`（Policy DSL 参考，提醒 YAML 隐式类型坑）、`docs/metadata.md`、`docs/organization/flat.md` 与 `hierarchical.md` 合并为一份多层组织文档；新增 ADR 标明替代 `0005-custom-inheritance` 与 `0006-flat-vs-hierarchical`，另新增 Policy DSL、Policy Hash、未知字段严格拒绝、include 语义的 ADR；写旧 API 迁移说明（对应 design 的映射表）；验收：`package-distribution`「文档可用性」Scenario 满足
- [x] 9.5 新建 `examples/policies/`（至少含 `novel.yaml`、`markdown.yaml`、`technical.yaml`，另加覆盖 6 个示例所需 Policy）并重写 6 个示例为 `Policy.from_file` + `execute`；验收：「示例可运行」Scenario 满足（6 示例逐一跑通，Semantic 用 Fake Provider）
- [x] 9.6 全量质量检查；验收：`ruff`、`mypy`、`pytest`、`python -m build`（wheel/sdist）全部通过

## Workflow follow-up

- HTTP Service（`POST /api/v1/chunks`）、`policy_ref` 与 Policy Governance 后台按设计 §12 在前十项完成后另开 Change 实施。
- 代码任务完成后经用户同意才归档本 Change；归档命令必须是 `openspec archive refactor-to-policy-driven-engine --skip-specs`——delta 已 sync 进正式 Spec，不加 `--skip-specs` 会重复应用 ADDED。
