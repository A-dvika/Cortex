# Cortex Triage Demo Video Voiceover

Use this with `cortex-demo-intro.html`. Record the animation first, then cut to the real Cortex Board when the animation says "Here is the demo."

Before recording: the board is currently seeded with exactly **5 real, live-triaged issues** pulled from `langchain-ai/langchain` (mirrored into a connected fork, `A-dvika/langchain`) — not synthetic demo data, and freshly verified clean (no leftover test rows from other work). If you want to show automatic intake live, resume the polling schedule first (`lemma schedules resume poll-github-issues`); otherwise the pre-populated board is the safe, always-works path.

## 0:00-0:10 - Opening

Every engineering team has the same hidden tax: bug triage. A messy report comes in, and someone has to decide how bad it is, who owns it, what might fix it, and whether it's even worth doing right now.

## 0:10-0:24 - Problem Statement

The bugs that page someone at 2am always get handled — they have to. What doesn't get handled is everything underneath: dependency alerts, flaky tests, issues nobody's urgent enough to interrupt anyone over. The cost isn't the fix — it's the twenty minutes of investigation before anyone can even decide what to do. That investigation tax is what piles up.

## 0:24-0:40 - Product

We built Cortex Triage, an AI triage operator for engineering teams, on Lemma. It connects to a real GitHub repo, watches for new issues, and for each one: classifies the bug, scores severity as P1, P2, or P3, suggests a fix, figures out who actually has context on that code, opens a Jira ticket, posts to Slack, and opens an incident if it's serious enough — automatically, the moment the issue lands.

## 0:40-0:55 - How We Built It With Lemma

Lemma is the infrastructure layer underneath. Agents do judgment — read a report, return a structured verdict. Functions do everything deterministic — writing rows, calling GitHub, creating Jira tickets, posting Slack messages. That split matters: the model can be wrong about a severity score and it costs nothing, because it never had write access to anything. A human always approves the one thing that actually matters — who gets assigned.

Concretely: 3 agents that only reason, 17 functions that own every side effect, 4 workflows that chain them together — one for manual intake, one that polls GitHub automatically, one for release notes, one that sweeps for unacknowledged incidents on a schedule — and 8 tables that hold the whole system's memory.

## 0:55-1:08 - Working Prototype Proof

This isn't a demo against fake data. The board right now holds five real open issues from LangChain's GitHub repo — a cache `KeyError`, a Chroma similarity-search bug, a streaming bug, a dict-merge `TypeError`, a callback `KeyError` — each one triaged by the live pipeline: real severity, real reasoning, a real suggested owner traced from commit history and CODEOWNERS, not a placeholder.

## 1:08-1:15 - Demo Handoff

Now let me show the live Cortex Board inside Lemma, connected to that real repo.

## Demo Actions To Record After The Intro

1. Open the GitHub repo (`A-dvika/langchain`, a fork of `langchain-ai/langchain`) and show 2–3 real issues — long descriptions, technical failure modes, unclear ownership.
2. Say: "This is where the problem starts. GitHub has the raw report, but it doesn't tell you how severe it is, who has context, or whether it's worth an incident."
3. Switch to the live `cortex-board`, connected to this exact repo.
4. Point out the board only shows issues from the connected repo — no leftover demo data, no other projects mixed in.
5. Open the **Cache length check** card (`eyurtsev` as suggested owner) — show severity, reasoning, confidence, fix suggestion, and the suggested-owner panel with the breaking commit link.
6. Scroll to the **investigation context** line — production/non-production, affected service count, fix complexity — and the decision panel underneath: Assign / Defer 2wk / Backlog / Close.
7. Click **Defer 2wk** live, type a one-line reason, and show it collapse into an audited decision line: who decided, what, and when.
8. (Optional, if the agent runtime is responsive) Trigger `poll-github-issues` manually or just open a new issue on the fork live, and show it appear on the board within the next cycle — fully triaged, owner suggested, Jira ticket attempted, Slack notified.
9. Mention that GitHub assignment and the backlog decision are still the only two things that need a human click — everything before that is automatic.
10. **(~15 seconds, keep it tight)** Switch to Slack. Open the Cortex-Triage chat there and type one line — e.g. "what's our open backlog" — and let the response come back. Switch back to the board immediately after; don't linger, this is a proof point, not a second product walkthrough.

What to say over step 10:

"One more thing worth showing fast: this exact Lemma pod — same tables, same agents, same functions — is also the backend for a Slack agent I built separately. It talks to Lemma through a small MCP server I wrote that exposes this pod's workflows as callable tools. Same backend, two completely different front doors, zero changes to Lemma to make that work. That's the actual test of whether a backend is real infrastructure or just logic glued behind one screen — and this one passed it."

## What To Say During The Demo

When showing GitHub issues:

"We connected this to a real GitHub repo — a fork of LangChain, one of the largest AI codebases out there, where issues are technical, noisy, and genuinely hard to route. A report can mention agents, tools, callbacks, model providers, streaming, or dependency versions. GitHub stores all of that. It doesn't turn it into a decision."

When switching to Cortex Board:

"This is Cortex Triage, our Lemma-powered operator board, live-connected to that repo. Every card here is a real LangChain issue, triaged automatically the moment it showed up."

When pointing at the Cache length check card:

"This bug crashes `generate()` whenever a cache implements `__len__` and reports zero entries. Cortex classified it as a crash, P2, with a confidence score — and it suggested `eyurtsev` as the owner, not because of a static CODEOWNERS rule, but because Cortex traced commit history on `caches.py` and found the person who actually wrote that code."

When showing the investigation context and decision panel:

"This is the part that actually saves time. Most bugs aren't urgent enough to page anyone, but somebody still has to read them eventually and decide what to do. Cortex answers the three questions that take the longest — is this in production, how many services does it touch, how complex is the fix — and puts them right next to an Assign, Defer, Backlog, or Close button. The model never makes that call. A human clicks it, and the decision — who, what, why, when — is recorded permanently."

When explaining the automatic intake:

"New issues don't need anyone to submit a form. A schedule checks the connected repo every couple of minutes, and the moment something new shows up, the same pipeline runs automatically — triage, fix suggestion, owner lookup, a Jira ticket, a Slack post, and an incident if it's serious. The only thing that ever requires a person is approving an assignment or deciding what happens to a backlog bug."

When closing:

"So the product isn't another GitHub issue viewer. It's an AI triage operator built on Lemma, connected to a real repo, that turns a flood of raw issues into a prioritized, explainable, auditable engineering queue — automatically."

## Pipeline Steps To Explain

Use this while showing either the board card, the workflow view, or a spoken walkthrough:

1. **Poll** — every 2 minutes, Cortex checks the connected repo for one new issue it hasn't seen. This is its own workflow (`poll-github-issues`), not a hidden step bolted onto triage.
2. **Triage Agent** — reads the title and body, classifies the bug type, scores impact and urgency, assigns P1/P2/P3, and explains the reasoning — plus three context fields: is this production code, how many services does it touch, how complex is the fix.
3. **Fix Suggestion** — proposes a likely fix direction, risk level, effort estimate, and confidence.
4. **Persist** — a deterministic Lemma function writes the issue, bug, and fix rows. This is the only thing that ever writes — the model never touches the table directly.
5. **Suggest Owner** — traces commit history and CODEOWNERS on the implicated file to find who actually has context, not just whoever committed most recently.
6. **Jira Ticket** — opens a tracking ticket with the severity, reasoning, and suggested owner as a recommendation, not an assignment.
7. **Slack Notification** — posts a one-line summary to the team's channel.
8. **Open Incident** — for P1/P2, creates an incident and alerts; P3s stay quiet on the board.
9. **Safe Proposal PR** — if the fix is low-risk and confidence is high, prepares a proposal PR. Never patches production code blindly.
10. **Human Decision** — the board is where a human actually decides: assign, defer, backlog, or close — the one step in the whole pipeline that's never automated.

Short version to say:

"Ten steps: poll, triage, fix suggestion, persistence, owner lookup, a Jira ticket, a Slack post, an incident if it's serious, a safe proposal PR, and a human decision at the end. Everything before that last step runs by itself."

When showing action buttons:

"The key product judgment is that Cortex automates the investigation, never the decision. Assigning someone, deferring a bug, or closing it out — those are always a human click. The model can be wrong about a severity score and the cost is zero, because it was never the thing deciding what happens next."

## Agents Breakdown

We use **3 agents**:

1. **Triage Agent**
   Reads the bug title and body, classifies the bug type, scores impact and urgency, assigns severity as P1/P2/P3, detects duplicate signals, explains the reasoning, and assesses production impact, blast radius, and fix complexity.

2. **Fix Suggester**
   Proposes a practical fix direction, risk level, effort estimate, and confidence score for a triaged bug.

3. **Release Notes Writer**
   Turns triaged/fixed bugs into human-readable release notes so the team can communicate what changed and why it mattered.

Important line:

"The agents do judgment. Lemma functions do every deterministic action — writing rows, calling GitHub, opening Jira tickets, posting Slack messages, opening incidents, and creating reviewable proposal PRs. Nothing the model says ever reaches a table or another system without going through code a human can read end to end."

## If A Judge Asks More About The Slack Agent

(The MCP beat is now scripted into the main demo at 2:50–3:05 — step 10. Only use this if a judge wants more detail afterward.)

The Slack agent is a Bolt app running over Socket Mode. It doesn't talk to Lemma directly — it's an MCP client that calls a small MCP server I wrote (Node, the official `@modelcontextprotocol/sdk`), which wraps this pod's workflows and tables as callable tools: triage a bug, list the backlog, look up a bug, record a decision, compile release notes. The MCP server is the only thing that knows how to call Lemma's REST API; Slack never touches it directly. That's the same separation of concerns as the rest of this system — Slack is a front door, Lemma is where the judgment and the state actually live.
