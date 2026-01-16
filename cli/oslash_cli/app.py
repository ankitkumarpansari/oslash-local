"""OSlash CLI - Main Textual Application."""

from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static
from textual.containers import Container, Vertical
from textual.binding import Binding

from oslash_cli.api import ApiClient, SearchResult
from oslash_cli.components import (
    SearchBar,
    ResultsList,
    ChatPanel,
    StatusBar,
)


class OSlashApp(App):
    """OSlash Local CLI Client."""

    TITLE = "OSlash Local"
    SUB_TITLE = "Search your files"
    CSS_PATH = Path(__file__).parent / "styles" / "app.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("s", "sync", "Sync"),
        Binding("c", "chat", "Chat", show=True),
        Binding("escape", "back", "Back", show=False),
        Binding("/", "focus_search", "Search", show=True),
    ]

    def __init__(self):
        super().__init__()
        self.api = ApiClient()
        self.current_query = ""
        self.current_results: list[SearchResult] = []

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="main"):
            # Search section
            with Vertical(id="search-section"):
                yield SearchBar(id="search-bar")

            # Results section
            with Vertical(id="results-section"):
                yield Static("Results will appear here", id="results-header")
                yield ResultsList(id="results-list")

            # Chat panel (hidden by default)
            yield ChatPanel(id="chat-panel")

        yield StatusBar(id="status-bar")
        yield Footer()

    async def on_mount(self) -> None:
        """Initialize on mount."""
        self.sub_title = "Press / to search"

        # Check server status
        await self._check_server()

        # Focus search bar
        self.query_one("#search-bar", SearchBar).focus()

    async def _check_server(self) -> None:
        """Check server connection and update status."""
        status_bar = self.query_one("#status-bar", StatusBar)

        async with self.api:
            is_online = await self.api.health_check()
            status_bar.is_online = is_online

            if is_online:
                try:
                    status = await self.api.get_status()
                    status_bar.total_docs = status.total_documents
                except Exception:
                    pass

    async def on_search_bar_submitted(self, event: SearchBar.Submitted) -> None:
        """Handle search submission."""
        query = event.query
        self.current_query = query

        # Update header
        header = self.query_one("#results-header", Static)
        header.update(f"[dim]Searching for:[/] [cyan]{query}[/]...")

        # Perform search
        async with self.api:
            try:
                response = await self.api.search(query, limit=10)
                self.current_results = response.results

                # Update results list
                results_list = self.query_one("#results-list", ResultsList)
                results_list.query = query
                results_list.results = response.results

                # Update header
                header.update(
                    f"[bold]{response.total_found}[/] results for "
                    f"[cyan]\"{query}\"[/] "
                    f"[dim]({response.search_time_ms:.0f}ms)[/]"
                )

                # Update status
                status_bar = self.query_one("#status-bar", StatusBar)
                status_bar.set_message(f"Found {response.total_found} results")

            except Exception as e:
                header.update(f"[red]Error:[/] {str(e)}")

    async def on_results_list_chat_requested(
        self, event: ResultsList.ChatRequested
    ) -> None:
        """Handle chat request from results list."""
        await self._enter_chat_mode(event.query, event.results)

    async def on_chat_panel_back_requested(
        self, event: ChatPanel.BackRequested
    ) -> None:
        """Handle back from chat."""
        self._exit_chat_mode()

    async def on_chat_input_submitted(self, event) -> None:
        """Handle chat question submission."""
        chat_panel = self.query_one("#chat-panel", ChatPanel)
        question = event.question

        # Add user message
        chat_panel.add_user_message(question)

        # Start assistant message
        chat_panel.start_assistant_message()

        # Stream response
        full_response = ""
        sources = []

        async with self.api:
            try:
                async for chunk in self.api.chat_stream(
                    question,
                    session_id=chat_panel.session_id,
                ):
                    if chunk.get("type") == "token":
                        token = chunk.get("content", "")
                        full_response += token
                        chat_panel.append_to_assistant(token)
                    elif chunk.get("type") == "sources":
                        sources = chunk.get("sources", [])

                chat_panel.finish_assistant_message(sources)

            except Exception as e:
                chat_panel.finish_assistant_message()
                chat_panel.add_user_message(f"Error: {str(e)}")

    async def _enter_chat_mode(
        self, query: str, results: list[SearchResult]
    ) -> None:
        """Enter chat mode with context."""
        # Hide search/results
        self.query_one("#search-section").display = False
        self.query_one("#results-section").display = False

        # Show chat panel
        chat_panel = self.query_one("#chat-panel", ChatPanel)
        chat_panel.set_context(query, results)
        chat_panel.is_visible = True

        self.sub_title = "Chat mode - Press Escape to go back"

    def _exit_chat_mode(self) -> None:
        """Exit chat mode."""
        # Hide chat panel
        chat_panel = self.query_one("#chat-panel", ChatPanel)
        chat_panel.is_visible = False

        # Show search/results
        self.query_one("#search-section").display = True
        self.query_one("#results-section").display = True

        # Focus search
        self.query_one("#search-bar", SearchBar).focus()
        self.sub_title = "Press / to search"

    def action_focus_search(self) -> None:
        """Focus the search bar."""
        self.query_one("#search-bar", SearchBar).focus()

    def action_chat(self) -> None:
        """Enter chat mode."""
        if self.current_results:
            self.run_worker(
                self._enter_chat_mode(self.current_query, self.current_results)
            )

    def action_back(self) -> None:
        """Go back from chat."""
        chat_panel = self.query_one("#chat-panel", ChatPanel)
        if chat_panel.is_visible:
            self._exit_chat_mode()

    async def action_sync(self) -> None:
        """Trigger sync."""
        status_bar = self.query_one("#status-bar", StatusBar)
        status_bar.is_syncing = True
        status_bar.set_message("Starting sync...")

        async with self.api:
            try:
                await self.api.sync()
                status_bar.set_message("Sync started")
            except Exception as e:
                status_bar.set_message(f"Sync failed: {e}")
            finally:
                status_bar.is_syncing = False


def run_app():
    """Run the OSlash CLI app."""
    app = OSlashApp()
    app.run()


if __name__ == "__main__":
    run_app()
