#input_type_name: PersistTriageInput
#output_type_name: PersistTriageResult
#function_name: persist_triage

"""Deterministic persistence step for the triage workflow.

Agents do the judgment (classify, score, suggest); this function does the
writing — one issue row, one bug row, one fix row — so persistence is exact,
idempotent in shape, and never left to model improvisation.
"""

from typing import Optional

from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod


class PersistTriageInput(BaseModel):
    # --- from the intake form ---
    title: str
    body: str = ""
    source: str = "manual"
    url: str = ""
    reporter: str = ""
    external_id: str = ""

    # --- from the triage agent ---
    bug_type: str = "other"
    severity: str = "P3"
    impact_score: int = 0
    urgency_score: int = 0
    confidence: float = 0.0
    is_duplicate: bool = False
    duplicate_of: str = ""
    reasoning: str = ""

    # --- from the fix-suggester agent ---
    fix_title: str = ""
    fix_suggestion: str = ""
    fix_code: str = ""
    risk_level: str = "medium"
    estimated_effort: str = "small"
    fix_confidence: float = 0.0


class PersistTriageResult(BaseModel):
    ok: bool
    issue_id: Optional[str] = None
    bug_id: Optional[str] = None
    fix_id: Optional[str] = None
    severity: str = "P3"


def _row_id(record) -> Optional[str]:
    """Pull the primary key from a create() result, tolerating dict or model."""
    if record is None:
        return None
    if isinstance(record, dict):
        return record.get("id")
    return getattr(record, "id", None)


async def persist_triage(ctx: FunctionContext, data: PersistTriageInput) -> PersistTriageResult:
    pod = Pod.from_env()  # authenticated as this function's workload principal

    issue = pod.table("issues").create({
        "source": data.source or "manual",
        "external_id": data.external_id,
        "title": data.title,
        "body": data.body,
        "url": data.url,
        "reporter": data.reporter,
        "triage_status": "triaged",
    })
    issue_id = _row_id(issue)

    bug = pod.table("bugs").create({
        "issue_id": issue_id,
        "title": data.title,
        "bug_type": data.bug_type or "other",
        "severity": data.severity or "P3",
        "impact_score": int(data.impact_score or 0),
        "urgency_score": int(data.urgency_score or 0),
        "confidence": float(data.confidence or 0.0),
        "is_duplicate": bool(data.is_duplicate),
        "duplicate_of": data.duplicate_of,
        "reasoning": data.reasoning,
    })
    bug_id = _row_id(bug)

    fix_id = None
    if data.fix_suggestion or data.fix_title:
        fix = pod.table("fixes").create({
            "bug_id": bug_id,
            "title": data.fix_title or "Suggested fix",
            "suggestion": data.fix_suggestion,
            "code_snippet": data.fix_code,
            "risk_level": data.risk_level or "medium",
            "estimated_effort": data.estimated_effort or "small",
            "confidence": float(data.fix_confidence or 0.0),
        })
        fix_id = _row_id(fix)

    return PersistTriageResult(
        ok=True,
        issue_id=issue_id,
        bug_id=bug_id,
        fix_id=fix_id,
        severity=data.severity or "P3",
    )
