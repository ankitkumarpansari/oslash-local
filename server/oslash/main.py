"""OSlash Local Server - Main entry point."""

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from oslash import __version__
from oslash.api import auth, chat, search, sync
from oslash.db import init_db, get_db_context, crud
from oslash.models.schemas import ServerStatus, AccountStatus, Source

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.dev.ConsoleRenderer(colors=True),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# Lifespan Management
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifespan - startup and shutdown."""
    # Startup
    logger.info("Starting OSlash Local server", version=__version__)

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # TODO: Initialize ChromaDB
    # TODO: Start background sync scheduler

    yield

    # Shutdown
    logger.info("Shutting down OSlash Local server")
    # TODO: Stop background tasks


# =============================================================================
# Create FastAPI Application
# =============================================================================

app = FastAPI(
    title="OSlash Local",
    description="RAG-powered file search across Google Drive, Gmail, Slack, and HubSpot",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# =============================================================================
# Middleware
# =============================================================================

# CORS - Allow extension to communicate with server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests."""
    start_time = time.time()

    response = await call_next(request)

    duration_ms = (time.time() - start_time) * 1000
    logger.info(
        "HTTP request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round(duration_ms, 2),
    )

    return response


# =============================================================================
# Exception Handlers
# =============================================================================


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions."""
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        error=str(exc),
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# =============================================================================
# Health & Status Endpoints
# =============================================================================


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """
    Health check endpoint.

    Returns server health status. Use this to verify the server is running.
    """
    return {
        "status": "healthy",
        "version": __version__,
    }


@app.get("/api/v1/status", response_model=ServerStatus, tags=["Status"])
async def get_status() -> ServerStatus:
    """
    Get server status and connected accounts.

    Returns information about connected accounts, document counts, and sync status.
    """
    async with get_db_context() as db:
        # Get connected accounts
        connected = await crud.get_all_connected_accounts(db)
        connected_map = {acc.source: acc for acc in connected}

        # Get sync states
        sync_states = await crud.get_all_sync_states(db)
        sync_map = {state.source: state for state in sync_states}

        # Get total document count
        total_docs = await crud.count_documents(db)

        accounts = {}
        for source in Source:
            acc = connected_map.get(source.value)
            sync_state = sync_map.get(source.value)
            doc_count = await crud.count_documents(db, source.value)

            accounts[source.value] = AccountStatus(
                connected=acc is not None,
                email=acc.email if acc else None,
                document_count=doc_count,
                last_sync=sync_state.last_synced_at if sync_state else None,
                status=sync_state.status if sync_state else "idle",
            )

    return ServerStatus(
        online=True,
        version=__version__,
        accounts=accounts,
        total_documents=total_docs,
        total_chunks=0,  # TODO: Get from ChromaDB
    )


@app.post("/api/v1/warm", tags=["Status"])
async def warm() -> dict:
    """
    Pre-warm the search pipeline.

    Call this when user starts typing to reduce latency.
    """
    # TODO: Pre-load embeddings model, warm ChromaDB cache
    logger.debug("Pre-warming search pipeline")
    return {"status": "ok"}


# =============================================================================
# WebSocket for Real-time Chat
# =============================================================================


class ConnectionManager:
    """Manage WebSocket connections."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info("WebSocket connected", session_id=session_id)

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info("WebSocket disconnected", session_id=session_id)

    async def send_json(self, session_id: str, data: dict):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(data)


ws_manager = ConnectionManager()


@app.websocket("/ws/chat/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time chat.

    Connect to stream chat responses token by token.

    Message format (client → server):
    ```json
    {"type": "question", "content": "What is in this document?"}
    ```

    Message format (server → client):
    ```json
    {"type": "start"}
    {"type": "token", "content": "The"}
    {"type": "token", "content": " document"}
    {"type": "token", "content": " contains"}
    {"type": "sources", "sources": ["doc1.pdf", "doc2.docx"]}
    {"type": "end"}
    ```
    """
    await ws_manager.connect(websocket, session_id)

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()

            if data.get("type") == "question":
                question = data.get("content", "")
                logger.info("Chat question received", session_id=session_id, question=question[:50])

                # Send start marker
                await websocket.send_json({"type": "start"})

                # TODO: Implement actual streaming with OpenAI
                # For now, send a mock response
                response = f"This is a streaming response to: {question}"
                for word in response.split():
                    await websocket.send_json({"type": "token", "content": word + " "})

                # Send sources
                await websocket.send_json({"type": "sources", "sources": []})

                # Send end marker
                await websocket.send_json({"type": "end"})

    except WebSocketDisconnect:
        ws_manager.disconnect(session_id)


# =============================================================================
# Include Routers
# =============================================================================

app.include_router(search.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(sync.router, prefix="/api/v1")


# =============================================================================
# Entry Point
# =============================================================================


def main():
    """Run the server."""
    uvicorn.run(
        "oslash.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
