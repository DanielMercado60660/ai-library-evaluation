"""Chat session management for the AI Library.

This module provides session management that integrates with ADK's
DatabaseSessionService for persistent sessions while maintaining
backward compatibility with the existing API.
"""

import logging
import os
import uuid
from typing import Optional
from datetime import datetime, timedelta, timezone

from agents.front_desk import FrontDeskAgent
from agents.session.adk_session_service import LibrarySessionService, LibrarySession
from agents.session.active_patron_context import bind_active_patron_context

logger = logging.getLogger(__name__)

USE_PERSISTENT_SESSIONS = os.getenv("USE_PERSISTENT_SESSIONS", "false").lower() in ("true", "1", "yes")


class ChatSession:
    """Represents an active chat session with a patron.

    This class wraps the ADK LibrarySession to provide backward compatibility
    with existing code while using ADK's session management features.
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        library_session: Optional[LibrarySession] = None,
    ):
        """Initialize a chat session.

        Args:
            session_id: Optional session ID (generated if not provided)
            library_session: Optional pre-existing LibrarySession
        """
        self.session_id = session_id or str(uuid.uuid4())
        self.agent = FrontDeskAgent()
        self.created_at = datetime.now(timezone.utc)
        self.last_activity = datetime.now(timezone.utc)

        # Link to ADK session if provided
        self._library_session = library_session

    @property
    def library_session(self) -> Optional[LibrarySession]:
        """Get the underlying ADK LibrarySession if available."""
        return self._library_session

    @library_session.setter
    def library_session(self, value: LibrarySession) -> None:
        """Set the underlying ADK LibrarySession."""
        self._library_session = value

    @property
    def bound_patron_id(self) -> str | None:
        """Return the patron id currently bound to this chat session."""
        if self._library_session:
            return self._library_session.patron_id
        return None

    @property
    def bound_patron_name(self) -> str | None:
        """Return patron display name bound to this session when available."""
        if not self._library_session:
            return None
        return self._library_session.state.get("patron_name")

    @property
    def bound_patron_role(self) -> str | None:
        """Return patron role bound to this session when available."""
        if not self._library_session:
            return None
        return self._library_session.state.get("patron_role")

    def bind_active_patron(
        self,
        patron_id: str | None,
        *,
        patron_name: str | None = None,
        patron_role: str | None = None,
    ) -> None:
        """Bind active patron identity to session state for downstream tools."""
        if not self._library_session:
            return

        if patron_id:
            self._library_session.patron_id = patron_id
            self._library_session.state["patron_name"] = patron_name
            self._library_session.state["patron_role"] = patron_role
        else:
            self._library_session.state["patron_name"] = patron_name
            self._library_session.state["patron_role"] = patron_role

    async def send_message(self, message: str) -> str:
        """Send a message and get a response.

        Args:
            message: The patron's message

        Returns:
            The agent's response
        """
        self.last_activity = datetime.now(timezone.utc)

        # Record to ADK session if available
        if self._library_session:
            self._library_session.add_to_history("user", message)
            self._library_session.touch()

        with bind_active_patron_context(
            self.bound_patron_id,
            name=self.bound_patron_name,
            role=self.bound_patron_role,
        ):
            if hasattr(self.agent, "chat_with_context"):
                response = await self.agent.chat_with_context(
                    message,
                    session_id=self.session_id,
                    user_id=self.bound_patron_id,
                )
            else:
                response = await self.agent.chat(message)

        # Record response to ADK session if available
        if self._library_session:
            self._library_session.add_to_history("assistant", response)

        return response

    def is_expired(self, timeout_minutes: int = 30) -> bool:
        """Check if the session has expired due to inactivity.

        Args:
            timeout_minutes: Timeout in minutes (default 30)

        Returns:
            True if session has expired
        """
        # Check ADK session if available
        if self._library_session:
            return self._library_session.is_expired(timeout_minutes)
        return datetime.now(timezone.utc) - self.last_activity > timedelta(minutes=timeout_minutes)


class ChatSessionManager:
    """Manages active chat sessions with optional ADK persistence.

    This class provides the same interface as before but now uses
    ADK's LibrarySessionService for persistent session storage.
    """

    def __init__(self, use_persistent_sessions: bool = True):
        """Initialize the session manager.

        Args:
            use_persistent_sessions: If True, use DatabaseSessionService for persistence
        """
        self._sessions: dict[str, ChatSession] = {}
        self._use_persistent = use_persistent_sessions

        if use_persistent_sessions:
            self._session_service = LibrarySessionService(use_in_memory=False)
        else:
            self._session_service = LibrarySessionService(use_in_memory=True)

        logger.info(
            f"ChatSessionManager initialized with "
            f"{'persistent' if use_persistent_sessions else 'in-memory'} sessions"
        )

    async def get_or_create_session_async(
        self,
        session_id: Optional[str] = None,
        patron_id: Optional[str] = None,
    ) -> ChatSession:
        """Get an existing session or create a new one (async version).

        Args:
            session_id: Optional session ID
            patron_id: Optional patron ID to associate with session

        Returns:
            ChatSession instance
        """
        # Clean up expired sessions periodically
        self._cleanup_expired_sessions()

        # Check local cache first
        if session_id and session_id in self._sessions:
            session = self._sessions[session_id]
            if not session.is_expired():
                if patron_id:
                    session.bind_active_patron(patron_id)
                return session
            # Session expired, remove it
            del self._sessions[session_id]

        # Get or create from ADK session service
        library_session = await self._session_service.get_or_create_session(
            session_id=session_id,
            patron_id=patron_id,
        )

        # Create ChatSession wrapper
        session = ChatSession(
            session_id=library_session.session_id,
            library_session=library_session,
        )
        session.bind_active_patron(patron_id)
        self._sessions[session.session_id] = session

        return session

    async def resolve_session_for_request(
        self,
        *,
        session_id: str | None,
        patron_id: str | None,
        patron_name: str | None = None,
        patron_role: str | None = None,
    ) -> tuple[ChatSession, bool]:
        """Resolve the effective session for an incoming chat request.

        If an existing session is bound to a different patron, this rotates to a
        fresh backend session and returns `session_rebound=True`.
        """
        rebound = False
        session: ChatSession | None = None

        if session_id:
            session = await self.get_session_async(session_id)
            if session and patron_id and session.bound_patron_id and session.bound_patron_id != patron_id:
                # Save any pending state before rotating to a new session
                await self.save_session(session)
                await self.end_session_async(session_id)
                session = None
                rebound = True

        if session is None:
            session = await self.get_or_create_session_async(
                session_id=session_id if not rebound else None,
                patron_id=patron_id,
            )

        if patron_id:
            session.bind_active_patron(
                patron_id,
                patron_name=patron_name,
                patron_role=patron_role,
            )
            await self.save_session(session)

        return session, rebound

    def get_or_create_session(
        self,
        session_id: Optional[str] = None,
    ) -> ChatSession:
        """Get an existing session or create a new one (sync version for backward compatibility).

        Note: This method creates sessions without ADK persistence.
        For full ADK integration, use get_or_create_session_async().

        Args:
            session_id: Optional session ID

        Returns:
            ChatSession instance
        """
        # Clean up expired sessions periodically
        self._cleanup_expired_sessions()

        if session_id and session_id in self._sessions:
            session = self._sessions[session_id]
            if not session.is_expired():
                return session
            # Session expired, remove it
            del self._sessions[session_id]

        # Create new session without ADK persistence (sync fallback)
        session = ChatSession(session_id)
        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get a session by ID if it exists and is not expired.

        Args:
            session_id: The session ID to look up

        Returns:
            ChatSession if found and not expired, None otherwise
        """
        session = self._sessions.get(session_id)
        if session and not session.is_expired():
            return session
        return None

    async def get_session_async(self, session_id: str) -> Optional[ChatSession]:
        """Get a session by ID (async version with ADK lookup).

        Args:
            session_id: The session ID to look up

        Returns:
            ChatSession if found and not expired, None otherwise
        """
        # Check local cache first
        session = self._sessions.get(session_id)
        if session and not session.is_expired():
            return session

        # Try to get from ADK session service
        library_session = await self._session_service.get_session(session_id)
        if library_session and not library_session.is_expired():
            session = ChatSession(
                session_id=library_session.session_id,
                library_session=library_session,
            )
            self._sessions[session_id] = session
            return session

        return None

    def end_session(self, session_id: str) -> bool:
        """End a session explicitly (sync version).

        Args:
            session_id: The session ID to end

        Returns:
            True if session was ended, False if not found
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    async def end_session_async(self, session_id: str) -> bool:
        """End a session explicitly (async version with ADK cleanup).

        Args:
            session_id: The session ID to end

        Returns:
            True if session was ended, False if not found
        """
        # Remove from local cache
        if session_id in self._sessions:
            del self._sessions[session_id]

        # Remove from ADK session service
        return await self._session_service.end_session(session_id)

    async def save_session(self, session: ChatSession) -> None:
        """Save session state to persistent storage.

        Args:
            session: The ChatSession to save
        """
        if session.library_session:
            await self._session_service.save_session(session.library_session)

    def _cleanup_expired_sessions(self) -> None:
        """Remove expired sessions from local cache."""
        expired = [
            sid for sid, session in self._sessions.items()
            if session.is_expired()
        ]
        for sid in expired:
            del self._sessions[sid]

        if expired:
            logger.debug(f"Cleaned up {len(expired)} expired sessions")

    @property
    def active_session_count(self) -> int:
        """Get the number of active sessions in cache."""
        return len(self._sessions)


# Global session manager instance.
# Set USE_PERSISTENT_SESSIONS=true to persist sessions across restarts (SQLite).
session_manager = ChatSessionManager(use_persistent_sessions=USE_PERSISTENT_SESSIONS)
