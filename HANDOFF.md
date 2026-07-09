# Handoff

**Last updated:** 2026-07-09
**Sequence in progress:** 1 — Extract the Notebook into a Tested Python Package — **COMPLETE, tagged `seq-1`**
**Branch:** `develop` (at tag `seq-1`, commit `11898e8`). `seq/1-codeframe` is fully merged and its remote branch was deleted by GitHub; the local branch has been pruned too.

## Sequence 0 (for reference)
Complete, tagged `seq-0` on `develop`, CI green on GitHub.

## Sequence 1 — completed
- Read `docs/source/PLAYBOOK.md` Sequence 1 and the full `docs/source/original_notebook.ipynb` before writing any code.
- Extracted every notebook section into `backend/codeframe/` exactly per the playbook's module table: `config.py`, `llm.py`, `preprocessing.py`, `translation.py`, `clustering.py`, `codebook.py`, `coding.py`, `refine.py`, `reporting.py`, `state.py`, plus `demo.py` (CLI). No `globals()`, no module-level side effects, every function takes explicit Pydantic config, UMAP/HDBSCAN seeded from `cfg.random_seed`.
- Added deps to `backend/pyproject.toml` (`ftfy`, `lingua-language-detector`, `tenacity`, `matplotlib`, `seaborn`, `pyarrow`, `pytest-cov`) and regenerated `backend/requirements.lock` in-container.
- Built `tests/fixtures/fake_openai.py` — a deterministic fake OpenAI client (chat + embeddings) driven by prompt-shape dispatch and keyword-category matching; supports failure-injection markers (`###NO_MATCH###`, `###INVALID_CODE###`, `BATCH_CODE_FAIL`, `BATCH_TRANSLATE_FAIL`, `ALWAYS_TRANSLATE_FAIL`, `AI_SPLIT_PARSE_FAIL`, `AI_SPLIT_EMPTY`, `AI_MERGE_NO_NAME`) so retry/fallback paths are testable without a real API.
- Committed `tests/data/tiny_survey.xlsx` — 30 synthetic English responses across 5 themes (taste, price, packaging, availability, energy/health), generated in-container.
- Full test suite in `backend/tests/codeframe/` (11 files, 100 tests) covering preprocessing, llm retry/parsing, translation, clustering determinism, codebook generation/loading/enrichment, coding batching/fallback, split/merge (non-mutating), reporting exports, state round-trip, and end-to-end demo determinism.
- **Bug found and fixed during implementation:** a catastrophic-backtracking regex in `tests/fixtures/fake_openai.py`'s codebook-response handler (`(?:.+\n?)*?` over a multi-KB prompt) hung the pytest process indefinitely (confirmed via `faulthandler` stack dump). Replaced with a bounded, non-nested split. Test-fixture bug only, not in production `codeframe/` code.
- **PR #2 → CI failure → fix:** opening the PR surfaced a `ruff` lint failure (`E741 Ambiguous variable name: l`) in `clustering.py` that local verification had missed (only `pytest` + the demo had been run, not `make ci`'s lint step). Fixed by renaming the variable; pushed; CI went green (`make ci` in 1m49s).
- PR #2 merged into `develop` (squash/merge commit `11898e8`), tag `seq-1` created on `develop` and pushed. Local stale branches `seq/0-scaffold` and `seq/1-codeframe` deleted (both fully merged); stale remote-tracking refs pruned.

## Test status: GREEN (local + GitHub Actions CI)
```
docker compose build api                                          → clean
docker compose run --rm api pytest -q --cov=codeframe --cov-fail-under=85
  → 100 passed, coverage 91.78% (gate: 85%)
docker compose run --rm api python -m codeframe.demo tests/data/tiny_survey.xlsx --fake-llm
  → codebook: ['Price & Value', 'Packaging & Design', 'Availability',
    'Energy & Health', 'Taste & Flavor', 'Other / Not classifiable'] (identical across repeated runs)
  → workbook has exactly 5 sheets: Summary, Frequencies, Co-occurrence, Codebook, Coded data
GitHub Actions (PR #2, run 28996692032): make ci green in 1m49s
```
Per-module coverage: clustering 94%, codebook 85%, coding 94%, config 98%, demo 97%, llm 98%, preprocessing 89%, refine 91%, reporting 96%, state 100%, translation 97%.

## Note for next session
`make.exe` is blocked on this Windows host by an Application Control policy — use the equivalent raw `docker compose` commands locally instead of `make up`/`make ci`/`make lint`. This bit us once already (a `ruff` lint failure only surfaced in CI because local verification skipped `make ci`'s lint step). **Before opening a PR, run `docker compose run --rm api ruff check .` locally** in addition to `pytest`, so lint failures are caught before pushing.

## Next action
Start **Sequence 2 — Data Model, Migrations & Object Storage**: `git checkout develop && git pull`, then `git checkout -b seq/2-data-model develop`, and follow Sequence 2's implementation/testing instructions in `docs/source/PLAYBOOK.md` (SQLAlchemy models with mandatory `org_id`/`role` multi-tenancy, Alembic migration `0001_initial`, MinIO storage wrapper, `scoped_query` org-scoping layer + `scripts/check_org_scoping.sh` CI check).
