# AGENTS.md

## Cursor Cloud specific instructions

### What this is
A pure static front-end MVP ("AI Coding 信息平台") plus a stdlib-only Python data-collection script. There is no build step and no third-party dependencies.

- Front-end: `index.html` (+ `styles.css`, `app.js`) and `evolution.html` (+ `evolution.css`, `evolution.js`).
- Data: JSON files in `data/` (`events.json`, `competitors.json`, `milestones.json`), loaded at runtime via `fetch`.
- Collector: `scripts/collect_events.py` (Python 3, standard library only — uses `urllib`, no `requests`).

### Running (dev)
The pages load `data/*.json` via `fetch`, so they must be served over HTTP — opening files via `file://` will fail with CORS errors. Serve from the repo root:

```bash
python3 -m http.server 8000
```

Then open `http://localhost:8000/index.html` (main feed) and `http://localhost:8000/evolution.html` (competitor history).

### Data collector
Network-dependent (hits external sites/APIs). Useful subcommands:

```bash
python3 scripts/collect_events.py --sources   # list monitored sources (offline-safe)
python3 scripts/collect_events.py --dry-run   # preview, no file writes (needs network)
python3 scripts/collect_events.py             # fetch + merge into data/events.json (needs network)
```

External fetches may fail/timeout in restricted networks; the script warns and continues, so a partial/empty result is expected without network access.

### Lint / test / build
There is no lint config, no automated test suite, and no build/bundler in this repo. "Build" for deploy is just publishing the static files (see `.github/workflows/deploy-pages.yml`).
