# Bug Triage & Release Operator — Gappy AI Hackathon

An AI **agentic app** built on the **Lemma SDK**: it turns a messy bug report
into a triaged, severity-scored, fix-suggested issue, and compiles release notes
from what's been triaged.

> The actual product is the importable Lemma pod bundle in
> **[`cortex-triage/`](cortex-triage/)**. Start with its
> [README](cortex-triage/README.md).

## Problem
Engineering teams burn hours triaging bugs by hand — reading each report,
guessing severity inconsistently, hunting duplicates, and writing release notes.

## Solution (the core loop)
```
report ──> triage-agent ──> fix-suggester ──> persist_triage ──> tables
            (classify +       (draft fix:        (deterministic     issues/
             score P1/P2/P3)   code, risk,        write)            bugs/fixes
                               effort)
                                                  compile-release-notes
                                                  ──> release-notes-writer ──> release_notes
```
Agents do judgment; a Python function does deterministic persistence; workflows
orchestrate. That's Lemma's intended "agents for judgment, functions for rules."

## What's built (verified against Lemma 0.5.0)
- **4 tables**: `issues`, `bugs` (FK→issues), `fixes` (FK→bugs), `release_notes`
- **3 agents**: `triage-agent`, `fix-suggester`, `release-notes-writer` (with
  structured `output_schema` and least-privilege permission grants)
- **1 function**: `persist_triage` (Python, `Pod.from_env()`)
- **2 workflows**: `triage-issue`, `compile-release-notes`

All 11 bundle JSON files validate; structure matches the CLI's `pod import`
contract; the CLI runs to the auth boundary (see Windows note below).

## Toolchain (real, installed)
| Piece | Command |
|---|---|
| CLI | `uv tool install lemma-terminal` → `lemma` |
| App/UI SDK | `npm install lemma-sdk` (TypeScript/React hooks) |
| Backend SDK | `lemma-python` (used inside functions) |
| Local platform | `install.sh` Docker stack (app :3711, api :8711) |

## ⚠️ Windows note
The Lemma CLI imports `termios` (Unix-only) and **crashes on native Windows**.
Use **WSL/Ubuntu** (present on this machine) for real work, or the
[`scripts/winshim/`](scripts/winshim/) shim for offline `--dry-run` validation.

## Deploy (summary — full steps in the bundle README)
```bash
lemma auth login
lemma pod create cortex-triage --org <ORG_UUID>
lemma pods import ./cortex-triage --pod <POD_ID> --dry-run
lemma pods import ./cortex-triage --pod <POD_ID>
lemma workflow run triage-issue --pod <POD_ID> -d '{"title":"Checkout 500s for all users","source":"manual"}' --wait
```
Full, annotated steps: [docs/08-deploy-run-debug.md](docs/08-deploy-run-debug.md).

## Docs in this repo
- **[docs/](docs/)** — a guided, teaching-style tour of the whole implementation (start at [docs/README.md](docs/README.md))
- [cortex-triage/README.md](cortex-triage/README.md) — deploy + run + demo
- [cortex-triage/AGENTS.md](cortex-triage/AGENTS.md) — how the bundle is structured
- [PROJECT_SPEC.md](PROJECT_SPEC.md) — product vision & judging fit (conceptual)
- [scripts/winshim/](scripts/winshim/) — Windows CLI workaround

---
Build window: June 24–30, 2026 · Submission: June 30 · Status: 🟢 **deployed to Lemma cloud (pod `cortex-triage`); triage loop verified end-to-end** (release-notes workflow needs hardening)
