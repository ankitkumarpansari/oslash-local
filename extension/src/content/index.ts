/**
 * OSlash Local - Content Script
 * 
 * Detects `o/ {query}` pattern in text inputs and triggers search overlay.
 */

import type { SearchQueryMessage, PrewarmMessage, PageContext, SearchResult, Position } from "../lib/types";

// Configuration
const TRIGGER_PATTERN = /o\/\s+(.{2,})/;
const PREWARM_PATTERN = /o\/\s?$/;
const DEBOUNCE_MS = 300;
const PREWARM_DEBOUNCE_MS = 100;

// State
let currentQuery = "";
let overlayVisible = false;
let activeInput: HTMLElement | null = null;

/**
 * Debounce utility function
 */
function debounce<T extends (...args: any[]) => void>(
  fn: T,
  ms: number
): (...args: Parameters<T>) => void {
  let timeoutId: ReturnType<typeof setTimeout>;
  return (...args: Parameters<T>) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => fn(...args), ms);
  };
}

/**
 * Get the text value from an input element
 */
function getInputValue(element: HTMLElement): string {
  if (element instanceof HTMLInputElement) {
    return element.value;
  }
  if (element instanceof HTMLTextAreaElement) {
    return element.value;
  }
  if (element.isContentEditable) {
    return element.innerText || element.textContent || "";
  }
  return "";
}

/**
 * Get current page context for search
 */
function getPageContext(): PageContext {
  return {
    url: window.location.href,
    title: document.title,
    selectedText: window.getSelection()?.toString() || "",
  };
}

/**
 * Calculate overlay position based on input element
 */
function calculateOverlayPosition(element: HTMLElement): Position {
  const rect = element.getBoundingClientRect();
  const scrollTop = window.scrollY || document.documentElement.scrollTop;
  const scrollLeft = window.scrollX || document.documentElement.scrollLeft;

  // Position below the input, or above if not enough space
  const spaceBelow = window.innerHeight - rect.bottom;
  const overlayHeight = 400; // Approximate overlay height

  let top: number;
  if (spaceBelow >= overlayHeight || spaceBelow > rect.top) {
    // Position below
    top = rect.bottom + scrollTop + 4;
  } else {
    // Position above
    top = rect.top + scrollTop - overlayHeight - 4;
  }

  return {
    top,
    left: rect.left + scrollLeft,
    width: Math.max(rect.width, 384), // Minimum 384px (w-96)
  };
}

/**
 * Handle input event to detect o/ pattern
 */
const handleInput = debounce((event: Event) => {
  const target = event.target as HTMLElement;
  if (!target) return;

  const text = getInputValue(target);
  const match = text.match(TRIGGER_PATTERN);

  if (match && match[1].length >= 2) {
    const query = match[1].trim();

    // Only send if query changed
    if (query !== currentQuery) {
      currentQuery = query;
      activeInput = target;

      const rect = target.getBoundingClientRect();

      // Send search request to background script
      const message: SearchQueryMessage = {
        type: "SEARCH_QUERY",
        query,
        context: getPageContext(),
        inputRect: rect,
      };

      chrome.runtime.sendMessage(message);
      console.log("[OSlash] Search query:", query);
    }
  } else if (overlayVisible && !text.includes("o/")) {
    // Hide overlay if o/ is removed
    hideOverlay();
  }
}, DEBOUNCE_MS);

/**
 * Handle input for pre-warming (faster response)
 */
const handlePrewarm = debounce((event: Event) => {
  const target = event.target as HTMLElement;
  if (!target) return;

  const text = getInputValue(target);

  if (PREWARM_PATTERN.test(text)) {
    const message: PrewarmMessage = { type: "PREWARM" };
    chrome.runtime.sendMessage(message);
    console.log("[OSlash] Pre-warming search pipeline");
  }
}, PREWARM_DEBOUNCE_MS);

/**
 * Create and show the search overlay
 */
function showOverlay(results: SearchResult[], position: Position, query: string): void {
  // Remove existing overlay
  hideOverlay();

  // Create overlay container
  const overlay = document.createElement("div");
  overlay.id = "oslash-overlay";
  overlay.className = "oslash-overlay";

  // Create shadow DOM for style isolation
  const shadow = overlay.attachShadow({ mode: "open" });

  // Add styles
  const styles = document.createElement("style");
  styles.textContent = getOverlayStyles();
  shadow.appendChild(styles);

  // Create overlay content
  const content = document.createElement("div");
  content.className = "overlay-container";
  content.style.cssText = `
    position: fixed;
    top: ${position.top}px;
    left: ${position.left}px;
    width: ${position.width}px;
    max-width: 480px;
    z-index: 2147483647;
  `;

  // Render results or loading state
  content.innerHTML = renderOverlayContent(results, query);
  shadow.appendChild(content);

  // Add to page
  document.body.appendChild(overlay);
  overlayVisible = true;

  // Setup keyboard navigation
  setupKeyboardNavigation(shadow, results);

  // Setup click outside to dismiss
  setTimeout(() => {
    document.addEventListener("click", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
  }, 0);
}

/**
 * Hide the search overlay
 */
function hideOverlay(): void {
  const overlay = document.getElementById("oslash-overlay");
  if (overlay) {
    overlay.remove();
  }
  overlayVisible = false;
  currentQuery = "";
  document.removeEventListener("click", handleClickOutside);
  document.removeEventListener("keydown", handleEscape);
}

/**
 * Handle click outside overlay to dismiss
 */
function handleClickOutside(event: MouseEvent): void {
  const overlay = document.getElementById("oslash-overlay");
  if (overlay && !overlay.contains(event.target as Node)) {
    hideOverlay();
  }
}

/**
 * Handle Escape key to dismiss
 */
function handleEscape(event: KeyboardEvent): void {
  if (event.key === "Escape") {
    hideOverlay();
  }
}

/**
 * Setup keyboard navigation for results
 */
function setupKeyboardNavigation(shadow: ShadowRoot, results: SearchResult[]): void {
  let selectedIndex = 0;
  const items = shadow.querySelectorAll(".result-item");

  function updateSelection(): void {
    items.forEach((item, i) => {
      if (i === selectedIndex) {
        item.classList.add("selected");
      } else {
        item.classList.remove("selected");
      }
    });
  }

  updateSelection();

  const handleKeyDown = (event: KeyboardEvent) => {
    if (!overlayVisible) return;

    switch (event.key) {
      case "ArrowDown":
        event.preventDefault();
        selectedIndex = Math.min(selectedIndex + 1, results.length - 1);
        updateSelection();
        break;

      case "ArrowUp":
        event.preventDefault();
        selectedIndex = Math.max(selectedIndex - 1, 0);
        updateSelection();
        break;

      case "Enter":
        event.preventDefault();
        if (results[selectedIndex]?.url) {
          window.open(results[selectedIndex].url!, "_blank");
          hideOverlay();
        }
        break;

      case "Tab":
        event.preventDefault();
        // TODO: Enter chat mode
        console.log("[OSlash] Chat mode not yet implemented");
        break;
    }
  };

  document.addEventListener("keydown", handleKeyDown);

  // Cleanup when overlay is removed
  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      for (const node of mutation.removedNodes) {
        if ((node as Element).id === "oslash-overlay") {
          document.removeEventListener("keydown", handleKeyDown);
          observer.disconnect();
        }
      }
    }
  });

  observer.observe(document.body, { childList: true });
}

/**
 * Render overlay content HTML
 */
function renderOverlayContent(results: SearchResult[], query: string): string {
  const sourceIcons: Record<string, string> = {
    gdrive: "📁",
    gmail: "📧",
    slack: "💬",
    hubspot: "🏢",
  };

  if (results.length === 0) {
    return `
      <div class="overlay-inner">
        <div class="empty-state">
          <div class="empty-icon">🔍</div>
          <div class="empty-text">No results found for "${escapeHtml(query)}"</div>
        </div>
        <div class="footer">
          ↑↓ Navigate • Enter Open • Tab Chat • Esc Close
        </div>
      </div>
    `;
  }

  const resultItems = results.slice(0, 5).map((result, index) => {
    const icon = sourceIcons[result.source] || "📄";
    const score = Math.round(result.score * 100);
    const date = result.modified_at
      ? new Date(result.modified_at).toLocaleDateString()
      : "";

    return `
      <button class="result-item ${index === 0 ? "selected" : ""}" data-url="${escapeHtml(result.url || "")}">
        <div class="result-icon">${icon}</div>
        <div class="result-content">
          <div class="result-title">${escapeHtml(result.title)}</div>
          <div class="result-meta">
            ${result.path ? escapeHtml(result.path) + " • " : ""}
            ${result.author ? escapeHtml(result.author) + " • " : ""}
            ${date}
          </div>
          <div class="result-snippet">${escapeHtml(result.snippet)}</div>
        </div>
        <div class="result-score">${score}%</div>
      </button>
    `;
  }).join("");

  return `
    <div class="overlay-inner">
      <div class="results-list">
        ${resultItems}
      </div>
      <div class="footer">
        ↑↓ Navigate • Enter Open • Tab Chat • Esc Close
      </div>
    </div>
  `;
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text: string): string {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Get overlay CSS styles
 */
function getOverlayStyles(): string {
  return `
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    .overlay-inner {
      background: white;
      border: 1px solid #e4e4e7;
      border-radius: 12px;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
      overflow: hidden;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }

    .results-list {
      max-height: 320px;
      overflow-y: auto;
    }

    .result-item {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      width: 100%;
      padding: 12px 16px;
      border: none;
      background: transparent;
      cursor: pointer;
      text-align: left;
      border-bottom: 1px solid #f4f4f5;
      transition: background-color 0.1s;
    }

    .result-item:last-child {
      border-bottom: none;
    }

    .result-item:hover,
    .result-item.selected {
      background: #fafafa;
    }

    .result-icon {
      font-size: 20px;
      flex-shrink: 0;
      width: 24px;
      text-align: center;
    }

    .result-content {
      flex: 1;
      min-width: 0;
    }

    .result-title {
      font-size: 14px;
      font-weight: 500;
      color: #18181b;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      text-wrap: balance;
    }

    .result-meta {
      font-size: 12px;
      color: #71717a;
      margin-top: 2px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .result-snippet {
      font-size: 13px;
      color: #52525b;
      margin-top: 4px;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
      text-wrap: pretty;
    }

    .result-score {
      font-size: 12px;
      color: #a1a1aa;
      font-variant-numeric: tabular-nums;
      flex-shrink: 0;
    }

    .empty-state {
      padding: 32px 16px;
      text-align: center;
    }

    .empty-icon {
      font-size: 32px;
      margin-bottom: 8px;
    }

    .empty-text {
      font-size: 14px;
      color: #71717a;
    }

    .footer {
      padding: 8px 16px;
      font-size: 11px;
      color: #a1a1aa;
      background: #fafafa;
      border-top: 1px solid #f4f4f5;
    }

    .loading {
      padding: 16px;
    }

    .skeleton {
      background: linear-gradient(90deg, #f4f4f5 25%, #e4e4e7 50%, #f4f4f5 75%);
      background-size: 200% 100%;
      animation: shimmer 1.5s infinite;
      border-radius: 4px;
    }

    .skeleton-title {
      height: 16px;
      width: 60%;
      margin-bottom: 8px;
    }

    .skeleton-text {
      height: 12px;
      width: 80%;
      margin-bottom: 4px;
    }

    @keyframes shimmer {
      0% { background-position: 200% 0; }
      100% { background-position: -200% 0; }
    }
  `;
}

/**
 * Show loading skeleton overlay
 */
function showLoadingOverlay(position: Position): void {
  hideOverlay();

  const overlay = document.createElement("div");
  overlay.id = "oslash-overlay";
  overlay.className = "oslash-overlay";

  const shadow = overlay.attachShadow({ mode: "open" });

  const styles = document.createElement("style");
  styles.textContent = getOverlayStyles();
  shadow.appendChild(styles);

  const content = document.createElement("div");
  content.className = "overlay-container";
  content.style.cssText = `
    position: fixed;
    top: ${position.top}px;
    left: ${position.left}px;
    width: ${position.width}px;
    max-width: 480px;
    z-index: 2147483647;
  `;

  content.innerHTML = `
    <div class="overlay-inner">
      <div class="loading">
        ${[1, 2, 3].map(() => `
          <div style="display: flex; gap: 12px; padding: 12px 0; border-bottom: 1px solid #f4f4f5;">
            <div class="skeleton" style="width: 24px; height: 24px; border-radius: 4px;"></div>
            <div style="flex: 1;">
              <div class="skeleton skeleton-title"></div>
              <div class="skeleton skeleton-text"></div>
              <div class="skeleton skeleton-text" style="width: 90%;"></div>
            </div>
          </div>
        `).join("")}
      </div>
      <div class="footer">Searching...</div>
    </div>
  `;

  shadow.appendChild(content);
  document.body.appendChild(overlay);
  overlayVisible = true;

  document.addEventListener("click", handleClickOutside);
  document.addEventListener("keydown", handleEscape);
}

/**
 * Listen for messages from background script
 */
chrome.runtime.onMessage.addListener((message, _sender, _sendResponse) => {
  if (message.type === "SEARCH_RESULTS") {
    const { results, searchTimeMs } = message;
    console.log(`[OSlash] Received ${results.length} results in ${searchTimeMs}ms`);

    if (activeInput) {
      const position = calculateOverlayPosition(activeInput);
      showOverlay(results, position, currentQuery);
    }
  }

  if (message.type === "SEARCH_ERROR") {
    console.error("[OSlash] Search error:", message.error);
    hideOverlay();
  }

  if (message.type === "SHOW_LOADING") {
    if (activeInput) {
      const position = calculateOverlayPosition(activeInput);
      showLoadingOverlay(position);
    }
  }

  if (message.type === "HIDE_OVERLAY") {
    hideOverlay();
  }
});

/**
 * Initialize content script
 */
function init(): void {
  // Attach input listeners using capture phase to catch all inputs
  document.addEventListener("input", handleInput, true);
  document.addEventListener("input", handlePrewarm, true);

  // Handle dynamically added content (for SPAs)
  const observer = new MutationObserver(() => {
    // Re-check for inputs if needed
    // Most cases are handled by event delegation above
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true,
  });

  console.log("[OSlash] Content script initialized");
}

// Initialize when DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
