#input_type_name: NotifyOwnerSlackInput
#output_type_name: NotifyOwnerSlackResult
#function_name: notify_owner_slack

"""Post a Slack message announcing a newly triaged bug — visibility, not a page.

Runs for every triaged bug regardless of severity, same reasoning as
`create_jira_ticket`: this is making a result visible, not deciding anything.
`open_incident` already pages P1/P2 through its own (separate, more urgent)
alert path — this is the quieter "here's what Cortex just found" note that
covers every severity, including P3s that never become incidents.

Best-effort: if no `alert_config.slack_webhook_url` is set, this is a
documented no-op (`ok: true`, `posted: false`), never a thrown error.
"""

from typing import Optional

import requests
from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod


class NotifyOwnerSlackInput(BaseModel):
    bug_id: str


class NotifyOwnerSlackResult(BaseModel):
    ok: bool
    posted: bool = False
    detail: str = ""


async def notify_owner_slack(ctx: FunctionContext, data: NotifyOwnerSlackInput) -> NotifyOwnerSlackResult:
    pod = Pod.from_env()

    try:
        bug = pod.table("bugs").get(data.bug_id)
    except Exception as e:
        return NotifyOwnerSlackResult(ok=False, detail="bug read failed: " + str(e)[:120])
    if not bug:
        return NotifyOwnerSlackResult(ok=False, detail="no such bug")

    webhook = ""
    try:
        cfgs = pod.records.list("alert_config", limit=1).to_dict()["items"]
        if cfgs:
            webhook = (cfgs[0].get("slack_webhook_url") or "").strip()
    except Exception:
        pass

    if not webhook:
        return NotifyOwnerSlackResult(ok=True, posted=False, detail="no alert channel configured")

    sev = bug.get("severity", "P3")
    emoji = {"P1": "🚨", "P2": "⚠️", "P3": "🧭"}.get(sev, "🧭")
    owner_line = ("suggested owner: @" + bug.get("assignee_login", "")) if bug.get("assignee_login") else "owner not yet suggested"
    lines = [emoji + " " + sev + " bug triaged: " + (bug.get("title") or "")]
    lines.append(owner_line + (" — " + bug.get("assignee_reason", "") if bug.get("assignee_reason") else ""))
    if bug.get("jira_issue_url"):
        lines.append("Jira: " + bug["jira_issue_url"])
    if bug.get("breaking_commit_url"):
        lines.append("Likely commit: " + bug["breaking_commit_url"])
    text = "\n".join(lines)

    posted = False
    try:
        r = requests.post(webhook, json={"text": text}, timeout=10)
        posted = r.status_code in (200, 201)
    except Exception:
        pass

    return NotifyOwnerSlackResult(ok=True, posted=posted,
                                  detail="posted" if posted else "post failed or webhook unreachable")
