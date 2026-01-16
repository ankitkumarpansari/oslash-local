import { useState, useEffect } from "preact/hooks";
import { cn } from "../lib/utils";
import type { ServerStatus, Source, AccountStatus } from "../lib/types";

// Source configuration
const SOURCES: { id: Source; name: string; icon: string }[] = [
  { id: "gdrive", name: "Google Drive", icon: "📁" },
  { id: "gmail", name: "Gmail", icon: "📧" },
  { id: "slack", name: "Slack", icon: "💬" },
  { id: "hubspot", name: "HubSpot", icon: "🏢" },
];

/**
 * Header component showing server status
 */
function Header({ isOnline, version }: { isOnline: boolean; version: string }) {
  return (
    <header className="flex items-center justify-between border-b border-zinc-100 px-4 py-3">
      <div className="flex items-center gap-2">
        <span className="text-lg font-semibold text-zinc-900">OSlash Local</span>
        <span className="text-xs text-zinc-400">v{version}</span>
      </div>
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "size-2 rounded-full",
            isOnline ? "bg-green-500" : "bg-red-500"
          )}
        />
        <span className="text-sm text-zinc-600">
          {isOnline ? "Online" : "Offline"}
        </span>
      </div>
    </header>
  );
}

/**
 * Account card component
 */
function AccountCard({
  source,
  account,
  onConnect,
  onSync,
}: {
  source: { id: Source; name: string; icon: string };
  account?: AccountStatus;
  onConnect: () => void;
  onSync: () => void;
}) {
  const isConnected = account?.connected ?? false;
  const isSyncing = account?.status === "syncing";

  // Format last sync time
  const formatLastSync = (timestamp: string | null): string => {
    if (!timestamp) return "Never";
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins} min ago`;
    if (diffMins < 1440) return `${Math.floor(diffMins / 60)} hr ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-3">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <span className="text-2xl">{source.icon}</span>
          <div>
            <h3 className="text-sm font-medium text-zinc-900">{source.name}</h3>
            {isConnected && account?.email && (
              <p className="text-xs text-zinc-500">{account.email}</p>
            )}
          </div>
        </div>

        {isConnected ? (
          <div className="flex items-center gap-2">
            {isSyncing ? (
              <span className="text-xs text-amber-600">Syncing...</span>
            ) : (
              <span className="text-xs text-green-600">✓ Synced</span>
            )}
          </div>
        ) : (
          <button
            onClick={onConnect}
            className="rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-zinc-800"
          >
            Connect
          </button>
        )}
      </div>

      {isConnected && (
        <div className="mt-2 flex items-center justify-between text-xs text-zinc-500">
          <span className="tabular-nums">
            {account?.document_count?.toLocaleString() ?? 0} items
          </span>
          <div className="flex items-center gap-2">
            <span>Last sync: {formatLastSync(account?.last_sync ?? null)}</span>
            <button
              onClick={onSync}
              disabled={isSyncing}
              className={cn(
                "text-zinc-400 hover:text-zinc-600",
                isSyncing && "cursor-not-allowed opacity-50"
              )}
            >
              ↻
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Footer component with actions
 */
function Footer({
  totalDocs,
  totalChunks,
  onSyncAll,
  isSyncing,
}: {
  totalDocs: number;
  totalChunks: number;
  onSyncAll: () => void;
  isSyncing: boolean;
}) {
  return (
    <footer className="border-t border-zinc-100 px-4 py-3">
      <div className="mb-3 text-center text-sm text-zinc-600">
        <span className="tabular-nums font-medium">{totalDocs.toLocaleString()}</span>{" "}
        documents indexed
        <span className="mx-1 text-zinc-300">•</span>
        <span className="tabular-nums">{totalChunks.toLocaleString()}</span> chunks
      </div>

      <div className="flex gap-2">
        <button
          onClick={onSyncAll}
          disabled={isSyncing}
          className={cn(
            "flex-1 rounded-md border border-zinc-200 px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50",
            isSyncing && "cursor-not-allowed opacity-50"
          )}
        >
          {isSyncing ? "Syncing..." : "Sync All"}
        </button>
        <button
          onClick={() => {
            // Open CLI - this would typically open a terminal or link to instructions
            chrome.tabs.create({ url: "http://localhost:8000/docs" });
          }}
          className="flex-1 rounded-md border border-zinc-200 px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50"
        >
          API Docs
        </button>
      </div>
    </footer>
  );
}

/**
 * Loading skeleton
 */
function PopupSkeleton() {
  return (
    <div className="w-80 bg-white">
      <header className="flex items-center justify-between border-b border-zinc-100 px-4 py-3">
        <div className="h-6 w-32 animate-pulse rounded bg-zinc-200" />
        <div className="h-4 w-16 animate-pulse rounded bg-zinc-200" />
      </header>

      <div className="space-y-2 p-4">
        <div className="h-4 w-36 animate-pulse rounded bg-zinc-200" />
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="h-20 animate-pulse rounded-lg border border-zinc-200 bg-zinc-50"
          />
        ))}
      </div>

      <footer className="border-t border-zinc-100 px-4 py-3">
        <div className="mb-3 flex justify-center">
          <div className="h-4 w-40 animate-pulse rounded bg-zinc-200" />
        </div>
        <div className="flex gap-2">
          <div className="h-10 flex-1 animate-pulse rounded-md bg-zinc-200" />
          <div className="h-10 flex-1 animate-pulse rounded-md bg-zinc-200" />
        </div>
      </footer>
    </div>
  );
}

/**
 * Offline state
 */
function OfflineState({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="w-80 bg-white">
      <header className="flex items-center justify-between border-b border-zinc-100 px-4 py-3">
        <span className="text-lg font-semibold text-zinc-900">OSlash Local</span>
        <div className="flex items-center gap-2">
          <span className="size-2 rounded-full bg-red-500" />
          <span className="text-sm text-zinc-600">Offline</span>
        </div>
      </header>

      <div className="p-8 text-center">
        <div className="mb-4 text-4xl">🔌</div>
        <h2 className="mb-2 text-lg font-medium text-zinc-900">Server Offline</h2>
        <p className="mb-4 text-sm text-zinc-500 text-pretty">
          The OSlash Local server is not running. Start it to use the extension.
        </p>
        <div className="space-y-2">
          <code className="block rounded-md bg-zinc-100 px-3 py-2 text-xs text-zinc-700">
            cd oslash-local/server && python -m oslash
          </code>
          <button
            onClick={onRetry}
            className="w-full rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800"
          >
            Retry Connection
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * Main App component
 */
export function App() {
  const [status, setStatus] = useState<ServerStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isOnline, setIsOnline] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);

  // Fetch server status
  const fetchStatus = async () => {
    setIsLoading(true);
    try {
      const response = await chrome.runtime.sendMessage({ type: "GET_STATUS" });
      if (response.success) {
        setStatus(response.status);
        setIsOnline(true);
      } else {
        setIsOnline(false);
      }
    } catch {
      setIsOnline(false);
    } finally {
      setIsLoading(false);
    }
  };

  // Initial fetch
  useEffect(() => {
    fetchStatus();
  }, []);

  // Handle connect source
  const handleConnect = async (sourceId: Source) => {
    try {
      const response = await chrome.runtime.sendMessage({
        type: "CONNECT_SOURCE",
        source: sourceId,
      });

      if (response.success && response.authUrl) {
        // Open OAuth URL in new tab
        chrome.tabs.create({ url: response.authUrl });
      } else {
        console.error("Failed to connect:", response.error);
      }
    } catch (error) {
      console.error("Connect error:", error);
    }
  };

  // Handle sync source
  const handleSyncSource = async (sourceId: Source) => {
    try {
      await chrome.runtime.sendMessage({
        type: "SYNC_SOURCE",
        source: sourceId,
        full: false,
      });
      // Refresh status after a delay
      setTimeout(fetchStatus, 1000);
    } catch (error) {
      console.error("Sync error:", error);
    }
  };

  // Handle sync all
  const handleSyncAll = async () => {
    setIsSyncing(true);
    try {
      await chrome.runtime.sendMessage({
        type: "SYNC_ALL",
        full: false,
      });
      // Refresh status after a delay
      setTimeout(() => {
        fetchStatus();
        setIsSyncing(false);
      }, 2000);
    } catch (error) {
      console.error("Sync all error:", error);
      setIsSyncing(false);
    }
  };

  // Loading state
  if (isLoading) {
    return <PopupSkeleton />;
  }

  // Offline state
  if (!isOnline) {
    return <OfflineState onRetry={fetchStatus} />;
  }

  return (
    <div className="w-80 bg-white">
      <Header isOnline={isOnline} version={status?.version ?? "0.1.0"} />

      <div className="space-y-2 p-4">
        <h2 className="text-sm font-medium text-zinc-700">Connected Accounts</h2>

        {SOURCES.map((source) => (
          <AccountCard
            key={source.id}
            source={source}
            account={status?.accounts?.[source.id]}
            onConnect={() => handleConnect(source.id)}
            onSync={() => handleSyncSource(source.id)}
          />
        ))}
      </div>

      <Footer
        totalDocs={status?.total_documents ?? 0}
        totalChunks={status?.total_chunks ?? 0}
        onSyncAll={handleSyncAll}
        isSyncing={isSyncing}
      />
    </div>
  );
}

export default App;
