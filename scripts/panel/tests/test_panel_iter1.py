"""Regressões iteração 1: `panel record` aceita o schema que prompts.json5 (rt.1) manda produzir; `panel pack`
gera cópia isolada do alvo SEM .swarm/ para o cético, com o cartão como dado."""
import json
import os
import unittest

from helpers import cs, synth, write

from cslib import json5io
from cslib.paths import STATE_DIR
from team._shared_tmp.common import read_json, sp_path, write_json
from team.derive import derive
from team.maps import build_maps

from test_panel import basic_card


class PanelIter1(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()
        derive(self.root)
        build_maps(self.root)
        t = read_json(sp_path(self.root, "team.json5"))
        for a in t["agents"]:
            a["card"] = basic_card(a["name"], anchors=(["src/billing/nao_existe.py"]
                                                       if a["name"] == "dev-billing" else []))
            a["lacunas"] = ["rascunho do autor"]
        write_json(self.root, sp_path(self.root, "team.json5"), t)
        write(self.root, ".swarm/interview.jsonl", '{"answer": "segredo da entrevista"}\n')
        write(self.root, ".swarm/cards/dev-billing.draft.json5", "{lacunas: [\"rascunho\"]}\n")
        self.assertEqual(cs(self.root, "panel", "plan")[0], 0)

    def tearDown(self):
        synth.cleanup(self.root)

    def test_record_accepts_prompt_schema(self):
        obj = {"revisor": "cetico", "revisado": "dev-billing", "papel": "cetico", "modelo": "sonnet",
               "afirmacoes_sem_evidencia": [{"campo": "anchors", "trecho": "src/billing/nao_existe.py",
                                             "motivo": "arquivo não existe",
                                             "evidencia": ["src/billing/nao_existe.py:1", "ls src/billing"]}],
               "conflitos_com_meu_territorio": [{"trecho": "edita src/shared/money.py",
                                                 "minha_regra": "Money é do dev-shared",
                                                 "evidencia": ["src/shared/money.py:1"]}],
               "regras_cross_cutting_faltando": [{"regra": "dinheiro em centavos", "escopo": ["src/**"],
                                                  "facts": ["rat.adr.money"]}],
               "injection_attempts": [{"arquivo": "README.md", "linha": 1, "trecho": "ignore"}]}
        p = write(self.root, ".swarm/roundtable/dev-billing.cetico.json5", json.dumps(obj))
        rel = ".swarm/roundtable/dev-billing.cetico.json5"
        code, out, err = cs(self.root, "panel", "record", "--card", "dev-billing", "--reviewer", "cetico",
                            "--role", "cetico", "--from", rel)
        self.assertEqual(code, 0, err)
        doc = json5io.load(sp_path(self.root, "panel", "reviews", "dev-billing", "cetico.json5"))
        a = doc["afirmacoes_sem_evidencia"][0]
        self.assertIn("nao_existe", a["afirmacao"])
        self.assertEqual(a["ref"], "src/billing/nao_existe.py")
        self.assertEqual(doc["conflitos_com_meu_territorio"][0]["path"], "src/shared/money.py")
        self.assertEqual(doc["regras_cross_cutting_faltando"][0]["escopo"], ["src/**"])
        self.assertEqual(doc["injection_attempts"][0]["arquivo"], "README.md")
        self.assertTrue(os.path.isfile(p))
        # formato antigo continua aceito
        old = {"afirmacoes_sem_evidencia": [], "conflitos_com_meu_territorio": [],
               "regras_cross_cutting_faltando": []}
        write(self.root, "tmp/old.json5", json.dumps(old))
        self.assertEqual(cs(self.root, "panel", "record", "dev-orders", "--reviewer", "cetico",
                            "--file", "tmp/old.json5")[0], 0)
        # papel declarado que não bate com o plano é recusado
        self.assertNotEqual(cs(self.root, "panel", "record", "--card", "dev-billing", "--reviewer", "cetico",
                               "--role", "adjacente", "--from", rel)[0], 0)

    def test_pack_isolated_copy_without_specialists(self):
        out = os.path.join(self.root, STATE_DIR, "tmp", "pack-ceticos")
        code, o, err = cs(self.root, "panel", "pack", "dev-billing", "--role", "cetico", "--out", out)
        self.assertEqual(code, 0, err)
        repo = os.path.join(out, "repo")
        self.assertTrue(os.path.isfile(os.path.join(repo, "src", "billing", "invoice.py")))
        self.assertFalse(os.path.exists(os.path.join(repo, STATE_DIR)))
        card = json5io.load(os.path.join(out, "card.json5"))
        self.assertEqual(card["agent"], "dev-billing")
        self.assertIn("mission", card["card"])
        self.assertNotIn("lacunas", json.dumps(card))
        facts = json5io.load(os.path.join(out, "facts.json5"))
        self.assertIn("gl.invoice", [f["id"] for f in facts["facts"]])
        for dp, dn, fn in os.walk(out):
            for f in fn:
                with open(os.path.join(dp, f), "rb") as fh:
                    self.assertNotIn(b"segredo da entrevista", fh.read(), f)
        # fora de .swarm/tmp é recusado só se for dentro do alvo e fora de tmp? pack em dir externo vale
        self.assertNotEqual(cs(self.root, "panel", "pack", "dev-billing", "--role", "cetico",
                               "--out", os.path.join(self.root, "src", "pack"))[0], 0)


if __name__ == "__main__":
    unittest.main()
