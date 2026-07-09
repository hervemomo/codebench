# Handoff

**Sequence in progress:** 0 — Repository Scaffold & Isolated Environment
**Branch:** `seq/0-scaffold` (cut from `develop`)

## Last done
- Monorepo layout created: `backend/`, `frontend/`, `docker/`, `.github/workflows/`, `scripts/`, `Makefile`.
- `docker/backend.Dockerfile`, `docker/frontend.Dockerfile`, `docker-compose.yml` (`api`, `worker`, `db`=postgres:16, `redis`=redis:7, `web`) — `minio` is deferred to Sequence 2 per the Playbook.
- `backend/app/main.py` with `GET /healthz` → `{"status":"ok","version":...}`; `backend/app/config.py` (pydantic-settings; missing `OPENAI_API_KEY` only raises when an LLM call is attempted, not at import).
- Tests: `backend/tests/test_healthz.py`, `backend/tests/test_env.py`.
- `backend/requirements.lock` and `frontend/package-lock.json` generated inside throwaway containers (`python:3.11-slim`, `node:20-slim`) — nothing installed on the host.
- `.env.example` committed; `.env` gitignored.
- `scripts/ci_setup.sh` and `.github/workflows/ci.yml` (runs on PR to `develop` and push to `develop`: `ci_setup.sh` then `make ci`).
- Committed the pre-existing `docs/source/` files (`PLAYBOOK.md`, `original_notebook.ipynb`, `codebench-prototype.jsx`) that had never been added to git.

## Next action
- Run Sequence 0's Section 7 command block end-to-end (`bash scripts/ci_setup.sh`, `make up`, `make test-backend`, `curl /healthz`, `make down`), fix anything red, then commit/push `seq/0-scaffold` and open a PR into `develop`.
- Once CI is green on GitHub and the PR is merged, tag `seq-0` on `develop` and start **Sequence 1 — Extract the Notebook into a Tested Python Package**.
