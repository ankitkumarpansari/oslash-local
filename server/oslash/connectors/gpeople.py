"""Google People API connector for syncing company directory contacts."""

import time
from datetime import datetime
from typing import Optional

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


class GooglePeopleConnector(BaseConnector):
    """
    Google People API connector for company directory search.

    Supports:
    - Listing directory people (domain profiles and contacts)
    - Searching directory people by query
    - Incremental sync with sync tokens
    - Contact metadata extraction (name, email, phone, organization, etc.)
    """

    SOURCE_NAME = "gpeople"

    # Directory sources to search
    DIRECTORY_SOURCES = [
        "DIRECTORY_SOURCE_TYPE_DOMAIN_PROFILE",
        "DIRECTORY_SOURCE_TYPE_DOMAIN_CONTACT",
    ]

    # Fields to request from the API
    READ_MASK = "names,emailAddresses,phoneNumbers,organizations,photos,biographies,locations,addresses"

    def __init__(self):
        super().__init__()
        self.service = None
        self.credentials = None
        self.settings = get_settings()

    async def authenticate(self, credentials: dict) -> bool:
        """
        Authenticate with Google People API using OAuth tokens.

        Args:
            credentials: Dict with 'access_token' or 'token', 'refresh_token', etc.

        Returns:
            True if authentication successful
        """
        try:
            # Support both 'access_token' (from OAuth storage) and 'token' (legacy)
            access_token = credentials.get("access_token") or credentials.get("token")

            self.credentials = Credentials(
                token=access_token,
                refresh_token=credentials.get("refresh_token"),
                token_uri=credentials.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=self.settings.google_client_id,
                client_secret=self.settings.google_client_secret,
            )

            # Build the People API service
            self.service = build("people", "v1", credentials=self.credentials)

            # Test the connection by getting the authenticated user's profile
            profile = self.service.people().get(
                resourceName="people/me",
                personFields="names,emailAddresses",
            ).execute()

            names = profile.get("names", [])
            user_name = names[0].get("displayName", "Unknown") if names else "Unknown"

            self.is_authenticated = True
            logger.info("Google People API authenticated", user=user_name)

            return True

        except Exception as e:
            logger.error("Google People API authentication failed", error=str(e))
            self.is_authenticated = False
            return False

    async def list_files(
        self,
        folder_id: Optional[str] = None,
        page_token: Optional[str] = None,
    ) -> tuple[list[FileInfo], Optional[str]]:
        """
        List people from the company directory.

        Args:
            folder_id: Not used for People API
            page_token: Pagination token

        Returns:
            Tuple of (people as FileInfo, next_page_token)
        """
        if not self.service:
            raise RuntimeError("Not authenticated")

        try:
            # List directory people
            request = self.service.people().listDirectoryPeople(
                sources=self.DIRECTORY_SOURCES,
                readMask=self.READ_MASK,
                pageSize=200,
                pageToken=page_token,
            )

            response = request.execute()

            files = []
            for person in response.get("people", []):
                resource_name = person.get("resourceName", "")
                person_id = resource_name.replace("people/", "")

                # Get display name
                names = person.get("names", [])
                display_name = names[0].get("displayName", "Unknown") if names else "Unknown"

                files.append(
                    FileInfo(
                        id=person_id,
                        name=display_name,
                        mime_type="application/vnd.google.person",
                    )
                )

            next_token = response.get("nextPageToken")
            logger.debug("Listed directory people", count=len(files), has_more=bool(next_token))

            return files, next_token

        except HttpError as e:
            logger.error("Failed to list directory people", error=str(e))
            raise

    async def search_directory(
        self,
        query: str,
        page_size: int = 20,
    ) -> list[dict]:
        """
        Search the company directory for people matching the query.

        Args:
            query: Search query (prefix match on names, emails, etc.)
            page_size: Number of results to return

        Returns:
            List of person dictionaries with contact information
        """
        if not self.service:
            raise RuntimeError("Not authenticated")

        try:
            response = self.service.people().searchDirectoryPeople(
                query=query,
                sources=self.DIRECTORY_SOURCES,
                readMask=self.READ_MASK,
                pageSize=page_size,
            ).execute()

            return response.get("people", [])

        except HttpError as e:
            logger.error("Failed to search directory", query=query, error=str(e))
            raise

    async def get_file_content(self, file_id: str) -> Optional[str]:
        """
        Get person details and format as searchable content.

        Args:
            file_id: Person resource ID (without 'people/' prefix)

        Returns:
            Formatted person content as text
        """
        if not self.service:
            raise RuntimeError("Not authenticated")

        try:
            # Get full person details
            person = self.service.people().get(
                resourceName=f"people/{file_id}",
                personFields=self.READ_MASK,
            ).execute()

            return self._format_person_content(person)

        except HttpError as e:
            if e.resp.status == 404:
                logger.warning("Person not found", person_id=file_id)
                return None
            logger.error("Failed to get person", person_id=file_id, error=str(e))
            raise

    def _format_person_content(self, person: dict) -> str:
        """
        Format a person's data as searchable text content.

        Args:
            person: Person data from the API

        Returns:
            Formatted text content
        """
        lines = []

        # Name
        names = person.get("names", [])
        if names:
            display_name = names[0].get("displayName", "")
            given_name = names[0].get("givenName", "")
            family_name = names[0].get("familyName", "")
            if display_name:
                lines.append(f"Name: {display_name}")
            if given_name or family_name:
                lines.append(f"First Name: {given_name}")
                lines.append(f"Last Name: {family_name}")

        # Email addresses
        emails = person.get("emailAddresses", [])
        for email in emails:
            email_value = email.get("value", "")
            email_type = email.get("type", "work")
            if email_value:
                lines.append(f"Email ({email_type}): {email_value}")

        # Phone numbers
        phones = person.get("phoneNumbers", [])
        for phone in phones:
            phone_value = phone.get("value", "")
            phone_type = phone.get("type", "work")
            if phone_value:
                lines.append(f"Phone ({phone_type}): {phone_value}")

        # Organization / Job
        orgs = person.get("organizations", [])
        for org in orgs:
            company = org.get("name", "")
            title = org.get("title", "")
            department = org.get("department", "")
            if company:
                lines.append(f"Company: {company}")
            if title:
                lines.append(f"Job Title: {title}")
            if department:
                lines.append(f"Department: {department}")

        # Locations
        locations = person.get("locations", [])
        for loc in locations:
            loc_value = loc.get("value", "")
            loc_type = loc.get("type", "")
            if loc_value:
                lines.append(f"Location ({loc_type}): {loc_value}")

        # Addresses
        addresses = person.get("addresses", [])
        for addr in addresses:
            formatted = addr.get("formattedValue", "")
            addr_type = addr.get("type", "work")
            if formatted:
                lines.append(f"Address ({addr_type}): {formatted}")

        # Biography
        bios = person.get("biographies", [])
        for bio in bios:
            bio_value = bio.get("value", "")
            if bio_value:
                lines.append(f"Bio: {bio_value}")

        return "\n".join(lines)

    def _get_person_metadata(self, person: dict) -> dict:
        """Extract metadata from a person record."""
        names = person.get("names", [])
        emails = person.get("emailAddresses", [])
        orgs = person.get("organizations", [])
        photos = person.get("photos", [])

        display_name = names[0].get("displayName", "Unknown") if names else "Unknown"
        primary_email = emails[0].get("value", "") if emails else ""
        job_title = orgs[0].get("title", "") if orgs else ""
        company = orgs[0].get("name", "") if orgs else ""
        department = orgs[0].get("department", "") if orgs else ""
        photo_url = photos[0].get("url", "") if photos else ""

        return {
            "display_name": display_name,
            "email": primary_email,
            "job_title": job_title,
            "company": company,
            "department": department,
            "photo_url": photo_url,
            "all_emails": [e.get("value", "") for e in emails],
            "all_phones": [p.get("value", "") for p in person.get("phoneNumbers", [])],
        }

    def person_to_document(self, person: dict, content: str) -> Document:
        """
        Convert a Google People person to a Document model.

        Args:
            person: Person data from the API
            content: Extracted text content

        Returns:
            Document model instance
        """
        metadata = self._get_person_metadata(person)
        resource_name = person.get("resourceName", "")
        person_id = resource_name.replace("people/", "")

        # Build URL to Google Contacts
        web_url = f"https://contacts.google.com/person/{person_id}"

        return Document(
            id=f"{self.SOURCE_NAME}:{person_id}",
            source=self.SOURCE_NAME,
            source_id=person_id,
            title=metadata["display_name"],
            path=metadata.get("department", "") or metadata.get("company", ""),
            author=metadata.get("email", ""),
            content_type="contact",
            raw_content=content,
            url=web_url,
            created_at=None,  # People API doesn't provide creation date
            modified_at=None,
            last_synced=datetime.utcnow(),
        )

    async def sync(self, full: bool = False) -> SyncResult:
        """
        Sync people from the company directory.

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
            "Google People sync completed",
            success=result.success,
            added=result.added,
            updated=result.updated,
            deleted=result.deleted,
            duration=result.duration_seconds,
        )

        return result

    async def _full_sync(self) -> SyncResult:
        """Perform a full sync of all directory people."""
        logger.info("Starting full Google People sync")

        result = SyncResult(success=True, source=self.SOURCE_NAME)
        chunker = get_chunker()
        embedding_service = get_embedding_service()
        vector_store = get_vector_store()

        try:
            # Request sync token for future incremental syncs
            page_token = None
            new_sync_token = None
            total_processed = 0
            max_people = 5000  # Limit for initial sync

            while total_processed < max_people:
                # Use requestSyncToken on first page to get sync token
                request_params = {
                    "sources": self.DIRECTORY_SOURCES,
                    "readMask": self.READ_MASK,
                    "pageSize": 200,
                }
                if page_token:
                    request_params["pageToken"] = page_token
                else:
                    request_params["requestSyncToken"] = True

                response = self.service.people().listDirectoryPeople(**request_params).execute()

                # Get sync token from first response
                if not new_sync_token:
                    new_sync_token = response.get("nextSyncToken")

                for person in response.get("people", []):
                    if total_processed >= max_people:
                        break

                    try:
                        resource_name = person.get("resourceName", "")
                        person_id = resource_name.replace("people/", "")

                        # Format content
                        content = self._format_person_content(person)
                        if not content:
                            continue

                        # Create document
                        doc = self.person_to_document(person, content)

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

                        # Chunk the document (contacts usually stay as single chunks)
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
                            "Failed to process person",
                            person_id=person.get("resourceName"),
                            error=str(e),
                        )
                        result.errors.append(f"Person {person.get('resourceName')}: {str(e)}")

                next_token = response.get("nextPageToken")
                if not next_token or total_processed >= max_people:
                    break
                page_token = next_token

            result.sync_token = new_sync_token

        except Exception as e:
            logger.error("Full Google People sync failed", error=str(e))
            result.success = False
            result.errors.append(str(e))

        return result

    async def _incremental_sync(self) -> SyncResult:
        """Perform incremental sync using sync token."""
        logger.info("Starting incremental Google People sync", sync_token=self.sync_token)

        result = SyncResult(success=True, source=self.SOURCE_NAME)
        chunker = get_chunker()
        embedding_service = get_embedding_service()
        vector_store = get_vector_store()

        try:
            # List with sync token to get changes
            response = self.service.people().listDirectoryPeople(
                sources=self.DIRECTORY_SOURCES,
                readMask=self.READ_MASK,
                pageSize=200,
                syncToken=self.sync_token,
            ).execute()

            new_sync_token = response.get("nextSyncToken", self.sync_token)

            # Process changed people
            for person in response.get("people", []):
                try:
                    resource_name = person.get("resourceName", "")
                    person_id = resource_name.replace("people/", "")

                    # Check if person was deleted (metadata.deleted = true)
                    metadata = person.get("metadata", {})
                    if metadata.get("deleted"):
                        doc_id = f"{self.SOURCE_NAME}:{person_id}"
                        async with get_db_context() as db:
                            await crud.delete_document(db, doc_id)
                        vector_store.delete_by_document_id(doc_id)
                        result.deleted += 1
                        continue

                    # Format content
                    content = self._format_person_content(person)
                    if not content:
                        continue

                    # Create document
                    doc = self.person_to_document(person, content)

                    # Save to database (upsert)
                    async with get_db_context() as db:
                        existing = await crud.get_document(db, doc.id)
                        if existing:
                            await crud.update_document(
                                db,
                                doc.id,
                                title=doc.title,
                                path=doc.path,
                                author=doc.author,
                                raw_content=doc.raw_content,
                            )
                            result.updated += 1
                        else:
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
                            result.added += 1

                    # Re-chunk and embed
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

                        # Remove old chunks and add new
                        vector_store.delete_by_document_id(doc.id)
                        vector_store.add_chunks(vector_chunks)

                except Exception as e:
                    logger.error(
                        "Failed to process person in incremental sync",
                        person_id=person.get("resourceName"),
                        error=str(e),
                    )
                    result.errors.append(f"Person {person.get('resourceName')}: {str(e)}")

            result.sync_token = new_sync_token

        except HttpError as e:
            if e.resp.status == 410:
                # Sync token expired, need full sync
                logger.warning("Sync token expired, performing full sync")
                return await self._full_sync()
            logger.error("Incremental Google People sync failed", error=str(e))
            result.success = False
            result.errors.append(str(e))

        except Exception as e:
            logger.error("Incremental Google People sync failed", error=str(e))
            result.success = False
            result.errors.append(str(e))

        return result


# Factory function
def create_gpeople_connector() -> GooglePeopleConnector:
    """Create a new Google People connector instance."""
    return GooglePeopleConnector()

