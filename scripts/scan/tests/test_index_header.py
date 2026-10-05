"""facts/index.json5 tem UM cabeçalho: `cs.py scan` (rebuild) e o sync por camada da entrevista/lacunas (`interview
record --answer-unknown` → gap.<id>, `interview sync`) gravam o mesmo texto — conteúdo igual ⇒ hash igual."""
import hashlib
import os
import shutil
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_precision import build, scan  # noqa: E402
import synth  # noqa: E402

from cslib import json5io, paths  # noqa: E402
from cslib.paths import STATE_DIR  # noqa: E402

FILES = {"src/app/main.py": "from src.app.util import f\n\n\ndef g():\n    return f()\n",
         "src/app/util.py": "def f():\n    return 1\n", "README.md": "# app\n"}


def idx(root):
    p = os.path.join(root, STATE_DIR, "facts", "index.json5")
    with open(p, "rb") as fh:
        raw = fh.read()
    return hashlib.sha256(raw).hexdigest(), raw.decode("utf-8").splitlines()[0], json5io.load(p)


def cs_ok(tc, root, *args):
    r = synth.cs(root, *args)
    tc.assertEqual(r.returncode, 0, r.stdout.decode() + r.stderr.decode())


class IndexHeader(unittest.TestCase):
    def setUp(self):
        self.root = build(FILES)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_scan_and_gap_write_same_header_and_hash(self):
        scan(self.root, "--no-exec", "--layers", "L0,L1,L2")
        h_scan, head_scan, doc_scan = idx(self.root)
        self.assertEqual(head_scan, "// " + paths.FACTS_INDEX_HEADER)
        # sync da entrevista/lacunas sem mudar conteúdo: bytes idênticos
        cs_ok(self, self.root, "interview", "sync")
        h_sync, head_sync, doc_sync = idx(self.root)
        self.assertEqual(doc_sync, doc_scan)
        self.assertEqual(head_sync, head_scan)
        self.assertEqual(h_sync, h_scan)
        # lacuna (gap.<id>) gravada pelo sync por camada; rescan reconstrói o MESMO índice → MESMO hash
        cs_ok(self, self.root, "interview", "record", "--id", "Q-01", "--question", "por que centavos?",
              "--answer-unknown")
        h_gap, head_gap, doc_gap = idx(self.root)
        self.assertTrue(any(k.startswith("gap.") for k in doc_gap), doc_gap)
        self.assertEqual(head_gap, head_scan)
        scan(self.root, "--no-exec", "--layers", "L0,L1,L2")
        h_rescan, _, doc_rescan = idx(self.root)
        self.assertEqual(doc_rescan, doc_gap)
        self.assertEqual(h_rescan, h_gap)


if __name__ == "__main__":
    unittest.main()
