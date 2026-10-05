"""AGENTS.md aninhado nunca vai para pasta que o Dockerfile copia para a imagem (iteração 1, go-polyglot)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from emit import platforms  # noqa: E402


class ShippedDirsTest(unittest.TestCase):
    def mk(self, files):
        d = Path(tempfile.mkdtemp())
        for rel, txt in files.items():
            (d / rel).parent.mkdir(parents=True, exist_ok=True)
            (d / rel).write_text(txt)
        return d

    def test_copy_specific_dirs(self):
        d = self.mk({"Dockerfile": "FROM x\nCOPY migrations /app/migrations\nCOPY --from=b /out/bin /bin\n"})
        self.assertEqual(platforms.shipped_dirs(d), {"migrations", "out"})

    def test_copy_root_means_everything(self):
        d = self.mk({"Dockerfile": "FROM x\nCOPY . .\n"})
        self.assertIsNone(platforms.shipped_dirs(d))

    def test_dockerignore_frees_nesting(self):
        d = self.mk({"Dockerfile": "FROM x\nCOPY . .\n", ".dockerignore": "**/AGENTS.md\n"})
        self.assertEqual(platforms.shipped_dirs(d), set())

    def test_no_dockerfile(self):
        self.assertEqual(platforms.shipped_dirs(self.mk({"README.md": "x"})), set())


if __name__ == "__main__":
    unittest.main()
