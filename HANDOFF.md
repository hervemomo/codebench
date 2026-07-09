# Handoff

**Last updated:** 2026-07-09
**Sequence in progress:** 1 — Extract the Notebook into a Tested Python Package — **implemented, locally green, awaiting PR review**
**Branch:** `seq/1-codeframe` (cut from `develop` at tag `seq-0`)

## Sequence 0 (for reference)
Complete, tagged `seq-0` on `develop`, CI green on GitHub. See git log / prior tag for details.

## Sequence 1 — completed this session
- Read `docs/source/PLAYBOOK.md` Sequence 1 and the full `docs/source/original_notebook.ipynb` before writing any code.
- Extracted every notebook section into `backend/codeframe/` exactly per the playbook's module table: `config.py`, `llm.py`, `preprocessing.py`, `translation.py`, `clustering.py`, `codebook.py`, `coding.py`, `refine.py`, `reporting.py`, `state.py`, plus `demo.py` (CLI). No `globals()`, no module-level side effects, every function takes explicit Pydantic config, UMAP/HDBSCAN seeded from `cfg.random_seed`.
- Added deps to `backend/pyproject.toml` (`ftfy`, `lingua-language-detector`, `tenacity`, `matplotlib`, `seaborn`, `pyarrow`, `pytest-cov`) and regenerated `backend/requirements.lock` in-container.
- Built `tests/fixtures/fake_openai.py` — a deterministic fake OpenAI client (chat + embeddings) driven by prompt-shape dispatch and keyword-category matching; supports failure-injection markers (`###NO_MATCH###`, `###INVALID_CODE###`, `BATCH_CODE_FAIL`, `BATCH_TRANSLATE_FAIL`, `ALWAYS_TRANSLATE_FAIL`, `AI_SPLIT_PARSE_FAIL`, `AI_SPLIT_EMPTY`, `AI_MERGE_NO_NAME`) so retry/fallback paths are testable without a real API.
- Committed `tests/data/tiny_survey.xlsx` — 30 synthetic English responses across 5 themes (taste, price, packaging, availability, energy/health), generated in-container.
- Full test suite in `backend/tests/codeframe/` (11 files, 100 tests) covering preprocessing, llm retry/parsing, translation, clustering determinism, codebook generation/loading/enrichment, coding batching/fallback, split/merge (non-mutating), reporting exports, state round-trip, and end-to-end demo determinism.
- **Bug found and fixed during verification:** a catastrophic-backtracking regex in `tests/fixtures/fake_openai.py`'s codebook-response handler (`(?:.+\n?)*?` over a multi-KB prompt) hung the pytest process indefinitely (confirmed via `faulthandler` stack dump). Replaced with a bounded, non-nested split. This was a test-fixture bug only, not in production `codeframe/` code.

## Test status: GREEN (local only — not yet pushed through GitHub Actions)
```
docker compose build api                                          → clean
docker compose run --rm api pytest -q --cov=codeframe --cov-fail-under=85
  → 100 passed, coverage 91.78% (gate: 85%)
docker compose run --rm api python -m codeframe.demo tests/data/tiny_survey.xlsx --fake-llm
  → run twice: identical codebook (['Price & Value', 'Packaging & Design', 'Availability',
    'Energy & Health', 'Taste & Flavor', 'Other / Not classifiable']) and identical cluster
    labels both times (also asserted directly in test_demo.py)
  → workbook has exactly 5 sheets: Summary, Frequencies, Co-occurrence, Codebook, Coded data
```
Per-module coverage: clustering 94%, codebook 85%, coding 94%, config 98%, demo 97%, llm 98%, preprocessing 89%, refine 91%, reporting 96%, state 100%, translation 97%.

## Next action
Push `seq/1-codeframe`, open a PR into `develop`, confirm GitHub Actions CI is green (same command as local: `ci_setup.sh` + `make ci` — note `make` is blocked locally on this Windows host by an Application Control policy, but works fine on the Linux CI runner), then merge and tag `seq-1` before starting **Sequence 2 — Data Model, Migrations & Object Storage**.
