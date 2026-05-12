"""Print a synchronous SQLAlchemy URL for Alembic (stdout). Used in CI."""

import os
import sys


def resolve_sync_url() -> str:
    sync = os.environ.get("SYNC_DATABASE_URL", "").strip()
    primary = os.environ.get("DATABASE_URL", "").strip()
    url = sync or primary
    if not url:
        print("Set DATABASE_URL or SYNC_DATABASE_URL", file=sys.stderr)
        raise SystemExit(1)
    if "+asyncpg://" in url:
        url = url.replace("+asyncpg://", "+psycopg://", 1)
    if "+psycopg_async://" in url:
        url = url.replace("+psycopg_async://", "+psycopg://", 1)
    return url


if __name__ == "__main__":
    print(resolve_sync_url())
