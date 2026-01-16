import { useState, useEffect, useCallback } from "preact/hooks";
import { api } from "./lib/api";
import { cn, formatRelativeTime, formatNumber, debounce } from "./lib/utils";
import type { ServerStatus, Source, SearchResult, SearchResponse } from "./lib/types";
import { SOURCES } from "./lib/types";

// =============================================================================
// Icons
// =============================================================================

const Icons = {
  search: (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
      <path d="M7.333 12.667A5.333 5.333 0 1 0 7.333 2a5.333 5.333 0 0 0 0 10.667ZM14 14l-2.9-2.9" stroke="currentColor" strokeWidth="1.33" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  sync: (
    <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
      <path d="M1.333 2.667v4h4M14.667 13.333v-4h-4" stroke="currentColor" strokeWidth="1.33" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M13.66 6A6 6 0 0 0 3.34 3.34L1.333 6.667M2.34 10a6 6 0 0 0 10.32 2.66l2.007-3.327" stroke="currentColor" strokeWidth="1.33" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  check: (
    <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
      <path d="M13.333 4 6 11.333 2.667 8" stroke="currentColor" strokeWidth="1.33" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  disconnect: (
    <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
      <path d="M6 10l4-4M8.5 3.5L10 2l4 4-1.5 1.5M7.5 12.5L6 14l-4-4 1.5-1.5" stroke="currentColor" strokeWidth="1.33" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  external: (
    <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
      <path d="M12 8.667v4A1.333 1.333 0 0 1 10.667 14H3.333A1.333 1.333 0 0 1 2 12.667V5.333A1.333 1.333 0 0 1 3.333 4h4M10 2h4v4M6.667 9.333 14 2" stroke="currentColor" strokeWidth="1.33" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
};

// =============================================================================
// Sidebar Component
// =============================================================================

function Sidebar({ 
  isOnline, 
  version,
  connectedCount,
  totalDocs,
}: { 
  isOnline: boolean; 
  version: string;
  connectedCount: number;
  totalDocs: number;
}) {
  return (
    <aside className="w-52 h-screen border-r border-border bg-bg-secondary flex flex-col fixed left-0 top-0">
      {/* Logo */}
      <div className="px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <div className="w-5 h-5 rounded bg-white flex items-center justify-center text-black text-xxs font-semibold">
            o/
          </div>
          <span className="text-sm font-medium text-white">OSlash Local</span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-2 px-2">
        <div className="space-y-0.5">
          <a href="#" className="flex items-center gap-2 px-2 py-1.5 text-sm text-white bg-bg-hover rounded-md">
            {Icons.search}
            <span>Search</span>
          </a>
        </div>

        <div className="mt-6 px-2">
          <div className="text-xxs font-medium text-text-tertiary uppercase tracking-wider mb-2">Sources</div>
          <div className="space-y-0.5">
            {SOURCES.map((source) => (
              <div key={source.id} className="flex items-center gap-2 px-2 py-1.5 text-sm text-text-secondary rounded-md hover:bg-bg-hover cursor-default">
                <img src={source.icon} alt={source.name} className="w-4 h-4 object-contain" />
                <span>{source.name}</span>
              </div>
            ))}
          </div>
        </div>
      </nav>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-border">
        <div className="flex items-center justify-between text-xxs text-text-tertiary">
          <div className="flex items-center gap-1.5">
            <span className={cn(
              "w-1.5 h-1.5 rounded-full",
              isOnline ? "bg-green-500" : "bg-red-500"
            )} />
            <span className="text-text-secondary">{isOnline ? "Online" : "Offline"}</span>
          </div>
          <span>v{version}</span>
        </div>
        <div className="mt-2 flex items-center justify-between text-xxs text-text-tertiary">
          <span>{connectedCount} connected</span>
          <span>{formatNumber(totalDocs)} docs</span>
        </div>
      </div>
    </aside>
  );
}

// =============================================================================
// Search Bar Component
// =============================================================================

function SearchBar({
  onSearch,
  isSearching,
}: {
  onSearch: (query: string) => void;
  isSearching: boolean;
}) {
  const [query, setQuery] = useState("");

  const debouncedSearch = useCallback(
    debounce((q: string) => {
      if (q.trim().length >= 2) {
        onSearch(q);
      }
    }, 300),
    [onSearch]
  );

  const handleInput = (e: Event) => {
    const value = (e.target as HTMLInputElement).value;
    setQuery(value);
    debouncedSearch(value);
  };

  const handleSubmit = (e: Event) => {
    e.preventDefault();
    if (query.trim()) {
      onSearch(query);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="relative">
      <div className="relative">
        <div className="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary">
          {isSearching ? (
            <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 16 16" fill="none">
              <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5" strokeDasharray="28" strokeDashoffset="7" strokeLinecap="round"/>
            </svg>
          ) : (
            Icons.search
          )}
        </div>
        <input
          type="text"
          value={query}
          onInput={handleInput}
          placeholder="Search files, emails, messages..."
          className="w-full h-9 pl-8 pr-16 text-sm bg-bg-tertiary border border-border rounded-md text-white placeholder-text-tertiary focus:outline-none focus:border-text-tertiary"
        />
        <div className="absolute right-3 top-1/2 -translate-y-1/2">
          <kbd className="px-1.5 py-0.5 text-xxs text-text-tertiary bg-bg-secondary rounded border border-border font-mono">
            ⌘K
          </kbd>
        </div>
      </div>
    </form>
  );
}

// =============================================================================
// Search Results Component
// =============================================================================

function SearchResults({
  results,
  searchTime,
  query,
}: {
  results: SearchResult[];
  searchTime: number;
  query: string;
}) {
  if (results.length === 0) {
    return (
      <div className="py-12 text-center">
        <p className="text-sm text-text-tertiary">No results found for "{query}"</p>
      </div>
    );
  }

  const sourceIcon: Record<string, string> = {
    gdrive: "/icons/gdrive.png",
    gmail: "/icons/gmail.png",
    slack: "/icons/slack.svg",
    hubspot: "/icons/hubspot.svg",
  };

  return (
    <div className="space-y-1">
      <p className="text-xxs text-text-tertiary mb-3">
        {results.length} results · {searchTime}ms
      </p>
      {results.map((result, index) => (
        <a
          key={result.chunk_id}
          href={result.url || "#"}
          target="_blank"
          rel="noopener noreferrer"
          className={cn(
            "block px-3 py-2.5 rounded-md hover:bg-bg-hover group transition-colors",
            "animate-slide-up"
          )}
          style={{ animationDelay: `${index * 30}ms`, opacity: 0 }}
        >
          <div className="flex items-start gap-2.5">
            <img 
              src={sourceIcon[result.source] || "/icons/gdrive.png"} 
              alt={result.source}
              className="w-4 h-4 mt-0.5 flex-shrink-0 object-contain"
            />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-medium text-white truncate">{result.title}</h3>
                <span className="opacity-0 group-hover:opacity-100 text-text-tertiary transition-opacity">
                  {Icons.external}
                </span>
              </div>
              {result.section_title && (
                <p className="text-xs text-text-secondary truncate mt-0.5">{result.section_title}</p>
              )}
              <p className="text-xs text-text-tertiary mt-1 line-clamp-2 leading-relaxed">{result.snippet}</p>
              <div className="flex items-center gap-2 mt-1.5 text-xxs text-text-tertiary">
                <span className="capitalize">{result.source}</span>
                {result.author && (
                  <>
                    <span>·</span>
                    <span>{result.author}</span>
                  </>
                )}
                {result.modified_at && (
                  <>
                    <span>·</span>
                    <span>{formatRelativeTime(result.modified_at)}</span>
                  </>
                )}
              </div>
            </div>
            <div className="text-xxs text-text-tertiary font-mono flex-shrink-0">
              {Math.round(result.score * 100)}%
            </div>
          </div>
        </a>
      ))}
    </div>
  );
}

// =============================================================================
// Account Row Component
// =============================================================================

function AccountRow({
  source,
  account,
  onConnect,
  onSync,
  onDisconnect,
}: {
  source: { id: Source; name: string; icon: string; description: string };
  account?: {
    connected: boolean;
    email: string | null;
    document_count: number;
    last_sync: string | null;
    status: string;
  };
  onConnect: () => void;
  onSync: () => void;
  onDisconnect: () => void;
}) {
  const isConnected = account?.connected ?? false;
  const isSyncing = account?.status === "syncing";

  return (
    <div className="flex items-center justify-between py-2.5 px-3 rounded-md hover:bg-bg-hover group">
      <div className="flex items-center gap-3">
        <img src={source.icon} alt={source.name} className="w-5 h-5 object-contain" />
        <div>
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-white">{source.name}</span>
            {isConnected && (
              <span className="flex items-center gap-1 text-xxs text-green-500">
                {Icons.check}
              </span>
            )}
          </div>
          <p className="text-xxs text-text-tertiary">
            {isConnected && account?.email 
              ? account.email 
              : source.description}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        {isConnected ? (
          <>
            <span className="text-xxs text-text-tertiary mr-2">
              {formatNumber(account?.document_count ?? 0)} items
              {account?.last_sync && ` · ${formatRelativeTime(account.last_sync)}`}
            </span>
            <button
              onClick={onSync}
              disabled={isSyncing}
              className={cn(
                "p-1.5 rounded text-text-tertiary hover:text-white hover:bg-bg-tertiary transition-colors",
                "opacity-0 group-hover:opacity-100",
                isSyncing && "opacity-100"
              )}
              title="Sync"
            >
              <span className={isSyncing ? "animate-spin block" : ""}>{Icons.sync}</span>
            </button>
            <button
              onClick={onDisconnect}
              className="p-1.5 rounded text-text-tertiary hover:text-red-500 hover:bg-red-500/10 transition-colors opacity-0 group-hover:opacity-100"
              title="Disconnect"
            >
              {Icons.disconnect}
            </button>
          </>
        ) : (
          <button
            onClick={onConnect}
            className="px-2.5 py-1 text-xs font-medium text-white hover:bg-bg-tertiary rounded transition-colors"
          >
            Connect
          </button>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// Offline State Component
// =============================================================================

function OfflineState({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-bg">
      <div className="max-w-sm w-full text-center px-6">
        <div className="w-10 h-10 mx-auto mb-4 rounded-lg bg-bg-tertiary flex items-center justify-center text-text-tertiary">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M18.36 6.64a9 9 0 1 1-12.73 0M12 2v10" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
        <h1 className="text-sm font-medium text-white mb-1">Server Offline</h1>
        <p className="text-xs text-text-tertiary mb-4">
          Start the OSlash Local server to continue.
        </p>
        <code className="block px-3 py-2 text-xxs text-text-secondary bg-bg-secondary rounded-md border border-border font-mono mb-4">
          python -m oslash
        </code>
        <button
          onClick={onRetry}
          className="px-3 py-1.5 text-xs font-medium text-black bg-white hover:bg-gray-200 rounded-md transition-colors"
        >
          Retry
        </button>
      </div>
    </div>
  );
}

// =============================================================================
// Loading State Component
// =============================================================================

function LoadingState() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-bg">
      <div className="flex items-center gap-2 text-sm text-text-tertiary">
        <svg className="w-4 h-4 animate-spin" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5" strokeDasharray="28" strokeDashoffset="7" strokeLinecap="round"/>
        </svg>
        <span>Loading...</span>
      </div>
    </div>
  );
}

// =============================================================================
// Main App Component
// =============================================================================

export function App() {
  const [status, setStatus] = useState<ServerStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isOnline, setIsOnline] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  
  // Search state
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchTime, setSearchTime] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);

  // Fetch server status
  const fetchStatus = useCallback(async () => {
    try {
      const serverStatus = await api.getStatus();
      setStatus(serverStatus);
      setIsOnline(true);
    } catch {
      setIsOnline(false);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Initial fetch and polling
  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 10000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  // Handle search
  const handleSearch = useCallback(async (query: string) => {
    setSearchQuery(query);
    setIsSearching(true);
    
    try {
      const response: SearchResponse = await api.search(query);
      setSearchResults(response.results);
      setSearchTime(response.search_time_ms);
    } catch (error) {
      console.error("Search error:", error);
      setSearchResults([]);
    } finally {
      setIsSearching(false);
    }
  }, []);

  // Handle connect source
  const handleConnect = useCallback(async (sourceId: Source) => {
    try {
      const result = await api.connectSource(sourceId);
      if (result.auth_url) {
        window.open(result.auth_url, "_blank");
      }
    } catch (error) {
      console.error("Connect error:", error);
    }
  }, []);

  // Handle sync source
  const handleSyncSource = useCallback(async (sourceId: Source) => {
    try {
      await api.syncSource(sourceId, false);
      setTimeout(fetchStatus, 1000);
    } catch (error) {
      console.error("Sync error:", error);
    }
  }, [fetchStatus]);

  // Handle disconnect source
  const handleDisconnect = useCallback(async (sourceId: Source) => {
    try {
      await api.disconnectSource(sourceId);
      await fetchStatus();
    } catch (error) {
      console.error("Disconnect error:", error);
    }
  }, [fetchStatus]);

  // Handle sync all
  const handleSyncAll = useCallback(async () => {
    setIsSyncing(true);
    try {
      await api.syncAll(false);
      setTimeout(() => {
        fetchStatus();
        setIsSyncing(false);
      }, 2000);
    } catch (error) {
      console.error("Sync all error:", error);
      setIsSyncing(false);
    }
  }, [fetchStatus]);

  // Loading state
  if (isLoading) {
    return <LoadingState />;
  }

  // Offline state
  if (!isOnline) {
    return <OfflineState onRetry={fetchStatus} />;
  }

  const connectedCount = Object.values(status?.accounts ?? {}).filter(a => a.connected).length;

  return (
    <div className="min-h-screen bg-bg">
      <Sidebar 
        isOnline={isOnline} 
        version={status?.version ?? "0.1.0"}
        connectedCount={connectedCount}
        totalDocs={status?.total_documents ?? 0}
      />

      <main className="ml-52 min-h-screen">
        {/* Header */}
        <header className="sticky top-0 z-10 bg-bg border-b border-border">
          <div className="px-6 py-3 flex items-center justify-between">
            <h1 className="text-sm font-medium text-white">Search</h1>
            <a 
              href="/docs" 
              target="_blank"
              className="flex items-center gap-1.5 text-xs text-text-tertiary hover:text-text-secondary transition-colors"
            >
              API Docs
              {Icons.external}
            </a>
          </div>
        </header>

        <div className="max-w-2xl mx-auto px-6 py-6">
          {/* Search */}
          <SearchBar onSearch={handleSearch} isSearching={isSearching} />

          {/* Search Results */}
          {searchQuery ? (
            <div className="mt-6">
              <SearchResults 
                results={searchResults} 
                searchTime={searchTime} 
                query={searchQuery}
              />
            </div>
          ) : (
            <>
              {/* Connected Accounts */}
              <div className="mt-8">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-xs font-medium text-text-tertiary uppercase tracking-wider">Connected Accounts</h2>
                  <button
                    onClick={handleSyncAll}
                    disabled={isSyncing || connectedCount === 0}
                    className={cn(
                      "flex items-center gap-1.5 px-2 py-1 text-xs text-text-tertiary hover:text-white hover:bg-bg-hover rounded transition-colors",
                      (isSyncing || connectedCount === 0) && "opacity-50 cursor-not-allowed"
                    )}
                  >
                    <span className={isSyncing ? "animate-spin" : ""}>{Icons.sync}</span>
                    {isSyncing ? "Syncing..." : "Sync all"}
                  </button>
                </div>

                <div className="border border-border rounded-lg divide-y divide-border">
                  {SOURCES.map((source) => (
                    <AccountRow
                      key={source.id}
                      source={source}
                      account={status?.accounts?.[source.id]}
                      onConnect={() => handleConnect(source.id)}
                      onSync={() => handleSyncSource(source.id)}
                      onDisconnect={() => handleDisconnect(source.id)}
                    />
                  ))}
                </div>
              </div>

              {/* Stats */}
              <div className="mt-8 grid grid-cols-3 gap-4">
                <div className="px-4 py-3 bg-bg-secondary rounded-lg border border-border">
                  <div className="text-lg font-medium text-white tabular-nums">{connectedCount}</div>
                  <div className="text-xxs text-text-tertiary">Connected</div>
                </div>
                <div className="px-4 py-3 bg-bg-secondary rounded-lg border border-border">
                  <div className="text-lg font-medium text-white tabular-nums">{formatNumber(status?.total_documents ?? 0)}</div>
                  <div className="text-xxs text-text-tertiary">Documents</div>
                </div>
                <div className="px-4 py-3 bg-bg-secondary rounded-lg border border-border">
                  <div className="text-lg font-medium text-white tabular-nums">{formatNumber(status?.total_chunks ?? 0)}</div>
                  <div className="text-xxs text-text-tertiary">Chunks</div>
                </div>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;
