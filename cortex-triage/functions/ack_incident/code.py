#input_type_name: AckIncidentInput
#output_type_name: AckIncidentResult
#function_name: ack_incident

"""A developer acknowledges an incident — stops further escalation."""

from datetime import datetime, timezone

from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod


class AckIncidentInput(BaseModel):
    incident_id: str
    acked_by: str = ""


class AckIncidentResult(BaseModel):
    ok: bool
    detail: str = ""


async def ack_incident(ctx: FunctionContext, data: AckIncidentInput) -> AckIncidentResult:
    pod = Pod.from_env()
    now = datetime.now(timezone.utc).isoformat()
    fields = {"status": "acked", "acked_at": now}
    if data.acked_by:
        fields["assignee_login"] = data.acked_by
    try:
        pod.table("incidents").update(data.incident_id, fields)
    except Exception as e:
        return AckIncidentResult(ok=False, detail="update failed: " + str(e)[:140])
    return AckIncidentResult(ok=True, detail="acked at " + now)
