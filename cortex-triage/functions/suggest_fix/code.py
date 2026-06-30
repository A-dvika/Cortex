#input_type_name: SuggestFixInput
#output_type_name: SuggestFixResult
#function_name: suggest_fix

"""Deterministic fix suggestion step for the demo path.

This replaces the fix-suggester agent in the workflow so vague incidents do not
leave the run waiting on a second model call.
"""

from pydantic import BaseModel
from lemma_sdk import FunctionContext


class SuggestFixInput(BaseModel):
    title: str
    body: str = ""
    bug_type: str = "other"


class SuggestFixResult(BaseModel):
    fix_title: str
    fix_suggestion: str
    fix_code: str = ""
    risk_level: str = "medium"
    estimated_effort: str = "small"
    fix_confidence: float = 0.45


def _mentions(text: str, *needles: str) -> bool:
    haystack = text.lower()
    return any(needle in haystack for needle in needles)


async def suggest_fix(ctx: FunctionContext, data: SuggestFixInput) -> SuggestFixResult:
    text = f"{data.title} {data.body}"
    bug_type = (data.bug_type or "other").lower()

    if bug_type == "crash" or _mentions(text, "500", "exception", "crash", "panic"):
        return SuggestFixResult(
            fix_title="Investigate failing request path",
            fix_suggestion=(
                "Check the failing endpoint logs from the deploy window, identify the first "
                "uncaught exception, and add the smallest guard or rollback needed to restore "
                "the path. Add a regression test for the failing request before merging."
            ),
            risk_level="medium",
            estimated_effort="small",
            fix_confidence=0.5,
        )

    if bug_type == "performance":
        return SuggestFixResult(
            fix_title="Profile the slow path",
            fix_suggestion=(
                "Capture the slow request or job trace, then remove the highest-cost query or "
                "loop first. Prefer an index, pagination, caching, or async handoff over a broad rewrite."
            ),
            risk_level="medium",
            estimated_effort="medium",
            fix_confidence=0.45,
        )

    if bug_type == "auth":
        return SuggestFixResult(
            fix_title="Verify auth checks",
            fix_suggestion=(
                "Reproduce the failing auth path and inspect token, scope, and permission checks "
                "at the boundary. Patch the smallest incorrect check and add coverage for the denied case."
            ),
            risk_level="medium",
            estimated_effort="small",
            fix_confidence=0.45,
        )

    if bug_type in {"ui", "docs"}:
        return SuggestFixResult(
            fix_title="Patch the visible issue",
            fix_suggestion=(
                "Reproduce the reported screen or document section, apply the smallest targeted "
                "copy/layout correction, and verify the reported state plus one adjacent state."
            ),
            risk_level="low",
            estimated_effort="trivial",
            fix_confidence=0.7,
        )

    return SuggestFixResult(
        fix_title="Reproduce and isolate the report",
        fix_suggestion=(
            "Reproduce the issue from the report, collect the failing logs or state, and patch the "
            "smallest confirmed root cause. Keep confidence moderate until the failing path is observed."
        ),
        risk_level="medium",
        estimated_effort="small",
        fix_confidence=0.4,
    )
