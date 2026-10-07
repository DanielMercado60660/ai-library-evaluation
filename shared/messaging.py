from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from enum import Enum

class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    EXPIRED = "expired"

class AsyncNotification(BaseModel):
    """
    Schema for handling asynchronous tasks when services are down
     or resources (like books) are unavailable.
    """
    notification_id: str
    patron_id: str
    service_origin: str  # e.g., "catalog", "circulation"
    trigger_event: str   # e.g., "book_available", "service_restored"
    
    # The context the agent needs to resume the task
    original_request_context: Dict[str, Any]
    
    status: NotificationStatus = NotificationStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    
    def to_system_prompt(self) -> str:
        """
        Converts this notification into a 'wake-up' prompt for the agent.
        """
        return f"NOTIFICATION: The {self.service_origin} service reports that '{self.trigger_event}' has occurred for patron {self.patron_id}."