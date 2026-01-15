"""Sync API endpoints."""

import asyncio
from typing import Optional

from fastapi import APIRouter, BackgroundTasks

from oslash.models.schemas import Source, SyncResult, SyncStatus

router = APIRouter(prefix="/sync", tags=["Sync"])


async def run_sync_task(source: Source) -> SyncResult:
    """
    Background task to sync a source.

    TODO: Implement actual sync with connectors.
    """
    # Simulate sync work
    await asyncio.sleep(2)

    return SyncResult(
        success=True,
        source=source,
        added=0,
        updated=0,
        deleted=0,
        errors=[],
        duration_seconds=2.0,
    )


@router.post("/", response_model=SyncResult)
async def sync_all(background_tasks: BackgroundTasks) -> SyncResult:
    """
    Trigger sync for all connected sources.

    Runs in background - returns immediately.
    """
    # TODO: Get connected sources from database
    connected_sources = []  # Will be populated from DB

    for source in connected_sources:
        background_tasks.add_task(run_sync_task, source)

    return SyncResult(
        success=True,
        added=0,
        updated=0,
        deleted=0,
        errors=[],
        duration_seconds=0,
    )


@router.post("/{source}", response_model=SyncResult)
async def sync_source(source: Source, background_tasks: BackgroundTasks) -> SyncResult:
    """
    Trigger sync for a specific source.
    """
    background_tasks.add_task(run_sync_task, source)

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
    # TODO: Get actual status from database
    statuses = {}
    for source in Source:
        statuses[source.value] = SyncStatus(
            source=source,
            status="idle",
            progress=None,
            last_sync=None,
            document_count=0,
            error=None,
        ).model_dump()

    return {"sources": statuses}


@router.get("/status/{source}", response_model=SyncStatus)
async def get_source_sync_status(source: Source) -> SyncStatus:
    """
    Get sync status for a specific source.
    """
    # TODO: Get actual status from database
    return SyncStatus(
        source=source,
        status="idle",
        progress=None,
        last_sync=None,
        document_count=0,
        error=None,
    )

