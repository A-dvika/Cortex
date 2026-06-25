#input_type_name: AssignOwnerInput
#output_type_name: AssignOwnerResult
#function_name: assign_owner

"""Assign a GitHub issue to the suggested owner and post a triage comment.

This is the WRITE step, run only on human approval. It needs a PAT (with repo
write) stored in the invoking user's github_config row. The GitHub issue number
comes from the linked issue's `external_id`.
"""

from typing import Optional

import requests
from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod

GH = "https://api.github.com"


class AssignOwnerInput(BaseModel):
    bug_id: str
    assignee: str = ""   # optional override; defaults to the bug's suggested login


class AssignOwnerResult(BaseModel):
    ok: bool
    assigned_to: str = ""
    issue_number: str = ""
    detail: str = ""


def _headers(pat):
    return {"Accept": "application/vnd.github+json", "User-Agent": "cortex-triage", "Authorization": "Bearer " + pat}


async def assign_owner(ctx: FunctionContext, data: AssignOwnerInput) -> AssignOwnerResult:
    pod = Pod.from_env()

    repo, pat = "", ""
    try:
        cfgs = pod.records.list("github_config", limit=1).to_dict()["items"]
        if cfgs:
            repo = (cfgs[0].get("repo") or "").strip()
            pat = (cfgs[0].get("pat") or "").strip()
    except Exception as e:
        return AssignOwnerResult(ok=False, detail="config read failed: " + str(e)[:120])
    if not repo:
        return AssignOwnerResult(ok=False, detail="No repo configured.")
    if not pat:
        return AssignOwnerResult(ok=False, detail="No PAT stored — add a token with repo write to assign.")

    try:
        bug = pod.table("bugs").get(data.bug_id)
    except Exception as e:
        return AssignOwnerResult(ok=False, detail="bug read failed: " + str(e)[:120])

    assignee = (data.assignee or bug.get("assignee_login") or "").strip().lstrip("@")
    if not assignee:
        return AssignOwnerResult(ok=False, detail="No assignee to set (run suggest_owner first).")

    # GitHub issue number lives on the linked issue's external_id
    issue_number = ""
    try:
        iss = pod.table("issues").get(bug.get("issue_id"))
        issue_number = str(iss.get("external_id") or "").strip()
    except Exception:
        pass
    if not issue_number.isdigit():
        return AssignOwnerResult(ok=False, assigned_to=assignee,
                                 detail="No numeric GitHub issue number on this bug (set the issue # / external_id).")

    # Optional fix for a richer comment
    fix_line = ""
    try:
        fixes = pod.records.list("fixes", limit=1,
                                 filter=[{"field": "bug_id", "op": "eq", "value": data.bug_id}]).to_dict()["items"]
        if fixes:
            f = fixes[0]
            fix_line = "\n\n**Suggested fix:** " + (f.get("title") or "") + \
                       ("\n" + f.get("suggestion") if f.get("suggestion") else "")
    except Exception:
        pass

    base = GH + "/repos/" + repo + "/issues/" + issue_number

    # 1) assign
    ra = requests.post(base + "/assignees", headers=_headers(pat), json={"assignees": [assignee]}, timeout=20)
    if ra.status_code not in (200, 201):
        return AssignOwnerResult(ok=False, assigned_to=assignee, issue_number=issue_number,
                                 detail="assign failed " + str(ra.status_code) + ": " + ra.text[:140])

    # 2) comment
    body = ("🤖 **Cortex-Triage**\n\n"
            "**Severity:** " + str(bug.get("severity") or "?") + " · **Type:** " + str(bug.get("bug_type") or "?") +
            "\n**Assigned to @" + assignee + "** — " + str(bug.get("assignee_reason") or "") +
            (("\n**Likely breaking commit:** " + bug.get("breaking_commit_url")) if bug.get("breaking_commit_url") else "") +
            fix_line)
    requests.post(base + "/comments", headers=_headers(pat), json={"body": body}, timeout=20)

    try:
        pod.table("bugs").update(data.bug_id, {"assign_status": "assigned"})
    except Exception:
        pass

    return AssignOwnerResult(ok=True, assigned_to=assignee, issue_number=issue_number,
                             detail="assigned #" + issue_number + " to @" + assignee)
