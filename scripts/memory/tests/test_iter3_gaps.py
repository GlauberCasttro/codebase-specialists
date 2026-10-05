"""Iteração 3 (contrato `gap`): facts/gaps.json5 nunca entra na memória (lacuna não é conhecimento)."""
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import mem  # noqa: E402


class GapsNotKnowledge(unittest.TestCase):
    def test_gaps_file_not_a_source(self):
        root = tempfile.mkdtemp(prefix="cs-mem-gap-")
        try:
            fd = os.path.join(root, ".swarm", "facts")
            os.makedirs(fd)
            for n in ("glossary.json5", "gaps.json5"):
                with open(os.path.join(fd, n), "w") as fh:
                    fh.write('{facts: []}\n')
            srcs = mem._sources(root, mem.mem_paths(root))
            self.assertIn(".swarm/facts/glossary.json5", srcs)
            self.assertNotIn(".swarm/facts/gaps.json5", srcs)
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
