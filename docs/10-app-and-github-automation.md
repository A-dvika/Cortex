# 10 · The app, and the GitHub automation layer

This doc covers the two newest, most complex parts of Cortex-Triage: the
operator **app** people actually use, and the **GitHub automation** functions
that turn "who broke this" from a manual investigation into an automatic
suggestion. Both are real, live, and only partially battle-tested — read
[09](09-lessons-and-roadmap.md) alongside this for what's still unverified.

## Part 1 — the app: a no-build HTML app, not a React/Vite app

Lemma supports two ways to build an app: a **Vite + React** project (`apps/<name>/source/`,
needs `npm install`/`npm run build`), or a single **no-build HTML file**
(`apps/<name>/html.html`). We chose HTML for `cortex-board`.

**Why no-build, specifically:** a Vite app needs its `npm install`/`build` step
to succeed at import time — one more thing that can fail on a flaky connection
or a launch-week registry hiccup. A single HTML file has nothing to build; it's
uploaded as-is. For a single-page dashboard (no routing, no component reuse
across pages), the docs themselves recommend defaulting to HTML — reach for Vite
only when the app genuinely needs multi-page state.

### How the app gets its identity and config

```html
<script>
  var cfg = window.__LEMMA_CONFIG__ || {};                 // injected by the host
  var base = (cfg.apiUrl || window.location.origin).replace(/\/$/, "");
  var s = document.createElement("script");
  s.src = base + "/public/sdk/lemma-client.js";             // SDK lives on the API host
  s.onload = boot;
  document.head.appendChild(s);
</script>
```

The pod host injects `window.__LEMMA_CONFIG__` (podId, apiUrl, authUrl) at serve
time — the same artifact runs unchanged locally, in staging, or in the cloud. The
SDK itself is fetched from the **API host**, not the app's own subdomain (a
relative `src` 404s — this is a documented gotcha we built around from the
start, not one we hit and fixed).

```js
async function boot() {
  client = new window.LemmaClient.LemmaClient();   // no args — config comes from window
  var st = await client.initialize();               // { status, user }
  if (st.status !== "authenticated") { client.auth.redirectToAuth(); return; }
  // ...now client.records / client.workflows / client.functions are usable
}
```

### The client calls the board actually makes

| Action | Call |
|---|---|
| Load the board | `client.records.list("bugs"\|"fixes"\|"issues"\|"incidents"\|"release_notes", {limit})` |
| Submit a new report | `client.workflows.runs.create("triage-issue")` → `client.workflows.runs.submitForm(runId, {node_id, inputs})` → poll `client.workflows.runs.get(runId)` |
| Approve & assign | `client.functions.run("assign_owner", {input: {bug_id}})` |
| Ack an incident | `client.functions.run("ack_incident", {input: {incident_id, acked_by}})` |
| Connect a repo | `client.records.create("github_config", {repo, pat})` |

> **Why "New report" goes through `workflows.runs` but "Approve & assign" goes
> through `functions.run`.** Submitting a report needs the whole `triage-issue`
> *pipeline* (multiple agents and functions in sequence) — that's a workflow run.
> Approving an assignment is one deterministic action — that's a direct function
> call, no orchestration needed. The app picks the right primitive for each job
> instead of routing everything through one mechanism.

### The live stepper

The "New report" modal renders a step list (`Submitting → Classifying → Drafting
a fix → Saving → Done`) and updates it by polling `run.current_node_id`:

```js
while (!terminal[run.status]) {
  await sleep(2000);
  run = await client.workflows.runs.get(run.id);
  renderSteps(run.current_node_id);  // maps node id -> step label
}
```

This is **polling**, not a subscription — acceptable here because it's a single
short-lived modal a user is actively watching, not a background list that should
react to other people's changes. (For a live-updating *list*, Lemma's own guidance
is to use the table WebSocket instead of polling — see `09-lessons-and-roadmap.md`
roadmap; the board currently reloads everything on a manual Refresh click rather
than subscribing, which is a known simplification, not the recommended pattern.)

## Part 2 — the GitHub automation functions

Five functions turn "who broke this and can we route it" into something
automatic. None of them use a Lemma **connector** — GitHub isn't in Lemma's
connector catalog (verified by listing all 79 connectors: Slack, Notion, Jira,
Linear, Sentry... no GitHub/GitLab/Bitbucket). So this is plain HTTP from inside
a function, against `api.github.com` directly.

### The trust boundary: read vs write

```
suggest_owner   READ-ONLY   no token needed (public repo)   runs automatically, every triage
assign_owner    WRITE       needs a PAT                     runs only on human "Approve & assign"
open_fix_pr     WRITE       needs a PAT                      runs automatically, but only opens a
                                                              PROPOSAL PR, never edits real code
```

**`suggest_owner`** (read path): given a bug, it finds the implicated file
(parsed from the title/body with a regex for common source extensions), then:
1. `GET /repos/{repo}/commits?path={file}` — the most recent commit touching
   that file is treated as the likely "breaking" commit; its author is a
   candidate owner.
2. `GET /repos/{repo}/contents/.github/CODEOWNERS` (and two fallback locations)
   — if a CODEOWNERS rule matches the path, that owner **wins** over the commit
   author (a documented team ownership beats an incidental recent committer).
3. Writes `assignee_login`, `assignee_reason`, `breaking_commit(_url)`,
   `assign_status: "suggested"` onto the `bugs` row.

This needs **no PAT** for a public repo — unauthenticated GitHub reads get
60 requests/hour, which is plenty for occasional triage. A PAT in `github_config`
simply raises that limit; it's not required for this function to work.

**`assign_owner`** (write path, human-gated): takes a `bug_id`, reads the
suggested (or overridden) assignee and the linked issue's `external_id` (the
real GitHub issue number), then:
1. `POST /repos/{repo}/issues/{n}/assignees`
2. `POST /repos/{repo}/issues/{n}/comments` — a structured comment: severity,
   type, who and why, the breaking commit link, and the suggested fix.
3. Sets `assign_status: "assigned"`.

This is the **only** place in the whole pod that writes an assignment to a real
repo, and it only runs when a person clicks **Approve & assign** on the board —
never automatically.

**`open_fix_pr`** (write path, auto-triggered, but conservative): eligibility is
`risk_level == "low"` **and** `confidence >= 0.6`. If not eligible, it records
`fix_pr_status: "ineligible"` and stops — this is the normal outcome for most
bugs; auto-PR is meant to catch the easy, obvious ones only. If eligible:
1. `GET /repos/{repo}` → default branch; `GET .../git/ref/heads/{branch}` → base SHA.
2. `POST .../git/refs` — create branch `cortex-fix/<bug-id-prefix>`.
3. `PUT .../contents/cortex-fixes/<id>.md` — commit a **markdown proposal**
   (bug summary, suggested fix, code sketch, confidence) to the new branch.
   It does **not** touch any existing source file.
4. `POST .../pulls` — open the PR against the default branch, then request
   review from the suggested owner and label it `ai-suggested-fix`.

> **Why a markdown proposal file instead of actually patching the code.** The
> fix suggestion comes from an LLM that has never run a test against this
> codebase. Splicing that snippet into a real file and opening a PR *as if it
> were a tested fix* would be actively dangerous — reviewers might trust the
> green "opened by automation" badge more than they should. A clearly-labeled
> proposal document, on its own branch, with a human reviewer tagged, gets the
> exact same time-saving benefit (a starting point, not a blank page) without
> the false confidence of "the AI already wrote the diff."

### The incident escalation chain

```
open_incident        creates an `incidents` row; P1 = urgent alert, P2 = normal,
                      P3 = silent (no row update needed — just doesn't alert)
ack_incident          human marks it acked -> stops escalation
escalate_incidents     (on its own 5-min schedule) re-pages any P1 still open
                       and unacked past alert_config.escalation_minutes
resolve_incident       closes it out once the underlying bug is actually fixed
```

`open_incident` is deliberately **best-effort**: if no `alert_config` webhook is
set, it still creates the incident row and returns `ok: true` — a missing alert
channel is a configuration gap, not a failure of the pipeline. The same
graceful-degradation pattern as `suggest_owner`/`open_fix_pr`: **a missing
external dependency is never a thrown error, it's a documented no-op.**

## See also

- The design rationale for read/write separation and the proposal-PR choice →
  [02 · Architecture overview](02-architecture-overview.md), decisions 5–7
- The new `bugs`/`incidents`/`github_config`/`alert_config` columns →
  [03 · Data model](03-data-model.md)
- How these functions are wired into `triage-issue` →
  [06 · Workflows](06-workflows.md)
- What's verified vs. still unproven about all of this →
  [09 · Lessons & roadmap](09-lessons-and-roadmap.md)
