#!/usr/bin/env python3
"""Fail if production code touches float in a money context (ADR 0001).

Usage: python3 scripts/check_no_float_money.py src/billing
"""
import pathlib
import re
import sys

PATTERNS = [re.compile(r"\bfloat\("), re.compile(r"\bround\("), re.compile(r"cents\s*/\s*[^/]")]
ALLOW = "# money-ok"


def main(root: str) -> int:
    bad = []
    for path in sorted(pathlib.Path(root).rglob("*.py")):
        for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if ALLOW in line:
                continue
            if any(p.search(line) for p in PATTERNS):
                bad.append("%s:%d: %s" % (path, no, line.strip()))
    for b in bad:
        print(b)
    if bad:
        print("money check failed: %d occurrence(s); see docs/adr/0001" % len(bad))
        return 1
    print("money check ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "src/billing"))
