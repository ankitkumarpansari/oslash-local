"""Google Drive connector for syncing documents."""

import io
import time
from datetime import datetime
from typing import Optional

import structlog
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError

from oslash.config import get_settings
from oslash.connectors.base import BaseConnector, FileInfo, SyncResult
from oslash.db import get_db_context, crud
from oslash.db.models import Document
from oslash.services.chunking import get_chunker
from oslash.services.embeddings import get_embedding_service
from oslash.vector import get_vector_store, Chunk

logger = structlog.get_logger(__name__)


class GoogleDriveConnector(BaseConnector):
    """
    Google Drive connector using Drive API v3.

    Supports:
    - Google Docs, Sheets, Slides (export as text)
    - PDFs, text files (download content)
    - Incremental sync with change tokens
    """

    SOURCE_NAME = "gdrive"

    # MIME types we can extract text from
    SUPPORTED_MIME_TYPES = {
        # Google native formats (export as text)
        "application/vnd.google-apps.document": "text/plain",
        "application/vnd.google-apps.spreadsheet": "text/csv",
        "application/vnd.google-apps.presentation": "text/plain",
        # Standard formats (download directly)
        "application/pdf": None,  # Requires PDF parsing
        "text/plain": "text/plain",
        "text/html": "text/html",
        "text/markdown": "text/markdown",
        "text/csv": "text/csv",
        "application/json": "application/json",
        "application/rtf": "text/plain",
    }

    # Skip these types
    SKIP_MIME_TYPES = {
        "application/vnd.google-apps.folder",
        "application/vnd.google-apps.shortcut",
        "application/vnd.google-apps.form",
        "application/vnd.google-apps.map",
        "application/vnd.google-apps.drawing",
        "application/vnd.google-apps.script",
        "image/",  # Skip images
        "video/",  # Skip videos
        "audio/",  # Skip audio
    }

    def __init__(self):
        super().__init__()
        self.service = None
        self.credentials = None
        self.settings = get_settings()

    async def authenticate(self, credentials: dict) -> bool:
        """
        Authenticate with Google Drive using OAuth tokens.

        Args:
            credentials: Dict with 'token', 'refresh_token', 'token_uri', etc.

        Returns:
            True if authentication successful
        """
        try:
            self.credentials = Credentials(
                token=credentials.get("token"),
                refresh_token=credentials.get("refresh_token"),
                token_uri=credentials.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=self.settings.google_client_id,
                client_secret=self.settings.google_client_secret,
            )

            # Build the Drive service
            self.service = build("drive", "v3", credentials=self.credentials)

            # Test the connection
            about = self.service.about().get(fields="user").execute()
            user_email = about.get("user", {}).get("emailAddress", "unknown")

            self.is_authenticated = True
            logger.info("Google Drive authenticated", email=user_email)

            return True

        except Exception as e:
            logger.error("Google Drive authentication failed", error=str(e))
            self.is_authenticated = False
            return False

    async def list_files(
        self,
        folder_id: Optional[str] = None,
        page_token: Optional[str] = None,
    ) -> tuple[list[FileInfo], Optional[str]]:
        """
        List files from Google Drive.

        Args:
            folder_id: Optional folder ID to list from (None = all files)
            page_token: Pagination token

        Returns:
            Tuple of (files, next_page_token)
        """
        if not self.service:
            raise RuntimeError("Not authenticated")

        try:
            # Build query
            query_parts = ["trashed = false"]
            if folder_id:
                query_parts.append(f"'{folder_id}' in parents")

            query = " and ".join(query_parts)

            # Request files
            request = self.service.files().list(
                q=query,
                pageSize=100,
                pageToken=page_token,
                fields="nextPageToken, files(id, name, mimeType, webViewLink, createdTime, modifiedTime, size, owners, parents)",
                orderBy="modifiedTime desc",
            )

            response = request.execute()

            files = []
            for item in response.get("files", []):
                # Skip unsupported types
                mime_type = item.get("mimeType", "")
                if self._should_skip(mime_type):
                    continue

                # Extract owner email
                owners = item.get("owners", [])
                owner = owners[0].get("emailAddress") if owners else None

                # Parse dates
                created_at = None
                modified_at = None
                if item.get("createdTime"):
                    created_at = datetime.fromisoformat(
                        item["createdTime"].replace("Z", "+00:00")
                    )
                if item.get("modifiedTime"):
                    modified_at = datetime.fromisoformat(
                        item["modifiedTime"].replace("Z", "+00:00")
                    )

                files.append(
                    FileInfo(
                        id=item["id"],
                        name=item["name"],
                        mime_type=mime_type,
                        web_url=item.get("webViewLink"),
                        created_at=created_at,
                        modified_at=modified_at,
                        size=int(item.get("size", 0)) if item.get("size") else None,
                        owner=owner,
                        parent_id=item.get("parents", [None])[0],
                    )
                )

            next_token = response.get("nextPageToken")
            logger.debug("Listed files", count=len(files), has_more=bool(next_token))

            return files, next_token

        except HttpError as e:
            logger.error("Failed to list files", error=str(e))
            raise

    async def get_file_content(self, file_id: str) -> Optional[str]:
        """
        Download and extract text content from a file.

        Args:
            file_id: Google Drive file ID

        Returns:
            Extracted text content, or None if not extractable
        """
        if not self.service:
            raise RuntimeError("Not authenticated")

        try:
            # Get file metadata first
            file_meta = self.service.files().get(
                fileId=file_id,
                fields="id, name, mimeType, size"
            ).execute()

            mime_type = file_meta.get("mimeType", "")
            file_size = int(file_meta.get("size", 0)) if file_meta.get("size") else 0

            # Check size limit
            max_size = self.settings.max_file_size_mb * 1024 * 1024
            if file_size > max_size:
                logger.warning(
                    "File too large, skipping",
                    file_id=file_id,
                    size_mb=file_size / (1024 * 1024),
                )
                return None

            # Handle Google native formats (export)
            if mime_type.startswith("application/vnd.google-apps."):
                return await self._export_google_file(file_id, mime_type)

            # Handle standard formats (download)
            return await self._download_file(file_id, mime_type)

        except HttpError as e:
            if e.resp.status == 404:
                logger.warning("File not found", file_id=file_id)
                return None
            logger.error("Failed to get file content", file_id=file_id, error=str(e))
            raise

    async def _export_google_file(self, file_id: str, mime_type: str) -> Optional[str]:
        """Export a Google native file (Docs, Sheets, Slides) as text."""
        export_mime = self.SUPPORTED_MIME_TYPES.get(mime_type)
        if not export_mime:
            return None

        try:
            request = self.service.files().export_media(
                fileId=file_id,
                mimeType=export_mime,
            )

            content = io.BytesIO()
            downloader = MediaIoBaseDownload(content, request)

            done = False
            while not done:
                _, done = downloader.next_chunk()

            content.seek(0)
            text = content.read().decode("utf-8", errors="ignore")

            logger.debug(
                "Exported Google file",
                file_id=file_id,
                mime_type=mime_type,
                length=len(text),
            )

            return text

        except HttpError as e:
            logger.error("Failed to export file", file_id=file_id, error=str(e))
            return None

    async def _download_file(self, file_id: str, mime_type: str) -> Optional[str]:
        """Download a standard file and extract text."""
        try:
            request = self.service.files().get_media(fileId=file_id)

            content = io.BytesIO()
            downloader = MediaIoBaseDownload(content, request)

            done = False
            while not done:
                _, done = downloader.next_chunk()

            content.seek(0)

            # Handle PDFs
            if mime_type == "application/pdf":
                return self._extract_pdf_text(content)

            # Handle text-based files
            text = content.read().decode("utf-8", errors="ignore")

            logger.debug(
                "Downloaded file",
                file_id=file_id,
                mime_type=mime_type,
                length=len(text),
            )

            return text

        except HttpError as e:
            logger.error("Failed to download file", file_id=file_id, error=str(e))
            return None

    def _extract_pdf_text(self, content: io.BytesIO) -> Optional[str]:
        """Extract text from a PDF file."""
        try:
            # Try using PyPDF2 or pdfplumber if available
            try:
                import pypdf

                reader = pypdf.PdfReader(content)
                text_parts = []
                for page in reader.pages:
                    text_parts.append(page.extract_text() or "")
                return "\n\n".join(text_parts)

            except ImportError:
                logger.warning("PyPDF not installed, skipping PDF extraction")
                return None

        except Exception as e:
            logger.error("Failed to extract PDF text", error=str(e))
            return None

    def _should_skip(self, mime_type: str) -> bool:
        """Check if a MIME type should be skipped."""
        if mime_type in self.SKIP_MIME_TYPES:
            return True
        for prefix in ["image/", "video/", "audio/"]:
            if mime_type.startswith(prefix):
                return True
        return False

    async def sync(self, full: bool = False) -> SyncResult:
        """
        Sync files from Google Drive.

        Args:
            full: If True, perform full sync. Otherwise incremental.

        Returns:
            SyncResult with counts and status
        """
        if not self.service:
            return SyncResult(
                success=False,
                source=self.SOURCE_NAME,
                errors=["Not authenticated"],
            )

        start_time = time.time()

        # Get stored sync token
        async with get_db_context() as db:
            sync_state = await crud.get_or_create_sync_state(db, self.SOURCE_NAME)
            self.sync_token = sync_state.last_sync_token

        if full or not self.sync_token:
            result = await self._full_sync()
        else:
            result = await self._incremental_sync()

        result.duration_seconds = time.time() - start_time

        # Update sync state
        async with get_db_context() as db:
            await crud.update_sync_state(
                db,
                self.SOURCE_NAME,
                status="idle" if result.success else "error",
                last_sync_token=result.sync_token,
                error_message=result.errors[0] if result.errors else None,
                document_count=result.added + result.updated,
            )

        logger.info(
            "Sync completed",
            source=self.SOURCE_NAME,
            success=result.success,
            added=result.added,
            updated=result.updated,
            deleted=result.deleted,
            duration=result.duration_seconds,
        )

        return result

    async def _full_sync(self) -> SyncResult:
        """Perform a full sync of all files."""
        logger.info("Starting full sync", source=self.SOURCE_NAME)

        result = SyncResult(success=True, source=self.SOURCE_NAME)
        chunker = get_chunker()
        embedding_service = get_embedding_service()
        vector_store = get_vector_store()

        try:
            # Get start page token for future incremental syncs
            start_token_response = self.service.changes().getStartPageToken().execute()
            new_sync_token = start_token_response.get("startPageToken")

            # Process all files
            async for file in self.iter_files():
                try:
                    # Get content
                    content = await self.get_file_content(file.id)
                    if not content:
                        continue

                    # Create document
                    doc = self.file_to_document(file, content)

                    # Save to database
                    async with get_db_context() as db:
                        await crud.create_document(
                            db,
                            source=doc.source,
                            source_id=doc.source_id,
                            title=doc.title,
                            path=doc.path,
                            author=doc.author,
                            content_type=doc.content_type,
                            raw_content=doc.raw_content,
                            url=doc.url,
                            created_at=doc.created_at,
                            modified_at=doc.modified_at,
                        )

                    # Chunk the document
                    chunks = chunker.chunk_document(doc)

                    if chunks:
                        # Generate embeddings
                        texts = [c.content for c in chunks]
                        embeddings = await embedding_service.embed_batch(texts)

                        # Create vector chunks
                        vector_chunks = []
                        for chunk, embedding in zip(chunks, embeddings):
                            vector_chunks.append(
                                Chunk(
                                    id=chunk.id,
                                    document_id=chunk.document_id,
                                    content=chunk.content,
                                    embedding=embedding,
                                    metadata=chunk.metadata.to_dict(),
                                )
                            )

                        # Add to vector store
                        vector_store.add_chunks(vector_chunks)

                    result.added += 1

                except Exception as e:
                    logger.error(
                        "Failed to process file",
                        file_id=file.id,
                        file_name=file.name,
                        error=str(e),
                    )
                    result.errors.append(f"{file.name}: {str(e)}")

            result.sync_token = new_sync_token

        except Exception as e:
            logger.error("Full sync failed", error=str(e))
            result.success = False
            result.errors.append(str(e))

        return result

    async def _incremental_sync(self) -> SyncResult:
        """Perform incremental sync using change tokens."""
        logger.info("Starting incremental sync", source=self.SOURCE_NAME)

        result = SyncResult(success=True, source=self.SOURCE_NAME)
        chunker = get_chunker()
        embedding_service = get_embedding_service()
        vector_store = get_vector_store()

        try:
            page_token = self.sync_token

            while page_token:
                response = self.service.changes().list(
                    pageToken=page_token,
                    fields="nextPageToken, newStartPageToken, changes(fileId, removed, file(id, name, mimeType, webViewLink, modifiedTime, owners))",
                ).execute()

                for change in response.get("changes", []):
                    file_id = change.get("fileId")
                    removed = change.get("removed", False)

                    if removed:
                        # Delete from database and vector store
                        doc_id = f"{self.SOURCE_NAME}:{file_id}"
                        async with get_db_context() as db:
                            await crud.delete_document(db, doc_id)
                        vector_store.delete_by_document_id(doc_id)
                        result.deleted += 1
                        continue

                    # Process updated/new file
                    file_data = change.get("file", {})
                    if not file_data:
                        continue

                    mime_type = file_data.get("mimeType", "")
                    if self._should_skip(mime_type):
                        continue

                    try:
                        content = await self.get_file_content(file_id)
                        if not content:
                            continue

                        # Create FileInfo
                        owners = file_data.get("owners", [])
                        owner = owners[0].get("emailAddress") if owners else None

                        modified_at = None
                        if file_data.get("modifiedTime"):
                            modified_at = datetime.fromisoformat(
                                file_data["modifiedTime"].replace("Z", "+00:00")
                            )

                        file = FileInfo(
                            id=file_id,
                            name=file_data.get("name", ""),
                            mime_type=mime_type,
                            web_url=file_data.get("webViewLink"),
                            modified_at=modified_at,
                            owner=owner,
                        )

                        doc = self.file_to_document(file, content)

                        # Update database
                        async with get_db_context() as db:
                            await crud.create_document(
                                db,
                                source=doc.source,
                                source_id=doc.source_id,
                                title=doc.title,
                                path=doc.path,
                                author=doc.author,
                                content_type=doc.content_type,
                                raw_content=doc.raw_content,
                                url=doc.url,
                                modified_at=doc.modified_at,
                            )

                        # Delete old chunks and add new ones
                        vector_store.delete_by_document_id(doc.id)

                        chunks = chunker.chunk_document(doc)
                        if chunks:
                            texts = [c.content for c in chunks]
                            embeddings = await embedding_service.embed_batch(texts)

                            vector_chunks = []
                            for chunk, embedding in zip(chunks, embeddings):
                                vector_chunks.append(
                                    Chunk(
                                        id=chunk.id,
                                        document_id=chunk.document_id,
                                        content=chunk.content,
                                        embedding=embedding,
                                        metadata=chunk.metadata.to_dict(),
                                    )
                                )

                            vector_store.add_chunks(vector_chunks)

                        result.updated += 1

                    except Exception as e:
                        logger.error(
                            "Failed to process change",
                            file_id=file_id,
                            error=str(e),
                        )
                        result.errors.append(f"File {file_id}: {str(e)}")

                # Get next page or new start token
                page_token = response.get("nextPageToken")
                if not page_token:
                    result.sync_token = response.get("newStartPageToken")

        except Exception as e:
            logger.error("Incremental sync failed", error=str(e))
            result.success = False
            result.errors.append(str(e))

        return result


# Factory function
def create_gdrive_connector() -> GoogleDriveConnector:
    """Create a new Google Drive connector instance."""
    return GoogleDriveConnector()

