"""OSlash CLI - Entry Point."""

import asyncio
import sys

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from oslash_cli.api import ApiClient

console = Console()

# Source icons
SOURCE_ICONS = {
    "gdrive": "📁",
    "gmail": "📧",
    "slack": "💬",
    "hubspot": "🏢",
}


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx):
    """OSlash Local - Search your files from the terminal.

    Run without arguments to launch the interactive TUI.
    """
    if ctx.invoked_subcommand is None:
        # Launch TUI by default
        from oslash_cli.app import run_app
        run_app()


@main.command()
def tui():
    """Launch interactive TUI."""
    from oslash_cli.app import run_app
    run_app()


@main.command()
@click.argument("query")
@click.option("-n", "--limit", default=5, help="Number of results to show")
@click.option("-s", "--source", multiple=True, help="Filter by source (gdrive, gmail, slack, hubspot)")
def search(query: str, limit: int, source: tuple):
    """Search for documents.

    Example: oslash search "quarterly report"
    """
    async def _search():
        async with ApiClient() as api:
            # Check server
            if not await api.health_check():
                console.print("[red]Error:[/] Server is offline. Start it with:")
                console.print("  cd server && python -m oslash")
                sys.exit(1)

            # Perform search
            sources = list(source) if source else None
            response = await api.search(query, sources=sources, limit=limit)

            if not response.results:
                console.print(f"[yellow]No results found for:[/] {query}")
                return

            # Display results
            console.print(
                f"\n[bold]{response.total_found}[/] results for "
                f"[cyan]\"{query}\"[/] "
                f"[dim]({response.search_time_ms:.0f}ms)[/]\n"
            )

            for i, result in enumerate(response.results, 1):
                icon = SOURCE_ICONS.get(result.source, "📄")
                score = int(result.score * 100)

                # Title
                title = Text()
                title.append(f"[{i}] ", style="dim")
                title.append(f"{icon} ", style="")
                title.append(result.title, style="bold")
                title.append(f"  {score}%", style="cyan")
                console.print(title)

                # Meta
                meta_parts = []
                if result.path:
                    meta_parts.append(result.path)
                if result.author:
                    meta_parts.append(result.author)
                if meta_parts:
                    console.print(f"    [dim]{' • '.join(meta_parts)}[/]")

                # Snippet
                if result.snippet:
                    snippet = result.snippet[:120]
                    if len(result.snippet) > 120:
                        snippet += "..."
                    console.print(f"    {snippet}")

                console.print()

    asyncio.run(_search())


@main.command()
@click.argument("question", required=False)
@click.option("-s", "--session", help="Session ID for conversation continuity")
def chat(question: str, session: str):
    """Chat with your documents.

    Example: oslash chat "What was our Q4 revenue?"

    Without a question, enters interactive chat mode.
    """
    if question:
        # Single question mode
        async def _chat():
            async with ApiClient() as api:
                if not await api.health_check():
                    console.print("[red]Error:[/] Server is offline")
                    sys.exit(1)

                console.print(f"[cyan]You:[/] {question}\n")

                # Stream response
                full_response = ""
                sources = []

                console.print("[green]Assistant:[/] ", end="")
                async for chunk in api.chat_stream(question, session_id=session):
                    if chunk.get("type") == "token":
                        token = chunk.get("content", "")
                        full_response += token
                        console.print(token, end="")
                    elif chunk.get("type") == "sources":
                        sources = chunk.get("sources", [])

                console.print("\n")
                if sources:
                    console.print(f"[dim]Sources: {', '.join(sources)}[/]")

        asyncio.run(_chat())
    else:
        # Interactive mode - launch TUI in chat mode
        from oslash_cli.app import run_app
        run_app()


@main.command()
def status():
    """Show server and sync status."""
    async def _status():
        async with ApiClient() as api:
            # Health check
            is_online = await api.health_check()

            if not is_online:
                console.print(Panel(
                    "[red]● Server Offline[/]\n\n"
                    "Start the server with:\n"
                    "  cd server && python -m oslash",
                    title="OSlash Local",
                ))
                return

            # Get status
            status = await api.get_status()

            # Create table
            table = Table(title="Connected Accounts")
            table.add_column("Source", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Email")
            table.add_column("Documents", justify="right")
            table.add_column("Last Sync")

            for source_id, acc in status.accounts.items():
                icon = SOURCE_ICONS.get(source_id, "📄")
                name = f"{icon} {source_id.title()}"

                if acc.connected:
                    status_text = "[green]✓ Connected[/]"
                else:
                    status_text = "[dim]Not connected[/]"

                email = acc.email or "-"
                docs = str(acc.document_count) if acc.connected else "-"
                last_sync = acc.last_sync[:10] if acc.last_sync else "-"

                table.add_row(name, status_text, email, docs, last_sync)

            console.print()
            console.print(f"[green]● Server Online[/] v{status.version}")
            console.print(f"Total: [bold]{status.total_documents:,}[/] documents, "
                         f"[bold]{status.total_chunks:,}[/] chunks\n")
            console.print(table)

    asyncio.run(_status())


@main.command()
@click.option("-s", "--source", help="Sync specific source only")
@click.option("-f", "--full", is_flag=True, help="Full sync (not incremental)")
def sync(source: str, full: bool):
    """Trigger sync for connected sources.

    Example: oslash sync --source gdrive
    """
    async def _sync():
        async with ApiClient() as api:
            if not await api.health_check():
                console.print("[red]Error:[/] Server is offline")
                sys.exit(1)

            if source:
                console.print(f"[yellow]⟳[/] Syncing {source}...")
            else:
                console.print("[yellow]⟳[/] Syncing all sources...")

            try:
                result = await api.sync(source=source, full=full)
                console.print("[green]✓[/] Sync started")

                # Show sync status
                sync_status = await api.get_sync_status()
                for src, status in sync_status.get("sources", {}).items():
                    icon = SOURCE_ICONS.get(src, "📄")
                    if status.get("is_syncing"):
                        console.print(f"  {icon} {src}: [yellow]syncing...[/]")
                    else:
                        console.print(f"  {icon} {src}: [green]idle[/]")

            except Exception as e:
                console.print(f"[red]Error:[/] {e}")

    asyncio.run(_sync())


if __name__ == "__main__":
    main()
