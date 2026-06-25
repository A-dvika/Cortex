#input_type_name: OpenIncidentInput
#output_type_name: OpenIncidentResult
#function_name: open_incident

"""Create an incident row and alert a developer at the moment it happens.

Severity decides urgency, mirroring the spec's decision tree:
  P1 -> immediate @-mention alert
  P2 -> a normal (non-urgent) alert
  P3 -> dashboard only, no alert

If a bug_id is given and suggest_owner already ran for it, the assignee found
there is who gets paged — incidents don't re-derive ownership themselves.
"""

from typing import Optional

import requests
from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod


class OpenIncidentInput(BaseModel):
    title: str
    summary: str = ""
    severity: str = "P3"
    bug_id: str = ""
    source: str = "manual"


class OpenIncidentResult(BaseModel):
    ok: bool
    incident_id: Optional[str] = None
    alerted: bool = False
    detail: str = ""


def _row_id(record) -> Optional[str]:
    if record is None:
        return None
    if isinstance(record, dict):
        return record.get("id")
    return getattr(record, "id", None)


async def open_incident(ctx: FunctionContext, data: OpenIncidentInput) -> OpenIncidentResult:
    pod = Pod.from_env()

    assignee = ""
    if data.bug_id:
        try:
            bug = pod.table("bugs").get(data.bug_id)
            assignee = (bug.get("assignee_login") or "").strip()
        except Exception:
            pass

    try:
        record = pod.table("incidents").create({
            "source": data.source or "manual",
            "title": data.title,
            "summary": data.summary,
            "severity": data.severity or "P3",
            "status": "open",
            "bug_id": data.bug_id or None,
            "assignee_login": assignee,
            "escalation_level": 0,
        })
    except Exception as e:
        return OpenIncidentResult(ok=False, detail="incident create failed: " + str(e)[:140])
    incident_id = _row_id(record)

    webhook = ""
    try:
        cfgs = pod.records.list("alert_config", limit=1).to_dict()["items"]
        if cfgs:
            webhook = (cfgs[0].get("slack_webhook_url") or "").strip()
    except Exception:
        pass

    if not webhook or data.severity == "P3":
        return OpenIncidentResult(ok=True, incident_id=incident_id, alerted=False,
                                  detail="incident created" + ("" if webhook else " (no alert channel configured)"))

    urgent = data.severity == "P1"
    who = (" cc @" + assignee) if assignee else ""
    text = (("🚨 *P1 INCIDENT* — " if urgent else "⚠️ P2 incident — ") + data.title +
           (("\n" + data.summary) if data.summary else "") + who)

    alerted = False
    try:
        r = requests.post(webhook, json={"text": text}, timeout=10)
        alerted = r.status_code in (200, 201)
    except Exception:
        pass

    try:
        pod.table("incidents").update(incident_id, {"alert_channel_msg": text[:600]})
    except Exception:
        pass

    return OpenIncidentResult(ok=True, incident_id=incident_id, alerted=alerted,
                              detail="incident created, alert " + ("sent" if alerted else "not sent"))
