"""Q&A Chat Engine with RAG-based answering."""

import uuid
from datetime import datetime
from typing import AsyncGenerator, Optional

import structlog
from openai import AsyncOpenAI

from oslash.config import get_settings
from oslash.services.search import get_search_service
from oslash.vector import SearchResult as VectorSearchResult

logger = structlog.get_logger(__name__)

# System prompt for the chat engine
SYSTEM_PROMPT = """You are a helpful assistant that answers questions based on the user's files and documents.

INSTRUCTIONS:
1. Use ONLY the provided context to answer questions
2. If the context doesn't contain relevant information, say "I couldn't find information about that in your documents"
3. Always cite your sources by mentioning the file name in brackets, e.g., [Q3-Report.docx]
4. Be concise but thorough
5. If asked about something not in the context, acknowledge it and suggest what the user might search for

CONTEXT FORMAT:
Each document chunk is prefixed with its source file name."""


class Message:
    """A chat message."""

    def __init__(
        self,
        role: str,
        content: str,
        sources: Optional[list[str]] = None,
        timestamp: Optional[datetime] = None,
    ):
        self.role = role
        self.content = content
        self.sources = sources or []
        self.timestamp = timestamp or datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "sources": self.sources,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        return cls(
            role=data["role"],
            content=data["content"],
            sources=data.get("sources", []),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if data.get("timestamp")
            else None,
        )


class ChatSession:
    """A chat session with history and context."""

    def __init__(
        self,
        session_id: Optional[str] = None,
        search_query: Optional[str] = None,
    ):
        self.id = session_id or str(uuid.uuid4())
        self.search_query = search_query
        self.messages: list[Message] = []
        self.context_chunks: list[VectorSearchResult] = []
        self.created_at = datetime.utcnow()

    def add_message(self, role: str, content: str, sources: Optional[list[str]] = None):
        """Add a message to the session."""
        self.messages.append(Message(role=role, content=content, sources=sources))

    def get_history(self, max_messages: int = 10) -> list[Message]:
        """Get recent message history."""
        return self.messages[-max_messages:]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "search_query": self.search_query,
            "messages": [m.to_dict() for m in self.messages],
            "created_at": self.created_at.isoformat(),
        }


class ChatEngine:
    """RAG-based Q&A chat engine using OpenAI."""

    def __init__(self):
        """Initialize the chat engine."""
        self.settings = get_settings()

        if not self.settings.openai_api_key:
            logger.warning("OpenAI API key not configured")
            self.client = None
        else:
            self.client = AsyncOpenAI(api_key=self.settings.openai_api_key)

        self.model = self.settings.chat_model
        self.max_tokens = self.settings.max_tokens
        self.temperature = self.settings.chat_temperature

        # In-memory session storage (will use DB in production)
        self.sessions: dict[str, ChatSession] = {}

        logger.info(
            "ChatEngine initialized",
            model=self.model,
            has_api_key=bool(self.client),
        )

    def _format_context(self, chunks: list[VectorSearchResult]) -> str:
        """Format context chunks for the prompt."""
        if not chunks:
            return "No relevant documents found."

        context_parts = []
        for chunk in chunks:
            title = chunk.metadata.get("title", "Unknown")
            source = chunk.metadata.get("source", "unknown")
            context_parts.append(f"[{title}] ({source}):\n{chunk.content}")

        return "\n\n---\n\n".join(context_parts)

    def _format_history(self, messages: list[Message], max_tokens: int = 2000) -> list[dict]:
        """Format message history for OpenAI API."""
        formatted = []
        total_chars = 0
        max_chars = max_tokens * 4  # Rough estimate

        # Process messages in reverse to keep most recent
        for msg in reversed(messages):
            msg_chars = len(msg.content)
            if total_chars + msg_chars > max_chars:
                break
            formatted.insert(0, {"role": msg.role, "content": msg.content})
            total_chars += msg_chars

        return formatted

    def _extract_citations(
        self, answer: str, chunks: list[VectorSearchResult]
    ) -> list[str]:
        """Extract file citations from the answer."""
        citations = []
        for chunk in chunks:
            title = chunk.metadata.get("title", "")
            if title and title.lower() in answer.lower():
                if title not in citations:
                    citations.append(title)

        # Also look for bracket citations [filename]
        import re

        bracket_citations = re.findall(r"\[([^\]]+)\]", answer)
        for cite in bracket_citations:
            if cite not in citations and not cite.startswith("http"):
                citations.append(cite)

        return citations

    async def answer(
        self,
        question: str,
        context_chunks: list[VectorSearchResult],
        chat_history: Optional[list[Message]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream an answer based on context and history.

        Args:
            question: The user's question
            context_chunks: Retrieved document chunks for context
            chat_history: Previous messages in the conversation

        Yields:
            Tokens of the response as they're generated
        """
        if not self.client:
            yield "Error: OpenAI API key not configured. Please add OPENAI_API_KEY to your .env file."
            return

        # Build the messages
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Add context
        context_text = self._format_context(context_chunks)
        messages.append({
            "role": "user",
            "content": f"Here are the relevant documents:\n\n{context_text}",
        })
        messages.append({
            "role": "assistant",
            "content": "I've reviewed the documents. What would you like to know?",
        })

        # Add conversation history
        if chat_history:
            formatted_history = self._format_history(chat_history)
            messages.extend(formatted_history)

        # Add current question
        messages.append({"role": "user", "content": question})

        logger.debug(
            "Sending chat request",
            model=self.model,
            num_messages=len(messages),
            context_chunks=len(context_chunks),
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                stream=True,
            )

            async for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error("Chat completion failed", error=str(e))
            yield f"Error generating response: {str(e)}"

    async def answer_with_search(
        self,
        question: str,
        session_id: Optional[str] = None,
        sources: Optional[list[str]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Answer a question by first searching for relevant context.

        This is the main entry point for the chat API.

        Args:
            question: The user's question
            session_id: Optional session ID for conversation continuity
            sources: Optional source filter

        Yields:
            Tokens of the response
        """
        # Get or create session
        if session_id and session_id in self.sessions:
            session = self.sessions[session_id]
        else:
            session = ChatSession(session_id=session_id, search_query=question)
            self.sessions[session.id] = session

        # Search for relevant context
        search_service = get_search_service()
        search_response = await search_service.search(
            query=question,
            sources=sources,
            limit=5,  # Top 5 most relevant chunks
        )

        # Get the underlying vector results for context
        # Re-search to get full chunk content
        from oslash.services.embeddings import get_embedding_service
        from oslash.vector import get_vector_store

        embedding_service = get_embedding_service()
        vector_store = get_vector_store()

        query_embedding = await embedding_service.embed_text(question)
        context_chunks = vector_store.search(
            query_embedding=query_embedding,
            n_results=5,
            where={"source": {"$in": sources}} if sources else None,
        )

        session.context_chunks = context_chunks

        # Add user message to history
        session.add_message("user", question)

        # Stream the answer
        full_answer = ""
        async for token in self.answer(
            question=question,
            context_chunks=context_chunks,
            chat_history=session.get_history()[:-1],  # Exclude current question
        ):
            full_answer += token
            yield token

        # Extract citations and add assistant message
        citations = self._extract_citations(full_answer, context_chunks)
        session.add_message("assistant", full_answer, sources=citations)

        logger.info(
            "Chat answer completed",
            session_id=session.id,
            question_length=len(question),
            answer_length=len(full_answer),
            citations=len(citations),
        )

    async def get_answer_sync(
        self,
        question: str,
        context_chunks: list[VectorSearchResult],
        chat_history: Optional[list[Message]] = None,
    ) -> tuple[str, list[str]]:
        """
        Get a complete answer (non-streaming).

        Returns:
            Tuple of (answer, citations)
        """
        full_answer = ""
        async for token in self.answer(question, context_chunks, chat_history):
            full_answer += token

        citations = self._extract_citations(full_answer, context_chunks)
        return full_answer, citations

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get a chat session by ID."""
        return self.sessions.get(session_id)

    def create_session(self, search_query: Optional[str] = None) -> ChatSession:
        """Create a new chat session."""
        session = ChatSession(search_query=search_query)
        self.sessions[session.id] = session
        return session

    def delete_session(self, session_id: str) -> bool:
        """Delete a chat session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False


# Global instance
_chat_engine: Optional[ChatEngine] = None


def get_chat_engine() -> ChatEngine:
    """Get or create the global chat engine instance."""
    global _chat_engine
    if _chat_engine is None:
        _chat_engine = ChatEngine()
    return _chat_engine

