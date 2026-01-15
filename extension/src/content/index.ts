/**
 * OSlash Local - Content Script
 * Detects o/ pattern in text inputs and triggers search
 */

const TRIGGER_PATTERN = /o\/\s+(.{2,})/;
const DEBOUNCE_MS = 300;

interface PageContext {
  url: string;
  title: string;
  selectedText: string;
}

function debounce<T extends (...args: unknown[]) => void>(
  fn: T,
  ms: number
): (...args: Parameters<T>) => void {
  let timeoutId: ReturnType<typeof setTimeout>;
  return (...args: Parameters<T>) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => fn(...args), ms);
  };
}

function getInputValue(element: HTMLElement): string {
  if (
    element instanceof HTMLInputElement ||
    element instanceof HTMLTextAreaElement
  ) {
    return element.value;
  }
  if (element.isContentEditable) {
    return element.innerText;
  }
  return "";
}

function getPageContext(): PageContext {
  return {
    url: window.location.href,
    title: document.title,
    selectedText: window.getSelection()?.toString() || "",
  };
}

const handleInput = debounce((event: Event) => {
  const target = event.target as HTMLElement;
  const text = getInputValue(target);
  const match = text.match(TRIGGER_PATTERN);

  if (match && match[1].length >= 2) {
    const query = match[1].trim();
    const rect = target.getBoundingClientRect();

    // Send to background script
    chrome.runtime.sendMessage({
      type: "SEARCH_QUERY",
      query,
      context: getPageContext(),
      inputRect: {
        top: rect.bottom + window.scrollY,
        left: rect.left + window.scrollX,
        width: rect.width,
      },
    });
  }
}, DEBOUNCE_MS);

// Pre-warm on "o/" detection
const handlePrewarm = debounce((event: Event) => {
  const target = event.target as HTMLElement;
  const text = getInputValue(target);

  if (text.endsWith("o/") || text.match(/o\/\s?$/)) {
    chrome.runtime.sendMessage({ type: "PREWARM" });
  }
}, 100);

// Attach listeners
document.addEventListener("input", handleInput, true);
document.addEventListener("input", handlePrewarm, true);

// Listen for results from background script
chrome.runtime.onMessage.addListener((message) => {
  if (message.type === "SEARCH_RESULTS") {
    console.log("OSlash: Received results", message.results);
    // TODO: Show overlay with results
  }

  if (message.type === "SEARCH_ERROR") {
    console.error("OSlash: Search error", message.error);
  }
});

console.log("OSlash Local: Content script loaded");

