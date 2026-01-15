## Description
Create Slack bot that responds to `o/` mentions in channels, enabling team-wide search with virality loop.

## Why This Matters
As highlighted in [Ramp's Inspect article](https://builders.ramp.com/post/why-we-built-our-background-agent):
> "We believe this is extremely effective, as it not only lets you quickly tackle issues from a variety of sources, but also introduces a virality loop. As people in your organization use it, others will see it."

## Acceptance Criteria
- [ ] Create Slack app with bot capabilities
- [ ] Listen for messages containing `o/`
- [ ] Parse query and call search API
- [ ] Format results using Block Kit
- [ ] Support threaded responses
- [ ] Add "Ask more" button for chat mode
- [ ] Handle rate limits gracefully

## Example Interaction
```
#general

@alice: o/ Q4 sales deck

🤖 OSlash found 3 results:

📄 Q4 Sales Deck Final.pptx
   Google Drive • john@company.com • Dec 1
   "Total revenue increased by 23%..."
   [Open] [Ask more]

📧 RE: Q4 Deck Review  
   Gmail • sarah@company.com • Nov 28
   "Attached the final version..."
   [Open] [Ask more]

💬 #sales-team thread
   Slack • mike • Nov 25
   "Here are the Q4 numbers..."
   [Open] [Ask more]

@bob: Nice! How do I use this?

🤖 Just type o/ followed by your search query in any channel!
   Examples:
   • o/ budget spreadsheet
   • o/ email from John about project
   • o/ slack thread about deployment
```

## Implementation
```python
# slack_bot/app.py
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

app = AsyncApp(token=os.environ["SLACK_BOT_TOKEN"])

@app.message(re.compile(r"o/\s+(.+)", re.IGNORECASE))
async def handle_search(message, say, context):
    query = context["matches"][0]
    user_id = message["user"]
    
    # Search via local API
    results = await search_api.search(query)
    
    # Format as Block Kit
    blocks = format_results_blocks(results, query)
    
    # Reply in thread
    await say(
        blocks=blocks,
        thread_ts=message.get("thread_ts", message["ts"])
    )

def format_results_blocks(results, query):
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"🔍 *Found {len(results)} results for:* _{query}_"
            }
        },
        {"type": "divider"}
    ]
    
    for r in results[:5]:
        icon = {"gdrive": "📄", "gmail": "📧", "slack": "💬", "hubspot": "🏢"}[r["source"]]
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{icon} {r['title']}*\n{r['path']} • {r['author']}\n_{r['snippet'][:100]}..._"
            },
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "Open"},
                "url": r["url"],
                "action_id": f"open_{r['id']}"
            }
        })
    
    return blocks

# Handle "Ask more" button
@app.action(re.compile(r"ask_more_(.+)"))
async def handle_ask_more(ack, body, client):
    await ack()
    doc_id = body["actions"][0]["action_id"].replace("ask_more_", "")
    
    # Open modal for follow-up question
    await client.views_open(
        trigger_id=body["trigger_id"],
        view=create_chat_modal(doc_id)
    )
```

## Slack App Configuration
```yaml
# manifest.yaml
display_information:
  name: OSlash Local
  description: Search your files with o/
  background_color: "#000000"

features:
  bot_user:
    display_name: OSlash
    always_online: true

oauth_config:
  scopes:
    bot:
      - channels:history
      - channels:read
      - chat:write
      - groups:history
      - groups:read
      - im:history
      - im:read
      - users:read

settings:
  event_subscriptions:
    bot_events:
      - message.channels
      - message.groups
      - message.im
  interactivity:
    is_enabled: true
```

## Estimate
8 hours

