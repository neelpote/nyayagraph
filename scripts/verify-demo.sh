#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-http://localhost:8000/api/v1}"
LOGIN_JSON="$(curl --fail --silent --show-error -X POST "${API_BASE}/auth/dev-login" \
  -H 'content-type: application/json' \
  -d '{"email":"io@nyaya.local","password":"NyayaDemo!2026"}')"
TOKEN="$(printf '%s' "${LOGIN_JSON}" | jq -r .accessToken)"
CASE_JSON="$(curl --fail --silent --show-error "${API_BASE}/cases/MH-PUNE-2026-00142" \
  -H "Authorization: Bearer ${TOKEN}")"
VERSION_ID="$(printf '%s' "${CASE_JSON}" | jq -r '.documents[] | select(.title == "FSL residue analysis report") | .versionId')"
curl --fail --silent --show-error -X POST "${API_BASE}/verification/document" \
  -H "Authorization: Bearer ${TOKEN}" \
  -F "document_version_id=${VERSION_ID}" \
  -F "file=@seed/documents/forensic-original.pdf;type=application/pdf" | jq -e '.status == "VERIFIED"' >/dev/null
curl --fail --silent --show-error -X POST "${API_BASE}/verification/document" \
  -H "Authorization: Bearer ${TOKEN}" \
  -F "document_version_id=${VERSION_ID}" \
  -F "file=@seed/documents/forensic-modified.pdf;type=application/pdf" | jq -e '.status == "HASH_MISMATCH"' >/dev/null
printf '%s\n' "NyayaGraph demo verification passed: case loaded, original verified, modified file rejected."
