"""Chat API endpoints."""

import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from oslash.models.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Ask a question about documents (non-streaming).

    - **question**: The question to ask
    - **session_id**: Optional session ID for conversation continuity
    - **document_ids**: Optional list of document IDs to use as context
    """
    session_id = request.session_id or str(uuid.uuid4())

    # TODO: Implement actual RAG chat with OpenAI
    answer = f"This is a placeholder response to: {request.question}"

    return ChatResponse(
        answer=answer,
        sources=[],
        session_id=session_id,
    )


@router.post("/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """
    Ask a question with streaming response (Server-Sent Events).

    Use this for real-time token-by-token responses.
    """

    async def generate() -> AsyncGenerator[str, None]:
        # TODO: Implement actual streaming with OpenAI
        response = f"This is a streaming response to: {request.question}"
        for word in response.split():
            yield f"data: {word} \n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/sessions")
async def list_sessions(limit: int = 10) -> dict:
    """
    List recent chat sessions.
    """
    # TODO: Implement with database
    return {"sessions": []}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict:
    """
    Get a specific chat session with message history.
    """
    # TODO: Implement with database
    return {
        "session_id": session_id,
        "messages": [],
        "context_documents": [],
    }


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict:
    """
    Delete a chat session.
    """
    # TODO: Implement with database
    return {"message": f"Session {session_id} deleted"}

