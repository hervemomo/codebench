#!/usr/bin/env bash
# Manual, real-worker walkthrough of Refinement: register -> project ->
# question -> upload -> preprocess -> AI codebook run -> review -> finalize ->
# apply -> split (AI-proposed sub-codes) -> review -> finalize -> apply ->
# merge (AI-proposed name) -> review -> finalize -> apply -> reset -> export
# (xlsx + PNG) -> download via presigned URL. Talks to the API over its
# published port (or BASE_URL), exercising the real `worker` container.
#
# Requires: db/redis/minio/api/worker running (`docker compose up -d`) and the
# MinIO bucket bootstrapped (see scripts/ci_setup.sh). Uses python3 for JSON
# parsing -- no jq dependency. If openpyxl is importable (it is, inside the
# api/worker containers -- a backend dependency), the workbook's sheet count
# is verified after download; otherwise just the download itself is checked.
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
COOKIE_JAR="$(mktemp)"
SURVEY_FILE="${SURVEY_FILE:-backend/tests/data/tiny_survey.xlsx}"
DOWNLOAD_DIR="$(mktemp -d)"
trap 'rm -f "${COOKIE_JAR}"; rm -rf "${DOWNLOAD_DIR}"' EXIT

json_get() {
  python3 -c "import json,sys; d=json.load(sys.stdin); print(d$1)"
}

json_get_lines() {
  # $1: a python expression over `d` that yields an iterable of strings, one per line
  python3 -c "import json,sys; d=json.load(sys.stdin); [print(x) for x in ($1)]"
}

poll_job() {
  local job_id="$1"
  local stage=""
  for _ in $(seq 1 180); do
    JOB=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" "${BASE_URL}/api/jobs/${job_id}")
    stage=$(echo "${JOB}" | json_get "['stage']")
    echo "  stage=${stage}"
    [ "${stage}" = "done" ] && break
    sleep 1
  done
  echo "${JOB}"
}

accept_all_proposed() {
  local run_id="$1"
  local run_detail
  run_detail=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" "${BASE_URL}/api/runs/${run_id}")
  local proposed_ids
  proposed_ids=$(echo "${run_detail}" | json_get_lines "c['code_id'] for c in d['codebook']['codes'] if c['status']=='proposed'")
  while IFS= read -r CODE_ID; do
    [ -z "${CODE_ID}" ] && continue
    echo "  accepting ${CODE_ID}"
    curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -X PATCH "${BASE_URL}/api/runs/${run_id}/codes/${CODE_ID}" \
      -H "Content-Type: application/json" -d '{"status":"accepted"}' > /dev/null
  done <<< "${proposed_ids}"
}

EMAIL="manual-refine-$(date +%s 2>/dev/null || echo static)@example.com"

echo "== register =="
curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"Password123!\",\"org_name\":\"Manual Refine Org\"}"
echo

echo "== create project =="
PROJECT=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/projects" \
  -H "Content-Type: application/json" \
  -d '{"name":"Manual Refine Project","context":"Consumers of a beverage brand describe what they like about it.","source_lang":"en","target_lang":"en","codebook_lang":"en"}')
PROJECT_ID=$(echo "${PROJECT}" | json_get "['id']")

echo "== create question =="
QUESTION=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/projects/${PROJECT_ID}/questions" \
  -H "Content-Type: application/json" \
  -d '{"text":"What do you like about the brand?","survey_col":"feedback"}')
QUESTION_ID=$(echo "${QUESTION}" | json_get "['id']")

echo "== upload + preprocess =="
DATASET=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/questions/${QUESTION_ID}/datasets" \
  -F "file=@${SURVEY_FILE};type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
DATASET_ID=$(echo "${DATASET}" | json_get "['id']")
PP_JOB_ID=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/datasets/${DATASET_ID}/preprocess" | json_get "['job_id']")
poll_job "${PP_JOB_ID}" > /dev/null
echo "preprocess done"

echo "== s2: AI codebook run =="
S2_RUN=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/questions/${QUESTION_ID}/runs" \
  -H "Content-Type: application/json" -d '{"kind":"ai","target_codes":6}')
S2_RUN_ID=$(echo "${S2_RUN}" | json_get "['id']")
poll_job "$(echo "${S2_RUN}" | json_get "['job_id']")" > /dev/null

echo "== s2: accept all, finalize, apply =="
accept_all_proposed "${S2_RUN_ID}"
curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/runs/${S2_RUN_ID}/finalize" > /dev/null
APPLY_JOB_ID=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/runs/${S2_RUN_ID}/apply" | json_get "['job_id']")
poll_job "${APPLY_JOB_ID}" > /dev/null
echo "s2 applied"

echo "== s2 frequencies =="
curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" "${BASE_URL}/api/runs/${S2_RUN_ID}/results/frequencies"
echo

S2_DETAIL=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" "${BASE_URL}/api/runs/${S2_RUN_ID}")
NON_OTHER_IDS=$(echo "${S2_DETAIL}" | json_get_lines "c['code_id'] for c in d['codebook']['codes'] if 'other' not in c['name'].lower() and 'autre' not in c['name'].lower()")
SPLIT_TARGET=$(echo "${NON_OTHER_IDS}" | sed -n '1p')
MERGE_A=$(echo "${NON_OTHER_IDS}" | sed -n '2p')
MERGE_B=$(echo "${NON_OTHER_IDS}" | sed -n '3p')
echo "split target: ${SPLIT_TARGET} | merge candidates: ${MERGE_A}, ${MERGE_B}"

echo "== split (AI-proposed sub-codes, subcodes omitted) =="
SPLIT_RESP=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/runs/${S2_RUN_ID}/split" \
  -H "Content-Type: application/json" -d "{\"parent_code_id\":\"${SPLIT_TARGET}\",\"n_proposed\":3}")
echo "${SPLIT_RESP}"
SPLIT_CHILD_ID=$(echo "${SPLIT_RESP}" | json_get "['runs'][0]['id']")
poll_job "$(echo "${SPLIT_RESP}" | json_get "['runs'][0]['job_id']")" > /dev/null

echo "== split child: accept all, finalize, apply =="
accept_all_proposed "${SPLIT_CHILD_ID}"
curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/runs/${SPLIT_CHILD_ID}/finalize" > /dev/null
SPLIT_APPLY_JOB=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/runs/${SPLIT_CHILD_ID}/apply" | json_get "['job_id']")
poll_job "${SPLIT_APPLY_JOB}" > /dev/null
echo "split child applied"
curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" "${BASE_URL}/api/runs/${SPLIT_CHILD_ID}/results/frequencies"
echo

echo "== merge (AI-proposed name, merged_name omitted), off the ORIGINAL s2 run =="
MERGE_RESP=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/runs/${S2_RUN_ID}/merge" \
  -H "Content-Type: application/json" -d "{\"code_ids\":[\"${MERGE_A}\",\"${MERGE_B}\"]}")
echo "${MERGE_RESP}"
MERGE_CHILD_ID=$(echo "${MERGE_RESP}" | json_get "['id']")
poll_job "$(echo "${MERGE_RESP}" | json_get "['job_id']")" > /dev/null

echo "== merge child: accept, finalize, apply =="
accept_all_proposed "${MERGE_CHILD_ID}"
curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/runs/${MERGE_CHILD_ID}/finalize" > /dev/null
MERGE_APPLY_JOB=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/runs/${MERGE_CHILD_ID}/apply" | json_get "['job_id']")
poll_job "${MERGE_APPLY_JOB}" > /dev/null
echo "merge child applied (branched directly off s2 -- split child branch untouched)"

echo "== reset to s2 =="
curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/questions/${QUESTION_ID}/reset?to_run=${S2_RUN_ID}"
echo

echo "== confirm split branch is still fully intact after reset =="
curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" "${BASE_URL}/api/runs/${SPLIT_CHILD_ID}" | json_get "['status']"

echo "== export xlsx from s2 =="
EXPORT_JOB=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/runs/${S2_RUN_ID}/exports?format=xlsx")
EXPORT_JOB_ID=$(echo "${EXPORT_JOB}" | json_get "['job_id']")
poll_job "${EXPORT_JOB_ID}" > /dev/null
ARTIFACT_ID=$(echo "${JOB}" | json_get "['result']['artifact_id']")
echo "artifact_id=${ARTIFACT_ID}"

EXPORT=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" "${BASE_URL}/api/exports/${ARTIFACT_ID}")
echo "${EXPORT}"
DOWNLOAD_URL=$(echo "${EXPORT}" | json_get "['url']")

echo "== download workbook via presigned URL =="
curl -sS -o "${DOWNLOAD_DIR}/report.xlsx" -w "HTTP %{http_code}, %{size_download} bytes\n" "${DOWNLOAD_URL}"

python3 -c "
import openpyxl, sys
try:
    wb = openpyxl.load_workbook('${DOWNLOAD_DIR}/report.xlsx')
    print('Sheets:', wb.sheetnames)
    assert len(wb.sheetnames) == 5, f'expected 5 sheets, got {len(wb.sheetnames)}'
    print('Workbook OK: 5 sheets confirmed.')
except ImportError:
    print('openpyxl not importable on this host -- skipping sheet-count check (download itself succeeded above).')
"

echo "== export png_frequencies =="
PNG_JOB=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/runs/${S2_RUN_ID}/exports?format=png_frequencies")
poll_job "$(echo "${PNG_JOB}" | json_get "['job_id']")" > /dev/null
PNG_ARTIFACT_ID=$(echo "${JOB}" | json_get "['result']['artifact_id']")
PNG_URL=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" "${BASE_URL}/api/exports/${PNG_ARTIFACT_ID}" | json_get "['url']")
curl -sS -o "${DOWNLOAD_DIR}/frequencies.png" -w "HTTP %{http_code}, %{size_download} bytes\n" "${PNG_URL}"
python3 -c "
with open('${DOWNLOAD_DIR}/frequencies.png', 'rb') as f:
    head = f.read(8)
assert head == b'\x89PNG\r\n\x1a\n', f'bad PNG magic bytes: {head!r}'
print('PNG magic bytes OK.')
"

echo
echo "Manual refine flow complete."
