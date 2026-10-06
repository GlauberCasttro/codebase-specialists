"""ORÁCULO campanha-iter10 — defeitos U-1 e U-2 do `cs.py upgrade` (achados pela medição da iter11,
campanha-iter11/oraculo/ESPEC.md §13). A iter10 é dona de scripts/upgrade/**. Quem implementa NÃO edita este arquivo.

U-1  `upgrade --apply` de alvo legado PAUSADO antes da etapa que instala o harness (validate.5) falhava no selftest
     (exigia o pre-commit que a etapa ainda não instalou), restaurava o backup e saía 1. Exigido: o upgrade conclui,
     `harness selftest` fica verde sem exigir o que a etapa ainda não instalou, e o alvo retoma do ponto onde parou
     (mesma etapa corrente, mesmos status de etapas/subetapas; validate.5 NÃO é dada como feita pelo upgrade).
     Anti-atalho: num alvo que JÁ passou de validate.5 (ts-shop, finished, com git hook) o pre-commit continua exigido.
U-2  o backup do upgrade copiava `tmp/` do legado (clones de exame com `.git`) e `.git/hooks` para
     `<estado>/backups/`; `sanitize --check` ficava vermelho para sempre. Exigido: nenhum `tmp/` nem `.git` (dir ou
     arquivo) dentro de `<estado>/backups/`; o manifest do backup (`manifest.json5`) registra o que foi excluído
     em `excluded: [<caminho>...]`; depois de `sanitize --apply`, `sanitize --check` sai 0.

Alvos: os 3 alvos da iteration-4 (layout legado `.specialists/`), COPIADOS para temporários antes de qualquer comando
(nunca altera o original). Nome da pasta de estado nova: `cslib.paths.STATE_DIR` ou ".swarm".
Rodar: python3 -m unittest -v test_upgrade_u1_u2   (≈ 1–3 min; um upgrade por alvo, compartilhado pela classe)
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HOME = os.path.expanduser("~")
SKILL = os.path.realpath(os.environ.get("CS_SKILL_DIR") or os.path.join(HOME, ".claude", "skills", "codebase-specialists"))
WORKSPACE = os.path.realpath(os.environ.get("CS_WORKSPACE") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SCRIPTS = os.path.join(SKILL, "scripts")
CS = os.path.join(SCRIPTS, "cs.py")
ITER4 = {f: os.path.join(WORKSPACE, "iteration-4", "%s-setup-vague" % f, "with_skill", "target")
         for f in ("py-billing", "go-polyglot", "ts-shop")}
LEGACY_DIR = ".specialists"   # nome da pasta NOS ALVOS HISTÓRICOS (dado de entrada), não do alvo migrado

if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
try:
    from cslib.paths import STATE_DIR as _SD  # noqa: E402
except ImportError:
    _SD = ".swarm"
SD = os.path.basename(str(_SD).rstrip("/")) or ".swarm"
from cslib import json5io  # noqa: E402


def run(argv, cwd, timeout=900):
    e = dict(os.environ)
    for k in ("CLAUDE_PROJECT_DIR", "CS_ACTOR", "CS_GUARD_OFF"):
        e.pop(k, None)
    p = subprocess.run(argv, cwd=cwd, env=e, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    return p.returncode, p.stdout.decode("utf-8", "replace") + "\n" + p.stderr.decode("utf-8", "replace")


def cs(t, *args, **kw):
    return run([sys.executable, CS, "--target", t] + list(args), t, **kw)


def skill_version():
    with open(os.path.join(SKILL, "VERSION"), encoding="utf-8") as f:
        return f.read().strip()


def stage_snapshot(run_json):
    """(current_stage, {etapa: status}, {subetapa: status}) — o 'ponto onde parou'."""
    st = run_json.get("stages") or {}
    stages = {k: (v or {}).get("status") for k, v in st.items()}
    subs = {}
    for v in st.values():
        for sid, sv in ((v or {}).get("substages") or {}).items():
            subs[sid] = (sv or {}).get("status")
    return run_json.get("current_stage"), stages, subs


def nested(root, name):
    out = []
    for dp, dns, fns in os.walk(root):
        for n in list(dns) + list(fns):
            if n == name:
                out.append(os.path.relpath(os.path.join(dp, n), root))
        dns[:] = [d for d in dns if d != ".git"]
    return out


class _Upgraded(object):
    """Copia o alvo da iteration-4, guarda o 'ponto onde parou' e roda `upgrade --apply --allow-outside` uma vez."""
    FIXTURE = None

    @classmethod
    def setUpClass(cls):
        src = ITER4[cls.FIXTURE]
        if not os.path.isfile(os.path.join(src, LEGACY_DIR, "run.json5")):
            raise unittest.SkipTest("alvo da iteration-4 ausente: %s" % src)
        cls.base = os.path.realpath(tempfile.mkdtemp(prefix="oraculo-iter10-u12-%s-" % cls.FIXTURE))
        cls.t = os.path.join(cls.base, "target")
        shutil.copytree(src, cls.t, symlinks=True)
        cls.before = stage_snapshot(json5io.read(os.path.join(cls.t, LEGACY_DIR, "run.json5")))
        cls.rc, cls.out = cs(cls.t, "upgrade", "--apply", "--allow-outside")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(getattr(cls, "base", ""), ignore_errors=True)

    def sd(self, *p):
        return os.path.join(self.t, SD, *p)

    def assert_upgraded(self):
        self.assertEqual(self.rc, 0, "upgrade --apply de %s deveria concluir: %s" % (self.FIXTURE, self.out[-2500:]))
        self.assertTrue(os.path.isfile(self.sd("run.json5")), "alvo migrado para %s/" % SD)
        self.assertEqual(json5io.read(self.sd("run.json5")).get("skill_version"), skill_version())

    # ------------------------------------------------------------------ U-2 (vale para todo alvo legado)
    def test_u2_backup_sem_tmp_nem_git_aninhado_e_manifest_registra_exclusao(self):
        self.assert_upgraded()
        bk = self.sd("backups")
        self.assertTrue(os.path.isdir(bk), "upgrade guarda backup em %s/backups/" % SD)
        gits = nested(bk, ".git")
        self.assertEqual(gits, [], "nenhum .git (dir ou arquivo) dentro do backup: %s" % gits[:5])
        tmps = [p for p in nested(bk, "tmp")]
        self.assertEqual(tmps, [], "backup não copia tmp/ do legado: %s" % tmps[:5])
        mans = [os.path.join(dp, "manifest.json5") for dp, _, fns in os.walk(bk) if "manifest.json5" in fns]
        self.assertTrue(mans, "backup tem manifest.json5")
        excl = []
        for m in mans:
            excl += [str(x) for x in (json5io.read(m).get("excluded") or [])]
        self.assertTrue(any("tmp" in x.split("/") for x in excl), "manifest registra `excluded` com o tmp/: %r" % excl)
        if self.HAS_NESTED_GIT:
            self.assertTrue(any(".git" in x.split("/") for x in excl), "manifest registra os .git excluídos: %r" % excl)

    def test_u2_sanitize_check_verde_no_alvo_migrado(self):
        self.assert_upgraded()
        rc, out = cs(self.t, "sanitize", "--apply")
        self.assertEqual(rc, 0, "sanitize --apply: %s" % out[-1500:])
        rc, out = cs(self.t, "sanitize", "--check")
        self.assertEqual(rc, 0, "sanitize --check deve ficar verde num alvo legado migrado: %s" % out[-2500:])


class _Pausado(_Upgraded):
    HAS_NESTED_GIT = True

    def test_u1_upgrade_de_alvo_pausado_conclui_com_selftest_verde(self):
        self.assert_upgraded()
        self.assertNotIn("backup restaurado", self.out, "upgrade não pode cair na restauração")
        rc, out = cs(self.t, "harness", "selftest")
        self.assertEqual(rc, 0, "selftest verde sem exigir o que validate.5 ainda não instalou: %s" % out[-2000:])

    def test_u1_alvo_retoma_do_ponto_onde_parou(self):
        self.assert_upgraded()
        cur0, stages0, subs0 = self.before
        cur1, stages1, subs1 = stage_snapshot(json5io.read(self.sd("run.json5")))
        self.assertEqual(cur1, cur0, "etapa corrente preservada (%s)" % cur0)
        self.assertEqual(stages1, stages0, "status das etapas preservados")
        for sid, st in subs0.items():
            self.assertEqual(subs1.get(sid), st, "subetapa %s preservada (%s → %s)" % (sid, st, subs1.get(sid)))
        self.assertNotEqual(subs1.get("validate.5"), "done", "upgrade não dá validate.5 (harness) como feita")
        rc, out = cs(self.t, "stage", "status")
        self.assertEqual(rc, 0, out[-1500:])
        self.assertIn(cur0, out, "stage status mostra a etapa onde parou")
        rc, out = cs(self.t, "stage", "load", cur0)
        self.assertEqual(rc, 0, "a execução retoma: `cs.py stage load %s`: %s" % (cur0, out[-1500:]))


class TestPyBillingPausado(_Pausado, unittest.TestCase):
    FIXTURE = "py-billing"


class TestGoPolyglotPausado(_Pausado, unittest.TestCase):
    FIXTURE = "go-polyglot"


class TestTsShopFinalizado(_Upgraded, unittest.TestCase):
    """Alvo que já passou de validate.5: U-2 vale; o pre-commit continua exigido (U-1 não vira atalho)."""
    FIXTURE = "ts-shop"
    HAS_NESTED_GIT = True

    def test_u1_alvo_finalizado_continua_exigindo_pre_commit(self):
        self.assert_upgraded()
        rc, out = cs(self.t, "harness", "selftest")
        self.assertEqual(rc, 0, "selftest verde depois do upgrade: %s" % out[-1500:])
        hook = os.path.join(self.t, ".git", "hooks", "pre-commit")
        self.assertTrue(os.path.exists(hook), "upgrade reinstala o git hook que o alvo já tinha")
        os.rename(hook, hook + ".off")
        try:
            rc, out = cs(self.t, "harness", "selftest")
            self.assertNotEqual(rc, 0, "alvo que já passou de validate.5 sem pre-commit → selftest vermelho")
            self.assertIn("pre-commit", out)
        finally:
            os.rename(hook + ".off", hook)


if __name__ == "__main__":
    unittest.main()
