# cortex-triage — Lemma pod bundle

A working **agentic incident-response operator** built on the Lemma SDK for the
Gappy AI hackathon. It turns a messy bug report into a triaged, severity-scored
issue with a suggested fix, finds who likely broke it on GitHub, opens an
incident (escalating P1s automatically), proposes a fix PR when it's safe to,
and compiles release notes on demand.

**Live:** https://cortex-board.apps.lemma.work

This directory **is** the product: a Lemma *pod bundle* (plain files) that you
import with `lemma pods import`. The bundle is the source of truth — edit files,
re-import. For the full teaching write-up, see [`../docs/`](../docs/README.md).

## What's inside (all real Lemma resources)

```
cortex-triage/
  pod.json
  tables/
    issues/          raw incoming reports
    bugs/            triaged + scored + owner/PR status (FK -> issues.id)
    fixes/           suggested fix per bug (FK -> bugs.id)
    incidents/       escalation per bug (FK -> bugs.id)
    release_notes/   compiled changelog rows
    github_config/   per-user repo + PAT (PERSONAL, RLS)
    alert_config/    per-user Slack webhooks + escalation timing (PERSONAL, RLS)
    source_config/   per-user Jira/Slack/email intake settings (PERSONAL, RLS)
  functions/
    persist_triage/     writes issue+bug+fix (Python, Pod.from_env)
    github_ping/        connectivity probe (verifies outbound HTTP works)
    ingest_external_report/ normalizes Jira/Slack/email/GitHub payloads into pending issues
    suggest_owner/       read-only GitHub: commits + CODEOWNERS -> likely owner
    assign_owner/        write: assigns the GitHub issue + comments (human-gated)
    open_incident/       creates an incident; P1=urgent alert, P2=normal, P3=silent
    ack_incident/        human acknowledges -> stops escalation
    escalate_incidents/  scheduled sweep: re-pages unacked P1s
    resolve_incident/    closes an incident once the bug is fixed
    open_fix_pr/          opens a proposal PR (never edits real code) if low-risk + confident
  agents/
    triage-agent/          classifies + scores severity (P1/P2/P3), structured output
    fix-suggester/         drafts a concrete fix (suggestion, code, risk, effort)
    release-notes-writer/  reads bugs+fixes, writes a release_notes row
  workflows/
    triage-issue/           intake->triage->fix->persist->owner->incident->auto-PR
    compile-release-notes/  version -> release-notes-writer
    escalate-incidents/     schedule-driven sweep (no human entry point)
  schedules/
    escalate-incidents/     TIME, every 5 minutes
  apps/
    cortex-board/           no-build HTML operator board (live URL above)
```

**Design choice that maps to Lemma's model:** agents do *judgment* (classify,
score, suggest); functions do deterministic rules, persistence, and GitHub
calls; workflows orchestrate the automatic chain; the app is where a human
makes the calls that shouldn't be automatic (assign, ack). See
[docs/02](../docs/02-architecture-overview.md) for the full rationale.

## Prerequisites (read this — Windows matters)

- **The Lemma CLI does not run on native Windows.** It does `import termios`
  (Unix-only) at startup, so every real command crashes with
  `ModuleNotFoundError: No module named 'termios'`.
  Two ways forward:
  1. **WSL (recommended).** Do all Lemma CLI work inside WSL/Ubuntu.
  2. **Windows + shim (dev/validation).** `PYTHONPATH=../scripts/winshim lemma ...`
     gets non-interactive commands running on native Windows.
- A **Lemma backend + auth token** — cloud (`lemma.work`) or local (`install.sh`).
- An **agent runtime** (model) — the default `system:lemma` profile is used.

## Deploy

```bash
uv tool install lemma-terminal               # if not already
lemma auth login                             # opens browser, stores token
lemma org create "your-org"                  # first time only
lemma pod create "cortex-triage" --org <ORG_UUID>
lemma pods import ./cortex-triage --pod <POD_ID> --dry-run --timeout 200
lemma pods import ./cortex-triage --pod <POD_ID> --timeout 300
```

Re-importing **upserts by resource name** — safe to run repeatedly as the bundle
grows. Build order (tables → functions → agents → workflows → schedules → apps)
is handled automatically.

## Run it

```bash
# Trigger the full triage pipeline on one report:
lemma workflow run triage-issue --pod <POD_ID> --wait -d '{
  "title": "Checkout returns 500 for all users",
  "body": "Since the 14:00 deploy every payment attempt fails. File: src/checkout.js",
  "source": "manual"
}'

# Inspect results:
lemma records list bugs --pod <POD_ID>
lemma records list incidents --pod <POD_ID>

# Connect a real GitHub repo (enables owner-suggestion + assign + auto-PR):
lemma records create github_config --pod <POD_ID> --data '{"repo":"owner/name","pat":"ghp_..."}'

# Compile release notes from what's been triaged (currently flaky — see docs/09):
lemma workflow run compile-release-notes --pod <POD_ID> -d '{ "version": "v0.3.0" }'
```

Or just use the live board: https://cortex-board.apps.lemma.work — **New report**,
**Connect repo**, **Approve & assign**, and **Ack** are all there.

## What's verified vs. still unverified — read this before demoing

`suggest_owner` has been run against a real public GitHub repo and correctly
found a likely owner with no token. The triage loop has produced a correct
P1/P2/P3 spread across 5 real reports. The incident pipeline auto-creates a row
on a real run.

**Not yet verified for real:** `assign_owner` and `open_fix_pr` have only run
with no repo/PAT configured (where they correctly no-op) — never against a
writable repo. The `escalate-incidents` schedule has never been observed firing.
No Slack webhook has ever been configured, so alerts have never actually sent.
Nobody has clicked through the app in a real browser yet. Full breakdown:
[docs/09 · Lessons & roadmap](../docs/09-lessons-and-roadmap.md).

## Roadmap (next milestones)

See [docs/09](../docs/09-lessons-and-roadmap.md) for the full, prioritized list —
verifying the above comes before any new feature.

## Judging fit

- **Problem clarity (35%)**: bug triage *and* "who do I assign this to" *and*
  "did anyone ack the P1" are all universal, specific eng-team pains.
- **Product judgment (25%)**: read/write separated by trust level; auto-PR
  proposes, never silently edits code; escalation pages again rather than
  assuming the first alert worked.
- **Execution (25%)**: the core triage loop runs end-to-end via one workflow,
  verified against a real GitHub repo, deployed on a live, working app.
- **SDK use (15%)**: 7 tables, 3 agents, 9 functions, 3 workflows, 1 schedule, 1
  app — Lemma used as the actual infrastructure layer, not a thin wrapper.
