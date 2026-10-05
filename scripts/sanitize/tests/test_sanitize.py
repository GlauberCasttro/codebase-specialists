"""DEC-SANITIZE (2026-10-03) — um teste por cenário SANITIZE-1..4 + cópia de exame apagada após `probes check`.

Layout pós-init reproduz o medido num repositório-piloto (projeto-legado): `tmp/` com cópia de exame (clone com `.git`), pacote de
entrada, rascunhos e scripts de contorno (`fix_g2.py`…), `harness/__pycache__`, sem `.gitignore`.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(os.path.dirname(HERE))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from cslib import json5io, paths  # noqa: E402
from sanitize import core  # noqa: E402

CS = os.path.join(SCRIPTS, "cs.py")
SKILL = os.path.dirname(SCRIPTS)
D = paths.SPECIALISTS_DIRNAME
GIT_ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@t", GIT_CONFIG_NOSYSTEM="1", LC_ALL="C")
GIT_ENV.pop("CLAUDE_PROJECT_DIR", None)


def git(cwd, *args):
    p = subprocess.run(["git", "-C", cwd, "-c", "init.defaultBranch=main", "-c", "commit.gpgsign=false"]
                       + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=GIT_ENV)
    if p.returncode != 0:
        raise AssertionError("git %s: %s" % (args, p.stderr.decode()))
    return p.stdout.decode()


def cs(root, *args):
    p = subprocess.run([sys.executable, CS, "--target", root] + list(args), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, env=GIT_ENV)
    return p.returncode, p.stdout.decode(), p.stderr.decode()


def write(path, text="x\n", mode=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)
    if mode:
        os.chmod(path, mode)


def tree_hash(root):
    h = hashlib.sha256()
    for dp, dn, fn in os.walk(root):
        dn.sort()
        for n in sorted(fn + [d for d in dn if os.path.islink(os.path.join(dp, d))]):
            p = os.path.join(dp, n)
            st = os.lstat(p)
            h.update(("%s|%o|%d\n" % (os.path.relpath(p, root), st.st_mode, st.st_mtime_ns)).encode())
            if os.path.isfile(p) and not os.path.islink(p):
                with open(p, "rb") as fh:
                    h.update(fh.read())
        h.update(("D %s %s\n" % (os.path.relpath(dp, root), dn)).encode())
    return h.hexdigest()


def post_init_repo():
    """Repo git com produto commitado e uma pasta da skill como o init a deixa hoje (lixo incluído)."""
    root = os.path.realpath(tempfile.mkdtemp(prefix="cs-sanitize-"))
    write(os.path.join(root, "src", "app.py"), "print('produto')\n")
    write(os.path.join(root, "README.md"), "# produto\n")
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "produto")
    sp = os.path.join(root, D)
    # artefatos que ficam (estado, fatos, harness, manifesto do emit)
    write(os.path.join(sp, "run.json5"), "{schema_version: 1}\n")
    write(os.path.join(sp, "facts", "index.json5"), "{facts: []}\n")
    write(os.path.join(sp, "harness", "engine.py"), "X = 1\n")
    write(os.path.join(sp, "harness", "__pycache__", "engine.cpython-313.pyc"), "bytecode")
    write(os.path.join(sp, "memory", "index", "bm25.json"), "{}")
    json5io.dump({"schema_version": 1, "files": [{"path": "CLAUDE.md", "platform": "claude-code"}]},
                 os.path.join(sp, "emit", "manifest.json5"), "manifesto de teste")
    write(os.path.join(root, "CLAUDE.md"), "<!-- gerado -->\n")
    write(os.path.join(root, ".claude", "settings.json"), "{}\n")
    # lixo de tmp/: cópia de exame (clone com .git próprio), pacote de entrada, rascunhos, contornos
    exam = os.path.join(sp, "tmp", "exam", "dev-a")
    write(os.path.join(exam, "exam.json5"), '{agent: "dev-a"}\n')
    repo = os.path.join(exam, "repo")
    write(os.path.join(repo, "src", "app.py"), "print('produto')\n")
    write(os.path.join(repo, "scripts", "build.sh"), "#!/bin/sh\n", 0o755)  # do produto: não é contorno
    git(repo, "init", "-q")
    write(os.path.join(sp, "tmp", "in", "pacote.json5"), "{}" + " " * 4096)
    write(os.path.join(sp, "tmp", "cards", "dev-a.json5"), "{}")
    write(os.path.join(sp, "tmp", "fix_g2.py"), "import sys\n")
    write(os.path.join(sp, "tmp", "inspect_g2.py"), "import os\n")
    write(os.path.join(sp, "tmp", "roster", "run"), "#!/bin/sh\necho\n")
    return root


class Sanitize(unittest.TestCase):
    def setUp(self):
        self.root = post_init_repo()
        self.sp = os.path.join(self.root, D)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_sanitize_1_apply_leaves_clean_small_committable_dir(self):
        code, out, err = cs(self.root, "sanitize", "--apply")
        self.assertEqual(code, 0, out + err)
        self.assertFalse(os.path.exists(os.path.join(self.sp, "tmp")), "tmp/ tem de sumir")
        for dp, dn, _ in os.walk(self.sp):
            self.assertNotIn("__pycache__", dn, dp)
            self.assertNotIn(".git", dn, dp)
        with open(os.path.join(self.sp, ".gitignore")) as fh:
            lines = set(fh.read().splitlines())
        for e in ("tmp/", "memory/index/", "__pycache__/", "backups/"):
            self.assertIn(e, lines)
        st = git(self.root, "status", "--porcelain", "-uall").splitlines()
        self.assertTrue(st)
        for ln in st:
            rel = ln[3:]
            self.assertTrue(rel.startswith(D + "/") or rel in ("CLAUDE.md", ".claude/settings.json"), ln)
            self.assertFalse(rel.startswith(D + "/memory/index/"), ln)
        self.assertLessEqual(core.size_of(self.sp), 5 * 1024 * 1024)
        self.assertIn("fica", out)
        self.assertIn("entra no commit", out)
        self.assertIn("%s/run.json5" % D, out)
        self.assertNotIn("bm25", out)
        rec = json5io.load(os.path.join(self.sp, "sanitize.json5"))
        self.assertTrue(rec["applied"])
        self.assertEqual(rec["product_changes"], [])
        code, out, err = cs(self.root, "sanitize", "--check")
        self.assertEqual(code, 0, out + err)
        # idempotente
        code, out, err = cs(self.root, "sanitize", "--apply")
        self.assertEqual(code, 0, out + err)

    def test_sanitize_1b_product_change_is_reported(self):
        write(os.path.join(self.root, "src", "app.py"), "print('mexeram')\n")
        code, out, _ = cs(self.root, "sanitize", "--apply")
        self.assertEqual(code, 0)
        self.assertIn("aviso: alterado fora do esperado (produto?): ", out)
        self.assertIn("src/app.py", out)

    def test_sanitize_2_plan_without_apply_deletes_nothing(self):
        before = tree_hash(self.root)
        code, out, err = cs(self.root, "sanitize")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(tree_hash(self.root), before, "plano não pode escrever nada")
        self.assertIn("nada foi apagado", out)
        self.assertIn("apagar: %s/tmp/" % D, out)
        self.assertIn("%s/harness/__pycache__/" % D, out)
        self.assertIn("gravar + tmp/, memory/index/, __pycache__/, backups/", out)
        code, out, _ = cs(self.root, "sanitize", "--json")
        self.assertEqual(code, 0)
        rep = json.loads(out)
        self.assertFalse(rep["applied"])
        self.assertGreater(rep["delete"]["tmp"]["bytes"], 4096)
        self.assertEqual(tree_hash(self.root), before)

    def test_sanitize_3_script_left_in_tmp_is_reported_as_workaround_before_deletion(self):
        code, out, err = cs(self.root, "sanitize", "--apply")
        self.assertEqual(code, 0, out + err)
        defects = [ln for ln in out.splitlines() if ln.startswith("DEFEITO (contorno manual")]
        got = sorted(ln.split(": ", 1)[1].split(" (")[0] for ln in defects)
        self.assertEqual(got, ["%s/tmp/fix_g2.py" % D, "%s/tmp/inspect_g2.py" % D, "%s/tmp/roster/run" % D])
        self.assertNotIn("build.sh", out, "script do produto na cópia de exame não é contorno")
        self.assertFalse(os.path.exists(os.path.join(self.sp, "tmp", "fix_g2.py")))
        rec = json5io.load(os.path.join(self.sp, "sanitize.json5"))
        self.assertEqual(len(rec["defects"]["workaround_scripts"]), 3)
        # o plano (sem --apply) também já aponta o contorno
        self.root2 = post_init_repo()
        try:
            _, out2, _ = cs(self.root2, "sanitize")
            self.assertIn("DEFEITO (contorno manual do executor, script deixado em tmp/): %s/tmp/fix_g2.py" % D,
                          out2)
        finally:
            shutil.rmtree(self.root2, ignore_errors=True)

    def test_sanitize_4_approve_4_does_not_close_dirty(self):
        from stage import engine
        cfg = engine.load_stages()
        subs = [s for s in cfg["stages"]["approve"]["substages"]]
        ids = [s["id"] for s in subs]
        self.assertIn("approve.4", ids)
        self.assertLess(ids.index("approve.4"), ids.index("approve.3"), "antes do cs-session save final")
        chk = [s for s in subs if s["id"] == "approve.4"][0]["check"]
        self.assertFalse(engine.run_check(self.root, chk)[0], "tmp/ cheio e sem .gitignore")
        self.assertEqual(cs(self.root, "sanitize", "--apply")[0], 0)
        self.assertTrue(engine.run_check(self.root, chk)[0])
        # tmp/ não vazio de novo → não fecha
        write(os.path.join(self.sp, "tmp", "rascunho.json5"), "{}")
        ok, code, detail, _ = engine.run_check(self.root, chk)
        self.assertFalse(ok)
        self.assertIn("tmp/", detail)
        shutil.rmtree(os.path.join(self.sp, "tmp"))
        self.assertTrue(engine.run_check(self.root, chk)[0])
        # sem .gitignore → não fecha; .gitignore incompleto → não fecha
        os.remove(os.path.join(self.sp, ".gitignore"))
        ok, _, detail, _ = engine.run_check(self.root, chk)
        self.assertFalse(ok)
        self.assertIn(".gitignore", detail)
        write(os.path.join(self.sp, ".gitignore"), "tmp/\n")
        self.assertFalse(engine.run_check(self.root, chk)[0])
        # .git aninhado fora de tmp/ → não fecha
        self.assertEqual(cs(self.root, "sanitize", "--apply")[0], 0)
        os.makedirs(os.path.join(self.sp, "copia", ".git"))
        ok, _, detail, _ = engine.run_check(self.root, chk)
        self.assertFalse(ok)
        self.assertIn(".git aninhado", detail)


AGENT = "dev-billing"


class ExamCopyRemovedAfterCheck(unittest.TestCase):
    """Causa do lixo: cada cópia de exame (clone com .git) é apagada logo após o `probes check` do agente."""

    def setUp(self):
        sys.path.insert(0, os.path.join(SCRIPTS, "team", "tests"))
        sys.path.insert(0, os.path.join(SCRIPTS, "probes", "tests"))
        import synth
        from team.derive import derive
        from probes.generate import generate
        self.synth = synth
        self.root = synth.make_repo()
        derive(self.root)
        generate(self.root)
        write(os.path.join(self.root, ".gitignore"), "%s/\n" % D)
        git(self.root, "init", "-q")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "init")
        self.outside = os.path.realpath(tempfile.mkdtemp(prefix="cs-exam-out-"))

    def tearDown(self):
        self.synth.cleanup(self.root)
        shutil.rmtree(self.outside, ignore_errors=True)

    def _exam(self, out):
        from probes.generate import load_bank
        from test_probes import perfect
        code, o, e = cs(self.root, "probes", "exam-pack", AGENT, "--out", out)
        self.assertEqual(code, 0, o + e)
        self.assertTrue(os.path.isdir(os.path.join(out, "repo", ".git")))
        items = [perfect(p) for p in load_bank(self.root)["probes"] if p["agent"] == AGENT]
        with open(os.path.join(out, "answers.json5"), "w") as fh:
            fh.write(json.dumps(items))
        code, o, e = cs(self.root, "probes", "check", AGENT, "--answers", os.path.join(out, "answers.json5"))
        self.assertIn(code, (0, 1), o + e)  # G4 pode reprovar (sem baseline): o que importa é a cópia
        self.assertIn("%s:" % AGENT, o)
        self.assertTrue(os.path.isfile(os.path.join(self.root, D, "probes", "exams", "%s.answers.json5" % AGENT)))
        self.assertTrue(os.path.isfile(os.path.join(self.root, D, "probes", "reports", "%s.json5" % AGENT)))

    def test_copy_inside_tmp_is_removed_after_check(self):
        out = os.path.join(self.root, D, "tmp", "exam", AGENT)
        self._exam(out)
        self.assertFalse(os.path.exists(os.path.join(out, "repo")), "cópia de exame acumulada após o check")
        self.assertFalse(os.path.exists(os.path.join(self.root, D, "probes", "exams",
                                                     "%s.exam-copy.json5" % AGENT)))
        self.assertTrue(os.path.isfile(os.path.join(self.root, "src", "billing", "invoice.py")), "alvo intacto")

    def test_copy_outside_target_is_removed_after_check(self):
        out = os.path.join(self.outside, AGENT)
        self._exam(out)
        self.assertFalse(os.path.exists(os.path.join(out, "repo")))
        # refino: novo exam-pack no mesmo --out continua funcionando
        code, o, e = cs(self.root, "probes", "exam-pack", AGENT, "--out", out)
        self.assertEqual(code, 0, o + e)
        self.assertTrue(os.path.isdir(os.path.join(out, "repo")))

    def test_foreign_dir_is_never_removed(self):
        from probes.exam import remove_exam_copy
        foreign = os.path.join(self.root, D, "tmp", "exam", AGENT, "repo")
        write(os.path.join(foreign, "keep.txt"))
        self.assertIsNone(remove_exam_copy(self.root, AGENT), "sem exam.json5 do agente não é cópia de exame")
        self.assertTrue(os.path.isfile(os.path.join(foreign, "keep.txt")))


if __name__ == "__main__":
    unittest.main()
