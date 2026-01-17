/**
 * Shared types for OSlash Local Extension
 */

// Source types
export type Source = "gdrive" | "gmail" | "slack" | "hubspot" | "gpeople";

export const SOURCES: { id: Source; name: string; icon: string }[] = [
  { id: "gdrive", name: "Google Drive", icon: "📁" },
  { id: "gmail", name: "Gmail", icon: "📧" },
  { id: "gpeople", name: "Google People", icon: "👥" },
  { id: "slack", name: "Slack", icon: "💬" },
  { id: "hubspot", name: "HubSpot", icon: "🏢" },
];

// Message types for extension communication
export interface SearchQueryMessage {
  type: "SEARCH_QUERY";
  query: string;
  context: PageContext;
  inputRect: DOMRect;
}

export interface SearchResultsMessage {
  type: "SEARCH_RESULTS";
  results: SearchResult[];
  inputRect: DOMRect;
  searchTimeMs: number;
}

export interface SearchErrorMessage {
  type: "SEARCH_ERROR";
  error: string;
}

export interface PrewarmMessage {
  type: "PREWARM";
}

export interface ShowOverlayMessage {
  type: "SHOW_OVERLAY";
  results: SearchResult[];
  position: Position;
  query: string;
}

export interface HideOverlayMessage {
  type: "HIDE_OVERLAY";
}

export interface OpenUrlMessage {
  type: "OPEN_URL";
  url: string;
}

export type ExtensionMessage =
  | SearchQueryMessage
  | SearchResultsMessage
  | SearchErrorMessage
  | PrewarmMessage
  | ShowOverlayMessage
  | HideOverlayMessage
  | OpenUrlMessage;

// Search result from API
export interface SearchResult {
  document_id: string;
  title: string;
  path: string | null;
  source: Source;
  author: string | null;
  url: string | null;
  snippet: string;
  score: number;
  modified_at: string | null;
  chunk_id: string;
  section_title: string | null;
}

// Page context for search
export interface PageContext {
  url: string;
  title: string;
  selectedText: string;
}

// Position for overlay
export interface Position {
  top: number;
  left: number;
  width: number;
}

// Server status
export interface ServerStatus {
  online: boolean;
  version: string;
  accounts: Partial<Record<Source, AccountStatus>>;
  total_documents: number;
  total_chunks: number;
}

// Account status
export interface AccountStatus {
  connected: boolean;
  email: string | null;
  document_count: number;
  last_sync: string | null;
  status: "idle" | "syncing" | "error";
}

// Sync status
export interface SyncStatus {
  source: Source;
  status: "idle" | "syncing" | "error";
  progress: number | null;
  last_sync: string | null;
  document_count: number;
  error: string | null;
}

