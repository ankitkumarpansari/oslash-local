"""Status bar component."""

from textual.widgets import Static
from textual.reactive import reactive


class StatusBar(Static):
    """Status bar showing server connection and sync status."""

    is_online: reactive[bool] = reactive(False)
    total_docs: reactive[int] = reactive(0)
    is_syncing: reactive[bool] = reactive(False)
    message: reactive[str] = reactive("")

    def render(self) -> str:
        parts = []

        # Connection status
        if self.is_online:
            parts.append("[green]● Online[/]")
        else:
            parts.append("[red]● Offline[/]")

        # Document count
        parts.append(f"[dim]{self.total_docs:,} docs[/]")

        # Sync status
        if self.is_syncing:
            parts.append("[yellow]⟳ Syncing...[/]")

        # Custom message
        if self.message:
            parts.append(f"[cyan]{self.message}[/]")

        return " │ ".join(parts)

    def set_message(self, message: str, duration: float = 3.0) -> None:
        """Show a temporary message."""
        self.message = message
        if duration > 0:
            self.set_timer(duration, lambda: self._clear_message())

    def _clear_message(self) -> None:
        self.message = ""

