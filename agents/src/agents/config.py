"""Configuration for the AI agents."""

import os

# Service URLs
CATALOG_URL = os.getenv("CATALOG_URL", "http://localhost:8001")
CIRCULATION_URL = os.getenv("CIRCULATION_URL", "http://localhost:8002")
RECOMMENDATION_URL = os.getenv("RECOMMENDATION_URL", "http://localhost:8003")
AUTH_URL = os.getenv("AUTH_URL", "http://localhost:8004")

# LLM Configuration
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-3-flash-preview")

# Agent Configuration
AGENT_MAX_ITERATIONS = int(os.getenv("AGENT_MAX_ITERATIONS", "10"))

# Evaluation mode: disable deterministic shortcuts so all queries go through the LLM.
# Set to "true" to enable shortcuts (faster but bypasses model inference).
EVAL_SHORTCUTS_ENABLED = os.getenv("EVAL_SHORTCUTS_ENABLED", "false").lower() in ("true", "1", "yes")

# ADK runtime timeout in seconds
AGENT_RESPONSE_TIMEOUT_SEC = int(os.getenv("AGENT_RESPONSE_TIMEOUT_SEC", "60"))

# Refusal markers — phrases that indicate the model refused/couldn't handle a request.
# Used only when EVAL_SHORTCUTS_ENABLED=true to trigger deterministic fallbacks.
REFUSAL_MARKERS = (
    "do not have the functionality",
    "don't have the functionality",
    "do not have access",
    "don't have access",
    "cannot access",
    "can't access",
    "unable to access",
    "i cannot",
)

# Patron ID prompt markers — phrases where the model asks for a patron ID
# (which it shouldn't when active profile context exists).
PATRON_ID_PROMPT_MARKERS = (
    "need your patron id",
    "provide your patron id",
    "what is your patron id",
    "could you please provide your patron id",
    "i'll need your patron id",
)
