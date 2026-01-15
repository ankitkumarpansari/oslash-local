"""OSlash Local - Textual TUI Application."""

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Input
from textual.containers import Container, Vertical


class OSlashApp(App):
    """OSlash Local TUI Client."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #main {
        height: 1fr;
    }

    #search-container {
        dock: top;
        height: 5;
        padding: 1 2;
    }

    #search-input {
        width: 100%;
    }

    #results {
        height: 1fr;
        margin: 0 2;
        border: solid $primary;
        padding: 1;
    }

    #status {
        dock: bottom;
        height: 3;
        padding: 0 2;
        background: $surface;
    }

    .result-item {
        height: auto;
        padding: 1;
        margin-bottom: 1;
    }

    .result-item:hover {
        background: $surface;
    }

    .dim {
        color: $text-muted;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("s", "sync", "Sync"),
        ("/", "focus_search", "Search"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Container(
                Input(placeholder="Search your files...", id="search-input"),
                id="search-container",
            ),
            Vertical(
                Static("Type to search across your connected accounts.", classes="dim"),
                id="results",
            ),
            Static("Press / to search • s to sync • q to quit", id="status"),
            id="main",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.title = "OSlash Local"
        self.sub_title = "RAG-powered file search"

    def action_focus_search(self) -> None:
        self.query_one("#search-input", Input).focus()

    def action_sync(self) -> None:
        self.notify("Syncing... (not implemented yet)")

    async def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input" and len(event.value) >= 2:
            # TODO: Implement search
            results_container = self.query_one("#results", Vertical)
            results_container.remove_children()
            results_container.mount(
                Static(f"Searching for: {event.value}...", classes="dim")
            )

