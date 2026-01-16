/**
 * OSlash Local - Background Service Worker
 * 
 * Handles communication between content scripts and the local server.
 */

import { api } from "../lib/api";

// Track server status
let serverOnline = false;

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
 * Message listener for content script communication
 */
chrome.runtime.onMessage.addListener(
  (message, sender, sendResponse) => {
    const tabId = sender.tab?.id;

    if (!tabId) {
      console.warn("[OSlash] Message received without tab ID");
      return;
    }

    switch (message.type) {
      case "SEARCH_QUERY":
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

      case "CHECK_SERVER":
        checkServerHealth().then((online) => {
          sendResponse({ online });
        });
        return true; // Keep channel open for async response

      case "GET_STATUS":
        api.getStatus()
          .then((status) => sendResponse({ success: true, status }))
          .catch((error) => sendResponse({ success: false, error: error.message }));
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

console.log("[OSlash] Background service worker initialized");
