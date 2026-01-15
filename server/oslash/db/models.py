"""SQLAlchemy database models."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    JSON,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class Document(Base):
    """Document metadata stored in SQLite."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    path: Mapped[Optional[str]] = mapped_column(String(1000))
    author: Mapped[Optional[str]] = mapped_column(String(255))
    content_type: Mapped[Optional[str]] = mapped_column(String(100))
    raw_content: Mapped[Optional[str]] = mapped_column(Text)
    url: Mapped[Optional[str]] = mapped_column(String(2000))
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    modified_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_synced: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_source_source_id"),
        Index("ix_documents_source_modified", "source", "modified_at"),
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, source={self.source}, title={self.title[:30]})>"


class SyncState(Base):
    """Track sync state for each source."""

    __tablename__ = "sync_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    last_sync_token: Mapped[Optional[str]] = mapped_column(String(500))
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="idle")
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    document_count: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<SyncState(source={self.source}, status={self.status})>"


class ConnectedAccount(Base):
    """OAuth tokens and account info for connected services."""

    __tablename__ = "connected_accounts"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    email: Mapped[Optional[str]] = mapped_column(String(255))
    connected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    token_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    refresh_token_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return f"<ConnectedAccount(source={self.source}, email={self.email})>"


class ChatSession(Base):
    """Chat session history."""

    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    title: Mapped[Optional[str]] = mapped_column(String(500))
    messages: Mapped[Optional[dict]] = mapped_column(JSON, default=list)
    context_document_ids: Mapped[Optional[dict]] = mapped_column(JSON, default=list)

    def __repr__(self) -> str:
        return f"<ChatSession(id={self.id}, title={self.title})>"


class SearchHistory(Base):
    """Search history for suggestions and analytics."""

    __tablename__ = "search_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query: Mapped[str] = mapped_column(String(500), nullable=False)
    searched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    selected_result_id: Mapped[Optional[str]] = mapped_column(String(255))

    __table_args__ = (Index("ix_search_history_query", "query"),)

    def __repr__(self) -> str:
        return f"<SearchHistory(query={self.query[:30]})>"

