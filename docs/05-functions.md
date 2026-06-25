# 05 · Functions

If agents are judgment, **functions are rules**: plain Python the pod runs the same
way every time. Cortex-Triage has one — `persist_triage` — and it does the most
important non-negotiable job: writing rows correctly.

## Anatomy of a function

```
functions/persist_triage/
  persist_triage.json   ← config (type, visibility, permissions, code ref)
  code.py               ← the actual Python
```

The JSON points at the code with `{"$file": "code.py"}`:

```json
{
  "name": "persist_triage",
  "description": "Deterministically writes the triaged issue, bug, and fix rows.",
  "type": "API",          // API = sync request/response; JOB = async background
  "visibility": "POD",
  "code": { "$file": "code.py" },
  "permissions": { "grants": [
    { "resource_type": "datastore_table", "resource_name": "issues",
      "permission_ids": ["datastore.table.read","datastore.record.read","datastore.record.write"] },
    { "resource_type": "datastore_table", "resource_name": "bugs",  "permission_ids": [ ... ] },
    { "resource_type": "datastore_table", "resource_name": "fixes", "permission_ids": [ ... ] }
  ] }
}
```

> **`type` API vs JOB:** `API` is a synchronous step (the workflow waits for its
> result) — right for "write three rows and return ids." `JOB` is for long async
> background work. Persisting is fast and inline, so it's `API`.

## The code contract

Lemma functions follow a precise shape. Here's the real `code.py` (trimmed):

```python
#input_type_name: PersistTriageInput
#output_type_name: PersistTriageResult
#function_name: persist_triage

from typing import Optional
from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod


class PersistTriageInput(BaseModel):
    # from the intake form
    title: str
    body: str = ""
    source: str = "manual"
    url: str = ""
    reporter: str = ""
    external_id: str = ""
    # from the triage agent
    bug_type: str = "other"
    severity: str = "P3"
    impact_score: int = 0
    urgency_score: int = 0
    confidence: float = 0.0
    is_duplicate: bool = False
    duplicate_of: str = ""
    reasoning: str = ""
    # from the fix-suggester agent
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


async def persist_triage(ctx: FunctionContext, data: PersistTriageInput) -> PersistTriageResult:
    pod = Pod.from_env()                          # authenticated as this function's principal

    issue = pod.table("issues").create({ ... "triage_status": "triaged" })
    issue_id = _row_id(issue)

    bug = pod.table("bugs").create({ "issue_id": issue_id, "severity": data.severity, ... })
    bug_id = _row_id(bug)

    fix_id = None
    if data.fix_suggestion or data.fix_title:
        fix = pod.table("fixes").create({ "bug_id": bug_id, ... })
        fix_id = _row_id(fix)

    return PersistTriageResult(ok=True, issue_id=issue_id, bug_id=bug_id, fix_id=fix_id, severity=data.severity)
```

### What each piece means
- **The header comments** (`#input_type_name:` …) declare the type names Lemma uses
  to generate the function's input/output schema. Keep them in sync with the classes.
- **`pydantic.BaseModel`** defines a typed input and output. Typed inputs are why a
  workflow can map fields into the function safely.
- **`async def <function_name>(ctx, data)`** is the entry point; its name must match
  `#function_name`. `ctx` is the `FunctionContext`; `data` is your input model.
- **`Pod.from_env()`** gives an authenticated pod client scoped to this function's
  permissions. `pod.table("bugs").create({...})` inserts a row.

> **Gotcha we hit — return shapes.** `create()` may return a dict or an object
> depending on context, so we wrote a tiny helper to read the new row's id either
> way:
> ```python
> def _row_id(record):
>     if record is None: return None
>     if isinstance(record, dict): return record.get("id")
>     return getattr(record, "id", None)
> ```
> Defensive code like this is exactly the kind of thing that belongs in a function,
> never in an agent prompt.

### Defaults everywhere
Every field except `title` has a default. **Why:** a real report might omit `url`
or `reporter`. Defaults mean a partial report still persists cleanly. (This pairs
with a workflow-level fix we discovered — see [06](06-workflows.md) and [09](09-lessons-and-roadmap.md).)

## Why persistence is a function, not an agent (the whole point)

| | Agent | Function |
|---|-------|----------|
| Good at | judgment, language, ambiguity | exact, repeatable rules |
| Output | may vary run to run | identical for identical input |
| Writing DB rows | risky (hallucinated/renamed fields) | safe and predictable |

The agents decide *what* the severity and fix are; the function guarantees those
decisions land in the right columns, the same way, every time. If you remember one
thing from these docs: **don't ask a language model to be a database driver.**

Next: how it's all wired in order → [06 · Workflows](06-workflows.md)
