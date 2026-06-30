#input_type_name: PollGithubIssuesInput
#output_type_name: PollGithubIssuesResult
#function_name: poll_github_issues

"""Automatic intake: notice new GitHub issues on the connected repo.

There is no anonymous webhook surface here — a real push webhook needs
Lemma's OAuth connector flow (browser consent), a separate setup step, not
something a scheduled function can wire up for itself. This is the honest
alternative: poll the repo's recent issues every couple of minutes and hand
back the single newest one Cortex hasn't seen yet (matched by source +
external_id + repo against the `issues` table).

This function never writes anything — it only looks and reports. The
poll-github-issues *workflow* (this function's only caller) does the actual
triage in the same run, via the same agent/function steps as the manual "New
bug report" button, so there is exactly one triage path either way. One new
issue per run, every 2 minutes, is plenty for how often any one repo gets new
reports — and it means the workflow stays a fixed, linear graph instead of
needing a dynamic loop over an unknown number of new issues.
"""

from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod

GH = "https://api.github.com"


class PollGithubIssuesInput(BaseModel):
    pass


class PollGithubIssuesResult(BaseModel):
    ok: bool
    found: bool = False
    checked: int = 0
    title: str = ""
    body: str = ""
    url: str = ""
    reporter: str = ""
    external_id: str = ""
    detail: str = ""


async def poll_github_issues(ctx: FunctionContext, data: PollGithubIssuesInput) -> PollGithubIssuesResult:
    import requests

    pod = Pod.from_env()

    repo, pat = "", ""
    try:
        cfgs = pod.records.list("github_config", limit=1).to_dict()["items"]
        if cfgs:
            repo = (cfgs[0].get("repo") or "").strip()
            pat = (cfgs[0].get("pat") or "").strip()
    except Exception as e:
        return PollGithubIssuesResult(ok=False, detail="config read failed: " + str(e)[:120])
    if not repo:
        return PollGithubIssuesResult(ok=True, found=False, detail="no repo configured — nothing to poll")

    headers = {"Accept": "application/vnd.github+json", "User-Agent": "cortex-triage"}
    if pat:
        headers["Authorization"] = "Bearer " + pat

    try:
        r = requests.get(
            GH + "/repos/" + repo + "/issues",
            params={"state": "open", "sort": "created", "direction": "desc", "per_page": 15},
            headers=headers, timeout=20,
        )
    except Exception as e:
        return PollGithubIssuesResult(ok=False, detail="GitHub request failed: " + str(e)[:140])
    if r.status_code != 200:
        return PollGithubIssuesResult(ok=False, detail="GitHub " + str(r.status_code) + ": " + r.text[:140])

    items = r.json() if isinstance(r.json(), list) else []
    checked = 0

    for issue in items:
        if "pull_request" in issue:
            continue  # the issues endpoint also lists PRs — not our concern here
        checked += 1
        number = str(issue.get("number") or "")
        if not number:
            continue

        try:
            existing = pod.records.list(
                "issues", limit=1,
                filter=[
                    {"field": "source", "op": "eq", "value": "github"},
                    {"field": "external_id", "op": "eq", "value": number},
                    {"field": "repo", "op": "eq", "value": repo},
                ],
            ).to_dict()["items"]
        except Exception:
            existing = []
        if existing:
            continue

        return PollGithubIssuesResult(
            ok=True, found=True, checked=checked,
            title=(issue.get("title") or "Untitled")[:300],
            body=(issue.get("body") or "")[:4000],
            url=issue.get("html_url") or "",
            reporter=((issue.get("user") or {}).get("login")) or "",
            external_id=number,
            detail="found new issue #" + number,
        )

    return PollGithubIssuesResult(ok=True, found=False, checked=checked, detail="checked " + str(checked) + ", nothing new")
