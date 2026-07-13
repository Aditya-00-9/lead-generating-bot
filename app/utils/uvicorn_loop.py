"""Uvicorn loop factory for Windows + psycopg async compatibility."""

from __future__ import annotations

import asyncio


def selector_loop_factory() -> asyncio.AbstractEventLoop:
    """Create SelectorEventLoop (required for psycopg async; uvicorn defaults to Proactor on Windows)."""
    return asyncio.SelectorEventLoop()
