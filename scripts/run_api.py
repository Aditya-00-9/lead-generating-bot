"""Start FastAPI with Windows-compatible asyncio policy for psycopg."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.utils.asyncio_policy import configure_windows_event_loop_policy

configure_windows_event_loop_policy()

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        loop="app.utils.uvicorn_loop:selector_loop_factory",
    )
