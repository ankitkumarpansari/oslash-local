"""Services module for OSlash Local."""

from oslash.services.embeddings import (
    EmbeddingService,
    get_embedding_service,
    init_embedding_service,
)

__all__ = ["EmbeddingService", "get_embedding_service", "init_embedding_service"]

