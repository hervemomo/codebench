#!/usr/bin/env bash
# Manual, real-worker walkthrough of the Code stage: register -> project ->
# question -> upload -> preprocess -> AI codebook run -> review -> finalize ->
# apply -> QA. Talks to the API over its published port (not `docker compose
# exec`), so it exercises the real `worker` container end to end -- the same
# reason Sequence 3's idempotency bug was only caught by a manual pass, not
# by pytest tests/api (which runs jobs inline with RQ_IS_ASYNC=false).
#
# Requires: db/redis/minio/api/worker running (`docker compose up -d`) and the
# MinIO bucket bootstrapped (`docker compose run --rm mc "..."`, see
# scripts/ci_setup.sh). Uses python3 for JSON parsing -- no jq dependency.
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
COOKIE_JAR="$(mktemp)"
SURVEY_FILE="backend/tests/data/tiny_survey.xlsx"
trap 'rm -f "${COOKIE_JAR}"' EXIT

json_get() {
  python3 -c "import json,sys; d=json.load(sys.stdin); print(d$1)"
}

EMAIL="manual-coding-$(date +%s 2>/dev/null || echo static)@example.com"

echo "== register =="
REGISTER=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"Password123!\",\"org_name\":\"Manual Coding Org\"}")
echo "${REGISTER}"

echo "== create project =="
PROJECT=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/projects" \
  -H "Content-Type: application/json" \
  -d '{"name":"Manual Coding Project","context":"Consumers of a beverage brand describe what they like about it.","source_lang":"en","target_lang":"en","codebook_lang":"en"}')
echo "${PROJECT}"
PROJECT_ID=$(echo "${PROJECT}" | json_get "['id']")

echo "== create question =="
QUESTION=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/projects/${PROJECT_ID}/questions" \
  -H "Content-Type: application/json" \
  -d '{"text":"What do you like about the brand?","survey_col":"feedback"}')
echo "${QUESTION}"
QUESTION_ID=$(echo "${QUESTION}" | json_get "['id']")

echo "== upload dataset =="
DATASET=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/questions/${QUESTION_ID}/datasets" \
  -F "file=@${SURVEY_FILE};type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
echo "${DATASET}"
DATASET_ID=$(echo "${DATASET}" | json_get "['id']")

echo "== enqueue preprocess =="
PREPROCESS=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/datasets/${DATASET_ID}/preprocess")
echo "${PREPROCESS}"
PP_JOB_ID=$(echo "${PREPROCESS}" | json_get "['job_id']")

echo "== poll preprocess job =="
for _ in $(seq 1 60); do
  JOB=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" "${BASE_URL}/api/jobs/${PP_JOB_ID}")
  STAGE=$(echo "${JOB}" | json_get "['stage']")
  echo "  stage=${STAGE}"
  [ "${STAGE}" = "done" ] && break
  sleep 1
done
echo "${JOB}"

echo "== dataset stats =="
curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" "${BASE_URL}/api/datasets/${DATASET_ID}/stats"
echo

echo "== create AI codebook run =="
RUN=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/questions/${QUESTION_ID}/runs" \
  -H "Content-Type: application/json" \
  -d '{"kind":"ai","target_codes":6}')
echo "${RUN}"
RUN_ID=$(echo "${RUN}" | json_get "['id']")
RUN_JOB_ID=$(echo "${RUN}" | json_get "['job_id']")

echo "== poll codebook-generation job =="
for _ in $(seq 1 120); do
  JOB=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" "${BASE_URL}/api/jobs/${RUN_JOB_ID}")
  STAGE=$(echo "${JOB}" | json_get "['stage']")
  echo "  stage=${STAGE}"
  [ "${STAGE}" = "done" ] && break
  sleep 1
done
echo "${JOB}"

echo "== review: accept every proposed code =="
RUN_DETAIL=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" "${BASE_URL}/api/runs/${RUN_ID}")
CODE_IDS=$(echo "${RUN_DETAIL}" | python3 -c "import json,sys; d=json.load(sys.stdin); print('\n'.join(c['code_id'] for c in d['codebook']['codes']))")
while IFS= read -r CODE_ID; do
  [ -z "${CODE_ID}" ] && continue
  echo "  accepting ${CODE_ID}"
  curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -X PATCH "${BASE_URL}/api/runs/${RUN_ID}/codes/${CODE_ID}" \
    -H "Content-Type: application/json" -d '{"status":"accepted"}' > /dev/null
done <<< "${CODE_IDS}"

echo "== finalize =="
FINALIZE=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/runs/${RUN_ID}/finalize")
echo "${FINALIZE}"

echo "== apply =="
APPLY=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/runs/${RUN_ID}/apply")
echo "${APPLY}"
APPLY_JOB_ID=$(echo "${APPLY}" | json_get "['job_id']")

echo "== poll apply job =="
for _ in $(seq 1 120); do
  JOB=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" "${BASE_URL}/api/jobs/${APPLY_JOB_ID}")
  STAGE=$(echo "${JOB}" | json_get "['stage']")
  echo "  stage=${STAGE}"
  [ "${STAGE}" = "done" ] && break
  sleep 1
done
echo "${JOB}"

echo "== run detail (status should be applied) =="
curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" "${BASE_URL}/api/runs/${RUN_ID}"
echo

echo "== QA metrics (first apply) =="
QA1=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" "${BASE_URL}/api/runs/${RUN_ID}/qa")
echo "${QA1}"
QA1_CODED=$(echo "${QA1}" | json_get "['total_coded']")

echo "== re-apply (idempotency check against the real worker) =="
APPLY2=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -X POST "${BASE_URL}/api/runs/${RUN_ID}/apply")
echo "${APPLY2}"
APPLY2_JOB_ID=$(echo "${APPLY2}" | json_get "['job_id']")
for _ in $(seq 1 120); do
  JOB=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" "${BASE_URL}/api/jobs/${APPLY2_JOB_ID}")
  STAGE=$(echo "${JOB}" | json_get "['stage']")
  echo "  stage=${STAGE}"
  [ "${STAGE}" = "done" ] && break
  sleep 1
done
echo "${JOB}"

echo "== QA metrics (after re-apply -- total_coded must be unchanged, not doubled) =="
QA2=$(curl -sS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" "${BASE_URL}/api/runs/${RUN_ID}/qa")
echo "${QA2}"
QA2_CODED=$(echo "${QA2}" | json_get "['total_coded']")

if [ "${QA1_CODED}" != "${QA2_CODED}" ]; then
  echo "IDEMPOTENCY CHECK FAILED: total_coded went from ${QA1_CODED} to ${QA2_CODED}"
  exit 1
fi
echo "Idempotency check OK: total_coded stayed at ${QA2_CODED} across re-apply."

echo
echo "Manual coding flow complete."
