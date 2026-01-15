"""OSlash Local CLI entry point."""

import click
from rich.console import Console

console = Console()


@click.group()
@click.version_option()
def main():
    """OSlash Local - Search your files with AI."""
    pass


@main.command()
def tui():
    """Launch interactive TUI."""
    from .app import OSlashApp

    app = OSlashApp()
    app.run()


@main.command()
@click.argument("query")
def search(query: str):
    """Quick search from command line."""
    import httpx

    try:
        with httpx.Client(timeout=10) as client:
            response = client.post(
                "http://localhost:8000/api/v1/search",
                json={"query": query, "limit": 5},
            )
            if response.status_code != 200:
                console.print("[red]Server error. Is the server running?[/]")
                return

            data = response.json()
            results = data.get("results", [])

            if not results:
                console.print("[yellow]No results found[/]")
                return

            for i, r in enumerate(results, 1):
                icon = {
                    "gdrive": "📄",
                    "gmail": "📧",
                    "slack": "💬",
                    "hubspot": "🏢",
                }.get(r.get("source", ""), "📎")
                console.print(f"\n[bold]{i}. {icon} {r.get('title', 'Untitled')}[/]")
                console.print(f"   [dim]{r.get('path', '')} • {r.get('author', '')}[/]")
                snippet = r.get("snippet", "")[:100]
                if snippet:
                    console.print(f"   {snippet}...")

    except httpx.ConnectError:
        console.print("[red]Cannot connect to server. Is it running?[/]")
        console.print("[dim]Start with: cd server && uvicorn oslash.main:app[/]")


@main.group()
def accounts():
    """Manage connected accounts."""
    pass


@accounts.command("list")
def accounts_list():
    """List all connected accounts."""
    import httpx

    try:
        with httpx.Client(timeout=5) as client:
            response = client.get("http://localhost:8000/api/v1/status")
            data = response.json()

        from rich.table import Table

        table = Table(title="Connected Accounts")
        table.add_column("Source", style="cyan")
        table.add_column("Email", style="green")
        table.add_column("Status")
        table.add_column("Documents", justify="right")

        accounts_data = data.get("accounts", {})
        for source in ["gdrive", "gmail", "slack", "hubspot"]:
            info = accounts_data.get(source, {})
            if info.get("connected"):
                table.add_row(
                    source,
                    info.get("email", "-"),
                    "✓ Connected",
                    str(info.get("documentCount", 0)),
                )
            else:
                table.add_row(source, "-", "Not connected", "-")

        console.print(table)

    except httpx.ConnectError:
        console.print("[red]Cannot connect to server[/]")


@accounts.command("connect")
@click.argument("source", type=click.Choice(["gdrive", "gmail", "slack", "hubspot"]))
def accounts_connect(source: str):
    """Connect a new account."""
    import httpx
    import webbrowser

    try:
        with httpx.Client(timeout=5) as client:
            response = client.get(f"http://localhost:8000/api/v1/auth/{source}/url")
            auth_url = response.json().get("url")

        console.print(f"Opening browser to connect {source}...")
        webbrowser.open(auth_url)
        console.print("[green]Complete the authorization in your browser.[/]")

    except httpx.ConnectError:
        console.print("[red]Cannot connect to server[/]")


@main.command()
@click.option("--source", "-s", help="Sync specific source only")
def sync(source: str | None = None):
    """Trigger manual sync."""
    import httpx

    endpoint = f"/api/v1/sync/{source}" if source else "/api/v1/sync"

    try:
        with console.status("Syncing..."):
            with httpx.Client(timeout=300) as client:
                response = client.post(f"http://localhost:8000{endpoint}")
                result = response.json()

        if result.get("success"):
            console.print("[green]Sync completed![/]")
            console.print(f"  Added: {result.get('added', 0)}")
            console.print(f"  Updated: {result.get('updated', 0)}")
            console.print(f"  Deleted: {result.get('deleted', 0)}")
        else:
            console.print(f"[red]Sync failed: {result.get('error', 'Unknown error')}[/]")

    except httpx.ConnectError:
        console.print("[red]Cannot connect to server[/]")


@main.command()
def status():
    """Show index statistics."""
    import httpx

    try:
        with httpx.Client(timeout=5) as client:
            response = client.get("http://localhost:8000/api/v1/status")
            data = response.json()

        console.print("\n[bold]OSlash Local Status[/]\n")
        online = data.get("online", False)
        console.print(f"Server: {'[green]Online[/]' if online else '[red]Offline[/]'}")
        console.print(f"Total Documents: {data.get('totalDocuments', 0):,}")
        console.print(f"Total Chunks: {data.get('totalChunks', 0):,}")

    except httpx.ConnectError:
        console.print("[red]Server is offline[/]")
        console.print("[dim]Start with: cd server && uvicorn oslash.main:app[/]")


if __name__ == "__main__":
    main()

