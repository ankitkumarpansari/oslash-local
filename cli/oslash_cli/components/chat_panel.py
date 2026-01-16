"""Chat panel component."""

from typing import Optional
import uuid

from textual.widgets import Static, Input, RichLog
from textual.containers import Container, VerticalScroll
from textual.reactive import reactive
from textual.message import Message
from rich.text import Text
from rich.markdown import Markdown

from oslash_cli.api import SearchResult


class ChatMessage(Static):
    """Single chat message."""

    def __init__(
        self,
        role: str,
        content: str,
        sources: Optional[list[str]] = None,
    ) -> None:
        self.role = role
        self.sources = sources or []
        super().__init__(self._render(content))

    def _render(self, content: str) -> Text:
        text = Text()

        if self.role == "user":
            text.append("You: ", style="bold cyan")
        else:
            text.append("Assistant: ", style="bold green")

        text.append(content)

        if self.sources:
            text.append("\n")
            text.append(f"Sources: {', '.join(self.sources)}", style="dim italic")

        return text

    def update_content(self, content: str) -> None:
        """Update message content (for streaming)."""
        self.update(self._render(content))


class ChatInput(Input):
    """Chat input field."""

    class Submitted(Message):
        """Emitted when user submits a question."""

        def __init__(self, question: str) -> None:
            self.question = question
            super().__init__()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key."""
        if event.value.strip():
            self.post_message(self.Submitted(event.value))
            self.value = ""


class ChatPanel(Container):
    """Chat interface with streaming support."""

    is_visible: reactive[bool] = reactive(False)
    is_streaming: reactive[bool] = reactive(False)
    context_query: reactive[str] = reactive("")
    context_results: reactive[list[SearchResult]] = reactive([])

    class BackRequested(Message):
        """Emitted when user wants to go back to search."""
        pass

    def __init__(self, id: str | None = None) -> None:
        super().__init__(id=id)
        self.session_id = str(uuid.uuid4())
        self._current_message: Optional[ChatMessage] = None

    def compose(self):
        yield Static("", id="chat-context")
        yield VerticalScroll(id="chat-messages")
        yield ChatInput(placeholder="Ask a question...", id="chat-input")

    def on_mount(self) -> None:
        """Hide by default."""
        self.display = False

    def watch_is_visible(self, visible: bool) -> None:
        """Show/hide panel."""
        self.display = visible
        if visible:
            self.query_one("#chat-input", ChatInput).focus()

    def set_context(self, query: str, results: list[SearchResult]) -> None:
        """Set the search context for chat."""
        self.context_query = query
        self.context_results = results

        # Update header
        header = self.query_one("#chat-context", Static)
        header.update(
            f"[bold]Context:[/] {len(results)} documents about [cyan]\"{query}\"[/cyan]"
        )

        # Clear previous messages
        messages = self.query_one("#chat-messages", VerticalScroll)
        messages.remove_children()

        # Reset session
        self.session_id = str(uuid.uuid4())

    def add_user_message(self, content: str) -> None:
        """Add a user message to the chat."""
        messages = self.query_one("#chat-messages", VerticalScroll)
        messages.mount(ChatMessage("user", content))
        messages.scroll_end()

    def start_assistant_message(self) -> ChatMessage:
        """Start a new assistant message for streaming."""
        messages = self.query_one("#chat-messages", VerticalScroll)
        self._current_message = ChatMessage("assistant", "")
        messages.mount(self._current_message)
        messages.scroll_end()
        self.is_streaming = True
        return self._current_message

    def append_to_assistant(self, token: str) -> None:
        """Append token to current assistant message."""
        if self._current_message:
            current_text = self._current_message.renderable
            if isinstance(current_text, Text):
                # Extract just the content part
                content = str(current_text).replace("Assistant: ", "", 1)
                content += token
                self._current_message.update_content(content)

            messages = self.query_one("#chat-messages", VerticalScroll)
            messages.scroll_end()

    def finish_assistant_message(self, sources: Optional[list[str]] = None) -> None:
        """Finish streaming and set sources."""
        if self._current_message and sources:
            self._current_message.sources = sources
            # Re-render with sources
            current_text = self._current_message.renderable
            if isinstance(current_text, Text):
                content = str(current_text).replace("Assistant: ", "", 1)
                self._current_message.update_content(content)

        self._current_message = None
        self.is_streaming = False

    def action_back(self) -> None:
        """Go back to search."""
        self.is_visible = False
        self.post_message(self.BackRequested())

    def on_key(self, event) -> None:
        """Handle Escape key."""
        if event.key == "escape":
            self.action_back()

