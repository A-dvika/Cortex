#input_type_name: CreateJiraTicketInput
#output_type_name: CreateJiraTicketResult
#function_name: create_jira_ticket

"""Open a Jira ticket for a triaged bug — visibility, not assignment.

This runs automatically for every triaged bug, same as `open_incident`: it is
the bug becoming trackable, not a decision about who does the work. The
suggested owner from `suggest_owner` is written into the description as a
recommendation only; nobody is assigned in Jira by this function. Assigning a
person is still a human action, same boundary as `assign_owner` on GitHub.

Best-effort like the rest of this pipeline: if `source_config` has no Jira
credentials yet, this is a documented no-op (`ok: true`, ticket not created),
never a thrown error.
"""

from typing import Optional

import requests
from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod


class CreateJiraTicketInput(BaseModel):
    bug_id: str


class CreateJiraTicketResult(BaseModel):
    ok: bool
    created: bool = False
    issue_key: str = ""
    issue_url: str = ""
    detail: str = ""


async def create_jira_ticket(ctx: FunctionContext, data: CreateJiraTicketInput) -> CreateJiraTicketResult:
    pod = Pod.from_env()

    try:
        bug = pod.table("bugs").get(data.bug_id)
    except Exception as e:
        return CreateJiraTicketResult(ok=False, detail="bug read failed: " + str(e)[:120])
    if not bug:
        return CreateJiraTicketResult(ok=False, detail="no such bug")

    cfg = None
    try:
        cfgs = pod.records.list("source_config", limit=1).to_dict()["items"]
        if cfgs:
            cfg = cfgs[0]
    except Exception:
        pass

    base_url = (cfg.get("jira_base_url") or "").strip().rstrip("/") if cfg else ""
    email = (cfg.get("jira_email") or "").strip() if cfg else ""
    token = (cfg.get("jira_api_token") or "").strip() if cfg else ""
    project_key = (cfg.get("jira_project_key") or "").strip() if cfg else ""

    if not (base_url and email and token and project_key):
        return CreateJiraTicketResult(
            ok=True, created=False,
            detail="Jira not configured — add jira_base_url/jira_email/jira_api_token/jira_project_key in source_config",
        )

    owner_line = (
        "Suggested owner (not assigned): @" + bug.get("assignee_login", "") + " — " + bug.get("assignee_reason", "")
        if bug.get("assignee_login") else "Suggested owner: none yet — suggest_owner has not run on this bug."
    )
    description = (
        "Auto-filed by Cortex-Triage. " + owner_line + "\n\n"
        "Severity: " + bug.get("severity", "P3") + "\n"
        "Fix complexity: " + bug.get("fix_complexity", "moderate") + "\n"
        "Affected services: " + str(bug.get("affected_service_count", 1)) + "\n"
        "Production code: " + ("yes" if bug.get("is_production_code", True) else "no") + "\n\n"
        "Reasoning: " + (bug.get("reasoning") or "") + "\n\n"
        "This ticket tracks investigation context only. Assigning a person is a human decision, made on the Cortex board."
    )

    try:
        r = requests.post(
            base_url + "/rest/api/2/issue",
            auth=(email, token),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            json={"fields": {
                "project": {"key": project_key},
                "summary": (bug.get("title") or "Untitled bug")[:250],
                "description": description,
                "issuetype": {"name": "Bug"},
            }},
            timeout=20,
        )
    except Exception as e:
        return CreateJiraTicketResult(ok=True, created=False, detail="Jira request failed: " + str(e)[:140])

    if r.status_code not in (200, 201):
        return CreateJiraTicketResult(ok=True, created=False, detail="Jira " + str(r.status_code) + ": " + r.text[:160])

    body = r.json() if r.content else {}
    key = body.get("key", "")
    issue_url = base_url + "/browse/" + key if key else ""

    try:
        pod.table("bugs").update(data.bug_id, {"jira_issue_key": key, "jira_issue_url": issue_url})
    except Exception as e:
        return CreateJiraTicketResult(ok=True, created=True, issue_key=key, issue_url=issue_url,
                                      detail="ticket created but bug update failed: " + str(e)[:120])

    return CreateJiraTicketResult(ok=True, created=True, issue_key=key, issue_url=issue_url,
                                  detail="created " + key)
