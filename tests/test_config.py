"""Config validation (fail fast) and JSON serialization round-trips."""

import re

import pytest

from chunkweave import (
    ConfigError,
    FlatConfig,
    HierarchicalConfig,
    LevelConfig,
    RecursiveConfig,
    SemanticConfig,
    SlidingWindowConfig,
    engine_config_from_dict,
)

# ---- SlidingWindowConfig ----


def test_sliding_window_defaults():
    cfg = SlidingWindowConfig(chunk_size=10)
    assert cfg.overlap == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"chunk_size": 0},
        {"chunk_size": -3},
        {"chunk_size": 10, "overlap": -1},
        {"chunk_size": 10, "overlap": 10},
        {"chunk_size": 10, "overlap": 99},
        {"chunk_size": "x"},
    ],
)
def test_sliding_window_invalid(kwargs):
    with pytest.raises(ConfigError):
        SlidingWindowConfig(**kwargs)


def test_sliding_window_max_overlap_ok():
    cfg = SlidingWindowConfig(chunk_size=5, overlap=4)
    assert cfg.overlap == 4


# ---- RecursiveConfig ----


def test_recursive_defaults():
    cfg = RecursiveConfig(chunk_size=10)
    assert cfg.separators  # default non-empty
    assert cfg.overlap == 0
    assert cfg.keep_separator == "previous"
    assert cfg.max_depth is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"chunk_size": 0},
        {"chunk_size": 10, "overlap": -1},
        {"chunk_size": 10, "keep_separator": "middle"},
        {"chunk_size": 10, "max_depth": 0},
        {"chunk_size": 10, "separators": [123]},
    ],
)
def test_recursive_invalid(kwargs):
    with pytest.raises(ConfigError):
        RecursiveConfig(**kwargs)


def test_recursive_empty_separators_ok():
    cfg = RecursiveConfig(chunk_size=5, separators=[])
    assert cfg.separators == []


# ---- SemanticConfig ----


def test_semantic_defaults():
    cfg = SemanticConfig(threshold=0.5, chunk_size=100)
    assert cfg.unit_separators


@pytest.mark.parametrize(
    "kwargs",
    [
        {"threshold": -0.1, "chunk_size": 10},
        {"threshold": 1.01, "chunk_size": 10},
        {"threshold": 0.5, "chunk_size": 0},
        {"threshold": "high", "chunk_size": 10},
    ],
)
def test_semantic_invalid(kwargs):
    with pytest.raises(ConfigError):
        SemanticConfig(**kwargs)


@pytest.mark.parametrize("t", [0.0, 1.0])
def test_semantic_threshold_bounds_ok(t):
    assert SemanticConfig(threshold=t, chunk_size=10).threshold == t


# ---- Organization configs ----


def test_flat_config():
    cfg = FlatConfig(strategy="sliding_window", config={"chunk_size": 4})
    assert cfg.strategy == "sliding_window"


def test_hierarchical_requires_nonempty_levels():
    with pytest.raises(ConfigError):
        HierarchicalConfig(levels=[])


def test_hierarchical_multilevel_ok():
    cfg = HierarchicalConfig(
        levels=[
            LevelConfig(strategy="recursive", config={"chunk_size": 100}, name="chapter"),
            LevelConfig(strategy="sliding_window", config={"chunk_size": 10}),
        ]
    )
    assert len(cfg.levels) == 2
    assert cfg.levels[0].name == "chapter"


def test_engine_config_dispatch():
    flat = engine_config_from_dict(
        {"organization": "flat", "strategy": "recursive", "config": {"chunk_size": 8}}
    )
    assert isinstance(flat, FlatConfig)
    hier = engine_config_from_dict(
        {
            "organization": "hierarchical",
            "levels": [{"strategy": "recursive", "config": {"chunk_size": 8}}],
        }
    )
    assert isinstance(hier, HierarchicalConfig)
    with pytest.raises(ConfigError):
        engine_config_from_dict({"organization": "weird"})


def test_custom_rejects_non_mapping():
    with pytest.raises(ConfigError):
        FlatConfig(strategy="x", custom=[1, 2])


# ---- Serialization ----


def test_config_json_roundtrip():
    for cfg in (
        SlidingWindowConfig(chunk_size=8, overlap=2),
        RecursiveConfig(
            chunk_size=16,
            separators=["\n\n", re.compile(r"第\d+章"), ""],
            overlap=3,
            keep_separator="next",
            max_depth=4,
        ),
        SemanticConfig(threshold=0.7, chunk_size=50, unit_separators=["。", "!"]),
    ):
        restored = type(cfg).from_json(cfg.to_json())
        assert restored.to_dict() == cfg.to_dict()


def test_regex_separator_tagged_roundtrip():
    cfg = RecursiveConfig(
        chunk_size=10, separators=["\n", re.compile(r"第[一二三四]章")]
    )
    data = cfg.to_dict()
    assert data["separators"][0] == {"value": "\n", "regex": False}
    assert data["separators"][1] == {"value": r"第[一二三四]章", "regex": True}
    restored = RecursiveConfig.from_dict(data)
    assert isinstance(restored.separators[1], re.Pattern)
    assert restored.separators[1].pattern == r"第[一二三四]章"


def test_separator_from_dict_accepts_plain_string():
    cfg = RecursiveConfig.from_dict(
        {"chunk_size": 5, "separators": ["\n", {"value": "x+", "regex": True}]}
    )
    assert cfg.separators[0] == "\n"
    assert isinstance(cfg.separators[1], re.Pattern)


def test_config_output_stable():
    cfg = RecursiveConfig(chunk_size=10, separators=["。", re.compile("!+")])
    assert cfg.to_json() == cfg.to_json()


def test_hierarchical_config_roundtrip():
    cfg = HierarchicalConfig(
        levels=[
            LevelConfig(
                strategy="recursive",
                config={"chunk_size": 500, "separators": ["\n\n"]},
                name="chapter",
                metadata={"kind": "chapter"},
            ),
            LevelConfig(strategy="sliding_window", config={"chunk_size": 50}),
        ],
        custom={"doc": "x"},
    )
    restored = HierarchicalConfig.from_dict(cfg.to_dict())
    assert restored.to_dict() == cfg.to_dict()
