Comprehensive implementation plan  
(for everything described in `plans/COMPREHENSIVE_IMPLEMENTATION.md`)

────────────────────────────────────────
Cursor rules being applied → 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13
────────────────────────────────────────

PHASE 0 · Foundation
1. Poetry project bootstrap  
   • create `pyproject.toml` (Poetry + Ruff + mypy)  
   • configure `[tool.wdf_pipeline]` block & env-var overrides  
2. Package skeleton `src/wdf/`  
   └── `__init__.py`, `settings.py` (pydantic-settings), `twitter_client.py` (interface & mock impl)  
3. Repo hygiene  
   • delete obsolete `*.bak` & duplicate scripts (rule 12)  
   • move standalone scripts into `src/wdf/tasks/` where applicable  
4. CI scaffold  
   • `.github/workflows/ci.yml` → lint → type-check → test → Docker build → push to GHCR

PHASE 1 · Task code
(One file per bullet lives in `src/wdf/tasks/`; each exposes `run()`)

1. `watch.py`  
   • watchdog on `transcripts/latest.txt` → Prefect flow trigger  
   • retry & structured logging (`structlog`)  
2. `summarise.py`  
   • `subprocess.run(["node", "scripts/gemini_summarise.js", …])`  
   • validate summary/keywords JSON & atomic rename  
3. `scrape.py`  
   • load keywords, pick `TwitterClient` (real/mock) from settings  
   • output deterministic mocks for tests  
4. `fewshot.py`  
   • build Gemma-3n prompt → exact 20 rows  
   • write `fewshots.json`, schema validation  
5. `classify.py` (wraps existing `3n.py`)  
   • add CLI `--fewshots-json` passthrough  
   • on completion write `classified.json` & Prometheus metric  
6. `deepseek.py` (already mostly done)  
   • scan `classified.json` `RELEVANT & no response` → batch prompt  
   • append `"response"` field  
7. `moderation.py`  
   • Rich-based TUI; arrow keys or `[a/e/r]` as spec’d  
   • every decision → `audit.csv`  
8. `publish_twitter` implemented in `twitter_client.py::publish_batch`

PHASE 2 · Prefect orchestration
1. `flow.py`  
   • define `@flow` with seven sequential `task()` calls  
   • parameters: `run_id`, `mock_mode`, model names  
2. Deployment YAML `ops/prefect-deploy.yaml`  
   • pin image digest  
   • workspace = settings.prefect_workspace

PHASE 3 · Observability
1. Add `prometheus_client` counters/timers inside every task (`*_total`, `latency_seconds`)  
2. Emit JSON logs with `structlog` (`logger.bind(task=…)…`)  
3. Provide Grafana dashboard JSON `ops/grafana/wdf.json`

PHASE 4 · Testing
1. Unit tests  
   • settings loader, JSON validators, each `TwitterClient` method  
2. Snapshot tests  
   • golden artefacts (`artefacts/golden/*.json`) checked via `deepdiff`  
3. VCR cassettes  
   • stub Ollama & real-Twitter network I/O  
4. GitHub Actions invokes `pytest -n auto --snapshot-update`

PHASE 5 · Packaging & Runtime
1. `docker-compose.yml`  
   • services: `ollama`, `redis`, `pipeline` (build from Poetry export)  
2. `Makefile` helpers  
   • `make bootstrap`, `make dev-run`, `make test`  
3. Entry-point `main.py` (in repo root or `src/wdf/flow.py __main__`)  
   • pretty logging, stage timing JSON

PHASE 6 · Documentation
1. Expand `README.md` with quick-start, env vars, flow diagram  
2. Keep `docs/` up-to-date; include chat-template reference and API mocks  
3. Inline docstrings + file headers (rule 8/9)

PHASE 7 · Verification & Cleanup
1. End-to-end mock run: `make dev-run` should create all artefacts under `artefacts/<run-id>/` and finish green  
2. Verify tweet char-count limit, response length, and cache hits (rule 10)  
3. Remove any legacy scripts (`gemini_summarize.py`) & unused files (rule 11)  

Deliverables summary
• All Python under `src/wdf/`; Node helpers under `scripts/`  
• Prefect deployment, Dockerfiles, CI workflow  
• Tests pass, `make dev-run` proves pipeline works stand-alone  
• Documentation & Grafana dashboard shipped

This plan touches every requirement in COMPREHENSIVE_IMPLEMENTATION.md and aligns with workspace rules (no hard-coding, verbose logging, etc.).