# 09 · Lessons & roadmap

The honest chapter: what we learned building Cortex-Triage, what's solid, what's
shaky, what's never actually been exercised, and where it goes next. Updated as
the incident-response layer, GitHub automation, and the app were added.

## What's solid (verified working, with evidence)

- **The triage core loop runs end-to-end.** `triage-issue` took five real reports
  and produced a correct severity spread (P1 crash · P2 data/perf/auth · P3 ui),
  each with reasoning, plus a suggested fix — all persisted to `issues`/`bugs`/`fixes`.
- **Structured output → deterministic persistence** works exactly as designed: the
  agent's `severity`/`bug_type` enums drop straight into the table columns.
- **Permissions are correct**: pure-reasoner agents hold no grants; functions hold
  exactly the table grants they need; `github_config`/`alert_config` are
  `PERSONAL` + RLS so credentials never leak across users.
- **The owner-finding logic works against a real GitHub repo.** `suggest_owner`
  was run via the CLI against `octocat/Hello-World` (a real, live repo, not a
  mock) and correctly found the most recent committer to a file, with no token.
  See [08](08-deploy-run-debug.md) for the exact transcript.
- **Outbound HTTP from a function sandbox was verified before being relied on**
  (`github_ping` → 200 from `api.github.com`), so the whole GitHub feature set is
  built on a confirmed capability, not an assumption.
- **The incident pipeline fires automatically.** Sending a P1 through
  `triage-issue` creates an `incidents` row with no extra step — confirmed live.
- **The app is deployed and serving the right content** — confirmed via direct
  HTTP fetch that the live URL returns our HTML, including after each redesign.

## What's shaky (known, with a fix in mind)

**`compile-release-notes` is only partially working.** The `release-notes-writer`
agent successfully *creates* a `release_notes` row but sometimes leaves
`notes_markdown` empty and the run is marked `FAILED` ("Agent conversation
FAILED") — flaky on the launch-day model runtime, because it's our only
*tool-using* agent: it must read two tables, join them, compose prose, and write
a row, all inside one agent conversation. Every tool call is a failure point.

**Planned fix (mirror the triage design):**
```
FORM(version)
  ─▶ FUNCTION gather_release_data   # query bugs+fixes deterministically -> JSON
  ─▶ AGENT  release-notes-writer    # PURE reasoner: JSON in -> markdown out
  ─▶ FUNCTION persist_release_notes # write the release_notes row exactly
  ─▶ END
```
Not yet implemented — still the single highest-value hardening task.

## What's built but never exercised for real (the honest gap)

These exist, were reviewed, and dry-run/imported cleanly — but have not been
*run* against the real-world system they're meant to act on:

- **`assign_owner` and `open_fix_pr`** (the GitHub *write* paths) have only been
  tested with no repo/PAT configured, where they correctly no-op. Neither has
  ever assigned a real issue or opened a real PR.
- **`escalate_incidents`'s schedule** was created but has not yet been observed
  actually firing on its 5-minute cron.
- **`alert_config` has never had a webhook in it** — the Slack-alert code path in
  `open_incident`/`escalate_incidents` has never actually sent a message.
- **`ack_incident` and the board's Ack button** have not been clicked in a real
  browser session — only confirmed present in the served HTML.
- **`resolve_incident` has no caller anywhere** — no UI button, no workflow node.
  It's a complete, correct function with nothing wired to it yet.
- **The app itself has not been operated by a human in a browser** — every check
  so far has been `curl`-level (confirms the right bytes are served, cannot catch
  a broken click handler or a runtime JS error).

None of this means the code is wrong — it means it's **unverified**, which is a
different risk than "known broken" (the release-notes issue above) and worth
tracking separately.

## Lessons learned

1. **Verify the framework before building on it.** The first version of this
   project guessed the API (wrong package name, YAML agents) *before the SDK was
   public*. Once we read `lemma schema <resource>` and the real bundle contract,
   everything was rebuilt correctly. **Ground truth beats assumptions.**
2. **Agents for judgment, functions for rules — and let permissions reflect it.**
   The more we pushed deterministic work into functions, the more reliable the
   system got. The one place we left multi-step work in an agent is the one place
   that's flaky. The whole post-`persist` chain (owner → incident → auto-PR) is
   functions, not agents, for exactly this reason.
3. **Structured `output_schema` is the load-bearing wall.** It's what lets agent
   outputs flow into functions and tables without parsing.
4. **Give FORM fields defaults.** Missing input that "resolves to nothing" fails a
   run; defaults turn absence into empty strings.
5. **Separate the read from the write, even when they're related.**
   `suggest_owner` (read-only) and `assign_owner` (write) are different functions
   with different trust levels — not because Lemma requires it, but because a
   read can run constantly and automatically while a write should wait for a
   human. The same split shows up in `ack_incident` vs `escalate_incidents`.
6. **"Automate the decision, not the action" for anything irreversible.**
   `open_fix_pr` opens a PR with a *proposal document*, never splicing AI code
   into a real file. The automation's job is to remove investigation work, not
   to remove the human review of a real change.
7. **Verify a new capability with the smallest possible probe before building on
   it.** `github_ping` (one HTTP call) came before any real GitHub logic — cheap
   insurance against discovering a sandbox restriction halfway through a feature.
8. **Tooling reality matters.** The CLI can't run on native Windows (`termios`);
   WSL or a shim is required. Launch-week cloud was flaky; idempotent imports +
   retries + `--timeout` get you through.
9. **Small CLI footguns:** `import` needs an existing pod; `--org` wants a UUID;
   tables/functions are `snake_case`, agents/workflows are `hyphen-case`.

## Roadmap (in priority order)

1. **Verify the unverified** (see above) — connect a real repo+PAT, configure a
   Slack webhook, click every button in a real browser, wait out one
   `escalate_incidents` cycle. This is now the top priority, ahead of new features.
2. **Harden release notes** — the function/agent/function split above.
3. **Wire `resolve_incident`** — a "Resolve" button on the board once a bug's fix
   is actually merged, or auto-resolve when the linked bug's status changes.
4. **Auto-intake via a Surface + Connector** — a Slack or GitHub **surface** so new
   reports create `issues` rows automatically; switch `triage-issue`'s start to
   `DATASTORE_EVENT` so they triage themselves.
5. **Multi-repo support** — `github_config` currently holds one repo per row; a
   real org needs several. GitHub itself has no such limit (one PAT can already
   reach every repo it's scoped to) — this is purely a data-model upgrade: a
   `repos` table instead of a single config row, with `issues` carrying which
   repo it came from.
6. **Duplicate detection** — add a `VECTOR` column to `bugs`, embed each report on
   triage, and have a function flag near-duplicates.
7. **Approval gates** before any *other* outward action beyond what already
   exists (e.g. auto-closing an issue, posting to a public channel).

## Map of the codebase

```
gappyai/
  cortex-triage/                 the pod bundle (the product)
    pod.json
    tables/      issues bugs fixes release_notes github_config incidents alert_config
    agents/      triage-agent fix-suggester release-notes-writer
    functions/   persist_triage github_ping suggest_owner assign_owner
                 open_incident ack_incident escalate_incidents resolve_incident open_fix_pr
    workflows/   triage-issue compile-release-notes escalate-incidents
    schedules/   escalate-incidents (TIME, */5 * * * *)
    apps/        cortex-board (no-build HTML app, live at cortex-board.apps.lemma.work)
    demo/
  docs/                          these docs
  scripts/winshim/                Windows termios workaround for the CLI
  README.md  IMPLEMENTATION_GUIDE.md  PROJECT_SPEC.md  SETUP_CHECKLIST.md
```

That's the whole system — concepts, design, code, and the honest state of each
piece, including what's still unproven. Start back at the [index](README.md) if
you want to re-trace any thread.
