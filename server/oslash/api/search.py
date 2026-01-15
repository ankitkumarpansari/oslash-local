"""Search API endpoints."""

import time
from typing import Optional

from fastapi import APIRouter, Query

from oslash.models.schemas import SearchRequest, SearchResponse, SearchResult, Source

router = APIRouter(prefix="/search", tags=["Search"])


@router.post("/", response_model=SearchResponse)
async def search(request: SearchRequest) -> SearchResponse:
    """
    Search for documents across connected sources.

    - **query**: Search query (2-500 characters)
    - **limit**: Maximum results to return (1-100, default 10)
    - **sources**: Optional filter by sources (gdrive, gmail, slack, hubspot)
    """
    start_time = time.time()

    # TODO: Implement actual search with embeddings + ChromaDB
    # For now, return mock results
    results: list[SearchResult] = []

    elapsed_ms = (time.time() - start_time) * 1000

    return SearchResponse(
        query=request.query,
        results=results,
        total_found=len(results),
        search_time_ms=round(elapsed_ms, 2),
    )


@router.get("/suggestions")
async def get_suggestions(
    q: str = Query(..., min_length=1, description="Partial query for suggestions"),
    limit: int = Query(default=5, ge=1, le=10),
) -> dict:
    """
    Get search suggestions based on partial query.
    """
    # TODO: Implement with search history and popular queries
    return {"query": q, "suggestions": []}


@router.get("/history")
async def get_search_history(
    limit: int = Query(default=10, ge=1, le=50),
) -> dict:
    """
    Get recent search history.
    """
    # TODO: Implement with database
    return {"history": []}


@router.delete("/history")
async def clear_search_history() -> dict:
    """
    Clear search history.
    """
    # TODO: Implement with database
    return {"message": "History cleared"}

