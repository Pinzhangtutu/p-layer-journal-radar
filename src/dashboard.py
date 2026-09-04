"""
Dashboard HTML generator for P-Layer Journal Radar.

Produces `docs/index.html` — a single, self-contained page that lists every
journal in the config, grouped by subfield, with each entry linking to its
per-journal RSS feed. No JS, no external assets; works fully offline.
"""

from __future__ import annotations

import html
from collections import defaultdict
from datetime import datetime
from email.utils import format_datetime
from typing import Any

SUBFIELD_ORDER = [
    "marketing", "management", "ob", "psychology", "sociology",
    "anthropology", "economics", "communication", "is", "education",
]
SUBFIELD_LABELS = {
    "marketing": ("营销学", "Marketing"),
    "management": ("管理学", "Management"),
    "ob": ("组织行为学", "Organizational Behavior"),
    "psychology": ("心理学", "Psychology"),
    "sociology": ("社会学", "Sociology"),
    "anthropology": ("人类学", "Anthropology"),
    "economics": ("经济学", "Economics"),
    "communication": ("传播学", "Communication"),
    "is": ("信息科学", "Information Science"),
    "education": ("教育学", "Education"),
}


def build_dashboard(
    feeds: list[dict[str, Any]],
    build_iso: str,
    lang: str = "zh",
) -> str:
    """Return the full HTML for the dashboard page.

    `feeds` — list of {journal, article_count, status, error?, last_success_iso?}.
    `build_iso` — ISO-8601 timestamp of the latest run; rendered as build time.
    `lang` — 'zh' or 'en'; controls the human-readable labels.
    """
    by_subfield: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in feeds:
        by_subfield[row["journal"].get("subfield", "")].append(row)

    last_build = _human_time(build_iso, lang)
    total_journals = sum(1 for r in feeds if r["journal"].get("enabled", True))
    total_articles = sum(int(r.get("article_count") or 0) for r in feeds)
    failed = sum(1 for r in feeds if r.get("status") == "failed")

    parts: list[str] = []
    parts.append(_doctype())
    parts.append(_head(lang, last_build))
    parts.append(_body_open(lang, total_journals, total_articles, failed, last_build))

    for sub in SUBFIELD_ORDER:
        rows = by_subfield.get(sub)
        if not rows:
            continue
        zh, en = SUBFIELD_LABELS.get(sub, (sub, sub))
        title = zh if lang == "zh" else en
        parts.append(f'<section class="subfield" id="sub-{html.escape(sub)}">\n')
        parts.append(f"  <h2>{html.escape(title)}</h2>\n")
        parts.append('  <ul class="journals">\n')
        # tier 1 first, then tier 2
        for tier in (1, 2):
            for row in rows:
                if row["journal"].get("tier") != tier:
                    continue
                parts.append(_render_row(row, lang))
        parts.append("  </ul>\n")
        parts.append("</section>\n")

    parts.append(_footer(lang))
    parts.append("</body>\n</html>\n")
    return "".join(parts)


def _render_row(row: dict[str, Any], lang: str) -> str:
    j = row["journal"]
    jid = j.get("id", "")
    abbr = html.escape(str(j.get("abbr", "")))
    name = html.escape(str(j.get("name", "")))
    publisher = html.escape(str(j.get("publisher", "")))
    stage = html.escape(str(j.get("stage", "")))
    feed_url = f"./{jid}.xml"
    count = int(row.get("article_count") or 0)
    status = row.get("status", "ok")
    error = row.get("error")
    last = row.get("last_success_iso")

    if status == "failed":
        badge_cls = "badge bad"
        badge_text = "失败" if lang == "zh" else "failed"
    elif count == 0:
        badge_cls = "badge empty"
        badge_text = "无新文" if lang == "zh" else "no items"
    else:
        badge_cls = "badge good"
        badge_text = f"{count} 篇" if lang == "zh" else f"{count} items"

    error_html = ""
    if error and status == "failed":
        error_html = (
            f'\n    <p class="err">⚠ {html.escape(str(error))}</p>'
        )

    last_html = ""
    if last:
        last_html = (
            f' <span class="last">· {html.escape(_human_time(last, lang))}</span>'
        )

    return (
        f'    <li class="journal" id="{html.escape(jid)}">\n'
        f'      <a class="feed" href="{html.escape(feed_url)}" '
        f'type="application/rss+xml">RSS</a>\n'
        f'      <b class="abbr">{abbr}</b>\n'
        f'      <span class="name">{name}</span>\n'
        f'      <span class="meta">{publisher} · {stage}</span>'
        f'{last_html}\n'
        f'      <span class="{badge_cls}">{badge_text}</span>'
        f'{error_html}\n'
        f'    </li>\n'
    )


def _doctype() -> str:
    return "<!doctype html>\n"


def _head(lang: str, last_build: str) -> str:
    title = "期刊雷达 · P-Layer" if lang == "zh" else "Journal Radar · P-Layer"
    return (
        f'<html lang="{html.escape(lang)}">\n'
        "<head>\n"
        "  <meta charset=\"utf-8\">\n"
        "  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n"
        f"  <title>{html.escape(title)}</title>\n"
        "  <style>\n"
        + _CSS() +
        "  </style>\n"
        "</head>\n"
    )


def _body_open(lang: str, total_journals: int, total_articles: int,
               failed: int, last_build: str) -> str:
    if lang == "zh":
        sub = "订阅任意期刊的 RSS feed，新文自动进入收件箱。"
    else:
        sub = "Subscribe to any journal's RSS feed; new articles land in your inbox."
    summary = (
        f"{total_journals} 本期刊 · {total_articles} 篇新文"
        if lang == "zh"
        else f"{total_journals} journals · {total_articles} new items"
    )
    failed_line = ""
    if failed:
        msg = (
            f"⚠ {failed} 本期刊抓取失败，详见下方徽标。"
            if lang == "zh"
            else f"⚠ {failed} journal(s) failed this run; see badges below."
        )
        failed_line = f'  <p class="failed-line">{html.escape(msg)}</p>\n'

    return (
        "<body>\n"
        f"  <header>\n"
        f"    <h1>📡 {html.escape('期刊雷达' if lang == 'zh' else 'Journal Radar')}</h1>\n"
        f"    <p class=\"sub\">{html.escape(sub)}</p>\n"
        f"    <p class=\"summary\">{html.escape(summary)} · "
        f"最近更新 {html.escape(last_build)}</p>\n"
        f"{failed_line}"
        f"  </header>\n"
        "  <main>\n"
    )


def _footer(lang: str) -> str:
    return (
        "  </main>\n"
        "  <footer>\n"
        f"    <p>{html.escape('由 P-Layer Journal Radar 自动生成 · 数据来自 Crossref 与各刊官网' if lang == 'zh' else 'Generated by P-Layer Journal Radar · Data from Crossref and publisher RSS')}</p>\n"
        "  </footer>\n"
    )


def _human_time(iso: str, lang: str) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso
    # For human display, show local-style formatted timestamp.
    return format_datetime(dt, usegmt=False)


def _CSS() -> str:
    return """
    :root {
      --bg: #f7f6f1;
      --card: #ffffff;
      --ink: #1f2933;
      --muted: #5b6470;
      --line: #e2e0d6;
      --accent: #1a4f6b;
      --good: #1a7a4e;
      --bad: #a23a3a;
      --empty: #b8c4d0;
    }
    body { font: 14px/1.6 -apple-system, "Segoe UI", "PingFang SC", system-ui, sans-serif;
           background: var(--bg); color: var(--ink); margin: 0; padding: 32px 24px; }
    header { max-width: 980px; margin: 0 auto 24px; }
    header h1 { margin: 0 0 6px; font-size: 28px; }
    header .sub { margin: 0 0 8px; color: var(--muted); font-size: 13px; }
    header .summary { margin: 0; color: var(--muted); font-size: 12px; }
    header .failed-line { margin: 8px 0 0; color: var(--bad); font-size: 12px; }
    main { max-width: 980px; margin: 0 auto; display: grid; gap: 22px; }
    .subfield { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 16px 20px; }
    .subfield h2 { margin: 0 0 12px; font-size: 16px; color: var(--accent); letter-spacing: .02em; }
    ul.journals { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
    li.journal { display: grid; grid-template-columns: 56px 60px 1fr auto; align-items: center; gap: 10px;
                 padding: 6px 4px; border-bottom: 1px dashed var(--line); }
    li.journal:last-child { border-bottom: none; }
    .feed { font-size: 10.5px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase;
            color: #fff; background: #d97706; padding: 2px 6px; border-radius: 4px; text-decoration: none;
            text-align: center; }
    .feed:hover { background: #b35d04; }
    .abbr { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 11px; font-weight: 700;
            color: var(--accent); background: rgba(26,79,107,.08); padding: 1px 5px; border-radius: 4px; text-align: center; }
    .name { font-weight: 600; }
    .meta { grid-column: 1 / span 4; color: var(--muted); font-size: 11.5px; margin-top: -2px; }
    .last { color: var(--muted); font-size: 11px; }
    .badge { font-size: 10.5px; font-weight: 700; letter-spacing: .04em; padding: 2px 7px; border-radius: 999px;
             margin-left: 6px; white-space: nowrap; }
    .badge.good { background: rgba(20,150,80,.15); color: var(--good); }
    .badge.bad { background: rgba(204,60,60,.15); color: var(--bad); }
    .badge.empty { background: rgba(0,0,0,.05); color: var(--muted); }
    .err { grid-column: 1 / span 4; color: var(--bad); font-size: 11.5px; margin: 4px 0 0; }
    footer { max-width: 980px; margin: 32px auto 0; color: var(--muted); font-size: 11.5px; text-align: center; }
    """
