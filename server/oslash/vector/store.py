"""ChromaDB vector store wrapper."""

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings
import structlog

logger = structlog.get_logger(__name__)

# Data directory for ChromaDB
DATA_DIR = Path(os.getenv("OSLASH_DATA_DIR", Path.home() / ".oslash"))
CHROMA_DIR = DATA_DIR / "chroma"


@dataclass
class Chunk:
    """A document chunk for embedding."""

    id: str
    document_id: str
    content: str
    embedding: Optional[list[float]] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class SearchResult:
    """A search result from the vector store."""

    chunk_id: str
    document_id: str
    content: str
    score: float
    metadata: dict = field(default_factory=dict)


@dataclass
class CollectionStats:
    """Statistics about the vector collection."""

    total_chunks: int
    sources: dict[str, int]  # source -> chunk count


class VectorStore:
    """ChromaDB vector store wrapper for document embeddings."""

    COLLECTION_NAME = "oslash_documents"

    def __init__(self, persist_directory: Optional[Path] = None):
        """Initialize ChromaDB with persistent storage."""
        self.persist_directory = persist_directory or CHROMA_DIR
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        logger.info("Initializing ChromaDB", path=str(self.persist_directory))

        # Initialize ChromaDB client with persistent storage
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={
                "description": "OSlash document chunks",
                "hnsw:space": "cosine",  # Use cosine similarity
            },
        )

        logger.info(
            "ChromaDB initialized",
            collection=self.COLLECTION_NAME,
            count=self.collection.count(),
        )

    def add_chunks(self, chunks: list[Chunk]) -> int:
        """
        Add document chunks to the vector store.

        Args:
            chunks: List of Chunk objects with embeddings

        Returns:
            Number of chunks added
        """
        if not chunks:
            return 0

        # Prepare data for ChromaDB
        ids = []
        embeddings = []
        documents = []
        metadatas = []

        for chunk in chunks:
            if chunk.embedding is None:
                logger.warning("Chunk missing embedding", chunk_id=chunk.id)
                continue

            ids.append(chunk.id)
            embeddings.append(chunk.embedding)
            documents.append(chunk.content)

            # Build metadata
            metadata = {
                "document_id": chunk.document_id,
                "source": chunk.metadata.get("source", "unknown"),
                "title": chunk.metadata.get("title", ""),
                "path": chunk.metadata.get("path", ""),
                "author": chunk.metadata.get("author", ""),
                "url": chunk.metadata.get("url", ""),
                "chunk_index": chunk.metadata.get("chunk_index", 0),
            }
            # Add modified_at as string if present
            if "modified_at" in chunk.metadata:
                modified = chunk.metadata["modified_at"]
                if isinstance(modified, datetime):
                    metadata["modified_at"] = modified.isoformat()
                else:
                    metadata["modified_at"] = str(modified)

            metadatas.append(metadata)

        if not ids:
            return 0

        # Upsert to collection
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

        logger.info("Added chunks to vector store", count=len(ids))
        return len(ids)

    def search(
        self,
        query_embedding: list[float],
        n_results: int = 10,
        where: Optional[dict] = None,
        where_document: Optional[dict] = None,
    ) -> list[SearchResult]:
        """
        Search for similar documents.

        Args:
            query_embedding: The query vector
            n_results: Maximum number of results
            where: Metadata filter (e.g., {"source": "gdrive"})
            where_document: Document content filter

        Returns:
            List of SearchResult objects sorted by similarity
        """
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where,
                where_document=where_document,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.error("Vector search failed", error=str(e))
            return []

        # Convert to SearchResult objects
        search_results = []
        if results["ids"] and results["ids"][0]:
            ids = results["ids"][0]
            documents = results["documents"][0] if results["documents"] else [""] * len(ids)
            metadatas = results["metadatas"][0] if results["metadatas"] else [{}] * len(ids)
            distances = results["distances"][0] if results["distances"] else [1.0] * len(ids)

            for i, chunk_id in enumerate(ids):
                # Convert distance to similarity score (cosine distance -> similarity)
                # ChromaDB returns distance, so score = 1 - distance for cosine
                score = max(0, 1 - distances[i])

                search_results.append(
                    SearchResult(
                        chunk_id=chunk_id,
                        document_id=metadatas[i].get("document_id", ""),
                        content=documents[i],
                        score=score,
                        metadata=metadatas[i],
                    )
                )

        return search_results

    def delete_by_document_id(self, document_id: str) -> int:
        """
        Delete all chunks for a document.

        Args:
            document_id: The document ID to delete

        Returns:
            Number of chunks deleted
        """
        try:
            # Get chunks for this document
            results = self.collection.get(
                where={"document_id": document_id},
                include=[],
            )
            chunk_ids = results["ids"]

            if chunk_ids:
                self.collection.delete(ids=chunk_ids)
                logger.info("Deleted chunks", document_id=document_id, count=len(chunk_ids))
                return len(chunk_ids)

            return 0
        except Exception as e:
            logger.error("Delete failed", document_id=document_id, error=str(e))
            return 0

    def delete_by_source(self, source: str) -> int:
        """
        Delete all chunks for a source (for re-indexing).

        Args:
            source: The source to delete (e.g., "gdrive", "gmail")

        Returns:
            Number of chunks deleted
        """
        try:
            # Get all chunks for this source
            results = self.collection.get(
                where={"source": source},
                include=[],
            )
            chunk_ids = results["ids"]

            if chunk_ids:
                self.collection.delete(ids=chunk_ids)
                logger.info("Deleted source chunks", source=source, count=len(chunk_ids))
                return len(chunk_ids)

            return 0
        except Exception as e:
            logger.error("Delete by source failed", source=source, error=str(e))
            return 0

    def get_stats(self) -> CollectionStats:
        """
        Get collection statistics.

        Returns:
            CollectionStats with total counts and per-source breakdown
        """
        total = self.collection.count()

        # Get per-source counts
        sources = {}
        for source in ["gdrive", "gmail", "slack", "hubspot"]:
            try:
                results = self.collection.get(
                    where={"source": source},
                    include=[],
                )
                sources[source] = len(results["ids"])
            except Exception:
                sources[source] = 0

        return CollectionStats(
            total_chunks=total,
            sources=sources,
        )

    def reset(self) -> None:
        """Reset the collection (delete all data). Use with caution!"""
        logger.warning("Resetting vector store")
        self.client.delete_collection(self.COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={
                "description": "OSlash document chunks",
                "hnsw:space": "cosine",
            },
        )


# Global vector store instance
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get or create the global vector store instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


def init_vector_store() -> VectorStore:
    """Initialize the vector store (call on startup)."""
    global _vector_store
    _vector_store = VectorStore()
    return _vector_store

