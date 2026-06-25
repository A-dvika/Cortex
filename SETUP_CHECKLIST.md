# Setup Checklist (verified)

## Already done on this machine ✅
- [x] Node v20.14.0, npm 10.7.0, Python 3.10.0, Docker 26.1.4, git — present
- [x] `uv` installed (0.11.24)
- [x] `lemma-terminal` CLI installed → `lemma` 0.5.0 (at `~/.local/bin`)
- [x] Pod bundle built & JSON-validated in `cortex-triage/`
- [x] CLI verified working via winshim (reaches auth boundary)

## To deploy/run — still needed
- [ ] **A Lemma backend + token.** Pick one:
  - Cloud: `lemma auth login` (uses lemma.work)
  - Local: `curl -fsSL https://raw.githubusercontent.com/lemma-work/lemma-platform/main/install.sh | bash`, then `lemma auth login`
- [ ] **Run CLI somewhere termios exists** (real `auth login`/`import`):
  - WSL/Ubuntu (installed) — recommended, or the local Docker platform
- [ ] **Agent runtime / model** available to the backend (default `system:lemma`,
      or pin one + provide an API key if self-hosting)

## Optional (later milestones)
- [ ] GitHub token (issues → pod) — for the surface/connector
- [ ] Slack workspace + bot token — for alerts/intake
- [ ] Node deps for the dashboard app: `npm install lemma-sdk`

## Decision needed from you
**Cloud (lemma.work) or local Docker backend?** This determines the exact
`auth login` flow and whether you run in WSL or in the Docker stack.
