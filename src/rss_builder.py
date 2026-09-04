"""
RSS 2.0 XML generation for P-Layer Journal Radar.

Produces a single, clean feed per journal so feed readers (Zotero, Feedly,
Inoreader, NetNewsWire, …) can subscribe. The output is hand-rolled XML
rather than using a library, so we can guarantee a strict subset that all
readers parse identically, and so the build has no extra dependencies.
"""

from __future__ import annotations

import html
import re
from typing import Any
from xml.sax.saxutils import escape, quoteattr

FEED_HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<rss version="2.0"\n'
    '     xmlns:dc="http://purl.org/dc/elements/1.1/"\n'
    '     xmlns:atom="http://www.w3.org/2005/Atom"\n'
    '     xmlns:content="http://purl.org/rss/1.0/modules/content/">\n'
    '<channel>\n'
)
FEED_FOOTER = '</channel>\n</rss>\n'

_WHITESPACE = re.compile(r"\s+")
_CDATA_END = re.compile(r"]]>")


def _text(s: str) -> str:
    return _WHITESPACE.sub(" ", html.unescape(s or "")).strip()


def _cdata(s: str) -> str:
    """Wrap content in CDATA, splitting any embedded `]]>` to keep XML valid."""
    if not s:
        return ""
    body = _CDATA_END.sub("]]]]><![CDATA[>", s)
    return f"<![CDATA[{body}]]>"


def build_rss(journal: dict[str, Any], articles: list[dict[str, Any]],
              feed_url: str, site_url: str, build_iso: str) -> str:
    """Return the full RSS 2.0 XML for one journal.

    `feed_url`  — public URL of THIS feed (used for atom:self, lets feed
                   readers detect the canonical location).
    `site_url`  — public URL of the dashboard root (linked from channel).
    """
    title = _text(journal.get("name", ""))
    abbr = _text(journal.get("abbr", ""))
    publisher = _text(journal.get("publisher", ""))
    stage = _text(journal.get("stage", ""))
    subfield = _text(journal.get("subfield", ""))
    desc_parts = [f"{abbr} — {publisher}".strip(" —")]
    if stage:
        desc_parts.append(f"Latest in: {stage}")
    if subfield:
        desc_parts.append(f"Subfield: {subfield}")
    desc = " · ".join(p for p in desc_parts if p)

    lines: list[str] = [FEED_HEADER]
    lines.append(f"<title>{escape(title)}</title>\n")
    lines.append(f"<link>{escape(site_url + '/#' + journal.get('id', ''))}</link>\n")
    lines.append(f"<description>{escape(desc)}</description>\n")
    lines.append(f"<language>en</language>\n")
    lines.append(
        f'<atom:link href={quoteattr(feed_url)} rel="self" type="application/rss+xml"/>\n'
    )
    lines.append(f"<lastBuildDate>{_rfc822(build_iso)}</lastBuildDate>\n")
    lines.append(f"<generator>p-layer-journal-radar</generator>\n")
    lines.append(f"<docs>https://www.rssboard.org/rss-specification</docs>\n")

    for art in articles:
        lines.extend(_render_item(art))

    lines.append(FEED_FOOTER)
    return "".join(lines)


def _render_item(art: dict[str, Any]) -> list[str]:
    title = _text(art.get("title", ""))
    url = _text(art.get("url", ""))
    doi = _text(art.get("doi", ""))
    authors = _text(art.get("authors", ""))
    abstract = (art.get("abstract") or "").strip()
    pub_date = art.get("pub_date") or ""
    guid = doi or url or title
    if not guid:
        return []

    out: list[str] = ["<item>\n"]
    out.append(f"<title>{escape(title)}</title>\n")
    out.append(f"<link>{escape(url)}</link>\n")
    out.append(
        f'<guid isPermaLink="false">{escape(guid)}</guid>\n'
    )
    out.append(f"<pubDate>{escape(pub_date)}</pubDate>\n")
    if authors:
        out.append(f"<dc:creator>{_cdata(authors)}</dc:creator>\n")
    if doi:
        out.append(f'<dc:identifier>{escape("doi:" + doi)}</dc:identifier>\n')

    if abstract:
        # Feed readers can show the abstract either as a description (with
        # markup preserved) or as content:encoded. We send both so any reader
        # shows something useful.
        out.append(f"<description>{_cdata(abstract)}</description>\n")
        out.append(f"<content:encoded>{_cdata(abstract)}</content:encoded>\n")
    else:
        out.append("<description></description>\n")

    out.append("</item>\n")
    return out


def _rfc822(iso_ts: str) -> str:
    """Convert an ISO-8601 timestamp to RFC 822 (for <lastBuildDate>)."""
    from datetime import datetime
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except ValueError:
        from email.utils import format_datetime
        from datetime import datetime, timezone
        return format_datetime(datetime.now(timezone.utc))
    from email.utils import format_datetime
    return format_datetime(dt.astimezone())
