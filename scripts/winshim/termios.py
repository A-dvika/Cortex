# Minimal Windows shim so the Lemma CLI (lemma_cli) can `import termios` at
# module load on native Windows. The real termios calls only run inside the
# interactive arrow-key selector, which is used ONLY when stdin/stdout are a TTY;
# non-interactive runs fall back to numbered prompts and never call these.
#
# Usage (Git Bash / PowerShell): put this dir on PYTHONPATH before running lemma.
#   PYTHONPATH=scripts/winshim lemma pods import ./cortex-triage --dry-run
#
# This is a DEV/VALIDATION convenience. The supported path on Windows is WSL.

TCSANOW = 0
TCSADRAIN = 1
TCSAFLUSH = 2


def tcgetattr(fd):
    return []


def tcsetattr(fd, when, attrs):
    return None


def tcsendbreak(fd, duration):
    return None


def tcdrain(fd):
    return None


def tcflush(fd, queue):
    return None


def tcflow(fd, action):
    return None
