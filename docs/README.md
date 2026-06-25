# Cortex-Triage — Implementation Docs (a guided tour)

Welcome. These docs explain **how Cortex-Triage is built on the Lemma SDK**, written
to *teach* — so even if you've never seen Lemma, you can follow along and end up
understanding both the product and the framework underneath it.

**Live:** the operator board is deployed at
**https://cortex-board.apps.lemma.work**, on pod `cortex-triage` (Lemma cloud).

## What Cortex-Triage is

An **agentic incident-response operator** that turns a messy bug report into:
1. a **triaged, severity-scored** issue (P1 / P2 / P3) with reasoning,
2. a **suggested fix** (steps + code sketch + risk + effort),
3. a **likely owner** found from the real GitHub repo's commits + CODEOWNERS,
4. an **incident**, escalated automatically if it's P1 and stays unacked,
5. when it's a safe, well-understood fix, a **proposal pull request** ready for
   human review, and
6. on demand, **release notes** compiled from everything triaged.

It's built for a real, universal pain: engineering teams burning hours manually
triaging bugs, figuring out who broke them, and writing changelogs.

## The one-paragraph mental model

Most software *records* what happened (a form saves a row). **Lemma** is for
software that *does the work*: you give AI **agents** a job and scoped access to
**tables** (structured data) and **files** (knowledge), you use **functions** for
the deterministic steps, and you wire them into **workflows** that run in order.
Everything lives in a **pod** (one workspace for one process). Cortex-Triage is
exactly that pattern applied to bug triage and incident response.

## How to read these docs

Read in order if you're new; jump around if you're not.

| # | Doc | What you'll learn |
|---|-----|-------------------|
| 01 | [Lemma mental model](01-lemma-mental-model.md) | The framework's building blocks (pod, table, agent, function, workflow…) and when to reach for each |
| 02 | [Architecture overview](02-architecture-overview.md) | Cortex-Triage's full design — triage, owner-finding, incidents, auto-PR — and the "agents vs functions" philosophy |
| 03 | [Data model (tables)](03-data-model.md) | All 7 tables: issues/bugs/fixes/release_notes/incidents/github_config/alert_config |
| 04 | [Agents](04-agents.md) | Instructions as job descriptions, structured output, grounding the model with a rubric |
| 05 | [Functions](05-functions.md) | Deterministic Python steps, the `Pod` API, and why persistence is a function not an agent |
| 06 | [Workflows](06-workflows.md) | Workflow graphs: nodes, edges, input-mapping, and the schedule-driven `escalate-incidents` |
| 07 | [Permissions & security](07-permissions-and-security.md) | Zero-access-by-default, grants, row-level security |
| 08 | [Deploy, run & debug](08-deploy-run-debug.md) | The real CLI flow, the pod-bundle format, running it, and how we debugged failures |
| 09 | [Lessons & roadmap](09-lessons-and-roadmap.md) | What's solid, what's shaky, what's unverified, and what to build next |
| 10 | [The app & GitHub automation](10-app-and-github-automation.md) | The no-build app's SDK calls, and how `suggest_owner`/`assign_owner`/`open_fix_pr` work against real GitHub |

## The shape of the whole system (one picture)

```
                  ┌────────────────────────────── pod: cortex-triage ───────────────────────────────┐
                  │                                                                                  │
a bug report ────▶│ workflow: triage-issue                                                           │
(title, body,…)   │  FORM─▶AGENT(triage)─▶AGENT(fix)─▶FN(persist)─▶FN(owner)─▶FN(incident)─▶FN(pr)─▶END │
                  │           classify       draft fix    write       find        escalate    proposal│
                  │           +score                      rows        owner       if P1       PR if   │
                  │                                                  (GitHub      (Slack)      low-risk│
                  │                                                   commits)                +confident│
                  │           tables: issues──<bugs──<fixes              incidents  github_config      │
                  │                                                                  alert_config       │
human ───────────▶│ board app (cortex-board): Approve&assign (FN assign_owner) · Ack (FN ack_incident)  │
                  │                                                                                    │
stale P1s ───────▶│ schedule (5 min) ─▶ workflow: escalate-incidents ─▶ FN escalate_incidents            │
                  │                                                                                    │
"release v0.3.0"─▶│ workflow: compile-release-notes: FORM─▶AGENT(writer, reads bugs+fixes)─▶END         │
                  └────────────────────────────────────────────────────────────────────────────────────┘
```

> Conventions in these docs: code blocks are real excerpts from the bundle in
> [`../cortex-triage/`](../cortex-triage/). Callouts marked **Why** explain a
> design choice; **Gotcha** flags something that bit us in practice.
