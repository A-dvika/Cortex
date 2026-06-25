# 07 · Permissions & security

Lemma's security model is small but strict, and getting it wrong produces the most
confusing class of bug ("the agent runs but sees nothing"). So it's worth a page.

## The golden rule: zero access by default

An agent or function can touch **nothing** until you explicitly grant it. There is
no ambient "it's all in one pod, so everything can see everything." You list every
table (and folder/app) a worker needs, and only those.

> **Why so strict?** Least privilege. A triage agent has no business reading a
> payroll table, even in the same org. Explicit grants make the blast radius of any
> single agent obvious and small.

## Anatomy of a grant

Grants live inside the agent/function JSON under `permissions.grants`:

```json
"permissions": { "grants": [
  { "resource_type": "datastore_table",
    "resource_name": "release_notes",
    "permission_ids": ["datastore.table.read",
                       "datastore.record.read",
                       "datastore.record.write"] }
] }
```

- **`resource_type`** — what kind of thing (`datastore_table` for a table).
- **`resource_name`** — which one, *by name* (so bundles stay portable across pods).
- **`permission_ids`** — the specific verbs:
  - `datastore.table.read` — see the table/schema,
  - `datastore.record.read` — read rows,
  - `datastore.record.write` — create/update rows.

## How Cortex-Triage applies it

| Worker | Grants | Rationale |
|--------|--------|-----------|
| `triage-agent` | *(none)* | pure reasoner — input → JSON, touches no tables |
| `fix-suggester` | *(none)* | pure reasoner |
| `persist_triage` (fn) | `issues`, `bugs`, `fixes`: read + write | it's the only writer of triage data |
| `release-notes-writer` | `bugs`, `fixes`: read · `release_notes`: read + write | reads the source, writes the changelog |

> **Notice the asymmetry:** the *function* holds the write power for triage data,
> not the agents. The agents propose; the function commits. Permissions encode that
> same agents-vs-functions philosophy from [05](05-functions.md) — the thing that
> can do irreversible writes is the deterministic one.

## Access scope vs sharing (two different switches)

Lemma separates two questions that are easy to conflate:
- **Access scope** — *what a worker can touch* (the grants above).
- **Sharing / visibility** — *who can see and use the resource itself*
  (`visibility: PERSONAL | POD | PUBLIC | RESTRICTED`).

Our resources are `visibility: POD` (the whole pod team can use them) while each
worker's *access scope* stays narrow. "Everyone on the team can open the triage
app" and "the triage agent can only touch three tables" are independent facts.

## Row-level security (RLS), revisited

From [03](03-data-model.md): RLS decides whether rows are private-per-user
(`enable_rls: true`, each row owned via `user_id`) or shared (`false`). Cortex
data is a shared queue, so RLS is off.

> **The #1 "agent sees nothing" checklist:**
> 1. Did you grant the table at all? (zero by default)
> 2. Did you grant `record.read` (not just `table.read`)?
> 3. Is RLS hiding rows owned by another user? (shared data should be `enable_rls:false`)
> 4. For writes, did you grant `record.write`?

## Human approval (the other guardrail)

Workflows can include an **approval** step — a human gate before anything with real
consequences. Cortex-Triage doesn't auto-act on the outside world yet (it writes to
its own tables), so it has no approval node. The moment we add a **connector** that,
say, posts a comment back to GitHub or closes an issue, an approval gate before that
action is the responsible design — see the roadmap in [09](09-lessons-and-roadmap.md).

Next: getting it onto a real backend → [08 · Deploy, run & debug](08-deploy-run-debug.md)
