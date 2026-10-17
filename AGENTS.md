# AGENTS.md

## Cursor Cloud specific instructions

This repo is a **pure static site** (no build step, no package manager, no dependencies).
It serves three pages — `index.html` (门户首页), `skills.html` (Skill 库), `evolution.html`
(竞品演进) — which `fetch()` JSON from `./data/*.json` at runtime.

### Running (development)

- The pages use relative `fetch()` calls, so they MUST be served over HTTP — opening the
  `.html` files via `file://` will fail to load data. Start a static server from the repo root:
  `python3 -m http.server 8000` then browse to `http://localhost:8000/index.html`.
- No install/build is required; there is nothing to compile and no `node_modules`.

### Data files (`data/`)

- `events.json`, `skills.json`, `competitors.json`, `milestones.json` are committed and are
  what the UI reads. The Python collector scripts only regenerate these.

### Collector scripts (`scripts/`)

- `collect_events.py` and `collect_skills.py` use the Python **standard library only**
  (`urllib`, no third-party packages). Run with `python3 scripts/<name>.py`.
- `--sources` lists monitored sources offline. The default run and `--dry-run` for skills
  perform live network requests to GitHub/RSS/blogs and will print `[WARN]` lines when a
  source is unreachable; this is non-fatal (it just collects fewer/no new items).

### Lint / test / build

- There is no test suite, linter config, or build pipeline. The practical checks are:
  validate the JSON data files (`python3 -m json.tool data/<file>.json`) and syntax-check the
  scripts (`python3 -m py_compile scripts/*.py`).
- CI/deploy is GitHub Pages only (`.github/workflows/deploy-pages.yml` uploads the repo root
  as a static artifact on push to `main`).
