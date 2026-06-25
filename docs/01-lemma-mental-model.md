# 01 · The Lemma mental model

Before we touch Cortex-Triage, let's build intuition for the framework. If you
know these primitives, everything else in these docs is just "which primitive,
wired to which."

## The core idea

> **Lemma is infrastructure for software that does work, not just records it.**

Normally, to build an "AI does a real workflow" product you'd glue together five
things: an LLM API, a database, a vector/search store, a workflow/queue engine,
and a bunch of integrations. Lemma gives you those as **one set of composable
primitives inside a workspace**, and it's open-source and locally runnable.

## The primitives (with plain-English analogies)

Think of a Lemma **pod** as a small company department, and the primitives as the
people, filing cabinets, and procedures inside it.

### Pod — the workspace
A **pod** is one self-contained workspace for *one team or process*: its agents,
data, files, workflows, and permissions all live together and stay isolated from
other pods. **Rule of thumb:** name a pod after the *process* ("cortex-triage"),
not the team.

### Table — structured data
A **table** is typed business data the pod reads and writes — rows and typed
columns, like a database table with per-row security. Reach for it when data needs
filtering/sorting/counting, moves through states (open → triaged → done), or is
shared by many agents/people. *In Cortex-Triage:* `issues`, `bugs`, `fixes`,
`release_notes`.

### File — unstructured knowledge
A **file** is a document the pod can search, read, and **cite** — contracts,
policies, runbooks, transcripts. Agents search files to *ground* their answers
instead of guessing. (Cortex-Triage keeps its knowledge — the severity rubric —
inside the agent instruction for simplicity, but files are the alternative.)

### Agent — an AI worker (judgment)
An **agent** is an AI worker with a **role**, **instructions** (its job
description), a **runtime** (the model), and **scoped access** to exactly the
tables/files/apps it needs. Use agents for *judgment*: classify, score, draft,
summarize, decide. *In Cortex-Triage:* `triage-agent`, `fix-suggester`,
`release-notes-writer`.

### Function — deterministic code (rules)
A **function** is plain code the pod runs the same way every time: validation,
math, formatting, calling an API, writing rows. Use functions for *rules*: the
same input must always produce the same output. *In Cortex-Triage:* `persist_triage`.

> **The single most important design principle in Lemma:**
> **agents for judgment, functions for rules.** If you catch an agent doing
> arithmetic or applying a fixed rulebook, that should be a function.

### Workflow — orchestration
A **workflow** is a repeatable process: an ordered graph of steps — agents,
functions, decisions, human approvals — with branching and inputs. It's
*inspectable*: every run is traceable step by step. *In Cortex-Triage:*
`triage-issue` and `compile-release-notes`.

### Surface — where work enters
A **surface** is a channel that brings work into the pod automatically: Slack,
Gmail, Teams, WhatsApp, Telegram, Outlook. Instead of someone copy-pasting a bug
into a form, a surface lets reports arrive from the tools people already use.
(Cortex-Triage's roadmap; not in the core import yet.)

### Connector — authenticated reach-out
A **connector** is an authenticated link to a third-party app (GitHub, Slack,
Salesforce, Notion…) so agents/functions can *act* in those systems — e.g. post a
comment back on a GitHub issue.

### App — a custom interface
An **app** is a custom UI deployed at its own URL where your team and the pod's
agents work together on the pod's data. Built with the `lemma-sdk` React hooks.
(Cortex-Triage's roadmap.)

### Schedule — time/event triggers
A **schedule** starts an agent or workflow on a cron timer, on a row event, or on
a webhook — e.g. "compile release notes every Friday at 9am."

### Access scope & approval — the guardrails
**Access scope** is the set of tables/folders/tools an agent or function may touch
— *nothing else*, granted explicitly (zero-access-by-default). **Approval** is a
human gate inside a workflow before anything with real consequences happens.

## How they compose (the sentence to remember)

> A **workflow** runs **agents** (judgment) and **functions** (rules) over
> **tables** (data) and **files** (knowledge), inside a **pod** (workspace),
> entered via **surfaces**, reaching out via **connectors**, watched through an
> **app**, kicked off by **schedules**, all fenced by **access scope**.

Next: how Cortex-Triage arranges these into a working product →
[02 · Architecture overview](02-architecture-overview.md)
