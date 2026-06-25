#input_type_name: EscalateIncidentsInput
#output_type_name: EscalateIncidentsResult
#function_name: escalate_incidents

"""Sweep open P1 incidents; page the escalation channel for any still unacked
past alert_config.escalation_minutes. Meant to run on a schedule (cron) —
see escalate-incidents workflow. Each incident escalates at most once (level
0 -> 1); repeated paging isn't worth the noise for an MVP escalation policy.
"""

from datetime import datetime, timezone
from typing import List

import requests
from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod


class EscalateIncidentsInput(BaseModel):
    pass


class EscalateIncidentsResult(BaseModel):
    ok: bool
    escalated_ids: List[str] = []
    detail: str = ""


def _age_minutes(created_at: str, now: datetime) -> float:
    if not created_at:
        return 0.0
    try:
        ts = created_at.replace("Z", "+00:00")
        created = datetime.fromisoformat(ts)
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return (now - created).total_seconds() / 60.0
    except Exception:
        return 0.0


async def escalate_incidents(ctx: FunctionContext, data: EscalateIncidentsInput) -> EscalateIncidentsResult:
    pod = Pod.from_env()

    webhook, escalation_minutes = "", 15
    try:
        cfgs = pod.records.list("alert_config", limit=1).to_dict()["items"]
        if cfgs:
            webhook = (cfgs[0].get("escalation_webhook_url") or cfgs[0].get("slack_webhook_url") or "").strip()
            escalation_minutes = int(cfgs[0].get("escalation_minutes") or 15)
    except Exception as e:
        return EscalateIncidentsResult(ok=False, detail="alert_config read failed: " + str(e)[:140])
    if not webhook:
        return EscalateIncidentsResult(ok=True, detail="no escalation channel configured")

    try:
        incidents = pod.records.list("incidents", limit=200,
                                     filter=[{"field": "status", "op": "eq", "value": "open"}]).to_dict()["items"]
    except Exception as e:
        return EscalateIncidentsResult(ok=False, detail="incidents read failed: " + str(e)[:140])

    now = datetime.now(timezone.utc)
    escalated = []
    for inc in incidents:
        if inc.get("severity") != "P1":
            continue
        if int(inc.get("escalation_level") or 0) >= 1:
            continue
        age = _age_minutes(inc.get("created_at") or "", now)
        if age < escalation_minutes:
            continue

        assignee = (inc.get("assignee_login") or "").strip()
        who = (" — primary @" + assignee + " hasn't acked") if assignee else ""
        text = ("⏰ *Escalation*: P1 incident open " + str(int(age)) + "m — " +
               (inc.get("title") or "") + who)
        try:
            requests.post(webhook, json={"text": text}, timeout=10)
        except Exception:
            continue

        try:
            pod.table("incidents").update(inc["id"], {"escalation_level": 1})
            escalated.append(inc["id"])
        except Exception:
            pass

    return EscalateIncidentsResult(ok=True, escalated_ids=escalated,
                                   detail=str(len(escalated)) + " incident(s) escalated")
