"""Exception hierarchy for chunkweave."""


class ChunkweaveError(Exception):
    """Base class for all chunkweave errors."""


class ConfigError(ChunkweaveError):
    """Raised when a strategy or organization configuration is invalid."""

    def __init__(self, field: str, reason: str) -> None:
        self.field = field
        self.reason = reason
        super().__init__(f"invalid config field {field!r}: {reason}")


class UnregisteredStrategyError(ChunkweaveError):
    """Raised when a strategy name is not registered."""

    def __init__(self, name: str, available: list[str] | None = None) -> None:
        self.name = name
        suffix = f" (available: {', '.join(sorted(available))})" if available else ""
        super().__init__(f"unregistered strategy: {name!r}{suffix}")


class RegistryConflictError(ChunkweaveError):
    """Raised when registering a strategy under an already-used name."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(
            f"strategy name already registered: {name!r} (pass replace=True to override)"
        )


class MetadataConflictError(ChunkweaveError):
    """Raised when custom metadata collides with a reserved field name."""

    def __init__(self, keys: set[str]) -> None:
        self.keys = set(keys)
        super().__init__(
            "custom metadata conflicts with reserved fields: " + ", ".join(sorted(self.keys))
        )


class ProviderMissingError(ChunkweaveError):
    """Raised when a strategy requires a similarity provider but none was injected."""

    def __init__(self, strategy: str = "semantic") -> None:
        self.strategy = strategy
        super().__init__(
            f"strategy {strategy!r} requires an injected similarity provider; "
            "call set_provider() or pass provider= before chunking"
        )
