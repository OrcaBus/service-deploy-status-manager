#!/usr/bin/env python3
"""
collect_deploy_status.py

Step 1 + 2 of the weekly deployment report.

Collects the currently-deployed state of every tracked OrcaBus microservice by:
  1. Querying the deploy-status manager API (getAllStacksSummary) for the latest
     event per stack, including the deployed git commit id.
  2. Filtering to production stacks only.
  3. Mapping each production stack to its GitHub repository.
  4. For each repo, resolving the tip of `main` and computing the commit-range
     between the deployed commit and `main` HEAD via the GitHub compare API
     (using the `gh` CLI so existing auth is reused).

Output: a single JSON document on stdout describing every service, its deployed
commit, the target `main` commit, and the list of commits/PRs in between. This
JSON is consumed by the report-generation step (the agent, or render_report.py).

No AWS credentials are strictly required for the API path: the deploy-status API
already reflects CloudFormation state. If --use-cfn is passed, the deployed
commit ids are cross-checked directly against CloudFormation stack outputs using
boto3 (requires AWS creds for the prod account).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Any, Optional
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

DEFAULT_API_BASE = "https://deploy-status.prod.umccr.org"
GITHUB_ORG = "OrcaBus"

# Production CloudFormation stacks are prefixed "OrcaBusProd-" (a few legacy ones
# use just "Prod-"). The remainder is a messy mix of naming conventions, e.g.:
#   OrcaBusProd-WorkflowManagerStack
#   OrcaBusProd-FileManagerStatefulStack
#   OrcaBusProd-DeployStatusStatelessDeployStack
#   OrcaBusProd-StatelessFastqSyncManager        (Stateful/Stateless as a prefix)
#   OrcaBusProd-OrcaBusStatelessPdxServiceStack  (repeated OrcaBus token)
#   Prod-StepsS3CopyStack                        (no OrcaBus prefix)
# We only care about production stacks for a "what will change if we deploy" view.
PROD_STACK_RE = re.compile(r"^(?:OrcaBus)?Prod-(?P<body>.+)$")


def eprint(*args: Any) -> None:
    print(*args, file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# deploy-status API
# ---------------------------------------------------------------------------
def fetch_all_stacks_summary(api_base: str, token: Optional[str]) -> list[dict]:
    url = api_base.rstrip("/") + "/api/v1/deployStatus/getAllStacksSummary"
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urlrequest.Request(url, headers=headers)
    try:
        with urlrequest.urlopen(req, timeout=60) as resp:
            payload = resp.read().decode("utf-8")
    except HTTPError as exc:
        eprint(f"ERROR: deploy-status API returned HTTP {exc.code} for {url}")
        eprint(exc.read().decode("utf-8", errors="replace"))
        raise
    except URLError as exc:
        eprint(f"ERROR: could not reach deploy-status API at {url}: {exc.reason}")
        raise
    data = json.loads(payload)
    if not isinstance(data, list):
        raise ValueError(f"Unexpected API response (expected list): {type(data)}")
    return data


# CloudFormation terminal statuses that represent the end of a deployment.
# A single deploy emits several in-progress events; we key "a deployment
# happened" off these terminal states only.
DEPLOY_SUCCESS_STATUSES = {
    "CREATE_COMPLETE",
    "UPDATE_COMPLETE",
    "IMPORT_COMPLETE",
}
DEPLOY_FAILURE_STATUSES = {
    "CREATE_FAILED",
    "UPDATE_FAILED",
    "ROLLBACK_COMPLETE",
    "ROLLBACK_FAILED",
    "UPDATE_ROLLBACK_COMPLETE",
    "UPDATE_ROLLBACK_FAILED",
    "IMPORT_ROLLBACK_COMPLETE",
    "IMPORT_ROLLBACK_FAILED",
    "DELETE_COMPLETE",
    "DELETE_FAILED",
}
DEPLOY_TERMINAL_STATUSES = DEPLOY_SUCCESS_STATUSES | DEPLOY_FAILURE_STATUSES


def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def fetch_stack_events(api_base: str, token: Optional[str], stack_ref: str, pages: int = 3) -> list[dict]:
    """
    Fetch recent events for a single stack (newest first). `stack_ref` may be the
    CloudFormation UUID or the orcabus id — the API accepts both. Reads up to
    `pages` pages of 100 to cover a week of activity without pulling full history.
    """
    events: list[dict] = []
    for page in range(1, pages + 1):
        url = (
            api_base.rstrip("/")
            + f"/api/v1/deployStatus/{stack_ref}/events?rowsPerPage=100&page={page}"
        )
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urlrequest.Request(url, headers=headers)
        try:
            with urlrequest.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (HTTPError, URLError) as exc:
            eprint(f"WARN: could not fetch events page {page} for stack {stack_ref}: {exc}")
            break
        batch = data.get("results", data) if isinstance(data, dict) else data
        if not batch:
            break
        events.extend(batch)
        # Stop early once the oldest event on this page predates any plausible
        # window (events are newest-first); the caller filters precisely.
        if len(batch) < 100:
            break
    return events


def collect_deploy_events(
    api_base: str,
    token: Optional[str],
    stacks: list[dict],
    since: datetime,
) -> list[dict]:
    """
    For the given production stacks, return the list of terminal deployment
    events (success or failure) that occurred at/after `since`, newest first.
    Each returned dict carries stackName, status, modificationTimestamp,
    gitCommitId (if any), and an `outcome` of "success" | "failed".
    """
    deploys: list[dict] = []
    for stack in stacks:
        ref = stack.get("stackId") or stack.get("stackOrcabusId")
        if not ref:
            continue
        for ev in fetch_stack_events(api_base, token, ref):
            status = ev.get("status")
            if status not in DEPLOY_TERMINAL_STATUSES:
                continue
            ts = _parse_ts(ev.get("modificationTimestamp"))
            if ts is None or ts < since:
                continue
            deploys.append({
                "stackName": ev.get("stackName") or stack.get("stackName"),
                "status": status,
                "outcome": "success" if status in DEPLOY_SUCCESS_STATUSES else "failed",
                "modificationTimestamp": ev.get("modificationTimestamp"),
                "gitCommitId": ev.get("gitCommitId"),
            })
    deploys.sort(key=lambda d: d.get("modificationTimestamp") or "", reverse=True)
    deploys = _dedupe_deployments(deploys)
    _enrich_deployments(deploys)
    return deploys


def _enrich_deployments(deploys: list[dict]) -> None:
    """
    Annotate each deployment in place with `dirty` (built from an uncommitted
    tree) and the resolved `repo`, plus the commit's *code author* purely as
    context.

    NOTE ON ATTRIBUTION: the deploy-status data (and the underlying CloudFormation
    Stack Status Change event) does NOT record who triggered the deployment — no
    IAM principal or user. So we cannot say who *pushed* a build to prod. The
    commit author below is who *wrote the code*, which is a different person from
    the deployer (especially for `-dirty` hand-deploys). It is labelled as such
    and must never be presented as "the deployer".
    """
    author_cache: dict[tuple, Optional[dict]] = {}
    for d in deploys:
        commit = d.get("gitCommitId") or ""
        d["dirty"] = commit.endswith("-dirty")

        m = PROD_STACK_RE.match(d.get("stackName", ""))
        repo = stack_to_repo(normalise_service(m.group("body"))) if m else None
        d["repo"] = repo

        if commit and repo:
            key = (repo, commit)
            if key not in author_cache:
                author_cache[key] = resolve_commit_author(repo, commit)
            d["commit_author"] = author_cache[key]
        else:
            d["commit_author"] = None


# CloudFormation can emit several terminal events for one logical deployment
# (nested-stack updates, cleanup churn). Collapse runs of the same stack + status
# + commit that land within a short window into a single deployment, keyed on the
# most recent timestamp of the run.
DEPLOY_DEDUPE_WINDOW = timedelta(minutes=30)


def _dedupe_deployments(deploys: list[dict]) -> list[dict]:
    collapsed: list[dict] = []
    for d in deploys:  # already newest-first
        ts = _parse_ts(d.get("modificationTimestamp"))
        merged = False
        for kept in collapsed:
            if (
                kept["stackName"] == d["stackName"]
                and kept["status"] == d["status"]
                and kept.get("gitCommitId") == d.get("gitCommitId")
            ):
                kept_ts = _parse_ts(kept.get("modificationTimestamp"))
                if ts is not None and kept_ts is not None and abs(kept_ts - ts) <= DEPLOY_DEDUPE_WINDOW:
                    kept["collapsedEvents"] = kept.get("collapsedEvents", 1) + 1
                    merged = True
                    break
        if not merged:
            d = {**d, "collapsedEvents": 1}
            collapsed.append(d)
    return collapsed


# ---------------------------------------------------------------------------
# stack -> repo mapping
# ---------------------------------------------------------------------------
# Reduce a raw CloudFormation stack body to a stable service key by stripping the
# Stateful/Stateless/Deploy/Stack/Infrastructure noise tokens that appear (in
# varying positions) across the different naming conventions in use.
def normalise_service(body: str) -> str:
    b = re.sub(r"^OrcaBus", "", body)           # some stacks repeat the OrcaBus token
    b = re.sub(r"(Stateful|Stateless)", "", b)  # remove statefulness marker anywhere
    b = re.sub(r"DeployStack$", "", b)
    b = re.sub(r"Stack$", "", b)
    b = re.sub(r"Infrastructure$", "", b)
    return b


# Convert a CamelCase service token into the kebab-case repo suffix used under
# github.com/OrcaBus/service-<name>.
#   "DeployStatusManager" -> "deploy-status-manager"
def camel_to_kebab(name: str) -> str:
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", name)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1-\2", s)
    return s.lower()


# Many prod stacks do not map cleanly to `service-<kebab>` — the stateful half of
# a service, acronyms, and legacy names all differ. These overrides are keyed on
# the normalised service token (output of normalise_service) and were verified
# against the live github.com/OrcaBus repo list. Anything not resolved here and
# not matching the kebab guess is flagged in the report's "Needs attention"
# section — extend this map when that happens.
REPO_OVERRIDES: dict[str, str] = {
    "DeployStatus": "service-deploy-status-manager",
    "DragenTso500Ctdna": "service-dragen-tso500-ctdna-pipeline-manager",
    "DragenWgtsDnaPipeline": "service-dragen-wgts-dna-pipeline-manager",
    "Fastq": "service-fastq-manager",
    "FastqDecompression": "service-fastq-decompression-manager",
    "FileManager": "service-filemanager",
    "Icav2DataCopyService": "service-icav2-data-copy-manager",
    "OncoanalyserWgtsBothPipeline": "service-oncoanalyser-wgts-both-pipeline-manager",
    "OncoanalyserWgtsDnaPipeline": "service-oncoanalyser-wgts-dna-pipeline-manager",
    "OncoanalyserWgtsRnaPipeline": "service-oncoanalyser-wgts-rna-pipeline-manager",
    "SashPipeline": "service-sash-pipeline-manager",
    "OrcaUI": "orca-ui",
    # Data sharing tracker does not yet extend GitStack, so the DataSharing
    # stacks correspond to the manager repo.
    "DataSharing": "service-data-sharing-manager",
    # "PdxService" stacks are the PierianDx TSO500 ctDNA pipeline manager.
    "PdxService": "service-pieriandx-tso500-ctdna-pipeline-manager",
    # Pipeline managers whose stack tokens don't match the kebab guess. Verified
    # against the live github.com/OrcaBus repo list (main HEADs match the
    # deployed commits reported by deploy-status).
    "-BclconvertInteropQc-Microservice": "service-bclconvert-interop-qc-pipeline-manager",
    "ArribaWgtsRnaPipeline": "service-arriba-wgts-rna-pipeline-manager",
    "BSSHToAWSS3Copy": "service-bssh-to-aws-s3-copy-manager",
    "BclConvert": "service-bclconvert-manager",
    "DragenWgtsRnaPipeline": "service-dragen-wgts-rna-pipeline-manager",
    "FastqUnarchiving": "service-fastq-unarchiving-manager",
    "RnasumPipeline": "service-rnasum-pipeline-manager",
    # Intentionally unmapped (no confirmed GitStack repo yet) — these surface in
    # the report's "Needs attention" section rather than being mis-attributed:
    #   PostgresManager, AuthorizationManager, StepsS3Copy
}


def stack_to_repo(service_token: str) -> str:
    if service_token in REPO_OVERRIDES:
        return REPO_OVERRIDES[service_token]
    return f"service-{camel_to_kebab(service_token)}"


# ---------------------------------------------------------------------------
# GitHub via gh CLI
# ---------------------------------------------------------------------------
def gh_api(path: str) -> Any:
    """Call the GitHub REST API through the gh CLI (reuses gh auth)."""
    proc = subprocess.run(
        ["gh", "api", path, "-H", "Accept: application/vnd.github+json"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"gh api {path} failed: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def get_main_head(repo: str) -> Optional[str]:
    try:
        data = gh_api(f"/repos/{GITHUB_ORG}/{repo}/commits/main")
        return data.get("sha")
    except RuntimeError as exc:
        eprint(f"WARN: could not resolve main HEAD for {repo}: {exc}")
        return None


def compare_commits(repo: str, base: str, head: str) -> Optional[dict]:
    """Return the GitHub compare payload between base (deployed) and head (main)."""
    try:
        return gh_api(f"/repos/{GITHUB_ORG}/{repo}/compare/{base}...{head}")
    except RuntimeError as exc:
        eprint(f"WARN: compare {base}...{head} failed for {repo} via GitHub API: {exc}")
        return None


# ---------------------------------------------------------------------------
# Local git fallback
# ---------------------------------------------------------------------------
# When the deployed commit has been rebased/force-pushed off `main`, GitHub's
# compare API 404s because the commit no longer exists on the remote. A local
# clone often still has the orphaned commit in its object store, so we can
# compute the delta locally. Roots to search for clones (first match wins).
LOCAL_CLONE_ROOTS = [
    os.path.expanduser("~/GitHub/ORCABUS"),
    os.path.expanduser("~/PyCharmProjects/ORCABUS"),
    os.path.expanduser("~/ORCABUS"),
]


def find_local_clone(repo: str) -> Optional[str]:
    for root in LOCAL_CLONE_ROOTS:
        candidate = os.path.join(root, repo)
        if os.path.isdir(os.path.join(candidate, ".git")):
            return candidate
    return None


def _git(repo_dir: str, *args: str) -> Optional[str]:
    proc = subprocess.run(
        ["git", "-C", repo_dir, *args], capture_output=True, text=True
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def compare_commits_local(repo: str, base: str, head: str) -> Optional[dict]:
    """
    Fall back to a local clone to compare base..head when the GitHub API cannot.
    Returns a payload shaped like the subset of the GitHub compare response the
    caller uses (ahead_by, behind_by, commits[].commit.{message,author}), plus a
    `_source: "local"` marker. Returns None if no local clone or the base commit
    is unknown locally.
    """
    repo_dir = find_local_clone(repo)
    if repo_dir is None:
        return None

    # Make sure we have up-to-date remote refs, best-effort.
    _git(repo_dir, "fetch", "--all", "--quiet")

    # Base commit must exist locally.
    if _git(repo_dir, "cat-file", "-t", base) != "commit":
        return None

    # Resolve head (main); prefer origin/main, fall back to main.
    head_ref = head
    if _git(repo_dir, "cat-file", "-t", head) != "commit":
        head_ref = _git(repo_dir, "rev-parse", "origin/main") or "origin/main"

    ahead = _git(repo_dir, "rev-list", "--count", f"{base}..{head_ref}")   # commits head has that base lacks
    behind = _git(repo_dir, "rev-list", "--count", f"{head_ref}..{base}")  # commits base has that head lacks
    if ahead is None:
        return None

    log = _git(
        repo_dir, "log", "--format=%H%x1f%an%x1f%aI%x1f%s", f"{base}..{head_ref}"
    ) or ""
    commits = []
    for line in log.splitlines():
        parts = line.split("\x1f")
        if len(parts) != 4:
            continue
        sha, author, date, subject = parts
        commits.append({
            "sha": sha,
            "commit": {"message": subject, "author": {"name": author, "date": date}},
        })

    return {
        "ahead_by": int(ahead),
        "behind_by": int(behind) if behind is not None else None,
        "commits": commits,
        "_source": "local",
        "_local_path": repo_dir,
    }


def resolve_commit_author(repo: str, commit: str) -> Optional[dict]:
    """
    Best-effort author lookup for a deployed commit, so we can attribute dirty /
    churny prod deploys. Tries the GitHub API first (gives a login handle), then a
    local clone (gives name/email). Returns {"name","login","source"} or None.
    The commit may carry a "-dirty" suffix — strip it before lookup.
    """
    ref = commit[: -len("-dirty")] if commit.endswith("-dirty") else commit
    if not ref:
        return None

    # GitHub API — yields the account login where available.
    try:
        data = gh_api(f"/repos/{GITHUB_ORG}/{repo}/commits/{ref}")
        author = data.get("author") or {}
        commit_author = (data.get("commit") or {}).get("author") or {}
        login = author.get("login")
        name = commit_author.get("name")
        if login or name:
            return {"name": name, "login": login, "source": "github"}
    except RuntimeError:
        pass

    # Local clone — resolves orphaned/force-pushed commits the remote no longer has.
    repo_dir = find_local_clone(repo)
    if repo_dir is not None and _git(repo_dir, "cat-file", "-t", ref) == "commit":
        name = _git(repo_dir, "show", "-s", "--format=%an", ref)
        email = _git(repo_dir, "show", "-s", "--format=%ae", ref)
        if name:
            return {"name": name, "login": None, "email": email, "source": "local"}

    return None


def list_recent_prs(repo: str, since: datetime) -> list[dict]:
    """List merged PRs into main since the given datetime (best-effort)."""
    try:
        proc = subprocess.run(
            [
                "gh", "pr", "list",
                "--repo", f"{GITHUB_ORG}/{repo}",
                "--state", "merged",
                "--base", "main",
                "--limit", "100",
                "--json", "number,title,mergedAt,author,url,labels",
            ],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            eprint(f"WARN: gh pr list failed for {repo}: {proc.stderr.strip()}")
            return []
        prs = json.loads(proc.stdout)
    except (RuntimeError, json.JSONDecodeError) as exc:
        eprint(f"WARN: could not list PRs for {repo}: {exc}")
        return []

    recent = []
    for pr in prs:
        merged_at = pr.get("mergedAt")
        if not merged_at:
            continue
        try:
            merged_dt = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))
        except ValueError:
            continue
        if merged_dt >= since:
            recent.append(pr)
    return recent


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class ServiceDiff:
    service: str
    repo: str
    stack_name: str
    deployed_status: Optional[str] = None
    deployed_commit: Optional[str] = None
    deployed_timestamp: Optional[str] = None
    main_commit: Optional[str] = None
    behind_by: Optional[int] = None  # commits main is ahead of deployed
    ahead_by: Optional[int] = None
    commits: list[dict] = field(default_factory=list)
    recent_prs: list[dict] = field(default_factory=list)
    comparison_source: Optional[str] = None  # "github" | "local"
    notes: list[str] = field(default_factory=list)
    resolved: bool = True


def summarise_commit(commit: dict) -> dict:
    c = commit.get("commit", {})
    message = c.get("message", "") or ""
    return {
        "sha": commit.get("sha", "")[:12],
        "title": message.splitlines()[0] if message else "",
        "author": (c.get("author") or {}).get("name"),
        "date": (c.get("author") or {}).get("date"),
    }


def build(
    summaries: list[dict],
    since: datetime,
    include_prs: bool,
) -> list[ServiceDiff]:
    results: list[ServiceDiff] = []

    # Collapse all stacks that map to the same repo into one entry. A single repo
    # can produce several stacks (stateful + stateless, and sometimes a separate
    # "...Manager" stateless stack). Key on the resolved repo so those merge, and
    # prefer the stack that reports a git commit id, breaking ties by the most
    # recent modification timestamp.
    prod: dict[str, dict] = {}
    for item in summaries:
        stack_name = item.get("stackName", "")
        m = PROD_STACK_RE.match(stack_name)
        if not m:
            continue
        service = normalise_service(m.group("body"))
        repo = stack_to_repo(service)
        item = {**item, "_service": service, "_repo": repo}

        existing = prod.get(repo)
        if existing is None:
            prod[repo] = item
            continue
        # Prefer an entry that carries a commit id; then prefer the newer one.
        new_has = bool(item.get("gitCommitId"))
        old_has = bool(existing.get("gitCommitId"))
        if new_has and not old_has:
            prod[repo] = item
        elif new_has == old_has:
            if (item.get("modificationTimestamp") or "") > (existing.get("modificationTimestamp") or ""):
                prod[repo] = item

    for repo, item in sorted(prod.items(), key=lambda kv: kv[1]["_service"]):
        service = item["_service"]
        diff = ServiceDiff(
            service=service,
            repo=repo,
            stack_name=item.get("stackName", ""),
            deployed_status=item.get("status"),
            deployed_commit=item.get("gitCommitId"),
            deployed_timestamp=item.get("modificationTimestamp"),
        )

        if not diff.deployed_commit:
            diff.notes.append("No git commit id reported by deploy-status (stack may not extend GitStack).")

        main_head = get_main_head(repo)
        if main_head is None:
            diff.resolved = False
            diff.notes.append(f"Could not resolve github.com/{GITHUB_ORG}/{repo} main branch — repo name may need an override.")
            results.append(diff)
            continue
        diff.main_commit = main_head

        if diff.deployed_commit:
            # Deployed commit ids can carry a "-dirty" suffix (built from a dirty
            # working tree) or be abbreviated. Strip "-dirty" for the comparison
            # and flag it, since a dirty build means prod does not correspond to a
            # clean commit on any branch.
            ref = diff.deployed_commit
            if ref.endswith("-dirty"):
                ref = ref[: -len("-dirty")]
                diff.notes.append("Deployed commit was a *dirty* build (uncommitted changes at deploy time); comparison is against the base commit only.")
            cmp = compare_commits(repo, ref, main_head)
            source = "github"
            if cmp is None:
                # The commit may have been rebased/force-pushed off main and no
                # longer exists on the remote. Try a local clone, which often
                # still has the orphaned object.
                cmp = compare_commits_local(repo, ref, main_head)
                if cmp is not None:
                    source = "local"
                    diff.notes.append(
                        f"Deployed commit `{ref}` is not on the remote `main` "
                        f"(likely rebased/force-pushed); compared via local clone "
                        f"at `{cmp.get('_local_path')}`."
                    )
            if cmp is not None:
                diff.comparison_source = source
                diff.behind_by = cmp.get("ahead_by")   # commits main has that deployed lacks
                diff.ahead_by = cmp.get("behind_by")
                diff.commits = [summarise_commit(c) for c in cmp.get("commits", [])]
            else:
                diff.notes.append(f"Commit comparison unavailable — deployed ref `{diff.deployed_commit}` not found in {repo} history on GitHub or any local clone (rebased/force-pushed?).")

        if include_prs:
            diff.recent_prs = list_recent_prs(repo, since)

        results.append(diff)

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect OrcaBus prod deployment status vs main.")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help="deploy-status API base URL.")
    parser.add_argument("--token", default=None, help="Bearer token for the deploy-status API, if required.")
    parser.add_argument("--days", type=int, default=7, help="Look-back window in days for prod deployments and recent PRs (default 7).")
    parser.add_argument("--no-prs", action="store_true", help="Skip merged-PR enrichment.")
    parser.add_argument("--no-deploy-events", action="store_true", help="Skip per-stack prod deployment history (faster; uses only the latest snapshot).")
    parser.add_argument("--out", default="-", help="Output JSON path, or '-' for stdout.")
    args = parser.parse_args()

    since = datetime.now(timezone.utc) - timedelta(days=args.days)

    # Token precedence: --token flag, then PORTAL_TOKEN / ORCABUS_TOKEN env vars.
    token = args.token or os.environ.get("PORTAL_TOKEN") or os.environ.get("ORCABUS_TOKEN")

    eprint(f"Querying deploy-status API: {args.api_base}")
    summaries = fetch_all_stacks_summary(args.api_base, token)
    eprint(f"Received {len(summaries)} stack summaries; filtering to production stacks…")

    # Production stacks only (raw, un-collapsed — deployments happen per stack).
    prod_stacks = [s for s in summaries if PROD_STACK_RE.match(s.get("stackName", ""))]

    diffs = build(summaries, since=since, include_prs=not args.no_prs)
    eprint(f"Resolved {sum(1 for d in diffs if d.resolved)}/{len(diffs)} production services.")

    deployments: list[dict] = []
    if not args.no_deploy_events:
        eprint(f"Fetching per-stack deployment history for {len(prod_stacks)} prod stacks (last {args.days}d)…")
        deployments = collect_deploy_events(args.api_base, token, prod_stacks, since)
        n_ok = sum(1 for d in deployments if d["outcome"] == "success")
        n_bad = len(deployments) - n_ok
        eprint(f"Found {len(deployments)} prod deployment events in window ({n_ok} succeeded, {n_bad} failed/rolled back).")

    doc = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "apiBase": args.api_base,
        "lookbackDays": args.days,
        "githubOrg": GITHUB_ORG,
        "deployments": deployments,
        "services": [asdict(d) for d in diffs],
    }
    text = json.dumps(doc, indent=2, default=str)
    if args.out == "-":
        print(text)
    else:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        eprint(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
