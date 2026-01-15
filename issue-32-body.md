## Description
Create Raycast extension for macOS users to search via Raycast launcher.

## Why Raycast
Raycast is a popular launcher for macOS power users. Adding OSlash search to Raycast provides:
- Instant access via keyboard shortcut
- Native macOS feel
- No browser needed
- Faster than extension popup

## Acceptance Criteria
- [ ] Create Raycast extension project
- [ ] Implement search command
- [ ] Display results in Raycast list
- [ ] Open files directly from results
- [ ] Add "Chat" action for follow-up questions
- [ ] Show sync status in menu bar (optional)

## Example Usage
```
1. Press Cmd+Space (Raycast)
2. Type "os" to filter to OSlash command
3. Type query: "Q4 sales report"
4. Results appear instantly
5. Press Enter to open, Cmd+K for actions
```

## Implementation
```typescript
// src/search.tsx
import { 
  ActionPanel, 
  Action, 
  List, 
  showToast, 
  Toast 
} from "@raycast/api";
import { useState, useEffect } from "react";
import { useFetch } from "@raycast/utils";

interface SearchResult {
  id: string;
  title: string;
  path: string;
  source: string;
  author: string;
  url: string;
  snippet: string;
  score: number;
}

export default function SearchCommand() {
  const [searchText, setSearchText] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (searchText.length < 2) {
      setResults([]);
      return;
    }

    const search = async () => {
      setIsLoading(true);
      try {
        const response = await fetch("http://localhost:8000/api/v1/search", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: searchText, limit: 10 }),
        });
        const data = await response.json();
        setResults(data.results);
      } catch (error) {
        showToast({
          style: Toast.Style.Failure,
          title: "Search failed",
          message: "Is OSlash server running?",
        });
      } finally {
        setIsLoading(false);
      }
    };

    const debounce = setTimeout(search, 300);
    return () => clearTimeout(debounce);
  }, [searchText]);

  const getIcon = (source: string) => {
    const icons: Record<string, string> = {
      gdrive: "📄",
      gmail: "📧",
      slack: "💬",
      hubspot: "🏢",
    };
    return icons[source] || "📎";
  };

  return (
    <List
      isLoading={isLoading}
      onSearchTextChange={setSearchText}
      searchBarPlaceholder="Search your files..."
      throttle
    >
      {results.map((result) => (
        <List.Item
          key={result.id}
          icon={getIcon(result.source)}
          title={result.title}
          subtitle={result.path}
          accessories={[
            { text: result.author },
            { text: `${Math.round(result.score * 100)}%` },
          ]}
          actions={
            <ActionPanel>
              <Action.OpenInBrowser url={result.url} title="Open" />
              <Action.Push
                title="Ask Question"
                target={<ChatView result={result} />}
              />
              <Action.CopyToClipboard
                title="Copy Link"
                content={result.url}
              />
            </ActionPanel>
          }
        />
      ))}
    </List>
  );
}

// Chat view for follow-up questions
function ChatView({ result }: { result: SearchResult }) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const askQuestion = async () => {
    setIsLoading(true);
    try {
      const response = await fetch("http://localhost:8000/api/v1/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          document_ids: [result.id],
        }),
      });
      const data = await response.json();
      setAnswer(data.answer);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <List isLoading={isLoading}>
      <List.Item
        title={result.title}
        subtitle="Context document"
        icon={getIcon(result.source)}
      />
      {answer && (
        <List.Item
          title="Answer"
          subtitle={answer}
          actions={
            <ActionPanel>
              <Action.CopyToClipboard content={answer} />
            </ActionPanel>
          }
        />
      )}
    </List>
  );
}
```

## Package Configuration
```json
// package.json
{
  "name": "oslash-local",
  "title": "OSlash Local",
  "description": "Search your files across Google Drive, Gmail, Slack, and HubSpot",
  "icon": "icon.png",
  "author": "ankitkumarpansari",
  "categories": ["Productivity", "Applications"],
  "license": "MIT",
  "commands": [
    {
      "name": "search",
      "title": "Search Files",
      "description": "Search across all connected sources",
      "mode": "view"
    },
    {
      "name": "status",
      "title": "View Status",
      "description": "Check connection and sync status",
      "mode": "view"
    }
  ],
  "dependencies": {
    "@raycast/api": "^1.64.0",
    "@raycast/utils": "^1.10.0"
  }
}
```

## Estimate
6 hours

