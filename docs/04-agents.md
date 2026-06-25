# 04 · Agents

Agents are where the *judgment* lives. This is the part people find magical, so
let's demystify exactly how an agent is defined and made reliable.

## Anatomy of an agent

An agent is a folder with two files:

```
agents/triage-agent/
  triage-agent.json     ← the config (name, schemas, toolsets, permissions)
  instruction.md        ← the "job description" (its system prompt, basically)
```

The JSON references the markdown with `{"$file": "instruction.md"}`, so the prose
lives in a real `.md` file you can edit comfortably.

## Three ideas make an agent reliable

### 1. The instruction *is* a job description
Treat `instruction.md` like onboarding docs for a new hire: role, exactly what to
do, the rubric to apply, and hard boundaries. Vague instructions → vague output.

Cortex-Triage's `triage-agent` instruction embeds the **severity rubric** directly,
so the model isn't guessing what "P1" means:

```markdown
## Severity rubric (decide impact + urgency first, then map)
**P1 — critical.** Any one of:
- Production is down / fully broken / data loss or corruption.
- A paying customer or revenue path (checkout, payments) is blocked.
- More than ~100 users affected with no workaround.
...
When signals conflict, weight impact more than urgency. If the report is vague,
lower your confidence and lean one severity *down* rather than inflating P1.
```

> **Why embed the rubric?** This is *grounding*. Instead of relying on the model's
> generic prior about severity, we give it our team's explicit policy. That's what
> made it correctly call the checkout-500 a P1 ("blocking a paying-customer flow")
> and the typo a P3. The same job could be done with a **file** the agent cites;
> we inlined it because it's short and central.

### 2. `output_schema` turns prose into a contract
By default an LLM returns free text. We give the agent an **`output_schema`** (a
JSON Schema) so it returns *structured, validated fields* the next workflow step
can consume:

```json
"output_schema": {
  "type": "object",
  "properties": {
    "bug_type":      { "type": "string", "enum": ["crash","performance","ui","data","auth","docs","other"] },
    "severity":      { "type": "string", "enum": ["P1","P2","P3"] },
    "impact_score":  { "type": "integer", "minimum": 0, "maximum": 100 },
    "urgency_score": { "type": "integer", "minimum": 0, "maximum": 100 },
    "confidence":    { "type": "number", "minimum": 0, "maximum": 1 },
    "is_duplicate":  { "type": "boolean" },
    "duplicate_of":  { "type": "string" },
    "reasoning":     { "type": "string" }
  },
  "required": ["bug_type","severity","impact_score","urgency_score","confidence","reasoning"]
}
```

> **Why this is the linchpin.** Because `triage-agent` emits `severity` as one of
> exactly `P1/P2/P3`, the downstream `persist_triage` function can drop it straight
> into the `bugs.severity` ENUM with no parsing, no regex, no "the model said
> 'critical' but the column wants 'P1'." Structured output is what lets agents and
> deterministic code interlock cleanly.

### 3. Least-privilege access (`toolsets` + `permissions`)
- **`toolsets`** lists capability groups (e.g. `POD` for pod data tools).
- **`permissions.grants`** lists the *specific* tables/folders the agent may touch.
  Default is **zero** — you grant exactly what's needed (see [07](07-permissions-and-security.md)).

## The three agents in Cortex-Triage

| Agent | Judgment it provides | Reads | Writes | Output |
|-------|----------------------|-------|--------|--------|
| `triage-agent` | classify + score severity | — (reasons from input) | — | structured verdict |
| `fix-suggester` | propose a first-pass fix | — | — | structured fix |
| `release-notes-writer` | compile a changelog | `bugs`, `fixes` | `release_notes` | a written row |

Notice the split: `triage-agent` and `fix-suggester` are **pure reasoners** — they
take input and return structured output, touching no tables (the *function* persists
their work). `release-notes-writer` is different: it actively *uses pod tools* to
read many rows and write one, so it carries real permission grants.

> **Design choice — pure reasoner vs tool-using agent.** Pure reasoners are easier
> to make reliable: their whole job is "input → JSON." Tool-using agents are more
> powerful but more failure-prone (each tool call is a place to go wrong). That's
> exactly why our release-notes agent is the flaky one — see [09](09-lessons-and-roadmap.md)
> for the planned fix (move the table-reading into a function, leave only prose to
> the agent).

## How the workflow feeds an agent

In the workflow, an `AGENT` node maps inputs into the agent via expressions:

```json
{ "id": "triage", "type": "AGENT",
  "config": { "agent_name": "triage-agent",
    "input_mapping": {
      "title": { "type": "expression", "value": "intake.title" },
      "body":  { "type": "expression", "value": "intake.body" } } } }
```

`intake.title` means "the `title` field from the `intake` (FORM) node." The agent's
outputs are then referenced downstream as `triage.severity`, `triage.bug_type`,
etc. More on that in [06 · Workflows](06-workflows.md).

Next: the deterministic half → [05 · Functions](05-functions.md)
