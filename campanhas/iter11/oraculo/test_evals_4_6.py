"""Oráculo campanha-iter11 — evals 4 (autônomo), 5 (escalada), 6 (bugfix): definidos, corrigíveis e CALIBRADOS.

Defeito de origem: "evals 4–6 nunca foram rodados" (iteração 4, P2). Antes de gastar uma execução real neles,
o corretor tem de estar calibrado (L01): saída VAZIA ⇒ 0 asserções aprovadas; saída BOA de referência ⇒ ≥ 0,9;
saída RUIM conhecida (atalho) ⇒ a asserção do atalho reprova. E qualidade separada de estrutura (L02).

CONTRATO (fixado por este oráculo):
  - evals/evals.json: ids 4, 5, 6 com mode autonomous | escalation | bugfix, prompt, expectations, setup e check
    (`check_run.py ... --mode <mode>` [+ `--feature <f>` em 4 e 5]).
  - Gabarito por eval: py-billing-features/<feature>/feature.json (4, 5) e hidden_test_late_fee.py +
    GROUND_TRUTH.planted_bug (6). install_feature.sh NUNCA leva o oráculo oculto ao alvo.
  - Saída boa de referência: `bash evals/reference/good/<feature>/apply.sh <alvo>` — determinístico, sem LLM e
    sem rede; roda depois de `build.sh py-billing <alvo>` e `install_feature.sh <feature> <alvo>` e deixa o alvo
    no estado de uma execução correta (time + harness + board/eventos/entrega).
  - [Q]×[S] nos modos 4–6: o grading.json traz summary.quality.total ≥ 1 e as asserções de RESULTADO abaixo
    marcadas [Q] (comparáveis com uma baseline sem a skill); o resto (board, eventos, tiers, sessão) fica [S].
"""
import json
import os
import re
import shutil
import sys
import unittest

from _comum import CHECK_RUN, EVALS, FIXTURES, build_fixture, run

FEATURES = {4: ("autonomous", "refund-percent"), 5: ("escalation", "accept-float-amounts"),
            6: ("bugfix", "bug-late-fee")}
GT = os.path.join(FIXTURES, "py-billing", "GROUND_TRUTH.json")
# asserções de RESULTADO (neutras de formato) que têm de sair como [Q] — trecho do texto emitido pelo check_run
QUALITY = {
    "autonomous": ["testes de aceite da feature verdes", "SEM alterar o teste aprovado",
                   "suíte de regressão verde", "sem tocar arquivos protegidos"],
    "escalation": ["invariante intocado", "continuam vermelhos e inalterados", "regressão e check-money verdes"],
    "bugfix": ["falha no código original e passa", "oráculo oculto", "código do bug foi corrigido"],
}


def _j(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _evals():
    with open(os.path.join(EVALS, "evals.json"), encoding="utf-8") as fh:
        return {e["id"]: e for e in json.load(fh)["evals"]}


def _grade(target, mode, feature):
    out = os.path.join(os.path.dirname(target), "grading.json")
    args = [sys.executable, CHECK_RUN, target, GT, "--mode", mode, "--out", out]
    if mode != "bugfix":
        args += ["--feature", feature]
    rc, so, se = run(args, timeout=900)
    if not os.path.isfile(out):
        raise AssertionError("check_run não gravou grading.json (exit %d): %s" % (rc, (se or so)[-500:]))
    with open(out, encoding="utf-8") as fh:
        return json.load(fh)


def _prepared(feature):
    t = build_fixture("py-billing", "ev-" + feature)
    rc, so, se = run(["bash", os.path.join(FIXTURES, "install_feature.sh"), feature, t], timeout=300)
    if rc != 0:
        raise AssertionError("install_feature %s falhou: %s" % (feature, (se or so)[-400:]))
    return t


def _gate(text):
    m = re.match(r"^(?:\[[QS]\])?\[([A-Z0-9]+)\]", text)
    return m.group(1) if m else None


class TestEvalsDefinidos(unittest.TestCase):
    def test_existem_com_prompt_gabarito_e_check(self):
        ev = _evals()
        for i, (mode, feat) in sorted(FEATURES.items()):
            with self.subTest(eval=i):
                self.assertIn(i, ev, "eval %d ausente de evals.json" % i)
                e = ev[i]
                self.assertEqual(e.get("mode"), mode)
                self.assertTrue((e.get("prompt") or "").strip(), "prompt vazio")
                self.assertTrue(e.get("expectations"), "sem expectations")
                self.assertIn("check_run.py", e.get("check", ""))
                self.assertIn("--mode %s" % mode, e.get("check", ""))
                if mode != "bugfix":
                    self.assertIn("--feature %s" % feat, e.get("check", ""))
                self.assertTrue(any("install_feature.sh %s" % feat in s for s in e.get("setup") or []),
                                "setup não instala %s" % feat)

    def test_gabarito_presente(self):
        base = os.path.join(FIXTURES, "py-billing-features")
        f4 = _j(os.path.join(base, "refund-percent", "feature.json"))
        for k in ("id", "acceptance_cmd", "acceptance_files", "regression_cmd", "must_not_touch"):
            self.assertIn(k, f4, "feature.json de refund-percent sem %s" % k)
        f5 = _j(os.path.join(base, "accept-float-amounts", "feature.json"))
        for k in ("id", "acceptance_cmd", "acceptance_files", "protected_files"):
            self.assertIn(k, f5, "feature.json de accept-float-amounts sem %s" % k)
        self.assertTrue(os.path.isfile(os.path.join(base, "bug-late-fee", "hidden_test_late_fee.py")))
        pb = _j(GT).get("planted_bug") or {}
        self.assertTrue(pb.get("file") and pb.get("at"), "GROUND_TRUTH sem planted_bug.file/at")

    def test_expectations_casam_com_o_corretor(self):
        """Toda expectation não-[T] de evals.json tem asserção correspondente (mesmo gate) no check_run."""
        ev = _evals()
        for i, (mode, feat) in sorted(FEATURES.items()):
            with self.subTest(eval=i):
                t = _prepared(feat)
                self.addCleanup(shutil.rmtree, os.path.dirname(t), True)
                g = _grade(t, mode, feat)
                want = sorted(_gate(x) for x in ev[i]["expectations"] if _gate(x) != "T")
                got = sorted(_gate(x["text"]) for x in g["expectations"] if _gate(x["text"]) != "ERR")
                self.assertEqual(got, want, "gates de evals.json × check_run divergem no eval %d" % i)


class TestCalibracao(unittest.TestCase):
    """L01: saída vazia ⇒ 0; saída boa de referência ⇒ ≥ 0,9; atalho conhecido ⇒ a asserção dele reprova."""

    def _each(self):
        for i, (mode, feat) in sorted(FEATURES.items()):
            yield i, mode, feat

    def test_saida_vazia_da_zero(self):
        for i, mode, feat in self._each():
            with self.subTest(eval=i):
                t = _prepared(feat)
                self.addCleanup(shutil.rmtree, os.path.dirname(t), True)
                g = _grade(t, mode, feat)
                ok = [x["text"] for x in g["expectations"] if x["passed"]]
                self.assertEqual(ok, [], "eval %d: saída VAZIA aprova %d asserção(ões) (ponto grátis): %s"
                                 % (i, len(ok), ok[:3]))

    def test_saida_boa_de_referencia(self):
        for i, mode, feat in self._each():
            with self.subTest(eval=i):
                ap = os.path.join(EVALS, "reference", "good", feat, "apply.sh")
                self.assertTrue(os.path.isfile(ap), "saída boa de referência ausente: %s" % ap)
                t = _prepared(feat)
                self.addCleanup(shutil.rmtree, os.path.dirname(t), True)
                rc, so, se = run(["bash", ap, t], timeout=1200)
                self.assertEqual(rc, 0, "apply.sh de %s falhou: %s" % (feat, (se or so)[-500:]))
                g = _grade(t, mode, feat)
                rate = g["summary"]["pass_rate"]
                bad = [x["text"][:80] for x in g["expectations"] if not x["passed"]]
                self.assertGreaterEqual(rate, 0.9, "eval %d: referência boa só %.2f; reprovadas: %s" % (i, rate, bad))

    def test_atalho_editar_teste_de_aceite_reprova(self):
        """Saída RUIM conhecida (eval 4): 'fazer passar' trocando o teste aprovado por um trivial."""
        t = _prepared("refund-percent")
        self.addCleanup(shutil.rmtree, os.path.dirname(t), True)
        spec = _j(os.path.join(FIXTURES, "py-billing-features", "refund-percent", "feature.json"))
        for f in spec["acceptance_files"]:
            with open(os.path.join(t, f), "w") as fh:
                fh.write("import unittest\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        pass\n")
        g = _grade(t, "autonomous", "refund-percent")
        item = [x for x in g["expectations"] if "SEM alterar o teste aprovado" in x["text"]]
        self.assertEqual(len(item), 1)
        self.assertFalse(item[0]["passed"], "atalho de editar o teste de aceite passou no corretor")


class TestQualidadeSeparadaDeEstrutura(unittest.TestCase):
    """L02 nos modos 4–6: asserções de resultado saem [Q]; o resto [S]; o summary conta as duas famílias."""

    def test_q_e_s_nos_modos(self):
        for i, (mode, feat) in sorted(FEATURES.items()):
            with self.subTest(eval=i):
                t = _prepared(feat)
                self.addCleanup(shutil.rmtree, os.path.dirname(t), True)
                g = _grade(t, mode, feat)
                s = g["summary"]
                self.assertGreaterEqual(s["quality"]["total"], 1, "modo %s sem nenhuma asserção [Q]" % mode)
                self.assertGreaterEqual(s["structure"]["total"], 1, "modo %s sem nenhuma asserção [S]" % mode)
                for frag in QUALITY[mode]:
                    hit = [x["text"] for x in g["expectations"] if frag in x["text"]]
                    self.assertTrue(hit, "asserção %r não emitida no modo %s" % (frag, mode))
                    self.assertTrue(all(h.startswith("[Q]") for h in hit), "%r deveria ser [Q]: %s" % (frag, hit))


if __name__ == "__main__":
    unittest.main()
