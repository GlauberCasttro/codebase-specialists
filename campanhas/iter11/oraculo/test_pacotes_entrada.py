"""Oráculo campanha-iter11 — pacotes de entrada por comando + caminho único das respostas do exame.

Defeito de origem (iteração 4, ts-shop: 5 contornos manuais; docs/08 P1; defeitos-abertos.json5):
  o orquestrador ESCREVEU SCRIPTS para montar a entrada do spot-check, do núcleo (core) e dos juízes POR-QUÊ e
  para tirar a maioria dos 3 juízes (`.specialists/tmp/why-majority.sh`); e o exame tinha TRÊS caminhos de
  resposta (questions.json5 isolado `<out>/answers.json5`, questions.json5 canônico
  `.swarm/probes/exams/<a>.answers.json5` e o prompt `{tmp}/answers/<a>.guided.json5`).

CONTRATO DE NOMES (fixado por este oráculo; a frente de correção implementa exatamente isto):
  cs.py facts spotcheck pack --out <arq> [--n N] [--batch K/M]
      → JSON5 {kind: "spotcheck-pack", facts: [{id, text, evidence: ["arq:linha", ...]}], record_cmd}
        ids existem em .swarm/facts/index.json5; evidência aponta arquivo existente do alvo;
        lotes K/M são disjuntos e a união é o pacote sem --batch; --out dentro do alvo só em .swarm/tmp/.
  cs.py team core pack --out <arq>
      → {kind: "core-pack", limit: 40, current: [<texto das linhas atuais de team.json5 core>],
         candidates: [{text, facts: [ids]}] ⊇ toda linha camadas.s0_core dos agentes, apply_cmd ~ "team core set"}
  cs.py panel why pack <agente> --out <dir>
      → <dir>/pack.json5 {kind: "why-pack", agent, judges: 3,
                          items: [{probe, question, answer, evidence}]}  (= sondas `why` do agente no bank;
                          answer = a resposta do exame do agente)
  cs.py panel why tally <agente> --from <dir>
      → lê <dir>/j*.json5 = {juiz, veredictos: {<probe>: "PASS"|"FAIL"}}; exige ≥3 juízes e nº ímpar; recusa
        sonda fora do pacote e veredito fora de PASS/FAIL; grava a MAIORIA em .swarm/probes/panel/<agente>.json5
        (mesmo formato de `panel why`). Recusa = exit != 0 e painel intacto.
  Exame — UM caminho de respostas por agente:
      o `answer_file` de `<out>/questions.json5` (exame isolado) é o MESMO do pacote canônico
      `.swarm/probes/exams/<a>.questions.json5`; `probes check <a>` sem --answers lê esse caminho;
      `--answers` diferente dele é recusado; references/prompts.json5 não manda gravar em outro lugar.

Alvo de teste: cópia do alvo da iteração 4 do ts-shop (init COMPLETO, GO simulado) migrada com
`upgrade --apply --allow-outside` (L05: cópia própria; o histórico nunca é tocado).
"""
import os
import re
import shutil
import unittest

from _comum import ITER4, SKILL, STATE_DIR, cs, load5, upgraded_legacy

AGENT = "architect"


def _prepare():
    t, rc, out = upgraded_legacy("ts-shop")
    if rc != 0:
        raise AssertionError("pré-condição: upgrade do alvo ts-shop da iteração 4 falhou (exit %d):\n%s"
                             % (rc, out[-1500:]))
    return t


class TestComandosRegistrados(unittest.TestCase):
    """Os 4 subcomandos existem (sem alvo; barato)."""

    def _help(self, *args):
        rc, out, err = cs(os.getcwd(), *(list(args) + ["--help"]))
        return rc, out + err

    def test_facts_spotcheck_pack(self):
        rc, txt = self._help("facts", "spotcheck", "pack")
        self.assertEqual(rc, 0, "`cs.py facts spotcheck pack` não existe:\n" + txt[-400:])
        self.assertIn("--out", txt)

    def test_team_core_pack(self):
        rc, txt = self._help("team", "core", "pack")
        self.assertEqual(rc, 0, "`cs.py team core pack` não existe:\n" + txt[-400:])
        self.assertIn("--out", txt)

    def test_panel_why_pack(self):
        rc, txt = self._help("panel", "why", "pack")
        self.assertEqual(rc, 0, "`cs.py panel why pack` não existe:\n" + txt[-400:])
        self.assertIn("--out", txt)

    def test_panel_why_tally(self):
        rc, txt = self._help("panel", "why", "tally")
        self.assertEqual(rc, 0, "`cs.py panel why tally` não existe:\n" + txt[-400:])
        self.assertIn("--from", txt)


class TestPacotesNoAlvo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t = _prepare()
        cls.idx = load5(os.path.join(cls.t, STATE_DIR, "facts", "index.json5"))
        cls.team = load5(os.path.join(cls.t, STATE_DIR, "team.json5"))
        cls.bank = load5(os.path.join(cls.t, STATE_DIR, "probes", "bank.json5"))
        cls.tmp = os.path.join(cls.t, STATE_DIR, "tmp", "oraculo")
        os.makedirs(cls.tmp, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(os.path.dirname(cls.t), ignore_errors=True)

    # ---------------------------------------------------------------- spot-check
    def _spot(self, name, *extra):
        out = os.path.join(self.tmp, name)
        rc, so, se = cs(self.t, "facts", "spotcheck", "pack", "--out", out, *extra)
        self.assertEqual(rc, 0, "facts spotcheck pack falhou: " + (se or so)[-500:])
        self.assertTrue(os.path.isfile(out), "pacote não gravado em --out")
        return load5(out)

    def test_spotcheck_pack_conteudo(self):
        p = self._spot("spot.json5")
        self.assertEqual(p.get("kind"), "spotcheck-pack")
        facts = p.get("facts") or []
        self.assertGreaterEqual(len(facts), 5, "spot-check confere 5–10 fatos (SKILL.md scan.5)")
        for f in facts:
            self.assertIn(f.get("id"), self.idx, "fato %r não existe em facts/index.json5" % f.get("id"))
            self.assertTrue(f.get("text"), "fato %s sem texto a conferir" % f.get("id"))
            ev = f.get("evidence") or []
            self.assertTrue(ev, "fato %s sem evidência" % f.get("id"))
            for e in ev:
                m = re.match(r"^(.+):(\d+)$", e)
                self.assertTrue(m, "evidência %r não é arquivo:linha" % e)
                self.assertTrue(os.path.isfile(os.path.join(self.t, m.group(1))), "evidência %r inexistente" % e)
        self.assertIn("facts spotcheck record", p.get("record_cmd", ""))

    def test_spotcheck_lotes_disjuntos_e_completos(self):
        full = set(f["id"] for f in self._spot("spot-all.json5")["facts"])
        a = set(f["id"] for f in self._spot("spot-1.json5", "--batch", "1/2")["facts"])
        b = set(f["id"] for f in self._spot("spot-2.json5", "--batch", "2/2")["facts"])
        self.assertTrue(a and b, "lote vazio")
        self.assertFalse(a & b, "lotes se sobrepõem: %s" % sorted(a & b)[:5])
        self.assertEqual(a | b, full, "união dos lotes != pacote completo")

    def test_spotcheck_out_dentro_do_alvo_fora_de_tmp_recusado(self):
        bad = os.path.join(self.t, "spot.json5")
        rc, so, se = cs(self.t, "facts", "spotcheck", "pack", "--out", bad)
        self.assertNotEqual(rc, 0, "--out no produto deveria ser recusado (só .swarm/tmp/ ou fora do alvo)")
        self.assertFalse(os.path.exists(bad))

    # ---------------------------------------------------------------- core
    def test_core_pack(self):
        out = os.path.join(self.tmp, "core-pack.json5")
        rc, so, se = cs(self.t, "team", "core", "pack", "--out", out)
        self.assertEqual(rc, 0, "team core pack falhou: " + (se or so)[-500:])
        p = load5(out)
        self.assertEqual(p.get("kind"), "core-pack")
        self.assertEqual(p.get("limit"), 40)
        cur = [l["text"] for l in (self.team.get("core") or {}).get("lines") or []]
        self.assertEqual(p.get("current"), cur, "current != linhas atuais do core em team.json5")
        cand = p.get("candidates") or []
        texts = set(c.get("text") for c in cand)
        s0 = set(l["text"] for a in self.team["agents"] for l in (a.get("camadas") or {}).get("s0_core") or [])
        self.assertTrue(s0, "pré-condição: cartões com s0_core")
        self.assertFalse(s0 - texts, "linhas s0_core fora dos candidatos: %s" % sorted(s0 - texts)[:3])
        for c in cand:
            self.assertTrue(c.get("facts"), "candidata sem fatos: %r" % c.get("text"))
            for fid in c["facts"]:
                self.assertIn(fid, self.idx, "candidata cita fato inexistente %r" % fid)
        self.assertIn("team core set", p.get("apply_cmd", ""))

    # ---------------------------------------------------------------- juízes POR-QUÊ
    def _why_probes(self):
        return sorted(p["id"] for p in self.bank["probes"] if p["agent"] == AGENT and p["type"] == "why")

    def _why_pack(self, name):
        out = os.path.join(self.tmp, name)
        rc, so, se = cs(self.t, "panel", "why", "pack", AGENT, "--out", out)
        self.assertEqual(rc, 0, "panel why pack falhou: " + (se or so)[-500:])
        return out, load5(os.path.join(out, "pack.json5"))

    def test_why_pack(self):
        out, p = self._why_pack("why-pack")
        self.assertEqual(p.get("kind"), "why-pack")
        self.assertEqual(p.get("agent"), AGENT)
        self.assertEqual(p.get("judges"), 3)
        items = p.get("items") or []
        self.assertEqual(sorted(i.get("probe") for i in items), self._why_probes(),
                         "itens != sondas why do agente no bank")
        answers = {a["id"]: a for a in load5(os.path.join(self.t, STATE_DIR, "probes", "exams",
                                                          "%s.answers.json5" % AGENT))}
        for i in items:
            self.assertTrue(i.get("question"))
            self.assertEqual(i.get("answer"), answers[i["probe"]]["answer"],
                             "resposta no pacote != resposta do exame (%s)" % i["probe"])

    def _write_judges(self, out, votes):
        """votes: {probe: [v1, v2, v3...]} → j1.json5..jN.json5"""
        import json
        n = len(next(iter(votes.values())))
        for k in range(n):
            with open(os.path.join(out, "j%d.json5" % (k + 1)), "w") as fh:
                json.dump({"juiz": "j%d" % (k + 1), "veredictos": {p: v[k] for p, v in votes.items()}}, fh)

    def _panel(self):
        p = os.path.join(self.t, STATE_DIR, "probes", "panel", "%s.json5" % AGENT)
        return load5(p) if os.path.isfile(p) else {}

    def _panel_bytes(self):
        p = os.path.join(self.t, STATE_DIR, "probes", "panel", "%s.json5" % AGENT)
        if not os.path.isfile(p):
            return None
        with open(p, "rb") as fh:
            return fh.read()

    def test_tally_maioria(self):
        a, b = self._why_probes()[:2]
        out, _ = self._why_pack("why-tally")
        self._write_judges(out, {a: ["PASS", "PASS", "FAIL"], b: ["FAIL", "PASS", "FAIL"]})
        rc, so, se = cs(self.t, "panel", "why", "tally", AGENT, "--from", out)
        self.assertEqual(rc, 0, "tally falhou: " + (se or so)[-500:])
        panel = self._panel()
        self.assertEqual(panel[a]["verdict"], "PASS")
        self.assertEqual(panel[b]["verdict"], "FAIL")
        self._write_judges(out, {a: ["FAIL", "FAIL", "PASS"], b: ["PASS", "PASS", "PASS"]})
        rc, so, se = cs(self.t, "panel", "why", "tally", AGENT, "--from", out)
        self.assertEqual(rc, 0, "tally (2ª) falhou: " + (se or so)[-500:])
        panel = self._panel()
        self.assertEqual(panel[a]["verdict"], "FAIL")
        self.assertEqual(panel[b]["verdict"], "PASS")

    def _assert_refused(self, out):
        before = self._panel_bytes()
        rc, so, se = cs(self.t, "panel", "why", "tally", AGENT, "--from", out)
        self.assertNotEqual(rc, 0, "tally deveria recusar: " + (so + se)[-300:])
        self.assertEqual(self._panel_bytes(), before, "tally recusado alterou o painel")

    def test_tally_recusa_dois_juizes(self):
        a, b = self._why_probes()[:2]
        out, _ = self._why_pack("why-dois")
        self._write_judges(out, {a: ["PASS", "PASS"], b: ["PASS", "FAIL"]})
        self._assert_refused(out)

    def test_tally_recusa_sonda_fora_do_pacote(self):
        a, b = self._why_probes()[:2]
        out, _ = self._why_pack("why-fora")
        self._write_judges(out, {a: ["PASS"] * 3, b: ["PASS"] * 3, "P-inexistente-99": ["PASS"] * 3})
        self._assert_refused(out)

    def test_tally_recusa_veredito_invalido(self):
        a, b = self._why_probes()[:2]
        out, _ = self._why_pack("why-invalido")
        self._write_judges(out, {a: ["PASS", "TALVEZ", "PASS"], b: ["PASS"] * 3})
        self._assert_refused(out)


class TestCaminhoUnicoRespostas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t = _prepare()
        cls.out = os.path.join(cls.t, STATE_DIR, "tmp", "exam", AGENT)
        canon = os.path.join(cls.t, STATE_DIR, "probes", "exams", "%s.answers.json5" % AGENT)
        with open(canon, "rb") as fh:
            cls.saved_answers = fh.read()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(os.path.dirname(cls.t), ignore_errors=True)

    def _pack(self):
        rc, so, se = cs(self.t, "probes", "exam-pack", AGENT, "--out", self.out)
        self.assertEqual(rc, 0, "exam-pack falhou: " + (se or so)[-500:])
        return load5(os.path.join(self.out, "questions.json5"))

    def _abs(self, p):
        return os.path.realpath(p if os.path.isabs(p) else os.path.join(self.t, p))

    def test_questions_isolado_e_canonico_tem_o_mesmo_answer_file(self):
        iso = self._pack()
        canon = load5(os.path.join(self.t, STATE_DIR, "probes", "exams", "%s.questions.json5" % AGENT))
        self.assertEqual(self._abs(iso["answer_file"]), self._abs(canon["answer_file"]),
                         "dois answer_file para o mesmo exame: %r × %r" % (iso["answer_file"], canon["answer_file"]))

    def test_prompts_nao_mandam_gravar_em_outro_caminho(self):
        with open(os.path.join(SKILL, "references", "prompts.json5"), encoding="utf-8") as fh:
            txt = fh.read()
        self.assertNotRegex(txt, r"answers/\{agente\}\.guided|\.guided\.json5",
                            "prompts.json5 manda o examinado gravar em {tmp}/answers/<a>.guided.json5 "
                            "(3º caminho, conflita com answer_file do exam-pack)")

    def test_check_sem_answers_le_o_caminho_unico(self):
        iso = self._pack()
        canon = os.path.join(self.t, STATE_DIR, "probes", "exams", "%s.answers.json5" % AGENT)
        report = os.path.join(self.t, STATE_DIR, "probes", "reports", "%s.json5" % AGENT)
        for p in (canon, report):
            if os.path.exists(p):
                os.remove(p)
        af = self._abs(iso["answer_file"])
        os.makedirs(os.path.dirname(af), exist_ok=True)
        with open(af, "wb") as fh:
            fh.write(self.saved_answers)
        rc, so, se = cs(self.t, "probes", "check", AGENT)
        self.assertIn(rc, (0, 1), "probes check sem --answers não achou as respostas no caminho único:\n"
                      + (se or so)[-600:])
        self.assertTrue(os.path.isfile(report), "report do agente não foi gravado (respostas não lidas)")

    def test_check_com_answers_divergente_recusado(self):
        iso = self._pack()
        other = os.path.join(self.t, STATE_DIR, "tmp", "outro-lugar", "answers.json5")
        os.makedirs(os.path.dirname(other), exist_ok=True)
        with open(other, "wb") as fh:
            fh.write(self.saved_answers)
        rc, so, se = cs(self.t, "probes", "check", AGENT, "--answers", other)
        self.assertNotEqual(rc, 0, "--answers fora do caminho único foi aceito (cópia silenciosa)")
        self.assertIn(os.path.basename(iso["answer_file"]), so + se, "a recusa deve citar o caminho único")


if __name__ == "__main__":
    unittest.main()
