#input_type_name: SuggestOwnerInput
#output_type_name: SuggestOwnerResult
#function_name: suggest_owner

"""Suggest who actually has context on a bug, from the GitHub repo's history.

Strategy (deterministic, read-only on GitHub):
  1. Find the file path implicated by the bug (explicit hint, else parsed
     from the report text and reasoning).
  2. Get *line-level* blame on that file — who wrote the code that's actually
     there now, not just whoever committed most recently. Blame needs a PAT
     (GitHub's GraphQL API requires auth even for public repos).
  3. If no PAT is configured, fall back to weighting commit authors by how
     often they've touched the file — frequency of contribution, which is a
     much better context signal than "most recent commit," since a one-off
     contributor would otherwise unfairly outrank the person who wrote most
     of the file.
  4. Read CODEOWNERS; if a rule matches the path, that's the policy-assigned
     owner and takes precedence for the primary assignee — but the blame and
     commit candidates are kept and surfaced as alternates, since CODEOWNERS
     records policy, not who currently has the most context on this code.
  5. Write the top suggestion plus ranked alternates to the bug row.

No writes to GitHub happen here — this only ever proposes.
"""

import base64
import fnmatch
import re
from typing import Optional

import requests
from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod

GH = "https://api.github.com"
GH_GRAPHQL = "https://api.github.com/graphql"
PATH_RE = re.compile(r"[\w./-]+\.(?:py|js|ts|tsx|jsx|go|rb|java|rs|php|c|cpp|cs|css|scss|html|json|ya?ml|sql|sh)")


class SuggestOwnerInput(BaseModel):
    bug_id: str
    suspect_path: str = ""   # optional explicit file hint


class SuggestOwnerResult(BaseModel):
    ok: bool
    source: str = "none"          # codeowners | blame | commits | none
    assignee_login: str = ""
    reason: str = ""
    candidates: str = ""          # other people with context, ranked, semicolon-separated
    breaking_commit: str = ""
    path: str = ""
    detail: str = ""


def _gh_get(url, params, pat):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "cortex-triage"}
    if pat:
        headers["Authorization"] = "Bearer " + pat
    return requests.get(url, params=params, headers=headers, timeout=20)


def _find_path(text: str) -> str:
    m = PATH_RE.search(text or "")
    return m.group(0) if m else ""


def _codeowners_for(repo, path, pat) -> Optional[str]:
    if not path:
        return None
    for loc in (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS"):
        r = _gh_get(GH + "/repos/" + repo + "/contents/" + loc, None, pat)
        if r.status_code != 200:
            continue
        try:
            content = base64.b64decode(r.json().get("content", "")).decode("utf-8", "replace")
        except Exception:
            continue
        owner = None
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            pattern, owners = parts[0], [p.lstrip("@") for p in parts[1:] if p.startswith("@")]
            if not owners:
                continue
            pat_glob = pattern
            if pat_glob.startswith("/"):
                pat_glob = pat_glob[1:]
            if pat_glob.endswith("/"):
                if path.startswith(pat_glob):
                    owner = owners[0]
            elif pat_glob == "*" or fnmatch.fnmatch(path, pat_glob) or fnmatch.fnmatch(path, "*" + pat_glob) or path.endswith(pat_glob):
                owner = owners[0]
        if owner:
            return owner
        return None
    return None


def _default_branch(repo, pat) -> str:
    r = _gh_get(GH + "/repos/" + repo, None, pat)
    if r.status_code == 200:
        return r.json().get("default_branch") or "main"
    return "main"


def _blame_authors(repo, path, branch, pat):
    """Line-level blame via GitHub's GraphQL API — who wrote the lines that
    are actually in the file today. Requires a PAT (GraphQL always needs
    auth, even for public repos). Returns {author: line_count}, or {} if
    unavailable.
    """
    if not pat or not path:
        return {}
    parts = repo.split("/", 1)
    if len(parts) != 2:
        return {}
    owner, name = parts
    query = """
    query($owner:String!, $name:String!, $branch:String!, $path:String!) {
      repository(owner:$owner, name:$name) {
        ref(qualifiedName:$branch) {
          target {
            ... on Commit {
              blame(path:$path) {
                ranges { startingLine endingLine commit { author { user { login } name } } } } } } } } }
    """
    try:
        r = requests.post(
            GH_GRAPHQL,
            json={"query": query, "variables": {"owner": owner, "name": name, "branch": branch, "path": path}},
            headers={"Authorization": "Bearer " + pat, "User-Agent": "cortex-triage"},
            timeout=20,
        )
        if r.status_code != 200:
            return {}
        data = (r.json() or {}).get("data") or {}
        ranges = (((data.get("repository") or {}).get("ref") or {}).get("target") or {}).get("blame", {}).get("ranges", [])
    except Exception:
        return {}

    tally = {}
    for rg in ranges or []:
        line_count = max(0, (rg.get("endingLine") or 0) - (rg.get("startingLine") or 0) + 1)
        author = (rg.get("commit") or {}).get("author") or {}
        who = ((author.get("user") or {}) or {}).get("login") or author.get("name") or ""
        if who:
            tally[who] = tally.get(who, 0) + line_count
    return tally


def _commit_authors(repo, path, pat, per_page=30):
    """Frequency of contribution to the file — who keeps showing up, not
    just whoever happened to commit last. Also returns the most recent
    commit (sha + url) as the 'breaking commit' reference.
    """
    params = {"per_page": per_page}
    if path:
        params["path"] = path
    r = _gh_get(GH + "/repos/" + repo + "/commits", params, pat)
    if r.status_code != 200:
        return {}, "", ""
    commits = r.json() if isinstance(r.json(), list) else []
    tally = {}
    breaking_sha, breaking_url = "", ""
    for c in commits:
        login = ((c.get("author") or {}) or {}).get("login") or ""
        name = (((c.get("commit") or {}).get("author") or {}) or {}).get("name") or ""
        who = login or name
        if who:
            tally[who] = tally.get(who, 0) + 1
        if not breaking_sha:
            breaking_sha = (c.get("sha") or "")[:10]
            breaking_url = c.get("html_url") or ""
    return tally, breaking_sha, breaking_url


def _rank(tally: dict, top_n: int = 3):
    return sorted(tally.items(), key=lambda kv: kv[1], reverse=True)[:top_n]


async def suggest_owner(ctx: FunctionContext, data: SuggestOwnerInput) -> SuggestOwnerResult:
    pod = Pod.from_env()

    repo, pat = "", ""
    try:
        cfgs = pod.records.list("github_config", limit=1).to_dict()["items"]
        if cfgs:
            repo = (cfgs[0].get("repo") or "").strip()
            pat = (cfgs[0].get("pat") or "").strip()
    except Exception as e:
        return SuggestOwnerResult(ok=False, detail="config read failed: " + str(e)[:120])
    if not repo:
        return SuggestOwnerResult(ok=False, detail="No repo configured (set one in github_config).")

    try:
        bug = pod.table("bugs").get(data.bug_id)
    except Exception as e:
        return SuggestOwnerResult(ok=False, detail="bug read failed: " + str(e)[:120])
    issue_text = ""
    try:
        iss = pod.table("issues").get(bug.get("issue_id"))
        issue_text = (iss.get("title") or "") + "\n" + (iss.get("body") or "")
    except Exception:
        pass
    path = (data.suspect_path or "").strip() or _find_path(
        (bug.get("title") or "") + "\n" + (bug.get("reasoning") or "") + "\n" + issue_text
    )

    branch = _default_branch(repo, pat)
    blame_tally = _blame_authors(repo, path, branch, pat) if path else {}
    commit_tally, breaking_sha, breaking_url = _commit_authors(repo, path, pat)

    if blame_tally:
        source, tally, unit = "blame", blame_tally, "lines"
    elif commit_tally:
        source, tally, unit = "commits", commit_tally, "commits"
    else:
        return SuggestOwnerResult(ok=False, path=path, detail="No commits/blame found for " + (path or repo))

    ranked = _rank(tally)
    co = _codeowners_for(repo, path, pat)

    if co:
        assignee = co
        top_context = ranked[0] if ranked else None
        if top_context and top_context[0] != co:
            reason = "CODEOWNERS owner for " + (path or "the repo") + " — most code context: @" + top_context[0] + " (" + str(top_context[1]) + " " + unit + ")"
        else:
            reason = "CODEOWNERS owner for " + (path or "the repo") + ", also has the most code context"
    else:
        assignee = ranked[0][0]
        reason = "most code context on " + (path or "the repo") + ": " + str(ranked[0][1]) + " " + unit + " (via " + source + ")"

    alternates = [who + " (" + str(n) + " " + unit + ")" for who, n in ranked if who != assignee]
    candidates = "; ".join(alternates)

    try:
        pod.table("bugs").update(data.bug_id, {
            "assignee_login": assignee,
            "assignee_reason": reason,
            "assignee_candidates": candidates,
            "breaking_commit": breaking_sha,
            "breaking_commit_url": breaking_url,
            "assign_status": "suggested",
        })
    except Exception as e:
        return SuggestOwnerResult(ok=False, assignee_login=assignee, reason=reason, candidates=candidates, path=path,
                                  breaking_commit=breaking_sha, detail="bug update failed: " + str(e)[:120])

    return SuggestOwnerResult(ok=True, source=("codeowners" if co else source), assignee_login=assignee, reason=reason,
                              candidates=candidates, breaking_commit=breaking_sha, path=path,
                              detail="suggested @" + assignee + (" (+" + str(len(alternates)) + " alternate" + ("s" if len(alternates) != 1 else "") + ")" if alternates else ""))
