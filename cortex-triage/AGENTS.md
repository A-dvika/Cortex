# Building this Lemma pod

This directory is a **pod bundle**: plain files imported with `lemma pods import`.
The bundle is the source of truth. Edit files, then re-import.

## Layout (folder name MUST equal each resource's `name`)
```
cortex-triage/
  pod.json
  tables/<name>/<name>.json
  functions/<name>/<name>.json + code.py     # JSON carries permissions.grants
  agents/<name>/<name>.json    + instruction.md
  workflows/<name>/<name>.json
```

## Naming rules that bite
- **tables, functions** → `snake_case` (must be valid SQL/Python). Here:
  `issues`, `bugs`, `fixes`, `release_notes`, `persist_triage`.
- **agents, workflows, surfaces** → `hyphen-case`. Here: `triage-agent`,
  `fix-suggester`, `release-notes-writer`, `triage-issue`, `compile-release-notes`.
- Never declare `id`/`created_at`/`updated_at`/`user_id` columns — auto-added.
- **Zero access by default.** Every table a function/agent touches must be in its
  `permissions.grants`.
- `{"$file": "..."}` inlines a sibling file (instruction.md, code.py). JSONC
  comments are allowed in bundle JSON.

## Scaffold more resources (then edit)
```bash
lemma table init <name>        # tables/<name>/<name>.json
lemma function init <name>     # functions/<name>/<name>.json + code.py
lemma agent init <name>        # agents/<name>/<name>.json + instruction.md
lemma workflow init <name>     # workflows/<name>/<name>.json
lemma schema <resource>        # canonical field reference for any resource
```

## Validate before import
```bash
lemma pods import . --dry-run   # validates everything without writing
```
