# 02 · Architecture overview

Now we apply the primitives from [01](01-lemma-mental-model.md) to a real product.

## The problem we're solving

Engineering teams receive bugs from everywhere (GitHub, Slack, email, support).
Someone has to:
- read each report and decide *how bad it is* (severity),
- classify *what kind* of bug it is,
- propose a first fix so an engineer isn't starting from zero, and
- eventually turn the fixed pile into **release notes**.

Done by hand this is slow, inconsistent (one person's P1 is another's P3), and
boring. It's a perfect fit for "AI does judgment, code does the bookkeeping."

## The solution in one diagram

The product has grown past "triage + fix suggestion" into a small **incident
response pipeline**: classify → fix → find who broke it → escalate → (if safe)
propose a PR — with a human approval gate before anything touches the real repo.

```
 INTAKE          JUDGMENT (agents)            RULES (functions)                  DATA (tables)
 ─────────────   ──────────────────────────   ─────────────────────────────────  ──────────────
 a bug report ─▶ triage-agent                                                    issues
 title, body,     • classify bug_type                                            bugs (severity,
 source, url…     • score impact/urgency  ─┐                                       type, scores,
                   • P1/P2/P3 + reasoning   ├─▶ persist_triage ──▶ issues+bugs+fixes  owner, fix_pr_*)
                                            │                         │           fixes (suggestion,
                 fix-suggester              │                         │             code, risk)
                   • draft fix, code,    ───┘                         ▼
                     risk, effort                              suggest_owner (GitHub, read-only)
                                                                 commits + CODEOWNERS
                                                                 → likely owner + breaking commit
                                                                         │
                                                                         ▼
                                                                  open_incident
                                                                  P1=urgent alert, P2=normal, P3=silent
                                                                         │             incidents
                                                                         ▼             alert_config
                                                                  open_fix_pr           github_config
                                                                  low-risk + confident?
                                                                  → real PR (proposal file,
                                                                    never splices live code)

 human reviews ──▶ assign_owner (write: assign + comment)   ack_incident   resolve_incident
                   (Approve & assign button, board UI)      (stop escalation)

 stale P1s ──▶ escalate-incidents (TIME schedule, every 5 min) ──▶ escalate_incidents
               (pages again if still unacked past alert_config.escalation_minutes)

 "release v0.3.0" ─▶ release-notes-writer (reads bugs+fixes) ─────────────▶   release_notes
```

Three workflows tie it together:
- **`triage-issue`** — the core loop: `FORM → triage-agent → fix-suggester → persist_triage → suggest_owner → open_incident → open_fix_pr → END`
- **`compile-release-notes`** — `FORM(version) → release-notes-writer → END`
- **`escalate-incidents`** — `escalate_incidents → END`, fired by a TIME schedule, no human trigger

## Why this shape? (the design decisions)

### 1. Two agents, not one mega-agent
We could have one agent "do everything." We split into `triage-agent`
(classify + score) and `fix-suggester` (propose a fix) because:
- **Single responsibility** → each instruction is short and focused, which makes
  the model more reliable and the output easier to validate.
- **Independent evolution** → you can improve fix suggestions without touching
  the severity rubric.
- **Composability** → the workflow can run them in sequence and even reuse the
  triage agent elsewhere.

### 2. Persistence is a *function*, not an agent
The agents return structured JSON; a deterministic function (`persist_triage`)
writes the rows. **Why:** writing to a database must be exact and identical every
time — that's a *rule*, not a *judgment*. Letting an agent "save the row" invites
hallucinated fields and non-determinism. This is the agents-vs-functions
principle in action (see [05](05-functions.md)).

### 3. Three tables with foreign keys, not one wide table
`issues → bugs → fixes` are separate tables linked by foreign keys. **Why:** they
have different lifecycles and cardinalities — one issue yields one bug record,
which may yield one (or more) fix suggestions; release notes reference many bugs.
Modeling them separately keeps each row clean and queryable (see [03](03-data-model.md)).

### 4. A FORM as the entry point
Each workflow starts with a `FORM` node that defines the run's input schema. **Why:**
it gives the workflow a typed, validated entry — whether a human submits it or a
future **surface** (Slack/GitHub) feeds it programmatically. The same workflow
works for both.

### 5. Read-only owner-finding is separate from the write that assigns
`suggest_owner` only *reads* GitHub (commits, CODEOWNERS) — no token required —
and writes its finding onto the `bugs` row. `assign_owner` is the only place that
*writes* to GitHub (assign + comment), and it only runs when a human clicks
**Approve & assign** on the board. **Why:** finding a likely owner is safe to do
automatically and constantly; acting on a real repo on someone's behalf is not —
so the read and the write are different functions with different trust levels,
not one function doing both.

### 6. "Auto-resolve" opens a proposal PR, never edits a real file
`open_fix_pr` is eligibility-gated (`risk == "low"` and `confidence ≥ 0.6`). When
eligible, it opens a real PR on a new branch — but the PR adds a new
`cortex-fixes/<id>.md` file describing the fix, it never splices the AI's code
snippet into an existing source file. **Why:** an unverified AI patch landing in
a real file without tests is how you cause the *next* incident, not resolve this
one. A human still has to write and merge the actual diff; the PR's job is to
hand them a reviewed starting point and a tagged reviewer, not to merge code.

### 7. Incidents escalate without a human in the loop, but never act without one
`open_incident` creates an `incidents` row and alerts immediately for P1 (with an
`@mention` of the suggested owner), normally for P2, silently for P3. A separate
**schedule** (not a workflow trigger from `triage-issue`) sweeps for unacked P1s
every 5 minutes and pages again — this runs independently of any single triage
run, which is exactly the point: escalation must keep happening even if nobody is
actively triaging right now.

## Data flow, step by step (the happy path)

1. A bug report enters the `triage-issue` workflow via the **FORM** (`intake`).
2. **`triage-agent`** receives `title`+`body`, returns `{bug_type, severity,
   impact_score, urgency_score, confidence, reasoning, …}`.
3. **`fix-suggester`** receives `title`+`body`+`bug_type`, returns `{fix_title,
   fix_suggestion, fix_code, risk_level, estimated_effort, fix_confidence}`.
4. **`persist_triage`** (function) takes the form input + both agents' outputs and
   writes: one `issues` row (status `triaged`), one `bugs` row, one `fixes` row.
5. The run ends; the rows are now queryable and would render on a dashboard/app.

5. **`suggest_owner`** reads the configured GitHub repo's commit history for the
   implicated file (parsed from the report) plus `CODEOWNERS`, and writes
   `assignee_login`, `assignee_reason`, `breaking_commit` back onto the bug row.
6. **`open_incident`** creates an `incidents` row and, for P1/P2, posts to the
   `alert_config` Slack webhook if one is configured (silently skips otherwise).
7. **`open_fix_pr`** checks eligibility on the linked fix; if eligible, opens a
   branch + proposal PR on GitHub and requests review from the suggested owner.
8. A human reviews the board: clicks **Approve & assign** (runs `assign_owner`,
   the only GitHub *write* in the triage path) and/or **Ack** on the incident
   (runs `ack_incident`, stopping escalation).

For release notes: the `release-notes-writer` agent reads the `bugs`/`fixes`
tables and writes a `release_notes` row for a given version.

For incident escalation: the `escalate-incidents` workflow, fired by its own
TIME schedule (not by `triage-issue`), sweeps all `open` P1 incidents older than
`alert_config.escalation_minutes` and pages the escalation channel once more.

## What "done" looks like (verified)

Running the core workflow over five sample reports produced exactly the spread
you'd hope for:

| Severity | Type | Impact/Urg | Report |
|---|---|---|---|
| P1 | crash | 95 / 95 | Checkout returns 500 for all users |
| P2 | data | 65 / 65 | Export CSV drops last row (odd sets) |
| P2 | performance | 55 / 50 | Dashboard 12s for >10k orders |
| P2 | auth | 50 / 55 | Login 401 after password reset |
| P3 | ui | 10 / 5 | Typo: 'Recieve notifications' |

The agent even ranked the data-integrity bug above the other P2s and dumped the
typo to P3 — judgment we never hand-coded.

Next: how the tables are modeled → [03 · Data model](03-data-model.md)
