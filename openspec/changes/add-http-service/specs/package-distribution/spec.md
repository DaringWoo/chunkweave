## MODIFIED Requirements

### Requirement: 可选依赖边界

Semantic Provider 相关扩展 MUST 以可选依赖（extras）或零依赖方式提供；不安装可选项时核心功能全部可用。HTTP 服务 MUST 经可选依赖 `server` 提供：核心安装 MUST NOT 包含 HTTP 框架；未安装 `server` 时 `import chunkweave` 正常，`import chunkweave.server` MUST 抛出带安装提示的 `ImportError`。

#### Scenario: 无可选依赖的核心功能

- **WHEN** 仅安装核心包且不装任何 extras
- **THEN** 单层与多层 Policy 及非 Semantic 策略全部可用；Semantic 在未注入 Provider 时给出清晰异常

#### Scenario: 未安装 server 时导入提示

- **WHEN** 仅安装核心包并尝试 `import chunkweave.server`
- **THEN** 抛出 `ImportError`，消息提示安装 `chunkweave[server]`

### Requirement: 文档可用性

项目 MUST 交付：`README.md`、`docs/design.md`、`docs/configuration.md`（Policy YAML DSL 参考，覆盖 `api_version`、`policy`、`pipeline.levels`、`params`、`metadata.fields`/`include`）、三种算法文档、多层组织文档（`pipeline.levels`）、`docs/metadata.md`（`value`/`source` 与 Context 的职责划分）、`docs/http-service.md`（接口、请求与响应示例、错误表、`create_app` 参数、启动方式）与 `docs/decisions/` ADR；文档描述的 API、参数与行为 MUST 与实际实现一致。

#### Scenario: 文档与实现一致

- **WHEN** 按文档中的 API 名称与参数示例调用
- **THEN** 调用成功且行为与文档描述一致
