"""Normalize Postgres URLs so SQLAlchemy uses psycopg v3, not the default psycopg2 dialect."""

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def _strip_query_params(url: str, names: frozenset[str]) -> str:
    p = urlparse(url)
    if not p.query:
        return url
    kept = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k not in names]
    return urlunparse(p._replace(query=urlencode(kept)))


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
    # Neon often adds channel_binding=require; psycopg3 + some hosts error on it.
    if "channel_binding" in url:
        url = _strip_query_params(url, frozenset({"channel_binding"}))
    return url
