#!/usr/bin/env python3
"""
render_report.py

Step 3 of the weekly deployment report (deterministic fallback renderer).

Takes the JSON produced by collect_deploy_status.py and renders a markdown
report describing, per service, the delta between what is deployed in production
and the tip of `main`, plus a high-level cross-service overview.

This renderer is intentionally mechanical: it summarises commit counts, PR
titles, and flags significant changes heuristically (by conventional-commit
prefix and PR labels). For a richer, prose "significant application changes"
narrative, the Kiro agent should read the same JSON and write the summary — see
SKILL.md. This script guarantees a useful report even without the agent.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

# Heuristics for flagging "significant" changes.
SIGNIFICANT_COMMIT_PREFIXES = ("feat", "feat!", "breaking", "perf")
BREAKING_MARKERS = ("!:", "breaking change", "breaking-change")
SIGNIFICANT_LABELS = {"breaking-change", "major", "migration", "schema-change", "feature"}


def is_significant_commit(title: str) -> bool:
    low = title.lower()
    if any(marker in low for marker in BREAKING_MARKERS):
        return True
    prefix = low.split(":", 1)[0].strip()
    return prefix in SIGNIFICANT_COMMIT_PREFIXES


def pr_is_significant(pr: dict) -> bool:
    labels = {(l.get("name") or "").lower() for l in pr.get("labels", [])}
    if labels & SIGNIFICANT_LABELS:
        return True
    return is_significant_commit(pr.get("title", ""))


def short(sha: str | None) -> str:
    return (sha or "")[:12] if sha else "—"


def _code_author(author: dict | None) -> str:
    if not author:
        return "unknown"
    login = author.get("login")
    if login:
        return f"@{login}"
    return author.get("name") or "unknown"


# Shown wherever we list a code author, so nobody reads it as "the deployer".
_DEPLOYER_CAVEAT = (
    "_The deploy-status data does not record who triggered each deployment "
    "(CloudFormation stack events carry no principal). The **code author** column "
    "below is who wrote the commit — not necessarily who deployed it._"
)


def render_deployment_health(deployments: list[dict], lookback: int) -> list[str]:
    """
    A deliberately blunt "name and shame" section flagging poor prod deploy
    hygiene in the window: dirty builds, repeated same-commit redeploys, and
    failed/rolled-back deploys.

    Attribution honesty: we cannot name the *deployer* (not in the data). We show
    the *code author* as context only, clearly labelled, with a caveat.
    """
    lines: list[str] = ["## Deployment health (name and shame)", ""]
    if not deployments:
        lines.append(f"No production deployments in the last {lookback} days — nothing to shame.")
        lines.append("")
        return lines

    dirty = [d for d in deployments if d.get("dirty")]
    failed = [d for d in deployments if d.get("outcome") == "failed"]

    # Repeated same-commit: group deployments by (stack, commit); flag any group
    # that fired more than once, and fold in per-deployment collapse counts.
    from collections import defaultdict
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for d in deployments:
        groups[(d.get("stackName"), d.get("gitCommitId"))].append(d)
    repeated = {
        key: ds for key, ds in groups.items()
        if len(ds) > 1 or sum(x.get("collapsedEvents", 1) for x in ds) > 1
    }

    if not dirty and not failed and not repeated:
        lines.append("Clean sheet — every prod deployment this window was a distinct, committed, successful build. Gold stars all round.")
        lines.append("")
        return lines

    lines.append(_DEPLOYER_CAVEAT)
    lines.append("")

    if dirty:
        lines.append(f"### Dirty deploys ({len(dirty)})")
        lines.append("")
        lines.append("Deployed to **production** from an uncommitted working tree (`-dirty`) — the running artifact matches no commit on any branch:")
        lines.append("")
        lines.append("| When (UTC) | Stack | Commit | Code author |")
        lines.append("|---|---|---|---|")
        for d in dirty:
            lines.append(
                f"| {d.get('modificationTimestamp', '?')} | `{d.get('stackName', '')}` "
                f"| `{d.get('gitCommitId', '')}` | {_code_author(d.get('commit_author'))} |"
            )
        lines.append("")

    if repeated:
        lines.append(f"### Repeated same-commit redeploys ({len(repeated)})")
        lines.append("")
        lines.append("Same stack, same commit, deployed to prod more than once in the window — usually hand-deploying to debug rather than shipping through the pipeline:")
        lines.append("")
        lines.append("| Stack | Commit | Times | Code author |")
        lines.append("|---|---|---:|---|")
        for (stack, commit), ds in sorted(
            repeated.items(), key=lambda kv: sum(x.get("collapsedEvents", 1) for x in kv[1]), reverse=True
        ):
            times = sum(x.get("collapsedEvents", 1) for x in ds)
            author = _code_author(next((x.get("commit_author") for x in ds if x.get("commit_author")), None))
            lines.append(f"| `{stack}` | `{commit}` | {times} | {author} |")
        lines.append("")

    if failed:
        lines.append(f"### Failed / rolled-back deploys ({len(failed)})")
        lines.append("")
        lines.append("| When (UTC) | Stack | Status | Commit | Code author |")
        lines.append("|---|---|---|---|---|")
        for d in failed:
            lines.append(
                f"| {d.get('modificationTimestamp', '?')} | `{d.get('stackName', '')}` "
                f"| `{d.get('status', '')}` | `{d.get('gitCommitId') or '—'}` | {_code_author(d.get('commit_author'))} |"
            )
        lines.append("")

    return lines


def render(doc: dict) -> str:
    services = doc.get("services", [])
    generated_at = doc.get("generatedAt", datetime.now(timezone.utc).isoformat())
    lookback = doc.get("lookbackDays", 7)
    org = doc.get("githubOrg", "OrcaBus")

    lines: list[str] = []
    lines.append("# OrcaBus Production Deployment Report")
    lines.append("")
    lines.append(f"- Generated: `{generated_at}`")
    lines.append(f"- Look-back window: last **{lookback}** days")
    lines.append(f"- Source: `{doc.get('apiBase', 'deploy-status API')}` + github.com/{org}")
    lines.append("")

    # --- High-level overview -------------------------------------------------
    up_to_date = [s for s in services if s.get("resolved") and (s.get("behind_by") == 0)]
    pending = [s for s in services if s.get("resolved") and (s.get("behind_by") or 0) > 0]
    unresolved = [s for s in services if not s.get("resolved")]
    significant_services = []
    for s in pending:
        sig_commits = [c for c in s.get("commits", []) if is_significant_commit(c.get("title", ""))]
        sig_prs = [p for p in s.get("recent_prs", []) if pr_is_significant(p)]
        if sig_commits or sig_prs:
            significant_services.append((s, sig_commits, sig_prs))

    deployments = doc.get("deployments", [])
    deploy_ok = [d for d in deployments if d.get("outcome") == "success"]
    deploy_bad = [d for d in deployments if d.get("outcome") == "failed"]
    deployed_stacks = {d.get("stackName") for d in deployments}

    lines.append("## High-level overview")
    lines.append("")
    lines.append(f"- **{len(services)}** production services tracked")
    lines.append(f"- **{len(deployments)}** production deployment(s) in the last {lookback} days "
                 f"across **{len(deployed_stacks)}** stack(s) "
                 f"({len(deploy_ok)} succeeded, {len(deploy_bad)} failed/rolled back)")
    lines.append(f"- **{len(up_to_date)}** already at `main`")
    lines.append(f"- **{len(pending)}** with undeployed changes on `main`")
    if unresolved:
        lines.append(f"- **{len(unresolved)}** could not be resolved (needs attention)")
    lines.append("")

    # --- Deployments to production in the window -----------------------------
    lines.append(f"## Deployments to production (last {lookback} days)")
    lines.append("")
    if not deployments:
        lines.append(f"No production deployments recorded in the last {lookback} days.")
        lines.append("")
    else:
        lines.append("| When (UTC) | Stack | Outcome | Commit |")
        lines.append("|---|---|:---:|---|")
        for d in deployments:  # newest-first from the collector
            outcome = "ok" if d.get("outcome") == "success" else "**FAILED**"
            repeats = d.get("collapsedEvents", 1)
            rep_note = f" (x{repeats})" if repeats and repeats > 1 else ""
            lines.append(
                f"| {d.get('modificationTimestamp', '?')} | `{d.get('stackName', '')}`{rep_note} "
                f"| {outcome} | `{short(d.get('gitCommitId'))}` |"
            )
        lines.append("")
        if deploy_bad:
            lines.append(f"{len(deploy_bad)} deployment(s) failed or rolled back — see the FAILED rows above.")
            lines.append("")

    # --- Deployment health (name and shame) ---------------------------------
    lines.extend(render_deployment_health(deployments, lookback))

    if pending:
        lines.append("### Services with pending changes (deploy would update these)")
        lines.append("")
        lines.append("| Service | Repo | Commits behind | Significant? | Deployed | main |")
        lines.append("|---|---|---:|:---:|---|---|")
        sig_repos = {s["repo"] for s, _, _ in significant_services}
        for s in sorted(pending, key=lambda x: (x.get("behind_by") or 0), reverse=True):
            flag = "yes" if s["repo"] in sig_repos else ""
            lines.append(
                f"| {s['service']} | `{s['repo']}` | {s.get('behind_by', '?')} | {flag} "
                f"| `{short(s.get('deployed_commit'))}` | `{short(s.get('main_commit'))}` |"
            )
        lines.append("")

    if significant_services:
        lines.append("### Significant application changes")
        lines.append("")
        lines.append("These services have changes on `main` that look impactful (features, breaking changes, migrations):")
        lines.append("")
        for s, sig_commits, sig_prs in significant_services:
            lines.append(f"- **{s['service']}** (`{s['repo']}`)")
            for pr in sig_prs:
                lines.append(f"  - PR #{pr.get('number')}: {pr.get('title')}  <{pr.get('url')}>")
            for c in sig_commits:
                if not sig_prs:
                    lines.append(f"  - `{c.get('sha')}` {c.get('title')}")
        lines.append("")

    if up_to_date:
        lines.append("### Up to date")
        lines.append("")
        lines.append(", ".join(f"`{s['service']}`" for s in up_to_date))
        lines.append("")

    if unresolved:
        lines.append("### Needs attention")
        lines.append("")
        for s in unresolved:
            note = "; ".join(s.get("notes", [])) or "unresolved"
            lines.append(f"- **{s['service']}** (`{s['repo']}`): {note}")
        lines.append("")

    # --- Per-service detail --------------------------------------------------
    lines.append("---")
    lines.append("")
    lines.append("## Per-service detail")
    lines.append("")
    for s in sorted(services, key=lambda x: x.get("service", "")):
        lines.append(f"### {s['service']}")
        lines.append("")
        lines.append(f"- Repo: `{org}/{s['repo']}`")
        lines.append(f"- Stack: `{s.get('stack_name', '')}`")
        lines.append(f"- Deployed status: `{s.get('deployed_status') or 'unknown'}`")
        lines.append(f"- Deployed commit: `{short(s.get('deployed_commit'))}`  "
                     f"({s.get('deployed_timestamp') or 'unknown time'})")
        lines.append(f"- `main` HEAD: `{short(s.get('main_commit'))}`")
        behind = s.get("behind_by")
        if behind == 0:
            lines.append("- Status: **up to date** with `main`")
        elif behind:
            lines.append(f"- Status: **{behind} commit(s) behind** `main`")
        else:
            lines.append("- Status: **unknown** (comparison unavailable)")
        if s.get("comparison_source") == "local":
            lines.append("- Comparison source: **local clone** (deployed commit is off the remote `main`)")
        lines.append("")

        commits = s.get("commits", [])
        if commits:
            lines.append(f"Undeployed commits ({len(commits)}):")
            lines.append("")
            for c in commits[:50]:
                marker = " ⚑" if is_significant_commit(c.get("title", "")) else ""
                lines.append(f"- `{c.get('sha')}` {c.get('title')}{marker}")
            if len(commits) > 50:
                lines.append(f"- … and {len(commits) - 50} more")
            lines.append("")

        prs = s.get("recent_prs", [])
        if prs:
            lines.append(f"Merged to `main` in the last {lookback} days ({len(prs)}) — development activity, not necessarily deployed:")
            lines.append("")
            for pr in prs:
                marker = " ⚑" if pr_is_significant(pr) else ""
                lines.append(f"- #{pr.get('number')} {pr.get('title')}{marker}  <{pr.get('url')}>")
            lines.append("")

        notes = s.get("notes", [])
        if notes:
            lines.append("Notes:")
            for n in notes:
                lines.append(f"- {n}")
            lines.append("")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the deployment status markdown report.")
    parser.add_argument("--in", dest="infile", default="-", help="Input JSON path, or '-' for stdin.")
    parser.add_argument("--out", default="-", help="Output markdown path, or '-' for stdout.")
    args = parser.parse_args()

    if args.infile == "-":
        doc = json.load(sys.stdin)
    else:
        with open(args.infile, encoding="utf-8") as fh:
            doc = json.load(fh)

    md = render(doc)
    if args.out == "-":
        print(md)
    else:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(md)
        print(f"Wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
