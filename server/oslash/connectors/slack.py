"""Slack connector for syncing messages and threads."""

import asyncio
import time
from collections import defaultdict
from datetime import datetime
from typing import Optional

import structlog
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from oslash.config import get_settings
from oslash.connectors.base import BaseConnector, FileInfo, SyncResult
from oslash.db import get_db_context, crud
from oslash.db.models import Document
from oslash.services.chunking import get_chunker
from oslash.services.embeddings import get_embedding_service
from oslash.vector import get_vector_store, Chunk

logger = structlog.get_logger(__name__)


class SlackConnector(BaseConnector):
    """
    Slack connector using Slack Web API.

    Supports:
    - Channel listing (public, private, DMs, group DMs)
    - Message history with threading
    - User name resolution
    - Incremental sync with timestamps
    """

    SOURCE_NAME = "slack"

    # Channel types to sync
    CHANNEL_TYPES = ["public_channel", "private_channel", "mpim", "im"]

    def __init__(self):
        super().__init__()
        self.client: Optional[WebClient] = None
        self.settings = get_settings()
        self.last_sync_timestamp: Optional[str] = None

        # Cache for user info
        self._user_cache: dict[str, dict] = {}

        # Workspace info
        self.team_id: Optional[str] = None
        self.team_domain: Optional[str] = None

    async def authenticate(self, credentials: dict) -> bool:
        """
        Authenticate with Slack using OAuth token.

        Args:
            credentials: Dict with 'token' (bot or user token)

        Returns:
            True if authentication successful
        """
        try:
            token = credentials.get("token") or credentials.get("access_token")
            if not token:
                logger.error("No Slack token provided")
                return False

            self.client = WebClient(token=token)

            # Test the connection
            auth_response = self.client.auth_test()

            if not auth_response.get("ok"):
                logger.error("Slack auth test failed", error=auth_response.get("error"))
                return False

            self.team_id = auth_response.get("team_id")
            self.team_domain = auth_response.get("url", "").replace("https://", "").replace(".slack.com/", "")

            self.is_authenticated = True
            logger.info(
                "Slack authenticated",
                team=auth_response.get("team"),
                user=auth_response.get("user"),
            )

            return True

        except SlackApiError as e:
            logger.error("Slack authentication failed", error=str(e))
            self.is_authenticated = False
            return False

    async def list_files(
        self,
        folder_id: Optional[str] = None,
        page_token: Optional[str] = None,
    ) -> tuple[list[FileInfo], Optional[str]]:
        """
        List channels from Slack.

        Args:
            folder_id: Not used for Slack
            page_token: Cursor for pagination

        Returns:
            Tuple of (channels as FileInfo, next_cursor)
        """
        if not self.client:
            raise RuntimeError("Not authenticated")

        try:
            # Get all channel types
            response = self.client.conversations_list(
                types=",".join(self.CHANNEL_TYPES),
                cursor=page_token,
                limit=200,
                exclude_archived=True,
            )

            if not response.get("ok"):
                raise RuntimeError(f"Failed to list channels: {response.get('error')}")

            files = []
            for channel in response.get("channels", []):
                # Skip channels we're not a member of
                if not channel.get("is_member", True):
                    continue

                files.append(
                    FileInfo(
                        id=channel["id"],
                        name=self._get_channel_name(channel),
                        mime_type="slack/channel",
                        path=f"#{self._get_channel_name(channel)}",
                    )
                )

            next_cursor = response.get("response_metadata", {}).get("next_cursor")
            if not next_cursor:
                next_cursor = None

            logger.debug("Listed channels", count=len(files), has_more=bool(next_cursor))

            return files, next_cursor

        except SlackApiError as e:
            logger.error("Failed to list channels", error=str(e))
            raise

    def _get_channel_name(self, channel: dict) -> str:
        """Get display name for a channel."""
        if channel.get("is_im"):
            # DM - get the other user's name
            user_id = channel.get("user")
            if user_id:
                user = self._get_user_info(user_id)
                return f"DM: {user.get('real_name', user.get('name', 'Unknown'))}"
            return "DM"

        if channel.get("is_mpim"):
            # Group DM
            return channel.get("name", "Group DM").replace("mpdm-", "").replace("-1", "")

        return channel.get("name", "Unknown")

    def _get_user_info(self, user_id: str) -> dict:
        """Get user info with caching."""
        if user_id in self._user_cache:
            return self._user_cache[user_id]

        if not self.client:
            return {"id": user_id, "name": "Unknown"}

        try:
            response = self.client.users_info(user=user_id)
            if response.get("ok"):
                user = response.get("user", {})
                self._user_cache[user_id] = user
                return user
        except SlackApiError:
            pass

        return {"id": user_id, "name": "Unknown"}

    def _get_username(self, user_id: str) -> str:
        """Get display name for a user."""
        user = self._get_user_info(user_id)
        return user.get("real_name") or user.get("name") or user_id

    async def get_file_content(self, file_id: str) -> Optional[str]:
        """
        Get channel history as content.

        Args:
            file_id: Channel ID

        Returns:
            Formatted messages as text
        """
        # This is handled differently for Slack - we process threads
        # See _get_channel_messages and _thread_to_document
        return None

    async def _get_channel_messages(
        self,
        channel_id: str,
        oldest: Optional[str] = None,
        limit: int = 200,
    ) -> list[dict]:
        """
        Get messages from a channel.

        Args:
            channel_id: Channel ID
            oldest: Oldest timestamp to fetch from (for incremental sync)
            limit: Maximum messages to fetch

        Returns:
            List of message objects
        """
        if not self.client:
            raise RuntimeError("Not authenticated")

        messages = []

        try:
            cursor = None
            while len(messages) < limit:
                response = self.client.conversations_history(
                    channel=channel_id,
                    cursor=cursor,
                    limit=min(200, limit - len(messages)),
                    oldest=oldest,
                )

                if not response.get("ok"):
                    logger.warning(
                        "Failed to get channel history",
                        channel=channel_id,
                        error=response.get("error"),
                    )
                    break

                batch = response.get("messages", [])
                messages.extend(batch)

                # Check for more messages
                if not response.get("has_more"):
                    break

                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

                # Rate limiting
                await asyncio.sleep(0.1)

            return messages

        except SlackApiError as e:
            if "ratelimited" in str(e):
                # Handle rate limiting
                retry_after = int(e.response.headers.get("Retry-After", 10))
                logger.warning("Rate limited, waiting", seconds=retry_after)
                await asyncio.sleep(retry_after)
                return await self._get_channel_messages(channel_id, oldest, limit)

            logger.error("Failed to get channel messages", channel=channel_id, error=str(e))
            return []

    async def _get_thread_replies(self, channel_id: str, thread_ts: str) -> list[dict]:
        """Get replies to a thread."""
        if not self.client:
            return []

        try:
            response = self.client.conversations_replies(
                channel=channel_id,
                ts=thread_ts,
                limit=100,
            )

            if response.get("ok"):
                return response.get("messages", [])

        except SlackApiError as e:
            logger.error("Failed to get thread replies", thread_ts=thread_ts, error=str(e))

        return []

    def _group_by_thread(self, messages: list[dict]) -> list[list[dict]]:
        """
        Group messages by thread.

        Returns list of threads, where each thread is a list of messages.
        Standalone messages become single-message threads.
        """
        threads: dict[str, list[dict]] = defaultdict(list)

        for msg in messages:
            # Skip bot messages and system messages
            if msg.get("subtype") in ["bot_message", "channel_join", "channel_leave"]:
                continue

            thread_ts = msg.get("thread_ts") or msg.get("ts")
            threads[thread_ts].append(msg)

        # Sort messages within each thread by timestamp
        result = []
        for thread_ts in sorted(threads.keys(), reverse=True):
            thread_msgs = sorted(threads[thread_ts], key=lambda m: m.get("ts", ""))
            result.append(thread_msgs)

        return result

    def _thread_to_document(self, channel: dict, thread: list[dict]) -> Document:
        """
        Convert a Slack thread to a Document.

        Args:
            channel: Channel info
            thread: List of messages in the thread

        Returns:
            Document model instance
        """
        if not thread:
            raise ValueError("Empty thread")

        first_msg = thread[0]
        channel_name = self._get_channel_name(channel)

        # Build thread content
        content_parts = []
        for msg in thread:
            user_name = self._get_username(msg.get("user", ""))
            text = msg.get("text", "")
            timestamp = msg.get("ts", "")

            # Format timestamp
            try:
                dt = datetime.fromtimestamp(float(timestamp))
                time_str = dt.strftime("%Y-%m-%d %H:%M")
            except:
                time_str = ""

            content_parts.append(f"[{time_str}] {user_name}: {text}")

        content = "\n".join(content_parts)

        # Build title from first message
        first_text = first_msg.get("text", "")[:100]
        title = f"#{channel_name} - {first_text}"
        if len(first_msg.get("text", "")) > 100:
            title += "..."

        # Build URL
        thread_ts = first_msg.get("ts", "").replace(".", "")
        url = f"https://{self.team_domain}.slack.com/archives/{channel['id']}/p{thread_ts}"

        # Parse timestamp
        created_at = None
        try:
            created_at = datetime.fromtimestamp(float(first_msg.get("ts", 0)))
        except:
            pass

        # Build document ID
        doc_id = f"{channel['id']}_{first_msg.get('ts', '')}"

        return Document(
            id=f"{self.SOURCE_NAME}:{doc_id}",
            source=self.SOURCE_NAME,
            source_id=doc_id,
            title=title,
            path=f"#{channel_name}",
            author=self._get_username(first_msg.get("user", "")),
            content_type="message",
            raw_content=content,
            url=url,
            created_at=created_at,
            modified_at=created_at,
            last_synced=datetime.utcnow(),
        )

    async def sync(self, full: bool = False) -> SyncResult:
        """
        Sync messages from Slack.

        Args:
            full: If True, perform full sync. Otherwise incremental.

        Returns:
            SyncResult with counts and status
        """
        if not self.client:
            return SyncResult(
                success=False,
                source=self.SOURCE_NAME,
                errors=["Not authenticated"],
            )

        start_time = time.time()

        # Get stored sync timestamp
        async with get_db_context() as db:
            sync_state = await crud.get_or_create_sync_state(db, self.SOURCE_NAME)
            self.last_sync_timestamp = sync_state.last_sync_token

        result = await self._sync_channels(full)
        result.duration_seconds = time.time() - start_time

        # Update sync state with current timestamp
        current_ts = str(time.time())
        async with get_db_context() as db:
            await crud.update_sync_state(
                db,
                self.SOURCE_NAME,
                status="idle" if result.success else "error",
                last_sync_token=current_ts,
                error_message=result.errors[0] if result.errors else None,
                document_count=result.added + result.updated,
            )

        logger.info(
            "Slack sync completed",
            success=result.success,
            added=result.added,
            updated=result.updated,
            deleted=result.deleted,
            duration=result.duration_seconds,
        )

        return result

    async def _sync_channels(self, full: bool = False) -> SyncResult:
        """Sync all channels."""
        result = SyncResult(success=True, source=self.SOURCE_NAME)
        chunker = get_chunker()
        embedding_service = get_embedding_service()
        vector_store = get_vector_store()

        # Determine oldest timestamp for incremental sync
        oldest = None if full else self.last_sync_timestamp

        try:
            # Get all channels
            page_token = None
            channels = []

            while True:
                batch, next_token = await self.list_files(page_token=page_token)
                channels.extend(batch)
                if not next_token:
                    break
                page_token = next_token

            logger.info("Syncing channels", count=len(channels), full=full)

            # Process each channel
            for channel_info in channels:
                channel_id = channel_info.id
                channel_name = channel_info.name

                try:
                    # Get channel details
                    channel_response = self.client.conversations_info(channel=channel_id)
                    if not channel_response.get("ok"):
                        continue
                    channel = channel_response.get("channel", {})

                    # Get messages
                    messages = await self._get_channel_messages(
                        channel_id,
                        oldest=oldest,
                        limit=500 if full else 100,
                    )

                    if not messages:
                        continue

                    # Group by thread
                    threads = self._group_by_thread(messages)

                    logger.debug(
                        "Processing channel",
                        channel=channel_name,
                        messages=len(messages),
                        threads=len(threads),
                    )

                    # Process each thread
                    for thread in threads:
                        if not thread:
                            continue

                        try:
                            # Get full thread if it has replies
                            first_msg = thread[0]
                            if first_msg.get("reply_count", 0) > 0:
                                full_thread = await self._get_thread_replies(
                                    channel_id, first_msg.get("ts")
                                )
                                if full_thread:
                                    thread = full_thread

                            # Create document
                            doc = self._thread_to_document(channel, thread)

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

                            # Chunk (usually single chunk for messages)
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
                            logger.error(
                                "Failed to process thread",
                                channel=channel_name,
                                error=str(e),
                            )
                            result.errors.append(f"Thread in #{channel_name}: {str(e)}")

                    # Rate limiting between channels
                    await asyncio.sleep(0.2)

                except Exception as e:
                    logger.error(
                        "Failed to sync channel",
                        channel=channel_name,
                        error=str(e),
                    )
                    result.errors.append(f"Channel #{channel_name}: {str(e)}")

        except Exception as e:
            logger.error("Slack sync failed", error=str(e))
            result.success = False
            result.errors.append(str(e))

        return result


# Factory function
def create_slack_connector() -> SlackConnector:
    """Create a new Slack connector instance."""
    return SlackConnector()

