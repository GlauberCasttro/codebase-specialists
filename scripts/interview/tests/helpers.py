"""Repo sintético (team/tests/synth.py) + execução do cs.py real em subprocesso."""
import os
import subprocess
import sys

SCRIPTS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(SCRIPTS, "team", "tests"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
import synth  # noqa: E402,F401

CS = os.path.join(SCRIPTS, "cs.py")


def cs(root, *args):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("CLAUDE_PROJECT_DIR", None)
    p = subprocess.run([sys.executable, CS, "--target", root] + list(args), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, env=env, cwd=root)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def write(root, rel, text):
    full = os.path.join(root, rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as fh:
        fh.write(text)
    return full
