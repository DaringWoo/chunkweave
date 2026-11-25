"""Exception hierarchy and error context."""

import pytest

from chunkweave import (
    ChunkweaveError,
    ConfigError,
    MetadataConflictError,
    ProviderMissingError,
    RegistryConflictError,
    UnregisteredStrategyError,
)


def test_all_errors_inherit_base():
    for exc in (
        ConfigError("f", "r"),
        UnregisteredStrategyError("x"),
        RegistryConflictError("x"),
        MetadataConflictError({"k"}),
        ProviderMissingError(),
    ):
        assert isinstance(exc, ChunkweaveError)


def test_config_error_message_has_context():
    err = ConfigError("chunk_size", "must be > 0, got 0")
    assert "chunk_size" in str(err)
    assert "must be > 0" in str(err)


def test_unregistered_strategy_error_names_strategy():
    err = UnregisteredStrategyError("nope", ["sliding_window"])
    assert err.name == "nope"
    assert "nope" in str(err)
    assert "sliding_window" in str(err)


def test_registry_conflict_names_name():
    err = RegistryConflictError("recursive")
    assert err.name == "recursive"
    assert "recursive" in str(err)


def test_metadata_conflict_lists_keys():
    err = MetadataConflictError({"level", "chunk_id"})
    assert err.keys == {"level", "chunk_id"}
    assert "level" in str(err)


def test_provider_missing_mentions_strategy():
    err = ProviderMissingError()
    assert err.strategy == "semantic"
    assert "semantic" in str(err)
    with pytest.raises(ProviderMissingError):
        raise err
