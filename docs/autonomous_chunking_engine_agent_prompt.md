# Autonomous Agent Prompt：RAG Chunking Engine

你是一名资深 Python
架构师和测试工程师。请在当前工作区中，独立设计、实现、测试并整理一个可安装、可扩展、可发布到
PyPI 的 Python
文本切块与组织引擎。必须实际修改代码、运行测试、修复问题并交付，不要只输出计划。

## 0. 无人值守执行规则

1.  先检查仓库、目录、Git 状态、Python 版本、已有约定和用户修改。
2.  有现有项目时在其基础上演进；空仓库才初始化。不得覆盖或删除未检查的用户文件。
3.  不向用户提问等待确认。非关键歧义自行选择简单、可维护的方案，并在
    `docs/decisions/` 记录 ADR。
4.  每个阶段完成后运行测试，再继续。不能只凭代码阅读声称测试通过。
5.  不得读取、输出或提交密钥、Token、`.env` 等秘密。
6.  不得 `git push`、发布 PyPI、创建远端 Release 或执行破坏性 Git 操作。
7.  不得删除测试、降低断言、跳过失败或伪造测试/Benchmark 结果。
8.  遇到阻塞先尝试替代方案；无法安全继续时，记录原因、影响和已完成部分。

本文定义的产品模型是约束。可以完善实现细节，不得擅自增加核心算法或组织方式，也不得扩大职责。

## 1. 项目定位与职责边界

项目是独立的 **Chunking Engine（文本切块与组织引擎）**，只负责： -
按指定策略切分输入文本； - 按指定组织方式组织 Chunk； - 维护 Chunk
关系； - 生成统一 Chunk 结果和元数据。

输入是 Python 字符串及配置，输出是 Chunk 集合或层级结构。

明确不负责： - PDF、DOCX、PPTX、HTML 等文件解析； -
OCR、文本清洗、预处理； - 文件上传、文档加载器； - Embedding
模型托管、模型下载和模型管理； - 检索用向量生成流水线； -
Milvus、Qdrant、Chroma 等向量数据库； - BM25、Dense/Hybrid
Retrieval、RRF、Reranker、Query Rewrite； - Web UI 或完整 RAG 应用。

**Semantic 的边界：**语义切块需要相似度/Embedding
能力来判断边界。只定义轻量协议或回调，由调用方注入；不管理模型、不存储向量、不强制依赖大型模型库。语义切块内部用于边界判断的临时向量，不等于供检索入库的最终向量。

## 2. 已确定的核心模型

两个独立维度： - **Organization**：Chunk 之间如何组织。 - **Chunking
Strategy**：文本如何切分。

二者必须解耦、可组合。

### 2.1 组织方式：只有两种

**Flat（平铺）** - 所有 Chunk 平级，不建立父子关系。 - 输出平铺 Chunk
集合。 - 不强制携带 `parent_id`、`level` 等无意义层级字段。

**Hierarchical（层级）** - 支持 N 层，不限制为两层。 -
每层独立配置切块策略和参数。 - 当前层产生的每个 Chunk
分别作为下一层输入范围。 - 子层不得越过父 Chunk 的文本范围。 -
Parent-Child 是只有两层的 Hierarchical 特例，不是第三种组织方式。

### 2.2 切块方式：只有三种

**A. Sliding Window（滑动窗口）**

核心参数： - `chunk_size` - `overlap`

语义约定： - `overlap = 0` 即固定长度切块，不另设 FixedSize 算法。 -
`overlap > 0` 产生重叠窗口。 - 校验 `0 <= overlap < chunk_size`。 -
确保窗口始终前进，不产生死循环。 - 明确长度单位与 Offset 语义。

**B. Recursive（符号递归）**

按分隔符优先级逐级切分；上一级结果仍不满足长度约束时，继续使用更细粒度分隔符。

示例：

``` python
separators = ["\\n\\n", "\\n", "。", "！", "？", "；", "，", ""]
```

要求： - 支持普通字符串和正则表达式分隔符； - 支持优先级、长度约束； -
支持必要的 Overlap，但不强制所有算法共用无意义参数； -
明确分隔符保留、删除、归属前块/后块规则； - 明确空分隔符/字符兜底； -
处理无匹配、超长原子片段、空规则； - 不允许无限递归或死循环。

句子、段落、标题等切分都通过 Recursive 的分隔符规则实现，不另设
Sentence、Paragraph、Structural 等核心算法。

**C. Semantic（语义切块）**

根据语义变化判断边界。

参数可包括： - 注入的语义计算接口； - `threshold`； - `chunk_size` /
最大长度约束； - 确有必要的窗口参数。

要求： - 定义清晰的注入协议； - 不绑定厂商或模型； - 不强制下载模型； -
核心安装不依赖大型模型库； -
最大长度必须可靠，语义边界超长时要有二次切分/兜底； -
明确阈值含义、算法、异常行为并测试； - 不把临时 Embedding 当作检索向量。

## 3. 层级配置与执行

Hierarchical 中每层独立配置策略。例如：

``` python
config = {
    "organization": "hierarchical",
    "levels": [
        {
            "name": "chapter",
            "strategy": "recursive",
            "config": {"chunk_size": 5000, "separators": ["章节正则", "\\n\\n"]}
        },
        {
            "name": "event",
            "strategy": "semantic",
            "config": {"chunk_size": 1000, "threshold": 0.8}
        },
        {
            "name": "detail",
            "strategy": "sliding_window",
            "config": {"chunk_size": 300, "overlap": 50}
        }
    ]
}
```

执行规则： 1. 输入文本进入第一层； 2. 第一层按自身配置切分； 3. 每个生成
Chunk 独立成为下一层的输入范围； 4. 下一层对每个父 Chunk 分别执行； 5.
按配置持续到最后一层； 6. 建立组织关系并组装元数据。

禁止把上一层所有 Chunk 合并后再切下一层。子 Chunk 不得跨越父 Chunk
边界。父层有 Overlap
时，不同父节点的子节点可能覆盖相同原文范围，这是允许的。

必须定义并测试：空输入、空层级、单层配置、某层无结果、Chunk
无法继续细分、层级深度和最后一层行为。Flat 只需单策略配置，不强制提供
levels。

## 4. Chunk 与元数据模型

元数据由四组构成：

`Metadata = Common + Organization + Strategy + Custom`

**Common Metadata**：描述 Chunk 本身，例如： - `chunk_id` - `content` -
`start_offset` - `end_offset`

**Organization Metadata**：由组织方式决定。Hierarchical 至少考虑： -
`parent_id` - `level` - `sequence`

Flat 不强制包含层级字段。明确根节点 parent 表示、level 从 0/1
开始、sequence 编号方式、子节点查询方式。

**Strategy Metadata**：由策略动态提供，例如： - Sliding
Window：`window_index`、`overlap_size` -
Recursive：`separator_used`、`separator_level` -
Semantic：`boundary_score`

只生成有真实意义的字段，避免策略之间字段冲突。

**Custom Metadata**： - 调用方传入； - 引擎原样保留，不解释业务含义； -
明确层级模式下向子 Chunk 继承的规则； -
保留字段冲突必须拒绝或明确处理，不可静默覆盖； - 避免多个 Chunk
意外共享可变字典。

Offset 约定： - 使用 Python 字符串索引语义（Unicode 码点索引）； -
采用左闭右开区间 `[start_offset, end_offset)`； - 所有层级 Offset
最终相对于最初输入文本； - 子层局部 Offset 必须正确转换为全局 Offset； -
Token 数与字符 Offset 是不同概念； - 测试中文、Emoji 和组合字符。

统一 Chunk 结果模型，不要每种策略返回互不兼容的类型。可采用 dataclass
或其他轻量模型。策略只产出切分结果和 Strategy Metadata，不得设置
`parent_id`、`level` 等组织字段。组织层负责这些字段。

## 5. 架构要求

至少分离以下职责：

**Strategy Layer** - Sliding Window Chunker - Recursive Chunker -
Semantic Chunker - 统一输入/输出协议，但不强迫共享所有参数。 -
单独可测，不依赖 Organization。

**Strategy Registry** - 注册内置三种策略； - 支持用户注册自定义
Chunker； - 未注册策略给出清晰异常； - 明确名称冲突行为； -
不负责层级组织。

**Organization Layer** - Flat； - Hierarchical； - 通过 Registry 获取
Chunker； - 负责层级执行、关系建立、Offset 转换、Organization
Metadata； - 不依赖具体语义 Provider。

**Metadata Assembly** - 统一组装
Common、Organization、Strategy、Custom； -
不把元数据逻辑散落到每个算法中。

**Public API** 至少支持： - Flat + 指定策略； - Hierarchical +
多层策略配置； - 注册自定义 Chunker； - 注入 Semantic Provider； -
获取平铺 Chunk 集合； - 获取/构建 Tree View； -
配置和结果序列化（合理时）。

API 名称由你设计，但保持一致、易用并写入 README。

## 6. 工程质量

-   优先沿用仓库已有 Python
    版本和工具链；空仓库选择合理且广泛可用的版本并记录。
-   使用现代类型标注、清晰命名和 Docstring。
-   核心依赖轻量；不依赖完整 RAG 框架。
-   Semantic 依赖可选或注入。
-   Chonkie、LlamaIndex 是设计参考，不是运行时依赖。
-   不复制其大段源码；独立实现并遵守许可证。
-   避免巨型类、超长函数、隐式全局状态和过度继承。
-   公开 API 有类型标注；异常清晰，不吞异常。
-   优先 pytest、Ruff；按项目情况使用 mypy 或 pyright。
-   先检查现有工具链，不无理由替换。

## 7. 必须测试的行为

### Sliding Window

-   overlap=0、正常重叠、最大合法重叠、非法 overlap；
-   文本短于/等于/长于窗口；
-   最后窗口、空文本；
-   中文、Emoji、Offset。

### Recursive

-   多级分隔符、正则、标题正则、优先级；
-   分隔符保留/归属；
-   最后一段无分隔符、无匹配、空分隔符；
-   超长原子片段、Overlap、空文本；
-   Unicode Offset；
-   无死循环。

### Semantic

-   使用确定性 Fake Provider 测试，不下载真实模型；
-   相似文本与主题变化；
-   threshold 边界；
-   文本不足以比较；
-   最大长度兜底；
-   Provider 异常；
-   未配置 Provider 时错误清晰。

### Flat

-   三种策略均可执行；
-   平级关系正确；
-   不产生无意义层级字段；
-   顺序和 Metadata 正确。

### Hierarchical

-   两层 Parent-Child 特例；
-   三层及以上；
-   每层不同策略；
-   每个父块分别执行下一层；
-   子块不越过父范围；
-   Parent ID、Level、Sequence 正确；
-   局部 Offset 转全局 Offset 正确；
-   父层 Overlap 导致的重复覆盖；
-   空层级和不可继续切分；
-   Custom Metadata 继承规则。

### Metadata 与属性测试

-   四组边界清楚；
-   策略和组织元数据动态生成；
-   Custom 不覆盖保留字段；
-   不共享意外可变对象；
-   JSON 序列化稳定；
-   Offset 不越界；
-   子范围不越过父范围；
-   输出顺序稳定；
-   非法配置快速失败。

测试必须验证实际行为，不可只测实例化。不得删除测试或弱化断言来让测试通过。

## 8. 文档与示例

至少交付： - `README.md` - `docs/design.md` - `docs/configuration.md` -
`docs/algorithms/sliding-window.md` - `docs/algorithms/recursive.md` -
`docs/algorithms/semantic.md` - `docs/organization/flat.md` -
`docs/organization/hierarchical.md` - `docs/metadata.md` -
`docs/decisions/`（ADR） - `examples/`

示例至少包括： 1. Flat + Sliding Window； 2. Flat +
Recursive（中文分隔符和正则）； 3. Flat + Semantic（Fake
Provider，不下载模型）； 4. Hierarchical：Recursive → Sliding Window；
5. Hierarchical：Recursive → Semantic → Sliding Window； 6. 自定义
Chunker 注册。

示例必须与真实 API 一致，并尽可能实际运行。

## 9. 性能

-   避免不必要的重复字符串扫描和 Token 计算；
-   Semantic 考虑批量相似度/Embedding 计算，避免逐句远程请求；
-   大文本避免不必要的完整副本；
-   正确性和可读性优先于微小优化；
-   提供可重复 Benchmark，说明环境、输入规模和参数；
-   不要求第一版并行或分布式执行；
-   不得编造性能数据。

## 10. 打包与发布准备

-   完善 `pyproject.toml`；
-   配置包元信息、版本、许可证等，不伪造作者身份；
-   构建 wheel 和 sdist；
-   检查依赖和包内容；
-   提供本地安装说明；
-   配置 CI：Lint、类型检查、测试、构建。

只准备发布，不得实际上传 PyPI 或创建远端 Release。

## 11. 实施阶段

按阶段自主执行，每阶段结束运行测试和自检。

**Phase 0：仓库检查** - 检查目录、Git 状态、Python 环境和现有约定； -
输出仓库现状、计划、风险； - 确保不覆盖用户修改。

**Phase 1：数据模型与配置** - Chunk； - 四组 Metadata； -
Flat/Hierarchical 配置； - 三种策略配置和校验； - 序列化测试。

**Phase 2：策略接口与 Registry** - Base Protocol/ABC； - Registry； -
自定义策略注册； - 统一策略结果。

**Phase 3：三种算法** 依次实现 Sliding
Window、Recursive、Semantic；每种完成测试和文档后再进入下一种。

**Phase 4：组织方式** 先 Flat，再
Hierarchical。重点验证多层执行、不同策略组合、父子关系、全局 Offset 和
Metadata。

**Phase 5：公共 API 与集成** 完成统一入口和全部组合示例。

**Phase 6：质量**
全量测试、Lint、类型检查、边界测试、构建；修复实际发现的问题。

**Phase 7：文档与发布准备** 完成文档、Benchmark、CI、wheel 和 sdist。

不要停留在计划阶段，不要等待用户逐阶段确认。

## 12. 最终验收标准

功能： - \[ \] Flat 可用； - \[ \] Hierarchical 支持 N 层； - \[ \]
Parent-Child 是两层层级特例； - \[ \] Sliding Window 可用，overlap=0
等价固定长度； - \[ \] Recursive 支持多级分隔符、正则和长度约束； - \[
\] Semantic 支持注入式 Provider，不强制下载模型； - \[ \]
每层独立配置策略和参数； - \[ \] 四组 Metadata 正确组装； - \[ \] Offset
可追溯到原始输入； - \[ \] 可注册自定义 Chunker； - \[ \]
结果可稳定序列化。

工程： - \[ \] 职责边界未被破坏； - \[ \] 核心依赖轻量； - \[ \]
单元和集成测试通过； - \[ \] Ruff 通过； - \[ \]
类型检查通过或记录合理例外； - \[ \] 示例可运行； - \[ \] 文档与 API
一致； - \[ \] wheel 和 sdist 成功构建； - \[ \] CI 可用； - \[ \]
没有虚构测试或性能结果。

## 13. 最终交付报告

生成 `IMPLEMENTATION_REPORT.md`，真实记录： 1. 最终目录结构； 2.
功能与模块； 3. 架构说明； 4. 各算法和参数； 5. Flat/Hierarchical
执行机制； 6. Metadata 示例； 7. 测试命令、实际数量、通过/失败结果； 8.
Ruff 和类型检查结果； 9. 构建结果； 10. 示例运行结果； 11. Benchmark
环境和结果； 12. 未实现内容与已知限制； 13. 安装、运行和二次开发说明；
14. 后续版本建议。

所有数字必须来自真实执行结果。未完成的内容必须如实标注。

## 14. 开始执行

现在检查工作区，开始 Phase
0，并持续完成后续阶段。最终目标是交付一个**职责边界清楚、算法与组织解耦、可测试、可扩展、可安装的
Python Chunking Engine**，而不是只生成一份看起来完整的代码。
