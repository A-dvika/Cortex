#input_type_name: DecideBugInput
#output_type_name: DecideBugResult
#function_name: decide_bug

"""Deterministic write for the human decision on a triaged bug.

The triage agent and suggest_owner only ever produce a recommendation —
severity, owner guess, complexity. Nothing about a bug changes status until a
human looks at that recommendation and picks one of: assign, defer, backlog,
or close. This function is the only thing that writes that decision, so the
audit trail (who decided what, when, and why) is always exact and queryable
later, never reconstructed from a chat log.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod

DECISIONS = {"assign", "defer", "backlog", "close"}
DECISION_TO_STATUS = {
    "assign": "assigned",
    "defer": "deferred",
    "backlog": "backlogged",
    "close": "closed",
}


class DecideBugInput(BaseModel):
    bug_id: str
    decision: str  # assign | defer | backlog | close
    reason: str = ""
    decided_by: str = ""
    defer_days: int = 14  # only used when decision == "defer"


class DecideBugResult(BaseModel):
    ok: bool
    decision_status: str = ""
    deferred_until: Optional[str] = None
    detail: str = ""


async def decide_bug(ctx: FunctionContext, data: DecideBugInput) -> DecideBugResult:
    decision = (data.decision or "").strip().lower()
    if decision not in DECISIONS:
        return DecideBugResult(ok=False, detail="decision must be one of: " + ", ".join(sorted(DECISIONS)))

    pod = Pod.from_env()

    try:
        bug = pod.table("bugs").get(data.bug_id)
    except Exception as e:
        return DecideBugResult(ok=False, detail="bug read failed: " + str(e)[:120])
    if not bug:
        return DecideBugResult(ok=False, detail="no such bug")

    status = DECISION_TO_STATUS[decision]
    now = datetime.now(timezone.utc)

    update = {
        "decision_status": status,
        "human_decision": decision,
        "decision_reason": data.reason or "",
        "decision_by": data.decided_by or "",
        "decided_at": now.isoformat(),
    }

    deferred_until_iso = None
    if decision == "defer":
        deferred_until = now + timedelta(days=max(1, int(data.defer_days or 14)))
        deferred_until_iso = deferred_until.isoformat()
        update["deferred_until"] = deferred_until_iso

    try:
        pod.table("bugs").update(data.bug_id, update)
    except Exception as e:
        return DecideBugResult(ok=False, detail="update failed: " + str(e)[:140])

    return DecideBugResult(
        ok=True,
        decision_status=status,
        deferred_until=deferred_until_iso,
        detail="recorded \"" + decision + "\" for bug " + data.bug_id[:8] + (" — reviewed in " + str(data.defer_days) + " days" if decision == "defer" else ""),
    )
