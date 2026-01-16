"""CRUD operations for database models."""

from datetime import datetime
from typing import Optional, Sequence
import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from oslash.db.models import (
    ChatSession,
    ConnectedAccount,
    Document,
    SearchHistory,
    SyncState,
)


# =============================================================================
# Document CRUD
# =============================================================================


async def create_document(
    db: AsyncSession,
    *,
    source: str,
    source_id: str,
    title: str,
    path: Optional[str] = None,
    author: Optional[str] = None,
    content_type: Optional[str] = None,
    raw_content: Optional[str] = None,
    url: Optional[str] = None,
    created_at: Optional[datetime] = None,
    modified_at: Optional[datetime] = None,
) -> Document:
    """Create or update a document."""
    doc_id = f"{source}:{source_id}"

    # Check if exists
    existing = await db.get(Document, doc_id)
    if existing:
        # Update existing
        existing.title = title
        existing.path = path
        existing.author = author
        existing.content_type = content_type
        existing.raw_content = raw_content
        existing.url = url
        existing.modified_at = modified_at
        existing.last_synced = datetime.utcnow()
        await db.flush()
        return existing

    # Create new
    doc = Document(
        id=doc_id,
        source=source,
        source_id=source_id,
        title=title,
        path=path,
        author=author,
        content_type=content_type,
        raw_content=raw_content,
        url=url,
        created_at=created_at,
        modified_at=modified_at,
        last_synced=datetime.utcnow(),
    )
    db.add(doc)
    await db.flush()
    return doc


async def get_document(db: AsyncSession, doc_id: str) -> Optional[Document]:
    """Get a document by ID."""
    return await db.get(Document, doc_id)


async def get_documents_by_source(
    db: AsyncSession, source: str, limit: int = 100, offset: int = 0
) -> Sequence[Document]:
    """Get documents by source."""
    result = await db.execute(
        select(Document)
        .where(Document.source == source)
        .order_by(Document.modified_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


async def delete_document(db: AsyncSession, doc_id: str) -> bool:
    """Delete a document."""
    result = await db.execute(delete(Document).where(Document.id == doc_id))
    return result.rowcount > 0


async def count_documents(db: AsyncSession, source: Optional[str] = None) -> int:
    """Count documents, optionally by source."""
    from sqlalchemy import func

    query = select(func.count(Document.id))
    if source:
        query = query.where(Document.source == source)
    result = await db.execute(query)
    return result.scalar() or 0


# =============================================================================
# SyncState CRUD
# =============================================================================


async def get_or_create_sync_state(db: AsyncSession, source: str) -> SyncState:
    """Get or create sync state for a source."""
    result = await db.execute(
        select(SyncState).where(SyncState.source == source)
    )
    state = result.scalar_one_or_none()

    if not state:
        state = SyncState(source=source, status="idle")
        db.add(state)
        await db.flush()

    return state


async def update_sync_state(
    db: AsyncSession,
    source: str,
    *,
    status: Optional[str] = None,
    last_sync_token: Optional[str] = None,
    error_message: Optional[str] = None,
    document_count: Optional[int] = None,
) -> SyncState:
    """Update sync state for a source."""
    state = await get_or_create_sync_state(db, source)

    if status is not None:
        state.status = status
        if status == "idle":
            state.last_synced_at = datetime.utcnow()
    if last_sync_token is not None:
        state.last_sync_token = last_sync_token
    if error_message is not None:
        state.error_message = error_message
    if document_count is not None:
        state.document_count = document_count

    await db.flush()
    return state


async def get_all_sync_states(db: AsyncSession) -> Sequence[SyncState]:
    """Get all sync states."""
    result = await db.execute(select(SyncState))
    return result.scalars().all()


async def delete_sync_state(db: AsyncSession, source: str) -> bool:
    """Delete sync state for a source."""
    result = await db.execute(
        delete(SyncState).where(SyncState.source == source)
    )
    return result.rowcount > 0


async def delete_documents_by_source(db: AsyncSession, source: str) -> int:
    """Delete all documents for a source."""
    result = await db.execute(
        delete(Document).where(Document.source == source)
    )
    return result.rowcount


# =============================================================================
# ConnectedAccount CRUD
# =============================================================================


async def create_connected_account(
    db: AsyncSession,
    *,
    source: str,
    email: Optional[str] = None,
    token_encrypted: Optional[str] = None,
    refresh_token_encrypted: Optional[str] = None,
    expires_at: Optional[datetime] = None,
) -> ConnectedAccount:
    """Create or update a connected account."""
    result = await db.execute(
        select(ConnectedAccount).where(ConnectedAccount.source == source)
    )
    account = result.scalar_one_or_none()

    if account:
        account.email = email
        account.token_encrypted = token_encrypted
        account.refresh_token_encrypted = refresh_token_encrypted
        account.expires_at = expires_at
        await db.flush()
        return account

    account = ConnectedAccount(
        id=str(uuid.uuid4()),
        source=source,
        email=email,
        token_encrypted=token_encrypted,
        refresh_token_encrypted=refresh_token_encrypted,
        expires_at=expires_at,
    )
    db.add(account)
    await db.flush()
    return account


async def get_connected_account(
    db: AsyncSession, source: str
) -> Optional[ConnectedAccount]:
    """Get connected account by source."""
    result = await db.execute(
        select(ConnectedAccount).where(ConnectedAccount.source == source)
    )
    return result.scalar_one_or_none()


async def get_all_connected_accounts(db: AsyncSession) -> Sequence[ConnectedAccount]:
    """Get all connected accounts."""
    result = await db.execute(select(ConnectedAccount))
    return result.scalars().all()


async def delete_connected_account(db: AsyncSession, source: str) -> bool:
    """Delete a connected account."""
    result = await db.execute(
        delete(ConnectedAccount).where(ConnectedAccount.source == source)
    )
    return result.rowcount > 0


async def upsert_connected_account(
    db: AsyncSession,
    *,
    source: str,
    email: Optional[str] = None,
    token_encrypted: Optional[str] = None,
    refresh_token_encrypted: Optional[str] = None,
    expires_at: Optional[datetime] = None,
) -> ConnectedAccount:
    """Create or update a connected account (alias for create_connected_account)."""
    return await create_connected_account(
        db,
        source=source,
        email=email,
        token_encrypted=token_encrypted,
        refresh_token_encrypted=refresh_token_encrypted,
        expires_at=expires_at,
    )


async def update_connected_account(
    db: AsyncSession,
    source: str,
    *,
    email: Optional[str] = None,
    token_encrypted: Optional[str] = None,
    refresh_token_encrypted: Optional[str] = None,
    expires_at: Optional[datetime] = None,
) -> Optional[ConnectedAccount]:
    """Update an existing connected account."""
    result = await db.execute(
        select(ConnectedAccount).where(ConnectedAccount.source == source)
    )
    account = result.scalar_one_or_none()

    if not account:
        return None

    if email is not None:
        account.email = email
    if token_encrypted is not None:
        account.token_encrypted = token_encrypted
    if refresh_token_encrypted is not None:
        account.refresh_token_encrypted = refresh_token_encrypted
    if expires_at is not None:
        account.expires_at = expires_at

    await db.flush()
    return account


# =============================================================================
# ChatSession CRUD
# =============================================================================


async def create_chat_session(
    db: AsyncSession,
    session_id: Optional[str] = None,
    title: Optional[str] = None,
) -> ChatSession:
    """Create a new chat session."""
    session = ChatSession(
        id=session_id or str(uuid.uuid4()),
        title=title,
        messages=[],
        context_document_ids=[],
    )
    db.add(session)
    await db.flush()
    return session


async def get_chat_session(
    db: AsyncSession, session_id: str
) -> Optional[ChatSession]:
    """Get a chat session by ID."""
    return await db.get(ChatSession, session_id)


async def update_chat_session(
    db: AsyncSession,
    session_id: str,
    *,
    title: Optional[str] = None,
    messages: Optional[list] = None,
    context_document_ids: Optional[list] = None,
) -> Optional[ChatSession]:
    """Update a chat session."""
    session = await get_chat_session(db, session_id)
    if not session:
        return None

    if title is not None:
        session.title = title
    if messages is not None:
        session.messages = messages
    if context_document_ids is not None:
        session.context_document_ids = context_document_ids

    await db.flush()
    return session


async def add_message_to_session(
    db: AsyncSession,
    session_id: str,
    role: str,
    content: str,
    sources: Optional[list[str]] = None,
) -> Optional[ChatSession]:
    """Add a message to a chat session."""
    session = await get_chat_session(db, session_id)
    if not session:
        return None

    messages = session.messages or []
    messages.append({
        "role": role,
        "content": content,
        "sources": sources or [],
        "timestamp": datetime.utcnow().isoformat(),
    })
    session.messages = messages
    await db.flush()
    return session


async def get_recent_sessions(
    db: AsyncSession, limit: int = 10
) -> Sequence[ChatSession]:
    """Get recent chat sessions."""
    result = await db.execute(
        select(ChatSession)
        .order_by(ChatSession.updated_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


async def delete_chat_session(db: AsyncSession, session_id: str) -> bool:
    """Delete a chat session."""
    result = await db.execute(
        delete(ChatSession).where(ChatSession.id == session_id)
    )
    return result.rowcount > 0


# =============================================================================
# SearchHistory CRUD
# =============================================================================


async def add_search_history(
    db: AsyncSession,
    query: str,
    result_count: int = 0,
    selected_result_id: Optional[str] = None,
) -> SearchHistory:
    """Add a search to history."""
    entry = SearchHistory(
        query=query,
        result_count=result_count,
        selected_result_id=selected_result_id,
    )
    db.add(entry)
    await db.flush()
    return entry


async def get_search_history(
    db: AsyncSession, limit: int = 10
) -> Sequence[SearchHistory]:
    """Get recent search history."""
    result = await db.execute(
        select(SearchHistory)
        .order_by(SearchHistory.searched_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


async def get_search_suggestions(
    db: AsyncSession, partial_query: str, limit: int = 5
) -> Sequence[str]:
    """Get search suggestions based on history."""
    result = await db.execute(
        select(SearchHistory.query)
        .where(SearchHistory.query.ilike(f"{partial_query}%"))
        .distinct()
        .limit(limit)
    )
    return result.scalars().all()


async def clear_search_history(db: AsyncSession) -> int:
    """Clear all search history."""
    result = await db.execute(delete(SearchHistory))
    return result.rowcount

