"""Results list component."""

from typing import Optional
import webbrowser

from textual.widgets import Static, ListItem, ListView
from textual.reactive import reactive
from textual.message import Message
from rich.text import Text

from oslash_cli.api import SearchResult


# Source icons
SOURCE_ICONS = {
    "gdrive": "📁",
    "gmail": "📧",
    "slack": "💬",
    "hubspot": "🏢",
}


class ResultItem(ListItem):
    """Single search result item."""

    def __init__(self, result: SearchResult, index: int) -> None:
        super().__init__()
        self.result = result
        self.index = index

    def compose(self):
        icon = SOURCE_ICONS.get(self.result.source, "📄")
        score = int(self.result.score * 100)

        # Title line
        title_text = Text()
        title_text.append(f"[{self.index}] ", style="dim")
        title_text.append(f"{icon} ", style="")
        title_text.append(self.result.title, style="bold")
        title_text.append(f"  {score}%", style="dim cyan")

        yield Static(title_text, classes="result-title")

        # Meta line
        meta_parts = []
        if self.result.path:
            meta_parts.append(self.result.path)
        if self.result.author:
            meta_parts.append(self.result.author)
        if self.result.modified_at:
            # Format date
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(self.result.modified_at.replace("Z", "+00:00"))
                meta_parts.append(dt.strftime("%b %d, %Y"))
            except:
                pass

        if meta_parts:
            yield Static(
                "    " + " • ".join(meta_parts),
                classes="result-meta",
            )

        # Snippet
        if self.result.snippet:
            snippet = self.result.snippet[:150]
            if len(self.result.snippet) > 150:
                snippet += "..."
            yield Static(f"    {snippet}", classes="result-snippet")


class ResultsList(ListView):
    """List of search results with keyboard navigation."""

    results: reactive[list[SearchResult]] = reactive([], always_update=True)
    query: reactive[str] = reactive("")

    class ResultSelected(Message):
        """Emitted when a result is selected."""

        def __init__(self, result: SearchResult) -> None:
            self.result = result
            super().__init__()

    class ChatRequested(Message):
        """Emitted when user wants to chat about results."""

        def __init__(self, query: str, results: list[SearchResult]) -> None:
            self.query = query
            self.results = results
            super().__init__()

    def watch_results(self, results: list[SearchResult]) -> None:
        """Update list when results change."""
        self.clear()
        for i, result in enumerate(results, 1):
            self.append(ResultItem(result, i))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle result selection - open URL."""
        if isinstance(event.item, ResultItem):
            result = event.item.result
            if result.url:
                webbrowser.open(result.url)
            self.post_message(self.ResultSelected(result))

    def action_chat(self) -> None:
        """Enter chat mode with current results."""
        if self.results:
            self.post_message(self.ChatRequested(self.query, list(self.results)))

