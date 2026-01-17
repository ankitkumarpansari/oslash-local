/**
 * Shared types for OSlash Local Web Dashboard
 */

// Source types
export type Source = "gdrive" | "gmail" | "slack" | "hubspot" | "gpeople";

export const SOURCES: { id: Source; name: string; icon: string; description: string }[] = [
  { id: "gdrive", name: "Google Drive", icon: "/icons/gdrive.png", description: "Documents, spreadsheets, and files" },
  { id: "gmail", name: "Gmail", icon: "/icons/gmail.png", description: "Emails and attachments" },
  { id: "gpeople", name: "Google People", icon: "/icons/gpeople.svg", description: "Company directory contacts" },
  { id: "slack", name: "Slack", icon: "/icons/slack.svg", description: "Messages and threads" },
  { id: "hubspot", name: "HubSpot", icon: "/icons/hubspot.svg", description: "CRM contacts and deals" },
];

// Server status
export interface ServerStatus {
  online: boolean;
  version: string;
  accounts: Record<Source, AccountStatus>;
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

// Search result from API
export interface SearchResult {
  id: string;
  title: string;
  path: string | null;
  source: Source;
  author: string | null;
  url: string | null;
  snippet: string;
  score: number;
  modified_at: string | null;
}

// Search response
export interface SearchResponse {
  query: string;
  results: SearchResult[];
  total_found: number;
  search_time_ms: number;
}

// Config response
export interface ConfigResponse {
  version: string;
  data_dir: string;
  services: {
    openai: boolean;
    google: boolean;
    slack: boolean;
    hubspot: boolean;
  };
  configured_sources: string[];
  settings: {
    embedding_model: string;
    chat_model: string;
    sync_interval_minutes: number;
    chunk_size: number;
    default_results_count: number;
  };
}

// Chat message types
export interface ChatMessage {
  type: "start" | "token" | "sources" | "end" | "error";
  content?: string;
  sources?: string[];
}

// Chat source reference
export interface ChatSource {
  id: string;
  title: string;
  source: Source;
  url: string | null;
  snippet: string;
}

