## Description
Create comprehensive user documentation including setup guide, usage instructions, and troubleshooting.

## Documentation Sections

### 1. README.md (Quick Start)
- Project overview
- Key features
- Quick installation
- Basic usage example

### 2. docs/installation.md
- System requirements
- Python setup (3.11+)
- Installing dependencies
- Extension installation
- CLI installation

### 3. docs/configuration.md
- Environment variables reference
- Config file options
- API keys setup (OpenAI, Google, Slack, HubSpot)

### 4. docs/connecting-accounts.md
- Google Drive setup
  - Creating Google Cloud project
  - Enabling Drive API
  - OAuth consent screen setup
  - Getting client credentials
- Gmail setup
  - Enabling Gmail API
  - Scopes explanation
- Slack setup
  - Creating Slack app
  - Required scopes
  - Installing to workspace
- HubSpot setup
  - Developer account
  - Private app creation
  - Required scopes

### 5. docs/usage.md
- Browser extension usage
  - o/ trigger syntax
  - Keyboard shortcuts
  - Search modifiers
- CLI usage
  - TUI mode
  - Command-line search
  - Account management
- Search tips
  - Source filters (email:, doc:, slack:)
  - Date filters
  - Author filters

### 6. docs/api-reference.md
- REST API endpoints
- WebSocket events
- Request/response schemas

### 7. docs/troubleshooting.md
- Common issues
  - Server not starting
  - Extension not connecting
  - OAuth errors
  - Sync failures
- Debug mode
- Log locations

## Sample Documentation

### docs/connecting-accounts.md
```markdown
# Connecting Accounts

## Google Drive & Gmail

Both Google Drive and Gmail use the same Google Cloud project.

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project named "OSlash Local"
3. Enable the following APIs:
   - Google Drive API
   - Gmail API

### Step 2: Configure OAuth Consent Screen

1. Go to APIs & Services > OAuth consent screen
2. Select "External" user type
3. Fill in app information:
   - App name: OSlash Local
   - User support email: your email
   - Developer contact: your email
4. Add scopes:
   - `https://www.googleapis.com/auth/drive.readonly`
   - `https://www.googleapis.com/auth/gmail.readonly`
5. Add your email as a test user

### Step 3: Create OAuth Credentials

1. Go to APIs & Services > Credentials
2. Create OAuth client ID
3. Application type: Desktop app
4. Download the JSON file
5. Add to your `.env`:
   ```
   GOOGLE_CLIENT_ID=your_client_id
   GOOGLE_CLIENT_SECRET=your_client_secret
   ```

### Step 4: Connect in OSlash

```bash
# Using CLI
oslash accounts connect gdrive
oslash accounts connect gmail

# Or use the browser extension popup
```

## Slack

### Step 1: Create Slack App

1. Go to [Slack API](https://api.slack.com/apps)
2. Create New App > From scratch
3. Name: "OSlash Local"
4. Select your workspace

### Step 2: Configure OAuth Scopes

Add these Bot Token Scopes:
- `channels:history`
- `channels:read`
- `groups:history`
- `groups:read`
- `im:history`
- `im:read`
- `users:read`

### Step 3: Install to Workspace

1. Go to OAuth & Permissions
2. Install to Workspace
3. Copy the Bot User OAuth Token
4. Add to your `.env`:
   ```
   SLACK_CLIENT_ID=your_client_id
   SLACK_CLIENT_SECRET=your_client_secret
   ```

## HubSpot

### Step 1: Create Developer Account

1. Go to [HubSpot Developers](https://developers.hubspot.com/)
2. Create a developer account if needed

### Step 2: Create Private App

1. Go to Settings > Integrations > Private Apps
2. Create a private app
3. Add scopes:
   - `crm.objects.contacts.read`
   - `crm.objects.companies.read`
   - `crm.objects.deals.read`
4. Copy the access token
5. Add to your `.env`:
   ```
   HUBSPOT_CLIENT_ID=your_client_id
   HUBSPOT_CLIENT_SECRET=your_client_secret
   ```
```

### docs/troubleshooting.md
```markdown
# Troubleshooting

## Server Issues

### Server won't start

**Symptom:** `uvicorn` fails to start or crashes immediately.

**Solutions:**
1. Check if port 8000 is already in use:
   ```bash
   lsof -i :8000
   ```
2. Verify Python version (requires 3.11+):
   ```bash
   python --version
   ```
3. Check logs:
   ```bash
   cat ~/.oslash/logs/server.log
   ```

### OpenAI API errors

**Symptom:** "Invalid API key" or rate limit errors.

**Solutions:**
1. Verify your API key is set:
   ```bash
   echo $OPENAI_API_KEY
   ```
2. Check API key validity at [OpenAI Dashboard](https://platform.openai.com/)
3. For rate limits, wait and retry

## Extension Issues

### Extension not detecting o/

**Symptom:** Typing `o/` doesn't trigger search.

**Solutions:**
1. Check if server is running:
   - Click extension icon
   - Should show "Online" status
2. Reload the page
3. Check if the input field is supported (some custom editors may not work)

### Results not showing

**Symptom:** Search triggers but no results appear.

**Solutions:**
1. Verify documents are indexed:
   ```bash
   oslash status
   ```
2. Try a broader search term
3. Check sync status in extension popup

## Sync Issues

### Google Drive sync fails

**Symptom:** "Authentication failed" or "Token expired"

**Solutions:**
1. Disconnect and reconnect:
   ```bash
   oslash accounts disconnect gdrive
   oslash accounts connect gdrive
   ```
2. Check Google Cloud Console for API quota

### Slack sync incomplete

**Symptom:** Missing channels or messages.

**Solutions:**
1. Verify bot is added to channels
2. Check Slack app scopes include `channels:history`
3. Re-authorize with updated scopes

## Debug Mode

Enable verbose logging:
```bash
OSLASH_LOG_LEVEL=DEBUG oslash tui
```

View logs:
```bash
tail -f ~/.oslash/logs/server.log
```
```

## Acceptance Criteria
- [ ] README with quick start
- [ ] Installation guide (server, extension, CLI)
- [ ] Configuration reference
- [ ] Connecting accounts guide (all 4 providers)
- [ ] Usage examples
- [ ] Troubleshooting FAQ
- [ ] API reference

## Estimate
4 hours

