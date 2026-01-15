"""Vector store API endpoints."""

from fastapi import APIRouter

from oslash.vector import get_vector_store

router = APIRouter(prefix="/vectors", tags=["Vectors"])


@router.get("/stats")
async def get_vector_stats() -> dict:
    """
    Get vector store statistics.

    Returns total chunk count and per-source breakdown.
    """
    store = get_vector_store()
    stats = store.get_stats()

    return {
        "total_chunks": stats.total_chunks,
        "sources": stats.sources,
    }


@router.post("/reset")
async def reset_vectors() -> dict:
    """
    Reset the vector store (delete all embeddings).

    WARNING: This will delete all indexed content and require re-syncing.
    """
    store = get_vector_store()
    store.reset()

    return {
        "message": "Vector store reset successfully",
        "total_chunks": 0,
    }

