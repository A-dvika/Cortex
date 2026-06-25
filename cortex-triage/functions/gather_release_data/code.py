#input_type_name: GatherReleaseDataInput
#output_type_name: GatherReleaseDataResult
#function_name: gather_release_data

"""Deterministic half of release-notes compilation: read bugs+fixes, join them,
and hand the writer agent a plain list of dicts. The agent that used to do this
join *and* write prose *and* persist a row inside one conversation was our most
failure-prone piece (every tool call is a place to go wrong) — this function
removes the table-reading from the agent entirely, leaving it a pure reasoner.
"""

from typing import List, Optional

from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod


class GatherReleaseDataInput(BaseModel):
    limit: int = 50


class BugSummary(BaseModel):
    title: str
    bug_type: str = "other"
    severity: str = "P3"
    reasoning: str = ""
    fix_title: str = ""
    fix_suggestion: str = ""
    risk_level: str = ""
    estimated_effort: str = ""


class GatherReleaseDataResult(BaseModel):
    ok: bool
    bug_count: int = 0
    bugs: List[BugSummary] = []
    detail: str = ""


def _sev_rank(s: str) -> int:
    return {"P1": 0, "P2": 1, "P3": 2}.get(s, 3)


async def gather_release_data(ctx: FunctionContext, data: GatherReleaseDataInput) -> GatherReleaseDataResult:
    pod = Pod.from_env()

    try:
        bugs = pod.records.list("bugs", limit=data.limit).to_dict()["items"]
    except Exception as e:
        return GatherReleaseDataResult(ok=False, detail="bugs read failed: " + str(e)[:140])

    try:
        fixes = pod.records.list("fixes", limit=500).to_dict()["items"]
    except Exception as e:
        return GatherReleaseDataResult(ok=False, detail="fixes read failed: " + str(e)[:140])

    fix_by_bug = {}
    for f in fixes:
        bid = f.get("bug_id")
        if bid and bid not in fix_by_bug:
            fix_by_bug[bid] = f

    bugs = sorted(bugs, key=lambda b: _sev_rank(b.get("severity")))

    summaries: List[BugSummary] = []
    for b in bugs:
        fix = fix_by_bug.get(b.get("id"), {})
        summaries.append(BugSummary(
            title=b.get("title") or "",
            bug_type=b.get("bug_type") or "other",
            severity=b.get("severity") or "P3",
            reasoning=b.get("reasoning") or "",
            fix_title=fix.get("title") or "",
            fix_suggestion=fix.get("suggestion") or "",
            risk_level=fix.get("risk_level") or "",
            estimated_effort=fix.get("estimated_effort") or "",
        ))

    return GatherReleaseDataResult(ok=True, bug_count=len(summaries), bugs=summaries,
                                   detail=str(len(summaries)) + " bug(s) gathered")
