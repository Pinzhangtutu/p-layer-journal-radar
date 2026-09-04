"""
Main orchestrator for P-Layer Journal Radar.

Run from the repo root:

    python3 scripts/fetch.py              # full run, all enabled journals
    python3 scripts/fetch.py --only jcr,jams   # limit to a subset
    python3 scripts/fetch.py --dry-run    # print summary, do not write files

The script:
  1. Loads config/journals.yaml.
  2. For each enabled journal, fetches the most recent items from Crossref.
  3. Filters out errata/editorials/etc, normalizes the data, dedupes by DOI.
  4. If a journal has `publisher_rss` set AND Crossref returned fewer than
     MIN_ARTICLES, fetches the publisher feed as a fallback (best-effort).
  5. Generates docs/{id}.xml — one RSS 2.0 feed per journal.
  6. Generates docs/index.html — a human-browsable dashboard.
  7. Writes docs/status.json — machine-readable run report.

The script never panics on a single journal's failure; that journal is
recorded in the status report with the error message and the rest of the
build continues.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

# Make `src.*` importable when the script is run as a top-level module.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from cleaner import (  # noqa: E402
    dedupe_by_doi,
    is_research_article,
    to_normalized_article,
)
from crossref import CrossrefError, fetch_journal_works  # noqa: E402
from dashboard import build_dashboard  # noqa: E402
from rss_builder import build_rss  # noqa: E402

DOCS_DIR = ROOT / "docs"
CONFIG_PATH = ROOT / "config" / "journals.yaml"
STATUS_PATH = DOCS_DIR / "status.json"
MIN_ARTICLES_FOR_PUBLISHER_FALLBACK = 10
DEFAULT_SITE_URL = os.environ.get("PIA_RADAR_SITE_URL", "https://example.com/journal-radar")
CONTACT_EMAIL = os.environ.get("PIA_CONTACT_EMAIL")  # polite pool for Crossref


def load_config() -> list[dict[str, Any]]:
    if not CONFIG_PATH.exists():
        raise SystemExit(f"missing config: {CONFIG_PATH}")
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, list):
        raise SystemExit("config/journals.yaml must be a list")
    return data


def fetch_one(journal: dict[str, Any]) -> dict[str, Any]:
    """Fetch, clean, and dedupe a single journal. Return a status row."""
    jid = journal.get("id", "")
    issn = str(journal.get("issn") or "").strip()
    name = str(journal.get("name") or jid)
    started = datetime.now(timezone.utc).isoformat()

    if not issn:
        return _fail_row(journal, "missing issn", started)

    try:
        items = fetch_journal_works(issn, rows=70, mailto=CONTACT_EMAIL)
    except CrossrefError as e:
        return _fail_row(journal, str(e), started)
    except Exception as e:  # pragma: no cover - defensive
        return _fail_row(journal, f"unexpected: {e}", started)

    kept = [to_normalized_article(it) for it in items if is_research_article(it)]
    kept = dedupe_by_doi(kept)
    # Newest first; Crossref already sorts desc, but double-check.
    kept.sort(key=lambda a: a.get("pub_date") or "", reverse=True)

    return {
        "journal": journal,
        "article_count": len(kept),
        "articles": kept,
        "status": "ok" if kept else "empty",
        "last_success_iso": datetime.now(timezone.utc).isoformat(),
        "started_iso": started,
    }


def _fail_row(journal: dict[str, Any], msg: str, started_iso: str) -> dict[str, Any]:
    return {
        "journal": journal,
        "article_count": 0,
        "articles": [],
        "status": "failed",
        "error": msg,
        "started_iso": started_iso,
    }


def write_rss_files(rows: list[dict[str, Any]], site_url: str, build_iso: str) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    for row in rows:
        j = row["journal"]
        jid = j.get("id", "")
        feed_url = f"{site_url.rstrip('/')}/{jid}.xml"
        xml = build_rss(
            journal=j,
            articles=row.get("articles") or [],
            feed_url=feed_url,
            site_url=site_url,
            build_iso=build_iso,
        )
        (DOCS_DIR / f"{jid}.xml").write_text(xml, encoding="utf-8")


def write_dashboard(rows: list[dict[str, Any]], build_iso: str) -> None:
    html_doc = build_dashboard(rows, build_iso, lang="zh")
    (DOCS_DIR / "index.html").write_text(html_doc, encoding="utf-8")


def write_status(rows: list[dict[str, Any]], build_iso: str) -> None:
    payload = {
        "last_run_iso": build_iso,
        "feeds": [
            {
                "id": r["journal"].get("id"),
                "name": r["journal"].get("name"),
                "status": r.get("status"),
                "article_count": r.get("article_count", 0),
                "error": r.get("error"),
                "last_success_iso": r.get("last_success_iso"),
            }
            for r in rows
        ],
    }
    STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", help="comma-separated journal ids to fetch")
    parser.add_argument("--dry-run", action="store_true",
                        help="fetch and clean, but do not write docs/*")
    parser.add_argument("--site-url", default=DEFAULT_SITE_URL,
                        help="public URL of the dashboard root (used in <link> and atom:self)")
    args = parser.parse_args()

    cfg = load_config()
    only = set([s.strip() for s in (args.only or "").split(",") if s.strip()])

    rows: list[dict[str, Any]] = []
    for journal in cfg:
        if not journal.get("enabled", True):
            continue
        if only and journal.get("id") not in only:
            continue
        print(f"  · {journal.get('abbr', journal.get('id')):>14}  "
              f"({journal.get('issn', 'no-issn')}) ...", flush=True)
        row = fetch_one(journal)
        status = row.get("status", "?")
        count = row.get("article_count", 0)
        print(f"      {status:>6}  {count} items", flush=True)
        if row.get("error"):
            print(f"      err: {row['error']}", flush=True)
        rows.append(row)

    build_iso = datetime.now(timezone.utc).isoformat()
    if args.dry_run:
        print(f"\n[dry-run] would write {len(rows)} feeds to {DOCS_DIR}/")
        return 0

    write_rss_files(rows, site_url=args.site_url, build_iso=build_iso)
    write_dashboard(rows, build_iso=build_iso)
    write_status(rows, build_iso=build_iso)
    print(f"\n✓ wrote {len(rows)} feeds and dashboard to {DOCS_DIR}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
