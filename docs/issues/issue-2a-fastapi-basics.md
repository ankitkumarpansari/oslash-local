## Description
Learn the fundamentals of FastAPI by building a simple API from scratch before diving into OSlash implementation.

## 🎓 Learning Objectives
By the end of this issue, you will understand:
- [ ] What an API is and why we need one
- [ ] How HTTP requests and responses work
- [ ] How to create endpoints with FastAPI
- [ ] How to handle different HTTP methods (GET, POST, PUT, DELETE)
- [ ] How to validate input data with Pydantic

## 📚 Concepts to Learn

### 1. What is an API?
**API = Application Programming Interface**

Think of it like a menu at a restaurant:
- The menu lists what you can order (available endpoints)
- You tell the waiter what you want (send a request)
- The kitchen prepares it (server processes)
- You get your food (receive a response)

```
Your App (Client)  ←→  API (Waiter)  ←→  Server (Kitchen)
```

### 2. HTTP Methods
| Method | Purpose | Example |
|--------|---------|---------|
| GET | Retrieve data | Get list of documents |
| POST | Create/Send data | Search with a query |
| PUT | Update data | Update settings |
| DELETE | Remove data | Disconnect an account |

### 3. HTTP Status Codes
| Code | Meaning | When Used |
|------|---------|-----------|
| 200 | OK | Request successful |
| 201 | Created | New resource created |
| 400 | Bad Request | Invalid input |
| 404 | Not Found | Resource doesn't exist |
| 500 | Server Error | Something broke |

## 🛠️ Hands-On Exercise

### Step 1: Create a Simple FastAPI App

Create `server/learn/01_basics.py`:

```python
"""
FastAPI Basics - Learning Exercise
Run with: uvicorn learn.01_basics:app --reload
"""

from fastapi import FastAPI

# Create the FastAPI application
app = FastAPI(
    title="My First API",
    description="Learning FastAPI basics",
    version="1.0.0"
)

# Your first endpoint!
@app.get("/")
def read_root():
    """
    This is the root endpoint.
    Visit http://localhost:8000/ to see this response.
    """
    return {"message": "Hello, World!"}

# GET endpoint with a path parameter
@app.get("/greet/{name}")
def greet_user(name: str):
    """
    Greet a user by name.
    Visit http://localhost:8000/greet/Ankit to try it.
    """
    return {"message": f"Hello, {name}!"}

# GET endpoint with query parameters
@app.get("/search")
def search_items(query: str, limit: int = 10):
    """
    Search with query parameters.
    Visit http://localhost:8000/search?query=test&limit=5
    """
    return {
        "query": query,
        "limit": limit,
        "results": [f"Result {i} for '{query}'" for i in range(limit)]
    }
```

### Step 2: Run and Test

```bash
cd server
uvicorn learn.01_basics:app --reload

# Test in browser or curl:
curl http://localhost:8000/
curl http://localhost:8000/greet/Ankit
curl "http://localhost:8000/search?query=hello&limit=3"

# View auto-generated docs:
open http://localhost:8000/docs
```

### Step 3: Add POST Endpoint

Add to the same file:

```python
from pydantic import BaseModel

# Define the shape of incoming data
class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    filters: list[str] | None = None

@app.post("/search")
def search_with_body(request: SearchRequest):
    """
    POST endpoint that accepts JSON body.
    
    Test with:
    curl -X POST http://localhost:8000/search \
      -H "Content-Type: application/json" \
      -d '{"query": "hello", "limit": 5}'
    """
    return {
        "query": request.query,
        "limit": request.limit,
        "filters": request.filters,
        "results": []
    }
```

## ✅ Acceptance Criteria
- [ ] Can explain what an API is in simple terms
- [ ] Can create a FastAPI app with GET endpoints
- [ ] Can create POST endpoints with request bodies
- [ ] Can use path parameters (`/greet/{name}`)
- [ ] Can use query parameters (`?query=test`)
- [ ] Can view the auto-generated Swagger docs

## 🔗 Resources
- [FastAPI Tutorial](https://fastapi.tiangolo.com/tutorial/)
- [HTTP Methods Explained](https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods)
- [Pydantic Documentation](https://docs.pydantic.dev/)

## ⏱️ Estimated Time
1-2 hours

## ➡️ Next
After completing this, move to Issue #2b: Pydantic Data Validation

