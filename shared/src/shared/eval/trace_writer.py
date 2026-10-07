"""JSONL trace writer for benchmark runs."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, UTC
from pathlib import Path
from typing import Any
from uuid import uuid4

from shared.eval.trace_schemas import TraceEvent, TraceEventType, TraceSummary


class TraceWriter:
    """Appends structured trace events to a JSONL file.

    Args:
        output_path: Path to the JSONL file to write.
        run_id: Optional run ID; generated if not provided.
    """

    def __init__(self, output_path: Path, *, run_id: str | None = None) -> None:
        self.output_path = Path(output_path)
        self.trace_id = f"trace-{uuid4().hex[:16]}"
        self.run_id = run_id or f"run-{uuid4().hex[:16]}"
        self._events: list[TraceEvent] = []

    def emit(
        self,
        event_type: TraceEventType,
        source: str,
        *,
        scenario_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> TraceEvent:
        """Emit a trace event to the JSONL file.

        Args:
            event_type: The type of trace event.
            source: Component that emitted the event.
            scenario_id: Optional scenario identifier.
            payload: Optional event-specific data.

        Returns:
            The emitted TraceEvent.
        """
        event = TraceEvent(
            trace_id=self.trace_id,
            run_id=self.run_id,
            scenario_id=scenario_id,
            event_type=event_type,
            source=source,
            payload=payload or {},
        )
        self._events.append(event)

        with open(self.output_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event.model_dump(mode="json")) + "\n")

        return event

    def summary(self) -> TraceSummary:
        """Compute an aggregated summary of all emitted events.

        Returns:
            TraceSummary with event counts and time range.
        """
        events = self._events
        if self.output_path.exists():
            parsed_events: list[TraceEvent] = []
            try:
                for line in self.output_path.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    try:
                        parsed_events.append(
                            TraceEvent.model_validate_json(line)
                        )
                    except Exception:
                        continue
                if parsed_events:
                    events = parsed_events
            except Exception:
                # Fall back to in-memory events when file parsing fails.
                events = self._events

        counts = Counter(e.event_type for e in events)
        timestamps = sorted(e.timestamp for e in events)
        now = datetime.now(UTC)

        return TraceSummary(
            trace_id=self.trace_id,
            run_id=self.run_id,
            total_events=len(events),
            event_type_counts=dict(counts),
            first_event_at=timestamps[0] if timestamps else now,
            last_event_at=timestamps[-1] if timestamps else now,
            trace_file=str(self.output_path),
        )
