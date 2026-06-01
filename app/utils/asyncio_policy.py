import asyncio
import sys


def configure_windows_event_loop_policy() -> None:
    """Use an event loop compatible with psycopg async connections on Windows."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
