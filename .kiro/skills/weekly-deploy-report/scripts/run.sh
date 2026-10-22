#!/usr/bin/env bash
#
# run.sh — one-shot weekly deployment report.
#
# Collects OrcaBus production deployment status from the deploy-status API,
# diffs each service against the tip of `main`, and renders a markdown report.
#
# Usage:
#   .kiro/skills/weekly-deploy-report/scripts/run.sh [--days N] [--api-base URL] [--out FILE]
#
# Requirements: python3, gh (authenticated), jq (optional).
# Auth: PORTAL_TOKEN (Cognito JWT) is auto-sourced from the repo-root .env if
# present. You can also export PORTAL_TOKEN/ORCABUS_TOKEN, or pass --token.
# The intermediate JSON is written next to the report so the Kiro agent can
# read it to write a richer prose "significant changes" narrative.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORT_DIR="$(cd "${SCRIPT_DIR}/../../../.." && pwd)/scratch"
DATE_STAMP="$(date -u +%Y-%m-%d)"

DAYS=7
API_BASE="https://deploy-status.prod.umccr.org"
OUT="${REPORT_DIR}/deployment-status-report-${DATE_STAMP}.md"
JSON_OUT="${REPORT_DIR}/deployment-status-${DATE_STAMP}.json"
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --days) DAYS="$2"; shift 2 ;;
    --api-base) API_BASE="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --token) EXTRA_ARGS+=(--token "$2"); shift 2 ;;
    --no-prs) EXTRA_ARGS+=(--no-prs); shift ;;
    -h|--help)
      grep '^#' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

mkdir -p "${REPORT_DIR}"

# Auto-source repo-root .env if present so PORTAL_TOKEN/ORCABUS_TOKEN are available.
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
if [[ -f "${REPO_ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${REPO_ROOT}/.env"
  set +a
fi

echo "==> Collecting deployment status (look-back: ${DAYS}d, api: ${API_BASE})" >&2
python3 "${SCRIPT_DIR}/collect_deploy_status.py" \
  --api-base "${API_BASE}" \
  --days "${DAYS}" \
  --out "${JSON_OUT}" \
  "${EXTRA_ARGS[@]}"

echo "==> Rendering markdown report" >&2
python3 "${SCRIPT_DIR}/render_report.py" --in "${JSON_OUT}" --out "${OUT}"

echo "" >&2
echo "Report:      ${OUT}" >&2
echo "Raw JSON:    ${JSON_OUT}" >&2
echo "" >&2
echo "Tip: ask Kiro to read ${JSON_OUT} and expand the 'Significant application changes' section into prose." >&2
