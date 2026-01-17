import { useState, useEffect, useCallback, useRef } from "preact/hooks";
import { api } from "./lib/api";
import { cn, formatNumber, debounce } from "./lib/utils";
import { parseQuery, getSourceDisplayName } from "./lib/queryParser";
import type { ServerStatus, Source, SearchResult, SearchResponse } from "./lib/types";
import { SOURCES } from "./lib/types";
import { ResultsGrid } from "./components/ResultCards";

// =============================================================================
// Icons
// =============================================================================

const Icons = {
  search: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M7.333 12.667A5.333 5.333 0 1 0 7.333 2a5.333 5.333 0 0 0 0 10.667ZM14 14l-2.9-2.9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  send: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M14.667 1.333 7.333 8.667M14.667 1.333l-4.667 13.334-2.667-6L1.333 6l13.334-4.667Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  sync: (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
      <path d="M1.333 2.667v4h4M14.667 13.333v-4h-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M13.66 6A6 6 0 0 0 3.34 3.34L1.333 6.667M2.34 10a6 6 0 0 0 10.32 2.66l2.007-3.327" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  check: (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
      <path d="M13.333 4 6 11.333 2.667 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  external: (
    <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
      <path d="M12 8.667v4A1.333 1.333 0 0 1 10.667 14H3.333A1.333 1.333 0 0 1 2 12.667V5.333A1.333 1.333 0 0 1 3.333 4h4M10 2h4v4M6.667 9.333 14 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  sparkles: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M8 1v2.5M8 12.5V15M3.5 8H1M15 8h-2.5M4.4 4.4l1.77 1.77M9.83 9.83l1.77 1.77M4.4 11.6l1.77-1.77M9.83 6.17l1.77-1.77" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),
  sun: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="3" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M8 1.333V3M8 13v1.667M1.333 8H3M13 8h1.667M3.286 3.286l1.178 1.178M11.536 11.536l1.178 1.178M3.286 12.714l1.178-1.178M11.536 4.464l1.178-1.178" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),
  moon: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M14 8.667A6 6 0 1 1 7.333 2 4.667 4.667 0 0 0 14 8.667Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  settings: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M13.6 10a1.2 1.2 0 0 0 .24 1.32l.04.04a1.46 1.46 0 1 1-2.06 2.06l-.04-.04a1.2 1.2 0 0 0-1.32-.24 1.2 1.2 0 0 0-.73 1.1v.12a1.45 1.45 0 1 1-2.9 0v-.06a1.2 1.2 0 0 0-.79-1.1 1.2 1.2 0 0 0-1.32.24l-.04.04a1.46 1.46 0 1 1-2.06-2.06l.04-.04a1.2 1.2 0 0 0 .24-1.32 1.2 1.2 0 0 0-1.1-.73h-.12a1.45 1.45 0 1 1 0-2.9h.06a1.2 1.2 0 0 0 1.1-.79 1.2 1.2 0 0 0-.24-1.32l-.04-.04a1.46 1.46 0 1 1 2.06-2.06l.04.04a1.2 1.2 0 0 0 1.32.24h.06a1.2 1.2 0 0 0 .73-1.1v-.12a1.45 1.45 0 1 1 2.9 0v.06a1.2 1.2 0 0 0 .73 1.1 1.2 1.2 0 0 0 1.32-.24l.04-.04a1.46 1.46 0 1 1 2.06 2.06l-.04.04a1.2 1.2 0 0 0-.24 1.32v.06a1.2 1.2 0 0 0 1.1.73h.12a1.45 1.45 0 1 1 0 2.9h-.06a1.2 1.2 0 0 0-1.1.73Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  close: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M12 4L4 12M4 4l8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),
  chevronDown: (
    <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
      <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
};

// Source icons mapping
const sourceIcons: Record<string, string> = {
  gmail: "/icons/gmail.png",
  gdrive: "/icons/gdrive.png",
  gpeople: "/icons/gpeople.svg",
  hubspot: "/icons/hubspot.svg",
  slack: "/icons/slack.svg",
};

// =============================================================================
// Main App Component
// =============================================================================

export function App() {
  // Server state
  const [status, setStatus] = useState<ServerStatus | null>(null);
  const [isOnline, setIsOnline] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  
  // Theme
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('oslash-theme');
      if (saved === 'light' || saved === 'dark') return saved;
      if (window.matchMedia('(prefers-color-scheme: light)').matches) return 'light';
    }
    return 'dark';
  });
  
  // Search state
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchTime, setSearchTime] = useState(0);
  const [isSearching, setIsSearching] = useState(false);
  const [activeSource, setActiveSource] = useState<string | null>(null);
  
  // AI Chat state
  const [aiInput, setAiInput] = useState("");
  const [aiResponse, setAiResponse] = useState("");
  const [isAiStreaming, setIsAiStreaming] = useState(false);
  const [sessionId] = useState(() => crypto.randomUUID());
  const streamingContentRef = useRef("");
  
  // Settings panel
  const [showSettings, setShowSettings] = useState(false);
  
  // Input refs
  const searchInputRef = useRef<HTMLInputElement>(null);
  const aiInputRef = useRef<HTMLInputElement>(null);

  // =============================================================================
  // Effects
  // =============================================================================

  // Fetch server status
  const fetchStatus = useCallback(async () => {
    try {
      const serverStatus = await api.getStatus();
      setStatus(serverStatus);
      setIsOnline(true);
    } catch {
      setIsOnline(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 10000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  // Apply theme
  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'light') {
      root.classList.add('light');
    } else {
      root.classList.remove('light');
    }
    localStorage.setItem('oslash-theme', theme);
  }, [theme]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        searchInputRef.current?.focus();
      }
      if (e.key === 'Escape') {
        setShowSettings(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);


  // Connect to AI WebSocket
  useEffect(() => {
    api.connectChat(sessionId, {
      onStart: () => {
        setIsAiStreaming(true);
        setAiResponse("");
        streamingContentRef.current = "";
      },
      onToken: (token) => {
        streamingContentRef.current += token;
        setAiResponse(streamingContentRef.current);
      },
      onEnd: () => {
        setIsAiStreaming(false);
      },
      onError: (error) => {
        setAiResponse(`Error: ${error}`);
        setIsAiStreaming(false);
      },
    });

    return () => api.disconnectChat();
  }, [sessionId]);

  // =============================================================================
  // Handlers
  // =============================================================================

  const toggleTheme = useCallback(() => {
    setTheme(prev => prev === 'dark' ? 'light' : 'dark');
  }, []);

  // Search handler
  const handleSearch = useCallback(async (query: string, sources?: string[]) => {
    if (!query.trim()) {
      setSearchResults([]);
      return;
    }
    
    setIsSearching(true);
    try {
      const response: SearchResponse = await api.search(query, { sources });
      setSearchResults(response.results);
      setSearchTime(response.search_time_ms);
    } catch (error) {
      console.error("Search error:", error);
      setSearchResults([]);
    } finally {
      setIsSearching(false);
    }
  }, []);

  // Handle URL query parameter for search (e.g., ?q=search-term)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const queryParam = params.get('q');
    if (queryParam) {
      setSearchQuery(queryParam);
      // Trigger search after a short delay to ensure everything is loaded
      setTimeout(() => {
        handleSearch(queryParam);
      }, 100);
      // Clear the URL parameter without reload
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, [handleSearch]);

  // Debounced search
  const debouncedSearch = useCallback(
    debounce((q: string) => {
      const parsed = parseQuery(q);
      if (parsed.query.length >= 2) {
        const sources = parsed.source ? [parsed.source] : undefined;
        setActiveSource(parsed.source);
        handleSearch(parsed.query, sources);
      } else {
        setSearchResults([]);
        setActiveSource(null);
      }
    }, 300),
    [handleSearch]
  );

  const handleSearchInput = (e: Event) => {
    const value = (e.target as HTMLInputElement).value;
    setSearchQuery(value);
    debouncedSearch(value);
  };

  // AI Chat handler
  const handleAiSubmit = (e: Event) => {
    e.preventDefault();
    if (!aiInput.trim() || isAiStreaming) return;
    
    api.sendChatMessage(aiInput);
    setAiInput("");
  };

  // Connect source
  const handleConnect = useCallback(async (sourceId: Source) => {
    try {
      const result = await api.connectSource(sourceId);
      if (result.auth_url) {
        window.open(result.auth_url, '_blank', 'width=600,height=700');
      }
    } catch (error) {
      console.error("Connect error:", error);
    }
  }, []);

  // Sync source
  const handleSyncSource = useCallback(async (sourceId: Source) => {
    setIsSyncing(true);
    try {
      await api.syncSource(sourceId);
      await fetchStatus();
    } catch (error) {
      console.error("Sync error:", error);
    } finally {
      setIsSyncing(false);
    }
  }, [fetchStatus]);

  // Disconnect source
  const handleDisconnect = useCallback(async (sourceId: Source) => {
    try {
      await api.disconnectSource(sourceId);
      await fetchStatus();
    } catch (error) {
      console.error("Disconnect error:", error);
    }
  }, [fetchStatus]);

  // Sync all
  const handleSyncAll = useCallback(async () => {
    setIsSyncing(true);
    try {
      await api.syncAll();
      await fetchStatus();
    } catch (error) {
      console.error("Sync all error:", error);
    } finally {
      setIsSyncing(false);
    }
  }, [fetchStatus]);

  // =============================================================================
  // Render
  // =============================================================================

  const connectedCount = Object.values(status?.accounts ?? {}).filter(a => a.connected).length;

  return (
    <div className="min-h-screen bg-bg flex flex-col">
      {/* Header */}
      <header className="flex-shrink-0 border-b border-border bg-bg-secondary/50 backdrop-blur-sm">
        <div className="max-w-5xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-lg bg-accent flex items-center justify-center text-white text-xs font-bold">
              o/
            </div>
            <span className="text-sm font-medium text-fg">OSlash</span>
            <span className={cn(
              "px-1.5 py-0.5 text-xxs rounded-full",
              isOnline 
                ? "bg-green-500/10 text-green-500" 
                : "bg-red-500/10 text-red-500"
            )}>
              {isOnline ? "Online" : "Offline"}
            </span>
          </div>
          
          <div className="flex items-center gap-2">
            <button
              onClick={toggleTheme}
              className="p-2 rounded-md hover:bg-bg-hover text-fg-secondary hover:text-fg transition-colors"
              title={theme === 'dark' ? 'Light mode' : 'Dark mode'}
            >
              {theme === 'dark' ? Icons.sun : Icons.moon}
            </button>
            <button
              onClick={() => setShowSettings(!showSettings)}
              className={cn(
                "p-2 rounded-md hover:bg-bg-hover text-fg-secondary hover:text-fg transition-colors",
                showSettings && "bg-bg-hover text-fg"
              )}
              title="Settings"
            >
              {Icons.settings}
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex flex-col max-w-5xl mx-auto w-full px-6 py-6">
        {/* Search Bar */}
        <div className="relative mb-6">
          <div className="absolute left-4 top-1/2 -translate-y-1/2 text-fg-tertiary">
            {isSearching ? (
              <svg className="w-4 h-4 animate-spin" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5" strokeDasharray="28" strokeDashoffset="7" strokeLinecap="round"/>
              </svg>
            ) : (
              Icons.search
            )}
          </div>
          <input
            ref={searchInputRef}
            type="text"
            value={searchQuery}
            onInput={handleSearchInput}
            placeholder="Search your files... (⌘K)"
            className="w-full h-12 pl-12 pr-4 text-base bg-bg-secondary border border-border rounded-xl text-fg placeholder-text-tertiary focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/20 transition-all"
          />
          {activeSource && (
            <div className="absolute right-4 top-1/2 -translate-y-1/2 flex items-center gap-1.5 px-2 py-1 bg-accent/10 text-accent rounded-md text-xs">
              <img src={sourceIcons[activeSource]} alt="" className="w-3.5 h-3.5" />
              {getSourceDisplayName(activeSource)}
            </div>
          )}
        </div>

        {/* Results Cards or Empty State */}
        <div className="flex-1 overflow-auto">
          {searchQuery && searchResults.length > 0 ? (
            <ResultsGrid results={searchResults} searchTime={searchTime} />
          ) : searchQuery ? (
            <div className="flex-1 flex items-center justify-center py-16">
              <p className="text-fg-tertiary">No results found for "{searchQuery}"</p>
            </div>
          ) : (
            /* Empty State - Show Connected Sources */
            <div className="space-y-6">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {SOURCES.map((source) => {
                  const account = status?.accounts?.[source.id];
                  const isConnected = account?.connected;
                  
                  return (
                    <div
                      key={source.id}
                      className={cn(
                        "p-4 rounded-xl border transition-all",
                        isConnected 
                          ? "bg-bg-secondary border-border hover:border-accent/50" 
                          : "bg-bg-tertiary/50 border-border/50"
                      )}
                    >
                      <div className="flex items-center gap-3 mb-3">
                        <img src={source.icon} alt="" className="w-8 h-8" />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="text-sm font-medium text-fg">{source.name}</span>
                            {isConnected && (
                              <span className="text-green-500">{Icons.check}</span>
                            )}
                          </div>
                        </div>
                      </div>
                      
                      {isConnected ? (
                        <div className="space-y-2">
                          <p className="text-xs text-fg-tertiary truncate">{account?.email}</p>
                          <div className="flex items-center justify-between">
                            <span className="text-xs text-fg-secondary">
                              {formatNumber(account?.document_count ?? 0)} items
                            </span>
                            <button
                              onClick={() => handleSyncSource(source.id)}
                              className="p-1 rounded hover:bg-bg-hover text-fg-tertiary hover:text-fg transition-colors"
                              title="Sync"
                            >
                              <span className={isSyncing ? "animate-spin block" : ""}>{Icons.sync}</span>
                            </button>
                          </div>
                        </div>
                      ) : (
                        <button
                          onClick={() => handleConnect(source.id)}
                          className="w-full py-1.5 text-xs font-medium text-accent hover:bg-accent/10 rounded-md transition-colors"
                        >
                          Connect
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
              
              {/* Quick Stats */}
              <div className="flex items-center justify-center gap-8 py-4 text-sm text-fg-secondary">
                <span>{connectedCount} sources connected</span>
                <span>·</span>
                <span>{formatNumber(status?.total_documents ?? 0)} documents</span>
                <span>·</span>
                <span>{formatNumber(status?.total_chunks ?? 0)} chunks indexed</span>
              </div>
            </div>
          )}
        </div>

        {/* AI Chat Section - Fixed at Bottom */}
        <div className="flex-shrink-0 mt-6 pt-6 border-t border-border">
          {/* AI Response */}
          {aiResponse && (
            <div className="mb-4 p-4 bg-bg-secondary border border-border rounded-xl">
              <div className="flex items-start gap-3">
                <div className="w-6 h-6 rounded-full bg-accent/20 flex items-center justify-center text-accent flex-shrink-0">
                  {Icons.sparkles}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-fg whitespace-pre-wrap leading-relaxed">{aiResponse}</p>
                  {isAiStreaming && (
                    <span className="inline-block w-1.5 h-4 bg-accent animate-pulse ml-0.5" />
                  )}
                </div>
              </div>
            </div>
          )}
          
          {/* AI Input */}
          <form onSubmit={handleAiSubmit} className="relative">
            <div className="absolute left-4 top-1/2 -translate-y-1/2 text-accent">
              {Icons.sparkles}
            </div>
            <input
              ref={aiInputRef}
              type="text"
              value={aiInput}
              onInput={(e) => setAiInput((e.target as HTMLInputElement).value)}
              placeholder="Ask AI about your files..."
              disabled={isAiStreaming}
              className="w-full h-12 pl-12 pr-14 text-base bg-bg-secondary border border-accent/30 rounded-xl text-fg placeholder-text-tertiary focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/20 disabled:opacity-50 transition-all"
            />
            <button
              type="submit"
              disabled={!aiInput.trim() || isAiStreaming}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-lg bg-accent text-white hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {Icons.send}
            </button>
          </form>
        </div>
      </main>

      {/* Settings Panel */}
      {showSettings && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={() => setShowSettings(false)}>
          <div 
            className="w-full max-w-md bg-bg border border-border rounded-2xl shadow-2xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-border">
              <h2 className="text-lg font-medium text-fg">Settings</h2>
              <button
                onClick={() => setShowSettings(false)}
                className="p-1 rounded hover:bg-bg-hover text-fg-tertiary hover:text-fg transition-colors"
              >
                {Icons.close}
              </button>
            </div>
            
            <div className="p-6 space-y-6">
              {/* Connected Accounts */}
              <div>
                <h3 className="text-sm font-medium text-fg mb-3">Connected Accounts</h3>
                <div className="space-y-2">
                  {SOURCES.map((source) => {
                    const account = status?.accounts?.[source.id];
                    const isConnected = account?.connected;
                    
                    return (
                      <div key={source.id} className="flex items-center justify-between py-2">
                        <div className="flex items-center gap-3">
                          <img src={source.icon} alt="" className="w-5 h-5" />
                          <div>
                            <span className="text-sm text-fg">{source.name}</span>
                            {isConnected && account?.email && (
                              <p className="text-xs text-fg-tertiary">{account.email}</p>
                            )}
                          </div>
                        </div>
                        {isConnected ? (
                          <button
                            onClick={() => handleDisconnect(source.id)}
                            className="text-xs text-red-500 hover:text-red-400 transition-colors"
                          >
                            Disconnect
                          </button>
                        ) : (
                          <button
                            onClick={() => handleConnect(source.id)}
                            className="text-xs text-accent hover:text-accent-hover transition-colors"
                          >
                            Connect
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
              
              {/* Sync */}
              <div>
                <h3 className="text-sm font-medium text-fg mb-3">Data Sync</h3>
                <button
                  onClick={handleSyncAll}
                  disabled={isSyncing || connectedCount === 0}
                  className="w-full py-2 text-sm font-medium bg-accent text-white rounded-lg hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {isSyncing ? "Syncing..." : "Sync All Sources"}
                </button>
              </div>
              
              {/* Stats */}
              <div className="pt-4 border-t border-border">
                <div className="grid grid-cols-3 gap-4 text-center">
                  <div>
                    <div className="text-xl font-medium text-fg">{connectedCount}</div>
                    <div className="text-xs text-fg-tertiary">Sources</div>
                  </div>
                  <div>
                    <div className="text-xl font-medium text-fg">{formatNumber(status?.total_documents ?? 0)}</div>
                    <div className="text-xs text-fg-tertiary">Documents</div>
                  </div>
                  <div>
                    <div className="text-xl font-medium text-fg">{formatNumber(status?.total_chunks ?? 0)}</div>
                    <div className="text-xs text-fg-tertiary">Chunks</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
