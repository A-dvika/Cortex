# 08 · Deploy, run & debug

This is the hands-on chapter: the exact toolchain, the bundle format, and the real
commands used to deploy Cortex-Triage and run it — including the things that broke.

## The pod bundle format (what "the code" actually is)

A pod is defined as a **bundle** — a directory of plain files you `import`. There's
no hidden state; the files *are* the source of truth.

```
cortex-triage/
  pod.json                                  {format_version, name, description}
  tables/<name>/<name>.json                 folder name MUST equal the resource name
  functions/<name>/<name>.json + code.py    JSON carries permissions; code in code.py
  agents/<name>/<name>.json   + instruction.md
  workflows/<name>/<name>.json
  schedules/<name>/<name>.json              one TIME/DATASTORE/WEBHOOK trigger + one target
  apps/<name>/<name>.json + html.html       no-build app (or + source/ for a Vite app)
```

Rules that bite:
- **Folder name == resource `name`.** `tables/bugs/bugs.json`, not `tables/bug/bugs.json`.
- **`{"$file":"x"}`** inlines a sibling file (instruction.md, code.py). JSONC
  comments are allowed in bundle JSON.
- **Naming conventions:** tables & functions are `snake_case` (valid SQL/Python);
  agents, workflows, surfaces are `hyphen-case`.
- **Never declare** `id`/`created_at`/`updated_at`/`user_id` columns — auto-added.
- **`lemma schema <resource>`** prints the canonical field reference for any
  resource type. When in doubt, run it — don't guess.

## The toolchain

```bash
# CLI (a Python tool, installed via uv)
python -m pip install uv          # if uv is missing
uv tool install lemma-terminal    # provides the `lemma` command
lemma --version                   # lemma 0.5.0, api schema 3.1.0
```

- **`lemma-terminal`** — the CLI (creates/imports/runs everything).
- **`lemma-sdk`** (npm) — the TypeScript/React hooks for building an **app** UI.
- **`lemma-python`** — the SDK used *inside* functions (`from lemma_sdk import Pod`).

> **⚠️ Windows gotcha (important).** The CLI does `import termios` at startup —
> a Unix-only module — so on native Windows every real command crashes with
> `ModuleNotFoundError: No module named 'termios'`. Two fixes:
> 1. **WSL** (recommended) — run the CLI inside Ubuntu where `termios` exists.
> 2. **Shim** (dev/validation) — put no-op `termios.py`/`tty.py` on `PYTHONPATH`.
>    We ship one in [`../scripts/winshim/`](../scripts/winshim/); prefix commands
>    with `PYTHONPATH=scripts/winshim`. With it, the CLI runs to completion on
>    Windows for non-interactive commands.

## Deploy: the exact sequence we ran (cloud)

```bash
# 1) authenticate (browser flow; --no-init skips the interactive org/pod picker)
PYTHONPATH=scripts/winshim lemma auth login --no-init
lemma auth status                                   # confirm: adici2403@gmail.com

# 2) a fresh account has no org — create one (NOTE: --org elsewhere wants the UUID)
lemma org create "advika-hackathon"                 # -> id 019ef9ba-…

# 3) create the pod (import loads INTO an existing pod; it doesn't create one)
lemma pod create "cortex-triage" --org <ORG_UUID> --description "…"   # -> pod id 019ef9bc-…

# 4) validate, then import the bundle into the pod
lemma pods import ./cortex-triage --pod <POD_ID> --dry-run   # prints a plan, says OK
lemma pods import ./cortex-triage --pod <POD_ID>             # creates everything
```

The dry-run plan we got listed all 10 resources as `created` and ended with `OK`;
the real import created 4 tables, 1 function, 3 agents, 2 workflows, then applied
permissions. (Renaming the deployed pod later is just a re-import with
`--set-pod-meta`.)

The pod has since grown well past that first import — re-importing is always
**upsert by name**, so the same two commands (`--dry-run` then for real) are all
that's ever needed, no matter how much the bundle has grown:

```bash
lemma pods import ./cortex-triage --pod <POD_ID> --dry-run --timeout 200
lemma pods import ./cortex-triage --pod <POD_ID> --timeout 300
```

A later import plan looked like this — **7 tables, 9 functions, 3 agents,
3 workflows, 1 schedule, 1 app**, all in one upsert:

```
tables      created   alert_config            functions  created  open_fix_pr
tables      updated   bugs                    functions  created  open_incident
tables      updated   fixes                   functions  updated  persist_triage
tables      updated   github_config           functions  created  resolve_incident
tables      created   incidents               functions  updated  suggest_owner
tables      updated   issues                  agents     updated  fix-suggester
tables      updated   release_notes           agents     updated  release-notes-writer
functions   created   ack_incident            agents     updated  triage-agent
functions   updated   assign_owner            workflows  updated  compile-release-notes
functions   created   escalate_incidents      workflows  created  escalate-incidents
functions   updated   github_ping             workflows  updated  triage-issue
                                               schedules  created  escalate-incidents
                                               apps       updated  cortex-board
```

> **Gotchas worth memorizing:**
> - `lemma pods import` imports **into an existing pod** (`--pod`); create the pod first.
> - `--org` on `pod create` wants the org **UUID**, not the slug (slug → `badly
>   formed hexadecimal UUID string`).
> - On launch day the cloud was flaky (503s, read-timeouts). Use `--timeout 180`
>   and just retry; imports upsert by name, so retries are safe/idempotent.

## Run a workflow

```bash
# fire the triage pipeline with a report (entry FORM data via -d/--data)
lemma workflow run triage-issue --pod <POD_ID> \
  -d '{"title":"Checkout returns 500 for all users","body":"…","source":"github"}' --wait
```

- `--wait` (default) polls until the run finishes; `--no-wait` returns immediately
  with a run id (good for firing several, then checking later).
- The agents call a model, so a run takes a little while — budget more than a quick
  CLI call's worth of patience, especially under load.

## Inspect results & debug

```bash
lemma workflow runs list triage-issue --pod <POD_ID>   # statuses: COMPLETED / FAILED / RUNNING
lemma workflow runs get <RUN_ID> --pod <POD_ID> --full # full run incl. per-node errors
lemma records list bugs --pod <POD_ID>                 # the rows that landed
```

Three real debugging stories from this build:
1. **`path 'intake.url' resolved to nothing`** — a workflow run FAILED at the
   `persist` node because a partial report omitted a form field that a mapping
   required. Fix: defaults on FORM fields (see [06](06-workflows.md)).
2. **`Agent conversation FAILED`** on `compile-release-notes` — the tool-using
   release-notes agent flaked on the launch-day runtime (it *did* create a
   `release_notes` row, but left `notes_markdown` empty before erroring). Diagnosis
   came straight from `workflow runs get --full`. The planned fix is in [09](09-lessons-and-roadmap.md).
3. **Verifying outbound HTTP before trusting a whole feature on it.** Before
   writing `suggest_owner`/`assign_owner`, we didn't assume function sandboxes
   could reach the internet — we wrote a one-call probe (`github_ping`, just
   `requests.get("https://api.github.com/rate_limit")`) and ran it first.
   It returned `200`, confirming outbound HTTP works, *before* any GitHub logic
   was built. That single probe is what made the rest of [10](10-app-and-github-automation.md)
   safe to build on.

## Verified against a real GitHub repo

`suggest_owner` was run via `lemma functions run` against a real public repo
(`octocat/Hello-World`), not a mock:

```bash
lemma records create github_config --pod <POD_ID> --data '{"repo":"octocat/Hello-World"}'
lemma functions run suggest_owner --pod <POD_ID> --data '{"bug_id":"<id>","suspect_path":"README"}'
# -> {"ok": true, "source": "commits", "assignee_login": "Spaceghost",
#     "reason": "most recent committer to README", "breaking_commit": "762941318e", ...}
```

It correctly found the most recent committer to that file with no token at all
(unauthenticated GitHub reads: 60 req/hr). `assign_owner` and `open_fix_pr` (the
*write* paths) have only been exercised with no repo/PAT configured, where they
correctly no-op (`"No repo/PAT configured"`) rather than erroring — they have
**not yet been run against a repo with write access**. That's the next thing to
verify before relying on them in a live demo.

> **Tip:** the CLI's `--json` output sometimes carries a trailing non-JSON note.
> When scripting, parse with a tolerant reader (`json.JSONDecoder().raw_decode`)
> that reads the first JSON value and ignores trailing text.

Next: what we learned and what to build next → [09 · Lessons & roadmap](09-lessons-and-roadmap.md)
