# winshim — run the Lemma CLI on native Windows

The Lemma CLI (`lemma-terminal`) does `import termios` at startup. `termios` is a
Unix-only Python module, so on native Windows **every real command crashes** with:

```
ModuleNotFoundError: No module named 'termios'
```

`termios`/`tty` are only actually *used* by the interactive arrow-key selector
(TTY-only). The crash is just the top-level import. These shim modules satisfy
that import so the CLI runs; non-interactive commands then work normally and fall
back to numbered prompts instead of arrow keys.

## Use it
```bash
# from the repo root, in Git Bash:
export PATH="$HOME/.local/bin:$PATH"
PYTHONPATH=scripts/winshim lemma pods import ./cortex-triage --dry-run
```

Verified: with the shim, the CLI gets past startup and reaches auth
(`Missing token … run lemma auth login`), i.e. it's working.

## Caveats
- This is a **dev/validation** convenience. Interactive selection menus and
  anything that truly needs a real terminal won't behave fully.
- The **supported** path on Windows is **WSL** (this machine has Ubuntu/WSL2),
  where `termios` exists natively. For real `auth login` + `import` + running
  workflows, prefer WSL or the local Docker platform.
