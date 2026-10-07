"""In-memory A2A relay store for MVP routing."""

from collections import defaultdict

from shared.a2a.schemas import A2AMessageEnvelope


class InMemoryA2ARelay:
    """Simple per-library message relay with ack tracking and dedup."""

    def __init__(self) -> None:
        self._messages_by_library: dict[str, list[A2AMessageEnvelope]] = defaultdict(list)
        self._acked_by_library: dict[str, set[str]] = defaultdict(set)
        self._seen_ids: set[str] = set()

    def clear(self) -> None:
        """Reset relay state (used in tests)."""
        self._messages_by_library.clear()
        self._acked_by_library.clear()
        self._seen_ids.clear()

    def send(self, message: A2AMessageEnvelope) -> bool:
        """Queue a message for destination library.

        Returns True if the message was newly queued, False if it was a
        duplicate (same message ID already seen).  Duplicates are silently
        dropped — the caller receives a success acknowledgment.
        """
        if message.id in self._seen_ids:
            return False
        self._seen_ids.add(message.id)
        self._messages_by_library[message.to_library].append(message)
        return True

    def inbox(
        self,
        library_code: str,
        include_acknowledged: bool = False,
        limit: int = 50,
    ) -> list[A2AMessageEnvelope]:
        """Return library inbox, optionally excluding acknowledged messages."""
        all_messages = self._messages_by_library.get(library_code, [])
        if include_acknowledged:
            return all_messages[:limit]

        acked = self._acked_by_library.get(library_code, set())
        pending = [msg for msg in all_messages if msg.id not in acked]
        return pending[:limit]

    def acknowledge(self, library_code: str, message_id: str) -> bool:
        """Ack one message if it exists in target library inbox."""
        exists = any(
            msg.id == message_id for msg in self._messages_by_library.get(library_code, [])
        )
        if not exists:
            return False
        self._acked_by_library[library_code].add(message_id)
        return True


relay_store = InMemoryA2ARelay()
