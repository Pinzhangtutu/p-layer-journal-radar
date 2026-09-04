# P-Layer Journal Radar

A self-hosted, no-third-party-Code "literature radar" that watches a curated
list of social-science journals and republishes their latest articles as
clean RSS 2.0 feeds on GitHub Pages.

- **Covers** ~80 journals across 10 subfields (Marketing, Management, OB,
  Psychology, Sociology, Anthropology, Economics, Communication, Information
  Science, Education) — see `config/journals.yaml`.
- **Source** is primarily [Crossref](https://www.crossref.org/), the
  publisher-supplied DOI registration agency. Crossref entries are usually
  richer and arrive sooner than publisher-direct RSS, and we strip the noise
  (errata, editorials, call-for-papers) that often pollutes publisher feeds.
- **Output** is one RSS 2.0 XML per journal in `docs/`, plus a single
  `docs/index.html` dashboard listing every feed.
- **Refresh cadence** is every 6 hours via GitHub Actions cron, plus a
  manual `workflow_dispatch` trigger for ad-hoc runs.

The whole thing is **< 500 lines of Python** with only `requests`, `pyyaml`,
and `python-dateutil` as dependencies. The XML output is hand-rolled, so
we don't depend on a feed-builder library and the feeds are byte-stable.

## How it works

```
┌──────────────────────┐    ┌───────────────────────┐    ┌────────────────────┐
│ GitHub Actions cron  │ →  │ scripts/fetch.py      │ →  │ docs/{id}.xml      │
│ every 6h + manual    │    │   ├ crossref.py       │    │ docs/index.html    │
└──────────────────────┘    │   ├ cleaner.py        │    │ docs/status.json   │
                           │   ├ rss_builder.py    │    └─────────┬──────────┘
                           │   └ dashboard.py      │              │
                           └───────────────────────┘              │
                                                                   ▼
                                                      ┌────────────────────────┐
                                                      │  GitHub Pages (public) │
                                                      │  /journal-radar/{id}.xml
                                                      └────────────────────────┘
```

## Setup

### 1. Create a new GitHub repo

Create an empty repository named `journal-radar` under your GitHub account
(or any name you like; the path is what ends up in the public URL). Push
this directory's contents to it.

```bash
cd /Users/pinzhangwang/P-Layer/apps/p-layer-journal-radar
git init
git add .
git commit -m "init: p-layer journal radar"
git branch -M main
git remote add origin git@github.com:<your-username>/journal-radar.git
git push -u origin main
```

### 2. Configure GitHub Pages

In the repo settings → **Pages**:
- Source: **Deploy from a branch**
- Branch: `main`, folder: `/docs`

Once the first workflow run completes, the dashboard will be live at:

    https://<your-username>.github.io/journal-radar/

and per-journal feeds at:

    https://<your-username>.github.io/journal-radar/jcr.xml
    https://<your-username>.github.io/journal-radar/jams.xml
    ...

### 3. (Optional) Set the public site URL

The feeds contain an `<atom:link rel="self">` and a `<link>` to the
dashboard. To make those point at your real GitHub Pages URL, set a
repository variable:

- Repo → Settings → Secrets and variables → Actions → **Variables** tab
- New variable: `PIA_RADAR_SITE_URL` = `https://<your-username>.github.io/journal-radar`

### 4. (Optional) Crossref polite pool

If you set a `PIA_CONTACT_EMAIL` repository secret, the script will send it
to Crossref as `?mailto=...`, which puts you in the polite pool (faster,
higher rate limits). Totally optional — the script works fine without it.

### 5. Plug into P-Layer

In the P-Layer app, the literature radar reads feeds from the
`pLayerRadarBaseUrl` localStorage key (default
`https://<your-username>.github.io/journal-radar`). Set it on the
Literature page (or via DevTools) and the radar will subscribe to every
feed in `docs/`.

## Editing the journal list

Add, remove, or disable journals in `config/journals.yaml`. Each entry is:

```yaml
- id: jcr          # lowercase, used as filename: docs/jcr.xml
  abbr: JCR
  name: Journal of Consumer Research
  subfield: marketing   # one of: marketing, management, ob, psychology, ...
  tier: 1               # 1 = top flagship, 2 = next-tier
  issn: 0093-5301       # any ISSN registered with Crossref (print or e-)
  publisher: Oxford University Press
  stage: "Advance / Accepted"
  publisher_rss: ""     # optional, leave empty for Crossref-only
  enabled: true         # set false to skip without deleting
```

After editing, either wait for the next cron run, or trigger it manually:
**Actions → Update journal radar → Run workflow**.

## Local development

```bash
# 1. Install deps
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Dry run
python scripts/fetch.py --dry-run

# 3. Real run, write to docs/
python scripts/fetch.py --site-url http://localhost:8000

# 4. Preview
cd docs && python -m http.server 8000
# Open http://localhost:8000
```

## File map

```
.
├── .github/workflows/update-rss.yml   # cron + manual trigger
├── config/journals.yaml                # the journal list (single source of truth)
├── docs/                                # generated output (committed to repo)
│   ├── index.html                       # dashboard
│   ├── {id}.xml                         # one RSS feed per journal
│   └── status.json                      # machine-readable run report
├── requirements.txt
├── scripts/
│   └── fetch.py                         # orchestrator
└── src/
    ├── crossref.py                      # Crossref REST client
    ├── cleaner.py                       # filter errata, clean JATS, format dates
    ├── rss_builder.py                   # RSS 2.0 XML generator
    └── dashboard.py                     # static HTML dashboard
```

## Why a separate repo

The radar publishes public feeds, so it makes sense as its own GitHub repo
with its own Pages site. The P-Layer app (which lives at
`apps/p-layer-dev/web/`) just consumes the feeds over HTTPS — no shared
build, no coupling, no third-party code.

## License

Use however you like.
