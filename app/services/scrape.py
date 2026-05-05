"""
Business-info scraper. Mirrors Kaamy-AI logic:

  1. Normalize URL & detect source (website / instagram / facebook / google maps).
  2. Fetch HTML via httpx (with desktop User-Agent so most sites cooperate).
  3. Harvest CSS hex/RGB colors BEFORE stripping styles (used as brand-color hints).
  4. Extract logo URL via 3 strategies (img tag heuristics → favicon → og:image).
  5. Strip scripts/styles/HTML, return clean text + structured assets.

LLM extraction lives in `onboarding.py` — this module only does fetching/parsing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from loguru import logger

SourceKind = Literal["website", "instagram", "facebook", "maps", "justdial", "sulekha", "unknown"]

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_HEX_RE = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
_RGB_RE = re.compile(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})")
# Skip these — they're either too common or are our own brand.
_BORING_COLORS = {"#fff", "#ffffff", "#000", "#000000", "#fafafa", "#f5f5f5", "#eee", "#eeeeee"}

_FETCH_TIMEOUT = httpx.Timeout(15.0, connect=8.0)
_MAX_BYTES = 1_500_000  # cap response size — some sites return MB of HTML


@dataclass
class ScrapedPage:
    url: str
    source: SourceKind
    final_url: str
    status: int
    text: str            # cleaned plain text (used as LLM input)
    raw_html: str
    colors: list[str] = field(default_factory=list)
    logo_url: str | None = None
    title: str | None = None


def normalize_url(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    return raw


def detect_source(url: str) -> SourceKind:
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return "unknown"
    if "google." in host and "/maps" in url.lower():
        return "maps"
    if "maps.google" in host or "goo.gl/maps" in url.lower():
        return "maps"
    if "instagram.com" in host:
        return "instagram"
    if "facebook.com" in host or host.endswith("fb.com"):
        return "facebook"
    if "justdial.com" in host:
        return "justdial"
    if "sulekha.com" in host:
        return "sulekha"
    return "website"


async def fetch(url: str) -> ScrapedPage:
    """Fetch one URL and return a cleaned ScrapedPage. Never raises."""
    norm = normalize_url(url)
    source = detect_source(norm)

    if not norm:
        return ScrapedPage(
            url=url, source="unknown", final_url="", status=0, text="", raw_html=""
        )

    try:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=_FETCH_TIMEOUT, headers=_HEADERS
        ) as client:
            resp = await client.get(norm)
            html = resp.text[:_MAX_BYTES]
            final_url = str(resp.url)
            status = resp.status_code
    except Exception as e:
        logger.warning(f"scrape fetch failed url={norm}: {e!r}")
        return ScrapedPage(
            url=norm, source=source, final_url=norm, status=0, text="", raw_html=""
        )

    colors = _extract_colors(html)
    logo = _extract_logo(html, base_url=final_url)
    text, title = _clean(html)

    logger.info(
        f"scrape ok url={norm} status={status} chars={len(text)} "
        f"colors={len(colors)} logo={'yes' if logo else 'no'}"
    )
    return ScrapedPage(
        url=norm,
        source=source,
        final_url=final_url,
        status=status,
        text=text,
        raw_html=html,
        colors=colors,
        logo_url=logo,
        title=title,
    )


async def fetch_with_aux(url: str) -> list[ScrapedPage]:
    """
    For a website root, also try /about and /contact in parallel — these
    typically hold most of the business info.
    """
    primary = await fetch(url)
    if primary.source != "website" or not primary.final_url:
        return [primary]

    base = primary.final_url.rstrip("/")
    aux_urls = [f"{base}/about", f"{base}/contact"]
    import asyncio

    aux_results = await asyncio.gather(*(fetch(u) for u in aux_urls), return_exceptions=True)
    pages = [primary]
    for r in aux_results:
        if isinstance(r, ScrapedPage) and r.text:
            pages.append(r)
    return pages


# ─── helpers ─────────────────────────────────────────────────────────────


def _extract_colors(html: str) -> list[str]:
    """Pull distinct hex / rgb() colors out of raw HTML/CSS, drop boring ones."""
    found: list[str] = []
    seen: set[str] = set()

    for m in _HEX_RE.finditer(html):
        c = "#" + m.group(1).lower()
        if len(c) == 4:
            # expand #abc -> #aabbcc
            c = "#" + "".join(ch * 2 for ch in c[1:])
        if c in _BORING_COLORS or c in seen:
            continue
        seen.add(c)
        found.append(c)
        if len(found) >= 25:
            break

    for m in _RGB_RE.finditer(html):
        r, g, b = (int(x) for x in m.groups())
        c = f"#{r:02x}{g:02x}{b:02x}"
        if c in _BORING_COLORS or c in seen:
            continue
        seen.add(c)
        found.append(c)
        if len(found) >= 25:
            break

    return found


def _extract_logo(html: str, base_url: str) -> str | None:
    """Three strategies in priority order: <img>, <link icon>, og:image."""
    soup = BeautifulSoup(html, "lxml")

    # 1. <img> with "logo" in src/alt/class/id
    for img in soup.find_all("img"):
        haystack = " ".join(
            str(img.get(attr, "")) for attr in ("src", "alt", "class", "id")
        ).lower()
        if "logo" in haystack:
            src = img.get("src")
            if src:
                return urljoin(base_url, src)

    # 2. <link rel="icon"> / apple-touch-icon
    for link in soup.find_all("link"):
        rel = " ".join(link.get("rel") or []).lower()
        if "icon" in rel:
            href = link.get("href")
            if href:
                return urljoin(base_url, href)

    # 3. og:image / twitter:image
    for prop in ("og:image", "twitter:image"):
        meta = soup.find("meta", attrs={"property": prop}) or soup.find(
            "meta", attrs={"name": prop}
        )
        if meta and meta.get("content"):
            return urljoin(base_url, meta["content"])

    return None


def _clean(html: str) -> tuple[str, str | None]:
    """Strip scripts/styles/tags, collapse whitespace, return (text, title)."""
    soup = BeautifulSoup(html, "lxml")
    title = (soup.title.string.strip() if soup.title and soup.title.string else None)

    for tag in soup(["script", "style", "noscript", "iframe", "svg"]):
        tag.decompose()

    text = soup.get_text(separator=" ")
    text = re.sub(r"\s+", " ", text).strip()
    # cap at ~12k chars — LLM context guard
    return text[:12000], title


URL_REGEX = re.compile(
    r"\b(?:https?://|www\.)[^\s<>'\"()]+",
    re.IGNORECASE,
)


def find_urls(text: str) -> list[str]:
    """Return all URLs found in a free-form text message."""
    return [m.group(0) for m in URL_REGEX.finditer(text or "")]
