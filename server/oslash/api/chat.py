"""Chat API endpoints."""

import uuid
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from oslash.db import get_db_context, crud
from oslash.models.schemas import ChatRequest, ChatResponse
from oslash.services.chat import get_chat_engine

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Ask a question about documents (non-streaming).

    - **question**: The question to ask
    - **session_id**: Optional session ID for conversation continuity
    - **document_ids**: Optional list of document IDs to use as context
    """
    chat_engine = get_chat_engine()
    session_id = request.session_id or str(uuid.uuid4())

    # Get sources filter from document_ids if provided
    sources = None  # Could filter by specific docs in the future

    # Get the answer (non-streaming)
    full_answer = ""
    citations: list[str] = []

    async for token in chat_engine.answer_with_search(
        question=request.question,
        session_id=session_id,
        sources=sources,
    ):
        full_answer += token

    # Get session to extract citations
    session = chat_engine.get_session(session_id)
    if session and session.messages:
        last_msg = session.messages[-1]
        citations = last_msg.sources

    # Save session to database
    async with get_db_context() as db:
        db_session = await crud.get_chat_session(db, session_id)
        if not db_session:
            await crud.create_chat_session(db, session_id, title=request.question[:50])

        await crud.add_message_to_session(db, session_id, "user", request.question)
        await crud.add_message_to_session(
            db, session_id, "assistant", full_answer, sources=citations
        )

    return ChatResponse(
        answer=full_answer,
        sources=citations,
        session_id=session_id,
    )


@router.post("/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """
    Ask a question with streaming response (Server-Sent Events).

    Use this for real-time token-by-token responses.
    """
    chat_engine = get_chat_engine()
    session_id = request.session_id or str(uuid.uuid4())

    async def generate() -> AsyncGenerator[str, None]:
        full_answer = ""

        async for token in chat_engine.answer_with_search(
            question=request.question,
            session_id=session_id,
        ):
            full_answer += token
            # SSE format
            yield f"data: {token}\n\n"

        # Send session ID at the end
        yield f"event: session\ndata: {session_id}\n\n"

        # Get citations
        session = chat_engine.get_session(session_id)
        if session and session.messages:
            citations = session.messages[-1].sources
            if citations:
                yield f"event: sources\ndata: {','.join(citations)}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Session-ID": session_id,
        },
    )


@router.get("/sessions")
async def list_sessions(limit: int = 10) -> dict:
    """
    List recent chat sessions.
    """
    async with get_db_context() as db:
        sessions = await crud.get_recent_sessions(db, limit)

    return {
        "sessions": [
            {
                "id": s.id,
                "title": s.title,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
                "message_count": len(s.messages) if s.messages else 0,
            }
            for s in sessions
        ]
    }


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict:
    """
    Get a specific chat session with message history.
    """
    async with get_db_context() as db:
        session = await crud.get_chat_session(db, session_id)

    if not session:
        return {
            "session_id": session_id,
            "messages": [],
            "context_documents": [],
        }

    return {
        "session_id": session.id,
        "title": session.title,
        "created_at": session.created_at.isoformat(),
        "messages": session.messages or [],
        "context_documents": session.context_document_ids or [],
    }


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict:
    """
    Delete a chat session.
    """
    # Delete from in-memory cache
    chat_engine = get_chat_engine()
    chat_engine.delete_session(session_id)

    # Delete from database
    async with get_db_context() as db:
        deleted = await crud.delete_chat_session(db, session_id)

    return {
        "message": f"Session {session_id} deleted" if deleted else "Session not found",
        "deleted": deleted,
    }
