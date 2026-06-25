#input_type_name: SuggestOwnerInput
#output_type_name: SuggestOwnerResult
#function_name: suggest_owner

"""Suggest the most likely owner of a bug from the GitHub repo's history.

Strategy (deterministic, read-only on GitHub):
  1. Find a file path implicated by the bug (explicit hint, else parsed from text).
  2. Pull recent commits touching that file -> the most recent is the likely
     "breaking" commit; its author is a strong owner candidate.
  3. Read CODEOWNERS; if a rule matches the path, that owner takes precedence.
  4. Write the suggestion (assignee_login, reason, breaking commit) to the bug row.

GitHub reads are unauthenticated (public repo, 60 req/hr) unless a PAT is stored
in github_config, which raises the limit. No writes to GitHub happen here.
"""

import base64
import fnmatch
import re
from typing import Optional

import requests
from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod

GH = "https://api.github.com"
PATH_RE = re.compile(r"[\w./-]+\.(?:py|js|ts|tsx|jsx|go|rb|java|rs|php|c|cpp|cs|css|scss|html|json|ya?ml|sql|sh)")


class SuggestOwnerInput(BaseModel):
    bug_id: str
    suspect_path: str = ""   # optional explicit file hint


class SuggestOwnerResult(BaseModel):
    ok: bool
    source: str = "none"          # codeowners | commits | none
    assignee_login: str = ""
    reason: str = ""
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


async def suggest_owner(ctx: FunctionContext, data: SuggestOwnerInput) -> SuggestOwnerResult:
    pod = Pod.from_env()

    # 1) repo + optional PAT from the invoking user's private config
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

    # 2) bug text -> implicated path
    try:
        bug = pod.table("bugs").get(data.bug_id)
    except Exception as e:
        return SuggestOwnerResult(ok=False, detail="bug read failed: " + str(e)[:120])
    # The file/stack trace usually lives in the issue body — read it too.
    issue_text = ""
    try:
        iss = pod.table("issues").get(bug.get("issue_id"))
        issue_text = (iss.get("title") or "") + "\n" + (iss.get("body") or "")
    except Exception:
        pass
    path = (data.suspect_path or "").strip() or _find_path(
        (bug.get("title") or "") + "\n" + (bug.get("reasoning") or "") + "\n" + issue_text
    )

    # 3) recent commits touching the path (or repo-wide if no path)
    params = {"per_page": 10}
    if path:
        params["path"] = path
    r = _gh_get(GH + "/repos/" + repo + "/commits", params, pat)
    if r.status_code != 200:
        return SuggestOwnerResult(ok=False, path=path, detail="GitHub commits " + str(r.status_code) + ": " + r.text[:120])
    commits = r.json() if isinstance(r.json(), list) else []

    breaking_sha, breaking_url, recent_login, recent_name = "", "", "", ""
    tally = {}
    for c in commits:
        login = ((c.get("author") or {}) or {}).get("login") or ""
        name = (((c.get("commit") or {}).get("author") or {}) or {}).get("name") or ""
        who = login or name
        if who:
            tally[who] = tally.get(who, 0) + 1
        if not breaking_sha:
            breaking_sha = (c.get("sha") or "")[:10]
            breaking_url = c.get("html_url") or ""
            recent_login, recent_name = login, name

    # 4) decide owner: CODEOWNERS wins, else most-recent committer to the file
    co = _codeowners_for(repo, path, pat)
    if co:
        assignee, source = co, "codeowners"
        reason = "CODEOWNERS owner for " + (path or "the repo")
    elif recent_login or recent_name:
        assignee, source = (recent_login or recent_name), "commits"
        top = max(tally, key=tally.get) if tally else assignee
        extra = "" if top == assignee else (" (most frequent recent committer: " + top + ")")
        reason = "most recent committer to " + (path or "the repo") + extra
    else:
        return SuggestOwnerResult(ok=False, path=path, detail="No commits/owners found for " + (path or repo))

    try:
        pod.table("bugs").update(data.bug_id, {
            "assignee_login": assignee,
            "assignee_reason": reason,
            "breaking_commit": breaking_sha,
            "breaking_commit_url": breaking_url,
            "assign_status": "suggested",
        })
    except Exception as e:
        return SuggestOwnerResult(ok=False, assignee_login=assignee, reason=reason, path=path,
                                  breaking_commit=breaking_sha, detail="bug update failed: " + str(e)[:120])

    return SuggestOwnerResult(ok=True, source=source, assignee_login=assignee, reason=reason,
                              breaking_commit=breaking_sha, path=path,
                              detail="suggested @" + assignee)
