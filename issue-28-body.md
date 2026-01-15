## Description
Create comprehensive unit tests for embedding service, chunker, search service, and chat engine.

## Acceptance Criteria
- [ ] Test embedding service with mocked OpenAI
- [ ] Test chunking strategies for each content type
- [ ] Test search pipeline with mock vector store
- [ ] Test chat engine with mock LLM
- [ ] Achieve 80%+ coverage on core module

## Test Structure
```
server/tests/
├── conftest.py              # Shared fixtures
├── test_embeddings.py       # Embedding service tests
├── test_chunker.py          # Chunking tests
├── test_search.py           # Search pipeline tests
├── test_chat.py             # Chat engine tests
├── test_api/
│   ├── test_search_endpoint.py
│   └── test_chat_endpoint.py
└── fixtures/
    ├── documents.json       # Sample documents
    └── chunks.json          # Expected chunks
```

## Test Cases

### Embedding Service Tests
```python
# tests/test_embeddings.py
import pytest
from unittest.mock import AsyncMock, patch

@pytest.fixture
def mock_openai():
    with patch("openai.AsyncOpenAI") as mock:
        client = mock.return_value
        client.embeddings.create = AsyncMock(return_value=MockEmbeddingResponse(
            data=[MockEmbedding(embedding=[0.1] * 1536)]
        ))
        yield client

@pytest.mark.asyncio
async def test_embed_single_text(mock_openai, embedding_service):
    result = await embedding_service.embed_text("test query")
    assert len(result) == 1536
    mock_openai.embeddings.create.assert_called_once()

@pytest.mark.asyncio
async def test_embed_batch(mock_openai, embedding_service):
    texts = ["text1", "text2", "text3"]
    results = await embedding_service.embed_batch(texts)
    assert len(results) == 3
    assert all(len(r) == 1536 for r in results)

@pytest.mark.asyncio
async def test_embed_empty_text_raises(embedding_service):
    with pytest.raises(ValueError, match="empty"):
        await embedding_service.embed_text("")

def test_token_counting(embedding_service):
    assert embedding_service.count_tokens("hello world") == 2
    assert embedding_service.count_tokens("") == 0
```

### Chunker Tests
```python
# tests/test_chunker.py
import pytest
from oslash.core.chunker import Chunker
from oslash.models.document import Document

@pytest.fixture
def chunker():
    return Chunker(max_tokens=800, overlap=100)

def test_chunk_email_single_chunk(chunker):
    doc = Document(
        id="1",
        source="gmail",
        content_type="email",
        title="Test Email",
        raw_content="Short email body"
    )
    chunks = chunker.chunk_document(doc)
    assert len(chunks) == 1
    assert chunks[0].metadata["content_type"] == "email"

def test_chunk_document_by_headings(chunker):
    doc = Document(
        id="2",
        source="gdrive",
        content_type="document",
        title="Test Doc",
        raw_content="""
# Section 1
Content for section 1.

# Section 2
Content for section 2.

# Section 3
Content for section 3.
"""
    )
    chunks = chunker.chunk_document(doc)
    assert len(chunks) == 3
    assert chunks[0].metadata["section_title"] == "Section 1"

def test_chunk_long_section_with_overlap(chunker):
    long_content = "word " * 1000  # ~1000 tokens
    doc = Document(
        id="3",
        source="gdrive",
        content_type="document",
        title="Long Doc",
        raw_content=f"# Long Section\n{long_content}"
    )
    chunks = chunker.chunk_document(doc)
    assert len(chunks) > 1
    # Check overlap exists
    assert chunks[0].content[-50:] in chunks[1].content[:150]

def test_chunk_metadata_enrichment(chunker):
    doc = Document(
        id="4",
        source="slack",
        content_type="message",
        title="#general thread",
        path="#general",
        author="john",
        raw_content="Thread content"
    )
    chunks = chunker.chunk_document(doc)
    assert chunks[0].metadata["source"] == "slack"
    assert chunks[0].metadata["author"] == "john"
    assert chunks[0].metadata["path"] == "#general"
```

### Search Pipeline Tests
```python
# tests/test_search.py
import pytest
from oslash.core.search import SearchService

@pytest.fixture
def mock_vector_store():
    store = AsyncMock()
    store.search.return_value = [
        SearchResult(id="1", score=0.95, metadata={"title": "Doc 1"}),
        SearchResult(id="2", score=0.85, metadata={"title": "Doc 2"}),
    ]
    return store

@pytest.mark.asyncio
async def test_search_returns_results(mock_vector_store, mock_embeddings):
    service = SearchService(mock_vector_store, mock_embeddings)
    response = await service.search("test query")
    
    assert len(response.results) == 2
    assert response.results[0].score > response.results[1].score

@pytest.mark.asyncio
async def test_search_with_source_filter(mock_vector_store, mock_embeddings):
    service = SearchService(mock_vector_store, mock_embeddings)
    await service.search("test", sources=["gmail"])
    
    mock_vector_store.search.assert_called_with(
        ANY,
        n_results=ANY,
        where={"source": {"$in": ["gmail"]}}
    )

@pytest.mark.asyncio
async def test_search_deduplicates_chunks(mock_vector_store, mock_embeddings):
    # Return multiple chunks from same document
    mock_vector_store.search.return_value = [
        SearchResult(id="doc1_chunk1", score=0.95, metadata={"document_id": "doc1"}),
        SearchResult(id="doc1_chunk2", score=0.90, metadata={"document_id": "doc1"}),
        SearchResult(id="doc2_chunk1", score=0.85, metadata={"document_id": "doc2"}),
    ]
    
    service = SearchService(mock_vector_store, mock_embeddings)
    response = await service.search("test")
    
    # Should return only best chunk per document
    assert len(response.results) == 2
```

## Dependencies
- pytest>=8.0.0
- pytest-asyncio>=0.23.0
- pytest-cov>=4.1.0
- pytest-mock>=3.12.0

## Estimate
6 hours

