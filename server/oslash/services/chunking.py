"""Semantic chunking engine for document processing."""

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import structlog
import tiktoken

from oslash.config import get_settings
from oslash.db.models import Document

logger = structlog.get_logger(__name__)

# Constants
DEFAULT_CHUNK_SIZE = 800  # tokens
DEFAULT_OVERLAP = 100  # tokens
MAX_CHUNK_SIZE = 1500  # tokens


@dataclass
class ChunkMetadata:
    """Metadata for a document chunk."""

    source: str
    title: str
    path: Optional[str] = None
    author: Optional[str] = None
    created_at: Optional[str] = None
    modified_at: Optional[str] = None
    url: Optional[str] = None
    content_type: Optional[str] = None
    chunk_index: int = 0
    total_chunks: int = 1
    section_title: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "source": self.source,
            "title": self.title,
            "path": self.path or "",
            "author": self.author or "",
            "created_at": self.created_at or "",
            "modified_at": self.modified_at or "",
            "url": self.url or "",
            "content_type": self.content_type or "",
            "chunk_index": self.chunk_index,
            "total_chunks": self.total_chunks,
            "section_title": self.section_title or "",
        }


@dataclass
class Chunk:
    """A document chunk ready for embedding."""

    id: str
    document_id: str
    content: str
    metadata: ChunkMetadata
    embedding: Optional[list[float]] = None

    def to_vector_chunk(self) -> dict:
        """Convert to format for VectorStore."""
        from oslash.vector import Chunk as VectorChunk

        return VectorChunk(
            id=self.id,
            document_id=self.document_id,
            content=self.content,
            embedding=self.embedding,
            metadata=self.metadata.to_dict(),
        )


@dataclass
class Section:
    """A document section (heading + content)."""

    title: Optional[str]
    content: str
    level: int = 0


class Chunker:
    """Semantic chunking engine with content-type-specific strategies."""

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_OVERLAP,
    ):
        """
        Initialize the chunker.

        Args:
            chunk_size: Target chunk size in tokens
            overlap: Overlap between chunks in tokens
        """
        settings = get_settings()
        self.chunk_size = chunk_size or settings.chunk_size
        self.overlap = overlap or settings.chunk_overlap

        # Initialize tokenizer
        try:
            self.tokenizer = tiktoken.encoding_for_model(settings.embedding_model)
        except KeyError:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")

        logger.info(
            "Chunker initialized",
            chunk_size=self.chunk_size,
            overlap=self.overlap,
        )

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.tokenizer.encode(text))

    def chunk_document(self, doc: Document) -> list[Chunk]:
        """
        Chunk a document using the appropriate strategy.

        Args:
            doc: Document to chunk

        Returns:
            List of Chunk objects
        """
        content_type = doc.content_type or "document"

        if content_type == "email":
            chunks = self._chunk_email(doc)
        elif content_type == "message" or content_type == "slack":
            chunks = self._chunk_message(doc)
        elif content_type == "contact" or content_type == "deal":
            chunks = self._chunk_crm_entity(doc)
        else:
            # Default: structured document chunking
            chunks = self._chunk_structured_doc(doc)

        logger.debug(
            "Document chunked",
            doc_id=doc.id,
            content_type=content_type,
            num_chunks=len(chunks),
        )

        return chunks

    def _create_base_metadata(self, doc: Document) -> ChunkMetadata:
        """Create base metadata from document."""
        return ChunkMetadata(
            source=doc.source,
            title=doc.title,
            path=doc.path,
            author=doc.author,
            created_at=doc.created_at.isoformat() if doc.created_at else None,
            modified_at=doc.modified_at.isoformat() if doc.modified_at else None,
            url=doc.url,
            content_type=doc.content_type,
        )

    def _create_chunk(
        self,
        doc: Document,
        content: str,
        index: int,
        total: int,
        section_title: Optional[str] = None,
    ) -> Chunk:
        """Create a chunk with metadata."""
        metadata = self._create_base_metadata(doc)
        metadata.chunk_index = index
        metadata.total_chunks = total
        metadata.section_title = section_title

        chunk_id = f"chunk_{doc.id}_{index}"

        return Chunk(
            id=chunk_id,
            document_id=doc.id,
            content=content.strip(),
            metadata=metadata,
        )

    # =========================================================================
    # Chunking Strategies
    # =========================================================================

    def _chunk_email(self, doc: Document) -> list[Chunk]:
        """
        Chunk an email - keep as single chunk if possible.

        Emails are typically short and context-dependent,
        so we try to keep them whole.
        """
        content = doc.raw_content or ""
        if not content.strip():
            return []

        # If email is small enough, keep as single chunk
        if self.count_tokens(content) <= MAX_CHUNK_SIZE:
            return [self._create_chunk(doc, content, 0, 1)]

        # Otherwise, split by paragraphs with overlap
        return self._split_with_overlap(doc, content)

    def _chunk_message(self, doc: Document) -> list[Chunk]:
        """
        Chunk a Slack message/thread - keep as single chunk.

        Messages and threads should stay together for context.
        """
        content = doc.raw_content or ""
        if not content.strip():
            return []

        # Keep messages as single chunks
        if self.count_tokens(content) <= MAX_CHUNK_SIZE:
            return [self._create_chunk(doc, content, 0, 1)]

        # For very long threads, split carefully
        return self._split_with_overlap(doc, content)

    def _chunk_crm_entity(self, doc: Document) -> list[Chunk]:
        """
        Chunk a HubSpot contact/deal - keep as single chunk.

        CRM entities are structured data and should stay together.
        """
        content = doc.raw_content or ""
        if not content.strip():
            return []

        return [self._create_chunk(doc, content, 0, 1)]

    def _chunk_structured_doc(self, doc: Document) -> list[Chunk]:
        """
        Chunk a structured document (Google Doc, etc.).

        Strategy:
        1. Split by headings into sections
        2. If section is too long, split by paragraphs with overlap
        3. Preserve section titles in metadata
        """
        content = doc.raw_content or ""
        if not content.strip():
            return []

        # Split by headings
        sections = self._split_by_headings(content)

        all_chunks: list[Chunk] = []

        for section in sections:
            section_tokens = self.count_tokens(section.content)

            if section_tokens <= self.chunk_size:
                # Section fits in one chunk
                chunk = self._create_chunk(
                    doc,
                    section.content,
                    len(all_chunks),
                    0,  # Will update total later
                    section.title,
                )
                all_chunks.append(chunk)
            else:
                # Section too long, split with overlap
                sub_chunks = self._split_section_with_overlap(
                    doc, section, len(all_chunks)
                )
                all_chunks.extend(sub_chunks)

        # Update total_chunks in all metadata
        for chunk in all_chunks:
            chunk.metadata.total_chunks = len(all_chunks)

        return all_chunks

    # =========================================================================
    # Splitting Helpers
    # =========================================================================

    def _split_by_headings(self, content: str) -> list[Section]:
        """
        Split content by markdown-style headings.

        Detects:
        - # Heading 1
        - ## Heading 2
        - ### Heading 3
        - **Bold headings**
        - UPPERCASE HEADINGS
        """
        # Pattern for various heading styles
        heading_pattern = r"^(#{1,6}\s+.+|(?:\*\*|__).+(?:\*\*|__)|[A-Z][A-Z\s]{3,}:?)$"

        lines = content.split("\n")
        sections: list[Section] = []
        current_section: Optional[Section] = None
        current_content: list[str] = []

        for line in lines:
            # Check if line is a heading
            is_heading = bool(re.match(heading_pattern, line.strip(), re.MULTILINE))

            if is_heading:
                # Save previous section
                if current_content:
                    text = "\n".join(current_content).strip()
                    if text:
                        if current_section:
                            current_section.content = text
                            sections.append(current_section)
                        else:
                            # Content before first heading
                            sections.append(Section(title=None, content=text))

                # Start new section
                title = line.strip().lstrip("#").strip()
                title = title.strip("*_")  # Remove bold markers
                current_section = Section(title=title, content="")
                current_content = []
            else:
                current_content.append(line)

        # Don't forget last section
        if current_content:
            text = "\n".join(current_content).strip()
            if text:
                if current_section:
                    current_section.content = text
                    sections.append(current_section)
                else:
                    sections.append(Section(title=None, content=text))

        # If no sections found, treat entire content as one section
        if not sections:
            sections.append(Section(title=None, content=content.strip()))

        return sections

    def _split_with_overlap(self, doc: Document, content: str) -> list[Chunk]:
        """Split content into overlapping chunks by paragraphs."""
        paragraphs = self._split_into_paragraphs(content)

        chunks: list[Chunk] = []
        current_chunk: list[str] = []
        current_tokens = 0

        for para in paragraphs:
            para_tokens = self.count_tokens(para)

            if current_tokens + para_tokens <= self.chunk_size:
                current_chunk.append(para)
                current_tokens += para_tokens
            else:
                # Save current chunk
                if current_chunk:
                    chunk_text = "\n\n".join(current_chunk)
                    chunks.append(
                        self._create_chunk(doc, chunk_text, len(chunks), 0)
                    )

                # Start new chunk with overlap
                overlap_paras = self._get_overlap_paragraphs(
                    current_chunk, self.overlap
                )
                current_chunk = overlap_paras + [para]
                current_tokens = sum(self.count_tokens(p) for p in current_chunk)

        # Don't forget last chunk
        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunks.append(self._create_chunk(doc, chunk_text, len(chunks), 0))

        # Update totals
        for chunk in chunks:
            chunk.metadata.total_chunks = len(chunks)

        return chunks

    def _split_section_with_overlap(
        self, doc: Document, section: Section, start_index: int
    ) -> list[Chunk]:
        """Split a section into overlapping chunks."""
        paragraphs = self._split_into_paragraphs(section.content)

        chunks: list[Chunk] = []
        current_chunk: list[str] = []
        current_tokens = 0
        chunk_index = start_index

        for para in paragraphs:
            para_tokens = self.count_tokens(para)

            if current_tokens + para_tokens <= self.chunk_size:
                current_chunk.append(para)
                current_tokens += para_tokens
            else:
                # Save current chunk
                if current_chunk:
                    chunk_text = "\n\n".join(current_chunk)
                    chunks.append(
                        self._create_chunk(
                            doc, chunk_text, chunk_index, 0, section.title
                        )
                    )
                    chunk_index += 1

                # Start new chunk with overlap
                overlap_paras = self._get_overlap_paragraphs(
                    current_chunk, self.overlap
                )
                current_chunk = overlap_paras + [para]
                current_tokens = sum(self.count_tokens(p) for p in current_chunk)

        # Don't forget last chunk
        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunks.append(
                self._create_chunk(doc, chunk_text, chunk_index, 0, section.title)
            )

        return chunks

    def _split_into_paragraphs(self, content: str) -> list[str]:
        """Split content into paragraphs."""
        # Split by double newlines or single newlines with blank lines
        paragraphs = re.split(r"\n\s*\n", content)
        return [p.strip() for p in paragraphs if p.strip()]

    def _get_overlap_paragraphs(
        self, paragraphs: list[str], target_tokens: int
    ) -> list[str]:
        """Get paragraphs for overlap from end of list."""
        if not paragraphs:
            return []

        overlap: list[str] = []
        tokens = 0

        for para in reversed(paragraphs):
            para_tokens = self.count_tokens(para)
            if tokens + para_tokens <= target_tokens:
                overlap.insert(0, para)
                tokens += para_tokens
            else:
                break

        return overlap


# Global instance
_chunker: Optional[Chunker] = None


def get_chunker() -> Chunker:
    """Get or create the global chunker instance."""
    global _chunker
    if _chunker is None:
        _chunker = Chunker()
    return _chunker

