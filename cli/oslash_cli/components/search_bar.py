"""Search bar component."""

from textual.widgets import Input
from textual.message import Message
from textual.timer import Timer


class SearchBar(Input):
    """Search input with debouncing."""

    DEBOUNCE_MS = 300

    class Submitted(Message):
        """Emitted when search should be performed."""

        def __init__(self, query: str) -> None:
            self.query = query
            super().__init__()

    def __init__(
        self,
        placeholder: str = "Type to search (min 2 chars)...",
        id: str | None = None,
    ) -> None:
        super().__init__(placeholder=placeholder, id=id)
        self._debounce_timer: Timer | None = None

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes with debouncing."""
        # Cancel existing timer
        if self._debounce_timer:
            self._debounce_timer.stop()
            self._debounce_timer = None

        # Only search if query is at least 2 characters
        if len(event.value) >= 2:
            self._debounce_timer = self.set_timer(
                self.DEBOUNCE_MS / 1000,
                lambda: self._emit_search(event.value),
            )

    def _emit_search(self, query: str) -> None:
        """Emit search message."""
        self.post_message(self.Submitted(query))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key - immediate search."""
        if len(event.value) >= 2:
            if self._debounce_timer:
                self._debounce_timer.stop()
            self.post_message(self.Submitted(event.value))

