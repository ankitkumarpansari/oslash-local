## Description
Create integration tests for each connector using recorded API responses.

## Acceptance Criteria
- [ ] Use `pytest-vcr` for recording API responses
- [ ] Test Google Drive sync flow
- [ ] Test Gmail sync flow
- [ ] Test Slack sync flow
- [ ] Test HubSpot sync flow
- [ ] Test OAuth token refresh

## Test Structure
```
server/tests/
├── integration/
│   ├── conftest.py
│   ├── test_gdrive_connector.py
│   ├── test_gmail_connector.py
│   ├── test_slack_connector.py
│   ├── test_hubspot_connector.py
│   └── cassettes/              # VCR recorded responses
│       ├── gdrive_list_files.yaml
│       ├── gmail_list_messages.yaml
│       └── ...
```

## Test Cases

### Google Drive Connector Tests
```python
# tests/integration/test_gdrive_connector.py
import pytest
from pytest_vcr import use_cassette

@pytest.fixture
def gdrive_connector(test_tokens):
    return GoogleDriveConnector(
        token_storage=MockTokenStorage(test_tokens["gdrive"])
    )

@use_cassette("cassettes/gdrive_list_files.yaml")
@pytest.mark.asyncio
async def test_list_files(gdrive_connector):
    files = await gdrive_connector._list_files(max_results=10)
    assert len(files) <= 10
    assert all("id" in f for f in files)
    assert all("name" in f for f in files)

@use_cassette("cassettes/gdrive_get_doc_content.yaml")
@pytest.mark.asyncio
async def test_get_document_content(gdrive_connector):
    content = await gdrive_connector.get_document_content("doc_id_123")
    assert isinstance(content, str)
    assert len(content) > 0

@use_cassette("cassettes/gdrive_incremental_sync.yaml")
@pytest.mark.asyncio
async def test_incremental_sync(gdrive_connector):
    # First sync to get initial state
    result1 = await gdrive_connector.sync(full=True)
    assert result1.documents_added > 0
    
    # Second sync should use change token
    result2 = await gdrive_connector.sync(full=False)
    assert result2.next_sync_token is not None

@pytest.mark.asyncio
async def test_handles_rate_limit(gdrive_connector, mocker):
    # Mock rate limit response
    mocker.patch.object(
        gdrive_connector,
        "_make_request",
        side_effect=[
            httpx.HTTPStatusError("Rate limited", request=None, response=Mock(status_code=429)),
            {"files": []}
        ]
    )
    
    # Should retry and succeed
    files = await gdrive_connector._list_files()
    assert files == []
```

### Gmail Connector Tests
```python
# tests/integration/test_gmail_connector.py
@use_cassette("cassettes/gmail_list_messages.yaml")
@pytest.mark.asyncio
async def test_list_messages(gmail_connector):
    messages = await gmail_connector._list_messages(max_results=10)
    assert len(messages) <= 10

@use_cassette("cassettes/gmail_get_message.yaml")
@pytest.mark.asyncio
async def test_get_message_content(gmail_connector):
    content = await gmail_connector._get_message_content("msg_id_123")
    assert "subject" in content
    assert "body" in content
    assert "from" in content

@pytest.mark.asyncio
async def test_extracts_plain_text_body(gmail_connector):
    # Test with multipart message
    raw_message = {
        "payload": {
            "mimeType": "multipart/alternative",
            "parts": [
                {"mimeType": "text/plain", "body": {"data": base64.b64encode(b"Plain text").decode()}},
                {"mimeType": "text/html", "body": {"data": base64.b64encode(b"<p>HTML</p>").decode()}}
            ]
        }
    }
    body = gmail_connector._extract_body(raw_message["payload"])
    assert body == "Plain text"

@pytest.mark.asyncio
async def test_converts_html_to_text(gmail_connector):
    # Test HTML-only message
    raw_message = {
        "payload": {
            "mimeType": "text/html",
            "body": {"data": base64.b64encode(b"<p>Hello <b>World</b></p>").decode()}
        }
    }
    body = gmail_connector._extract_body(raw_message["payload"])
    assert "Hello" in body
    assert "World" in body
    assert "<p>" not in body
```

### Token Refresh Tests
```python
# tests/integration/test_token_refresh.py
@pytest.mark.asyncio
async def test_auto_refresh_expired_token(token_manager, mocker):
    # Set up expired token
    await token_manager.storage.store(
        provider="gdrive",
        access_token="expired_token",
        refresh_token="valid_refresh",
        expires_in=-100  # Already expired
    )
    
    # Mock refresh endpoint
    mocker.patch("httpx.AsyncClient.post", return_value=Mock(
        json=lambda: {"access_token": "new_token", "expires_in": 3600}
    ))
    
    # Should auto-refresh
    token = await token_manager.get_valid_token("gdrive")
    assert token == "new_token"

@pytest.mark.asyncio
async def test_refresh_failure_raises(token_manager, mocker):
    await token_manager.storage.store(
        provider="gdrive",
        access_token="expired",
        refresh_token="invalid_refresh",
        expires_in=-100
    )
    
    mocker.patch("httpx.AsyncClient.post", return_value=Mock(
        status_code=400,
        json=lambda: {"error": "invalid_grant"}
    ))
    
    with pytest.raises(TokenRefreshError):
        await token_manager.get_valid_token("gdrive")
```

## Recording New Cassettes
```bash
# Set real credentials and run tests to record
RECORD_MODE=new_episodes pytest tests/integration/ -v

# Sanitize recorded cassettes to remove sensitive data
python scripts/sanitize_cassettes.py
```

## Dependencies
- pytest-vcr>=1.0.2
- vcrpy>=6.0.1

## Estimate
5 hours

