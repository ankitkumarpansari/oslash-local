"""Base connector class for all source connectors."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncGenerator, Optional

import structlog

from oslash.db.models import Document

logger = structlog.get_logger(__name__)


@dataclass
class SyncResult:
    """Result of a sync operation."""

    success: bool
    source: str
    added: int = 0
    updated: int = 0
    deleted: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0
    sync_token: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "source": self.source,
            "added": self.added,
            "updated": self.updated,
            "deleted": self.deleted,
            "errors": self.errors,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class FileInfo:
    """Information about a file from a source."""

    id: str
    name: str
    mime_type: str
    path: Optional[str] = None
    web_url: Optional[str] = None
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    size: Optional[int] = None
    owner: Optional[str] = None
    parent_id: Optional[str] = None


class BaseConnector(ABC):
    """
    Abstract base class for all source connectors.

    Each connector must implement:
    - authenticate(): Set up credentials
    - list_files(): Get list of files
    - get_file_content(): Download and extract text
    - sync(): Perform full or incremental sync
    """

    SOURCE_NAME: str = "unknown"

    def __init__(self):
        self.is_authenticated = False
        self.sync_token: Optional[str] = None
        self.last_sync: Optional[datetime] = None

    @abstractmethod
    async def authenticate(self, credentials: dict) -> bool:
        """
        Authenticate with the source.

        Args:
            credentials: OAuth tokens or API keys

        Returns:
            True if authentication successful
        """
        pass

    @abstractmethod
    async def list_files(
        self,
        folder_id: Optional[str] = None,
        page_token: Optional[str] = None,
    ) -> tuple[list[FileInfo], Optional[str]]:
        """
        List files from the source.

        Args:
            folder_id: Optional folder to list from
            page_token: Pagination token

        Returns:
            Tuple of (files, next_page_token)
        """
        pass

    @abstractmethod
    async def get_file_content(self, file_id: str) -> Optional[str]:
        """
        Download and extract text content from a file.

        Args:
            file_id: The file ID

        Returns:
            Extracted text content, or None if not extractable
        """
        pass

    @abstractmethod
    async def sync(self, full: bool = False) -> SyncResult:
        """
        Sync files from the source.

        Args:
            full: If True, perform full sync. Otherwise incremental.

        Returns:
            SyncResult with counts and status
        """
        pass

    async def iter_files(self) -> AsyncGenerator[FileInfo, None]:
        """
        Iterate through all files in the source.

        Yields:
            FileInfo objects
        """
        page_token = None
        while True:
            files, next_token = await self.list_files(page_token=page_token)
            for file in files:
                yield file
            if not next_token:
                break
            page_token = next_token

    def file_to_document(self, file: FileInfo, content: str) -> Document:
        """
        Convert a FileInfo to a Document model.

        Args:
            file: File information
            content: Extracted text content

        Returns:
            Document model instance
        """
        return Document(
            id=f"{self.SOURCE_NAME}:{file.id}",
            source=self.SOURCE_NAME,
            source_id=file.id,
            title=file.name,
            path=file.path,
            author=file.owner,
            content_type=self._get_content_type(file.mime_type),
            raw_content=content,
            url=file.web_url,
            created_at=file.created_at,
            modified_at=file.modified_at,
            last_synced=datetime.utcnow(),
        )

    def _get_content_type(self, mime_type: str) -> str:
        """Map MIME type to content type for chunking."""
        mime_map = {
            "application/vnd.google-apps.document": "document",
            "application/vnd.google-apps.spreadsheet": "spreadsheet",
            "application/vnd.google-apps.presentation": "presentation",
            "application/pdf": "pdf",
            "text/plain": "text",
            "text/html": "html",
            "text/markdown": "markdown",
            "message/rfc822": "email",
        }
        return mime_map.get(mime_type, "document")

