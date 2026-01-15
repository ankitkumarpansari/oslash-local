"""OpenAI embedding service for generating vector embeddings."""

import asyncio
from typing import Optional

import structlog
import tiktoken
from openai import AsyncOpenAI, RateLimitError, APIError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from oslash.config import get_settings

logger = structlog.get_logger(__name__)

# Constants
MAX_TOKENS_PER_TEXT = 8191  # OpenAI limit for embedding model
MAX_BATCH_SIZE = 2048  # OpenAI batch limit
DEFAULT_MODEL = "text-embedding-3-small"


class EmbeddingService:
    """Service for generating text embeddings using OpenAI."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """
        Initialize the embedding service.

        Args:
            api_key: OpenAI API key (defaults to settings)
            model: Embedding model name (defaults to settings)
        """
        settings = get_settings()
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.embedding_model

        if not self.api_key:
            logger.warning("OpenAI API key not configured")
            self.client = None
        else:
            self.client = AsyncOpenAI(api_key=self.api_key)

        # Initialize tokenizer for the embedding model
        try:
            self.tokenizer = tiktoken.encoding_for_model(self.model)
        except KeyError:
            # Fallback to cl100k_base for newer models
            self.tokenizer = tiktoken.get_encoding("cl100k_base")

        logger.info(
            "EmbeddingService initialized",
            model=self.model,
            has_api_key=bool(self.api_key),
        )

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in a text string.

        Args:
            text: The text to count tokens for

        Returns:
            Number of tokens
        """
        return len(self.tokenizer.encode(text))

    def truncate_text(self, text: str, max_tokens: int = MAX_TOKENS_PER_TEXT) -> str:
        """
        Truncate text to fit within token limit.

        Args:
            text: The text to truncate
            max_tokens: Maximum number of tokens

        Returns:
            Truncated text
        """
        tokens = self.tokenizer.encode(text)
        if len(tokens) <= max_tokens:
            return text
        truncated_tokens = tokens[:max_tokens]
        return self.tokenizer.decode(truncated_tokens)

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIError)),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        before_sleep=lambda retry_state: logger.warning(
            "Retrying embedding request",
            attempt=retry_state.attempt_number,
            error=str(retry_state.outcome.exception()) if retry_state.outcome else None,
        ),
    )
    async def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: The text to embed

        Returns:
            Embedding vector as list of floats

        Raises:
            ValueError: If API key not configured
            Exception: If embedding fails after retries
        """
        if not self.client:
            raise ValueError("OpenAI API key not configured")

        # Truncate if necessary
        text = self.truncate_text(text)

        response = await self.client.embeddings.create(
            model=self.model,
            input=text,
        )

        return response.data[0].embedding

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIError)),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        before_sleep=lambda retry_state: logger.warning(
            "Retrying batch embedding request",
            attempt=retry_state.attempt_number,
        ),
    )
    async def _embed_batch_internal(self, texts: list[str]) -> list[list[float]]:
        """Internal batch embedding with retry logic."""
        if not self.client:
            raise ValueError("OpenAI API key not configured")

        response = await self.client.embeddings.create(
            model=self.model,
            input=texts,
        )

        # Sort by index to maintain order
        sorted_data = sorted(response.data, key=lambda x: x.index)
        return [item.embedding for item in sorted_data]

    async def embed_batch(
        self,
        texts: list[str],
        batch_size: int = MAX_BATCH_SIZE,
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts with batching.

        Args:
            texts: List of texts to embed
            batch_size: Maximum texts per API call

        Returns:
            List of embedding vectors

        Raises:
            ValueError: If API key not configured
        """
        if not texts:
            return []

        if not self.client:
            raise ValueError("OpenAI API key not configured")

        # Truncate all texts
        truncated_texts = [self.truncate_text(t) for t in texts]

        # Process in batches
        all_embeddings: list[list[float]] = []
        for i in range(0, len(truncated_texts), batch_size):
            batch = truncated_texts[i : i + batch_size]
            logger.debug(
                "Processing embedding batch",
                batch_index=i // batch_size,
                batch_size=len(batch),
                total=len(truncated_texts),
            )
            embeddings = await self._embed_batch_internal(batch)
            all_embeddings.extend(embeddings)

            # Small delay between batches to avoid rate limits
            if i + batch_size < len(truncated_texts):
                await asyncio.sleep(0.1)

        return all_embeddings

    async def embed_query(self, query: str) -> list[float]:
        """
        Generate embedding for a search query.

        This is an alias for embed_text, but could be customized
        for query-specific preprocessing in the future.

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

