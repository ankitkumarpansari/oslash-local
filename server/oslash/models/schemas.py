"""Pydantic schemas for API requests and responses."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Source(str, Enum):
    """Available data sources."""

    GDRIVE = "gdrive"
    GMAIL = "gmail"
    SLACK = "slack"
    HUBSPOT = "hubspot"


# =============================================================================
# Search Schemas
# =============================================================================


class SearchRequest(BaseModel):
    """Search request body."""

    query: str = Field(..., min_length=2, max_length=500, description="Search query")
    limit: int = Field(default=10, ge=1, le=100, description="Max results to return")
    sources: Optional[list[Source]] = Field(default=None, description="Filter by sources")


class SearchResult(BaseModel):
    """Single search result."""

    id: str
    title: str
    source: Source
    path: Optional[str] = None
    author: Optional[str] = None
    snippet: Optional[str] = None
    url: str
    score: float = Field(ge=0, le=1)
    modified_at: Optional[datetime] = None


class SearchResponse(BaseModel):
    """Search response."""

    query: str
    results: list[SearchResult]
    total_found: int
    search_time_ms: float


# =============================================================================
# Chat Schemas
# =============================================================================


class ChatMessage(BaseModel):
    """Single chat message."""

    role: str = Field(..., pattern="^(user|assistant)$")
    content: str
    timestamp: Optional[datetime] = None
    sources: Optional[list[str]] = None


class ChatRequest(BaseModel):
    """Chat request body."""

    question: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None
    document_ids: Optional[list[str]] = None


class ChatResponse(BaseModel):
    """Chat response (for non-streaming)."""

    answer: str
    sources: list[str]
    session_id: str


# =============================================================================
# Auth Schemas
# =============================================================================


class AccountStatus(BaseModel):
    """Status of a connected account."""

    connected: bool
    email: Optional[str] = None
    document_count: int = 0
    last_sync: Optional[datetime] = None
    status: str = "idle"  # idle, syncing, error


class AuthUrlResponse(BaseModel):
    """OAuth URL response."""

    provider: Source
    url: str
    state: str


# =============================================================================
# Sync Schemas
# =============================================================================


class SyncStatus(BaseModel):
    """Sync status for a source."""

    source: Source
    status: str  # idle, syncing, error
    progress: Optional[int] = None
    last_sync: Optional[datetime] = None
    document_count: int = 0
    error: Optional[str] = None


class SyncResult(BaseModel):
    """Result of a sync operation."""

    success: bool
    source: Optional[Source] = None
    added: int = 0
    updated: int = 0
    deleted: int = 0
    errors: list[str] = []
    duration_seconds: float = 0


# =============================================================================
# Status Schemas
# =============================================================================


class ServerStatus(BaseModel):
    """Server status response."""

    online: bool = True
    version: str
    accounts: dict[str, AccountStatus]
    total_documents: int
    total_chunks: int

