"""Iteração 3 (P0) — refino só do agente reprovado, ciclo nunca registrado com respostas velhas, exame
guiado isolado (`probes exam-pack <a> --out <dir>`), veredito de juiz nunca herdado por id repetido."""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "team", "tests"))
sys.path.insert(0, HERE)
import synth  # noqa: E402

from team._shared_tmp.common import read_json, sp_path, write_json  # noqa: E402
from team.derive import derive  # noqa: E402
from probes.exam import baseline_filter  # noqa: E402
from probes.generate import generate, load_bank  # noqa: E402
from test_probes import perfect  # noqa: E402
from test_final import cs  # noqa: E402

BAD = "dev-billing"


class Refine(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()
        derive(self.root)
        self.bank = generate(self.root, seed="s1")
        self.agents = sorted(self.bank["agents"])
        for a in self.agents:
            self.baseline(a)
            self.answer(a, good=(a != BAD))

    def tearDown(self):
        synth.cleanup(self.root)

    def baseline(self, a):
        write_json(self.root, sp_path(self.root, "probes", "exams", "%s.baseline.json5" % a), [{"id": x["id"], "answer": "não sei"} for x in load_bank(self.root)["probes"] if x["agent"] == a])
        baseline_filter(self.root, a)

    def answer(self, a, good=True):
        bank = load_bank(self.root)
        ps = [p for p in bank["probes"] if p["agent"] == a]
        items = [perfect(p) for p in ps] if good else \
            [{"id": p["id"], "answer": "não sei", "evidence": ["grep -rn x src"]} for p in ps]
        write_json(self.root, sp_path(self.root, "probes", "exams", "%s.answers.json5" % a), items)

    def cycles(self):
        return read_json(sp_path(self.root, "probes", "cycles.json5"))

    def probes_of(self, a):
        return [p for p in load_bank(self.root)["probes"] if p["agent"] == a]

    def test_rotate_touches_only_the_agent(self):
        others_before = {a: self.probes_of(a) for a in self.agents if a != BAD}
        old_q = set(p["question"] for p in self.probes_of(BAD))
        code, out, err = cs(self.root, "probes", "generate", "--rotate", "--agent", BAD)
        self.assertEqual(code, 0, out + err)
        for a, ps in others_before.items():
            self.assertEqual(self.probes_of(a), ps, a)
        new = self.probes_of(BAD)
        self.assertTrue(new and all(p["id"].startswith("P-%s-r1-" % BAD) for p in new))
        self.assertFalse(old_q & set(p["question"] for p in new), "sondas do refino têm de ser NOVAS")
        bank = load_bank(self.root)
        self.assertNotIn(BAD, bank["baseline"])
        self.assertTrue(all(a in bank["baseline"] for a in others_before))
        # --rotate sem --agent é recusado (rotação é por agente)
        self.assertEqual(cs(self.root, "probes", "generate", "--rotate")[0], 2)

    def test_check_all_after_rotation_rescoring_only_the_refined_agent(self):
        self.assertEqual(cs(self.root, "probes", "check", "--all")[0], 1)
        c1 = self.cycles()
        self.assertEqual(len(c1[BAD]), 1)
        cs(self.root, "probes", "generate", "--rotate", "--agent", BAD)
        # iteração 2: check --all ANTES do reexame registrava ciclo com respostas velhas e esgotava o agente
        code, out, err = cs(self.root, "probes", "check", "--all")
        self.assertEqual(code, 1)
        self.assertIn("respostas velhas", out)
        c2 = self.cycles()
        self.assertEqual({a: len(v) for a, v in c2.items()}, {a: len(v) for a, v in c1.items()},
                         "nenhum ciclo novo com respostas velhas")
        self.assertEqual(c2[BAD], c1[BAD])
        time.sleep(0.01)
        self.baseline(BAD)
        self.answer(BAD, good=True)
        code, out, err = cs(self.root, "probes", "check", "--all", "--final")
        self.assertEqual(code, 0, out + err)
        c3 = self.cycles()
        self.assertEqual(len(c3[BAD]), 2)
        for a in self.agents:
            if a != BAD:
                self.assertEqual(len(c3[a]), 1, a)

    def test_full_regeneration_keeps_previous_pass_and_refuses_stale(self):
        cs(self.root, "probes", "check", "--all")
        generate(self.root, seed="s2")  # o caminho errado da iteração 2: banco inteiro novo
        code, out, err = cs(self.root, "probes", "check", "--all")
        cyc = self.cycles()
        for a in self.agents:
            self.assertEqual(len(cyc[a]), 1, "%s: ciclo novo com respostas velhas" % a)
        self.assertIn("não repontuado", out)
        self.assertIn("respostas velhas", out)
        # check de um agente só também recusa respostas velhas (exit 1, nada registrado)
        code, _, err = cs(self.root, "probes", "check", BAD)
        self.assertEqual(code, 1)
        self.assertIn("respostas velhas", err)

    def test_examined_check_of_validate3(self):
        # painel POR-QUÊ pendente: o `check --all` antigo passava com PASS provisório; validate.3 não fecha
        code, _, err = cs(self.root, "probes", "check", "--all", "--examined")
        self.assertEqual(code, 1)
        self.assertIn("painel POR-QUÊ pendente", err)
        from panel.core import why_verdict
        for p in load_bank(self.root)["probes"]:
            if p.get("panel"):
                why_verdict(self.root, p["agent"], p["id"], "PASS")
        # todos examinados (dev-billing reprovado) → validate.3 fecha; o reprovado vai ao refino (validate.4)
        code, o, err = cs(self.root, "probes", "check", "--all", "--examined")
        self.assertEqual(code, 0, o + err)
        self.assertEqual(cs(self.root, "probes", "check", "--all", "--final")[0], 1)
        os.remove(sp_path(self.root, "probes", "exams", "%s.answers.json5" % BAD))
        code, _, err = cs(self.root, "probes", "check", "--all", "--examined")
        self.assertEqual(code, 1)
        self.assertIn("não examinado", err)

    def test_judge_verdict_not_inherited_after_rotation(self):
        why = [p for p in self.probes_of(BAD) if p.get("panel")]
        if not why:
            self.skipTest("sem sonda POR-QUÊ no território sintético")
        pid = why[0]["id"]
        self.assertIn("gabarito_fonte", why[0])
        self.assertIn("source", why[0]["answer"])
        self.assertEqual(cs(self.root, "panel", "why", BAD, "--probe", pid, "--verdict", "PASS")[0], 0)
        cs(self.root, "probes", "generate", "--rotate", "--agent", BAD)
        panel = read_json(sp_path(self.root, "probes", "panel", "%s.json5" % BAD))
        self.assertNotIn(pid, panel)


    def test_judge_verdict_keyed_by_probe_identity(self):
        # banco inteiro regenerado reusa ids P-<a>-NN com perguntas novas: o veredito velho não vale
        from probes.exam import panel_verdict
        why = [p for p in load_bank(self.root)["probes"] if p.get("panel")]
        if not why:
            self.skipTest("sem sonda POR-QUÊ")
        p = why[0]
        from panel.core import why_verdict
        why_verdict(self.root, p["agent"], p["id"], "FAIL")
        entry = read_json(sp_path(self.root, "probes", "panel", "%s.json5" % p["agent"]))[p["id"]]
        self.assertEqual(panel_verdict(entry, p), "FAIL")
        other = dict(p, question=p["question"] + " (outra)")
        self.assertIsNone(panel_verdict(entry, other))


class ExamIsolated(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()
        derive(self.root)
        generate(self.root)
        self.out = tempfile.mkdtemp(prefix="cs-exam-")
        shutil.rmtree(self.out)

    def tearDown(self):
        synth.cleanup(self.root)
        shutil.rmtree(self.out, ignore_errors=True)

    def test_out_inside_target_refused(self):
        # iteração 4: dentro de <alvo>/.swarm/tmp/ é aceito (excluído da cópia); no resto do alvo, recusado
        code, _, err = cs(self.root, "probes", "exam-pack", BAD, "--out", os.path.join(self.root, "exam"))
        self.assertEqual(code, 2)
        self.assertIn("gabarito", err)
        code, _, err = cs(self.root, "probes", "exam-pack", BAD, "--out",
                          os.path.join(self.root, ".swarm", "tmp", "exam", BAD))
        self.assertEqual(code, 0, err)

    def test_isolated_copy_without_answer_key(self):
        code, out, err = cs(self.root, "probes", "exam-pack", BAD, "--out", self.out)
        self.assertEqual(code, 0, err)
        qpath = out.strip().splitlines()[-1]
        self.assertEqual(qpath, os.path.join(os.path.realpath(self.out), "questions.json5"))
        repo = os.path.join(self.out, "repo")
        self.assertTrue(os.path.isfile(os.path.join(repo, "src", "billing", "invoice.py")))
        for dp, dn, fn in os.walk(self.out):
            self.assertNotIn(".swarm", dn)
            for f in fn:
                with open(os.path.join(dp, f), "rb") as fh:
                    self.assertNotIn(b"bank.json5", fh.read() if f.endswith(".json5") else b"")
        q = read_json(qpath)
        self.assertTrue(q["questions"])
        self.assertFalse(any("answer" in x for x in q["questions"]))
        # respostas gravadas no diretório do exame chegam ao `check --all` (cópia canônica)
        bank = load_bank(self.root)
        items = [perfect(p) for p in bank["probes"] if p["agent"] == BAD]
        with open(os.path.join(self.out, "answers.json5"), "w") as fh:
            import json
            fh.write(json.dumps(items))
        write_json(self.root, sp_path(self.root, "probes", "exams", "%s.baseline.json5" % BAD), [{"id": x["id"], "answer": "não sei"} for x in load_bank(self.root)["probes"] if x["agent"] == BAD])
        baseline_filter(self.root, BAD)
        code, o, e = cs(self.root, "probes", "check", BAD, "--answers", os.path.join(self.out, "answers.json5"))
        self.assertEqual(code, 0, o + e)
        self.assertTrue(os.path.isfile(sp_path(self.root, "probes", "exams", "%s.answers.json5" % BAD)))


if __name__ == "__main__":
    unittest.main()
