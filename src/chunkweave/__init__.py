"""chunkweave: composable text chunking and organization engine."""

from .chunk import Chunk, ChunkMetadata
from .config import (
    EngineConfig,
    FlatConfig,
    HierarchicalConfig,
    LevelConfig,
    RecursiveConfig,
    SemanticConfig,
    SlidingWindowConfig,
    engine_config_from_dict,
)
from .engine import ChunkEngine
from .errors import (
    ChunkweaveError,
    ConfigError,
    MetadataConflictError,
    ProviderMissingError,
    RegistryConflictError,
    UnregisteredStrategyError,
)
from .metadata import attach_custom_metadata, reserved_field_names
from .registry import Registry, default_registry
from .strategies import (
    Chunker,
    ProviderAware,
    RecursiveChunker,
    SemanticChunker,
    SimilarityProvider,
    SlidingWindowChunker,
)
from .tree import ChunkNode, ChunkResult

__version__ = "0.1.0"

__all__ = [
    "Chunk",
    "ChunkEngine",
    "ChunkMetadata",
    "ChunkNode",
    "ChunkResult",
    "Chunker",
    "ChunkweaveError",
    "ConfigError",
    "EngineConfig",
    "FlatConfig",
    "HierarchicalConfig",
    "LevelConfig",
    "MetadataConflictError",
    "ProviderAware",
    "ProviderMissingError",
    "RecursiveChunker",
    "RecursiveConfig",
    "Registry",
    "RegistryConflictError",
    "SemanticChunker",
    "SemanticConfig",
    "SimilarityProvider",
    "SlidingWindowChunker",
    "SlidingWindowConfig",
    "UnregisteredStrategyError",
    "__version__",
    "attach_custom_metadata",
    "default_registry",
    "engine_config_from_dict",
    "reserved_field_names",
]
