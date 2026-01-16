"""Gmail connector for syncing emails."""

import base64
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional

import html2text
import structlog
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from oslash.config import get_settings
from oslash.connectors.base import BaseConnector, FileInfo, SyncResult
from oslash.db import get_db_context, crud
from oslash.db.models import Document
from oslash.services.chunking import get_chunker
from oslash.services.embeddings import get_embedding_service
from oslash.vector import get_vector_store, Chunk

logger = structlog.get_logger(__name__)


class GmailConnector(BaseConnector):
    """
    Gmail connector using Gmail API.

    Supports:
    - Email listing with metadata
    - Body extraction (plain text or HTML→text)
    - Incremental sync with history API
    - Label filtering
    """

    SOURCE_NAME = "gmail"

    # Labels to skip by default
    SKIP_LABELS = {
        "SPAM",
        "TRASH",
        "CATEGORY_PROMOTIONS",
        "CATEGORY_SOCIAL",
        "CATEGORY_UPDATES",
        "DRAFT",
    }

    # Labels to include (if set, only these are synced)
    INCLUDE_LABELS = {
        "INBOX",
        "SENT",
        "IMPORTANT",
        "STARRED",
    }

    def __init__(self):
        super().__init__()
        self.service = None
        self.credentials = None
        self.settings = get_settings()
        self.history_id: Optional[str] = None

        # HTML to text converter
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        self.html_converter.ignore_images = True
        self.html_converter.ignore_emphasis = False
        self.html_converter.body_width = 0  # Don't wrap lines

    async def authenticate(self, credentials: dict) -> bool:
        """
        Authenticate with Gmail using OAuth tokens.

        Args:
            credentials: Dict with 'token', 'refresh_token', etc.

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

            # Build the Gmail service
            self.service = build("gmail", "v1", credentials=self.credentials)

            # Test the connection and get user email
            profile = self.service.users().getProfile(userId="me").execute()
            user_email = profile.get("emailAddress", "unknown")

            self.is_authenticated = True
            logger.info("Gmail authenticated", email=user_email)

            return True

        except Exception as e:
            logger.error("Gmail authentication failed", error=str(e))
            self.is_authenticated = False
            return False

    async def list_files(
        self,
        folder_id: Optional[str] = None,
        page_token: Optional[str] = None,
    ) -> tuple[list[FileInfo], Optional[str]]:
        """
        List emails from Gmail.

        Args:
            folder_id: Label ID to filter by (None = all included labels)
            page_token: Pagination token

        Returns:
            Tuple of (emails as FileInfo, next_page_token)
        """
        if not self.service:
            raise RuntimeError("Not authenticated")

        try:
            # Build query
            query_parts = []

            # Filter by label if specified
            if folder_id:
                label_ids = [folder_id]
            else:
                label_ids = list(self.INCLUDE_LABELS)

            # Request messages
            request = self.service.users().messages().list(
                userId="me",
                labelIds=label_ids,
                pageToken=page_token,
                maxResults=100,
            )

            response = request.execute()

            files = []
            for item in response.get("messages", []):
                # Get basic message info
                msg_id = item["id"]

                # We'll get full details when extracting content
                files.append(
                    FileInfo(
                        id=msg_id,
                        name=msg_id,  # Will be replaced with subject
                        mime_type="message/rfc822",
                    )
                )

            next_token = response.get("nextPageToken")
            logger.debug("Listed emails", count=len(files), has_more=bool(next_token))

            return files, next_token

        except HttpError as e:
            logger.error("Failed to list emails", error=str(e))
            raise

    async def get_file_content(self, file_id: str) -> Optional[str]:
        """
        Get email content including headers and body.

        Args:
            file_id: Gmail message ID

        Returns:
            Formatted email content as text
        """
        if not self.service:
            raise RuntimeError("Not authenticated")

        try:
            # Get full message
            message = self.service.users().messages().get(
                userId="me",
                id=file_id,
                format="full",
            ).execute()

            # Check labels - skip if in excluded labels
            labels = message.get("labelIds", [])
            if any(label in self.SKIP_LABELS for label in labels):
                return None

            # Extract headers
            headers = {}
            payload = message.get("payload", {})
            for header in payload.get("headers", []):
                name = header.get("name", "").lower()
                value = header.get("value", "")
                if name in ["subject", "from", "to", "cc", "date"]:
                    headers[name] = value

            # Extract body
            body = self._extract_body(payload)

            # Format as document
            subject = headers.get("subject", "(No Subject)")
            from_addr = headers.get("from", "")
            to_addr = headers.get("to", "")
            date = headers.get("date", "")

            content = f"""Subject: {subject}
From: {from_addr}
To: {to_addr}
Date: {date}

{body}"""

            return content

        except HttpError as e:
            if e.resp.status == 404:
                logger.warning("Email not found", message_id=file_id)
                return None
            logger.error("Failed to get email", message_id=file_id, error=str(e))
            raise

    def _extract_body(self, payload: dict) -> str:
        """
        Extract email body, preferring plain text over HTML.

        Args:
            payload: Gmail message payload

        Returns:
            Extracted body text
        """
        mime_type = payload.get("mimeType", "")

        # Simple text/plain
        if mime_type == "text/plain":
            data = payload.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

        # Simple text/html
        if mime_type == "text/html":
            data = payload.get("body", {}).get("data", "")
            if data:
                html = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                return self.html_converter.handle(html)

        # Multipart message
        if mime_type.startswith("multipart/"):
            parts = payload.get("parts", [])

            # First try to find text/plain
            for part in parts:
                if part.get("mimeType") == "text/plain":
                    data = part.get("body", {}).get("data", "")
                    if data:
                        return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

            # Fallback to text/html
            for part in parts:
                if part.get("mimeType") == "text/html":
                    data = part.get("body", {}).get("data", "")
                    if data:
                        html = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                        return self.html_converter.handle(html)

            # Recursively check nested multipart
            for part in parts:
                if part.get("mimeType", "").startswith("multipart/"):
                    result = self._extract_body(part)
                    if result:
                        return result

        return ""

    def _get_email_metadata(self, message: dict) -> dict:
        """Extract metadata from a Gmail message."""
        headers = {}
        payload = message.get("payload", {})
        for header in payload.get("headers", []):
            name = header.get("name", "").lower()
            value = header.get("value", "")
            headers[name] = value

        # Parse recipients
        to_list = [addr.strip() for addr in headers.get("to", "").split(",") if addr.strip()]
        cc_list = [addr.strip() for addr in headers.get("cc", "").split(",") if addr.strip()]

        # Check for attachments
        has_attachments = self._has_attachments(payload)

        return {
            "subject": headers.get("subject", "(No Subject)"),
            "from": headers.get("from", ""),
            "to": to_list,
            "cc": cc_list,
            "date": headers.get("date", ""),
            "thread_id": message.get("threadId", ""),
            "labels": message.get("labelIds", []),
            "has_attachments": has_attachments,
            "snippet": message.get("snippet", ""),
        }

    def _has_attachments(self, payload: dict) -> bool:
        """Check if message has attachments."""
        if payload.get("filename"):
            return True
        for part in payload.get("parts", []):
            if part.get("filename"):
                return True
            if self._has_attachments(part):
                return True
        return False

    def _parse_email_date(self, date_str: str) -> Optional[datetime]:
        """Parse email date string to datetime."""
        if not date_str:
            return None
        try:
            return parsedate_to_datetime(date_str)
        except Exception:
            return None

    def email_to_document(self, message: dict, content: str) -> Document:
        """
        Convert a Gmail message to a Document model.

        Args:
            message: Gmail message object
            content: Extracted email content

        Returns:
            Document model instance
        """
        metadata = self._get_email_metadata(message)

        # Build label path
        labels = metadata.get("labels", [])
        label_path = "/".join([l for l in labels if l not in self.SKIP_LABELS][:3])

        # Parse date
        email_date = self._parse_email_date(metadata.get("date", ""))

        # Build Gmail URL
        msg_id = message.get("id", "")
        web_url = f"https://mail.google.com/mail/u/0/#inbox/{msg_id}"

        return Document(
            id=f"{self.SOURCE_NAME}:{msg_id}",
            source=self.SOURCE_NAME,
            source_id=msg_id,
            title=metadata.get("subject", "(No Subject)"),
            path=label_path,
            author=metadata.get("from", ""),
            content_type="email",
            raw_content=content,
            url=web_url,
            created_at=email_date,
            modified_at=email_date,
            last_synced=datetime.utcnow(),
        )

    async def sync(self, full: bool = False) -> SyncResult:
        """
        Sync emails from Gmail.

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

        # Get stored history ID
        async with get_db_context() as db:
            sync_state = await crud.get_or_create_sync_state(db, self.SOURCE_NAME)
            self.history_id = sync_state.last_sync_token

        if full or not self.history_id:
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
            "Gmail sync completed",
            success=result.success,
            added=result.added,
            updated=result.updated,
            deleted=result.deleted,
            duration=result.duration_seconds,
        )

        return result

    async def _full_sync(self) -> SyncResult:
        """Perform a full sync of all emails."""
        logger.info("Starting full Gmail sync")

        result = SyncResult(success=True, source=self.SOURCE_NAME)
        chunker = get_chunker()
        embedding_service = get_embedding_service()
        vector_store = get_vector_store()

        try:
            # Get current history ID for future incremental syncs
            profile = self.service.users().getProfile(userId="me").execute()
            new_history_id = profile.get("historyId")

            # Process all emails
            page_token = None
            total_processed = 0
            max_emails = 1000  # Limit for initial sync

            while total_processed < max_emails:
                files, next_token = await self.list_files(page_token=page_token)

                for file in files:
                    if total_processed >= max_emails:
                        break

                    try:
                        # Get full message
                        message = self.service.users().messages().get(
                            userId="me",
                            id=file.id,
                            format="full",
                        ).execute()

                        # Check labels
                        labels = message.get("labelIds", [])
                        if any(label in self.SKIP_LABELS for label in labels):
                            continue

                        # Get content
                        content = await self.get_file_content(file.id)
                        if not content:
                            continue

                        # Create document
                        doc = self.email_to_document(message, content)

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

                        # Chunk the document (emails usually stay as single chunks)
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
                        total_processed += 1

                    except Exception as e:
                        logger.error(
                            "Failed to process email",
                            message_id=file.id,
                            error=str(e),
                        )
                        result.errors.append(f"Email {file.id}: {str(e)}")

                if not next_token or total_processed >= max_emails:
                    break
                page_token = next_token

            result.sync_token = new_history_id

        except Exception as e:
            logger.error("Full Gmail sync failed", error=str(e))
            result.success = False
            result.errors.append(str(e))

        return result

    async def _incremental_sync(self) -> SyncResult:
        """Perform incremental sync using history API."""
        logger.info("Starting incremental Gmail sync", history_id=self.history_id)

        result = SyncResult(success=True, source=self.SOURCE_NAME)
        chunker = get_chunker()
        embedding_service = get_embedding_service()
        vector_store = get_vector_store()

        try:
            # Get history since last sync
            history_response = self.service.users().history().list(
                userId="me",
                startHistoryId=self.history_id,
                historyTypes=["messageAdded", "messageDeleted"],
            ).execute()

            new_history_id = history_response.get("historyId", self.history_id)

            # Process history records
            for record in history_response.get("history", []):
                # Handle added messages
                for added in record.get("messagesAdded", []):
                    msg_data = added.get("message", {})
                    msg_id = msg_data.get("id")

                    if not msg_id:
                        continue

                    try:
                        # Get full message
                        message = self.service.users().messages().get(
                            userId="me",
                            id=msg_id,
                            format="full",
                        ).execute()

                        # Check labels
                        labels = message.get("labelIds", [])
                        if any(label in self.SKIP_LABELS for label in labels):
                            continue

                        content = await self.get_file_content(msg_id)
                        if not content:
                            continue

                        doc = self.email_to_document(message, content)

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
                            )

                        # Chunk and embed
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

                        result.added += 1

                    except Exception as e:
                        logger.error("Failed to process added email", msg_id=msg_id, error=str(e))
                        result.errors.append(f"Email {msg_id}: {str(e)}")

                # Handle deleted messages
                for deleted in record.get("messagesDeleted", []):
                    msg_data = deleted.get("message", {})
                    msg_id = msg_data.get("id")

                    if msg_id:
                        doc_id = f"{self.SOURCE_NAME}:{msg_id}"
                        async with get_db_context() as db:
                            await crud.delete_document(db, doc_id)
                        vector_store.delete_by_document_id(doc_id)
                        result.deleted += 1

            result.sync_token = new_history_id

        except HttpError as e:
            if e.resp.status == 404:
                # History ID expired, need full sync
                logger.warning("History ID expired, performing full sync")
                return await self._full_sync()
            logger.error("Incremental Gmail sync failed", error=str(e))
            result.success = False
            result.errors.append(str(e))

        except Exception as e:
            logger.error("Incremental Gmail sync failed", error=str(e))
            result.success = False
            result.errors.append(str(e))

        return result


# Factory function
def create_gmail_connector() -> GmailConnector:
    """Create a new Gmail connector instance."""
    return GmailConnector()

