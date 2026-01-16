"""API client for OSlash Local server."""

import json
from typing import AsyncIterator, Optional
from dataclasses import dataclass

import httpx


@dataclass
class SearchResult:
    """A single search result."""
    document_id: str
    title: str
    path: Optional[str]
    source: str
    author: Optional[str]
    url: Optional[str]
    snippet: str
    score: float
    modified_at: Optional[str]
    chunk_id: str
    section_title: Optional[str]


@dataclass
class SearchResponse:
    """Search response from API."""
    query: str
    results: list[SearchResult]
    total_found: int
    search_time_ms: float


@dataclass
class AccountStatus:
    """Status of a connected account."""
    connected: bool
    email: Optional[str]
    document_count: int
    last_sync: Optional[str]
    status: str


@dataclass
class ServerStatus:
    """Server status response."""
    online: bool
    version: str
    accounts: dict[str, AccountStatus]
    total_documents: int
    total_chunks: int


class ApiClient:
    """Async API client for OSlash Local server."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("ApiClient must be used as async context manager")
        return self._client

    async def health_check(self) -> bool:
        """Check if server is healthy."""
        try:
            response = await self.client.get("/health", timeout=2.0)
            return response.status_code == 200
        except Exception:
            return False

    async def get_status(self) -> ServerStatus:
        """Get server status including connected accounts."""
        response = await self.client.get("/api/v1/status")
        response.raise_for_status()
        data = response.json()

        accounts = {}
        for source, acc_data in data.get("accounts", {}).items():
            accounts[source] = AccountStatus(
                connected=acc_data.get("connected", False),
                email=acc_data.get("email"),
                document_count=acc_data.get("document_count", 0),
                last_sync=acc_data.get("last_sync"),
                status=acc_data.get("status", "idle"),
            )

        return ServerStatus(
            online=data.get("online", True),
            version=data.get("version", "unknown"),
            accounts=accounts,
            total_documents=data.get("total_documents", 0),
            total_chunks=data.get("total_chunks", 0),
        )

    async def search(
        self,
        query: str,
        sources: Optional[list[str]] = None,
        limit: int = 10,
    ) -> SearchResponse:
        """Perform a search query."""
        payload = {"query": query, "limit": limit}
        if sources:
            payload["sources"] = sources

        response = await self.client.post("/api/v1/search/", json=payload)
        response.raise_for_status()
        data = response.json()

        results = [
            SearchResult(
                document_id=r.get("document_id", ""),
                title=r.get("title", "Untitled"),
                path=r.get("path"),
                source=r.get("source", "unknown"),
                author=r.get("author"),
                url=r.get("url"),
                snippet=r.get("snippet", ""),
                score=r.get("score", 0.0),
                modified_at=r.get("modified_at"),
                chunk_id=r.get("chunk_id", ""),
                section_title=r.get("section_title"),
            )
            for r in data.get("results", [])
        ]

        return SearchResponse(
            query=data.get("query", query),
            results=results,
            total_found=data.get("total_found", len(results)),
            search_time_ms=data.get("search_time_ms", 0.0),
        )

    async def chat(
        self,
        question: str,
        session_id: Optional[str] = None,
        sources: Optional[list[str]] = None,
    ) -> dict:
        """Send a chat message and get response (non-streaming)."""
        payload = {"query": question}
        if session_id:
            payload["session_id"] = session_id
        if sources:
            payload["sources"] = sources

        response = await self.client.post("/api/v1/chat/", json=payload)
        response.raise_for_status()
        return response.json()

    async def chat_stream(
        self,
        question: str,
        session_id: Optional[str] = None,
        sources: Optional[list[str]] = None,
    ) -> AsyncIterator[dict]:
        """Stream chat response token by token."""
        payload = {"query": question}
        if session_id:
            payload["session_id"] = session_id
        if sources:
            payload["sources"] = sources

        async with self.client.stream(
            "POST",
            "/api/v1/chat/stream/",
            json=payload,
            timeout=60.0,
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("event:"):
                    event_type = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    data_str = line.split(":", 1)[1].strip()
                    if data_str and data_str != "[DONE]":
                        try:
                            data = json.loads(data_str)
                            yield {"type": event_type, **data}
                        except json.JSONDecodeError:
                            yield {"type": event_type, "content": data_str}

    async def sync(self, source: Optional[str] = None, full: bool = False) -> dict:
        """Trigger sync for a source or all sources."""
        if source:
            response = await self.client.post(
                f"/api/v1/sync/{source}",
                params={"full": full},
            )
        else:
            response = await self.client.post(
                "/api/v1/sync",
                params={"full": full},
            )
        response.raise_for_status()
        return response.json()

    async def get_sync_status(self) -> dict:
        """Get sync status for all sources."""
        response = await self.client.get("/api/v1/sync/status")
        response.raise_for_status()
        return response.json()


# Singleton instance for convenience
_api: Optional[ApiClient] = None


def get_api() -> ApiClient:
    """Get the global API client instance."""
    global _api
    if _api is None:
        _api = ApiClient()
    return _api

