## Description
Build OAuth 2.0 flow handler that opens browser for authorization and captures callback on localhost.

## Acceptance Criteria
- [ ] Create OAuth callback endpoint `/auth/{provider}/callback`
- [ ] Generate state parameter for CSRF protection
- [ ] Exchange auth code for tokens
- [ ] Store tokens securely (encrypted)
- [ ] Handle token refresh automatically
- [ ] Support Google, Slack, HubSpot OAuth

## OAuth Flow
```
┌─────────────────────────────────────────────────────────────┐
│                    OAuth Flow                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. User clicks "Connect Google Drive" in CLI/Extension     │
│                          │                                  │
│                          ▼                                  │
│  2. Server generates state token, returns auth URL          │
│     GET /api/v1/auth/gdrive/url                            │
│     → https://accounts.google.com/oauth?state=xxx          │
│                          │                                  │
│                          ▼                                  │
│  3. Browser opens → User authorizes                         │
│                          │                                  │
│                          ▼                                  │
│  4. Google redirects to callback                            │
│     GET /api/v1/auth/gdrive/callback?code=xxx&state=xxx    │
│                          │                                  │
│                          ▼                                  │
│  5. Server exchanges code for tokens                        │
│     POST https://oauth2.googleapis.com/token               │
│                          │                                  │
│                          ▼                                  │
│  6. Tokens encrypted and stored in SQLite                   │
│                          │                                  │
│                          ▼                                  │
│  7. Redirect to success page / close browser               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Implementation
```python
# api/auth.py
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, HTMLResponse
import secrets
from urllib.parse import urlencode

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory state storage (use Redis in production)
pending_states: dict[str, dict] = {}

OAUTH_CONFIGS = {
    "gdrive": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": [
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/drive.metadata.readonly"
        ]
    },
    "gmail": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": ["https://www.googleapis.com/auth/gmail.readonly"]
    },
    "slack": {
        "auth_url": "https://slack.com/oauth/v2/authorize",
        "token_url": "https://slack.com/api/oauth.v2.access",
        "scopes": ["channels:history", "channels:read", "users:read"]
    },
    "hubspot": {
        "auth_url": "https://app.hubspot.com/oauth/authorize",
        "token_url": "https://api.hubapi.com/oauth/v1/token",
        "scopes": ["crm.objects.contacts.read", "crm.objects.deals.read"]
    }
}

@router.get("/{provider}/url")
async def get_auth_url(provider: str) -> dict:
    """Generate OAuth authorization URL"""
    if provider not in OAUTH_CONFIGS:
        raise HTTPException(404, f"Unknown provider: {provider}")
    
    config = OAUTH_CONFIGS[provider]
    state = secrets.token_urlsafe(32)
    
    # Store state for verification
    pending_states[state] = {"provider": provider, "created_at": datetime.now()}
    
    params = {
        "client_id": settings.get_client_id(provider),
        "redirect_uri": f"http://localhost:8000/api/v1/auth/{provider}/callback",
        "scope": " ".join(config["scopes"]),
        "state": state,
        "response_type": "code",
        "access_type": "offline",  # For refresh token
        "prompt": "consent"
    }
    
    auth_url = f"{config['auth_url']}?{urlencode(params)}"
    return {"url": auth_url, "state": state}

@router.get("/{provider}/callback")
async def oauth_callback(provider: str, code: str, state: str) -> HTMLResponse:
    """Handle OAuth callback"""
    # Verify state
    if state not in pending_states:
        raise HTTPException(400, "Invalid state parameter")
    
    stored = pending_states.pop(state)
    if stored["provider"] != provider:
        raise HTTPException(400, "State mismatch")
    
    # Exchange code for tokens
    config = OAUTH_CONFIGS[provider]
    async with httpx.AsyncClient() as client:
        response = await client.post(
            config["token_url"],
            data={
                "client_id": settings.get_client_id(provider),
                "client_secret": settings.get_client_secret(provider),
                "code": code,
                "redirect_uri": f"http://localhost:8000/api/v1/auth/{provider}/callback",
                "grant_type": "authorization_code"
            }
        )
        tokens = response.json()
    
    # Store encrypted tokens
    await token_storage.store(
        provider=provider,
        access_token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token"),
        expires_in=tokens.get("expires_in", 3600)
    )
    
    # Return success page that auto-closes
    return HTMLResponse("""
    <html>
        <body style="font-family: system-ui; text-align: center; padding: 50px;">
            <h1>✓ Connected!</h1>
            <p>You can close this window.</p>
            <script>setTimeout(() => window.close(), 2000)</script>
        </body>
    </html>
    """)

@router.delete("/{provider}")
async def disconnect(provider: str):
    """Disconnect account and revoke tokens"""
    await token_storage.delete(provider)
    return {"status": "disconnected"}
```

## Token Refresh
```python
# core/token_manager.py
class TokenManager:
    async def get_valid_token(self, provider: str) -> str:
        """Get valid access token, refreshing if needed"""
        account = await self.storage.get(provider)
        if not account:
            raise ValueError(f"No account connected for {provider}")
        
        if account.expires_at < datetime.now() + timedelta(minutes=5):
            # Token expiring soon, refresh it
            await self._refresh_token(provider, account)
            account = await self.storage.get(provider)
        
        return account.access_token
    
    async def _refresh_token(self, provider: str, account: ConnectedAccount):
        """Refresh expired access token"""
        config = OAUTH_CONFIGS[provider]
        async with httpx.AsyncClient() as client:
            response = await client.post(
                config["token_url"],
                data={
                    "client_id": settings.get_client_id(provider),
                    "client_secret": settings.get_client_secret(provider),
                    "refresh_token": account.refresh_token,
                    "grant_type": "refresh_token"
                }
            )
            tokens = response.json()
        
        await self.storage.update(
            provider=provider,
            access_token=tokens["access_token"],
            expires_in=tokens.get("expires_in", 3600)
        )
```

## Estimate
5 hours

