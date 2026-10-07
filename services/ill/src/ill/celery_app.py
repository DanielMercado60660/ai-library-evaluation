"""Celery application configuration for ILL service.

This module configures Celery for async task processing with Redis as the broker.
"""

import os
from celery import Celery

# Get Redis URL from environment or use default
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Create Celery app
app = Celery(
    "ill",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["ill.tasks"],  # Auto-discover tasks from ill.tasks module
)

# Configure Celery
app.conf.update(
    # Task serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task execution
    task_track_started=True,
    task_time_limit=300,  # 5 minutes hard limit
    task_soft_time_limit=240,  # 4 minutes soft limit

    # Task routing
    task_routes={
        "ill.tasks.create_circulation_checkout": {"queue": "ill_processing"},
        "ill.tasks.update_catalog_status": {"queue": "ill_processing"},
        "ill.tasks.notify_partner_library": {"queue": "notifications"},
        "ill.tasks.check_overdue_ill_items": {"queue": "periodic"},
    },

    # Result backend
    result_expires=3600,  # Results expire after 1 hour

    # Worker configuration
    worker_prefetch_multiplier=1,  # Only prefetch one task at a time
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks
)

# Optional: Configure periodic tasks (beat schedule)
# Uncomment when implementing periodic tasks
# app.conf.beat_schedule = {
#     "check-overdue-items": {
#         "task": "ill.tasks.check_overdue_ill_items",
#         "schedule": 86400.0,  # Run daily (24 hours)
#     },
# }

if __name__ == "__main__":
    app.start()
