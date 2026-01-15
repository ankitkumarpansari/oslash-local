"""Search service for RAG-powered document search."""

import re
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import structlog

from oslash.config import get_settings
from oslash.services.embeddings import get_embedding_service
from oslash.vector import get_vector_store, SearchResult as VectorSearchResult

logger = structlog.get_logger(__name__)


@dataclass
class SearchResult:
    """A search result with document info and relevance."""

    document_id: str
    title: str
    source: str
    path: Optional[str]
    author: Optional[str]
    url: Optional[str]
    snippet: str
    score: float
    modified_at: Optional[datetime]
    chunk_count: int = 1

    def to_dict(self) -> dict:
        """Convert to API response format."""
        return {
            "id": self.document_id,
            "title": self.title,
            "source": self.source,
            "path": self.path,
            "author": self.author,
            "url": self.url,
            "snippet": self.snippet,
            "score": self.score,
            "modified_at": self.modified_at.isoformat() if self.modified_at else None,
        }


@dataclass
class SearchResponse:
    """Search response with results and metadata."""

    query: str
    results: list[SearchResult]
    total_found: int
    search_time_ms: float

    def to_dict(self) -> dict:
        """Convert to API response format."""
        return {
            "query": self.query,
            "results": [r.to_dict() for r in self.results],
            "total_found": self.total_found,
            "search_time_ms": self.search_time_ms,
        }


class SearchService:
    """Service for semantic document search."""

    def __init__(self):
        """Initialize search service."""
        self.settings = get_settings()
        self.embedding_service = get_embedding_service()
        self.vector_store = get_vector_store()

        logger.info("SearchService initialized")

    def _preprocess_query(self, query: str) -> str:
        """
        Pre-process search query.

        - Normalize whitespace
        - Expand common abbreviations
        - Remove special characters that might confuse search
        """
        # Normalize whitespace
        query = " ".join(query.split())

        # Expand common abbreviations
        abbreviations = {
            r"\bdoc\b": "document",
            r"\bdocs\b": "documents",
            r"\binfo\b": "information",
            r"\bmtg\b": "meeting",
            r"\bpls\b": "please",
            r"\basap\b": "as soon as possible",
            r"\bfyi\b": "for your information",
            r"\bwrt\b": "with respect to",
            r"\bre\b": "regarding",
        }

        for pattern, replacement in abbreviations.items():
            query = re.sub(pattern, replacement, query, flags=re.IGNORECASE)

        return query.strip()

    def _extract_snippet(self, content: str, max_length: int = 300) -> str:
        """Extract a readable snippet from chunk content."""
        if len(content) <= max_length:
            return content

        # Try to break at sentence boundary
        truncated = content[:max_length]
        last_period = truncated.rfind(".")
        last_newline = truncated.rfind("\n")

        break_point = max(last_period, last_newline)
        if break_point > max_length // 2:
            return truncated[: break_point + 1].strip()

        # Fall back to word boundary
        last_space = truncated.rfind(" ")
        if last_space > 0:
            return truncated[:last_space].strip() + "..."

        return truncated + "..."

    def _group_by_document(
        self, results: list[VectorSearchResult]
    ) -> list[SearchResult]:
        """
        Group search results by document, keeping best chunk per document.

        This deduplicates results when multiple chunks from the same
        document match the query.
        """
        # Group by document_id
        doc_groups: dict[str, list[VectorSearchResult]] = defaultdict(list)
        for result in results:
            doc_id = result.metadata.get("document_id", result.chunk_id)
            doc_groups[doc_id].append(result)

        # For each document, take the best scoring chunk
        grouped_results: list[SearchResult] = []
        for doc_id, chunks in doc_groups.items():
            # Sort by score descending
            chunks.sort(key=lambda x: x.score, reverse=True)
            best_chunk = chunks[0]

            # Parse modified_at
            modified_at = None
            if best_chunk.metadata.get("modified_at"):
                try:
                    modified_at = datetime.fromisoformat(
                        best_chunk.metadata["modified_at"]
                    )
                except (ValueError, TypeError):
                    pass

            grouped_results.append(
                SearchResult(
                    document_id=doc_id,
                    title=best_chunk.metadata.get("title", "Untitled"),
                    source=best_chunk.metadata.get("source", "unknown"),
                    path=best_chunk.metadata.get("path"),
                    author=best_chunk.metadata.get("author"),
                    url=best_chunk.metadata.get("url"),
                    snippet=self._extract_snippet(best_chunk.content),
                    score=best_chunk.score,
                    modified_at=modified_at,
                    chunk_count=len(chunks),
                )
            )

        # Sort by score
        grouped_results.sort(key=lambda x: x.score, reverse=True)
        return grouped_results

    def _build_filter(
        self,
        sources: Optional[list[str]] = None,
    ) -> Optional[dict]:
        """Build ChromaDB filter from search parameters."""
        if not sources:
            return None

        if len(sources) == 1:
            return {"source": sources[0]}

        return {"source": {"$in": sources}}

    async def search(
        self,
        query: str,
        sources: Optional[list[str]] = None,
        limit: int = 10,
    ) -> SearchResponse:
        """
        Search for documents matching the query.

        Args:
            query: Search query
            sources: Optional list of sources to filter (gdrive, gmail, slack, hubspot)
            limit: Maximum number of results

        Returns:
            SearchResponse with results and metadata
        """
        start_time = time.time()

        # Pre-process query
        processed_query = self._preprocess_query(query)
        logger.debug("Query preprocessed", original=query, processed=processed_query)

        # Generate embedding
        try:
            embedding = await self.embedding_service.embed_text(processed_query)
        except Exception as e:
            logger.error("Embedding failed", error=str(e))
            return SearchResponse(
                query=query,
                results=[],
                total_found=0,
                search_time_ms=(time.time() - start_time) * 1000,
            )

        # Build filter
        where_filter = self._build_filter(sources)

        # Search vector store (over-fetch for deduplication)
        vector_results = self.vector_store.search(
            query_embedding=embedding,
            n_results=limit * 3,
            where=where_filter,
        )

        # Group by document and deduplicate
        grouped_results = self._group_by_document(vector_results)

        # Apply similarity threshold
        threshold = self.settings.similarity_threshold
        filtered_results = [r for r in grouped_results if r.score >= threshold]

        # Limit results
        final_results = filtered_results[:limit]

        elapsed_ms = (time.time() - start_time) * 1000

        logger.info(
            "Search completed",
            query=query[:50],
            sources=sources,
            results=len(final_results),
            time_ms=round(elapsed_ms, 2),
        )

        return SearchResponse(
            query=query,
            results=final_results,
            total_found=len(filtered_results),
            search_time_ms=round(elapsed_ms, 2),
        )

    async def search_similar(
        self,
        document_id: str,
        limit: int = 5,
    ) -> SearchResponse:
        """
        Find documents similar to a given document.

        Args:
            document_id: ID of the document to find similar ones for
            limit: Maximum number of results

        Returns:
            SearchResponse with similar documents
        """
        start_time = time.time()

        # Get chunks for the document
        results = self.vector_store.collection.get(
            where={"document_id": document_id},
            include=["documents", "embeddings"],
        )

        if not results["ids"]:
            return SearchResponse(
                query=f"similar:{document_id}",
                results=[],
                total_found=0,
                search_time_ms=(time.time() - start_time) * 1000,
            )

        # Use the first chunk's embedding
        embedding = results["embeddings"][0]

        # Search for similar (excluding the source document)
        vector_results = self.vector_store.search(
            query_embedding=embedding,
            n_results=limit * 3,
        )

        # Filter out the source document and group
        filtered = [r for r in vector_results if r.document_id != document_id]
        grouped_results = self._group_by_document(filtered)

        elapsed_ms = (time.time() - start_time) * 1000

        return SearchResponse(
            query=f"similar:{document_id}",
            results=grouped_results[:limit],
            total_found=len(grouped_results),
            search_time_ms=round(elapsed_ms, 2),
        )


# Global instance
_search_service: Optional[SearchService] = None


def get_search_service() -> SearchService:
    """Get or create the global search service instance."""
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service

