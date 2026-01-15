## Description
Learn async/await in Python - the key to handling multiple requests efficiently, especially when calling external APIs like OpenAI.

## 🎓 Learning Objectives
By the end of this issue, you will understand:
- [ ] What synchronous vs asynchronous code means
- [ ] Why async matters for API servers
- [ ] How to write async functions in Python
- [ ] How to use `await` for non-blocking operations
- [ ] Common async patterns in FastAPI

## 📚 Concepts to Learn

### 1. Sync vs Async: The Coffee Shop Analogy

**Synchronous (Blocking):**
```
Customer 1 orders → Barista makes coffee → Customer 1 gets coffee
                    (everyone waits)
Customer 2 orders → Barista makes coffee → Customer 2 gets coffee
                    (everyone waits)
Customer 3 orders → Barista makes coffee → Customer 3 gets coffee

Total time: 15 minutes (5 min each, sequential)
```

**Asynchronous (Non-Blocking):**
```
Customer 1 orders → Barista starts coffee 1
Customer 2 orders → Barista starts coffee 2
Customer 3 orders → Barista starts coffee 3
                    (all brewing simultaneously)
Coffee 1 ready → Customer 1 gets coffee
Coffee 2 ready → Customer 2 gets coffee
Coffee 3 ready → Customer 3 gets coffee

Total time: ~5 minutes (parallel)
```

### 2. Why This Matters for OSlash

When you search, the server needs to:
1. Call OpenAI API to generate embeddings (takes ~200ms)
2. Search ChromaDB (takes ~50ms)
3. Maybe call OpenAI again for Q&A (takes ~500ms)

**Without async:** Server is stuck waiting, can't handle other requests
**With async:** Server handles other requests while waiting for APIs

```
Request 1: Search "Q4 report"
    │
    ├─► Call OpenAI (waiting 200ms...)
    │   │
    │   │  ← Request 2 arrives: Search "budget"
    │   │     Server can handle it! (async)
    │   │
    │   ▼
    ├─► OpenAI responds, continue processing
    │
    ▼
Response 1 sent
```

### 3. Python Async Syntax

```python
# Regular (sync) function
def get_data():
    result = slow_operation()  # Blocks here
    return result

# Async function
async def get_data():
    result = await slow_operation()  # Doesn't block!
    return result
```

Key rules:
- `async def` - Declares an async function
- `await` - Wait for async operation without blocking
- Can only use `await` inside `async def`

## 🛠️ Hands-On Exercise

### Step 1: Understanding the Difference

Create `server/learn/03_async.py`:

```python
"""
Async/Await - Learning Exercise
Run with: uvicorn learn.03_async:app --reload
"""

import asyncio
import time
from fastapi import FastAPI

app = FastAPI(title="Async Learning")

# Simulate a slow operation (like calling OpenAI)
def slow_sync_operation(name: str, seconds: int) -> str:
    """Synchronous - BLOCKS the server"""
    print(f"[SYNC] Starting {name}...")
    time.sleep(seconds)  # This blocks everything!
    print(f"[SYNC] Finished {name}")
    return f"{name} result"

async def slow_async_operation(name: str, seconds: int) -> str:
    """Asynchronous - doesn't block"""
    print(f"[ASYNC] Starting {name}...")
    await asyncio.sleep(seconds)  # This yields control
    print(f"[ASYNC] Finished {name}")
    return f"{name} result"

# ❌ BAD: Sync endpoint - blocks the entire server
@app.get("/sync")
def sync_endpoint():
    """
    This blocks the server for 3 seconds.
    Try opening two browser tabs to /sync simultaneously.
    Second request waits for first to complete!
    """
    start = time.time()
    result = slow_sync_operation("sync_task", 3)
    elapsed = time.time() - start
    return {"result": result, "elapsed": f"{elapsed:.2f}s"}

# ✅ GOOD: Async endpoint - doesn't block
@app.get("/async")
async def async_endpoint():
    """
    This doesn't block the server.
    Try opening two browser tabs to /async simultaneously.
    Both complete in ~3 seconds total!
    """
    start = time.time()
    result = await slow_async_operation("async_task", 3)
    elapsed = time.time() - start
    return {"result": result, "elapsed": f"{elapsed:.2f}s"}

# Parallel async operations
@app.get("/parallel")
async def parallel_endpoint():
    """
    Run multiple async operations in parallel.
    3 operations of 2 seconds each = ~2 seconds total (not 6!)
    """
    start = time.time()
    
    # Run all three simultaneously
    results = await asyncio.gather(
        slow_async_operation("task1", 2),
        slow_async_operation("task2", 2),
        slow_async_operation("task3", 2),
    )
    
    elapsed = time.time() - start
    return {
        "results": results,
        "elapsed": f"{elapsed:.2f}s",
        "note": "3 x 2-second tasks completed in ~2 seconds!"
    }

# Sequential async operations
@app.get("/sequential")
async def sequential_endpoint():
    """
    Run async operations one after another.
    3 operations of 2 seconds each = ~6 seconds total
    """
    start = time.time()
    
    # Run one at a time (still async, but sequential)
    result1 = await slow_async_operation("task1", 2)
    result2 = await slow_async_operation("task2", 2)
    result3 = await slow_async_operation("task3", 2)
    
    elapsed = time.time() - start
    return {
        "results": [result1, result2, result3],
        "elapsed": f"{elapsed:.2f}s",
        "note": "Sequential = 6 seconds"
    }
```

### Step 2: Test and Compare

```bash
cd server
uvicorn learn.03_async:app --reload

# Test sync (blocks server)
# Open two browser tabs to http://localhost:8000/sync
# Notice: Second tab waits for first!

# Test async (doesn't block)
# Open two browser tabs to http://localhost:8000/async
# Notice: Both complete around the same time!

# Test parallel execution
curl http://localhost:8000/parallel
# Returns in ~2 seconds (not 6!)

# Test sequential execution
curl http://localhost:8000/sequential
# Returns in ~6 seconds
```

### Step 3: Real-World Example (Simulating OpenAI)

```python
import httpx

# Simulating OpenAI API call
async def get_embedding(text: str) -> list[float]:
    """
    In real code, this would call OpenAI.
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.openai.com/v1/embeddings",
            json={"input": text, "model": "text-embedding-3-small"},
            headers={"Authorization": f"Bearer {api_key}"}
        )
        return response.json()["data"][0]["embedding"]
    """
    # Simulate API delay
    await asyncio.sleep(0.2)
    return [0.1, 0.2, 0.3]  # Fake embedding

@app.post("/search-demo")
async def search_demo(query: str):
    """
    Demonstrates async in a search scenario.
    """
    start = time.time()
    
    # Step 1: Get embedding (async, ~200ms)
    embedding = await get_embedding(query)
    
    # Step 2: Search database (async, ~50ms)
    await asyncio.sleep(0.05)  # Simulate DB query
    results = [{"title": "Result 1"}, {"title": "Result 2"}]
    
    elapsed = time.time() - start
    return {
        "query": query,
        "embedding_length": len(embedding),
        "results": results,
        "elapsed_ms": f"{elapsed * 1000:.0f}ms"
    }
```

## 🎯 Key Takeaways

1. **Use `async def` for endpoints that call external APIs**
2. **Use `await` when calling async functions**
3. **Use `asyncio.gather()` to run multiple async operations in parallel**
4. **Never use `time.sleep()` in async code - use `asyncio.sleep()`**
5. **Use `httpx.AsyncClient` instead of `requests` for HTTP calls**

## ✅ Acceptance Criteria
- [ ] Can explain the difference between sync and async
- [ ] Can write async functions with `async def`
- [ ] Can use `await` to call async functions
- [ ] Can use `asyncio.gather()` for parallel operations
- [ ] Understand why async matters for API performance

## 🔗 Resources
- [Python asyncio Documentation](https://docs.python.org/3/library/asyncio.html)
- [FastAPI Async](https://fastapi.tiangolo.com/async/)
- [httpx - Async HTTP Client](https://www.python-httpx.org/)

## ⏱️ Estimated Time
1-2 hours

## ➡️ Next
After completing this, move to Issue #2d: FastAPI Routers & Project Structure

