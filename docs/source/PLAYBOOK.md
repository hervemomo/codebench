# CodeBench — Claude Code Implementation Playbook
### Fully automated, CI/CD-compatible sequences for converting `original_notebook.ipynb` into the CodeBench web application (per `codebench-prototype.jsx`)

**How to use:** Feed each "Sequence" block to Claude Code as a prompt, in order. Every sequence is self-contained, runs in Docker (no host dependencies), and ends with a green CI gate before the next sequence starts. Target repo layout is a monorepo:

```
codebench/
├── backend/          # FastAPI + extracted notebook package
├── frontend/         # React (Vite) app grown from the prototype
├── docker/           # Dockerfiles + compose
├── .github/workflows/ci.yml
└── Makefile
```

## Per-sequence operating procedure (the run → fix → green loop)

Follow this exact procedure for **every** sequence N:

1. **Start clean.** `git checkout develop && git pull`, then `git checkout -b seq/N-<name> develop`.
2. **Prompt Claude Code** with the full text of Sequence N (plus this file, the notebook, and the prototype in the repo). Claude Code implements sections 2–5 (environment, code, tests).
3. **Verify — run Sequence N's "7. Run & Test Commands" block.** Preferred: tell Claude Code *"Now run the Section 7 command block yourself. If anything fails, fix it and re-run until everything passes, then show me the final passing output."* Claude Code executes the commands and sees the output directly. Fallback (commands run in a terminal Claude Code doesn't control, e.g. a CI runner): copy the failing output — the full traceback or failed-test lines — and paste it back into the session as your next message.
4. **Loop until green.** "Green" = every command in the block exits 0 and matches that sequence's Success Criteria (e.g. `31 passed`, coverage ≥85%, demo completes). "Red" = any failure (`FAILED test_x.py::...`, `ModuleNotFoundError`, non-zero exit). On red: Claude Code fixes → re-run step 3. Never proceed on red, and never let Claude Code "fix" a failure by deleting or skipping the test — the fix must satisfy the original assertion or come with a justified test correction.
5. **Commit & merge.** Run Sequence N's git block (commit with the given message, push, PR → `develop`, merge when the CI pipeline is also green, tag `seq-N` on develop).
6. **Only then start Sequence N+1** (back to step 1). This gating exists because each sequence builds on the previous one — a red Sequence 3 carried forward means debugging two layers at once inside Sequence 4.

Rule of thumb: local green (step 4) and CI green (step 5) must **both** hold; if CI fails where local passed, treat the CI log exactly like step 3's failure output and paste it into the session.

---

Global conventions used by all sequences:
- Python 3.11, Node 20. All commands run **inside containers** via `docker compose run`.
- Test frameworks: `pytest` (+ `pytest-asyncio`, `httpx`) backend; `vitest` + `@testing-library/react` frontend; `playwright` for E2E.
- Every LLM call is mocked in tests via a `FakeOpenAI` client fixture — CI never needs an API key.
- Success gate for every sequence: `make ci` exits 0.

---

## Sequence 0 — Repository Scaffold & Isolated Environment

**1. Goal**
Create the monorepo, Docker-based dev environment, Makefile entry points, and a CI pipeline skeleton that runs on every push. Nothing installs on the host.

**2. Isolated Environment Setup**

`docker/backend.Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY backend/pyproject.toml backend/requirements.lock ./
RUN pip install -r requirements.lock
COPY backend/ .
```

`docker/frontend.Dockerfile`:
```dockerfile
FROM node:20-slim
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
```

`docker-compose.yml` (services: `api`, `worker`, `db` = postgres:16, `redis` = redis:7, `web`). All volumes are named volumes; no bind mounts to system paths.

Initial dependency list (backend `pyproject.toml`): fastapi, uvicorn, pydantic-settings, sqlalchemy, alembic, psycopg[binary], redis, rq, pandas, openpyxl, numpy, scikit-learn, umap-learn, hdbscan, openai, python-multipart, pytest, pytest-asyncio, httpx, factory-boy.

CI-compatible setup script `scripts/ci_setup.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
docker compose build --pull
docker compose up -d db redis
docker compose run --rm api python -c "import fastapi, pandas, sklearn; print('deps OK')"
```

**3. Implementation Instructions**
1. `git init`, create the tree above, add `.gitignore`, `.dockerignore`, `.env.example` (`OPENAI_API_KEY=`, `DATABASE_URL=postgresql+psycopg://cb:cb@db:5432/cb`, `REDIS_URL=redis://redis:6379/0`).
2. `backend/app/main.py` with a `/healthz` endpoint returning `{"status":"ok","version":...}`.
3. `Makefile` targets: `build`, `up`, `down`, `test-backend`, `test-frontend`, `lint`, `ci` (= build + lint + all tests).
4. `.github/workflows/ci.yml`: checkout → `bash scripts/ci_setup.sh` → `make ci`. (GitLab/Azure equivalents: run the same two commands; everything is docker-encapsulated so the runner only needs Docker.)

**4. Automated Testing**
- File: `backend/tests/test_healthz.py` — `httpx` async client asserts `GET /healthz` → 200, body contains `status: ok`.
- File: `backend/tests/test_env.py` — asserts settings load from env vars, missing `OPENAI_API_KEY` raises a clear error only when an LLM call is attempted (not at import).
- CI command: `docker compose run --rm api pytest -q` → expected output: `2 passed`.

**5. Manual Testing**
```bash
make build && make up
curl -s localhost:8000/healthz
```
Expected: JSON `{"status":"ok",...}`; `docker compose ps` shows api/db/redis healthy. Verify isolation: `pip list` on the host is unchanged.

**6. Success Criteria**
- CI workflow green on push; `/healthz` 200 in container; zero host-level installs; lockfiles committed (deterministic builds).

**7. Run & Test Commands**
```bash
bash scripts/ci_setup.sh
make up
make test-backend
curl -s localhost:8000/healthz
make down
```

---

## Sequence 1 — Extract the Notebook into a Tested Python Package

**1. Goal**
Convert every notebook section into importable, config-driven modules under `backend/codeframe/`, removing all globals, hard-coded filenames, and notebook-only behavior. This is the foundation every later sequence calls.

**2. Isolated Environment Setup**
Reuses Sequence 0 containers. Add to lockfile: `langdetect` (or whatever the notebook uses), `tenacity`. Rebuild: `docker compose build api`.

**3. Implementation Instructions**
Create `backend/codeframe/` with this mapping from the notebook:

| Module | Notebook source | Key contents |
|---|---|---|
| `config.py` | 0-B, 0-D | `ProjectConfig`, `PreprocessConfig`, `ClusterConfig`, `CodingConfig` Pydantic models (fields: survey question/context, language codes, `coding_batch_size`, `translation_batch_size`, UMAP/HDBSCAN params, token caps, `default_min_words`, `empty_responses`, model names) |
| `llm.py` | 0-E | `chat_with_retry(client, ...)` with timeout/retry from config; token-usage accounting returned per call; `LLMClient` protocol so tests inject `FakeOpenAI` |
| `preprocessing.py` | 1-A/1-B | `load_survey_data(path, sheet, col)`, `preprocess(df, cfg) -> PreprocessResult` returning kept rows + invalid + duplicate frames (no file writes) |
| `translation.py` | 1-A | `translate_records(df, cfg, client)` batched |
| `clustering.py` | 2-A | `embed(texts, cfg, client)`, `discover_themes(embeddings, cfg) -> ClusterResult` with representatives |
| `codebook.py` | 0-E, 2-B, 3-B | `Codebook`/`Code` dataclasses, `generate_codebook(...)` (with truncation retry + code cap), `load_user_codebook(source, ...)`, `enrich_with_ai(...)`, `to_compact_prompt()` |
| `coding.py` | 2-B | `apply_codes(df, codebook, cfg, client, progress_cb=None)` — emits `(batch_i, n_batches)` via callback |
| `refine.py` | 4-B, 5-B | `split_code(...)`, `merge_codes(...)` returning new (df, codebook) pairs — pure functions, no mutation |
| `reporting.py` | 0-F | `frequency_table(df, codebook)`, `cooccurrence_matrix(...)` returning DataFrames; `export_workbook(...)`, `export_charts(...)` write to a caller-supplied path |
| `state.py` | 0-G | `PipelineState(df, codebook, meta)` + `serialize/deserialize` (parquet + JSON), path-agnostic |

Rules Claude Code must enforce: no `globals()`, no module-level side effects, every function takes explicit config, all randomness seeded via `cfg.random_seed` (UMAP/HDBSCAN) for determinism.

**4. Automated Testing**
- `tests/fixtures/fake_openai.py` — deterministic fake returning canned codebook JSON / coding JSON / translations.
- `tests/data/tiny_survey.xlsx` — 30 synthetic responses (committed).
- Test files & cases:
  - `test_preprocessing.py`: drops empty/`EMPTY_RESPONSES` values, min-word filter, duplicate detection; invalid+duplicate frames have expected row counts.
  - `test_codebook.py`: generation parses fake JSON, respects `target_codes_cap`, truncation retry path triggers on oversized fake response; user codebook loads from xlsx/csv/json/list; catch-all "Other" code always present.
  - `test_coding.py`: every kept row gets ≥1 code; batching math correct; progress callback called `ceil(n/batch)` times; reasoning saved only when configured.
  - `test_refine.py`: split reassigns parent rows to subcodes, preserves parent when configured; merge unions assignments and removes originals; both are non-mutating.
  - `test_reporting.py`: frequency totals equal assignment counts; workbook has 5 sheets; PNGs created.
  - `test_state.py`: round-trip serialize/deserialize is lossless.
- CI: `docker compose run --rm api pytest -q --cov=codeframe --cov-fail-under=85`. Expected: `~30 passed`, coverage ≥85%.

**5. Manual Testing**
```bash
docker compose run --rm api python -m codeframe.demo tests/data/tiny_survey.xlsx --fake-llm
```
(`demo.py` runs the whole pipeline with the fake client.) Expected log: rows loaded → kept/removed counts → 3–6 codes generated → coding batches → workbook written to `/tmp/out/`. Open the workbook via `docker cp` and verify the 5 sheets.

**6. Success Criteria**
- All notebook capabilities reachable through package functions; pytest green with ≥85% coverage; demo pipeline completes end-to-end with the fake LLM; running the demo twice yields identical cluster labels (determinism).

**7. Run & Test Commands**
```bash
docker compose build api
docker compose run --rm api pytest -q --cov=codeframe --cov-fail-under=85
docker compose run --rm api python -m codeframe.demo tests/data/tiny_survey.xlsx --fake-llm
```

---

## Sequence 2 — Data Model, Migrations & Object Storage

**1. Goal**
Persist projects, questions, datasets, runs, codebooks, and per-response code assignments in Postgres; store uploaded/exported files in S3-compatible storage (MinIO in dev/CI).

**2. Isolated Environment Setup**
Add `minio` service to compose; backend deps: `boto3`, `alembic`. `scripts/ci_setup.sh` gains `docker compose up -d minio` and bucket creation via `mc`.

**3. Implementation Instructions**
- SQLAlchemy models in `backend/app/models/`: `Organization`, `User(email, password_hash, org_id, role)`, `Project(context, source_lang, target_lang, codebook_lang)`, `Question(text, survey_col)`, `Dataset(file_key, sheet, status)`, `Response(raw_text, clean_text, translated_text, is_valid, invalid_reason)`, `CodingRun(kind: s2|s3|split|merge, parent_run_id, status, config_json, codebook_json, token_usage)`, `CodeAssignment(response_id, run_id, code_id, confidence, reasoning)`, `ExportArtifact(run_id, kind, file_key)`.
- **Multi-tenancy from day one:** every tenant table carries a non-nullable, indexed `org_id` FK (yes, even `Response` and `CodeAssignment`), and `User` carries `role` (enum: `admin|analyst`; only `analyst` used initially). The columns cost nothing now; retrofitting them later means rewriting every query and migration.
- **Mandatory org-scoping rule:** create `app/db/scoped.py` with a `scoped_query(session, Model, org_id)` helper / repository base class. Direct queries on tenant tables are forbidden by convention **and** by CI: `scripts/check_org_scoping.sh` greps for `select(`/`session.query(` against tenant models outside the repository layer and fails the build. No endpoint may ever trust a client-supplied `org_id` — it always comes from the authenticated session (Sequence 3).
- `parent_run_id` chains give the checkpoint lineage (replaces notebook 0-G pickles).
- Alembic migration `0001_initial`; `app/storage.py` wrapper (put/get/presign) pointing at MinIO locally and S3 in prod via env.

**4. Automated Testing**
- `test_models.py`: create full object graph with factory-boy; cascade rules; unique constraints.
- `test_migrations.py`: `alembic upgrade head` then `alembic downgrade base` on a fresh DB succeeds.
- `test_storage.py`: put/get/presign round-trip against MinIO.
- `test_lineage.py`: run chain s2 → split → merge; walking `parent_run_id` reconstructs history.
- `test_tenancy.py`: create objects under two orgs; `scoped_query` for org A never returns org B rows at any level (project → response → assignment); inserting a tenant row without `org_id` raises IntegrityError.
- CI additionally runs `bash scripts/check_org_scoping.sh` (fails on any unscoped tenant query) → `~15 passed + scoping check OK`.

**5. Manual Testing**
```bash
docker compose run --rm api alembic upgrade head
docker compose run --rm api python -m app.seed   # seeds demo org/project/question
docker compose exec db psql -U cb -c "\dt"
```
Expected: all tables listed; MinIO console (localhost:9001) shows the `codebench` bucket.

**6. Success Criteria**
- Migrations idempotent up/down; seed script populates a browsable project; assignments stored long-format (one row per response-code pair); CI green.

**7. Run & Test Commands**
```bash
docker compose up -d db redis minio
docker compose run --rm api alembic upgrade head
docker compose run --rm api pytest tests/db -q
docker compose run --rm api python -m app.seed
```

---

## Sequence 3 — API Layer + Async Job Runner (Upload → Preprocess vertical slice)

**1. Goal**
Expose the first working vertical slice over HTTP: project/question CRUD, file upload with preview, preprocessing as a background job with live progress, and preprocessing stats for the UI (replacing `removed_records.xlsx`).

**2. Isolated Environment Setup**
Compose `worker` service: `command: rq worker --url $REDIS_URL codebench`. No new host requirements.

**3. Implementation Instructions**
- **Real authentication (before any business endpoint):** `POST /api/auth/register` (dev/admin only), `POST /api/auth/login` (argon2/bcrypt password check → signed, HTTP-only session cookie via `itsdangerous`/`fastapi-users`, or a JWT with short expiry + refresh), `POST /api/auth/logout`, `GET /api/auth/me`. No email-lookup simulation — real credentials from day one so a pilot research team can have actual accounts. A `get_current_user` dependency resolves the session and injects `(user, org_id)`; **every** router below depends on it, and all data access goes through the Sequence-2 `scoped_query` layer using that server-side `org_id` — request bodies and query params never carry org identifiers. Frontend (Sequence 6) gets a login page and 401→redirect handling.
- Routers: `POST/GET /api/projects`, `POST /api/projects/{id}/questions`, `PUT /api/projects/{id}/context`.
- `POST /api/questions/{id}/datasets` (multipart) → store file in MinIO, parse header + first 10 rows, return column list + preview (feeds the prototype's `PreviewTable` and column picker).
- `POST /api/datasets/{id}/preprocess` → enqueue RQ job calling `codeframe.preprocessing` + `translation`; job writes `Response` rows and updates `Dataset.status`.
- Progress: job writes `{stage, current, total}` to Redis key `progress:{job_id}`; `GET /api/jobs/{id}` returns it; `GET /api/jobs/{id}/stream` exposes SSE.
- `GET /api/datasets/{id}/stats` → kept/invalid/duplicate counts, invalid reasons breakdown, sample removed rows.

**4. Automated Testing**
- `test_auth.py`: login with wrong password → 401; session cookie is HTTP-only + signed; `GET /api/auth/me` reflects logged-in user; all business endpoints return 401 without a session.
- `test_cross_org.py`: user from org A requests org B's project/dataset/run IDs directly → 404 (not 403 — don't leak existence); uploaded files from org B are unreachable via org A presigned flows.
- `test_api_projects.py`: CRUD happy paths + validation errors (422).
- `test_upload.py`: upload `tiny_survey.xlsx` → 201, preview has 10 rows, file exists in MinIO.
- `test_preprocess_job.py`: run RQ job synchronously (`is_async=False`) with fake LLM; asserts Response rows created, stats endpoint matches Sequence-1 package results exactly.
- `test_sse.py`: progress stream emits monotonically increasing `current`.
- CI: `docker compose run --rm api pytest tests/api -q` → `~14 passed`.

**5. Manual Testing**
```bash
make up
curl -F "file=@backend/tests/data/tiny_survey.xlsx" localhost:8000/api/questions/1/datasets
curl -X POST localhost:8000/api/datasets/1/preprocess
curl localhost:8000/api/jobs/<job_id>          # poll until status=finished
curl localhost:8000/api/datasets/1/stats
```
Expected: stats show kept=~25, invalid+duplicates=~5 for the fixture; worker logs show batch progress.

**6. Success Criteria**
- Upload→preprocess→stats works end-to-end via HTTP only; job survives worker restart (idempotent re-run); OpenAPI docs at `/docs` render all endpoints; CI green.

**7. Run & Test Commands**
```bash
docker compose up -d
docker compose run --rm api pytest tests/api -q
# manual slice
curl -F "file=@backend/tests/data/tiny_survey.xlsx" localhost:8000/api/questions/1/datasets
```

---

## Sequence 4 — Codebook Generation, Review Workflow & Coding Jobs

**1. Goal**
Implement the Code stage: AI codebook generation (notebook S2), user codebook import (S3), the human-in-the-loop review state from the prototype (accept/reject/edit codes before application), and the batch coding job with progress.

**2. Isolated Environment Setup**
No new services. Add `DRAFT → REVIEWED → APPLIED` run-status enum migration (`alembic revision`).

**3. Implementation Instructions**
- `POST /api/questions/{id}/runs` body `{kind: "ai"|"import", cluster_overrides?, codebook_source?}`:
  - `ai`: job = embed → cluster → `generate_codebook` → save run in `DRAFT` with `codebook_json` marked per-code `status: proposed`.
  - `import`: parse xlsx/csv/json/list via `load_user_codebook`, optional `enrich=true` job.
- Review endpoints: `PATCH /api/runs/{id}/codes/{code_id}` (accept/reject/edit name+definition), `POST /api/runs/{id}/codes` (manual add), `POST /api/runs/{id}/finalize` → rejects run if any code still `proposed`; guarantees catch-all code exists.
- `POST /api/runs/{id}/apply` → coding job using only accepted codes; writes `CodeAssignment` rows; stores token usage on the run.
- `GET /api/runs/{id}/qa` → uncoded rate, catch-all rate, multi-label histogram, low-confidence samples, near-zero-frequency codes, top co-occurring pairs (feeds QA Review page).

**4. Automated Testing**
- `test_codebook_ai.py`: fake-LLM generation produces DRAFT run; codes proposed; cap respected.
- `test_codebook_import.py`: each source format; missing-ID auto-generation; catch-all injection.
- `test_review.py`: cannot finalize with pending codes (409); cannot apply unfinalized run (409); edits persist.
- `test_apply_job.py`: after apply, `count(distinct response_id in assignments) == kept responses`; rejected codes never assigned; progress events count matches batches.
- `test_qa.py`: metrics computed correctly on a hand-built fixture (known catch-all rate = 2/25 etc.).
- CI: `pytest tests/coding -q` → `~16 passed`.

**5. Manual Testing**
Run the flow with a real key once (optional, outside CI): set `OPENAI_API_KEY` in `.env`, repeat the curl flow with `kind=ai`, inspect `/api/runs/1/qa`. Otherwise run with `FAKE_LLM=1` env flag. Expected: DRAFT codebook visible, finalize blocked until all codes reviewed, apply completes, QA payload non-empty.

**6. Success Criteria**
- Review gate enforced by API (not just UI); assignments reproducible with fake LLM; token usage recorded; QA metrics match fixture math; CI green with **no** external API calls.

**7. Run & Test Commands**
```bash
docker compose run --rm api alembic upgrade head
docker compose run --rm api pytest tests/coding -q
FAKE_LLM=1 docker compose up -d && bash scripts/manual_coding_flow.sh
```

---

## Sequence 5 — Refinement (Split/Merge), Checkpoints & Exports

**1. Goal**
Implement the Refinement stage (notebook S4/S5) as new child runs with proposal→review→apply flow, run-lineage reset (notebook 0-G), and the Results exports (Excel workbook, CSVs, chart PNGs — notebook 0-F).

**2. Isolated Environment Setup**
Backend dep: `matplotlib` (headless, `MPLBACKEND=Agg` in Dockerfile).

**3. Implementation Instructions**
- `POST /api/runs/{id}/split` `{parent_code_id, subcodes?, n_proposed?}` → if subcodes omitted, job proposes them (DRAFT child run); review + apply reuse Sequence-4 machinery; multi-config splits create one child run each.
- `POST /api/runs/{id}/merge` `{code_ids, merged_name?, merged_id?}` — same pattern.
- `POST /api/questions/{id}/reset?to_run={run_id}` → sets active run pointer back along lineage (nothing deleted).
- Results/exports: `GET /api/runs/{id}/results/frequencies|cooccurrence|codebook`, `GET /api/runs/{id}/responses?search=&code=&page=` (paginated), `POST /api/runs/{id}/exports?format=xlsx|csv_frequencies|csv_coded|png_frequencies|png_cooccurrence` → job writes artifact to MinIO, `GET /api/exports/{id}` returns presigned URL.

**4. Automated Testing**
- `test_split.py`: parent rows fully redistributed; `preserve_parent` honored; lineage `parent_run_id` correct.
- `test_merge.py`: merged frequency = union (not sum) of member assignments; originals removed from child codebook.
- `test_reset.py`: reset to `s2` then re-split produces branch; original branch intact.
- `test_exports.py`: workbook has 5 sheets with expected row counts; PNGs are valid images (>1KB, correct magic bytes); presigned URL fetch returns 200.
- `test_results_api.py`: pagination/search/filter math on 200-row fixture.
- CI: `pytest tests/refine tests/exports -q` → `~15 passed`.

**5. Manual Testing**
Run split → inspect proposal → accept → apply → download workbook via presigned URL; open in Excel/LibreOffice and check the *Données codées* sheet shows subcodes. Then `reset?to_run=<s2>` and confirm frequencies revert.

**6. Success Criteria**
- Full notebook parity: everything the notebook could produce (workbook, both PNGs, coded CSV, codebook JSON) is downloadable through the API; lineage/reset works; CI green.

**7. Run & Test Commands**
```bash
docker compose run --rm api pytest tests/refine tests/exports -q
bash scripts/manual_refine_flow.sh   # scripted curl walkthrough
```

---

## Sequence 6 — Frontend: Prototype → Real Application

**1. Goal**
Convert `codebench-prototype.jsx` into a production React app wired to the API: routing, React Query data layer, live job progress, review interactions, charts, and export buttons.

**2. Isolated Environment Setup**
`docker/frontend.Dockerfile` (Sequence 0). Deps: react, react-dom, react-router-dom, @tanstack/react-query, recharts, lucide-react, vitest, @testing-library/react, msw (API mocking), jsdom. Dev server in compose (`web` service, port 5173, proxying `/api` to `api`).

**3. Implementation Instructions**
0. Add `/login` page (email + password → `POST /api/auth/login`), an auth context from `GET /api/auth/me`, an Axios/fetch interceptor redirecting 401 → `/login`, and a logout item in the TopBar user menu. Session cookie is HTTP-only, so no token storage in JS.
1. Scaffold Vite + React; split the prototype file into `src/components/` (TopBar, Sidebar, Card, Btn, Toggle, SliderRow, PreviewTable…) and `src/pages/` (Projects, CreateProject, Context, AddQuestion, Upload, Preprocess, Code, QAReview, Refinement, Results with its 5 tabs).
2. Replace `go(page)` with routes: `/projects`, `/projects/:pid`, `/projects/:pid/questions/:qid/{upload|preprocess|code|qa|refinement|results}`. Sidebar stage rail derives from route + run status.
3. `src/api/` typed client (generated from OpenAPI or hand-written hooks): `useProjects`, `useUploadDataset`, `usePreprocessJob` (SSE hook), `useRun`, `useApplyRun`, `useResults`, `useExport`.
4. Wire the review UI: `CodebookSuggestionCard` accept/reject → `PATCH codes`; finalize button disabled until zero proposed codes; Split/Merge panels post to refinement endpoints; reset button calls reset with confirm modal.
5. Charts: Recharts bar chart for frequencies; heatmap grid for co-occurrence; PNG export via server artifact (reuses notebook-quality matplotlib output) with client fallback.

**4. Automated Testing**
- Vitest + MSW test files: `ProjectsPage.test.tsx` (list renders, delete modal), `UploadPage.test.tsx` (file select → preview table rows), `CodePage.test.tsx` (proposed codes render; accept flips status; finalize disabled/enabled logic), `RefinementPage.test.tsx` (split proposal flow), `ResultsTabs.test.tsx` (tab switching, pagination controls, export button fires request).
- CI: `docker compose run --rm web npm test -- --run` → expected `~20 passed`; plus `npm run build` must succeed (type/build gate).

**5. Manual Testing**
```bash
docker compose up -d
open http://localhost:5173
```
Walk the full flow with `FAKE_LLM=1`: create project → add question → upload fixture xlsx → preprocess (watch live progress bar) → generate codebook → review/accept codes → apply → QA page shows metrics → split one code → results tabs → download Excel. Expected: no console errors; stage rail highlights match current page.

**6. Success Criteria**
- Every prototype screen functional against the real API; `npm run build` clean; component tests green; the fake-LLM walkthrough completes in <3 minutes.

**7. Run & Test Commands**
```bash
docker compose build web
docker compose run --rm web npm test -- --run
docker compose run --rm web npm run build
docker compose up -d && open http://localhost:5173
```

---

## Sequence 7 — End-to-End Tests, Full CI/CD Pipeline & Release Artifacts

**1. Goal**
Add Playwright E2E covering the entire user journey, assemble the final multi-stage CI/CD pipeline (lint → unit → integration → E2E → build/push images), and produce deployable artifacts.

**2. Isolated Environment Setup**
`docker/e2e.Dockerfile` from `mcr.microsoft.com/playwright:v1.x-jammy`; compose profile `e2e` starting the full stack with `FAKE_LLM=1` and a seeded DB.

**3. Implementation Instructions**
1. `e2e/journey.spec.ts`: create project → upload → preprocess → generate → review (accept all, edit one definition) → apply → QA → split → merge → reset → export workbook → assert downloaded file size >10KB and API sheet-count endpoint says 5.
2. `e2e/failure.spec.ts`: upload wrong file type → friendly error; finalize with pending code → blocked with message.
3. Final `.github/workflows/ci.yml` stages (each a job, needs-chained):
   - `lint`: ruff + eslint in containers
   - `test-backend`: pytest w/ coverage gate 85%
   - `test-frontend`: vitest + build
   - `e2e`: compose profile e2e + playwright, upload HTML report + traces as CI artifacts
   - `release` (on version tag on `main`): build prod images (`backend`, `frontend` behind nginx), push to registry, attach compose deploy bundle. Tags on any other branch are ignored.
4. `docker/frontend.prod.Dockerfile`: multi-stage `npm run build` → nginx static + `/api` proxy.

**4. Automated Testing**
The E2E suite *is* the test. CI command: `docker compose --profile e2e up -d && docker compose run --rm e2e npx playwright test`. Expected: `2 passed`; artifacts: `playwright-report/`, screenshots on failure.

**5. Manual Testing**
Download the CI artifact `playwright-report` and open `index.html` — every step has a screenshot/trace. Locally: `docker compose --profile e2e run --rm e2e npx playwright test --ui` for interactive replay.

**6. Success Criteria**
- One-command pipeline: fresh clone + `make ci` passes on a machine with only Docker installed.
- Tag push produces versioned images and a deploy bundle.
- E2E journey green; pipeline total <15 min; zero external network calls in test stages (fake LLM, MinIO, local registry cache).

**7. Run & Test Commands**
```bash
# the entire project, from scratch, in isolation:
git clone <repo> && cd codebench
bash scripts/ci_setup.sh
make ci                                   # lint + unit + integration
docker compose --profile e2e up -d
docker compose run --rm e2e npx playwright test
git tag v0.1.0 && git push --tags          # triggers release job
```

---

## Sequence ordering & gating summary

| Sequence | Depends on | CI gate |
|---|---|---|
| 0 Scaffold/env | — | healthz + env tests |
| 1 Package extraction | 0 | pytest ≥85% cov + demo run |
| 2 Data model/storage | 0 | db + migration tests |
| 3 API + jobs slice | 1,2 | api tests + curl slice |
| 4 Codebook/coding | 3 | coding tests, no external calls |
| 5 Refinement/exports | 4 | refine+export tests, workbook parity |
| 6 Frontend | 3–5 | vitest + build |
| 7 E2E + pipeline | all | full journey green, release artifacts |

## Git workflow per sequence (develop → main release model)

Branching model: **`main` = release-only** (every commit on it is deployable and tagged), **`develop` = integration branch** where all sequences land. Each sequence gets a short-lived branch off `develop`, merged back via PR when its CI gate is green. Releasing = fast-forward/merge `develop` into `main` + version tag, which triggers the Sequence-7 release job.

One-time setup:

```bash
git checkout -b main && git commit --allow-empty -m "chore: initial commit"
git push -u origin main
git checkout -b develop && git push -u origin develop
# In your host (GitHub/GitLab): set develop as the default branch,
# protect BOTH branches (require green CI, no direct pushes),
# and restrict main to merges from develop only.
```

CI config: run the full pipeline on PRs to `develop` and on `develop` itself; run the `release` job **only** on `main` tags (`on: push: tags: ['v*']` with a check that the tag commit is on `main`).

```bash
# Sequence 0
git checkout develop && git pull
git checkout -b seq/0-scaffold
git add -A && git commit -m "chore(scaffold): monorepo, docker compose env, healthz api, ci skeleton"
git push -u origin seq/0-scaffold        # PR → develop; squash-merge when CI green
git checkout develop && git pull && git tag seq-0 && git push --tags

# Sequence 1
git checkout -b seq/1-codeframe develop
git add -A && git commit -m "feat(codeframe): extract notebook into tested package (preprocess, cluster, codebook, coding, refine, reporting, state)"
git push -u origin seq/1-codeframe       # PR → develop
git checkout develop && git pull && git tag seq-1 && git push --tags

# Sequence 2
git checkout -b seq/2-data-model develop
git add -A && git commit -m "feat(db): tenant data model with org_id+role on all tables, alembic migrations, minio storage, org-scoped query layer + ci scoping check"
git push -u origin seq/2-data-model      # PR → develop
git checkout develop && git pull && git tag seq-2 && git push --tags

# Sequence 3
git checkout -b seq/3-api-auth-preprocess develop
git add -A && git commit -m "feat(api): session auth (login/logout/me), org-scoped project+question CRUD, upload with preview, async preprocess job with SSE progress"
git push -u origin seq/3-api-auth-preprocess   # PR → develop
git checkout develop && git pull && git tag seq-3 && git push --tags

# Sequence 4
git checkout -b seq/4-codebook-coding develop
git add -A && git commit -m "feat(coding): ai + imported codebooks with draft/review/apply gate, batch coding job, qa metrics endpoint"
git push -u origin seq/4-codebook-coding # PR → develop
git checkout develop && git pull && git tag seq-4 && git push --tags

# Sequence 5
git checkout -b seq/5-refine-exports develop
git add -A && git commit -m "feat(refine): split/merge as child runs, lineage reset, results endpoints, xlsx/csv/png exports to object storage"
git push -u origin seq/5-refine-exports  # PR → develop
git checkout develop && git pull && git tag seq-5 && git push --tags

# Sequence 6
git checkout -b seq/6-frontend develop
git add -A && git commit -m "feat(web): react app from prototype — login, routing, react-query data layer, review ui, refinement panels, results tabs + exports"
git push -u origin seq/6-frontend        # PR → develop
git checkout develop && git pull && git tag seq-6 && git push --tags

# Sequence 7 — last integration merge, then RELEASE to main
git checkout -b seq/7-e2e-release develop
git add -A && git commit -m "ci(e2e): playwright full-journey suite, staged pipeline, prod images + release job"
git push -u origin seq/7-e2e-release     # PR → develop; merge when full pipeline incl. e2e is green

# Release: promote develop to main
git checkout main && git pull
git merge --no-ff develop -m "release: v0.1.0"
git tag -a v0.1.0 -m "CodeBench v0.1.0 — first full pipeline release"
git push origin main --tags              # triggers release job (build+push prod images)

# Hotfix pattern (later): branch hotfix/x off main, fix, merge to main + tag vX.Y.Z+1,
# then merge main back into develop to keep branches converged.
```

Rules for Claude Code: sequence branches are always cut from an up-to-date `develop`; never commit directly to `develop` or `main`; never start sequence N+1 until sequence N's PR is merged with a green gate; `main` only ever advances via a release merge from `develop`; never amend or move published tags.

**Prompting tip for Claude Code:** give it one sequence at a time, plus this file and the two source files (`original_notebook.ipynb`, `codebench-prototype.jsx`) in the repo. Then follow the "Per-sequence operating procedure" at the top of this document: run the sequence's Section 7 block, loop run→fix until green, commit via the git block, and only then start the next sequence.
