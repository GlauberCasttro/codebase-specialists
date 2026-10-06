"""Oráculo campanha-iter11 — sanitize num init completo nas 3 fixtures (SANITIZE-1..4 do ROADMAP).

Duas famílias:
  A) PROXY MECÂNICO (roda já): cópia de cada alvo da iteração 4 (ts-shop completo; py-billing e go-polyglot
     pausados em validate) migrada com `upgrade --apply --allow-outside` e saneada com `sanitize --apply`.
     Prova o mecanismo (tmp vazio, .gitignore, sem lixo, sem .git aninhado, ≤5 MB, git status só com o
     esperado; approve.4 fecha só assim) — e que um alvo legado (o caso da retomada) chega lá.
  B) PROVA REAL (exige a medição): toda execução COMPLETA da campanha em
     campanha-iter11/runs/eval-<id>-<fixture>/<with_skill_fast|with_skill_full>/run-<k>/target, COMO ENTREGUE pelo executor (o teste NÃO roda
     sanitize): approve.4 done, alvo limpo. Falha até existir ≥1 execução completa por fixture.
"""
import glob
import os
import shutil
import unittest

from _comum import (CAMPANHA, FIXTURES, FIXTURE_NAMES, STATE_DIR, cs, dir_size, load5, nested_git, pycaches,
                    run, tree_hash, upgraded_legacy)

MAX_BYTES = 5 * 1024 * 1024
GITIGNORE = ("tmp/", "memory/index/", "__pycache__/", "backups/")
# gerenciados (bloco próprio) + instalados pelo harness fora de .swarm/ (nenhum manifesto os lista hoje)
MANAGED = ("Makefile", "CLAUDE.md", "AGENTS.md", "specialists.mk", ".claude/settings.json", ".claude/hooks/cs-guard.sh")


def _porcelain(t):
    rc, out, err = run(["git", "-C", t, "status", "--porcelain", "-uall"])
    if rc != 0:
        raise AssertionError("git status falhou: " + err)
    return [l[3:].strip().strip('"') for l in out.splitlines() if l.strip()]


def _allowed_paths(t):
    allowed = set(MANAGED)
    man = os.path.join(t, STATE_DIR, "emit", "manifest.json5")
    if os.path.isfile(man):
        allowed |= set(f["path"] for f in load5(man).get("files") or [])
    return allowed


def _product_files(fixture):
    base = os.path.join(FIXTURES, fixture, "repo")
    return set(os.path.relpath(os.path.join(dp, f), base) for dp, _, fns in os.walk(base) for f in fns)


class _Limpo(object):
    """Asserções de 'alvo limpo' comuns às famílias A e B."""

    def assert_limpo(self, t, fixture, label):
        sw = os.path.join(t, STATE_DIR)
        tmp = os.path.join(sw, "tmp")
        self.assertFalse(os.path.isdir(tmp) and os.listdir(tmp), "%s: .swarm/tmp/ não vazio: %s"
                         % (label, sorted(os.listdir(tmp))[:6] if os.path.isdir(tmp) else ""))
        gi = os.path.join(sw, ".gitignore")
        self.assertTrue(os.path.isfile(gi), "%s: .swarm/.gitignore ausente" % label)
        with open(gi, encoding="utf-8") as fh:
            lines = set(l.strip() for l in fh)
        self.assertFalse(set(GITIGNORE) - lines, "%s: .gitignore sem %s" % (label, sorted(set(GITIGNORE) - lines)))
        ng = nested_git(t)
        self.assertEqual(ng, [], "%s: .git aninhado no alvo: %s" % (label, ng[:5]))
        size = dir_size(sw)
        self.assertLessEqual(size, MAX_BYTES, "%s: .swarm/ com %.1f MB (> 5 MB; SANITIZE-1)" % (label, size / 1048576.0))
        allowed = _allowed_paths(t)
        prod = _product_files(fixture)
        bad = [p for p in _porcelain(t) if not p.startswith(STATE_DIR + "/") and p not in allowed]
        self.assertEqual(bad, [], "%s: git status com caminho fora do manifesto/gerenciados: %s" % (label, bad[:8]))
        touched = [p for p in _porcelain(t) if p in prod and p not in allowed]
        self.assertEqual(touched, [], "%s: arquivo de produto alterado: %s" % (label, touched))
        rc, so, se = cs(t, "sanitize", "--check")
        self.assertEqual(rc, 0, "%s: sanitize --check vermelho:\n%s" % (label, (so + se)[-800:]))


class TestSanitizeProxyIter4(unittest.TestCase, _Limpo):
    """Família A — um teste por fixture (cada um com a própria cópia; L05)."""

    def _fluxo(self, fixture, completo):
        t, rc, out = upgraded_legacy(fixture)
        self.addCleanup(shutil.rmtree, os.path.dirname(t), True)
        self.assertEqual(rc, 0, "upgrade do alvo legado %s falhou — sem isso a retomada da iteração 4 não "
                                "chega ao sanitize:\n%s" % (fixture, out[-1200:]))
        # SANITIZE-2: plano não escreve
        h0 = tree_hash(t)
        rc, so, se = cs(t, "sanitize")
        self.assertEqual(rc, 0, "sanitize (plano) falhou: " + (se or so)[-400:])
        self.assertEqual(tree_hash(t), h0, "sanitize sem --apply alterou a árvore")
        # antes: approve.4 não fecha
        rc, so, se = cs(t, "sanitize", "--check")
        self.assertNotEqual(rc, 0, "sanitize --check verde ANTES do apply (check não prova efeito)")
        if completo:
            rc, so, se = cs(t, "stage", "check", "approve.4")
            self.assertNotEqual(rc, 0, "approve.4 fechou com tmp/ sujo")
        scripts = sorted(os.path.basename(p) for p in glob.glob(os.path.join(t, STATE_DIR, "tmp", "**", "*"),
                                                                recursive=True)
                         if p.endswith((".sh", ".py")) and "/exam/" not in p)
        rc, so, se = cs(t, "sanitize", "--apply")
        self.assertEqual(rc, 0, "sanitize --apply falhou: " + (se or so)[-600:])
        # SANITIZE-3: contorno manual (script em tmp/) relatado antes de apagar
        for s in scripts:
            self.assertIn(s, so + se, "script de contorno %s apagado sem aparecer no relatório" % s)
        self.assertEqual(pycaches(os.path.join(t, STATE_DIR)), [], "__pycache__ sob .swarm/ após o apply")
        self.assert_limpo(t, fixture, fixture)
        if completo:
            rc, so, se = cs(t, "stage", "check", "approve.4")
            self.assertEqual(rc, 0, "approve.4 não fechou num alvo limpo:\n" + (so + se)[-600:])
        return t

    def test_ts_shop_completo(self):
        t = self._fluxo("ts-shop", completo=True)
        # SANITIZE-4: approve.4 só fecha limpo
        junk = os.path.join(t, STATE_DIR, "tmp", "lixo.txt")
        os.makedirs(os.path.dirname(junk), exist_ok=True)
        with open(junk, "w") as fh:
            fh.write("x")
        rc, _, _ = cs(t, "stage", "check", "approve.4")
        self.assertNotEqual(rc, 0, "approve.4 fechou com tmp/ não vazio")
        os.remove(junk)
        gi = os.path.join(t, STATE_DIR, ".gitignore")
        with open(gi) as fh:
            keep = fh.read()
        os.remove(gi)
        rc, _, _ = cs(t, "stage", "check", "approve.4")
        self.assertNotEqual(rc, 0, "approve.4 fechou sem .gitignore")
        with open(gi, "w") as fh:
            fh.write(keep)
        rc, so, se = cs(t, "stage", "check", "approve.4")
        self.assertEqual(rc, 0, "approve.4 não voltou a fechar com o alvo limpo: " + (so + se)[-300:])

    def test_py_billing_pausado(self):
        self._fluxo("py-billing", completo=False)

    def test_go_polyglot_pausado(self):
        self._fluxo("go-polyglot", completo=False)


def _runs_completos(fixture):
    """Execuções da campanha com init completo (approve.4 done e current_stage finished)."""
    found = []
    for cfg in ("with_skill_fast", "with_skill_full"):
        for t in sorted(glob.glob(os.path.join(CAMPANHA, "runs", "eval-*-%s" % fixture, cfg, "run-*", "target"))):
            rj = os.path.join(t, STATE_DIR, "run.json5")
            if not os.path.isfile(rj):
                continue
            r = load5(rj)
            sub = (((r.get("stages") or {}).get("approve") or {}).get("substages") or {}).get("approve.4") or {}
            if r.get("current_stage") == "finished" and sub.get("status") == "done":
                found.append(t)
    return found


class TestSanitizeInitCompletoCampanha(unittest.TestCase, _Limpo):
    """Família B — a prova pedida pelo founder: init completo de verdade, nas 3 fixtures."""

    def test_tres_fixtures_tem_init_completo(self):
        falta = [f for f in FIXTURE_NAMES if not _runs_completos(f)]
        self.assertEqual(falta, [], "sem execução COMPLETA (approve.4 done) da campanha para: %s "
                                    "(esperado em %s/runs/eval-<id>-<fixture>/with_skill_<fast|full>/run-<k>/target)" % (falta, CAMPANHA))

    def test_alvos_entregues_limpos(self):
        ts = [(f, t) for f in FIXTURE_NAMES for t in _runs_completos(f)]
        self.assertTrue(ts, "nenhuma execução completa para conferir")
        for f, t in ts:
            with self.subTest(alvo=t):
                self.assert_limpo(t, f, os.path.relpath(t, CAMPANHA))


if __name__ == "__main__":
    unittest.main()
