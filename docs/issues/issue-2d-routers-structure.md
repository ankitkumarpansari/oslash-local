## Description
Learn how to organize a FastAPI project with routers, making the codebase maintainable as it grows.

## 🎓 Learning Objectives
By the end of this issue, you will understand:
- [ ] Why we need routers (code organization)
- [ ] How to create and use APIRouter
- [ ] How to structure a FastAPI project
- [ ] How to use dependency injection
- [ ] How to add middleware

## 📚 Concepts to Learn

### 1. The Problem: One Big File

Without routers, everything goes in one file:
```python
# main.py - Gets HUGE and unmaintainable!
@app.get("/health")
@app.get("/api/v1/status")
@app.post("/api/v1/search")
@app.post("/api/v1/chat")
@app.get("/api/v1/auth/google/url")
@app.get("/api/v1/auth/google/callback")
@app.get("/api/v1/auth/slack/url")
@app.get("/api/v1/auth/slack/callback")
@app.post("/api/v1/sync")
# ... 50 more endpoints ...
```

### 2. The Solution: Routers

Split into logical modules:
```
server/oslash/
├── main.py           # Just imports and combines routers
├── api/
│   ├── search.py     # /api/v1/search endpoints
│   ├── chat.py       # /api/v1/chat endpoints
│   ├── auth.py       # /api/v1/auth/* endpoints
│   └── sync.py       # /api/v1/sync endpoints
```

### 3. How Routers Work

```python
# api/search.py
from fastapi import APIRouter

router = APIRouter(
    prefix="/search",      # All routes start with /search
    tags=["Search"]        # Groups in Swagger docs
)

@router.post("/")          # Becomes POST /api/v1/search/
async def search():
    pass

@router.get("/history")    # Becomes GET /api/v1/search/history
async def get_history():
    pass

# main.py
from fastapi import FastAPI
from api.search import router as search_router

app = FastAPI()
app.include_router(search_router, prefix="/api/v1")
```

## 🛠️ Hands-On Exercise

### Step 1: Create Router Structure

Create the following files:

**`server/learn/routers/__init__.py`:**
```python
"""Router modules for the API."""
```

**`server/learn/routers/search.py`:**
```python
"""Search API endpoints."""

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

router = APIRouter(
    prefix="/search",
    tags=["Search"],
    responses={404: {"description": "Not found"}},
)

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2)
    limit: int = Field(default=10, ge=1, le=100)

class SearchResult(BaseModel):
    id: str
    title: str
    score: float

class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total: int

@router.post("/", response_model=SearchResponse)
async def search(request: SearchRequest):
    """
    Search for documents.
    
    - **query**: Search query (min 2 characters)
    - **limit**: Max results (1-100)
    """
    # Mock implementation
    return SearchResponse(
        query=request.query,
        results=[
            SearchResult(id="1", title=f"Result for {request.query}", score=0.95)
        ],
        total=1
    )

@router.get("/history")
async def get_search_history(limit: int = Query(default=10, le=50)):
    """Get recent search history."""
    return {
        "history": [
            {"query": "Q4 report", "timestamp": "2024-01-15T10:00:00"},
            {"query": "budget", "timestamp": "2024-01-15T09:30:00"},
        ][:limit]
    }

@router.delete("/history")
async def clear_search_history():
    """Clear search history."""
    return {"message": "History cleared"}
```

**`server/learn/routers/auth.py`:**
```python
"""Authentication API endpoints."""

from fastapi import APIRouter, HTTPException
from enum import Enum

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

class Provider(str, Enum):
    GDRIVE = "gdrive"
    GMAIL = "gmail"
    SLACK = "slack"
    HUBSPOT = "hubspot"

# Mock OAuth URLs
OAUTH_URLS = {
    Provider.GDRIVE: "https://accounts.google.com/oauth?...",
    Provider.GMAIL: "https://accounts.google.com/oauth?...",
    Provider.SLACK: "https://slack.com/oauth?...",
    Provider.HUBSPOT: "https://app.hubspot.com/oauth?...",
}

@router.get("/{provider}/url")
async def get_auth_url(provider: Provider):
    """
    Get OAuth authorization URL for a provider.
    
    - **provider**: One of: gdrive, gmail, slack, hubspot
    """
    return {
        "provider": provider,
        "url": OAUTH_URLS[provider],
        "message": "Open this URL to authorize"
    }

@router.get("/{provider}/callback")
async def oauth_callback(provider: Provider, code: str, state: str):
    """
    Handle OAuth callback.
    This is called by the OAuth provider after user authorizes.
    """
    # In real implementation: exchange code for tokens
    return {
        "provider": provider,
        "status": "connected",
        "message": f"Successfully connected {provider}"
    }

@router.delete("/{provider}")
async def disconnect(provider: Provider):
    """Disconnect an account."""
    return {
        "provider": provider,
        "status": "disconnected"
    }

@router.get("/status")
async def get_auth_status():
    """Get connection status for all providers."""
    return {
        "accounts": {
            "gdrive": {"connected": True, "email": "user@gmail.com"},
            "gmail": {"connected": True, "email": "user@gmail.com"},
            "slack": {"connected": False},
            "hubspot": {"connected": False},
        }
    }
```

**`server/learn/routers/sync.py`:**
```python
"""Sync API endpoints."""

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from enum import Enum
import asyncio

router = APIRouter(
    prefix="/sync",
    tags=["Sync"],
)

class Source(str, Enum):
    GDRIVE = "gdrive"
    GMAIL = "gmail"
    SLACK = "slack"
    HUBSPOT = "hubspot"

class SyncResult(BaseModel):
    source: str
    added: int
    updated: int
    deleted: int
    errors: list[str]

# Simulate background sync
async def run_sync(source: str):
    """Background task for syncing."""
    print(f"Starting sync for {source}...")
    await asyncio.sleep(2)  # Simulate work
    print(f"Completed sync for {source}")

@router.post("/")
async def sync_all(background_tasks: BackgroundTasks):
    """
    Trigger sync for all connected sources.
    Runs in background - returns immediately.
    """
    for source in Source:
        background_tasks.add_task(run_sync, source.value)
    
    return {
        "message": "Sync started for all sources",
        "status": "running"
    }

@router.post("/{source}")
async def sync_source(source: Source, background_tasks: BackgroundTasks):
    """Trigger sync for a specific source."""
    background_tasks.add_task(run_sync, source.value)
    return {
        "message": f"Sync started for {source}",
        "status": "running"
    }

@router.get("/status")
async def get_sync_status():
    """Get sync status for all sources."""
    return {
        "sources": {
            "gdrive": {"status": "idle", "last_sync": "2024-01-15T10:00:00", "documents": 1234},
            "gmail": {"status": "idle", "last_sync": "2024-01-15T10:00:00", "documents": 5678},
            "slack": {"status": "syncing", "progress": 45},
            "hubspot": {"status": "error", "error": "Rate limit exceeded"},
        }
    }
```

### Step 2: Create Main App with Routers

**`server/learn/04_routers.py`:**
```python
"""
FastAPI Routers - Learning Exercise
Run with: uvicorn learn.04_routers:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers
from learn.routers import search, auth, sync

# Create app
app = FastAPI(
    title="OSlash Local API",
    description="RAG-powered file search",
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check (not in a router - it's simple)
@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "version": "0.1.0"}

# Include routers with /api/v1 prefix
app.include_router(search.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(sync.router, prefix="/api/v1")

# Now we have these endpoints:
# GET  /health
# POST /api/v1/search/
# GET  /api/v1/search/history
# DELETE /api/v1/search/history
# GET  /api/v1/auth/{provider}/url
# GET  /api/v1/auth/{provider}/callback
# DELETE /api/v1/auth/{provider}
# GET  /api/v1/auth/status
# POST /api/v1/sync/
# POST /api/v1/sync/{source}
# GET  /api/v1/sync/status
```

### Step 3: Test the Organized API

```bash
cd server
uvicorn learn.04_routers:app --reload

# View organized Swagger docs
open http://localhost:8000/docs
# Notice: Endpoints are grouped by tags!

# Test search
curl -X POST http://localhost:8000/api/v1/search/ \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}'

# Test auth
curl http://localhost:8000/api/v1/auth/gdrive/url
curl http://localhost:8000/api/v1/auth/status

# Test sync
curl -X POST http://localhost:8000/api/v1/sync/
curl http://localhost:8000/api/v1/sync/status
```

## 📁 Final Project Structure

```
server/oslash/
├── __init__.py
├── main.py                 # App creation, router includes
├── config.py               # Settings
├── api/
│   ├── __init__.py
│   ├── search.py          # Search router
│   ├── chat.py            # Chat router
│   ├── auth.py            # Auth router
│   └── sync.py            # Sync router
├── core/
│   ├── __init__.py
│   ├── embeddings.py      # OpenAI embeddings
│   ├── vectorstore.py     # ChromaDB
│   └── search.py          # Search logic
├── connectors/
│   ├── __init__.py
│   ├── base.py            # Base connector
│   ├── gdrive.py          # Google Drive
│   └── ...
└── models/
    ├── __init__.py
    ├── document.py        # Document model
    └── chunk.py           # Chunk model
```

## ✅ Acceptance Criteria
- [ ] Can create APIRouter with prefix and tags
- [ ] Can organize endpoints into separate files
- [ ] Can include routers in main app
- [ ] Can use BackgroundTasks for async jobs
- [ ] Understand the project structure pattern

## 🔗 Resources
- [FastAPI Bigger Applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
- [APIRouter Documentation](https://fastapi.tiangolo.com/reference/apirouter/)

## ⏱️ Estimated Time
2 hours

## ➡️ Next
After completing this, move to Issue #2e: WebSockets for Real-time Streaming

