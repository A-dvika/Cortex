#input_type_name: PersistReleaseNotesInput
#output_type_name: PersistReleaseNotesResult
#function_name: persist_release_notes

"""Deterministic write of the compiled release notes. Mirrors persist_triage:
the agent decides the prose, this function guarantees it lands in the table
the same way every time."""

from typing import List, Optional

from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod


class PersistReleaseNotesInput(BaseModel):
    version: str
    notes_markdown: str = ""
    highlights: List[str] = []
    breaking_changes: List[str] = []
    bug_count: int = 0


class PersistReleaseNotesResult(BaseModel):
    ok: bool
    release_id: Optional[str] = None


def _row_id(record):
    if record is None:
        return None
    if isinstance(record, dict):
        return record.get("id")
    return getattr(record, "id", None)


async def persist_release_notes(ctx: FunctionContext, data: PersistReleaseNotesInput) -> PersistReleaseNotesResult:
    pod = Pod.from_env()
    try:
        row = pod.table("release_notes").create({
            "version": data.version,
            "notes_markdown": data.notes_markdown,
            "highlights": data.highlights,
            "breaking_changes": data.breaking_changes,
            "bug_count": data.bug_count,
        })
    except Exception as e:
        return PersistReleaseNotesResult(ok=False)
    return PersistReleaseNotesResult(ok=True, release_id=_row_id(row))
