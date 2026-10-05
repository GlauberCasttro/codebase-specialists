#!/usr/bin/env python3
"""cs.py memory <args de cs-mem> — memória do harness (BM25, lições por agente). Delegação fina para mem.main."""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(os.path.dirname(HERE), "harness", "engine")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _run(args):
    import mem
    target = getattr(args, "target", None) or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    return mem.main(["--root", os.path.realpath(target)] + list(args.mem_args))


def register(subparsers):
    p = subparsers.add_parser("memory", help="cs-mem: add|correct|check|inject|archive|search|revalidate|consolidate|stats")
    p.add_argument("mem_args", nargs=argparse.REMAINDER)
    p.set_defaults(func=_run)


if __name__ == "__main__":
    import mem
    sys.exit(mem.main())
