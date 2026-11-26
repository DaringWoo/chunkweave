"""Compiler: ExecutionPlan content, semantic checks, Policy Hash stability."""

import re

import pytest

from chunkweave import (
    ExecutionPlan,
    Policy,
    PolicyValidationError,
    Registry,
    UnregisteredStrategyError,
)
from chunkweave.compiler import compile_policy, policy_hash
from conftest import make_policy


def compile_it(policy):
    return compile_policy(policy, Registry())


# ---- IR content ----


def test_plan_holds_identity_and_levels():
    policy = make_policy(
        [
            {"name": "章节", "strategy": "recursive",
             "params": {"chunk_size": 100}},
            {"name": "窗", "strategy": "sliding_window",
             "params": {"chunk_size": 20, "overlap": 5}},
        ],
        fields={"kind": {"value": "x"}},
    )
    plan = compile_it(policy)
    assert isinstance(plan, ExecutionPlan)
    assert plan.api_version == "chunkweave/v1"
    assert plan.policy_id == "test-policy"
    assert plan.policy_name == "test"
    assert plan.policy_version == "1.0.0"
    assert [lv.index for lv in plan.levels] == [0, 1]
    assert [lv.name for lv in plan.levels] == ["章节", "窗"]
    assert [lv.strategy for lv in plan.levels] == ["recursive", "sliding_window"]


def test_plan_params_defaults_filled():
    policy = make_policy([
        {"name": "l0", "strategy": "sliding_window", "params": {"chunk_size": 10}}
    ])
    plan = compile_it(policy)
    # overlap default filled in (not copied verbatim from declaration)
    assert plan.levels[0].params == {"chunk_size": 10, "overlap": 0}


def test_plan_level_requires_provider():
    policy = make_policy([
        {"name": "l0", "strategy": "semantic",
         "params": {"threshold": 0.5, "chunk_size": 10}}
    ])
    plan = compile_it(policy)
    assert plan.levels[0].requires_provider is True
    policy2 = make_policy([
        {"name": "l0", "strategy": "sliding_window", "params": {"chunk_size": 1}}
    ])
    assert compile_it(policy2).levels[0].requires_provider is False


def test_plan_metadata_fields():
    policy = make_policy(
        [{"name": "l0", "strategy": "sliding_window", "params": {"chunk_size": 4}}],
        fields={
            "kind": {"value": "doc"},
            "author": {"source": "context.doc.author"},
            "deep": {"source": "context.a.b.c"},
        },
        include={"strategy": False},
    )
    plan = compile_it(policy)
    by_name = {f.name: f for f in plan.metadata_fields}
    assert by_name["kind"].kind == "value"
    assert by_name["kind"].value == "doc"
    assert by_name["author"].kind == "source"
    assert by_name["author"].path == ["doc", "author"]
    assert by_name["deep"].path == ["a", "b", "c"]
    assert plan.include_strategy is False
    assert plan.include_organization is True


def test_compile_needs_no_text_context_or_provider():
    policy = make_policy([
        {"name": "l0", "strategy": "semantic",
         "params": {"threshold": 0.5, "chunk_size": 10}}
    ])
    plan = compile_it(policy)  # no provider needed to compile
    assert plan.levels[0].strategy == "semantic"


def test_ir_serializable_roundtrip_with_regex():
    policy = make_policy(
        [
            {"name": "l0", "strategy": "recursive",
             "params": {"chunk_size": 100,
                        "separators": ["\n\n",
                                       {"value": r"第[一二三四]+章", "regex": True}]}},
        ],
        fields={"k": {"value": {"nested": [1, 2]}}, "s": {"source": "context.a"}},
    )
    plan = compile_it(policy)
    restored = ExecutionPlan.model_validate_json(plan.model_dump_json())
    assert restored == plan
    # regex separator kept in discriminable declared form
    sep = restored.levels[0].params["separators"][1]
    assert sep == {"value": r"第[一二三四]+章", "regex": True}
    # no runtime objects anywhere
    import json

    json.dumps(plan.model_dump(mode="json"), ensure_ascii=False)


# ---- semantic validation errors ----


def test_unregistered_strategy_path_and_type():
    policy = make_policy([
        {"name": "l0", "strategy": "sliding_window", "params": {"chunk_size": 4}},
        {"name": "l1", "strategy": "nope"},
    ])
    with pytest.raises(UnregisteredStrategyError) as exc:
        compile_it(policy)
    assert isinstance(exc.value, PolicyValidationError)
    assert exc.value.path == "pipeline.levels[1].strategy"
    assert "nope" in str(exc.value)
    assert exc.value.name == "nope"


def test_unknown_param_path_and_reason():
    policy = make_policy([
        {"name": "win", "strategy": "sliding_window",
         "params": {"chunk_size": 4, "bogus": 1}},
    ])
    with pytest.raises(PolicyValidationError) as exc:
        compile_it(policy)
    assert exc.value.path == "pipeline.levels[0].params.bogus"
    assert "bogus" in exc.value.reason
    assert "sliding_window" in exc.value.reason
    assert "win" in exc.value.reason


def test_invalid_param_value_path_and_reason():
    policy = make_policy([
        {"name": "win", "strategy": "sliding_window",
         "params": {"chunk_size": 0}},
    ])
    with pytest.raises(PolicyValidationError) as exc:
        compile_it(policy)
    assert exc.value.path == "pipeline.levels[0].params.chunk_size"
    assert "sliding_window" in exc.value.reason
    assert "win" in exc.value.reason


def test_invalid_param_nested_loc():
    policy = make_policy([
        {"name": "rec", "strategy": "recursive",
         "params": {"chunk_size": 10, "separators": [123]}},
    ])
    with pytest.raises(PolicyValidationError) as exc:
        compile_it(policy)
    assert exc.value.path.startswith("pipeline.levels[0].params.separators")


def test_compile_failure_before_chunking():
    """Invalid params surface at compile time, not mid-execution."""
    policy = make_policy([
        {"name": "win", "strategy": "sliding_window",
         "params": {"chunk_size": 10, "overlap": 99}},
    ])
    with pytest.raises(PolicyValidationError) as exc:
        compile_it(policy)
    assert "overlap" in str(exc.value)


# ---- policy hash ----


def test_hash_format():
    h = policy_hash(make_policy([
        {"name": "l0", "strategy": "sliding_window", "params": {"chunk_size": 4}}
    ]))
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", h)


def test_hash_stable_across_yaml_cosmetics():
    a = """\
api_version: chunkweave/v1
policy:
  id: p1
  name: t
  version: 1.0.0
pipeline:
  levels:
    - name: l0
      strategy: sliding_window
      params:
        chunk_size: 10
        overlap: 1
"""
    # key order, whitespace, comments and quoting style differ
    b = """\
# a comment
pipeline: {levels: [{strategy: 'sliding_window', params: {overlap: 1, chunk_size: 10}, name: "l0"}]}
policy: {version: "1.0.0", name: t, id: p1}
api_version: 'chunkweave/v1'
"""
    assert policy_hash(Policy.from_yaml(a)) == policy_hash(Policy.from_yaml(b))


def test_hash_same_for_implicit_and_explicit_defaults():
    implicit = make_policy(
        [{"name": "l0", "strategy": "sliding_window", "params": {"chunk_size": 4}}],
        fields={"k": {"value": 1}},
    )
    explicit = make_policy(
        [{"name": "l0", "strategy": "sliding_window", "params": {"chunk_size": 4}}],
        fields={"k": {"value": 1}},
        include={"strategy": True, "organization": True},
    )
    assert policy_hash(implicit) == policy_hash(explicit)


def test_hash_changes_on_declared_value():
    a = make_policy([
        {"name": "l0", "strategy": "sliding_window", "params": {"chunk_size": 4}}
    ])
    b = make_policy([
        {"name": "l0", "strategy": "sliding_window", "params": {"chunk_size": 5}}
    ])
    assert policy_hash(a) != policy_hash(b)


def test_hash_distinguishes_null_value_from_source():
    a = make_policy(
        [{"name": "l0", "strategy": "sliding_window", "params": {"chunk_size": 4}}],
        fields={"k": {"value": None}},
    )
    b = make_policy(
        [{"name": "l0", "strategy": "sliding_window", "params": {"chunk_size": 4}}],
        fields={"k": {"source": "context.k"}},
    )
    assert policy_hash(a) != policy_hash(b)


def test_plan_hash_matches_policy_hash():
    policy = make_policy([
        {"name": "l0", "strategy": "sliding_window", "params": {"chunk_size": 4}}
    ])
    assert compile_it(policy).policy_hash == policy_hash(policy)


def test_plan_serializable_no_runtime_objects():
    policy = make_policy([
        {"name": "l0", "strategy": "semantic",
         "params": {"threshold": 0.5, "chunk_size": 10}}
    ])
    plan = compile_it(policy)
    dumped = plan.model_dump_json()

    def no_provider(obj):
        if isinstance(obj, dict):
            assert "provider" not in obj or obj["provider"] in (True, False)
            for v in obj.values():
                no_provider(v)
        elif isinstance(obj, list):
            for v in obj:
                no_provider(v)

    no_provider(plan.model_dump(mode="json"))
    restored = ExecutionPlan.model_validate_json(dumped)
    assert restored == plan
