"""Authentication API endpoints."""

import secrets
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from oslash.models.schemas import AccountStatus, AuthUrlResponse, Source

router = APIRouter(prefix="/auth", tags=["Authentication"])

# In-memory state storage (will be replaced with proper storage)
pending_states: dict[str, dict] = {}

# OAuth configuration (will come from settings)
OAUTH_CONFIGS = {
    Source.GDRIVE: {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "scopes": [
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/drive.metadata.readonly",
        ],
    },
    Source.GMAIL: {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
    },
    Source.SLACK: {
        "auth_url": "https://slack.com/oauth/v2/authorize",
        "scopes": ["channels:history", "channels:read", "users:read"],
    },
    Source.HUBSPOT: {
        "auth_url": "https://app.hubspot.com/oauth/authorize",
        "scopes": ["crm.objects.contacts.read", "crm.objects.deals.read"],
    },
}


@router.get("/{provider}/url", response_model=AuthUrlResponse)
async def get_auth_url(provider: Source) -> AuthUrlResponse:
    """
    Get OAuth authorization URL for a provider.

    Open this URL in a browser to authorize the connection.
    """
    config = OAUTH_CONFIGS.get(provider)
    if not config:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    state = secrets.token_urlsafe(32)
    pending_states[state] = {
        "provider": provider,
        "created_at": datetime.now(),
    }

    # TODO: Build actual OAuth URL with client_id from settings
    # For now, return a placeholder
    auth_url = f"{config['auth_url']}?state={state}&scope={'+'.join(config['scopes'])}"

    return AuthUrlResponse(
        provider=provider,
        url=auth_url,
        state=state,
    )


@router.get("/{provider}/callback")
async def oauth_callback(provider: Source, code: str, state: str) -> HTMLResponse:
    """
    Handle OAuth callback from provider.

    This endpoint is called by the OAuth provider after user authorizes.
    """
    # Verify state
    if state not in pending_states:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    stored = pending_states.pop(state)
    if stored["provider"] != provider:
        raise HTTPException(status_code=400, detail="State mismatch")

    # TODO: Exchange code for tokens and store them
    # For now, just return success page

    return HTMLResponse(
        """
        <html>
        <head>
            <title>Connected!</title>
            <style>
                body {
                    font-family: system-ui, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: #f5f5f5;
                }
                .card {
                    background: white;
                    padding: 40px;
                    border-radius: 12px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    text-align: center;
                }
                h1 { color: #10b981; margin: 0 0 10px; }
                p { color: #666; margin: 0; }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>✓ Connected!</h1>
                <p>You can close this window.</p>
            </div>
            <script>setTimeout(() => window.close(), 3000)</script>
        </body>
        </html>
        """
    )


@router.delete("/{provider}")
async def disconnect(provider: Source) -> dict:
    """
    Disconnect an account and revoke tokens.
    """
    # TODO: Implement actual token revocation
    return {
        "provider": provider,
        "status": "disconnected",
        "message": f"Successfully disconnected {provider}",
    }


@router.get("/status")
async def get_auth_status() -> dict:
    """
    Get connection status for all providers.
    """
    # TODO: Get actual status from database
    accounts = {}
    for source in Source:
        accounts[source.value] = AccountStatus(
            connected=False,
            email=None,
            document_count=0,
            last_sync=None,
            status="idle",
        ).model_dump()

    return {"accounts": accounts}

