"""A2A envelope and relay schemas shared across services."""

from datetime import datetime, UTC
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, ConfigDict


class A2AMessageType(str, Enum):
    """Supported A2A message types for MVP."""

    LOAN_REQUEST = "loan_request"
    LOAN_RESPONSE = "loan_response"
    ITEM_SHIPPED = "item_shipped"
    ITEM_RETURNED = "item_returned"
    ITEM_RETURN_ACK = "item_return_ack"
    ERROR = "error"


class A2AMessageEnvelope(BaseModel):
    """Transport envelope for registry-backed relay."""

    model_config = ConfigDict(use_enum_values=True)

    id: str = Field(default_factory=lambda: f"a2a-{uuid4().hex[:16]}")
    type: A2AMessageType
    from_library: str
    to_library: str
    correlation_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any] = Field(default_factory=dict)


class A2ASendRequest(BaseModel):
    """Send request for registry relay."""

    message: A2AMessageEnvelope


class A2ASendResponse(BaseModel):
    """Relay acknowledgement for sent message."""

    accepted: bool
    message_id: str
    queued_for: str
    status: str = "queued"  # "queued" or "duplicate"


class A2AInboxResponse(BaseModel):
    """Inbox response for library message pull."""

    library_code: str
    total: int
    messages: list[A2AMessageEnvelope]


class A2AAckRequest(BaseModel):
    """Acknowledge one message in relay."""

    library_code: str


class A2AAckResponse(BaseModel):
    """Ack response."""

    acknowledged: bool
    message_id: str
    library_code: str
