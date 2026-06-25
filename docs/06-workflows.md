# 06 · Workflows

A workflow is a **graph**: nodes (steps) connected by edges (order). This is where
agents and functions get wired into a process that runs start-to-finish.

## The pieces of a workflow

```json
{
  "name": "triage-issue",
  "start": { "type": "MANUAL" },     // how the workflow is triggered
  "nodes": [ ... ],                  // the steps
  "edges": [ ... ],                  // the order between steps
  "visibility": "POD"
}
```

### `start.type` — how a run begins
- `MANUAL` — started by a person or an API/CLI call (what we use).
- `SCHEDULED` — started by a schedule (cron).
- `DATASTORE_EVENT` — started when a row is inserted/updated in a table.
- `EVENT` — started by an external event.

> A natural upgrade: change `triage-issue` to `DATASTORE_EVENT` on the `issues`
> table so that *any* new issue row (e.g. created by a Slack surface) auto-triages.

### Node types
`FORM`, `AGENT`, `FUNCTION`, `DECISION`, `LOOP`, `WAIT_UNTIL`, `END`. We use four:
- **FORM** — collects the run's typed input (the entry point).
- **AGENT** — runs an agent with mapped inputs.
- **FUNCTION** — runs a function with mapped inputs.
- **END** — terminal node.

### Edges
Each edge is `{ "id", "source", "target" }` — "after `source` finishes, go to
`target`." Our flows are linear, so the edges form a simple chain.

## `triage-issue` walked node by node

```
intake(FORM) ──▶ triage(AGENT) ──▶ suggest(AGENT) ──▶ persist(FUNCTION)
   ──▶ owner(FUNCTION: suggest_owner) ──▶ incident(FUNCTION: open_incident)
   ──▶ auto_resolve(FUNCTION: open_fix_pr) ──▶ end(END)
```

The five steps after `persist` are all `FUNCTION` nodes, not agents — by the time
ownership-finding, incident-opening, and PR eligibility are decided, every input
is already structured data (the bug row), so there's no judgment left to do,
only rules to apply. That's the agents-vs-functions principle holding all the way
through the pipeline, not just at the persistence step.

**1. `intake` (FORM)** — defines what a report looks like:

```json
{ "id": "intake", "type": "FORM", "config": { "input_schema": {
  "type": "object",
  "properties": {
    "title":  { "type": "string", "title": "Title" },
    "body":   { "type": "string", "title": "Description", "default": "" },
    "source": { "type": "string", "enum": ["github","slack","email","manual"], "default": "manual" },
    "url":    { "type": "string", "default": "" },
    "reporter":    { "type": "string", "default": "" },
    "external_id": { "type": "string", "default": "" }
  },
  "required": ["title"] } } }
```

> **Gotcha that bit us — and the fix.** Originally the optional fields had no
> `default`. When a report omitted, say, `url`, the downstream mapping
> `intake.url` *resolved to nothing*, and the run FAILED at the `persist` node with
> `path 'intake.url' resolved to nothing`. Adding `"default": ""` to every optional
> field makes a partial report resolve cleanly. **Lesson: give FORM fields defaults
> so missing input becomes empty, not absent.**

**2. `triage` (AGENT)** — maps form fields into `triage-agent`:

```json
{ "id": "triage", "type": "AGENT", "config": {
  "agent_name": "triage-agent",
  "input_mapping": {
    "title": { "type": "expression", "value": "intake.title" },
    "body":  { "type": "expression", "value": "intake.body" } } } }
```

**3. `suggest` (AGENT)** — `fix-suggester`, and notice it can consume the previous
agent's output (`triage.bug_type`):

```json
"input_mapping": {
  "title":    { "type": "expression", "value": "intake.title" },
  "body":     { "type": "expression", "value": "intake.body" },
  "bug_type": { "type": "expression", "value": "triage.bug_type" } }
```

**4. `persist` (FUNCTION)** — the deterministic write. It maps **everything** —
form input + both agents' structured outputs — into the function's typed input:

```json
"input_mapping": {
  "title":    { "type": "expression", "value": "intake.title" },
  "severity": { "type": "expression", "value": "triage.severity" },
  "impact_score": { "type": "expression", "value": "triage.impact_score" },
  "reasoning":    { "type": "expression", "value": "triage.reasoning" },
  "fix_suggestion": { "type": "expression", "value": "suggest.fix_suggestion" },
  "risk_level":     { "type": "expression", "value": "suggest.risk_level" }
  /* …and the rest… */ }
```

**5. `owner` (FUNCTION)** — `suggest_owner`, mapped from `persist`'s own output:

```json
{ "id": "owner", "type": "FUNCTION", "config": { "function_name": "suggest_owner",
  "input_mapping": { "bug_id": { "type": "expression", "value": "persist.bug_id" } } } }
```

This is the first node to consume a **function's** output rather than an agent's
— `persist_triage` returns `{issue_id, bug_id, fix_id, severity}`, and `owner`
reads `persist.bug_id` from it. Expressions don't care whether the upstream node
was an AGENT or a FUNCTION; they just read whatever fields its output declared.

**6. `incident` (FUNCTION)** — `open_incident`, mapped from both `intake` and
`triage` (it needs the original title/source *and* the agent's severity call):

```json
"input_mapping": {
  "title":    { "type": "expression", "value": "intake.title" },
  "summary":  { "type": "expression", "value": "triage.reasoning" },
  "severity": { "type": "expression", "value": "triage.severity" },
  "bug_id":   { "type": "expression", "value": "persist.bug_id" },
  "source":   { "type": "expression", "value": "intake.source" } }
```

**7. `auto_resolve` (FUNCTION)** — `open_fix_pr`, same `bug_id` pattern as `owner`.
It re-reads the bug's linked fix internally rather than having it mapped in,
since by this point the eligibility check (`risk_level`, `confidence`) is the
function's own job, not the workflow's.

**8. `end` (END)** — done. The rows now exist across `issues`/`bugs`/`fixes`, plus
possibly `incidents` (if severity warranted one) and a `fix_pr_url` on the bug
(if the fix was eligible for auto-PR).

> **Why these run inside `triage-issue` instead of as their own workflow.** They
> share the same `bug_id` and need to run unconditionally right after persistence
> — there's no human decision point between "bug saved" and "find out who broke
> it." Compare to `assign_owner` and `ack_incident`, which run **outside** any
> workflow, triggered directly from the app's buttons (`client.functions.run(...)`)
> — those *are* human decision points, so they're standalone functions invoked on
> demand, not steps in an automatic chain.

### The expression mental model
`<node_id>.<field>` reads a value produced earlier in the run:
- `intake.title` → a FORM field,
- `triage.severity` → a `triage-agent` output (defined by its `output_schema`),
- `suggest.risk_level` → a `fix-suggester` output.

This is *exactly* why [structured `output_schema`](04-agents.md) matters: it's the
named, typed surface other nodes read from.

## `compile-release-notes` walked

```
intake(FORM: version) ──▶ compile(AGENT: release-notes-writer) ──▶ end(END)
```

Simpler graph, but the agent does more *inside itself*: it uses POD tools to read
`bugs`+`fixes` and write a `release_notes` row. That extra tool use is powerful but
less predictable than a pure reasoner — see the honest status in
[09 · Lessons](09-lessons-and-roadmap.md).

## `escalate-incidents` — a workflow with no human entry point

```
escalate(FUNCTION: escalate_incidents) ──▶ end(END)
```

The smallest possible workflow — one function, no FORM. **Why no FORM:** nothing
ever submits input to this run; it's started entirely by a **schedule**, not a
person or another workflow:

```json
{ "name": "escalate-incidents", "schedule_type": "TIME",
  "config": { "cron": "*/5 * * * *" },
  "workflow_name": "escalate-incidents", "is_active": true }
```

Every 5 minutes, the schedule creates a run of `escalate-incidents`, which calls
`escalate_incidents` (sweeps `incidents` for `status=open`, `severity=P1`, older
than `alert_config.escalation_minutes`, and pages again). This is the one part of
Cortex-Triage that **acts without anyone asking it to** — see [05](05-functions.md)
for why that's still safe: it only re-sends an alert, it never assigns, merges,
or closes anything on its own.

> **`start.type` for a schedule-driven workflow is still `MANUAL`** — the
> schedule is what creates the run, not a `start.type: SCHEDULED` workflow field.
> A workflow doesn't know or care *how* its runs get created.

## Validating a workflow before import
`lemma workflow validate` statically checks a graph (entry node, edges, an END,
valid targets) before you import — catch typos without a round trip.

Next: the guardrails that keep agents/functions honest → [07 · Permissions](07-permissions-and-security.md)
