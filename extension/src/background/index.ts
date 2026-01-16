/**
 * OSlash Local - Background Service Worker
 * 
 * Handles communication between content scripts and the local server.
 * Includes omnibox support for "o <term>" and webNavigation interception
 * for "o/<term>" typed in address bar.
 */

import { api } from "../lib/api";

// Track server status
let serverOnline = false;

// Search engines to intercept when user types "o/term" in address bar
const SEARCH_ENGINES = [
  { host: "www.google.com", param: "q" },
  { host: "www.bing.com", param: "q" },
  { host: "duckduckgo.com", param: "q" },
  { host: "search.yahoo.com", param: "p" },
];

/**
 * Check server health and update status
 */
async function checkServerHealth(): Promise<boolean> {
  try {
    serverOnline = await api.checkHealth();
    console.log(`[OSlash] Server ${serverOnline ? "online" : "offline"}`);

    // Update badge to show status
    if (serverOnline) {
      chrome.action.setBadgeText({ text: "" });
      chrome.action.setBadgeBackgroundColor({ color: "#22c55e" });
    } else {
      chrome.action.setBadgeText({ text: "!" });
      chrome.action.setBadgeBackgroundColor({ color: "#ef4444" });
    }

    return serverOnline;
  } catch {
    serverOnline = false;
    chrome.action.setBadgeText({ text: "!" });
    chrome.action.setBadgeBackgroundColor({ color: "#ef4444" });
    return false;
  }
}

/**
 * Handle search query from content script
 */
async function handleSearchQuery(
  query: string,
  context: { url: string; title: string; selectedText: string },
  inputRect: DOMRect,
  tabId: number
): Promise<void> {
  console.log(`[OSlash] Searching for: "${query}"`);

  // Show loading state
  chrome.tabs.sendMessage(tabId, { type: "SHOW_LOADING" });

  try {
    // Check server health first
    if (!serverOnline) {
      const isOnline = await checkServerHealth();
      if (!isOnline) {
        chrome.tabs.sendMessage(tabId, {
          type: "SEARCH_ERROR",
          error: "Server is offline. Please start the OSlash Local server.",
        });
        return;
      }
    }

    // Perform search
    const startTime = Date.now();
    const response = await api.search(query, {
      limit: 5,
      context,
    });
    const searchTimeMs = Date.now() - startTime;

    console.log(`[OSlash] Found ${response.results.length} results in ${searchTimeMs}ms`);

    // Send results to content script
    chrome.tabs.sendMessage(tabId, {
      type: "SEARCH_RESULTS",
      results: response.results,
      inputRect,
      searchTimeMs,
    });
  } catch (error) {
    console.error("[OSlash] Search error:", error);
    chrome.tabs.sendMessage(tabId, {
      type: "SEARCH_ERROR",
      error: error instanceof Error ? error.message : "Search failed",
    });
  }
}

/**
 * Handle prewarm request
 */
function handlePrewarm(): void {
  if (serverOnline) {
    api.prewarm();
  }
}

/**
 * Message listener for content script and popup communication
 */
chrome.runtime.onMessage.addListener(
  (message, sender, sendResponse) => {
    const tabId = sender.tab?.id;

    switch (message.type) {
      // === Content script messages (require tab ID) ===
      case "SEARCH_QUERY":
        if (!tabId) {
          console.warn("[OSlash] SEARCH_QUERY received without tab ID");
          return;
        }
        handleSearchQuery(
          message.query,
          message.context,
          message.inputRect,
          tabId
        );
        break;

      case "PREWARM":
        handlePrewarm();
        break;

      // === Popup messages (don't require tab ID) ===
      case "CHECK_SERVER":
        checkServerHealth().then((online) => {
          sendResponse({ online });
        });
        return true; // Keep channel open for async response

      case "GET_STATUS":
        api.getStatus()
          .then((status) => sendResponse({ success: true, status }))
          .catch((error) => {
            console.error("[OSlash] GET_STATUS error:", error);
            sendResponse({ success: false, error: error.message });
          });
        return true;

      case "SYNC_ALL":
        api.syncAll(message.full)
          .then(() => sendResponse({ success: true }))
          .catch((error) => sendResponse({ success: false, error: error.message }));
        return true;

      case "SYNC_SOURCE":
        api.syncSource(message.source, message.full)
          .then(() => sendResponse({ success: true }))
          .catch((error) => sendResponse({ success: false, error: error.message }));
        return true;

      case "CONNECT_SOURCE":
        api.connectSource(message.source)
          .then((result) => sendResponse({ success: true, authUrl: result.auth_url }))
          .catch((error) => sendResponse({ success: false, error: error.message }));
        return true;

      case "DISCONNECT_SOURCE":
        api.disconnectSource(message.source)
          .then(() => sendResponse({ success: true }))
          .catch((error) => sendResponse({ success: false, error: error.message }));
        return true;

      default:
        console.warn("[OSlash] Unknown message type:", message.type);
    }
  }
);

/**
 * Handle extension installation
 */
chrome.runtime.onInstalled.addListener((details) => {
  console.log("[OSlash] Extension installed:", details.reason);

  // Initial health check
  checkServerHealth();

  // Set up periodic health checks
  chrome.alarms.create("healthCheck", {
    periodInMinutes: 0.5, // Every 30 seconds
  });
});

/**
 * Handle alarms
 */
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "healthCheck") {
    checkServerHealth();
  }
});

/**
 * Handle extension startup
 */
chrome.runtime.onStartup.addListener(() => {
  console.log("[OSlash] Extension started");
  checkServerHealth();
});

// Initial health check on script load
checkServerHealth();

/**
 * ============================================================
 * OMNIBOX SUPPORT - Handle "o <term>" typed in address bar
 * ============================================================
 * 
 * When user types "o " (o + space) in Chrome's address bar,
 * Chrome activates the omnibox and shows OSlash suggestions.
 */

/**
 * Handle omnibox input - perform search and show suggestions
 */
chrome.omnibox.onInputChanged.addListener(
  async (text: string, suggest: (suggestions: chrome.omnibox.SuggestResult[]) => void) => {
    if (!text.trim()) {
      return;
    }

    console.log(`[OSlash] Omnibox input: "${text}"`);

    try {
      // Check server health first
      if (!serverOnline) {
        const isOnline = await checkServerHealth();
        if (!isOnline) {
          chrome.omnibox.setDefaultSuggestion({
            description: "⚠️ Server offline - Start the OSlash Local server"
          });
          return;
        }
      }

      // Perform search
      const response = await api.search(text, { limit: 5 });
      
      if (response.results.length === 0) {
        chrome.omnibox.setDefaultSuggestion({
          description: `No results for "${text}"`
        });
        return;
      }

      // Set first result as default suggestion
      const firstResult = response.results[0];
      chrome.omnibox.setDefaultSuggestion({
        description: `${escapeXml(firstResult.title)} - ${escapeXml(firstResult.source)}`
      });

      // Convert remaining results to suggestions
      const suggestions: chrome.omnibox.SuggestResult[] = response.results.slice(1).map((result) => ({
        content: result.url || result.title,
        description: `${escapeXml(result.title)} - <dim>${escapeXml(result.source)}</dim>`,
      }));

      suggest(suggestions);
    } catch (error) {
      console.error("[OSlash] Omnibox search error:", error);
      chrome.omnibox.setDefaultSuggestion({
        description: "Search error - try again"
      });
    }
  }
);

/**
 * Handle omnibox selection - navigate to the selected result
 */
chrome.omnibox.onInputEntered.addListener(
  async (text: string, disposition: chrome.omnibox.OnInputEnteredDisposition) => {
    console.log(`[OSlash] Omnibox entered: "${text}", disposition: ${disposition}`);

    // If text is already a URL (user selected a suggestion), navigate directly
    if (text.startsWith("http://") || text.startsWith("https://")) {
      navigateToUrl(text, disposition);
      return;
    }

    // Otherwise, perform search and navigate to first result
    try {
      if (!serverOnline) {
        const isOnline = await checkServerHealth();
        if (!isOnline) {
          return;
        }
      }

      const response = await api.search(text, { limit: 1 });
      
      if (response.results.length > 0 && response.results[0].url) {
        navigateToUrl(response.results[0].url, disposition);
      }
    } catch (error) {
      console.error("[OSlash] Omnibox navigation error:", error);
    }
  }
);

/**
 * Set default suggestion text when omnibox is activated
 */
chrome.omnibox.onInputStarted.addListener(() => {
  chrome.omnibox.setDefaultSuggestion({
    description: "Search your files with OSlash..."
  });
});

/**
 * Navigate to URL based on disposition
 */
function navigateToUrl(url: string, disposition: chrome.omnibox.OnInputEnteredDisposition): void {
  switch (disposition) {
    case "currentTab":
      chrome.tabs.update({ url });
      break;
    case "newForegroundTab":
      chrome.tabs.create({ url, active: true });
      break;
    case "newBackgroundTab":
      chrome.tabs.create({ url, active: false });
      break;
  }
}

/**
 * Escape XML special characters for omnibox descriptions
 */
function escapeXml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

/**
 * ============================================================
 * WEB NAVIGATION INTERCEPTION - Handle "o/term" in address bar
 * ============================================================
 * 
 * When user types "o/term" directly in the address bar, Chrome
 * treats it as a search query and navigates to Google/Bing/etc.
 * We intercept this navigation and redirect to OSlash results.
 */

chrome.webNavigation.onCommitted.addListener(
  async (details: chrome.webNavigation.WebNavigationTransitionCallbackDetails) => {
    // Only intercept navigations from the address bar
    if (!details.transitionQualifiers?.includes("from_address_bar")) {
      return;
    }

    try {
      const url = new URL(details.url);
      
      // Find matching search engine
      const engine = SEARCH_ENGINES.find((e) => url.host === e.host);
      if (!engine) {
        return;
      }

      // Get search query
      const query = url.searchParams.get(engine.param) || "";
      
      // Check if query starts with "o/" (case insensitive)
      if (!query.toLowerCase().startsWith("o/")) {
        return;
      }

      // Extract the search term after "o/"
      const searchTerm = query.slice(2).trim();
      if (!searchTerm) {
        return;
      }

      console.log(`[OSlash] Intercepted o/ search: "${searchTerm}"`);

      // Check server health
      if (!serverOnline) {
        const isOnline = await checkServerHealth();
        if (!isOnline) {
          console.log("[OSlash] Server offline, cannot intercept o/ search");
          return;
        }
      }

      // Perform search
      const response = await api.search(searchTerm, { limit: 1 });
      
      if (response.results.length > 0 && response.results[0].url) {
        // Redirect to the first result
        console.log(`[OSlash] Redirecting to: ${response.results[0].url}`);
        chrome.tabs.update(details.tabId, { url: response.results[0].url });
      } else {
        console.log("[OSlash] No results found for o/ search");
      }
    } catch (error) {
      console.error("[OSlash] Error intercepting o/ search:", error);
    }
  }
);

console.log("[OSlash] Background service worker initialized");
