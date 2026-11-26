"""Strategy params models: validation rules, strict types, declared form."""

import json

import pytest
from pydantic import ValidationError

from chunkweave import (
    RecursiveParams,
    SemanticParams,
    SeparatorSpec,
    SlidingWindowParams,
)

# ---- SlidingWindowParams ----


def test_sliding_window_defaults():
    params = SlidingWindowParams(chunk_size=10)
    assert params.overlap == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"chunk_size": 0},
        {"chunk_size": -3},
        {"chunk_size": 10, "overlap": -1},
        {"chunk_size": 10, "overlap": 10},
        {"chunk_size": 10, "overlap": 99},
        {"chunk_size": "x"},
        {"chunk_size": 10.0},
        {"chunk_size": True},
        {"chunk_size": 10, "overlap": True},
        {"chunk_size": 10, "overlap": "1"},
    ],
)
def test_sliding_window_invalid(kwargs):
    with pytest.raises(ValidationError):
        SlidingWindowParams(**kwargs)


def test_sliding_window_max_overlap_ok():
    params = SlidingWindowParams(chunk_size=5, overlap=4)
    assert params.overlap == 4


def test_sliding_window_unknown_param_rejected():
    with pytest.raises(ValidationError):
        SlidingWindowParams(chunk_size=10, typo_param=1)


# ---- RecursiveParams ----


def test_recursive_defaults():
    params = RecursiveParams(chunk_size=10)
    assert params.separators  # default non-empty
    assert params.overlap == 0
    assert params.keep_separator == "previous"
    assert params.max_depth is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"chunk_size": 0},
        {"chunk_size": True},
        {"chunk_size": 10, "overlap": -1},
        {"chunk_size": 10, "overlap": True},
        {"chunk_size": 10, "keep_separator": "middle"},
        {"chunk_size": 10, "keep_separator": True},
        {"chunk_size": 10, "max_depth": 0},
        {"chunk_size": 10, "max_depth": -2},
        {"chunk_size": 10, "max_depth": True},
        {"chunk_size": 10, "separators": [123]},
        {"chunk_size": 10, "separators": [True]},
        {"chunk_size": 10, "separators": [{"value": "\n", "regex": "yes"}]},
        {"chunk_size": 10, "separators": [{"value": "\n", "extra": 1}]},
        {"chunk_size": 10, "separators": [{"regex": True}]},
    ],
)
def test_recursive_invalid(kwargs):
    with pytest.raises(ValidationError):
        RecursiveParams(**kwargs)


def test_recursive_empty_separators_ok():
    params = RecursiveParams(chunk_size=5, separators=[])
    assert params.separators == []


def test_recursive_regex_separator_decl():
    params = RecursiveParams(
        chunk_size=10,
        separators=["\n\n", {"value": r"第[一二三四]+章", "regex": True}],
    )
    assert params.separators[0] == "\n\n"
    assert isinstance(params.separators[1], SeparatorSpec)
    assert params.separators[1].regex is True


def test_recursive_regex_separator_not_compiling_rejected():
    with pytest.raises(ValidationError):
        SeparatorSpec(value="([", regex=True)
    with pytest.raises(ValidationError):
        RecursiveParams(
            chunk_size=10, separators=[{"value": "([", "regex": True}]
        )


def test_recursive_unknown_param_rejected():
    with pytest.raises(ValidationError):
        RecursiveParams(chunk_size=10, window=3)


# ---- SemanticParams ----


def test_semantic_defaults():
    params = SemanticParams(threshold=0.5, chunk_size=100)
    assert params.unit_separators


@pytest.mark.parametrize(
    "kwargs",
    [
        {"threshold": -0.1, "chunk_size": 10},
        {"threshold": 1.01, "chunk_size": 10},
        {"threshold": 0.5, "chunk_size": 0},
        {"threshold": "high", "chunk_size": 10},
        {"threshold": "0.5", "chunk_size": 10},
        {"threshold": True, "chunk_size": 10},
        {"threshold": 0.5, "chunk_size": True},
        {"threshold": 0.5, "chunk_size": "10"},
    ],
)
def test_semantic_invalid(kwargs):
    with pytest.raises(ValidationError):
        SemanticParams(**kwargs)


@pytest.mark.parametrize("t", [0.0, 1.0, 0, 1])
def test_semantic_threshold_bounds_ok(t):
    params = SemanticParams(threshold=t, chunk_size=10)
    assert params.threshold == t
    assert isinstance(params.threshold, float)


def test_semantic_unknown_param_rejected():
    with pytest.raises(ValidationError):
        SemanticParams(threshold=0.5, chunk_size=10, provider="x")


# ---- declared form stays JSON-serializable ----


def test_params_dump_json_serializable():
    params = RecursiveParams(
        chunk_size=10,
        separators=["\n", {"value": r"第[一二三四]+章", "regex": True}],
    )
    dumped = params.model_dump()
    json.dumps(dumped, ensure_ascii=False)
    assert dumped["separators"][1] == {"value": r"第[一二三四]+章", "regex": True}
    params2 = RecursiveParams.model_validate(dumped)
    assert params2 == params
