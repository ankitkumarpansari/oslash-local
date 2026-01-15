"""Vector store module for OSlash Local."""

from oslash.vector.store import (
    VectorStore,
    Chunk,
    SearchResult,
    CollectionStats,
    get_vector_store,
    init_vector_store,
)

__all__ = [
    "VectorStore",
    "Chunk",
    "SearchResult",
    "CollectionStats",
    "get_vector_store",
    "init_vector_store",
]

