## Description
Migrate to Cloudflare Durable Objects for multi-device support, enabling search from any device while keeping data synced.

## Why Multi-Device
Currently, OSlash Local runs entirely on one machine. Multi-device support enables:
- Search from laptop, phone, or any browser
- Shared index across devices
- Team collaboration (future)
- No need to keep local server running

## Architecture Change
```
CURRENT (Local-Only)
┌─────────────────────────────────────────┐
│  Your Machine                           │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐ │
│  │Extension│→ │ FastAPI │→ │ChromaDB │ │
│  └─────────┘  └─────────┘  └─────────┘ │
└─────────────────────────────────────────┘

FUTURE (Multi-Device)
┌─────────────────────────────────────────────────────────────┐
│  Cloudflare Edge                                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Durable Object (per user)                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │   │
│  │  │ SQLite      │  │ Vector      │  │ WebSocket  │  │   │
│  │  │ (metadata)  │  │ (embeddings)│  │ (realtime) │  │   │
│  │  └─────────────┘  └─────────────┘  └────────────┘  │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
           ▲              ▲              ▲
           │              │              │
    ┌──────┴──────┐ ┌─────┴─────┐ ┌─────┴─────┐
    │   Laptop    │ │   Phone   │ │  Tablet   │
    │  Extension  │ │    PWA    │ │   CLI     │
    └─────────────┘ └───────────┘ └───────────┘
```

## Key Components

### 1. Cloudflare Worker (API Gateway)
```typescript
// worker/src/index.ts
import { Hono } from 'hono';

export interface Env {
  USER_SESSIONS: DurableObjectNamespace;
}

const app = new Hono<{ Bindings: Env }>();

app.post('/api/search', async (c) => {
  const userId = c.req.header('X-User-Id');
  const stub = c.env.USER_SESSIONS.get(
    c.env.USER_SESSIONS.idFromName(userId)
  );
  return stub.fetch(c.req.raw);
});

export default app;
```

### 2. Durable Object (Per-User State)
```typescript
// worker/src/session.ts
import { DurableObject } from 'cloudflare:workers';

export class UserSession extends DurableObject {
  private sql: SqlStorage;
  
  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env);
    this.sql = ctx.storage.sql;
    this.initializeSchema();
  }
  
  private initializeSchema() {
    this.sql.exec(`
      CREATE TABLE IF NOT EXISTS documents (
        id TEXT PRIMARY KEY,
        source TEXT,
        title TEXT,
        content TEXT,
        embedding BLOB,
        metadata TEXT
      )
    `);
  }
  
  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);
    
    if (url.pathname === '/search') {
      return this.handleSearch(request);
    }
    
    return new Response('Not found', { status: 404 });
  }
  
  private async handleSearch(request: Request): Promise<Response> {
    const { query } = await request.json();
    
    // Get embedding from OpenAI
    const embedding = await this.getEmbedding(query);
    
    // Vector search using SQLite with vector extension
    const results = this.sql.exec(`
      SELECT id, title, source, 
             vector_distance(embedding, ?) as distance
      FROM documents
      ORDER BY distance
      LIMIT 10
    `, [embedding]).toArray();
    
    return Response.json({ results });
  }
}
```

### 3. Sync Worker (Background)
```typescript
// Runs periodically to sync from sources
export class SyncWorker {
  async scheduled(event: ScheduledEvent, env: Env) {
    // Get all users with connected accounts
    const users = await this.getActiveUsers(env);
    
    for (const userId of users) {
      const stub = env.USER_SESSIONS.get(
        env.USER_SESSIONS.idFromName(userId)
      );
      await stub.fetch(new Request('https://internal/sync'));
    }
  }
}
```

## Migration Path
1. **Phase 1**: Add Cloudflare Worker as optional backend
2. **Phase 2**: Implement vector search in Durable Objects
3. **Phase 3**: Add sync workers for each connector
4. **Phase 4**: Mobile PWA client
5. **Phase 5**: Deprecate local-only mode (optional)

## Cloudflare Pricing
- Workers: 100K requests/day free
- Durable Objects: $0.15/million requests
- Storage: $0.20/GB/month
- **Estimated cost**: $5-10/month for heavy personal use

## Acceptance Criteria
- [ ] Create Cloudflare Worker project
- [ ] Implement Durable Object with SQLite
- [ ] Add vector search capability
- [ ] Migrate sync logic to Workers
- [ ] Update extension to support both local and cloud
- [ ] Add authentication (Cloudflare Access or custom)
- [ ] Create mobile PWA

## Dependencies
- Cloudflare Workers account
- Wrangler CLI
- hono (web framework)

## Estimate
12 hours (complex, multi-phase)

