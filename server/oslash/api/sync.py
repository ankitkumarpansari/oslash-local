"""Sync API endpoints."""

import asyncio
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Query

from oslash.db import get_db_context, crud
from oslash.models.schemas import Source, SyncResult, SyncStatus

router = APIRouter(prefix="/sync", tags=["Sync"])

# Track active sync tasks
_active_syncs: dict[str, bool] = {}


async def run_connector_sync(source: str, full: bool = False) -> SyncResult:
    """Run sync for a specific source."""
    from oslash.connectors import (
        create_gdrive_connector,
        create_gmail_connector,
        create_slack_connector,
        create_hubspot_connector,
    )

    # Create the appropriate connector
    if source == "gdrive":
        connector = create_gdrive_connector()
    elif source == "gmail":
        connector = create_gmail_connector()
    elif source == "slack":
        connector = create_slack_connector()
    elif source == "hubspot":
        connector = create_hubspot_connector()
    else:
        return SyncResult(
            success=False,
            source=Source(source),
            errors=[f"Connector not implemented for {source}"],
        )

    return await _run_connector(connector, source, full)


async def _run_connector(connector, source: str, full: bool = False) -> SyncResult:
    """Run a connector with credentials from database."""
    from oslash.connectors.base import BaseConnector

    # Get credentials from database
    async with get_db_context() as db:
        account = await crud.get_connected_account(db, source)
        if not account or not account.token_encrypted:
            return SyncResult(
                success=False,
                source=Source(source),
                errors=[f"{source} not connected"],
            )

        # TODO: Decrypt token
        # For now, assume token is stored as JSON
        import json
        try:
            credentials = json.loads(account.token_encrypted)
        except:
            return SyncResult(
                success=False,
                source=Source(source),
                errors=["Invalid credentials"],
            )

    # Authenticate
    if not await connector.authenticate(credentials):
        return SyncResult(
            success=False,
            source=Source(source),
            errors=["Authentication failed"],
        )

    # Run sync
    result = await connector.sync(full=full)
    return SyncResult(
        success=result.success,
        source=Source(source),
        added=result.added,
        updated=result.updated,
        deleted=result.deleted,
        errors=result.errors,
        duration_seconds=result.duration_seconds,
    )


async def run_sync_task(source: Source, full: bool = False) -> SyncResult:
    """
    Background task to sync a source.
    """
    global _active_syncs

    source_name = source.value
    if _active_syncs.get(source_name):
        return SyncResult(
            success=False,
            source=source,
            errors=["Sync already in progress"],
        )

    _active_syncs[source_name] = True

    try:
        # Update status to syncing
        async with get_db_context() as db:
            await crud.update_sync_state(db, source_name, status="syncing")

        # Run the appropriate connector
        if source in [Source.GDRIVE, Source.GMAIL, Source.SLACK, Source.HUBSPOT]:
            result = await run_connector_sync(source.value, full)
        else:
            result = SyncResult(success=False, source=source, errors=["Unknown source"])

        return result

    finally:
        _active_syncs[source_name] = False


@router.post("/", response_model=SyncResult)
async def sync_all(
    background_tasks: BackgroundTasks,
    full: bool = Query(default=False, description="Perform full sync instead of incremental"),
) -> SyncResult:
    """
    Trigger sync for all connected sources.

    Runs in background - returns immediately.
    """
    # Get connected sources from database
    async with get_db_context() as db:
        accounts = await crud.get_all_connected_accounts(db)
        connected_sources = [Source(acc.source) for acc in accounts]

    if not connected_sources:
        return SyncResult(
            success=True,
            added=0,
            updated=0,
            deleted=0,
            errors=["No sources connected"],
            duration_seconds=0,
        )

    for source in connected_sources:
        background_tasks.add_task(run_sync_task, source, full)

    return SyncResult(
        success=True,
        added=0,
        updated=0,
        deleted=0,
        errors=[],
        duration_seconds=0,
    )


@router.post("/{source}", response_model=SyncResult)
async def sync_source(
    source: Source,
    background_tasks: BackgroundTasks,
    full: bool = Query(default=False, description="Perform full sync instead of incremental"),
) -> SyncResult:
    """
    Trigger sync for a specific source.
    """
    # Check if source is connected
    async with get_db_context() as db:
        account = await crud.get_connected_account(db, source.value)
        if not account:
            return SyncResult(
                success=False,
                source=source,
                errors=[f"{source.value} is not connected"],
            )

    background_tasks.add_task(run_sync_task, source, full)

    return SyncResult(
        success=True,
        source=source,
        added=0,
        updated=0,
        deleted=0,
        errors=[],
        duration_seconds=0,
    )


@router.get("/status")
async def get_sync_status() -> dict:
    """
    Get sync status for all sources.
    """
    async with get_db_context() as db:
        sync_states = await crud.get_all_sync_states(db)
        state_map = {s.source: s for s in sync_states}

        statuses = {}
        for source in Source:
            state = state_map.get(source.value)
            statuses[source.value] = {
                "source": source.value,
                "status": state.status if state else "idle",
                "progress": None,
                "last_sync": state.last_synced_at.isoformat() if state and state.last_synced_at else None,
                "document_count": state.document_count if state else 0,
                "error": state.error_message if state else None,
                "is_syncing": _active_syncs.get(source.value, False),
            }

    return {"sources": statuses}


@router.get("/status/{source}", response_model=SyncStatus)
async def get_source_sync_status(source: Source) -> SyncStatus:
    """
    Get sync status for a specific source.
    """
    async with get_db_context() as db:
        state = await crud.get_or_create_sync_state(db, source.value)

    return SyncStatus(
        source=source,
        status=state.status,
        progress=None,
        last_sync=state.last_synced_at,
        document_count=state.document_count,
        error=state.error_message,
    )
