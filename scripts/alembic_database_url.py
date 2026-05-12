"""Print a synchronous SQLAlchemy URL for Alembic (stdout). Used in CI."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.utils.postgres_url import normalize_postgres_url


def resolve_sync_url() -> str:
    sync = os.environ.get("SYNC_DATABASE_URL", "").strip()
    primary = os.environ.get("DATABASE_URL", "").strip()
    url = sync or primary
    if not url:
        print("Set DATABASE_URL or SYNC_DATABASE_URL", file=sys.stderr)
        raise SystemExit(1)
    return normalize_postgres_url(url)


if __name__ == "__main__":
    print(resolve_sync_url())
