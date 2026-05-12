"""Normalize Postgres URLs so SQLAlchemy uses psycopg v3, not the default psycopg2 dialect."""


def normalize_postgres_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return url
    if "+asyncpg://" in url:
        url = url.replace("+asyncpg://", "+psycopg://", 1)
    if "+psycopg_async://" in url:
        url = url.replace("+psycopg_async://", "+psycopg://", 1)
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url
