# 03 · Data model (tables)

Tables are where Cortex-Triage keeps state. Good data modeling is most of the
battle, so let's go slowly.

## The seven tables and how they relate

```
issues  (one raw report)
  └──< bugs  (one triaged verdict per issue)        issue_id ─▶ issues.id
         ├──< fixes     (one suggested fix per bug)  bug_id  ─▶ bugs.id
         └──< incidents (one escalation per bug)     bug_id  ─▶ bugs.id

release_notes (one compiled changelog per version)   references many bugs (by content)
github_config  (which repo + PAT to read/write)       PERSONAL, RLS on
alert_config   (Slack webhooks + escalation timing)   PERSONAL, RLS on
```

`──<` means "one to many" (one issue can have a bug; one bug can have fixes and
an incident). `github_config`/`alert_config` aren't part of the triage lineage —
they're per-user **settings** tables the functions read configuration from.

## How a table is defined

A table is a JSON file at `cortex-triage/tables/<name>/<name>.json`. Here's the
real `bugs` table, annotated:

```json
{
  "name": "bugs",
  "primary_key_column": "id",      // an "id" UUID is auto-added; we just name it
  "enable_rls": false,             // shared team data (see RLS below)
  "visibility": "POD",             // visible to the whole pod
  "columns": [
    { "name": "issue_id", "type": "UUID", "required": true,
      "foreign_key": { "references": "issues.id" } },   // link to the issue
    { "name": "title", "type": "TEXT", "required": true, "max_length": 300 },
    { "name": "bug_type", "type": "ENUM", "required": true, "default": "other",
      "options": ["crash","performance","ui","data","auth","docs","other"] },
    { "name": "severity", "type": "ENUM", "required": true, "default": "P3",
      "options": ["P1","P2","P3"] },
    { "name": "impact_score", "type": "INTEGER", "default": 0 },
    { "name": "urgency_score", "type": "INTEGER", "default": 0 },
    { "name": "confidence", "type": "FLOAT", "default": 0 },
    { "name": "is_duplicate", "type": "BOOLEAN", "default": false },
    { "name": "duplicate_of", "type": "TEXT", "max_length": 300 },
    { "name": "reasoning", "type": "TEXT" },
    { "name": "assignee_login", "type": "TEXT", "max_length": 120 },     // from suggest_owner
    { "name": "assignee_reason", "type": "TEXT" },
    { "name": "breaking_commit", "type": "TEXT", "max_length": 60 },
    { "name": "breaking_commit_url", "type": "TEXT", "max_length": 600 },
    { "name": "assign_status", "type": "ENUM", "required": true, "default": "none",
      "options": ["none", "suggested", "assigned"] },                   // assign_owner sets "assigned"
    { "name": "fix_pr_url", "type": "TEXT", "max_length": 600 },        // from open_fix_pr
    { "name": "fix_pr_status", "type": "ENUM", "required": true, "default": "none",
      "options": ["none", "ineligible", "opened", "failed"] }
  ],
  "config": {}
}
```

> **Why these columns live on `bugs` instead of a separate "ownership" table:**
> they're 1:1 facts about *this* bug (one owner suggestion, one PR attempt), not a
> growing list — so adding columns is simpler than adding another join. Compare
> to `fixes`/`incidents`, which are genuinely 1:many and earn their own table.

## Concepts you need to know

### Column types
Lemma's column types: `BOOLEAN DATE DATETIME ENUM FILE_PATH FLOAT INTEGER JSON
SERIAL TEXT USER UUID VECTOR`. We use:
- **ENUM** for closed sets (`severity`, `bug_type`, `risk_level`) — this constrains
  values at the database level, so an agent literally cannot store "P4".
- **INTEGER / FLOAT** for scores and confidence.
- **TEXT** for free prose (`reasoning`, `suggestion`, `code_snippet`).
- **UUID** for foreign keys.
- **JSON** for list-shaped fields (`release_notes.highlights`, `breaking_changes`).

> **Why ENUMs matter here:** the agent's `output_schema` *also* constrains these
> to the same options (belt and suspenders). The schema guides the model; the ENUM
> guarantees the database. Two layers of "garbage can't get in."

### System columns are automatic — never declare them
Every table auto-gets `id`, `created_at`, `updated_at`, and (when RLS is on)
`user_id`. **Gotcha:** if you declare any of these yourself, import fails. We rely
on `created_at` for ordering runs without ever writing it.

### Foreign keys
`bugs.issue_id` declares `"foreign_key": { "references": "issues.id" }`. On import,
Lemma orders table creation by dependency, so `issues` is created before `bugs`
before `fixes` automatically — you don't sequence them yourself.

> **Design note — why `duplicate_of` is TEXT, not a self-foreign-key.** A bug
> pointing at another bug would be a self-referential FK (a table referencing
> itself), which complicates creation ordering. Duplicate detection is a roadmap
> feature, so we store a human-readable hint as TEXT now and can upgrade it to a
> proper FK (or a `VECTOR` similarity search) later without a painful migration.

### Row-level security (RLS)
`enable_rls: true` means rows are **private per user** (each row carries a
`user_id` and users only see their own). `enable_rls: false` means **shared team
data**. Cortex-Triage triage data is a shared team queue, so all four tables set
`enable_rls: false` with `visibility: POD`.

> **Rule of thumb:** personal to-do-style data → RLS on. Shared operational data a
> whole team works → RLS off + POD visibility. Choosing wrong is the most common
> "why can't the agent see the rows?" bug.

## The other tables (summary)

- **`issues`** — the raw report: `source` (ENUM github/slack/email/manual),
  `external_id`, `title`, `body`, `url`, `reporter`, and `triage_status`
  (ENUM pending/triaged/done). The function flips it to `triaged` when done.
  `external_id` is the **GitHub issue number** — `assign_owner` and `open_fix_pr`
  read it to know which real issue to act on.
- **`fixes`** — `bug_id` (FK→bugs.id), `title`, `suggestion`, `code_snippet`,
  `risk_level` (ENUM), `estimated_effort` (ENUM), `confidence`. `risk_level` +
  `confidence` together gate `open_fix_pr`'s eligibility check.
- **`release_notes`** — `version`, `notes_markdown`, `highlights` (JSON),
  `breaking_changes` (JSON), `bug_count`.
- **`incidents`** — `source` (ENUM), `title`, `summary`, `severity` (ENUM),
  `status` (ENUM open/acked/resolved), `bug_id` (FK→bugs.id), `assignee_login`,
  `escalation_level` (INTEGER), `alert_channel_msg`, `acked_at`/`resolved_at`
  (DATETIME). One row per bug that triggered an escalation; `escalation_level`
  is how `escalate_incidents` avoids re-paging the same incident endlessly.
- **`github_config`** *(PERSONAL, RLS on)* — `repo` (`owner/name`), `pat`,
  `label`. Each user connects their own; functions resolve "the invoking user's"
  row via `Pod.from_env()`'s delegated identity.
- **`alert_config`** *(PERSONAL, RLS on)* — `slack_webhook_url`,
  `escalation_webhook_url`, `escalation_minutes` (default 15), `label`.

> **Why `github_config`/`alert_config` are `PERSONAL` + RLS-on, unlike the rest:**
> a PAT and a Slack webhook are credentials, not team data — RLS means each
> user's row is private to them, never visible to (or read by) anyone else's
> functions. This is the same RLS mechanism from above, just used for the
> opposite reason: hiding rows, not sharing them.

Next: the agents that fill these tables with judgment → [04 · Agents](04-agents.md)
