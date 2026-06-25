# Minimal Windows shim for `import tty` (used alongside termios by lemma_cli's
# interactive selector). No-ops are safe for non-interactive CLI runs.
# See termios.py in this folder for context.


def setraw(fd, when=None):
    return None


def setcbreak(fd, when=None):
    return None
