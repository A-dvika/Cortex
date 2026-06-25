#input_type_name: OpenFixPrInput
#output_type_name: OpenFixPrResult
#function_name: open_fix_pr

"""Auto-resolve step: for an eligible bug (low risk, high-confidence fix), open
a real GitHub PR on a new branch carrying the suggested fix, and request review
from whoever suggest_owner identified as the person who knows that part of the
codebase.

This deliberately does NOT splice the suggested code_snippet into an existing
source file — an unverified AI patch landing in a real file without running
tests is how you cause the next incident, not resolve this one. Instead it
commits the fix as a structured, reviewable patch note on its own branch and
opens a PR against it, so a human still has to actually merge the change.
That's the honest meaning of "auto-resolve" without a sandboxed test runner.

Eligibility (tunable): risk_level == "low" AND confidence >= MIN_CONFIDENCE.
Anything else is left to the existing manual flow (assign_owner).
"""

import base64

import requests
from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod

GH = "https://api.github.com"
MIN_CONFIDENCE = 0.55  # see fix-suggester's calibration guidance — 0.55+ on a genuinely low-risk fix is meant to be reachable


class OpenFixPrInput(BaseModel):
    bug_id: str


class OpenFixPrResult(BaseModel):
    ok: bool
    eligible: bool = False
    pr_url: str = ""
    reviewer: str = ""
    detail: str = ""


def _headers(pat):
    h = {"Accept": "application/vnd.github+json", "User-Agent": "cortex-triage"}
    if pat:
        h["Authorization"] = "Bearer " + pat
    return h


async def open_fix_pr(ctx: FunctionContext, data: OpenFixPrInput) -> OpenFixPrResult:
    pod = Pod.from_env()

    repo, pat = "", ""
    try:
        cfgs = pod.records.list("github_config", limit=1).to_dict()["items"]
        if cfgs:
            repo = (cfgs[0].get("repo") or "").strip()
            pat = (cfgs[0].get("pat") or "").strip()
    except Exception as e:
        return OpenFixPrResult(ok=False, detail="config read failed: " + str(e)[:120])
    if not repo or not pat:
        return OpenFixPrResult(ok=False, detail="No repo/PAT configured — PR creation needs repo write access.")

    try:
        bug = pod.table("bugs").get(data.bug_id)
    except Exception as e:
        return OpenFixPrResult(ok=False, detail="bug read failed: " + str(e)[:120])

    try:
        fixes = pod.records.list("fixes", limit=1,
                                 filter=[{"field": "bug_id", "op": "eq", "value": data.bug_id}]).to_dict()["items"]
    except Exception as e:
        return OpenFixPrResult(ok=False, detail="fix read failed: " + str(e)[:120])
    if not fixes:
        return OpenFixPrResult(ok=False, detail="No fix suggestion found for this bug.")
    fix = fixes[0]

    risk = (fix.get("risk_level") or "high").lower()
    confidence = float(fix.get("confidence") or 0)
    eligible = risk == "low" and confidence >= MIN_CONFIDENCE
    if not eligible:
        try:
            pod.table("bugs").update(data.bug_id, {"fix_pr_status": "ineligible"})
        except Exception:
            pass
        return OpenFixPrResult(ok=True, eligible=False,
                               detail="Not auto-PR eligible (risk=" + risk + ", confidence=" + str(confidence) +
                                      "); left for manual review.")

    issue_number = ""
    try:
        iss = pod.table("issues").get(bug.get("issue_id"))
        issue_number = str(iss.get("external_id") or "").strip()
    except Exception:
        pass

    headers = _headers(pat)

    r = requests.get(GH + "/repos/" + repo, headers=headers, timeout=20)
    if r.status_code != 200:
        return OpenFixPrResult(ok=False, eligible=True, detail="repo lookup failed " + str(r.status_code) + ": " + r.text[:140])
    default_branch = r.json().get("default_branch", "main")

    r = requests.get(GH + "/repos/" + repo + "/git/ref/heads/" + default_branch, headers=headers, timeout=20)
    if r.status_code != 200:
        return OpenFixPrResult(ok=False, eligible=True, detail="base ref lookup failed " + str(r.status_code) + ": " + r.text[:140])
    base_sha = r.json()["object"]["sha"]

    branch = "cortex-fix/" + data.bug_id[:8]
    r = requests.post(GH + "/repos/" + repo + "/git/refs", headers=headers,
                      json={"ref": "refs/heads/" + branch, "sha": base_sha}, timeout=20)
    if r.status_code not in (200, 201):
        if "Reference already exists" not in r.text:
            return OpenFixPrResult(ok=False, eligible=True, detail="branch create failed " + str(r.status_code) + ": " + r.text[:140])

    patch_path = "cortex-fixes/" + data.bug_id[:8] + ".md"
    body_md = (
        "# " + (fix.get("title") or "Suggested fix") + "\n\n"
        "**Bug:** " + (bug.get("title") or "") + " (" + str(bug.get("severity") or "?") + " / " + str(bug.get("bug_type") or "?") + ")\n\n"
        "**Suggested fix:**\n\n" + (fix.get("suggestion") or "") + "\n\n"
        + (("**Code sketch:**\n\n```\n" + fix.get("code_snippet") + "\n```\n\n") if fix.get("code_snippet") else "")
        + "*Drafted by cortex-triage. Confidence " + str(confidence) + " · review before merging.*\n"
    )
    r = requests.put(GH + "/repos/" + repo + "/contents/" + patch_path, headers=headers, json={
        "message": "cortex-triage: suggested fix for " + (bug.get("title") or data.bug_id),
        "content": base64.b64encode(body_md.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }, timeout=20)
    if r.status_code not in (200, 201):
        return OpenFixPrResult(ok=False, eligible=True, detail="commit failed " + str(r.status_code) + ": " + r.text[:140])

    pr_title = "🤖 Suggested fix: " + (fix.get("title") or bug.get("title") or "")
    pr_body = ("Auto-drafted by cortex-triage for a " + risk + "-risk, high-confidence fix.\n\n" + body_md +
              (("\nRefs #" + issue_number) if issue_number.isdigit() else ""))
    r = requests.post(GH + "/repos/" + repo + "/pulls", headers=headers, json={
        "title": pr_title, "head": branch, "base": default_branch, "body": pr_body,
    }, timeout=20)
    if r.status_code not in (200, 201):
        try:
            pod.table("bugs").update(data.bug_id, {"fix_pr_status": "failed"})
        except Exception:
            pass
        return OpenFixPrResult(ok=False, eligible=True, detail="PR create failed " + str(r.status_code) + ": " + r.text[:140])

    pr = r.json()
    pr_url = pr.get("html_url", "")
    pr_number = pr.get("number")

    reviewer = (bug.get("assignee_login") or "").strip()
    if reviewer and pr_number:
        requests.post(GH + "/repos/" + repo + "/pulls/" + str(pr_number) + "/requested_reviewers",
                      headers=headers, json={"reviewers": [reviewer]}, timeout=20)
    if pr_number:
        requests.post(GH + "/repos/" + repo + "/issues/" + str(pr_number) + "/labels",
                      headers=headers, json={"labels": ["ai-suggested-fix"]}, timeout=20)

    try:
        pod.table("bugs").update(data.bug_id, {"fix_pr_url": pr_url, "fix_pr_status": "opened"})
    except Exception:
        pass

    return OpenFixPrResult(ok=True, eligible=True, pr_url=pr_url, reviewer=reviewer,
                           detail="opened " + pr_url + (" — review requested from @" + reviewer if reviewer else ""))
