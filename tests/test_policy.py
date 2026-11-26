"""Policy model: loading, structural validation, field-name rules."""

import pytest
import yaml
from pydantic import ValidationError

from chunkweave import Policy, PolicyLoadError, PolicyValidationError
from chunkweave.policy import MetadataFieldConfig

MINIMAL = """\
api_version: chunkweave/v1
policy:
  id: p1
  name: test
  version: 1.0.0
pipeline:
  levels:
    - name: l0
      strategy: sliding_window
      params:
        chunk_size: 500
"""

# ---- 顶层结构 ----


def test_minimal_policy_valid():
    p = Policy.from_yaml(MINIMAL)
    assert p.id == "p1"
    assert p.name == "test"
    assert p.version == "1.0.0"
    assert p.metadata.fields == {}
    assert p.metadata.include.strategy is True
    assert p.metadata.include.organization is True


@pytest.mark.parametrize("key", ["id", "name", "version"])
def test_missing_identity_field(key):
    doc = """\
api_version: chunkweave/v1
policy:
  id: p1
  name: t
  version: 1.0.0
pipeline:
  levels: [{name: l0, strategy: x}]
"""
    lines = [
        ln
        for ln in doc.splitlines()
        if not ln.strip().startswith(f"{key}:")
    ]
    with pytest.raises(PolicyValidationError) as exc:
        Policy.from_yaml("\n".join(lines))
    assert f"policy.{key}" in str(exc.value)


@pytest.mark.parametrize("key", ["id", "name", "version"])
def test_empty_identity_field(key):
    data = {
        "api_version": "chunkweave/v1",
        "policy": {"id": "p1", "name": "t", "version": "1.0.0"},
        "pipeline": {"levels": [{"name": "l0", "strategy": "x"}]},
    }
    data["policy"][key] = ""
    with pytest.raises(PolicyValidationError):
        Policy.from_yaml(yaml.safe_dump(data))


def test_wrong_api_version():
    doc = MINIMAL.replace("chunkweave/v1", "chunkweave/v2")
    with pytest.raises(PolicyValidationError) as exc:
        Policy.from_yaml(doc)
    assert "chunkweave/v1" in str(exc.value)


def test_missing_api_version():
    with pytest.raises(PolicyValidationError) as exc:
        Policy.from_yaml(MINIMAL.replace("api_version: chunkweave/v1\n", ""))
    assert "api_version" in str(exc.value)


# ---- 加载 ----


def test_from_file(tmp_path):
    f = tmp_path / "p.yaml"
    f.write_text(MINIMAL, encoding="utf-8")
    p = Policy.from_file(f)
    assert p.id == "p1"


def test_from_file_missing(tmp_path):
    with pytest.raises(PolicyLoadError):
        Policy.from_file(tmp_path / "nope.yaml")


def test_from_file_reads_utf8(tmp_path):
    f = tmp_path / "p.yaml"
    f.write_text(MINIMAL.replace("test", "测试策略"), encoding="utf-8")
    assert Policy.from_file(str(f)).name == "测试策略"


def test_yaml_syntax_error():
    with pytest.raises(PolicyLoadError):
        Policy.from_yaml("a: [unclosed\nb: : :\n")


def test_root_not_mapping():
    with pytest.raises(PolicyLoadError):
        Policy.from_yaml("- just\n- a\n- list\n")


def test_empty_document_is_load_error():
    with pytest.raises(PolicyLoadError):
        Policy.from_yaml("")


def test_unsafe_tag_rejected():
    doc = """\
api_version: !!python/object/apply:os.system ["echo hi"]
policy: {id: p1, name: t, version: 1.0.0}
pipeline: {levels: [{name: l0, strategy: x}]}
"""
    with pytest.raises(PolicyLoadError):
        Policy.from_yaml(doc)


# ---- 对象访问 ----


def test_attribute_access():
    p = Policy.from_yaml(MINIMAL)
    assert p.policy.id == "p1"
    assert p.policy.name == "test"
    assert p.pipeline.levels[0].name == "l0"
    assert p.pipeline.levels[0].params == {"chunk_size": 500}
    assert p.metadata.fields == {}


# ---- pipeline.levels ----


def test_empty_levels_rejected():
    doc = """\
api_version: chunkweave/v1
policy: {id: p1, name: t, version: 1.0.0}
pipeline: {levels: []}
"""
    with pytest.raises(PolicyValidationError) as exc:
        Policy.from_yaml(doc)
    assert "pipeline.levels" in str(exc.value)


def test_missing_levels_rejected():
    doc = """\
api_version: chunkweave/v1
policy: {id: p1, name: t, version: 1.0.0}
pipeline: {}
"""
    with pytest.raises(PolicyValidationError) as exc:
        Policy.from_yaml(doc)
    assert "pipeline.levels" in str(exc.value)


def test_level_missing_params_defaults_to_empty():
    doc = """\
api_version: chunkweave/v1
policy: {id: p1, name: t, version: 1.0.0}
pipeline:
  levels:
    - {name: l0, strategy: sliding_window}
    - {name: l1, strategy: recursive, params: {chunk_size: 10}}
"""
    p = Policy.from_yaml(doc)
    assert p.pipeline.levels[0].params == {}
    assert p.pipeline.levels[1].params == {"chunk_size": 10}


def test_field_path_in_error():
    doc = """\
api_version: chunkweave/v1
policy: {id: p1, name: t, version: 1.0.0}
pipeline:
  levels:
    - {name: l0, strategy: a}
    - {name: l1}
"""
    with pytest.raises(PolicyValidationError) as exc:
        Policy.from_yaml(doc)
    assert "pipeline.levels[1].strategy" in str(exc.value)


def test_non_string_strategy_type_rejected():
    doc = """\
api_version: chunkweave/v1
policy: {id: p1, name: t, version: 1.0.0}
pipeline:
  levels:
    - {name: l0, strategy: 123}
"""
    with pytest.raises(PolicyValidationError) as exc:
        Policy.from_yaml(doc)
    assert "pipeline.levels[0].strategy" in str(exc.value)


# ---- 未知字段拒绝 ----


def test_unknown_top_level_key():
    doc = MINIMAL + "bogus: 1\n"
    with pytest.raises(PolicyValidationError) as exc:
        Policy.from_yaml(doc)
    assert "bogus" in str(exc.value)


def test_unknown_policy_key():
    doc = MINIMAL.replace("  version: 1.0.0\n", "  version: 1.0.0\n  extra: x\n")
    with pytest.raises(PolicyValidationError) as exc:
        Policy.from_yaml(doc)
    assert "policy.extra" in str(exc.value)


def test_unknown_pipeline_key():
    doc = MINIMAL.replace("pipeline:\n", "pipeline:\n  bogus: 1\n")
    with pytest.raises(PolicyValidationError) as exc:
        Policy.from_yaml(doc)
    assert "pipeline.bogus" in str(exc.value)


def test_unknown_level_key():
    doc = MINIMAL.replace(
        "    - name: l0\n", "    - name: l0\n      bogus: 1\n"
    )
    with pytest.raises(PolicyValidationError) as exc:
        Policy.from_yaml(doc)
    assert "pipeline.levels[0].bogus" in str(exc.value)


def test_unknown_metadata_key():
    doc = MINIMAL + "metadata:\n  bogus: 1\n"
    with pytest.raises(PolicyValidationError) as exc:
        Policy.from_yaml(doc)
    assert "metadata.bogus" in str(exc.value)


def test_unknown_include_key():
    doc = MINIMAL + "metadata:\n  include:\n    bogus: true\n"
    with pytest.raises(PolicyValidationError) as exc:
        Policy.from_yaml(doc)
    assert "metadata.include.bogus" in str(exc.value)


def test_unknown_field_config_key():
    doc = MINIMAL + """\
metadata:
  fields:
    k: {value: 1, bogus: 2}
"""
    with pytest.raises(PolicyValidationError) as exc:
        Policy.from_yaml(doc)
    assert "metadata.fields.k.bogus" in str(exc.value)


def test_value_mapping_content_not_constrained():
    doc = MINIMAL + """\
metadata:
  fields:
    nested: {value: {any: {deep: keys}}}
"""
    p = Policy.from_yaml(doc)
    assert p.metadata.fields["nested"].value == {"any": {"deep": "keys"}}


# ---- 版本格式 ----


@pytest.mark.parametrize("version", ["1.0", "v1.0.0", "1.0.0.1", "latest", "1.0.0a"])
def test_bad_version_format(version):
    doc = MINIMAL.replace("version: 1.0.0", f"version: {version}")
    with pytest.raises(PolicyValidationError) as exc:
        Policy.from_yaml(doc)
    assert "version" in str(exc.value)


def test_version_parsed_as_float_rejected():
    doc = MINIMAL.replace("version: 1.0.0", "version: 1.0")
    with pytest.raises(PolicyValidationError):
        Policy.from_yaml(doc)


# ---- metadata.fields ----


def test_neither_value_nor_source():
    doc = MINIMAL + "metadata:\n  fields:\n    k: {}\n"
    with pytest.raises(PolicyValidationError) as exc:
        Policy.from_yaml(doc)
    assert "metadata.fields.k" in str(exc.value)


def test_both_value_and_source():
    doc = MINIMAL + "metadata:\n  fields:\n    k: {value: 1, source: context.a}\n"
    with pytest.raises(PolicyValidationError):
        Policy.from_yaml(doc)


def test_source_null_rejected():
    doc = MINIMAL + "metadata:\n  fields:\n    k: {source: null}\n"
    with pytest.raises(PolicyValidationError):
        Policy.from_yaml(doc)


def test_value_null_is_declared():
    doc = MINIMAL + "metadata:\n  fields:\n    k: {value: null}\n"
    p = Policy.from_yaml(doc)
    f = p.metadata.fields["k"]
    assert f.is_fixed
    assert not f.is_context
    assert f.value is None


def test_source_valid():
    doc = MINIMAL + "metadata:\n  fields:\n    k: {source: context.doc.author}\n"
    p = Policy.from_yaml(doc)
    f = p.metadata.fields["k"]
    assert f.is_context
    assert f.source == "context.doc.author"


@pytest.mark.parametrize(
    "src",
    ["context", "ctx.a", "context.", "context..a", "context.a b", "context.a. b", 123],
)
def test_source_invalid_syntax(src):
    doc = MINIMAL + f'metadata:\n  fields:\n    k: {{source: "{src}"}}\n'
    with pytest.raises((PolicyValidationError, ValidationError)):
        Policy.from_yaml(doc)


def test_value_not_json_serializable():
    data = {
        "api_version": "chunkweave/v1",
        "policy": {"id": "p", "name": "n", "version": "1.0.0"},
        "pipeline": {"levels": [{"name": "l", "strategy": "s"}]},
        "metadata": {"fields": {"k": {"value": object()}}},
    }
    with pytest.raises(ValidationError):
        Policy.model_validate(data)


def test_field_config_roundtrip_distinguishes_null_value():
    fixed = MetadataFieldConfig.model_validate({"value": None})
    sourced = MetadataFieldConfig.model_validate({"source": "context.a"})
    assert fixed.model_dump() == {"value": None}
    assert sourced.model_dump() == {"source": "context.a"}
    assert MetadataFieldConfig.model_validate(fixed.model_dump()) == fixed
    assert MetadataFieldConfig.model_validate(sourced.model_dump()) == sourced


# ---- include ----


def test_include_explicit_values():
    doc = MINIMAL + "metadata:\n  include: {strategy: false, organization: true}\n"
    p = Policy.from_yaml(doc)
    assert p.metadata.include.strategy is False
    assert p.metadata.include.organization is True


@pytest.mark.parametrize("val", ["1", "'x'", "0.5"])
def test_include_non_bool_rejected(val):
    doc = MINIMAL + f"metadata:\n  include: {{strategy: {val}}}\n"
    with pytest.raises(PolicyValidationError):
        Policy.from_yaml(doc)


# ---- 保留键 ----


@pytest.mark.parametrize(
    "key",
    [
        "chunk_id",
        "content",
        "parent_id",
        "level",
        "sequence",
        "start_offset",
        "end_offset",
        "strategy",
        "strategy_metadata",
        "metadata",
        "level_name",
    ],
)
def test_reserved_field_name_rejected(key):
    doc = MINIMAL + f"metadata:\n  fields:\n    {key}: {{value: 1}}\n"
    with pytest.raises(PolicyValidationError) as exc:
        Policy.from_yaml(doc)
    assert key in str(exc.value)


def test_reserved_key_rejected_even_with_include_off():
    doc = MINIMAL + """\
metadata:
  fields:
    parent_id: {value: 1}
  include: {strategy: false, organization: false}
"""
    with pytest.raises(PolicyValidationError):
        Policy.from_yaml(doc)


def test_empty_field_name_rejected():
    doc = MINIMAL + "metadata:\n  fields:\n    '': {value: 1}\n"
    with pytest.raises(PolicyValidationError):
        Policy.from_yaml(doc)


# ---- 序列化往返 ----


def test_model_dump_roundtrip():
    doc = MINIMAL + """\
metadata:
  fields:
    author: {source: context.doc.author}
    kind: {value: 技术}
    empty: {value: null}
  include: {strategy: false}
"""
    p = Policy.from_yaml(doc)
    dumped = p.model_dump()
    p2 = Policy.model_validate(dumped)
    assert p2.model_dump() == dumped
    assert p2.metadata.fields["author"].is_context
    assert p2.metadata.fields["empty"].is_fixed
    assert p2.metadata.fields["empty"].value is None


def test_model_dump_with_regex_params_roundtrip():
    doc = """\
api_version: chunkweave/v1
policy: {id: p1, name: t, version: 1.0.0}
pipeline:
  levels:
    - name: l0
      strategy: recursive
      params:
        chunk_size: 100
        separators: ["\\n\\n", {value: "第[一二三四]+章", regex: true}]
"""
    p = Policy.from_yaml(doc)
    dumped = p.model_dump()
    p2 = Policy.model_validate(dumped)
    assert p2.pipeline.levels[0].params == p.pipeline.levels[0].params
    assert p2.model_dump() == dumped
