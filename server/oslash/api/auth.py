"""Authentication API endpoints with full OAuth 2.0 flow."""

import json
import secrets
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

import httpx
import structlog
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from oslash.config import get_settings
from oslash.db import get_db_context, crud
from oslash.models.schemas import AccountStatus, AuthUrlResponse, Source

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# In-memory state storage (for CSRF protection)
# In production, use Redis or database
pending_states: dict[str, dict] = {}

# OAuth configuration per provider
OAUTH_CONFIGS = {
    Source.GDRIVE: {
        "name": "Google Drive",
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v2/userinfo",
        "scopes": [
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/drive.metadata.readonly",
            "https://www.googleapis.com/auth/userinfo.email",
        ],
        "client_id_key": "google_client_id",
        "client_secret_key": "google_client_secret",
    },
    Source.GMAIL: {
        "name": "Gmail",
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v2/userinfo",
        "scopes": [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/userinfo.email",
        ],
        "client_id_key": "google_client_id",
        "client_secret_key": "google_client_secret",
    },
    Source.SLACK: {
        "name": "Slack",
        "auth_url": "https://slack.com/oauth/v2/authorize",
        "token_url": "https://slack.com/api/oauth.v2.access",
        "userinfo_url": "https://slack.com/api/users.identity",
        "scopes": [
            "channels:history",
            "channels:read",
            "groups:history",
            "groups:read",
            "im:history",
            "im:read",
            "mpim:history",
            "mpim:read",
            "users:read",
        ],
        "client_id_key": "slack_client_id",
        "client_secret_key": "slack_client_secret",
    },
    Source.HUBSPOT: {
        "name": "HubSpot",
        "auth_url": "https://app.hubspot.com/oauth/authorize",
        "token_url": "https://api.hubapi.com/oauth/v1/token",
        "userinfo_url": "https://api.hubapi.com/oauth/v1/access-tokens",
        "scopes": [
            "crm.objects.contacts.read",
            "crm.objects.companies.read",
            "crm.objects.deals.read",
        ],
        "client_id_key": "hubspot_client_id",
        "client_secret_key": "hubspot_client_secret",
    },
}


def get_callback_url(provider: Source) -> str:
    """Get the OAuth callback URL for a provider."""
    settings = get_settings()
    return f"http://{settings.host}:{settings.port}/api/v1/auth/{provider.value}/callback"


def get_client_credentials(provider: Source) -> tuple[Optional[str], Optional[str]]:
    """Get client ID and secret for a provider."""
    settings = get_settings()
    config = OAUTH_CONFIGS.get(provider)
    if not config:
        return None, None

    client_id = getattr(settings, config["client_id_key"], None)
    client_secret = getattr(settings, config["client_secret_key"], None)
    return client_id, client_secret


@router.get("/{provider}/url", response_model=AuthUrlResponse)
async def get_auth_url(provider: Source) -> AuthUrlResponse:
    """
    Get OAuth authorization URL for a provider.

    Open this URL in a browser to authorize the connection.
    The user will be redirected back to the callback URL after authorization.
    """
    config = OAUTH_CONFIGS.get(provider)
    if not config:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    client_id, client_secret = get_client_credentials(provider)
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=400,
            detail=f"OAuth not configured for {provider.value}. "
            f"Set {config['client_id_key'].upper()} and {config['client_secret_key'].upper()} in .env",
        )

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    pending_states[state] = {
        "provider": provider,
        "created_at": datetime.utcnow(),
    }

    # Clean up old states (older than 10 minutes)
    cutoff = datetime.utcnow() - timedelta(minutes=10)
    expired_states = [s for s, v in pending_states.items() if v["created_at"] < cutoff]
    for s in expired_states:
        pending_states.pop(s, None)

    # Build authorization URL
    params = {
        "client_id": client_id,
        "redirect_uri": get_callback_url(provider),
        "scope": " ".join(config["scopes"]),
        "state": state,
        "response_type": "code",
    }

    # Google-specific: request offline access for refresh token
    if provider in [Source.GDRIVE, Source.GMAIL]:
        params["access_type"] = "offline"
        params["prompt"] = "consent"  # Force consent to get refresh token

    # Slack uses comma-separated scopes
    if provider == Source.SLACK:
        params["scope"] = ",".join(config["scopes"])

    auth_url = f"{config['auth_url']}?{urlencode(params)}"

    logger.info("Generated OAuth URL", provider=provider.value, state=state[:8])

    return AuthUrlResponse(
        provider=provider,
        url=auth_url,
        state=state,
    )


@router.get("/{provider}/callback")
async def oauth_callback(
    provider: Source,
    code: str = Query(..., description="Authorization code from provider"),
    state: str = Query(..., description="State parameter for CSRF verification"),
    error: Optional[str] = Query(None, description="Error from provider"),
    error_description: Optional[str] = Query(None, description="Error description"),
) -> HTMLResponse:
    """
    Handle OAuth callback from provider.

    This endpoint is called by the OAuth provider after user authorizes.
    It exchanges the authorization code for access tokens and stores them.
    """
    # Handle errors from provider
    if error:
        logger.error("OAuth error from provider", provider=provider.value, error=error)
        return _error_page(f"Authorization failed: {error_description or error}")

    # Verify state
    if state not in pending_states:
        logger.warning("Invalid OAuth state", provider=provider.value, state=state[:8])
        return _error_page("Invalid or expired authorization. Please try again.")

    stored = pending_states.pop(state)
    if stored["provider"] != provider:
        logger.warning("OAuth state mismatch", provider=provider.value)
        return _error_page("Authorization mismatch. Please try again.")

    config = OAUTH_CONFIGS.get(provider)
    if not config:
        return _error_page(f"Unknown provider: {provider}")

    client_id, client_secret = get_client_credentials(provider)
    if not client_id or not client_secret:
        return _error_page("OAuth not configured for this provider.")

    try:
        # Exchange code for tokens
        tokens = await _exchange_code_for_tokens(
            provider=provider,
            code=code,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=get_callback_url(provider),
            token_url=config["token_url"],
        )

        # Get user info (email)
        user_email = await _get_user_email(
            provider=provider,
            access_token=tokens["access_token"],
            userinfo_url=config["userinfo_url"],
        )

        # Calculate token expiry
        expires_in = tokens.get("expires_in", 3600)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        # Store tokens in database
        async with get_db_context() as db:
            # Store tokens as JSON (in production, encrypt these!)
            token_data = json.dumps({
                "access_token": tokens["access_token"],
                "refresh_token": tokens.get("refresh_token"),
                "token_type": tokens.get("token_type", "Bearer"),
                "expires_in": expires_in,
            })

            await crud.upsert_connected_account(
                db,
                source=provider.value,
                email=user_email,
                token_encrypted=token_data,  # TODO: Encrypt in production
                refresh_token_encrypted=tokens.get("refresh_token"),
                expires_at=expires_at,
            )

            # Initialize sync state
            await crud.get_or_create_sync_state(db, provider.value)

        logger.info(
            "OAuth completed successfully",
            provider=provider.value,
            email=user_email,
        )

        return _success_page(config["name"], user_email)

    except Exception as e:
        logger.error("OAuth token exchange failed", provider=provider.value, error=str(e))
        return _error_page(f"Failed to complete authorization: {str(e)}")


async def _exchange_code_for_tokens(
    provider: Source,
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    token_url: str,
) -> dict:
    """Exchange authorization code for access tokens."""
    async with httpx.AsyncClient() as client:
        # Different providers have different token request formats
        if provider == Source.SLACK:
            # Slack uses query parameters
            response = await client.post(
                token_url,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )
            data = response.json()
            if not data.get("ok"):
                raise ValueError(data.get("error", "Unknown Slack error"))
            return {
                "access_token": data.get("access_token") or data.get("authed_user", {}).get("access_token"),
                "refresh_token": data.get("refresh_token"),
                "token_type": "Bearer",
                "expires_in": data.get("expires_in", 43200),  # Slack tokens last 12 hours
            }

        elif provider == Source.HUBSPOT:
            # HubSpot uses form data
            response = await client.post(
                token_url,
                data={
                    "grant_type": "authorization_code",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
            )
            response.raise_for_status()
            return response.json()

        else:
            # Google (Drive, Gmail) uses form data
            response = await client.post(
                token_url,
                data={
                    "grant_type": "authorization_code",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
            )
            response.raise_for_status()
            return response.json()


async def _get_user_email(
    provider: Source,
    access_token: str,
    userinfo_url: str,
) -> str:
    """Get user email from provider."""
    async with httpx.AsyncClient() as client:
        if provider == Source.SLACK:
            # Slack requires a different endpoint
            response = await client.get(
                "https://slack.com/api/auth.test",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            data = response.json()
            if data.get("ok"):
                # Get user info
                user_response = await client.get(
                    "https://slack.com/api/users.info",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params={"user": data.get("user_id")},
                )
                user_data = user_response.json()
                if user_data.get("ok"):
                    return user_data.get("user", {}).get("profile", {}).get("email", data.get("user", "unknown"))
            return data.get("user", "unknown@slack")

        elif provider == Source.HUBSPOT:
            # HubSpot returns token info
            response = await client.get(
                f"{userinfo_url}/{access_token}",
            )
            data = response.json()
            return data.get("user", "unknown@hubspot")

        else:
            # Google userinfo endpoint
            response = await client.get(
                userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("email", "unknown@google")


@router.post("/{provider}/refresh")
async def refresh_token(provider: Source) -> dict:
    """
    Refresh access token for a provider.

    Called automatically when tokens expire.
    """
    config = OAUTH_CONFIGS.get(provider)
    if not config:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    client_id, client_secret = get_client_credentials(provider)
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="OAuth not configured")

    async with get_db_context() as db:
        account = await crud.get_connected_account(db, provider.value)
        if not account:
            raise HTTPException(status_code=404, detail="Account not connected")

        if not account.refresh_token_encrypted:
            raise HTTPException(status_code=400, detail="No refresh token available")

        try:
            # Refresh the token
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    config["token_url"],
                    data={
                        "grant_type": "refresh_token",
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "refresh_token": account.refresh_token_encrypted,
                    },
                )
                response.raise_for_status()
                tokens = response.json()

            # Update stored tokens
            expires_in = tokens.get("expires_in", 3600)
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

            token_data = json.dumps({
                "access_token": tokens["access_token"],
                "refresh_token": tokens.get("refresh_token", account.refresh_token_encrypted),
                "token_type": tokens.get("token_type", "Bearer"),
                "expires_in": expires_in,
            })

            await crud.update_connected_account(
                db,
                source=provider.value,
                token_encrypted=token_data,
                refresh_token_encrypted=tokens.get("refresh_token", account.refresh_token_encrypted),
                expires_at=expires_at,
            )

            logger.info("Token refreshed", provider=provider.value)
            return {"status": "refreshed", "expires_in": expires_in}

        except Exception as e:
            logger.error("Token refresh failed", provider=provider.value, error=str(e))
            raise HTTPException(status_code=500, detail=f"Token refresh failed: {str(e)}")


@router.delete("/{provider}")
async def disconnect(provider: Source) -> dict:
    """
    Disconnect an account and revoke tokens.
    """
    async with get_db_context() as db:
        account = await crud.get_connected_account(db, provider.value)
        if not account:
            raise HTTPException(status_code=404, detail="Account not connected")

        # Delete account and associated data
        await crud.delete_connected_account(db, provider.value)

        # Delete documents and sync state
        await crud.delete_documents_by_source(db, provider.value)
        await crud.delete_sync_state(db, provider.value)

    logger.info("Account disconnected", provider=provider.value)

    return {
        "provider": provider.value,
        "status": "disconnected",
        "message": f"Successfully disconnected {provider.value}",
    }


@router.get("/status")
async def get_auth_status() -> dict:
    """
    Get connection status for all providers.
    """
    async with get_db_context() as db:
        accounts_list = await crud.get_all_connected_accounts(db)
        accounts_map = {a.source: a for a in accounts_list}

        sync_states = await crud.get_all_sync_states(db)
        sync_map = {s.source: s for s in sync_states}

    accounts = {}
    for source in Source:
        account = accounts_map.get(source.value)
        sync_state = sync_map.get(source.value)

        accounts[source.value] = AccountStatus(
            connected=bool(account),
            email=account.email if account else None,
            document_count=sync_state.document_count if sync_state else 0,
            last_sync=sync_state.last_synced_at.isoformat() if sync_state and sync_state.last_synced_at else None,
            status=sync_state.status if sync_state else "idle",
        ).model_dump()

    return {"accounts": accounts}


def _success_page(provider_name: str, email: str) -> HTMLResponse:
    """Generate success page HTML."""
    return HTMLResponse(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Connected!</title>
            <style>
                * {{ box-sizing: border-box; margin: 0; padding: 0; }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                }}
                .card {{
                    background: white;
                    padding: 48px;
                    border-radius: 16px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                    text-align: center;
                    max-width: 400px;
                }}
                .icon {{
                    font-size: 64px;
                    margin-bottom: 16px;
                }}
                h1 {{
                    color: #10b981;
                    font-size: 28px;
                    margin-bottom: 8px;
                }}
                .provider {{
                    color: #374151;
                    font-size: 18px;
                    margin-bottom: 4px;
                }}
                .email {{
                    color: #6b7280;
                    font-size: 14px;
                    margin-bottom: 24px;
                }}
                .message {{
                    color: #9ca3af;
                    font-size: 14px;
                }}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="icon">✓</div>
                <h1>Connected!</h1>
                <p class="provider">{provider_name}</p>
                <p class="email">{email}</p>
                <p class="message">You can close this window.</p>
            </div>
            <script>setTimeout(() => window.close(), 3000)</script>
        </body>
        </html>
    """)


def _error_page(message: str) -> HTMLResponse:
    """Generate error page HTML."""
    return HTMLResponse(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Connection Failed</title>
            <style>
                * {{ box-sizing: border-box; margin: 0; padding: 0; }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    background: #f3f4f6;
                }}
                .card {{
                    background: white;
                    padding: 48px;
                    border-radius: 16px;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                    text-align: center;
                    max-width: 400px;
                }}
                .icon {{
                    font-size: 64px;
                    margin-bottom: 16px;
                }}
                h1 {{
                    color: #ef4444;
                    font-size: 24px;
                    margin-bottom: 16px;
                }}
                .message {{
                    color: #6b7280;
                    font-size: 14px;
                    line-height: 1.5;
                }}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="icon">✗</div>
                <h1>Connection Failed</h1>
                <p class="message">{message}</p>
            </div>
        </body>
        </html>
    """, status_code=400)
