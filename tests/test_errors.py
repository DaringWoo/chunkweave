"""Exception hierarchy and error context."""

import pytest

from chunkweave import (
    ChunkweaveError,
    ContextResolutionError,
    PolicyLoadError,
    PolicyValidationError,
    ProviderMissingError,
    RegistryConflictError,
    UnregisteredStrategyError,
)


def test_all_errors_inherit_base():
    for exc in (
        PolicyLoadError("m"),
        PolicyValidationError("p", "r"),
        UnregisteredStrategyError("x"),
        RegistryConflictError("x"),
        ContextResolutionError("f", "p", "r"),
        ProviderMissingError(),
    ):
        assert isinstance(exc, ChunkweaveError)


def test_unregistered_is_policy_validation():
    err = UnregisteredStrategyError("nope", ["sliding_window"], path="pipeline.levels[0].strategy")
    assert isinstance(err, PolicyValidationError)
    assert err.path == "pipeline.levels[0].strategy"


def test_policy_validation_error_has_path_and_reason():
    err = PolicyValidationError("pipeline.levels[1].strategy", "Field required")
    assert err.path == "pipeline.levels[1].strategy"
    assert err.reason == "Field required"
    assert "pipeline.levels[1].strategy" in str(err)
    assert "Field required" in str(err)


def test_policy_validation_error_empty_path():
    err = PolicyValidationError("", "bad")
    assert "at" not in str(err) or str(err).startswith("invalid policy:")
    assert "bad" in str(err)


def test_unregistered_strategy_error_names_strategy():
    err = UnregisteredStrategyError("nope", ["sliding_window"])
    assert err.name == "nope"
    assert "nope" in str(err)
    assert "sliding_window" in str(err)


def test_registry_conflict_names_name():
    err = RegistryConflictError("recursive")
    assert err.name == "recursive"
    assert "recursive" in str(err)


def test_context_resolution_error_has_field_path_reason():
    err = ContextResolutionError("author", "context.doc.author", "missing key")
    assert err.field == "author"
    assert err.path == "context.doc.author"
    assert err.reason == "missing key"
    assert "author" in str(err)
    assert "context.doc.author" in str(err)


def test_provider_missing_mentions_strategy_and_execute():
    err = ProviderMissingError()
    assert err.strategy == "semantic"
    assert "semantic" in str(err)
    assert "provider=" in str(err)
    with pytest.raises(ProviderMissingError):
        raise err
