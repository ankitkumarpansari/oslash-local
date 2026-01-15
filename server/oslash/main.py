"""OSlash Local Server - Main entry point."""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="OSlash Local",
    description="RAG-powered file search server",
    version="0.1.0",
)

# Configure CORS for extension communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow extension from any origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}


@app.get("/api/v1/status")
async def get_status():
    """Get server status and connected accounts."""
    # TODO: Implement actual status
    return {
        "online": True,
        "accounts": {
            "gdrive": {"connected": False},
            "gmail": {"connected": False},
            "slack": {"connected": False},
            "hubspot": {"connected": False},
        },
        "totalDocuments": 0,
        "totalChunks": 0,
    }


@app.post("/api/v1/search")
async def search(request: dict):
    """Search documents."""
    query = request.get("query", "")
    limit = request.get("limit", 10)

    # TODO: Implement actual search
    return {
        "query": query,
        "results": [],
        "totalFound": 0,
    }


@app.post("/api/v1/warm")
async def warm():
    """Pre-warm the search pipeline."""
    # TODO: Implement pre-warming
    return {"status": "ok"}


@app.post("/api/v1/sync")
async def sync():
    """Trigger manual sync."""
    # TODO: Implement sync
    return {
        "success": True,
        "added": 0,
        "updated": 0,
        "deleted": 0,
    }


def main():
    """Run the server."""
    uvicorn.run(
        "oslash.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()

