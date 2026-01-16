"""Background sync scheduler using APScheduler."""

import asyncio
from datetime import datetime
from typing import Callable, Optional

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobExecutionEvent

from oslash.config import get_settings
from oslash.db import get_db_context, crud
from oslash.models.schemas import Source

logger = structlog.get_logger(__name__)


class SyncScheduler:
    """
    Background scheduler for automatic syncing of connected sources.

    Uses APScheduler to run incremental syncs at configurable intervals.
    """

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.settings = get_settings()
        self._is_running = False
        self._sync_callbacks: list[Callable] = []

    def start(self) -> None:
        """Start the scheduler with configured sync job."""
        if self._is_running:
            logger.warning("Scheduler already running")
            return

        # Add sync job
        self.scheduler.add_job(
            self._sync_all_sources,
            trigger=IntervalTrigger(minutes=self.settings.sync_interval_minutes),
            id="sync_all_sources",
            name="Sync All Connected Sources",
            replace_existing=True,
            max_instances=1,  # Don't overlap syncs
        )

        # Add event listeners
        self.scheduler.add_listener(
            self._on_job_executed,
            EVENT_JOB_EXECUTED,
        )
        self.scheduler.add_listener(
            self._on_job_error,
            EVENT_JOB_ERROR,
        )

        self.scheduler.start()
        self._is_running = True

        logger.info(
            "Sync scheduler started",
            interval_minutes=self.settings.sync_interval_minutes,
        )

    def stop(self) -> None:
        """Stop the scheduler."""
        if not self._is_running:
            return

        self.scheduler.shutdown(wait=False)
        self._is_running = False
        logger.info("Sync scheduler stopped")

    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._is_running

    def add_sync_callback(self, callback: Callable) -> None:
        """Add a callback to be called after each sync."""
        self._sync_callbacks.append(callback)

    async def trigger_sync(
        self,
        source: Optional[Source] = None,
        full: bool = False,
    ) -> dict:
        """
        Manually trigger a sync.

        Args:
            source: Specific source to sync, or None for all
            full: Whether to perform a full sync

        Returns:
            Dict with sync status
        """
        if source:
            return await self._sync_source(source.value, full)
        else:
            return await self._sync_all_sources(full)

    async def _sync_all_sources(self, full: bool = False) -> dict:
        """Sync all connected sources."""
        logger.info("Starting sync for all sources", full=full)

        results = {}
        async with get_db_context() as db:
            accounts = await crud.get_all_connected_accounts(db)

        for account in accounts:
            source = account.source
            try:
                result = await self._sync_source(source, full)
                results[source] = result
            except Exception as e:
                logger.error("Sync failed for source", source=source, error=str(e))
                results[source] = {"success": False, "error": str(e)}

        # Call callbacks
        for callback in self._sync_callbacks:
            try:
                await callback(results)
            except Exception as e:
                logger.error("Sync callback failed", error=str(e))

        return results

    async def _sync_source(self, source: str, full: bool = False) -> dict:
        """Sync a single source."""
        from oslash.connectors import (
            create_gdrive_connector,
            create_gmail_connector,
            create_slack_connector,
            create_hubspot_connector,
        )

        logger.info("Starting sync", source=source, full=full)

        # Update status to syncing
        async with get_db_context() as db:
            await crud.update_sync_state(db, source, status="syncing")

        try:
            # Get credentials
            async with get_db_context() as db:
                account = await crud.get_connected_account(db, source)
                if not account or not account.token_encrypted:
                    raise ValueError(f"{source} not connected")

                import json
                credentials = json.loads(account.token_encrypted)

            # Create connector
            if source == "gdrive":
                connector = create_gdrive_connector()
            elif source == "gmail":
                connector = create_gmail_connector()
            elif source == "slack":
                connector = create_slack_connector()
            elif source == "hubspot":
                connector = create_hubspot_connector()
            else:
                raise ValueError(f"Unknown source: {source}")

            # Authenticate
            if not await connector.authenticate(credentials):
                raise ValueError("Authentication failed")

            # Run sync
            result = await connector.sync(full=full)

            # Update status
            async with get_db_context() as db:
                await crud.update_sync_state(
                    db,
                    source,
                    status="idle",
                    document_count=result.added + result.updated,
                    error_message=None,
                )

            logger.info(
                "Sync completed",
                source=source,
                added=result.added,
                updated=result.updated,
                deleted=result.deleted,
                duration=result.duration_seconds,
            )

            return {
                "success": result.success,
                "added": result.added,
                "updated": result.updated,
                "deleted": result.deleted,
                "errors": result.errors,
                "duration_seconds": result.duration_seconds,
            }

        except Exception as e:
            logger.error("Sync failed", source=source, error=str(e))

            # Update status to error
            async with get_db_context() as db:
                await crud.update_sync_state(
                    db,
                    source,
                    status="error",
                    error_message=str(e),
                )

            return {
                "success": False,
                "error": str(e),
            }

    def _on_job_executed(self, event: JobExecutionEvent) -> None:
        """Handle successful job execution."""
        logger.debug(
            "Scheduled job executed",
            job_id=event.job_id,
            scheduled_time=event.scheduled_run_time,
        )

    def _on_job_error(self, event: JobExecutionEvent) -> None:
        """Handle job execution error."""
        logger.error(
            "Scheduled job failed",
            job_id=event.job_id,
            exception=str(event.exception),
        )

    def get_next_run_time(self) -> Optional[datetime]:
        """Get the next scheduled sync time."""
        job = self.scheduler.get_job("sync_all_sources")
        if job:
            return job.next_run_time
        return None

    def get_status(self) -> dict:
        """Get scheduler status."""
        return {
            "is_running": self._is_running,
            "interval_minutes": self.settings.sync_interval_minutes,
            "next_run_time": self.get_next_run_time().isoformat() if self.get_next_run_time() else None,
        }


# Global scheduler instance
_scheduler: Optional[SyncScheduler] = None


def get_scheduler() -> SyncScheduler:
    """Get the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = SyncScheduler()
    return _scheduler


def start_scheduler() -> None:
    """Start the global scheduler."""
    scheduler = get_scheduler()
    scheduler.start()


def stop_scheduler() -> None:
    """Stop the global scheduler."""
    global _scheduler
    if _scheduler:
        _scheduler.stop()
        _scheduler = None

