# Implementation Guide (verified against Lemma 0.5.0)

> This supersedes any earlier draft. The earlier version guessed the API
> (`npm install -g lemma`, YAML agents) **before** the SDK was inspected. The
> commands and formats below are verified against the installed
> `lemma-terminal` 0.5.0 CLI and the real pod-bundle contract.

## How Lemma actually works (the parts we use)
- A **pod** is a workspace. You define its resources as a **bundle** = a
  directory of JSON (+ `instruction.md` / `code.py`) and `lemma pods import` it.
- Resource schemas are authoritative via `lemma schema <pod|table|function|agent|workflow|schedule|surface>`.
- Bundle contract (from the CLI source):
  ```
  pod.json
  tables/<name>/<name>.json            # folder name MUST equal "name"
  functions/<name>/<name>.json + code.py
  agents/<name>/<name>.json    + instruction.md
  workflows/<name>/<name>.json
  ```
  `{"$file":"x"}` inlines a sibling file. System columns
  (`id/created_at/updated_at/user_id`) are auto-added. **Zero access by default** —
  list every table a function/agent touches under `permissions.grants`.
- Naming: tables & functions = `snake_case`; agents, workflows, surfaces = `hyphen-case`.

## Toolchain setup
```bash
# CLI (Python tool via uv)
python -m pip install uv            # if uv missing
uv tool install lemma-terminal      # provides the `lemma` command
# add to PATH: ~/.local/bin  (Linux/WSL) or %USERPROFILE%\.local\bin (Windows)
lemma --version                     # lemma 0.5.0, api schema 3.1.0
```

### Windows
The CLI imports `termios` and crashes on native Windows. Use **WSL** (Ubuntu is
installed) for real work. For offline validation only, use the shim:
```bash
PYTHONPATH=scripts/winshim lemma pods import ./cortex-triage --dry-run
```

## Build → validate → deploy
```bash
lemma auth login                                    # cloud or local backend
lemma pods import ./cortex-triage --dry-run   # validate (no writes)
lemma pods import ./cortex-triage             # upsert by resource name
```

## Run
```bash
lemma workflow run triage-issue --pod <POD_ID> -d '{ "title": "...", "body": "...", "source": "manual" }' --wait
lemma records list bugs --pod <POD_ID>
lemma workflow run compile-release-notes --pod <POD_ID> -d '{ "version": "v0.3.0" }'
```
(The verb is `workflow run` — confirm flags with `lemma workflow run --help`.)

## Extending (next milestones)
1. **Surface + connector** (`lemma connectors`, then `surfaces/slack/slack.json`)
   so Slack/GitHub reports auto-create `issues` rows.
2. **Dashboard app** under `apps/<name>/source/` (Vite + React) using
   `lemma-sdk` hooks: `useRecords("bugs")`, `useWorkflowRun("triage-issue")`.
3. **Duplicate detection**: add a `VECTOR` column to `bugs`, embed on triage,
   query nearest neighbours in `persist_triage`.
4. **Approval node** in `triage-issue` before any auto-action on P1s.

## Reference
- `lemma schema <resource>` — canonical fields for each resource type
- `lemma --help` — full command surface
- `cortex-triage/AGENTS.md` — bundle-specific build notes
