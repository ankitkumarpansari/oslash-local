## Description
Integrate Cohere rerank API to improve search result quality by reranking initial vector search results.

## Why Reranking
Vector search returns semantically similar results, but relevance ordering can be improved. Reranking:
- Improves precision for top results
- Better handles keyword-heavy queries
- Cross-encoder models understand query-document relationship better

## Acceptance Criteria
- [ ] Add Cohere API integration
- [ ] Implement reranking step in search pipeline
- [ ] Make reranking optional (configurable)
- [ ] Cache reranking results for repeated queries
- [ ] Add fallback if Cohere API fails

## Search Pipeline with Reranking
```
Query: "Q4 sales numbers from John"
           │
           ▼
┌─────────────────────────────┐
│  1. Embed Query             │
│     OpenAI embeddings       │
└─────────────────────────────┘
           │
           ▼
┌─────────────────────────────┐
│  2. Vector Search           │
│     ChromaDB top 50         │
└─────────────────────────────┘
           │
           ▼
┌─────────────────────────────┐
│  3. Rerank (NEW)            │
│     Cohere rerank-v3        │
│     Input: query + 50 docs  │
│     Output: reordered list  │
└─────────────────────────────┘
           │
           ▼
┌─────────────────────────────┐
│  4. Return Top 10           │
└─────────────────────────────┘
```

## Implementation
```python
# core/reranker.py
import cohere
from typing import List, Optional

class CohereReranker:
    def __init__(self, api_key: str):
        self.client = cohere.Client(api_key)
        self.model = "rerank-english-v3.0"
    
    async def rerank(
        self,
        query: str,
        documents: List[dict],
        top_n: int = 10
    ) -> List[dict]:
        """Rerank documents using Cohere"""
        if not documents:
            return []
        
        # Extract text for reranking
        texts = [self._get_rerank_text(doc) for doc in documents]
        
        try:
            response = self.client.rerank(
                model=self.model,
                query=query,
                documents=texts,
                top_n=top_n,
                return_documents=False
            )
            
            # Reorder documents based on rerank scores
            reranked = []
            for result in response.results:
                doc = documents[result.index].copy()
                doc["rerank_score"] = result.relevance_score
                reranked.append(doc)
            
            return reranked
            
        except Exception as e:
            # Fallback to original order on error
            logger.warning(f"Reranking failed: {e}")
            return documents[:top_n]
    
    def _get_rerank_text(self, doc: dict) -> str:
        """Combine title and snippet for reranking"""
        return f"{doc['title']}\n{doc.get('snippet', '')}"


# Updated search service
class SearchService:
    def __init__(
        self,
        vector_store: VectorStore,
        embedding_service: EmbeddingService,
        reranker: Optional[CohereReranker] = None
    ):
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.reranker = reranker
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        use_reranking: bool = True
    ) -> SearchResponse:
        # 1. Embed query
        embedding = await self.embedding_service.embed_text(query)
        
        # 2. Vector search (over-fetch if reranking)
        fetch_limit = limit * 5 if (use_reranking and self.reranker) else limit * 2
        results = await self.vector_store.search(embedding, n_results=fetch_limit)
        
        # 3. Group by document
        grouped = self._group_by_document(results)
        
        # 4. Rerank if enabled
        if use_reranking and self.reranker and len(grouped) > limit:
            grouped = await self.reranker.rerank(query, grouped, top_n=limit)
        
        return SearchResponse(results=grouped[:limit])
```

## Configuration
```python
# config.py
class Settings(BaseSettings):
    # ... existing settings ...
    
    # Reranking
    rerank_enabled: bool = True
    cohere_api_key: Optional[str] = None
    rerank_model: str = "rerank-english-v3.0"
```

## Cohere Free Tier
- 1,000 rerank calls/month free
- Sufficient for personal use (~33 searches/day)
- No credit card required

## Dependencies
- cohere>=4.40

## Estimate
3 hours

