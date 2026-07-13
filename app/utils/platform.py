"""Derive lead platform from URLs and model output."""

from __future__ import annotations

from urllib.parse import urlparse

_HOST_PLATFORM: list[tuple[str, str]] = [
    ("reddit.com", "reddit"),
    ("g2.com", "g2"),
    ("capterra.com", "capterra"),
    ("trustpilot.com", "trustpilot"),
    ("producthunt.com", "producthunt"),
    ("news.ycombinator.com", "hackernews"),
    ("ycombinator.com", "hackernews"),
    ("linkedin.com", "linkedin"),
    ("twitter.com", "twitter"),
    ("x.com", "twitter"),
    ("getapp.com", "getapp"),
    ("softwareadvice.com", "softwareadvice"),
]


def platform_from_url(url: str, *, fallback: str = "other") -> str:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    for fragment, name in _HOST_PLATFORM:
        if host == fragment or host.endswith(f".{fragment}") or fragment in host:
            return name
    return fallback


def resolve_platform(model_value: str | None, url: str, *, fallback: str = "other") -> str:
    raw = (model_value or "").strip().lower()
    if raw and raw not in {"web", "unknown"}:
        return raw[:64]
    return platform_from_url(url, fallback=fallback)
