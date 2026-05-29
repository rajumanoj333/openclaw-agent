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
_BORING_COLORS = {
    "#fff", "#ffffff", "#000", "#000000",
    "#fafafa", "#f5f5f5", "#f0f0f0", "#eee", "#eeeeee",
    "#111", "#111111", "#222", "#222222", "#333", "#333333",
}


def _is_useful_color(hex6: str) -> bool:
    """
    Reject near-white, near-black, near-greyscale colors. These are CSS
    structural values (backgrounds, body text) not brand colors. A real
    brand color has chromatic spread + sits in the perceptually visible
    lightness range.
    """
    if hex6 in _BORING_COLORS:
        return False
    try:
        r = int(hex6[1:3], 16)
        g = int(hex6[3:5], 16)
        b = int(hex6[5:7], 16)
    except (ValueError, IndexError):
        return False
    avg = (r + g + b) / 3
    if avg > 235 or avg < 22:
        return False
    spread = max(r, g, b) - min(r, g, b)
    return spread >= 14

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

    # Skip aux pages that 404'd — their HTML is just the site's "page not
    # found" template, which adds noise (nav + footer + CTAs) without
    # contributing real business info. Some sites (Apple) ship a 2-3kb
    # 404 page that confuses the LLM extraction.
    if status >= 400:
        logger.info(f"scrape skip non-2xx url={norm} status={status}")
        return ScrapedPage(
            url=norm, source=source, final_url=final_url, status=status,
            text="", raw_html="",
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
    """
    Pull distinct hex / rgb() colors out of raw HTML/CSS.

    Priority order:
      1. <meta name="theme-color"> — the canonical brand color, set by the
         site owner for mobile address bar / PWA tinting.
      2. <link rel="mask-icon" color="...">
      3. CSS hex literals
      4. CSS rgb()/rgba() values
    Filtered by _is_useful_color() — near-white, near-black, and
    near-greyscale values are dropped as they're structural CSS not brand.
    """
    soup = BeautifulSoup(html, "lxml")
    found: list[str] = []
    seen: set[str] = set()

    def _accept(hex_value: str) -> None:
        if hex_value in seen:
            return
        if not _is_useful_color(hex_value):
            return
        seen.add(hex_value)
        found.append(hex_value)

    # 1. theme-color (best brand signal)
    for meta_name in ("theme-color", "msapplication-TileColor"):
        tag = soup.find("meta", attrs={"name": meta_name})
        if tag and tag.get("content"):
            v = tag["content"].strip().lower()
            if v.startswith("#") and (len(v) == 4 or len(v) == 7):
                if len(v) == 4:
                    v = "#" + "".join(ch * 2 for ch in v[1:])
                _accept(v)

    # 2. mask-icon color
    for link in soup.find_all("link", attrs={"rel": True}):
        rels = link.get("rel") or []
        if isinstance(rels, str):
            rels = [rels]
        if "mask-icon" in [str(r).lower() for r in rels]:
            v = (link.get("color") or "").strip().lower()
            if v.startswith("#") and len(v) in (4, 7):
                if len(v) == 4:
                    v = "#" + "".join(ch * 2 for ch in v[1:])
                _accept(v)

    # 3. CSS hex literals — scan the whole HTML (catches inline styles + CSS)
    for m in _HEX_RE.finditer(html):
        c = "#" + m.group(1).lower()
        if len(c) == 4:
            c = "#" + "".join(ch * 2 for ch in c[1:])
        _accept(c)
        if len(found) >= 12:
            break

    # 4. rgb()/rgba() values
    for m in _RGB_RE.finditer(html):
        r, g, b = (int(x) for x in m.groups())
        c = f"#{r:02x}{g:02x}{b:02x}"
        _accept(c)
        if len(found) >= 12:
            break

    return found


def _extract_logo(html: str, base_url: str) -> str | None:
    """
    Logo detection in priority order. Schema.org Organization.logo is the
    most reliable signal on big sites — that's the canonical marketing
    asset. Falls through to <img>, then favicon variants, then og:image
    (worst — often product/article hero on big-brand pages).
    """
    soup = BeautifulSoup(html, "lxml")

    # 1. JSON-LD schema.org Organization.logo — most reliable on big sites.
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text() or ""
        if not raw.strip():
            continue
        try:
            import json
            blobs = json.loads(raw)
        except json.JSONDecodeError:
            continue
        # Schema.org allows single object or array; @graph for nested
        candidates: list = blobs if isinstance(blobs, list) else [blobs]
        if isinstance(blobs, dict) and isinstance(blobs.get("@graph"), list):
            candidates = candidates + blobs["@graph"]
        for c in candidates:
            if not isinstance(c, dict):
                continue
            t = c.get("@type")
            types = t if isinstance(t, list) else [t] if t else []
            org_like = any(
                str(tt).lower() in ("organization", "localbusiness", "corporation",
                                    "store", "restaurant", "school", "medicalclinic")
                for tt in types
            )
            if not org_like:
                continue
            logo = c.get("logo")
            if isinstance(logo, str) and logo and not logo.startswith("data:"):
                return urljoin(base_url, logo)
            if isinstance(logo, dict):
                url = logo.get("url") or logo.get("contentUrl")
                if isinstance(url, str) and url and not url.startswith("data:"):
                    return urljoin(base_url, url)

    # 2. <img> with "logo" in src/alt/class/id
    for img in soup.find_all("img"):
        haystack = " ".join(
            str(img.get(attr, "")) for attr in ("src", "alt", "class", "id")
        ).lower()
        if "logo" in haystack:
            src = img.get("src") or img.get("data-src")
            if src and not src.startswith("data:"):
                return urljoin(base_url, src)

    # 3. apple-touch-icon (usually 180x180, higher quality than favicon).
    # 4. <link rel="icon"> / mask-icon / shortcut icon
    # BS parses rel as a list (it's a multi-value HTML attr) so we have to
    # match by iterating, not via attrs={"rel": "..."} which only matches
    # exact string equality and silently skips real-world list values.
    apple_touch: str | None = None
    plain_icon: str | None = None
    for link in soup.find_all("link"):
        rels = link.get("rel") or []
        if isinstance(rels, str):
            rels = [rels]
        rel_set = {str(r).lower() for r in rels}
        href = link.get("href")
        if not href or href.startswith("data:"):
            continue
        if "apple-touch-icon" in rel_set or "apple-touch-icon-precomposed" in rel_set:
            apple_touch = apple_touch or urljoin(base_url, href)
        elif any("icon" in r for r in rel_set):
            plain_icon = plain_icon or urljoin(base_url, href)
    if apple_touch:
        return apple_touch
    if plain_icon:
        return plain_icon

    # 5. og:image / twitter:image — last resort (often product/article image).
    for prop in ("og:image", "twitter:image"):
        meta = soup.find("meta", attrs={"property": prop}) or soup.find(
            "meta", attrs={"name": prop}
        )
        if meta and meta.get("content"):
            content = meta["content"]
            if not content.startswith("data:"):
                return urljoin(base_url, content)

    return None


def _clean(html: str) -> tuple[str, str | None]:
    """
    Strip scripts/styles/tags, collapse whitespace, return (text, title).

    BEFORE stripping <script type="application/ld+json"> blocks (used by Google
    for rich snippets — typically Organization / LocalBusiness / Product) and
    relevant <meta> tags (description, og:*, twitter:*) are extracted and
    prepended to the cleaned text. These structured signals dramatically
    improve LLM extraction quality on big brand sites where the visible HTML
    is mostly product nav.
    """
    soup = BeautifulSoup(html, "lxml")
    title = (soup.title.string.strip() if soup.title and soup.title.string else None)

    structured: list[str] = []

    # 1. JSON-LD structured data (often has Organization with name, url, sameAs,
    #    address, contactPoint, founder, foundingDate, logo, description, etc.)
    for s in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = s.string or s.get_text()
        if not raw or not raw.strip():
            continue
        # cap each JSON-LD blob — some sites ship 50+ KB of breadcrumbs
        snippet = raw.strip()[:4000]
        structured.append(f"[JSON-LD]\n{snippet}")

    # 2. Meta description + og: + twitter: (canonical short summary of page)
    meta_kv: list[str] = []
    for prop in (
        "description",
        "keywords",
        "og:title",
        "og:description",
        "og:site_name",
        "twitter:title",
        "twitter:description",
    ):
        meta = soup.find("meta", attrs={"name": prop}) or soup.find(
            "meta", attrs={"property": prop}
        )
        if meta and meta.get("content"):
            meta_kv.append(f"{prop}: {meta['content'].strip()[:600]}")
    if meta_kv:
        structured.append("[META]\n" + "\n".join(meta_kv))

    for tag in soup(["script", "style", "noscript", "iframe", "svg"]):
        tag.decompose()

    visible = soup.get_text(separator=" ")
    visible = re.sub(r"\s+", " ", visible).strip()

    # Prepend the structured block so trim() keeps it in the head.
    combined = (
        "\n\n".join(structured) + "\n\n[VISIBLE TEXT]\n" + visible
        if structured
        else visible
    )
    return combined[:12000], title


URL_REGEX = re.compile(
    r"\b(?:https?://|www\.)[^\s<>'\"()]+",
    re.IGNORECASE,
)


def find_urls(text: str) -> list[str]:
    """Return all URLs found in a free-form text message."""
    return [m.group(0) for m in URL_REGEX.finditer(text or "")]
