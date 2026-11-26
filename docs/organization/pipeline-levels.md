# Pipeline 层级组织

`pipeline.levels` 是唯一的组织方式：一个有序层级列表，每层声明自己的
`name`、`strategy` 与 `params`。一层即平铺，两层即父子，N 层即多级——
父子不是独立的组织类型。

```yaml
pipeline:
  levels:
    - name: chapter
      strategy: recursive
      params: {chunk_size: 5000}
    - name: event
      strategy: semantic
      params: {threshold: 0.8, chunk_size: 1000}
    - name: detail
      strategy: sliding_window
      params: {chunk_size: 300, overlap: 50}
```

## 执行规则

1. 第 0 层对整个输入文本切块。
2. 第 i 层（i ≥ 1）对上一层**每个** Chunk 的 `content` 逐个独立切块——
   父块在下切前不会先合并。
3. 子块全局 Offset = 子 span 局部 Offset + 父块 `start_offset`；
   `content == text[start_offset:end_offset]` 恒成立，子块不越父界。
4. 父块 overlap 允许子块覆盖同一段文本。
5. `content` 为空的 span 被丢弃，`chunk_id` 编号只计保留的 span；
   某父块没有子块时该分支终止（策略无法继续切分时该分支自然终止）。
6. 空输入得到空结果；空 `levels` 在加载时被拒绝；单层合法。

## 组织字段

Runtime 写入，不由策略负责：

- `parent_id`：父块 `chunk_id`，第 0 层为 `None`。
- `level`：0 起层级序号。
- `sequence`：同一父块内（第 0 层为根块之间）从 0 连续编号。
- `level_name`：所在层 `name`，仅经 `include.organization` 复制进
  `metadata`，不是 Chunk 属性。

`chunk_id` 按广度优先重新编号为 `chunk-NNNN`，保证全局唯一且确定。

## 结果顺序

`result.chunks` 按 `(start_offset, level)` 稳定排序：同起点的父块排在
子块之前。排序由 Runtime 完成，`ChunkResult` 模型本身不排序。

## 层级视图

层级关系只由 `parent_id` 表达；需要树形视图时按 `parent_id` 自行
重建（几行代码即可），扁平列表是唯一事实来源。

参见 `examples/two_level_recursive_sliding.py` 与
`examples/three_level_recursive_semantic_sliding.py`。
