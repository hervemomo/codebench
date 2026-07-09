#!/usr/bin/env bash
# Fails the build if any tenant-model query bypasses the org-scoping repository
# layer (app/db/scoped.py). No endpoint may ever construct its own
# select(<TenantModel>) / session.query(<TenantModel>) — always go through
# scoped_query() or a ScopedRepository subclass instead.
set -euo pipefail

TENANT_MODELS="User|Project|Question|Dataset|Response|CodingRun|CodeAssignment|ExportArtifact"
PATTERN="(select\\(|session\\.query\\()\\s*(${TENANT_MODELS})\\b"

VIOLATIONS=$(grep -rnE "${PATTERN}" backend/app --include="*.py" | grep -v "^backend/app/db/scoped.py:" || true)

if [ -n "${VIOLATIONS}" ]; then
  echo "Unscoped tenant-model queries found outside the repository layer (backend/app/db/scoped.py):"
  echo "${VIOLATIONS}"
  echo
  echo "Use scoped_query(session, Model, org_id) or a ScopedRepository subclass instead."
  exit 1
fi

echo "Org-scoping check OK — no unscoped tenant-model queries found."
