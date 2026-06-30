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
    # If set, this run is triaging an issue that already exists (e.g. the
    # auto-triage-issue workflow, started by that row's own INSERT) — update
    # it instead of creating a second one. Empty for the manual-intake path.
    issue_id: str = ""

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
    is_production_code: bool = True
    affected_service_count: int = 1
    fix_complexity: str = "moderate"

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

    repo = ""
    try:
        cfgs = pod.records.list("github_config", limit=1).to_dict()["items"]
        if cfgs:
            repo = (cfgs[0].get("repo") or "").strip()
    except Exception:
        pass

    if data.issue_id:
        issue_id = data.issue_id
        try:
            pod.table("issues").update(issue_id, {"triage_status": "triaged"})
        except Exception:
            pass
    else:
        issue = pod.table("issues").create({
            "source": data.source or "manual",
            "external_id": data.external_id,
            "repo": repo,
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
        "is_production_code": bool(data.is_production_code),
        "affected_service_count": int(data.affected_service_count or 1),
        "fix_complexity": data.fix_complexity or "moderate",
        "decision_status": "pending",
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
