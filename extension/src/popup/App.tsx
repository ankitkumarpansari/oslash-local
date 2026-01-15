import { useState, useEffect } from "preact/hooks";
import { cn } from "@/lib/utils";

interface ServerStatus {
  online: boolean;
  accounts: Record<
    string,
    {
      connected: boolean;
      email?: string;
      documentCount?: number;
      lastSync?: string;
      status?: string;
    }
  >;
  totalDocuments: number;
}

const SOURCES = [
  { id: "gdrive", name: "Google Drive", icon: "📁" },
  { id: "gmail", name: "Gmail", icon: "📧" },
  { id: "slack", name: "Slack", icon: "💬" },
  { id: "hubspot", name: "HubSpot", icon: "🏢" },
];

const SERVER_URL = "http://localhost:8000";

export function App() {
  const [status, setStatus] = useState<ServerStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStatus();
  }, []);

  async function fetchStatus() {
    try {
      const response = await fetch(`${SERVER_URL}/api/v1/status`, {
        signal: AbortSignal.timeout(3000),
      });
      if (response.ok) {
        const data = await response.json();
        setStatus({ ...data, online: true });
      } else {
        setStatus({ online: false, accounts: {}, totalDocuments: 0 });
      }
    } catch {
      setStatus({ online: false, accounts: {}, totalDocuments: 0 });
    } finally {
      setIsLoading(false);
    }
  }

  async function handleSync() {
    try {
      await fetch(`${SERVER_URL}/api/v1/sync`, { method: "POST" });
      fetchStatus();
    } catch (e) {
      setError("Failed to sync");
    }
  }

  async function handleConnect(source: string) {
    try {
      const response = await fetch(`${SERVER_URL}/api/v1/auth/${source}/url`);
      const { url } = await response.json();
      chrome.tabs.create({ url });
    } catch {
      setError(`Failed to connect ${source}`);
    }
  }

  if (isLoading) {
    return (
      <div className="w-80 bg-white p-4">
        <div className="animate-pulse space-y-3">
          <div className="h-6 w-32 rounded bg-zinc-100" />
          <div className="h-16 rounded bg-zinc-100" />
          <div className="h-16 rounded bg-zinc-100" />
        </div>
      </div>
    );
  }

  return (
    <div className="w-80 bg-white">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-100 px-4 py-3">
        <h1 className="text-sm font-semibold text-zinc-900 text-balance">
          OSlash Local
        </h1>
        <span
          className={cn(
            "flex items-center gap-1.5 text-xs",
            status?.online ? "text-green-600" : "text-red-500"
          )}
        >
          <span
            className={cn(
              "size-2 rounded-full",
              status?.online ? "bg-green-500" : "bg-red-500"
            )}
          />
          {status?.online ? "Online" : "Offline"}
        </span>
      </div>

      {/* Error message */}
      {error && (
        <div className="mx-4 mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">
          {error}
        </div>
      )}

      {/* Accounts */}
      <div className="p-4">
        <h2 className="mb-3 text-xs font-medium uppercase tracking-wide text-zinc-500">
          Connected Accounts
        </h2>
        <div className="space-y-2">
          {SOURCES.map((source) => {
            const account = status?.accounts[source.id];
            const isConnected = account?.connected;

            return (
              <div
                key={source.id}
                className="rounded-lg border border-zinc-200 p-3"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">{source.icon}</span>
                    <span className="text-sm font-medium text-zinc-900">
                      {source.name}
                    </span>
                  </div>
                  {isConnected ? (
                    <span className="text-xs text-green-600">✓ Connected</span>
                  ) : (
                    <button
                      onClick={() => handleConnect(source.id)}
                      disabled={!status?.online}
                      className={cn(
                        "rounded px-2 py-1 text-xs font-medium",
                        status?.online
                          ? "bg-zinc-900 text-white hover:bg-zinc-800"
                          : "cursor-not-allowed bg-zinc-100 text-zinc-400"
                      )}
                    >
                      Connect
                    </button>
                  )}
                </div>
                {isConnected && account && (
                  <div className="mt-2 text-xs text-zinc-500">
                    <p className="truncate">{account.email}</p>
                    <p>
                      {account.documentCount?.toLocaleString()} files •{" "}
                      {account.lastSync || "Never synced"}
                    </p>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Footer */}
      <div className="border-t border-zinc-100 px-4 py-3">
        <div className="mb-3 text-xs text-zinc-500">
          Total indexed:{" "}
          <span className="tabular-nums font-medium text-zinc-700">
            {status?.totalDocuments.toLocaleString() || 0}
          </span>{" "}
          documents
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleSync}
            disabled={!status?.online}
            className={cn(
              "flex-1 rounded-lg py-2 text-sm font-medium",
              status?.online
                ? "bg-zinc-900 text-white hover:bg-zinc-800"
                : "cursor-not-allowed bg-zinc-100 text-zinc-400"
            )}
          >
            Sync Now
          </button>
          <button
            onClick={() => {
              // TODO: Open CLI or settings page
            }}
            className="flex-1 rounded-lg border border-zinc-200 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50"
          >
            Open CLI
          </button>
        </div>
      </div>
    </div>
  );
}

