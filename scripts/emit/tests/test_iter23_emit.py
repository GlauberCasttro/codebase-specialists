"""iter23 (CA-07/CA-10): textos emitidos citam os comandos da árvore; o MANIFEST do harness grava a versão."""
import os
import re
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(SKILL, "scripts", "harness"))

FORBIDDEN = re.compile(r"cs-state\s+add\s+(epic|feature|story|sprint)\b")
TREE_NEW = ("epico", "sprint", "feature", "story", "task")


def _read(*p):
    with open(os.path.join(SKILL, *p), encoding="utf-8") as f:
        return f.read()


class TestEmitidosUsamArvore(unittest.TestCase):
    FILES = [("assets", "templates", "orchestrator.md"), ("assets", "templates", "product-process.md"),
             ("assets", "templates", "plan-sprint.md"), ("scripts", "emit", "render.py"),
             ("scripts", "harness", "install.py")]

    def test_sem_add_epic_feature_story(self):
        for f in self.FILES:
            txt = _read(*f)
            hits = [ln.strip() for ln in txt.splitlines() if FORBIDDEN.search(ln)]
            self.assertEqual(hits, [], "/".join(f))

    def test_plan_sprint_usa_plan_da_arvore(self):
        txt = _read("assets", "templates", "plan-sprint.md")
        self.assertIn("cs-state new sprint", txt)
        self.assertIn("cs-state plan", txt)
        self.assertNotIn("cs-state sprint plan", txt)

    def test_makefile_targets_da_arvore(self):
        import install
        names = [t[0] for t in install.MAKE_TARGETS]
        for k in TREE_NEW:
            if k != "epico":
                self.assertIn("new-" + k, names)
        self.assertIn("new-epic", names)
        self.assertIn("plan", names)
        for n in ("add-epic", "add-feature", "add-story", "sprint-plan"):
            self.assertNotIn(n, names)

    def test_comandos_dos_alvos_existem_no_motor(self):
        import install
        sys.path.insert(0, os.path.join(SKILL, "scripts", "harness", "engine"))
        for name, cmd, _ in install.MAKE_TARGETS:
            m = re.match(r"cs-state (new \w+|plan)", cmd)
            if m:
                import subprocess
                r = subprocess.run([sys.executable, os.path.join(SKILL, "scripts", "harness", "engine", "state.py")]
                                   + m.group(1).split() + ["-h"], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, name + r.stderr)


class TestManifestVersion(unittest.TestCase):
    def test_install_grava_version(self):
        import install
        src = _read("scripts", "harness", "install.py")
        self.assertIn('"version": skill_version()', src)
        self.assertTrue(install.skill_version())


if __name__ == "__main__":
    unittest.main()
