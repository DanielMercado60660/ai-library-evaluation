"""ADK Session Service - DatabaseSessionService wrapper for the AI Library.

Provides persistent session management using ADK's DatabaseSessionService with:
- Patron context management
- Session state helpers for library operations
- Backward-compatible interface with existing ChatSession API
"""

import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from google.adk.sessions import DatabaseSessionService, InMemorySessionService, Session

logger = logging.getLogger(__name__)


# Database URL for session persistence (uses aiosqlite for async SQLite)
SESSION_DB_URL = os.getenv("SESSION_DB_URL", "sqlite+aiosqlite:///./db/sessions.db")

# Default session timeout in minutes
SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", "30"))

# ADK session service constants
ADK_APP_NAME = "ai-library"
ADK_DEFAULT_USER_ID = "anonymous"


@dataclass
class LibrarySession:
    """Represents a library patron session with state management.

    Wraps ADK Session with library-specific state helpers.
    """

    session_id: str
    adk_session: Session
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def state(self) -> dict[str, Any]:
        """Get the session state dictionary."""
        return self.adk_session.state

    @property
    def patron_id(self) -> Optional[str]:
        """Get the patron ID from session state."""
        return self.state.get("patron_id")

    @patron_id.setter
    def patron_id(self, value: str) -> None:
        """Set the patron ID in session state."""
        self.state["patron_id"] = value

    def bind_active_patron(
        self,
        patron_id: str | None,
        *,
        patron_name: str | None = None,
        patron_role: str | None = None,
    ) -> None:
        """Bind active patron identity metadata into session state."""
        self.state["patron_id"] = patron_id
        self.state["patron_name"] = patron_name
        self.state["patron_role"] = patron_role

    @property
    def conversation_history(self) -> list[dict]:
        """Get conversation history from state."""
        return self.state.get("conversation_history", [])

    def add_to_history(self, role: str, content: str) -> None:
        """Add a message to conversation history."""
        if "conversation_history" not in self.state:
            self.state["conversation_history"] = []
        self.state["conversation_history"].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def clear_history(self) -> None:
        """Clear conversation history."""
        self.state["conversation_history"] = []

    @property
    def patron_context(self) -> Optional[dict]:
        """Get cached patron context (checkouts, fines, etc.)."""
        return self.state.get("patron_context")

    @patron_context.setter
    def patron_context(self, value: dict) -> None:
        """Cache patron context for the session."""
        self.state["patron_context"] = value

    @property
    def last_search_results(self) -> Optional[list]:
        """Get last catalog search results."""
        return self.state.get("last_search_results")

    @last_search_results.setter
    def last_search_results(self, value: list) -> None:
        """Cache last search results."""
        self.state["last_search_results"] = value

    @property
    def last_action(self) -> Optional[dict]:
        """Get last action taken (checkout, hold, etc.)."""
        return self.state.get("last_action")

    @last_action.setter
    def last_action(self, value: dict) -> None:
        """Record last action taken."""
        self.state["last_action"] = value

    def touch(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now(timezone.utc)

    def is_expired(self, timeout_minutes: int = SESSION_TIMEOUT_MINUTES) -> bool:
        """Check if the session has expired due to inactivity."""
        return datetime.now(timezone.utc) - self.last_activity > timedelta(minutes=timeout_minutes)


class LibrarySessionService:
    """Library session service using ADK's DatabaseSessionService.

    Provides persistent session management with library-specific helpers.

    Usage:
        service = LibrarySessionService()
        session = await service.get_or_create_session("session-123", patron_id="patron-001")
        session.add_to_history("user", "Find tragedy books")
        await service.save_session(session)
    """

    def __init__(
        self,
        db_url: str = SESSION_DB_URL,
        use_in_memory: bool = False,
    ):
        """Initialize the session service.

        Args:
            db_url: Database URL for persistent storage
            use_in_memory: If True, use InMemorySessionService (for testing)
        """
        if use_in_memory:
            self._adk_service = InMemorySessionService()
            logger.info("Using in-memory session service")
        else:
            # Ensure parent directory exists for SQLite databases
            if "sqlite" in db_url:
                db_path = db_url.split("///", 1)[-1] if "///" in db_url else ""
                if db_path:
                    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            self._adk_service = DatabaseSessionService(db_url=db_url)
            logger.info(f"Using database session service: {db_url}")

        self._sessions_cache: dict[str, LibrarySession] = {}

    async def get_or_create_session(
        self,
        session_id: Optional[str] = None,
        patron_id: Optional[str] = None,
    ) -> LibrarySession:
        """Get an existing session or create a new one.

        Args:
            session_id: Optional session ID (generated if not provided)
            patron_id: Optional patron ID to associate with session

        Returns:
            LibrarySession instance
        """
        # Clean up expired sessions from cache
        self._cleanup_expired_sessions()

        # Generate session ID if not provided
        if not session_id:
            session_id = str(uuid.uuid4())

        # Check cache first
        if session_id in self._sessions_cache:
            session = self._sessions_cache[session_id]
            if not session.is_expired():
                session.touch()
                return session
            # Session expired, remove from cache
            del self._sessions_cache[session_id]

        # Use patron_id as user_id if provided, else default
        user_id = patron_id or ADK_DEFAULT_USER_ID

        # Try to get from ADK service
        adk_session = await self._adk_service.get_session(
            app_name=ADK_APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )

        if not adk_session:
            # Create new session with initial state
            initial_state = {
                "patron_id": patron_id,
                "patron_name": None,
                "patron_role": None,
                "conversation_history": [],
                "patron_context": None,
                "last_search_results": None,
                "last_action": None,
            }
            adk_session = await self._adk_service.create_session(
                app_name=ADK_APP_NAME,
                user_id=user_id,
                session_id=session_id,
                state=initial_state,
            )
            logger.info(f"Created new session: {session_id}")
        else:
            logger.info(f"Retrieved existing session: {session_id}")

        # Wrap in LibrarySession
        library_session = LibrarySession(
            session_id=session_id,
            adk_session=adk_session,
        )

        # Update patron_id if provided and different
        if patron_id and library_session.patron_id != patron_id:
            library_session.patron_id = patron_id

        # Cache the session
        self._sessions_cache[session_id] = library_session

        return library_session

    async def get_session(
        self,
        session_id: str,
        user_id: Optional[str] = None,
    ) -> Optional[LibrarySession]:
        """Get a session by ID if it exists.

        Args:
            session_id: Session ID to retrieve
            user_id: Optional user ID (defaults to ADK_DEFAULT_USER_ID)

        Returns:
            LibrarySession if found and not expired, None otherwise
        """
        # Check cache first
        if session_id in self._sessions_cache:
            session = self._sessions_cache[session_id]
            if not session.is_expired():
                return session
            del self._sessions_cache[session_id]

        # Try to get from ADK service
        adk_session = await self._adk_service.get_session(
            app_name=ADK_APP_NAME,
            user_id=user_id or ADK_DEFAULT_USER_ID,
            session_id=session_id,
        )
        if not adk_session:
            return None

        # Wrap and cache
        library_session = LibrarySession(
            session_id=session_id,
            adk_session=adk_session,
        )
        self._sessions_cache[session_id] = library_session
        return library_session

    async def save_session(self, session: LibrarySession) -> None:
        """Save session state to persistent storage.

        For InMemorySessionService, this is a no-op since state is already in memory.
        For DatabaseSessionService, this persists the state.

        Args:
            session: LibrarySession to save
        """
        session.touch()
        # InMemorySessionService doesn't have save_session (state is already in memory)
        if hasattr(self._adk_service, 'save_session'):
            await self._adk_service.save_session(session.adk_session)
        logger.debug(f"Saved session: {session.session_id}")

    async def end_session(
        self,
        session_id: str,
        user_id: Optional[str] = None,
    ) -> bool:
        """End a session explicitly.

        Args:
            session_id: Session ID to end
            user_id: Optional user ID (defaults to ADK_DEFAULT_USER_ID)

        Returns:
            True if session was ended, False if not found
        """
        # Remove from cache
        if session_id in self._sessions_cache:
            del self._sessions_cache[session_id]

        # Delete from ADK service
        try:
            await self._adk_service.delete_session(
                app_name=ADK_APP_NAME,
                user_id=user_id or ADK_DEFAULT_USER_ID,
                session_id=session_id,
            )
            logger.info(f"Ended session: {session_id}")
            return True
        except Exception as e:
            logger.warning(f"Error ending session {session_id}: {e}")
            return False

    def _cleanup_expired_sessions(self) -> None:
        """Remove expired sessions from cache."""
        expired = [
            sid for sid, session in self._sessions_cache.items()
            if session.is_expired()
        ]
        for sid in expired:
            del self._sessions_cache[sid]

        if expired:
            logger.debug(f"Cleaned up {len(expired)} expired sessions from cache")

    @property
    def cached_session_count(self) -> int:
        """Get number of sessions in cache."""
        return len(self._sessions_cache)
