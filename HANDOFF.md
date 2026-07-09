# Handoff

**Last updated:** 2026-07-09 (session end)
**Sequence in progress:** 4 — Codebook Generation, Review Workflow & Coding Jobs — **not yet started**
**Branch:** none cut yet — next step is to cut `seq/4-codebook-review-coding` from up-to-date `develop`

## Sequence 0–3 (for reference)
All complete, tagged `seq-0`/`seq-1`/`seq-2`/`seq-3` on `develop`, CI green on GitHub. PR #4 (`seq/3-api-auth-preprocess` → `develop`) merged 2026-07-09 via merge commit `d068a12`.

## Sequence 3 — completed
- Real auth (no simulation): `POST /api/auth/{register,login,logout}`, `GET /api/auth/me`. Argon2 password hashing; session is a signed (itsdangerous), HTTP-only cookie carrying only a user id. `register` is the dev/admin bootstrap path — creates a brand-new org + its first admin user in one call.
- `get_current_user` dependency resolves `(user, org_id)` from the cookie and is required by every business router; `org_id` is never accepted from the client.
- **The one sanctioned exception to org-scoping:** `find_user_by_email` / `get_user_by_id_unscoped`, added to `app/db/scoped.py` itself (not `app/auth.py`) — determining which org a user belongs to is the whole point of these two pre-auth queries, so `scripts/check_org_scoping.sh`'s "outside this module" rule doesn't need special-casing.
- Routers: `POST/GET /api/projects`, `POST /api/projects/{id}/questions`, `PUT /api/projects/{id}/context`, `POST /api/questions/{id}/datasets` (multipart → MinIO + 10-row preview), `POST /api/datasets/{id}/preprocess` (enqueues RQ job), `GET /api/datasets/{id}/stats`, `GET /api/jobs/{id}` + `/stream` (SSE). All cross-org ID lookups 404 (never 403) by construction, since every lookup goes through `scoped_query`.
- `app/jobs/preprocess.py`: RQ job runs `codeframe.preprocessing` + `translation` (Sequence 1 package), writes `Response` rows, updates `Dataset.status`. Progress is an RPUSH'd Redis list (`progress:{job_id}`) of `{stage, current, total}` snapshots — the SSE endpoint replays existing entries then polls for new ones, so it works identically whether the job already finished (tests) or is still running (real worker).
- `RQ_IS_ASYNC=false` + `FAKE_LLM=true` settings (env-overridable) let `tests/api/` run the real RQ enqueue path fully synchronously with the deterministic fake LLM — no separate worker process or API key needed in CI.
- `docker-compose.yml` `worker` service now runs the real `rq worker --url $REDIS_URL codebench` (replacing Sequence 0's placeholder); both `api` and `worker` also depend on `minio`.
- `tests/api/` (40 tests): `test_auth.py`, `test_cross_org.py`, `test_api_projects.py`, `test_upload.py`, `test_preprocess_job.py`, `test_sse.py`.
- **Three bugs found and fixed during implementation/manual verification:**
  1. `codeframe.preprocessing.load_survey_data()` expects a filesystem path (mirrors the notebook), but the file only exists as MinIO bytes — fixed by staging to a `tempfile.NamedTemporaryFile` before calling it.
  2. This session's newer Starlette `TestClient` no longer accepts `json=` on `.get()` at all (even `None`) — fixed by only passing the kwarg when there's an actual body.
  3. **Found only in the manual curl slice, not by any automated test:** re-running `POST /api/datasets/{id}/preprocess` on the same dataset via the real async worker **doubled** the `Response` row count (60 instead of 30) instead of being idempotent — violating a named Success Criterion. Root cause: the job only ever `INSERT`ed, never cleared prior output. Fixed by deleting existing `Response` rows for that dataset (org-scoped) before inserting; added `test_preprocess_job_is_idempotent_on_rerun` to lock in the fix. **This is why the manual curl slice matters — the full automated suite was green while this bug was live.**
  4. (Environment gotcha, not a code bug) `api` and `worker` build as *separate* Docker images from the same Dockerfile — rebuilding `api` alone left `worker` running stale code with no `app/jobs` module at all, surfacing as a confusing RQ `import_attribute` error. Now always run `docker compose build` (no service arg) after backend changes.
- Manual curl slice run against the live stack (real worker, not synchronous test mode): register → login(implicit via cookie) → create project → create question → upload `tiny_survey.xlsx` → enqueue preprocess → poll job (`loading`→`loaded`→`preprocessed`→`translated`→`done`) → stats. `kept=30, invalid=0, duplicates=0` — matches Sequence 1's codeframe output exactly. `/docs` and `/openapi.json` both 200.
- PR #4 opened `seq/3-api-auth-preprocess` → `develop` (explicit `--base develop`, since GitHub's UI "Compare & pull request" banner defaults to `main`). GitHub Actions CI run 29055345605 went green (`make ci`, org-scoping check, all steps ✓) in 2m24s. Merged via merge commit `d068a12` (same convention as PRs #1–#3: regular merge, not squash). Tagged `seq-3` on `develop` and pushed the tag.

## Test status: GREEN (GitHub Actions CI green on PR #4, run 29055345605)
```
docker compose run --rm api ruff check .                     → All checks passed!
bash scripts/check_org_scoping.sh                             → Org-scoping check OK
docker compose run --rm api pytest tests/api -q                → 40 passed (stable across repeat runs)
docker compose run --rm api pytest -q                          → 164 passed (100 Seq1 + 24 Seq2 + 40 Seq3)
Manual curl slice against the real worker (not is_async=False): full upload→preprocess→poll→stats
  round-trip green; re-run confirmed idempotent (30, not 60) after the fix.
```

## Note for next session
- `make.exe` is still blocked on this Windows host by an Application Control policy — use raw `docker compose` commands locally.
- **Always run `docker compose build` (all services, no service arg) after backend code changes** — `api` and `worker` are separate images from the same Dockerfile and silently drift apart otherwise (bit us this session).
- **Always run `docker compose run --rm api ruff check .` AND `bash scripts/check_org_scoping.sh` locally before opening a PR**, in addition to `pytest`.
- **The automated suite passing is not sufficient proof of correctness for anything touching the real async worker** — this session's idempotency bug was invisible to `pytest tests/api` (which only exercises the synchronous `is_async=False` path) and only surfaced via the manual curl slice against the real `rq worker` process. Any future job-queue work should get a manual real-worker pass, not just synchronous tests.

## Next action
Sequence 3 is fully closed out (merged, tagged, CI green). Start Sequence 4 — Codebook Generation, Review Workflow & Coding Jobs:
- Cut `seq/4-codebook-review-coding` from up-to-date `develop` (currently at tag `seq-3`).
- New migration: `DRAFT → REVIEWED → APPLIED` run-status enum (remember the Sequence-2 lesson: explicitly drop native Postgres ENUM types in `downgrade()`).
- Implement `POST /api/questions/{id}/runs` (`kind: "ai"|"import"`), review endpoints (`PATCH .../codes/{code_id}`, `POST .../codes`, `POST .../finalize`), `POST /api/runs/{id}/apply` (coding job), `GET /api/runs/{id}/qa`.
- Section 7 gate: `docker compose run --rm api alembic upgrade head`, `docker compose run --rm api pytest tests/coding -q` (~16 tests), `FAKE_LLM=1 docker compose up -d && bash scripts/manual_coding_flow.sh`.
- Per the standing lesson from Sequence 3: the automated suite alone is not sufficient proof for anything touching the real async worker — do a manual real-worker pass on the apply/coding job, not just synchronous tests.
- Local branch `seq/3-api-auth-preprocess` can be pruned (already merged) — do this at the start of the next session if not already done.
