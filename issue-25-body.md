## Description
Add CLI commands for managing connected accounts and triggering syncs.

## Commands
```bash
oslash accounts list          # List connected accounts
oslash accounts connect gdrive # Start OAuth flow
oslash accounts disconnect gmail # Remove account
oslash sync                   # Trigger manual sync
oslash sync --source=slack    # Sync specific source
oslash status                 # Show index stats
```

## Implementation
```python
# __main__.py
import click
from rich.console import Console
from rich.table import Table
import httpx
import webbrowser

console = Console()

@click.group()
def main():
    """OSlash Local CLI"""
    pass

@main.command()
def tui():
    """Launch interactive TUI"""
    from .app import OSlashApp
    app = OSlashApp()
    app.run()

@main.group()
def accounts():
    """Manage connected accounts"""
    pass

@accounts.command("list")
def accounts_list():
    """List all connected accounts"""
    with httpx.Client() as client:
        response = client.get("http://localhost:8000/api/v1/status")
        data = response.json()
    
    table = Table(title="Connected Accounts")
    table.add_column("Source", style="cyan")
    table.add_column("Email", style="green")
    table.add_column("Status")
    table.add_column("Documents", justify="right")
    table.add_column("Last Sync")
    
    for source, info in data["accounts"].items():
        if info["connected"]:
            table.add_row(
                source,
                info["email"],
                "✓ Connected" if info["status"] == "idle" else info["status"],
                str(info["document_count"]),
                info["last_sync"]
            )
        else:
            table.add_row(source, "-", "Not connected", "-", "-")
    
    console.print(table)

@accounts.command("connect")
@click.argument("source", type=click.Choice(["gdrive", "gmail", "slack", "hubspot"]))
def accounts_connect(source: str):
    """Connect a new account"""
    with httpx.Client() as client:
        response = client.get(f"http://localhost:8000/api/v1/auth/{source}/url")
        auth_url = response.json()["url"]
    
    console.print(f"Opening browser to connect {source}...")
    webbrowser.open(auth_url)
    console.print("[green]Complete the authorization in your browser.[/]")

@accounts.command("disconnect")
@click.argument("source", type=click.Choice(["gdrive", "gmail", "slack", "hubspot"]))
@click.confirmation_option(prompt="Are you sure you want to disconnect?")
def accounts_disconnect(source: str):
    """Disconnect an account"""
    with httpx.Client() as client:
        response = client.delete(f"http://localhost:8000/api/v1/auth/{source}")
        if response.status_code == 200:
            console.print(f"[green]Disconnected {source}[/]")
        else:
            console.print(f"[red]Failed to disconnect: {response.text}[/]")

@main.command()
@click.option("--source", "-s", help="Sync specific source only")
def sync(source: str = None):
    """Trigger manual sync"""
    endpoint = f"/api/v1/sync/{source}" if source else "/api/v1/sync"
    
    with console.status("Syncing..."):
        with httpx.Client(timeout=300) as client:
            response = client.post(f"http://localhost:8000{endpoint}")
            result = response.json()
    
    if result["success"]:
        console.print("[green]Sync completed![/]")
        console.print(f"  Added: {result['added']}")
        console.print(f"  Updated: {result['updated']}")
        console.print(f"  Deleted: {result['deleted']}")
    else:
        console.print(f"[red]Sync failed: {result['error']}[/]")

@main.command()
def status():
    """Show index statistics"""
    with httpx.Client() as client:
        response = client.get("http://localhost:8000/api/v1/status")
        data = response.json()
    
    console.print("\n[bold]OSlash Local Status[/]\n")
    console.print(f"Server: {'[green]Online[/]' if data['online'] else '[red]Offline[/]'}")
    console.print(f"Total Documents: {data['total_documents']:,}")
    console.print(f"Total Chunks: {data['total_chunks']:,}")
    console.print(f"Vector DB Size: {data['db_size_mb']:.1f} MB")

@main.command()
@click.argument("query")
def search(query: str):
    """Quick search from command line"""
    with httpx.Client() as client:
        response = client.post(
            "http://localhost:8000/api/v1/search",
            json={"query": query, "limit": 5}
        )
        results = response.json()["results"]
    
    if not results:
        console.print("[yellow]No results found[/]")
        return
    
    for i, r in enumerate(results, 1):
        icon = {"gdrive": "📄", "gmail": "📧", "slack": "💬", "hubspot": "🏢"}.get(r['source'], "📎")
        console.print(f"\n[bold]{i}. {icon} {r['title']}[/]")
        console.print(f"   [dim]{r['path']} • {r['author']}[/]")
        console.print(f"   {r['snippet'][:100]}...")

if __name__ == "__main__":
    main()
```

## Estimate
3 hours

