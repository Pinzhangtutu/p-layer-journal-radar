"""
Article cleaning & normalization for P-Layer Journal Radar.

Crossref returns raw metadata; the cleaner turns it into the uniform shape
that rss_builder expects. It also drops noise that publishers often mix into
their "new article" streams: errata, editorials, call-for-papers, etc.
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from email.utils import format_datetime
from typing import Any

# Match noise prefixes regardless of case. We treat the title as a strong
# signal; if it starts with one of these, the entry is dropped.
_NOISE_PREFIX = re.compile(
    r"^\s*("
    r"erratum|errata|corrigendum|correction|retraction|withdrawal|"
    r"editorial|editorials|editor'?s?\s+note|foreword|preface|"
    r"call\s+for\s+papers?|call\s+for\s+submissions?|announcement|"
    r"in\s+memoriam|tribute|obituary|"
    r"front\s*matter|back\s*matter|issue\s+information|masthead|"
    r"table\s+of\s+contents?|contents\s+page|"
    r"award\s+address|presidential\s+address|"
    r"reply\s+to|response\s+to|response\s+from|"
    r"book\s+review|book\s+reviews|review\s+essay|"
    r"introduction\s+to\s+the\s+special\s+issue|"
    r"special\s+issue\s+(foreword|introduction|preface)"
    r")\b[:\-\s]",
    re.IGNORECASE,
)

# Subjects Crossref attaches to noise entries (we still check them, but a hit
# here is not sufficient on its own to drop a paper).
_NOISE_SUBJECTS = {
    "erratum", "corrigendum", "retraction", "editorial",
    "correction", "withdrawal",
}

_JATS_TAG = re.compile(r"</?jats:[^>]*>")
_HTML_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")
_DOI_PREFIX = re.compile(r"^https?://(?:dx\.)?doi\.org/", re.IGNORECASE)


def is_research_article(item: dict[str, Any]) -> bool:
    """Return True if the Crossref work looks like an actual research article."""
    title = _first(item.get("title") or "")
    if not title:
        return False
    if _NOISE_PREFIX.match(title):
        return False

    type_ = item.get("type") or ""
    if type_ and type_ != "journal-article":
        return False

    subjects = {str(s).lower() for s in (item.get("subject") or [])}
    if subjects & _NOISE_SUBJECTS:
        return False

    # Some editorial notes are filed as journal-article; double-check by
    # title word for the common "Editorial:" / "Foreword:" forms that bypass
    # the prefix regex (e.g. when the colon is far from the start).
    lowered = title.lower()
    if lowered.startswith("editorial:") or lowered.startswith("editor's note:"):
        return False

    return True


def clean_abstract(raw: str | None) -> str:
    """Strip JATS/HTML tags and normalise whitespace, returning plain text."""
    if not raw:
        return ""
    text = html.unescape(raw)
    text = _JATS_TAG.sub("", text)
    text = _HTML_TAG.sub("", text)
    text = _WHITESPACE.sub(" ", text).strip()
    return text


def format_authors(authors: list[dict[str, Any]] | None) -> str:
    """Format the Crossref `author` list as `Given Family; Given Family`."""
    if not authors:
        return ""
    formatted: list[str] = []
    for a in authors:
        if not isinstance(a, dict):
            continue
        if a.get("name"):
            formatted.append(str(a["name"]).strip())
            continue
        given = str(a.get("given") or "").strip()
        family = str(a.get("family") or "").strip()
        full = f"{given} {family}".strip()
        if full:
            formatted.append(full)
    return "; ".join(formatted)


def format_date_rfc822(item: dict[str, Any]) -> str:
    """Return an RFC 822 UTC timestamp derived from `published`/`issued`."""
    parts = (item.get("published") or item.get("issued") or {}).get("date-parts")
    if not parts or not parts[0]:
        return format_datetime(datetime.now(timezone.utc))

    date_parts = parts[0]
    year = int(date_parts[0])
    month = int(date_parts[1]) if len(date_parts) > 1 and date_parts[1] else 1
    day = int(date_parts[2]) if len(date_parts) > 2 and date_parts[2] else 1
    dt = datetime(year, month, day, tzinfo=timezone.utc)
    return format_datetime(dt)


def first_author_short(authors: list[dict[str, Any]] | None) -> str:
    if not authors:
        return ""
    a = authors[0]
    if not isinstance(a, dict):
        return ""
    if a.get("family"):
        return f"{a.get('family', '')} {a.get('given', '')[:1]}.".strip()
    return str(a.get("name") or "").strip()


def get_doi(item: dict[str, Any]) -> str:
    return str(item.get("DOI") or "").strip()


def get_url(item: dict[str, Any]) -> str:
    url = str(item.get("URL") or "").strip()
    if url:
        return url
    doi = get_doi(item)
    if doi:
        return f"https://doi.org/{doi}"
    return ""


def get_title(item: dict[str, Any]) -> str:
    return _first(item.get("title") or "")


def _first(values: list[Any]) -> str:
    for v in values:
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return ""


def to_normalized_article(item: dict[str, Any]) -> dict[str, Any]:
    """Convert a raw Crossref `work` into the shape RSS builder expects."""
    authors = item.get("author") or []
    return {
        "doi": get_doi(item),
        "title": get_title(item),
        "authors": format_authors(authors),
        "author_short": first_author_short(authors),
        "abstract": clean_abstract(item.get("abstract")),
        "url": get_url(item),
        "pub_date": format_date_rfc822(item),
        "container": _first(item.get("container-title") or []),
        "volume": str(item.get("volume") or "").strip(),
        "issue": str(item.get("issue") or "").strip(),
        "page": str(item.get("page") or "").strip(),
    }


def dedupe_by_doi(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop duplicate articles by DOI, keeping the first occurrence (newest)."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for art in articles:
        doi = art.get("doi", "").lower()
        if doi and doi in seen:
            continue
        if doi:
            seen.add(doi)
        out.append(art)
    return out
