#input_type_name: ResolveIncidentInput
#output_type_name: ResolveIncidentResult
#function_name: resolve_incident

"""Close out an incident once the underlying bug is actually fixed."""

from datetime import datetime, timezone

from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod


class ResolveIncidentInput(BaseModel):
    incident_id: str
    resolution_note: str = ""


class ResolveIncidentResult(BaseModel):
    ok: bool
    detail: str = ""


async def resolve_incident(ctx: FunctionContext, data: ResolveIncidentInput) -> ResolveIncidentResult:
    pod = Pod.from_env()
    now = datetime.now(timezone.utc).isoformat()
    fields = {"status": "resolved", "resolved_at": now}
    if data.resolution_note:
        try:
            existing = pod.table("incidents").get(data.incident_id)
            prior = (existing.get("summary") or "").strip()
            fields["summary"] = (prior + "\n\nResolution: " + data.resolution_note) if prior else ("Resolution: " + data.resolution_note)
        except Exception:
            fields["summary"] = "Resolution: " + data.resolution_note
    try:
        pod.table("incidents").update(data.incident_id, fields)
    except Exception as e:
        return ResolveIncidentResult(ok=False, detail="update failed: " + str(e)[:140])
    return ResolveIncidentResult(ok=True, detail="resolved at " + now)
