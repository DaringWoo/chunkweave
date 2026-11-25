# Tasks

## 1. 元数据组装

- [x] 1.1 实现 `assembly.py` 统一组装函数：Common + Organization + Strategy + Custom 四组合入，Custom 逐块深拷贝，验证四组边界与冲突拒绝的单测通过
- [x] 1.2 实现 Custom 继承规则：引擎级 custom 传播全部后代、层级 `metadata` 近者覆盖、保留字段冲突配置期拒绝，验证三层继承与冲突单测通过

## 2. Flat 组织

- [x] 2.1 实现 `FlatOrganization`：单策略执行、平级输出、不写组织字段，验证三种策略（含 Fake Provider 的 semantic）平铺结果与元数据单测通过

## 3. Hierarchical 组织

- [x] 3.1 实现 `HierarchicalOrganization` 逐层下推：每父块独立作为下层输入（禁合并）、层级间局部 Offset 加 `parent.start_offset` 换算全局，验证两层 Parent-Child 与三层不同策略的 `parent_id`/`level`/`sequence` 单测通过
- [x] 3.2 实现边界行为：空输入、空 `levels` 拒绝、某层无结果分支终止、不可再细分、末层为叶、父层 overlap 允许重复覆盖，验证子块范围 ⊆ 父块范围及全局 Offset 的性质断言单测全部通过且无死循环

## 4. Tree View 与结果模型

- [x] 4.1 实现 `ChunkResult`（平铺集合按 Offset 序）与 `ChunkNode`/`tree()`（从 `parent_id` 现算嵌套结构），验证 Tree View 与 `parent_id` 关系一致的单测通过

## 5. 公共 API

- [x] 5.1 实现 `ChunkEngine`：`register`/`set_provider`/`chunk(config)`，Flat 与 Hierarchical 一键执行，未注册策略、缺 Provider 透出清晰异常，验证 API 层单测通过
- [x] 5.2 实现自定义 Chunker 在任意层按名引用、`ChunkResult`/`ChunkNode` 的 `to_dict`/`to_json` 序列化往返，验证等价性与 Tree 重建单测通过

## 6. 集成与质量门禁

- [x] 6.1 全量运行 `pytest`（覆盖 chunk-organization、chunking-api 两份规格全部 Scenario 及与既有策略的组合），全部通过
- [x] 6.2 `ruff check` 与 `mypy src` 通过，修复真实发现的问题（禁止删测试、弱化断言或静默跳过）
