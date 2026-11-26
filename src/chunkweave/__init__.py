"""chunkweave: declarative, policy-driven text chunking engine."""

from .compiler import ExecutionPlan, PlanField, PlanLevel
from .engine import ChunkEngine, Registry, StrategySpec
from .models import (
    Chunk,
    ChunkResult,
    ChunkSpan,
    ChunkweaveError,
    ContextResolutionError,
    PolicyLoadError,
    PolicyValidationError,
    ProviderMissingError,
    RegistryConflictError,
    UnregisteredStrategyError,
    chunk_id_for,
)
from .policy import API_VERSION, Policy
from .strategies import (
    Chunker,
    RecursiveChunker,
    RecursiveParams,
    SemanticChunker,
    SemanticParams,
    SeparatorSpec,
    SimilarityProvider,
    SlidingWindowChunker,
    SlidingWindowParams,
)

__version__ = "0.1.0"

__all__ = [
    "API_VERSION",
    "Chunk",
    "ChunkEngine",
    "ChunkResult",
    "ChunkSpan",
    "Chunker",
    "ChunkweaveError",
    "ContextResolutionError",
    "ExecutionPlan",
    "PlanField",
    "PlanLevel",
    "Policy",
    "PolicyLoadError",
    "PolicyValidationError",
    "ProviderMissingError",
    "RecursiveChunker",
    "RecursiveParams",
    "Registry",
    "RegistryConflictError",
    "SemanticChunker",
    "SemanticParams",
    "SeparatorSpec",
    "SimilarityProvider",
    "SlidingWindowChunker",
    "SlidingWindowParams",
    "StrategySpec",
    "UnregisteredStrategyError",
    "__version__",
    "chunk_id_for",
]
