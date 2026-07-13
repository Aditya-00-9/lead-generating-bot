"""Shared lead-discovery signals and search query templates (Phase 1)."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from urllib.parse import urlparse

from rapidfuzz.fuzz import ratio

from app.models.schemas import ExtractedWebMention

PREFERRED_SOURCES: list[str] = [
    "reddit.com",
    "facebook.com",
    "linkedin.com",
    "news.ycombinator.com",
    "twitter.com",
    "x.com",
    "producthunt.com",
    "trustpilot.com",
    "g2.com",
    "capterra.com",
    "getapp.com",
    "softwareadvice.com",
]

PAIN_SIGNALS: list[str] = [
    "cancelling my subscription",
    "canceling my subscription",
    "switching from",
    "looking for alternative",
    "terrible support",
    "overpriced",
    "too slow",
    "lost our data",
    "billing nightmare",
    "contract trap",
    "feature missing",
    "migrating away from",
    "frustrated with",
    "anyone else having issues with",
    "thinking of switching",
    "moved away from",
    "not worth",
    "switched to",
]

# Fresh discussion first; demote evergreen product review index pages.
# Prefer individual post/review permalinks over listing URLs.
SEARCH_QUERY_TEMPLATES: list[str] = [
    'site:reddit.com "{competitor}" (cancel OR switch OR "not worth" OR "looking for alternative")',
    'site:reddit.com/r/gymowners "{competitor}"',
    'site:reddit.com/r/smallbusiness OR site:reddit.com/r/SaaS "{competitor}" (billing OR support OR switch)',
    'site:facebook.com/groups "{competitor}" (switch OR alternative OR cancel OR expensive)',
    '"{competitor}" ("past month" OR "this year" OR 2025 OR 2026) (switch OR cancel OR "not worth" OR "looking for")',
    '"{competitor}" "too expensive" OR "bad support" OR "switched to" OR "migrating away"',
    '"{competitor}" "looking for recommendations" OR "anyone recommend" studio OR gym software',
    '"{competitor}" LinkedIn (complaint OR issue OR switching OR frustrated)',
    '"{competitor}" site:news.ycombinator.com',
    '"{competitor}" (churn OR "cancel subscription" OR "contract trap")',
    '"{competitor}" alternative -site:g2.com -site:capterra.com',
    'site:trustpilot.com/reviews "{competitor}"',
    'site:g2.com "{competitor}" (cons OR "not recommend") review -"/reviews?"',
    'site:capterra.com "{competitor}" (negative OR "would not recommend")',
]

# Ambiguous short brand names that collide with generic language.
AMBIGUOUS_COMPETITORS: frozenset[str] = frozenset({"mindbody", "jackrabbit", "glofox", "vagaro"})

DEFAULT_CONTEXT_WORDS: list[str] = [
    "studio",
    "gym",
    "software",
    "booking",
    "class",
    "yoga",
    "fitness",
    "pilates",
    "scheduling",
    "membership",
    "martial arts",
    "dojo",
]

COMPETITOR_CONTEXT_WORDS: dict[str, list[str]] = {
    "mindbody": ["studio", "gym", "software", "booking", "class", "yoga", "fitness", "pilates", "scheduling"],
    "jackrabbit": ["class", "studio", "gym", "dance", "gymnastics", "software", "scheduling"],
    "glofox": ["gym", "fitness", "studio", "software", "booking", "members"],
    "vagaro": ["salon", "spa", "studio", "booking", "software", "scheduling"],
}

# Prefer fetchable discussion hosts; G2/Capterra block bots (403).
DEEP_EXTRACT_PRIORITY_HOSTS: tuple[str, ...] = (
    "reddit.com",
    "news.ycombinator.com",
    "linkedin.com",
    "trustpilot.com",
)

DEEP_EXTRACT_DENYLIST_HOST_FRAGMENTS: tuple[str, ...] = (
    "g2.com",
    "capterra.com",
    "medium.com",
    "quora.com",
    "pinterest.com",
    "buzzfeed.com",
    "forbes.com",
    "techradar.com",
    "softwareadvice.com/resources",
    "getapp.com/resources",
    "alternativeto.net",
    "slant.co",
)

# Product-level review indexes that rediscover forever and rarely yield unique leads.
_G2_LISTING = re.compile(r"^/products/[^/]+/reviews/?$", re.IGNORECASE)
_G2_LISTING_QS = re.compile(r"^/products/[^/]+/reviews$", re.IGNORECASE)
_CAPTERRA_LISTING = re.compile(r"^/p/\d+/[^/]+/reviews/?$", re.IGNORECASE)
_TRUSTPILOT_COMPANY = re.compile(r"^/review/[^/]+/?$", re.IGNORECASE)


def rotate_competitors(
    competitors: list[str],
    *,
    competitors_per_run: int,
    on_date: date | None = None,
) -> list[str]:
    """Slice competitors by day-of-year so each run deep-dives a rotating subset."""
    brands = [c.strip() for c in competitors if c.strip()]
    if not brands:
        return []
    n = max(1, competitors_per_run)
    if len(brands) <= n:
        return brands
    day = (on_date or datetime.now(timezone.utc).date()).timetuple().tm_yday
    start = (day - 1) % len(brands)
    return [brands[(start + i) % len(brands)] for i in range(n)]


def build_search_queries(
    competitors: list[str],
    keywords: list[str],
    *,
    max_searches: int,
    competitors_per_run: int,
    on_date: date | None = None,
) -> list[str]:
    """Interleave rotated competitor × template queries, then keyword fallbacks."""
    brands = rotate_competitors(
        competitors,
        competitors_per_run=competitors_per_run,
        on_date=on_date,
    )
    if not brands and keywords:
        return [k.strip() for k in keywords if k.strip()][:max_searches]

    per_brand: list[list[str]] = []
    for brand in brands:
        per_brand.append([tpl.format(competitor=brand) for tpl in SEARCH_QUERY_TEMPLATES])

    queries: list[str] = []
    max_rounds = max((len(q) for q in per_brand), default=0)
    for round_idx in range(max_rounds):
        for brand_queries in per_brand:
            if round_idx < len(brand_queries):
                queries.append(brand_queries[round_idx])
                if len(queries) >= max_searches:
                    return queries

    for kw in keywords:
        kw = kw.strip()
        if kw and kw not in queries:
            queries.append(kw)
            if len(queries) >= max_searches:
                break
    return queries[:max_searches]


def format_preferred_sources() -> str:
    return ", ".join(PREFERRED_SOURCES)


def format_pain_signals() -> str:
    return "\n".join(f"- {s}" for s in PAIN_SIGNALS)


# Short substring checks for pipeline gate 1 (fast pre-triage filter).
GATE_PAIN_SIGNALS: list[str] = [
    "cancel",
    "canceling",
    "cancellation",
    "switching",
    "switch to",
    "switch from",
    "switched to",
    "hate",
    "broken",
    "bug",
    "glitch",
    "expensive",
    "overpriced",
    "support is",
    "terrible",
    "nightmare",
    "looking for alternative",
    "moved away",
    "thinking of switching",
    "considering leaving",
    "frustrated with",
    "billing nightmare",
    "not worth",
    "migrating away",
]


def text_has_pain_signal(text: str) -> bool:
    t = text.lower()
    if any(s in t for s in GATE_PAIN_SIGNALS):
        return True
    return any(s in t for s in PAIN_SIGNALS)


def _host_matches(url: str, fragment: str) -> bool:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    path = urlparse(url).path.lower()
    if fragment.endswith("/resources"):
        return fragment.split("/")[0] in host and "/resources" in path
    return host == fragment or host.endswith(f".{fragment}") or fragment in host


def is_weak_listing_url(url: str) -> bool:
    """True for product review index pages (not individual review/thread permalinks)."""
    parsed = urlparse((url or "").strip().split()[0])
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/") or "/"
    path_with_slash = path if path.endswith("/") else path + "/"
    # Normalize path without trailing slash for regexes that allow optional /
    bare = path.rstrip("/")

    if host == "g2.com" or host.endswith(".g2.com"):
        # Individual reviews have extra path segments after /reviews/
        if _G2_LISTING.match(bare) or _G2_LISTING_QS.match(bare):
            return True
        # /products/foo/reviews with only query string (e.g. ?qs=pros-and-cons)
        if re.match(r"^/products/[^/]+/reviews$", bare, re.IGNORECASE) and parsed.query:
            return True
        return False

    if host == "capterra.com" or host.endswith(".capterra.com"):
        return bool(_CAPTERRA_LISTING.match(bare) or _CAPTERRA_LISTING.match(path_with_slash.rstrip("/")))

    if host == "trustpilot.com" or host.endswith(".trustpilot.com"):
        # Company page /review/company.com — individual reviews have /reviews/id
        if "/reviews/" in bare.lower():
            return False
        return bool(_TRUSTPILOT_COMPANY.match(bare))

    return False


def is_deep_extract_denied(url: str) -> bool:
    return any(_host_matches(url, fragment) for fragment in DEEP_EXTRACT_DENYLIST_HOST_FRAGMENTS)


def deep_extract_priority(url: str) -> int:
    for idx, host in enumerate(DEEP_EXTRACT_PRIORITY_HOSTS):
        if _host_matches(url, host):
            return len(DEEP_EXTRACT_PRIORITY_HOSTS) - idx
    return 0


def select_urls_for_deep_extract(items: list[ExtractedWebMention], limit: int) -> list[str]:
    """Pick URLs for page fetch: prioritize discussion hosts, skip listicles and blocked review sites."""
    candidates: list[ExtractedWebMention] = []
    for item in items:
        url = (item.source_url or "").strip().split()[0]
        if not url.startswith("http") or is_deep_extract_denied(url) or is_weak_listing_url(url):
            continue
        excerpt = (item.excerpt or item.title or "").strip()
        if excerpt and text_has_pain_signal(excerpt):
            continue
        candidates.append(item)

    candidates.sort(
        key=lambda it: (deep_extract_priority(it.source_url), it.relevance_score),
        reverse=True,
    )
    urls: list[str] = []
    for item in candidates[:limit]:
        url = (item.source_url or "").strip().split()[0]
        if url and url not in urls:
            urls.append(url)
    return urls


def blend_source_quality(triage_quality: float, collection_relevance: float | None) -> float:
    if collection_relevance is None:
        return triage_quality
    return round(0.55 * triage_quality + 0.45 * collection_relevance, 2)


def _competitor_in_text(text: str, competitor: str) -> bool:
    return competitor.lower() in text.lower()


def passes_competitor_context(
    text: str,
    competitors: list[str],
    competitor_mentioned: str | None = None,
) -> bool:
    """Require industry context words near ambiguous competitor names."""
    lowered = text.lower()
    brands = [competitor_mentioned] if competitor_mentioned else competitors
    mentioned: list[str] = []
    for brand in brands:
        if brand and _competitor_in_text(lowered, brand):
            mentioned.append(brand)

    if not mentioned:
        return True

    for brand in mentioned:
        key = brand.lower()
        if key not in AMBIGUOUS_COMPETITORS and " " in brand.strip():
            continue
        if key not in AMBIGUOUS_COMPETITORS and len(key) >= 10:
            continue
        context_words = COMPETITOR_CONTEXT_WORDS.get(key, DEFAULT_CONTEXT_WORDS)
        if not any(word in lowered for word in context_words):
            return False
    return True


def is_near_duplicate_text(
    text_a: str,
    text_b: str,
    *,
    threshold: int,
    competitor_a: str | None = None,
    competitor_b: str | None = None,
) -> bool:
    if competitor_a and competitor_b and competitor_a.lower() != competitor_b.lower():
        return False
    return ratio(text_a[:1000], text_b[:1000]) >= threshold


def format_seen_urls_block(urls: list[str], *, max_urls: int = 80) -> str:
    """Build a prompt block steering the model away from already-stored URLs."""
    cleaned: list[str] = []
    for u in urls:
        u = (u or "").strip().split()[0]
        if u.startswith("http") and u not in cleaned:
            cleaned.append(u)
        if len(cleaned) >= max_urls:
            break
    if not cleaned:
        return ""
    lines = "\n".join(f"- {u}" for u in cleaned)
    return (
        "Already collected — do NOT return these URLs (find different permalinks/threads):\n"
        f"{lines}\n"
    )
