"""iter26 (CA-04/CA-09): textos emitidos citam só flags/subcomandos en do cs-state, e cada um EXECUTA num alvo árvore."""
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(SKILL, "scripts"))
sys.path.insert(0, HERE)

PT = re.compile(r"--(tipo|como|quero|para|motivo|reproducao)\b|\bnew epico\b")
CITED = re.compile(r"cs-state new (epic|sprint|feature|story|task)\b([^`\n]*)")
SD = ".swarm"


def _run(args, cwd):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


class TestTextosEmitidos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import fixture
        cls.tmp = tempfile.mkdtemp(prefix="cs-iter26-")
        cls.addClassCleanup(shutil.rmtree, cls.tmp, True)
        src = fixture.make_repo()
        cls.root = os.path.join(cls.tmp, "alvo")
        shutil.move(src, cls.root)
        subprocess.run(["git", "init", "-q"], cwd=cls.root)
        cs = [sys.executable, os.path.join(SKILL, "scripts", "cs.py"), "--target", cls.root]
        for a in (["init", "--platforms", "claude-code"], ["harness", "install", "--allow-outside"],
                  ["emit", "--allow-outside"]):
            rc, out, err = _run(cs + a, cls.root)
            assert rc == 0, (a, out[-800:], err[-800:])
        cls.state = [sys.executable, os.path.join(cls.root, SD, "harness", "state.py"), "--root", cls.root]
        rc, out, err = _run(cls.state + ["init"], cls.root)
        assert rc == 0, (out, err)

    def _texts(self):
        got = []
        for rel in ("CLAUDE.md", "AGENTS.md", "Makefile", "specialists.mk"):
            if os.path.isfile(os.path.join(self.root, rel)):
                got.append(rel)
        for d in (".claude", ".cursor", ".github", os.path.join(SD, "emit")):
            for dp, _, fns in os.walk(os.path.join(self.root, d)):
                if "agent-memory" in dp:
                    continue
                for fn in fns:
                    got.append(os.path.relpath(os.path.join(dp, fn), self.root))
        for rel in got:
            try:
                with open(os.path.join(self.root, rel), encoding="utf-8") as f:
                    yield rel, f.read()
            except (UnicodeDecodeError, OSError):
                continue

    def test_sem_flags_pt(self):
        hits = ["%s:%d: %s" % (rel, i, ln.strip()[:120]) for rel, t in self._texts()
                for i, ln in enumerate(t.splitlines(), 1) if "cs-auto" not in ln and PT.search(ln)]
        self.assertEqual(hits, [])

    def test_orquestrador_orienta_git_add(self):
        with open(os.path.join(self.root, ".claude", "orchestrator.md"), encoding="utf-8") as f:
            self.assertRegex(f.read(), r"git add (-A )?\.swarm")

    def test_cada_flag_citada_existe_no_motor(self):
        """toda flag de `cs-state new <kind> ...` citada nos textos aparece no --help real daquele subcomando."""
        helps = {}
        for kind in ("epic", "sprint", "feature", "story", "task"):
            rc, out, err = _run(self.state + ["new", kind, "--help"], self.root)
            self.assertEqual(rc, 0, kind + err)
            helps[kind] = out
        bad = []
        for rel, t in self._texts():
            for ln in t.splitlines():
                for m in CITED.finditer(ln):
                    for flag in re.findall(r"(?<![\w-])--[a-z][a-z-]*", m.group(2)):
                        if flag not in helps[m.group(1)] and flag != "--dry-run":
                            bad.append("%s: new %s %s" % (rel, m.group(1), flag))
        self.assertEqual(bad, [])

    def test_exemplos_do_processo_executam(self):
        """os exemplos `cs-state new story ...` do product-process rodam (--dry-run) numa feature real do alvo."""
        st = self.state
        ids = {}
        for kind, args in (("epic", ["--title", "E", "--objetivo", "o"]),):
            rc, out, err = _run(st + ["new", kind] + args, self.root)
            self.assertEqual(rc, 0, out + err)
            ids[kind] = re.search(r"(EPC-\d+)", out).group(1)
        rc, out, err = _run(st + ["new", "sprint", "--meta", "m", "--epico", ids["epic"]], self.root)
        self.assertEqual(rc, 0, out + err)
        spr = re.search(r"(SPR-\d+)", out).group(1)
        rc, out, err = _run(st + ["new", "feature", "--title", "F", "--sprint", spr, "--aceite", "true"], self.root)
        self.assertEqual(rc, 0, out + err)
        fea = re.search(r"(FEA-\d+)", out).group(1)
        agent = re.search(r"dev-[\w-]+", " ".join(os.listdir(os.path.join(self.root, ".claude", "agents")))).group(0)
        ran = 0
        with open(os.path.join(SKILL, "assets", "templates", "product-process.md"), encoding="utf-8") as f:
            tpl = f.read()
        for rel, t in list(self._texts()) + [("product-process.md", tpl)]:
            for ln in t.splitlines():
                m = re.search(r"`(\.swarm/bin/cs-state new story [^`]*)`", ln)
                if not m or "<US|BUG|FIX" in m.group(1):
                    continue
                cmd = m.group(1).replace("FEA-003", fea).replace("BUG-7", "BUG-1").replace("<agente>", agent)
                cmd = re.sub(r"<[^>]*>", "src/billing/x.py", cmd)
                argv = shlex.split(cmd)
                if "--type" not in argv and "--tipo" not in argv:
                    continue
                rc, out, err = _run(st + argv[1:] + ["--dry-run"], self.root)
                self.assertEqual(rc, 0, "%s: %s\n%s%s" % (rel, cmd, out, err))
                ran += 1
        self.assertGreater(ran, 0)


if __name__ == "__main__":
    unittest.main()
