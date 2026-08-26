---
name: weekly-deploy-report
description: >-
  Generate a weekly OrcaBus production deployment report. Scans CloudFormation
  production state via the deploy-status manager API to collect the currently
  deployed git commit per service, compares each against the tip of the repo's
  main branch, and produces a markdown summary of what would change if
  everything were deployed — with a high-level cross-service overview that
  highlights significant application changes. Use when asked for a deployment
  status report, a "what's pending for prod" summary, or the weekly deploy
  digest.
---

# Weekly Deployment Report

## What this does

Produces a report answering: **"If we deployed every OrcaBus service to
production right now, what would change?"**

Stages:

1. **Collect deployed state** — Query the deploy-status manager API
   (`getAllStacksSummary`), which reflects live CloudFormation state, to get the
   currently deployed git commit id for each production stack.
2. **Collect deployments in the window** — For each production stack, read its
   CloudFormation event history (`/{stack_id}/events`) and keep the terminal
   deployment events (success = `*_COMPLETE`, failure = `*_FAILED` / rollbacks)
   that occurred in the last N days. This is what actually got deployed to
   **production**, distinct from what merged to `main`.
3. **Diff against `main`** — For each production service, resolve the tip of its
   GitHub `main` branch and compute the commits between the deployed commit and
   `main` (the full gap, not time-boxed).
4. **Summarise** — Render a markdown report: a "Deployments to production (last N
   days)" table, a "Deployment health (name and shame)" section, a per-service
   pending-changes breakdown, and a high-level overview that flags significant
   application changes (features, breaking changes, schema/migration work).

### Deployment health (name and shame)

Flags poor prod deploy hygiene in the window: **dirty** deploys (`-dirty`
commit = built from an uncommitted tree), **repeated same-commit** redeploys of a
stack (hand-deploy/debug churn), and **failed/rolled-back** deploys.

**Attribution limitation (do not "fix" by attributing the deployer).** The
deploy-status data and the underlying CloudFormation Stack Status Change event do
**not** record who triggered a deployment — there is no IAM principal or user in
the event. So the report cannot name the deployer. The "Code author" column is
the author of the deployed _commit_ (resolved via GitHub/local git) and is shown
as context only, with an explicit caveat. It is often a different person from
whoever ran the deploy (especially for dirty hand-deploys). Never relabel it as
the deployer.

### Deployment vs merge activity (important distinction)

- **Deployments to production** come from the deploy-status event history and are
  time-boxed by `--days`. A logical deployment is a terminal CloudFormation event;
  near-duplicate completions for the same stack+commit within 30 minutes are
  collapsed into one (with an `xN` repeat count).
- **"Merged to `main`" PR list** (per service) is _development_ activity, not
  deployment — a merged PR may not be in prod yet. It is labelled as such.
- The **deployed-vs-`main` diff** is not time-boxed: it reports the full gap
  regardless of age.

## When to use

- The user asks for the weekly deployment report / deploy digest.
- The user asks what deployed to production recently / in the last week.
- The user asks what is pending for a production deploy, or how far behind prod
  is from `main` across services.
- Triggered on a schedule (see the companion hook / cron guidance below).

Use `--no-deploy-events` to skip the per-stack event history (faster; drops the
"Deployments to production" section and relies only on the latest snapshot).

## Prerequisites

- `python3`, `gh` (authenticated to the `OrcaBus` org), and network access to
  `https://deploy-status.prod.umccr.org` (note the `prod` segment — the bare
  `deploy-status.umccr.org` does not resolve).
- A Cognito JWT for the deploy-status API. It is auto-sourced from `PORTAL_TOKEN`
  in the repo-root `.env`; you can also export `PORTAL_TOKEN` / `ORCABUS_TOKEN`
  or pass `--token`. Without it the API call returns 401/403.
- The deploy-status API is behind Cognito and may require VPN / UMCCR network
  access to reach.

## How to run

Preferred one-shot entry point:

```sh
# PORTAL_TOKEN is auto-sourced from .env; no export needed if it's set there.
.kiro/skills/weekly-deploy-report/scripts/run.sh --days 7
```

This writes two files into `scratch/`:

- `deployment-status-<date>.json` — the raw collected diff (machine-readable).
- `deployment-status-report-<date>.md` — the rendered markdown report.

Run the stages separately if you need to:

```sh
# Stage 1 + 2: collect state and diff against main
python3 .kiro/skills/weekly-deploy-report/scripts/collect_deploy_status.py \
  --api-base https://deploy-status.prod.umccr.org --days 7 --out scratch/deploy.json

# Stage 3: deterministic markdown render
python3 .kiro/skills/weekly-deploy-report/scripts/render_report.py \
  --in scratch/deploy.json --out scratch/deployment-status-report.md
```

## Agent workflow (produce the richer narrative)

`render_report.py` gives a solid, deterministic report on its own. To deliver
the higher-value "significant application changes" narrative the user asked for,
do the following after running the scripts:

1. Run `run.sh` (or the two stages) to produce the JSON + markdown.
2. Read the generated `scratch/deployment-status-<date>.json`.
3. For services with pending changes, read the flagged commit titles and PRs.
   Where a change looks impactful but the intent is unclear, fetch the PR body
   with `gh pr view <n> --repo OrcaBus/<repo>` to understand it.
4. Rewrite the **"Significant application changes"** section of the markdown as
   prose: for each notable service, explain in one or two sentences what changes
   and why it matters (new capability, breaking API/event-schema change, data
   migration, dependency of other services). Group cross-service themes (e.g.
   "three services adopt the new WRSC schema").
5. Keep the deterministic per-service tables and detail intact below the
   narrative — they are the evidence backing the summary.

Focus the narrative on impact and risk, not commit counts. Call out anything
that changes a published event schema or an API contract, since other OrcaBus
services depend on those.

## Stack → repo mapping

Production stacks are prefixed `OrcaBusProd-` (a few use `Prod-`) and follow
several inconsistent conventions for the remainder — `Stateful`/`Stateless` may
be a prefix or embedded, and a `Deploy`/`Stack`/`Manager` suffix may or may not
appear. `normalise_service()` strips that noise to a service key, which
`stack_to_repo()` maps to a `github.com/OrcaBus/service-<name>` repo via a
verified `REPO_OVERRIDES` table (with a kebab-case fallback). All stacks that map
to the same repo are collapsed into one entry.

Deployed commit ids may carry a `-dirty` suffix (built from an uncommitted
working tree); the collector strips it for comparison and notes it. When the
report's **"Needs attention"** section flags an unresolved repo or a commit not
found in history, add/fix an entry in `REPO_OVERRIDES` and re-run. Some prod
stacks (e.g. AuthorizationManager, PostgresManager, StepsS3Copy) intentionally
remain unmapped until their repo is confirmed.

**Local-clone fallback.** If a deployed commit has been rebased or force-pushed
off `main`, GitHub's compare API 404s (the commit no longer exists on the
remote). The collector then falls back to a local clone — searched under
`~/GitHub/ORCABUS`, `~/PyCharmProjects/ORCABUS`, `~/ORCABUS` (see
`LOCAL_CLONE_ROOTS`) — which usually still holds the orphaned object, and
computes the delta locally. Such services are marked "Comparison source: local
clone" and noted as running an off-`main` commit. Keeping local clones roughly
up to date (a periodic `git fetch`) improves coverage.

## Scheduling

For unattended weekly runs, use cron (the report is a plain script):

```sh
# Mondays at 08:00 — adjust path and token sourcing as needed
0 8 * * 1 cd /path/to/service-deploy-status-manager && \
  .kiro/skills/weekly-deploy-report/scripts/run.sh --days 7 >> scratch/deploy-report.log 2>&1
# (run.sh auto-sources PORTAL_TOKEN from .env; ensure the token there is fresh)
```

Inside Kiro, the companion `weekly-deploy-report` SessionStart hook nudges you to
generate the report when a new week has started and none exists yet for the
current week.
