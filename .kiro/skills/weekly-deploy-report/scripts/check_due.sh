#!/usr/bin/env bash
#
# check_due.sh — SessionStart guard for the weekly deployment report.
#
# Exits 0 and prints a short nudge (to stdout, forwarded into the agent context
# by the SessionStart hook) only when a report for the current ISO week does not
# yet exist in scratch/. Otherwise prints nothing. Always exits 0 so it never
# blocks a session.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
SCRATCH_DIR="${REPO_ROOT}/scratch"

# Current ISO year-week, e.g. 2026-W35
CURRENT_WEEK="$(date -u +%G-W%V)"

# A report is "present" for this week if any dated report file in scratch/
# carries a date that falls in the current ISO week.
already_done=0
if [[ -d "${SCRATCH_DIR}" ]]; then
  for f in "${SCRATCH_DIR}"/deployment-status-report-*.md; do
    [[ -e "$f" ]] || continue
    # Extract YYYY-MM-DD from the filename.
    file_date="$(basename "$f" | sed -n 's/^deployment-status-report-\([0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}\)\.md$/\1/p')"
    [[ -n "$file_date" ]] || continue
    file_week="$(date -u -d "$file_date" +%G-W%V 2>/dev/null || echo '')"
    if [[ "$file_week" == "$CURRENT_WEEK" ]]; then
      already_done=1
      break
    fi
  done
fi

if [[ "$already_done" -eq 0 ]]; then
  cat <<EOF
[weekly-deploy-report] No production deployment report exists for the current week (${CURRENT_WEEK}).
When appropriate, offer to generate it using the 'weekly-deploy-report' skill
(.kiro/skills/weekly-deploy-report/scripts/run.sh --days 7). Requires ORCABUS_TOKEN and gh auth.
EOF
fi

exit 0
