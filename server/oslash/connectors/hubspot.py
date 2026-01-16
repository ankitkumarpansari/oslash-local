"""HubSpot connector for syncing CRM data."""

import asyncio
import os
import ssl
import time
from datetime import datetime
from typing import Optional

import certifi
import structlog
from hubspot import HubSpot
from hubspot.crm.contacts import ApiException as ContactsApiException
from hubspot.crm.companies import ApiException as CompaniesApiException
from hubspot.crm.deals import ApiException as DealsApiException

from oslash.config import get_settings

# Fix SSL certificate verification on macOS
os.environ.setdefault('SSL_CERT_FILE', certifi.where())
os.environ.setdefault('REQUESTS_CA_BUNDLE', certifi.where())
from oslash.connectors.base import BaseConnector, FileInfo, SyncResult
from oslash.db import get_db_context, crud
from oslash.db.models import Document
from oslash.services.chunking import get_chunker
from oslash.services.embeddings import get_embedding_service
from oslash.vector import get_vector_store, Chunk

logger = structlog.get_logger(__name__)


class HubSpotConnector(BaseConnector):
    """
    HubSpot connector using HubSpot API.

    Supports:
    - Contacts with properties
    - Companies with properties
    - Deals with pipeline stages
    - Notes/engagements
    - Incremental sync with updatedAt
    """

    SOURCE_NAME = "hubspot"

    # Object types to sync
    OBJECT_TYPES = ["contacts", "companies", "deals"]

    # Properties to fetch for each object type
    CONTACT_PROPERTIES = [
        "firstname", "lastname", "email", "phone", "company",
        "jobtitle", "city", "state", "country", "website",
        "lifecyclestage", "hs_lead_status", "createdate", "lastmodifieddate",
    ]

    COMPANY_PROPERTIES = [
        "name", "domain", "industry", "phone", "city", "state", "country",
        "numberofemployees", "annualrevenue", "description",
        "createdate", "hs_lastmodifieddate",
    ]

    DEAL_PROPERTIES = [
        "dealname", "amount", "dealstage", "pipeline", "closedate",
        "hs_priority", "deal_currency_code", "description",
        "createdate", "hs_lastmodifieddate",
    ]

    def __init__(self):
        super().__init__()
        self.client: Optional[HubSpot] = None
        self.settings = get_settings()
        self.portal_id: Optional[str] = None
        self.last_sync_time: Optional[datetime] = None
        self._using_api_key = False

    async def authenticate(self, credentials: dict) -> bool:
        """
        Authenticate with HubSpot using OAuth token or API key.

        Args:
            credentials: Dict with 'access_token', 'token', or 'api_key'

        Returns:
            True if authentication successful
        """
        try:
            # Try to get token from credentials or fall back to API key from settings
            token = (
                credentials.get("access_token") 
                or credentials.get("token") 
                or credentials.get("api_key")
                or self.settings.hubspot_api_key
            )
            
            if not token:
                logger.error("No HubSpot token or API key provided")
                return False

            self._using_api_key = token == self.settings.hubspot_api_key
            self.client = HubSpot(access_token=token)

            # Test the connection by getting contacts
            try:
                contacts = self.client.crm.contacts.basic_api.get_page(limit=1)
                self.portal_id = "connected"
                logger.info("HubSpot connection verified", using_api_key=self._using_api_key)
            except Exception as e:
                logger.error("HubSpot connection test failed", error=str(e))
                return False

            self.is_authenticated = True
            logger.info("HubSpot authenticated", using_api_key=self._using_api_key)

            return True

        except Exception as e:
            logger.error("HubSpot authentication failed", error=str(e))
            self.is_authenticated = False
            return False
    
    async def authenticate_with_api_key(self) -> bool:
        """
        Authenticate using the API key from settings.
        
        Returns:
            True if authentication successful
        """
        if not self.settings.hubspot_api_key:
            logger.error("No HubSpot API key configured")
            return False
        
        return await self.authenticate({"api_key": self.settings.hubspot_api_key})

    async def list_files(
        self,
        folder_id: Optional[str] = None,
        page_token: Optional[str] = None,
    ) -> tuple[list[FileInfo], Optional[str]]:
        """
        List HubSpot objects.

        Args:
            folder_id: Object type (contacts, companies, deals)
            page_token: Pagination cursor

        Returns:
            Tuple of (objects as FileInfo, next_cursor)
        """
        if not self.client:
            raise RuntimeError("Not authenticated")

        object_type = folder_id or "contacts"

        try:
            if object_type == "contacts":
                response = self.client.crm.contacts.basic_api.get_page(
                    limit=100,
                    after=page_token,
                    properties=self.CONTACT_PROPERTIES,
                )
            elif object_type == "companies":
                response = self.client.crm.companies.basic_api.get_page(
                    limit=100,
                    after=page_token,
                    properties=self.COMPANY_PROPERTIES,
                )
            elif object_type == "deals":
                response = self.client.crm.deals.basic_api.get_page(
                    limit=100,
                    after=page_token,
                    properties=self.DEAL_PROPERTIES,
                )
            else:
                return [], None

            files = []
            for obj in response.results:
                props = obj.properties
                name = self._get_object_name(object_type, props)

                files.append(
                    FileInfo(
                        id=obj.id,
                        name=name,
                        mime_type=f"hubspot/{object_type}",
                        path=object_type,
                    )
                )

            # Get next page cursor
            next_cursor = None
            if response.paging and response.paging.next:
                next_cursor = response.paging.next.after

            logger.debug(
                "Listed HubSpot objects",
                type=object_type,
                count=len(files),
                has_more=bool(next_cursor),
            )

            return files, next_cursor

        except Exception as e:
            logger.error("Failed to list HubSpot objects", type=object_type, error=str(e))
            raise

    def _get_object_name(self, object_type: str, props: dict) -> str:
        """Get display name for an object."""
        if object_type == "contacts":
            first = props.get("firstname", "") or ""
            last = props.get("lastname", "") or ""
            name = f"{first} {last}".strip()
            return name or props.get("email", "Unknown Contact")

        elif object_type == "companies":
            return props.get("name", "Unknown Company")

        elif object_type == "deals":
            return props.get("dealname", "Unknown Deal")

        return "Unknown"

    async def get_file_content(self, file_id: str) -> Optional[str]:
        """
        Get HubSpot object content.

        Note: Content is generated in sync methods directly.
        """
        return None

    def _contact_to_document(self, contact) -> Document:
        """Convert HubSpot contact to Document."""
        props = contact.properties
        contact_id = contact.id

        # Build name
        first = props.get("firstname", "") or ""
        last = props.get("lastname", "") or ""
        name = f"{first} {last}".strip() or "Unknown Contact"

        # Build content
        content_parts = [f"Contact: {name}"]

        if props.get("email"):
            content_parts.append(f"Email: {props['email']}")
        if props.get("phone"):
            content_parts.append(f"Phone: {props['phone']}")
        if props.get("company"):
            content_parts.append(f"Company: {props['company']}")
        if props.get("jobtitle"):
            content_parts.append(f"Job Title: {props['jobtitle']}")

        location_parts = []
        if props.get("city"):
            location_parts.append(props["city"])
        if props.get("state"):
            location_parts.append(props["state"])
        if props.get("country"):
            location_parts.append(props["country"])
        if location_parts:
            content_parts.append(f"Location: {', '.join(location_parts)}")

        if props.get("lifecyclestage"):
            content_parts.append(f"Lifecycle Stage: {props['lifecyclestage']}")
        if props.get("hs_lead_status"):
            content_parts.append(f"Lead Status: {props['hs_lead_status']}")

        content = "\n".join(content_parts)

        # Parse dates
        created_at = self._parse_date(props.get("createdate"))
        modified_at = self._parse_date(props.get("lastmodifieddate"))

        # Build URL
        url = f"https://app.hubspot.com/contacts/{self.portal_id}/contact/{contact_id}"

        return Document(
            id=f"{self.SOURCE_NAME}:contact:{contact_id}",
            source=self.SOURCE_NAME,
            source_id=f"contact:{contact_id}",
            title=name,
            path="contacts",
            author=props.get("email", ""),
            content_type="contact",
            raw_content=content,
            url=url,
            created_at=created_at,
            modified_at=modified_at,
            last_synced=datetime.utcnow(),
        )

    def _company_to_document(self, company) -> Document:
        """Convert HubSpot company to Document."""
        props = company.properties
        company_id = company.id

        name = props.get("name", "Unknown Company")

        # Build content
        content_parts = [f"Company: {name}"]

        if props.get("domain"):
            content_parts.append(f"Website: {props['domain']}")
        if props.get("industry"):
            content_parts.append(f"Industry: {props['industry']}")
        if props.get("phone"):
            content_parts.append(f"Phone: {props['phone']}")

        location_parts = []
        if props.get("city"):
            location_parts.append(props["city"])
        if props.get("state"):
            location_parts.append(props["state"])
        if props.get("country"):
            location_parts.append(props["country"])
        if location_parts:
            content_parts.append(f"Location: {', '.join(location_parts)}")

        if props.get("numberofemployees"):
            content_parts.append(f"Employees: {props['numberofemployees']}")
        if props.get("annualrevenue"):
            content_parts.append(f"Annual Revenue: ${props['annualrevenue']}")
        if props.get("description"):
            content_parts.append(f"\nDescription: {props['description']}")

        content = "\n".join(content_parts)

        # Parse dates
        created_at = self._parse_date(props.get("createdate"))
        modified_at = self._parse_date(props.get("hs_lastmodifieddate"))

        # Build URL
        url = f"https://app.hubspot.com/contacts/{self.portal_id}/company/{company_id}"

        return Document(
            id=f"{self.SOURCE_NAME}:company:{company_id}",
            source=self.SOURCE_NAME,
            source_id=f"company:{company_id}",
            title=name,
            path="companies",
            author="",
            content_type="contact",  # Using contact type for CRM entities
            raw_content=content,
            url=url,
            created_at=created_at,
            modified_at=modified_at,
            last_synced=datetime.utcnow(),
        )

    def _deal_to_document(self, deal) -> Document:
        """Convert HubSpot deal to Document."""
        props = deal.properties
        deal_id = deal.id

        name = props.get("dealname", "Unknown Deal")

        # Build content
        content_parts = [f"Deal: {name}"]

        if props.get("amount"):
            currency = props.get("deal_currency_code", "USD")
            content_parts.append(f"Amount: {currency} {props['amount']}")
        if props.get("dealstage"):
            content_parts.append(f"Stage: {props['dealstage']}")
        if props.get("pipeline"):
            content_parts.append(f"Pipeline: {props['pipeline']}")
        if props.get("closedate"):
            content_parts.append(f"Close Date: {props['closedate']}")
        if props.get("hs_priority"):
            content_parts.append(f"Priority: {props['hs_priority']}")
        if props.get("description"):
            content_parts.append(f"\nDescription: {props['description']}")

        content = "\n".join(content_parts)

        # Parse dates
        created_at = self._parse_date(props.get("createdate"))
        modified_at = self._parse_date(props.get("hs_lastmodifieddate"))

        # Build URL
        url = f"https://app.hubspot.com/contacts/{self.portal_id}/deal/{deal_id}"

        return Document(
            id=f"{self.SOURCE_NAME}:deal:{deal_id}",
            source=self.SOURCE_NAME,
            source_id=f"deal:{deal_id}",
            title=name,
            path="deals",
            author="",
            content_type="deal",
            raw_content=content,
            url=url,
            created_at=created_at,
            modified_at=modified_at,
            last_synced=datetime.utcnow(),
        )

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse HubSpot date string."""
        if not date_str:
            return None
        try:
            # HubSpot returns ISO format dates
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except:
            return None

    async def sync(self, full: bool = False) -> SyncResult:
        """
        Sync CRM data from HubSpot.

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

        # Get stored sync time
        async with get_db_context() as db:
            sync_state = await crud.get_or_create_sync_state(db, self.SOURCE_NAME)
            if sync_state.last_sync_token:
                try:
                    self.last_sync_time = datetime.fromisoformat(sync_state.last_sync_token)
                except:
                    self.last_sync_time = None

        result = await self._sync_all_objects(full)
        result.duration_seconds = time.time() - start_time

        # Update sync state
        current_time = datetime.utcnow().isoformat()
        async with get_db_context() as db:
            await crud.update_sync_state(
                db,
                self.SOURCE_NAME,
                status="idle" if result.success else "error",
                last_sync_token=current_time,
                error_message=result.errors[0] if result.errors else None,
                document_count=result.added + result.updated,
            )

        logger.info(
            "HubSpot sync completed",
            success=result.success,
            added=result.added,
            updated=result.updated,
            duration=result.duration_seconds,
        )

        return result

    async def _sync_all_objects(self, full: bool = False) -> SyncResult:
        """Sync all object types."""
        result = SyncResult(success=True, source=self.SOURCE_NAME)
        chunker = get_chunker()
        embedding_service = get_embedding_service()
        vector_store = get_vector_store()

        for object_type in self.OBJECT_TYPES:
            try:
                logger.info(f"Syncing HubSpot {object_type}")

                # Fetch objects
                objects = await self._fetch_all_objects(object_type, full)

                for obj in objects:
                    try:
                        # Convert to document
                        if object_type == "contacts":
                            doc = self._contact_to_document(obj)
                        elif object_type == "companies":
                            doc = self._company_to_document(obj)
                        elif object_type == "deals":
                            doc = self._deal_to_document(obj)
                        else:
                            continue

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
                        logger.error(
                            f"Failed to process {object_type}",
                            object_id=obj.id,
                            error=str(e),
                        )
                        result.errors.append(f"{object_type} {obj.id}: {str(e)}")

                # Rate limiting between object types
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Failed to sync {object_type}", error=str(e))
                result.errors.append(f"{object_type}: {str(e)}")

        return result

    async def _fetch_all_objects(self, object_type: str, full: bool = False) -> list:
        """Fetch all objects of a type with pagination."""
        objects = []
        after = None

        # Build filter for incremental sync
        filter_groups = None
        if not full and self.last_sync_time:
            # Use lastmodifieddate filter for incremental sync
            filter_groups = [{
                "filters": [{
                    "propertyName": "lastmodifieddate" if object_type == "contacts" else "hs_lastmodifieddate",
                    "operator": "GTE",
                    "value": int(self.last_sync_time.timestamp() * 1000),
                }]
            }]

        try:
            while True:
                if object_type == "contacts":
                    if filter_groups and not full:
                        # Use search API for filtered results
                        response = self.client.crm.contacts.search_api.do_search(
                            public_object_search_request={
                                "filter_groups": filter_groups,
                                "properties": self.CONTACT_PROPERTIES,
                                "limit": 100,
                                "after": after,
                            }
                        )
                    else:
                        response = self.client.crm.contacts.basic_api.get_page(
                            limit=100,
                            after=after,
                            properties=self.CONTACT_PROPERTIES,
                        )

                elif object_type == "companies":
                    if filter_groups and not full:
                        response = self.client.crm.companies.search_api.do_search(
                            public_object_search_request={
                                "filter_groups": filter_groups,
                                "properties": self.COMPANY_PROPERTIES,
                                "limit": 100,
                                "after": after,
                            }
                        )
                    else:
                        response = self.client.crm.companies.basic_api.get_page(
                            limit=100,
                            after=after,
                            properties=self.COMPANY_PROPERTIES,
                        )

                elif object_type == "deals":
                    if filter_groups and not full:
                        response = self.client.crm.deals.search_api.do_search(
                            public_object_search_request={
                                "filter_groups": filter_groups,
                                "properties": self.DEAL_PROPERTIES,
                                "limit": 100,
                                "after": after,
                            }
                        )
                    else:
                        response = self.client.crm.deals.basic_api.get_page(
                            limit=100,
                            after=after,
                            properties=self.DEAL_PROPERTIES,
                        )
                else:
                    break

                objects.extend(response.results)

                # Check for more pages
                if response.paging and response.paging.next:
                    after = response.paging.next.after
                else:
                    break

                # Rate limiting
                await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Failed to fetch {object_type}", error=str(e))

        logger.debug(f"Fetched {len(objects)} {object_type}")
        return objects


# Factory function
def create_hubspot_connector() -> HubSpotConnector:
    """Create a new HubSpot connector instance."""
    return HubSpotConnector()

