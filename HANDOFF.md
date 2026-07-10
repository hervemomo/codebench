# Handoff

**Last updated:** 2026-07-10 (session end)
**Sequence in progress:** 6 — Frontend: Prototype → Real Application — **not yet started**
**Branch:** none cut yet — next step is to cut `seq/6-frontend` from up-to-date `develop`

## Sequence 0–5 (for reference)
All complete, tagged `seq-0` through `seq-5` on `develop`, CI green on GitHub. PR #6 (`seq/5-refine-exports` → `develop`) merged 2026-07-10 via merge commit `ab824c3`.

## Branch-cleanup policy (as of 2026-07-09)
Per-sequence branches (`seq/N-*`) are **left in place**, local and remote, once their PR merges — they're inert (already merged, won't be merged again, don't affect CI). Do **not** prune them after each sequence merge. Instead, do one batch prune of every merged `seq/N-*` branch at the point of the eventual `develop` → `main` release merge. `seq/0-scaffold`, `seq/4-codebook-coding`, and `seq/5-refine-exports` are currently on origin under this policy; `seq/1`/`seq/2`/`seq/3` were already pruned before the policy was adopted, so there's nothing to reconcile there.

## Sequence 4 — summary (for reference)
AI/import codebook generation (`POST /api/questions/{id}/runs`), the DRAFT→REVIEWED→APPLIED review gate (`PATCH .../codes/{code_id}`, `POST .../codes`, `POST .../finalize`), apply (`POST .../apply`, idempotent by design), and QA metrics (`GET .../qa`, pure-function `app/qa.py::compute_qa_metrics`). 24 tests in `tests/coding/`. Full detail in the `seq-4` tag's commit / PR #5 if needed.

## Sequence 5 — summary (for reference)
Split/merge as new child `CodingRun`s (`POST /api/runs/{id}/split` — single `parent_code_id` or `parent_codes: [...]` to split several different codes at once, each into its own child run; `POST /api/runs/{id}/merge`, frequency is a true set union not a sum) reusing Sequence 4's review/finalize/apply gate unchanged. Lineage reset (`POST /api/questions/{id}/reset?to_run=`, pure bookkeeping, nothing deleted, auto-advanced on every apply). Results (`GET /runs/{id}/results/{frequencies|cooccurrence|codebook}`, paginated/searchable `GET /runs/{id}/responses`) and exports (`POST /runs/{id}/exports?format=xlsx|csv_frequencies|csv_coded|png_frequencies|png_cooccurrence` → MinIO → `ExportArtifact`, `GET /exports/{id}` presigned URL). New migration `0003_active_run_pointer` (`questions.active_run_id`). 29 tests in `tests/refine/` + `tests/exports/`. Full detail in the `seq-5` tag's commit / PR #6 if needed.

**Key lessons carried forward from Sequence 5** (still relevant to Sequence 6 and beyond):
- Adding a second FK between two tables that already have a SQLAlchemy `relationship()` requires `foreign_keys=` on **both** sides of the existing relationship, not just the new one, or mapper configuration fails at runtime with `InvalidRequestError: ... multiple foreign key paths`.
- JSONB columns mutated in place (not reassigned) need `sqlalchemy.orm.attributes.flag_modified(obj, "column_name")` or the change silently doesn't persist.
- Idempotency (delete-then-insert before writing job output) is standing practice for every job that writes DB rows.
- When a Playbook request-body field is ambiguous (e.g. "multi-config splits create one child run each" didn't say what varies between configs), implement your best-guess reading, flag it explicitly to the user with a concrete example, and be ready to rework before the next sequence builds a UI around it — this happened once already (Sequence 5's split endpoint) and cost one extra round-trip; asking before implementing would have been cheaper.

## Test status: GREEN (local + manual real-worker pass + GitHub Actions CI green on PR #6, run 29067909311)
```
docker compose run --rm api alembic upgrade head              → ...-> 0003_active_run_pointer
docker compose run --rm api ruff check .                      → All checks passed!
bash scripts/check_org_scoping.sh                              → Org-scoping check OK
docker compose run --rm api pytest tests/refine tests/exports -q → 29 passed
docker compose run --rm api pytest -q                          → 217 passed (188 Seq0-4 + 29 Seq5)
Manual flow (scripts/manual_refine_flow.sh) against the real worker: full
  upload→preprocess→AI-codebook→apply→split(AI-proposed)→apply→merge(AI-proposed)→
  apply→reset→export-xlsx→export-png round-trip green. Workbook downloaded via
  presigned URL confirmed to have exactly 5 sheets; PNG magic bytes confirmed.
```

## Note for next session
- `make.exe` is still blocked on this Windows host by an Application Control policy — use raw `docker compose` commands locally.
- **Always run `docker compose build` (all services, no service arg) after backend code changes** — `api` and `worker` are separate images from the same Dockerfile and silently drift apart otherwise. This has now bitten three sequences in a row; treat it as inherent to this project's setup, not a one-off.
- **Always run `docker compose run --rm api ruff check .` AND `bash scripts/check_org_scoping.sh` locally before opening a PR**, in addition to `pytest`.
- This host has an unrelated stray Python process bound to `127.0.0.1:8000` from a different, unrelated project (`codeframe-webapp`) that intercepts plain `curl http://localhost:8000/...`. Don't kill it without asking; instead run manual flows via `docker run --rm --network codebench_default ...` hitting `http://api:8000` (Docker service DNS), as Sequences 4 and 5's manual scripts did.
- **Docker Desktop's backend engine can silently stop responding** (`docker ps` fails with a pipe error, or later a 500 on the same pipe) even while the Docker Desktop process is still alive. Fix: kill the Docker Desktop processes, run `wsl --shutdown`, then relaunch `Docker Desktop.exe` — a plain relaunch without the WSL shutdown wasn't enough last time and got stuck on a 500. Give it 60-90s after relaunch before retrying `docker ps`. This happened mid-Sequence-5 and cost real time; check Docker health early in a session if commands start failing strangely.
- Idempotency (delete-then-insert before writing job output) is standing practice for every job that writes DB rows now — build it in from the start, don't wait to find the bug.

## Next action
Sequence 5 is fully closed out (merged, tagged, CI green). Start Sequence 6 — Frontend: Prototype → Real Application:
- Cut `seq/6-frontend` from up-to-date `develop` (currently at tag `seq-5`).
- This is the first frontend-focused sequence — `docker/frontend.Dockerfile` and the `web` service already exist (Sequence 0) but are still a placeholder. New deps: react, react-dom, react-router-dom, @tanstack/react-query, recharts, lucide-react, vitest, @testing-library/react, msw, jsdom.
- Convert `docs/source/codebench-prototype.jsx` into a real Vite+React app wired to the API built across Sequences 3-5: `/login` page + auth context (`GET /api/auth/me`, 401 → redirect), route-based navigation replacing the prototype's `go(page)` state machine, a typed API client/hooks layer, live job progress via the SSE endpoint, the review UI (accept/reject/edit → `PATCH codes`, finalize gate), split/merge panels, reset with a confirm modal, Recharts frequency/co-occurrence charts, and export buttons hitting the real export endpoints.
- Every backend endpoint this UI needs already exists and is tested — Sequences 3-5 delivered the full API surface (auth, upload/preprocess, codebook generation/review/apply, QA, split/merge/reset, results/exports). This sequence is pure frontend integration, no backend changes expected.
- Section 7 gate: `docker compose run --rm web npm test -- --run` (~20 tests), `docker compose run --rm web npm run build` (must succeed — this is also the type-check gate), manual walkthrough at `http://localhost:5173` with `FAKE_LLM=1` (create project → question → upload → preprocess → generate codebook → review → apply → QA → split → results → download Excel; expect no console errors, <3 minutes end to end).
- Local branch `seq/5-refine-exports` can be pruned per the batch policy above — **not** now, only at the eventual `develop` → `main` release.
