"""Per-request context shared with the agent's tools (who is asking, and where)."""
from contextvars import ContextVar

current_user_id: ContextVar = ContextVar("current_user_id", default=None)
# (lat, lng) only when the user pressed "Use my location". Never stored in the database or logs.
current_location: ContextVar = ContextVar("current_location", default=None)
