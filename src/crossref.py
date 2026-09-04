"""
Crossref REST API client for P-Layer Journal Radar.

Crossref is a DOI registration agency. Publishers deposit metadata for every
DOI they mint, so Crossref is usually the most complete and most up-to-date
source of "what just got published" for any given journal.

We use one of the free, public REST endpoints:
  https://api.crossref.org/works
  ?filter=issn:{ISSN},type:journal-article
  &sort=published&order=desc
  &rows=70
  &select=DOI,title,author,abstract,published,issued,container-title,link,URL,volume,issue,page,article-number,subject

The polite pool requires a contact email in the `mailto` query param; we send
the value from the PIA_CONTACT_EMAIL env var when set, otherwise omit it.
"""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

CROSSREF_BASE = "https://api.crossref.org/works"
USER_AGENT = "p-layer-journal-radar/0.1 (+https://github.com/)"
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2.0


class CrossrefError(RuntimeError):
    """Raised when the Crossref API cannot be reached or returns a hard error."""


def _http_get_json(url: str, timeout: float = 25.0) -> dict[str, Any]:
    """GET url, parse JSON. Retries on 429 and 5xx with exponential backoff."""
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})

    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            with urlopen(req, timeout=timeout) as resp:
                body = resp.read()
            return json.loads(body)
        except HTTPError as e:
            last_err = e
            if e.code == 429 or 500 <= e.code < 600:
                time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue
            raise CrossrefError(f"Crossref HTTP {e.code} for {url}") from e
        except URLError as e:
            last_err = e
            time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
            continue
    raise CrossrefError(f"Crossref unreachable after {MAX_RETRIES} tries: {last_err}")


def fetch_journal_works(issn: str, rows: int = 70, mailto: str | None = None) -> list[dict[str, Any]]:
    """Return the most recent Crossref `works` entries for a journal ISSN.

    Entries are sorted by `published` date descending. We additionally filter
    client-side to `type == "journal-article"` because some publishers deposit
    book reviews, errata, and editorial material into the same ISSN bucket.
    """
    params: list[tuple[str, str]] = [
        ("filter", f"issn:{issn},type:journal-article"),
        ("sort", "published"),
        ("order", "desc"),
        ("rows", str(rows)),
        ("select",
         "DOI,title,author,abstract,published,issued,container-title,link,URL,"
         "volume,issue,page,article-number,subject,type"),
    ]
    if mailto:
        params.append(("mailto", mailto))

    url = f"{CROSSREF_BASE}?{urlencode(params)}"
    payload = _http_get_json(url)
    message = payload.get("message") or {}
    items = message.get("items") or []
    return [item for item in items if item.get("type") == "journal-article"]
