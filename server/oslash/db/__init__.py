"""Database module for OSlash Local."""

from oslash.db.session import get_db, get_db_context, init_db
from oslash.db.models import (
    Base,
    Document,
    SyncState,
    ConnectedAccount,
    ChatSession,
    SearchHistory,
)
from oslash.db import crud

__all__ = [
    # Session management
    "get_db",
    "get_db_context",
    "init_db",
    # Models
    "Base",
    "Document",
    "SyncState",
    "ConnectedAccount",
    "ChatSession",
    "SearchHistory",
    # CRUD module
    "crud",
]
