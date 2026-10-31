# AGENTS.md

## Cursor Cloud specific instructions

This repository is a **pure static website** (plain HTML/CSS/JS) for the "AI Coding 信息平台" portal, plus two **stdlib-only Python 3 data-collection scripts**. There is no build step, no package manager, and no third-party dependencies to install (Python 3.12 ships in the environment).

### Services

- **Static site (the app)** — `index.html` (portal home), `skills.html` (Skill library), `evolution.html` (competitor evolution). The pages use `fetch("./data/*.json")`, so they MUST be served over HTTP; opening files via `file://` will fail to load data. Run a dev server from the repo root, e.g. `python3 -m http.server 8000`, then open `http://localhost:8000/index.html`.
- **Data collectors** (optional, network-dependent) — `python3 scripts/collect_events.py` and `python3 scripts/collect_skills.py` refresh `data/events.json` / `data/skills.json` from public sources. Use `--sources` to list monitored sources and `--dry-run` to preview without writing. These hit external URLs and will silently skip sources when offline; they are NOT required to run or develop the site.

### Lint / test / build

- There is no lint config, no automated test suite, and no build command in this repo. "Build" is just serving the static files.
- To sanity-check changes: serve the site and verify pages load, or validate data files with `python3 -c "import json; json.load(open('data/events.json'))"`.
