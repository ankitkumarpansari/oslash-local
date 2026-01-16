"""Embedding service using Chroma's default embedding function (Sentence Transformers)."""

import asyncio
from typing import Optional

import structlog
from chromadb.utils import embedding_functions

from oslash.config import get_settings

logger = structlog.get_logger(__name__)

# Default model for local embeddings
DEFAULT_MODEL = "all-MiniLM-L6-v2"


class EmbeddingService:
    """Service for generating text embeddings using local Sentence Transformers."""

    def __init__(self, model: Optional[str] = None):
        """
        Initialize the embedding service with Sentence Transformers.

        Args:
            model: Model name (defaults to all-MiniLM-L6-v2)
        """
        self.model = model or DEFAULT_MODEL
        
        # Use Chroma's built-in Sentence Transformer embedding function
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=self.model
        )

        logger.info(
            "EmbeddingService initialized with local model",
            model=self.model,
        )

    def count_tokens(self, text: str) -> int:
        """
        Estimate token count (rough approximation for Sentence Transformers).

        Args:
            text: The text to count tokens for

        Returns:
            Estimated number of tokens
        """
        # Rough approximation: ~4 characters per token
        return len(text) // 4

    def truncate_text(self, text: str, max_chars: int = 8000) -> str:
        """
        Truncate text to fit within character limit.

        Args:
            text: The text to truncate
            max_chars: Maximum number of characters

        Returns:
            Truncated text
        """
        if len(text) <= max_chars:
            return text
        return text[:max_chars]

    async def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: The text to embed

        Returns:
            Embedding vector as list of floats
        """
        # Truncate if necessary
        text = self.truncate_text(text)

        # Run in thread pool since sentence-transformers is synchronous
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: self.embedding_fn([text])
        )

        return embeddings[0]

    async def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 32,
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts with batching.

        Args:
            texts: List of texts to embed
            batch_size: Maximum texts per batch

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        # Truncate all texts
        truncated_texts = [self.truncate_text(t) for t in texts]

        # Process in batches
        all_embeddings: list[list[float]] = []
        loop = asyncio.get_event_loop()

        for i in range(0, len(truncated_texts), batch_size):
            batch = truncated_texts[i : i + batch_size]
            logger.debug(
                "Processing embedding batch",
                batch_index=i // batch_size,
                batch_size=len(batch),
                total=len(truncated_texts),
            )
            
            # Run in thread pool
            embeddings = await loop.run_in_executor(
                None,
                lambda b=batch: self.embedding_fn(b)
            )
            all_embeddings.extend(embeddings)

        return all_embeddings

    async def embed_query(self, query: str) -> list[float]:
        """
        Generate embedding for a search query.

        Args:
            query: The search query

        Returns:
            Embedding vector
        """
        return await self.embed_text(query)


# Global instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get or create the global embedding service instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


def init_embedding_service() -> EmbeddingService:
    """Initialize the embedding service (call on startup)."""
    global _embedding_service
    _embedding_service = EmbeddingService()
    return _embedding_service
