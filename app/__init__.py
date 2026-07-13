"""KramaAI lead monitoring application package."""

from app.utils.asyncio_policy import configure_windows_event_loop_policy

configure_windows_event_loop_policy()
