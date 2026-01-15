"""Search API endpoints."""

from typing import Optional

from fastapi import APIRouter, Query

from oslash.db import get_db_context, crud
from oslash.models.schemas import SearchRequest, SearchResponse, SearchResult, Source
from oslash.services.search import get_search_service

router = APIRouter(prefix="/search", tags=["Search"])


@router.post("/", response_model=SearchResponse)
async def search(request: SearchRequest) -> SearchResponse:
    """
    Search for documents across connected sources.

    - **query**: Search query (2-500 characters)
    - **limit**: Maximum results to return (1-100, default 10)
    - **sources**: Optional filter by sources (gdrive, gmail, slack, hubspot)
    """
    search_service = get_search_service()

    # Convert source enum to strings
    source_filter = None
    if request.sources:
        source_filter = [s.value for s in request.sources]

    # Perform search
    response = await search_service.search(
        query=request.query,
        sources=source_filter,
        limit=request.limit,
    )

    # Log search to history
    async with get_db_context() as db:
        await crud.add_search_history(
            db,
            query=request.query,
            result_count=response.total_found,
        )

    # Convert to API response format
    results = [
        SearchResult(
            id=r.document_id,
            title=r.title,
            source=Source(r.source),
            path=r.path,
            author=r.author,
            snippet=r.snippet,
            url=r.url or "",
            score=r.score,
            modified_at=r.modified_at,
        )
        for r in response.results
    ]

    return SearchResponse(
        query=response.query,
        results=results,
        total_found=response.total_found,
        search_time_ms=response.search_time_ms,
    )


@router.get("/suggestions")
async def get_suggestions(
    q: str = Query(..., min_length=1, description="Partial query for suggestions"),
    limit: int = Query(default=5, ge=1, le=10),
) -> dict:
    """
    Get search suggestions based on partial query.
    """
    async with get_db_context() as db:
        suggestions = await crud.get_search_suggestions(db, q, limit)

    return {"query": q, "suggestions": list(suggestions)}


@router.get("/history")
async def get_search_history(
    limit: int = Query(default=10, ge=1, le=50),
) -> dict:
    """
    Get recent search history.
    """
    async with get_db_context() as db:
        history = await crud.get_search_history(db, limit)

    return {
        "history": [
            {
                "query": h.query,
                "searched_at": h.searched_at.isoformat(),
                "result_count": h.result_count,
            }
            for h in history
        ]
    }


@router.delete("/history")
async def clear_search_history() -> dict:
    """
    Clear search history.
    """
    async with get_db_context() as db:
        count = await crud.clear_search_history(db)

    return {"message": f"Cleared {count} search history entries"}
