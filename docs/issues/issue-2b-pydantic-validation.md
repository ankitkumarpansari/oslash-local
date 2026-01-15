## Description
Learn how Pydantic validates data automatically, preventing bugs and making your API more robust.

## 🎓 Learning Objectives
By the end of this issue, you will understand:
- [ ] What data validation is and why it matters
- [ ] How to define Pydantic models
- [ ] How FastAPI uses Pydantic for automatic validation
- [ ] How to add custom validation rules
- [ ] How to handle validation errors

## 📚 Concepts to Learn

### 1. Why Validate Data?

Without validation:
```python
@app.post("/search")
def search(request: dict):
    query = request["query"]  # What if "query" doesn't exist? 💥
    limit = request["limit"]  # What if limit is "abc"? 💥
```

With Pydantic validation:
```python
class SearchRequest(BaseModel):
    query: str      # Must be a string
    limit: int      # Must be an integer

@app.post("/search")
def search(request: SearchRequest):
    # Pydantic already validated! Safe to use.
    query = request.query  # Guaranteed to be a string
    limit = request.limit  # Guaranteed to be an integer
```

### 2. Pydantic Model Basics

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class Document(BaseModel):
    # Required fields
    id: str
    title: str
    
    # Optional field (can be None)
    author: Optional[str] = None
    
    # Field with default value
    source: str = "unknown"
    
    # Field with constraints
    score: float = Field(ge=0, le=1)  # Must be between 0 and 1
    
    # Automatically parsed
    created_at: datetime
```

### 3. Validation in Action

```python
# Valid ✅
doc = Document(
    id="123",
    title="Q4 Report",
    score=0.95,
    created_at="2024-01-15T10:30:00"
)

# Invalid ❌ - Pydantic raises ValidationError
doc = Document(
    id=123,           # Error: must be string
    title="Report",
    score=1.5,        # Error: must be <= 1
    created_at="not a date"  # Error: invalid datetime
)
```

## 🛠️ Hands-On Exercise

### Step 1: Create Pydantic Models for OSlash

Create `server/learn/02_pydantic.py`:

```python
"""
Pydantic Validation - Learning Exercise
Run with: uvicorn learn.02_pydantic:app --reload
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from enum import Enum

app = FastAPI(title="Pydantic Learning")

# Enum for allowed sources
class Source(str, Enum):
    GDRIVE = "gdrive"
    GMAIL = "gmail"
    SLACK = "slack"
    HUBSPOT = "hubspot"

# Search request model
class SearchRequest(BaseModel):
    query: str = Field(
        ...,  # ... means required
        min_length=2,
        max_length=500,
        description="Search query text"
    )
    limit: int = Field(
        default=10,
        ge=1,      # Greater than or equal to 1
        le=100,    # Less than or equal to 100
        description="Maximum results to return"
    )
    sources: Optional[list[Source]] = Field(
        default=None,
        description="Filter by sources"
    )
    
    # Custom validator
    @field_validator('query')
    @classmethod
    def query_must_not_be_empty(cls, v: str) -> str:
        if v.strip() == "":
            raise ValueError("Query cannot be empty or whitespace")
        return v.strip()

# Search result model
class SearchResult(BaseModel):
    id: str
    title: str
    source: Source
    score: float = Field(ge=0, le=1)
    snippet: Optional[str] = None
    url: str
    
    class Config:
        # Allow creating from ORM objects
        from_attributes = True

# Response model
class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total_found: int
    search_time_ms: float

# Endpoint with full validation
@app.post("/search", response_model=SearchResponse)
def search(request: SearchRequest):
    """
    Search with validated input and output.
    
    Try these:
    
    ✅ Valid:
    curl -X POST http://localhost:8000/search \
      -H "Content-Type: application/json" \
      -d '{"query": "test", "limit": 5}'
    
    ❌ Invalid (query too short):
    curl -X POST http://localhost:8000/search \
      -H "Content-Type: application/json" \
      -d '{"query": "a", "limit": 5}'
    
    ❌ Invalid (limit too high):
    curl -X POST http://localhost:8000/search \
      -H "Content-Type: application/json" \
      -d '{"query": "test", "limit": 500}'
    
    ❌ Invalid (bad source):
    curl -X POST http://localhost:8000/search \
      -H "Content-Type: application/json" \
      -d '{"query": "test", "sources": ["invalid"]}'
    """
    # Mock results
    mock_results = [
        SearchResult(
            id="1",
            title=f"Result for {request.query}",
            source=Source.GDRIVE,
            score=0.95,
            snippet=f"Found '{request.query}' in this document...",
            url="https://docs.google.com/..."
        )
    ]
    
    return SearchResponse(
        query=request.query,
        results=mock_results[:request.limit],
        total_found=len(mock_results),
        search_time_ms=12.5
    )

# Example: Nested models
class Author(BaseModel):
    name: str
    email: str

class Document(BaseModel):
    id: str
    title: str
    author: Author  # Nested model
    tags: list[str] = []
    metadata: dict[str, str] = {}

@app.post("/documents")
def create_document(doc: Document):
    """
    Example with nested validation.
    
    curl -X POST http://localhost:8000/documents \
      -H "Content-Type: application/json" \
      -d '{
        "id": "123",
        "title": "My Doc",
        "author": {"name": "Ankit", "email": "ankit@example.com"},
        "tags": ["important", "q4"]
      }'
    """
    return {"message": "Document created", "document": doc}
```

### Step 2: Test Validation

```bash
cd server
uvicorn learn.02_pydantic:app --reload

# Test valid request
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Q4 report", "limit": 5}'

# Test invalid - query too short
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "a"}'
# Returns 422 Unprocessable Entity with error details

# Test invalid - limit out of range
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "limit": 500}'

# View validation in Swagger docs
open http://localhost:8000/docs
```

### Step 3: Understand Error Responses

When validation fails, FastAPI returns:
```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "query"],
      "msg": "String should have at least 2 characters",
      "input": "a",
      "ctx": {"min_length": 2}
    }
  ]
}
```

## ✅ Acceptance Criteria
- [ ] Can create Pydantic models with required and optional fields
- [ ] Can add field constraints (min/max length, ge/le)
- [ ] Can create custom validators with `@field_validator`
- [ ] Can use Enums for restricted choices
- [ ] Can create nested models
- [ ] Can understand validation error responses

## 🔗 Resources
- [Pydantic V2 Documentation](https://docs.pydantic.dev/latest/)
- [FastAPI Request Body](https://fastapi.tiangolo.com/tutorial/body/)
- [Field Types](https://docs.pydantic.dev/latest/concepts/fields/)

## ⏱️ Estimated Time
1-2 hours

## ➡️ Next
After completing this, move to Issue #2c: Async/Await in Python

