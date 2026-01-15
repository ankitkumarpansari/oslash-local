/**
 * OSlash Local - Background Service Worker
 * Handles communication between content script and local server
 */

const SERVER_URL = "http://localhost:8000";

interface SearchRequest {
  type: "SEARCH_QUERY";
  query: string;
  context: {
    url: string;
    title: string;
    selectedText: string;
  };
  inputRect: {
    top: number;
    left: number;
    width: number;
  };
}

interface PrewarmRequest {
  type: "PREWARM";
}

type Message = SearchRequest | PrewarmRequest;

// Check if server is online
async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${SERVER_URL}/health`, {
      method: "GET",
      signal: AbortSignal.timeout(2000),
    });
    return response.ok;
  } catch {
    return false;
  }
}

// Search API call
async function search(
  query: string,
  context?: SearchRequest["context"]
): Promise<unknown> {
  const response = await fetch(`${SERVER_URL}/api/v1/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, context, limit: 5 }),
  });

  if (!response.ok) {
    throw new Error(`Search failed: ${response.statusText}`);
  }

  return response.json();
}

// Pre-warm the server
async function prewarm(): Promise<void> {
  try {
    await fetch(`${SERVER_URL}/api/v1/warm`, { method: "POST" });
  } catch {
    // Ignore errors for pre-warm
  }
}

// Handle messages from content script
chrome.runtime.onMessage.addListener(
  (message: Message, sender, sendResponse) => {
    if (message.type === "SEARCH_QUERY") {
      search(message.query, message.context)
        .then((results) => {
          if (sender.tab?.id) {
            chrome.tabs.sendMessage(sender.tab.id, {
              type: "SEARCH_RESULTS",
              results,
              inputRect: message.inputRect,
            });
          }
        })
        .catch((error) => {
          if (sender.tab?.id) {
            chrome.tabs.sendMessage(sender.tab.id, {
              type: "SEARCH_ERROR",
              error: error.message,
            });
          }
        });
    }

    if (message.type === "PREWARM") {
      prewarm();
    }

    // Return true to indicate async response
    return true;
  }
);

// Check health on install
chrome.runtime.onInstalled.addListener(async () => {
  const isOnline = await checkHealth();
  console.log(`OSlash Local: Server is ${isOnline ? "online" : "offline"}`);
});

console.log("OSlash Local: Background service worker loaded");

