"""Iteração 4 (frente team/emit/harness) — regressões dos defeitos medidos na rodada 3:

1. `team facts` não entregava instrução do time de escopo `**` (docs.instr.*) a NENHUM agente, e o gate
   `security` recebia só gap.* (0 invariantes, 0 ADR, 0 comandos) — cartão de security saía vazio;
2. revisão/refino gravava cartão com referência inexistente ou comando sem [unverified] (G2 vermelho sem saída:
   depois do reexame aprovado a CLI travava a revisão);
3. `team approve` sem `--simulated`;
4. `team core from-panel` deixava 3 versões da mesma regra (fatos superconjunto / acento);
5. `team card-status` acusava "cartão mudou depois da revisão" quando a revisão mais recente era a da mesa
   redonda re-consolidada (comparava com refines[-1])."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import synth  # noqa: E402
from test_roster_core import card, cs, team_of  # noqa: E402

from team._shared_tmp.common import read_json, sp_path, write_json  # noqa: E402
from team.derive import derive  # noqa: E402

INSTR = {"id": "docs.instr.claude.md.3", "layer": "project_docs", "scope": ["**"], "confidence": "high",
         "origin": "mechanical", "fingerprint": "x", "evidence": [{"file": "README.md", "line": 1}],
         "claim": "Instrução de agente preexistente (CLAUDE.md:3): não faça deploy na sexta",
         "data": {"kind": "agent_instruction"}}
NEVER = {"id": "rules.never.python.eval", "layer": "rules", "scope": ["src/**"], "confidence": "high",
         "origin": "mechanical", "fingerprint": "x", "evidence": [{"cmd": "grep -rn eval( src", "exit": 1}],
         "claim": "Invariante: eval() tem 0 ocorrências em 14 arquivos python de produto (não introduzir)",
         "data": {"kind": "negative", "pattern": "eval(", "count": 0}}


def add_facts(root):
    """Camada project_docs (L10) + um invariante negativo SEM palavra de segurança no texto (eval())."""
    fd = sp_path(root, "facts")
    with open(os.path.join(fd, "project_docs.json5"), "w") as fh:
        fh.write("// L10 sintético\n" + json.dumps({"facts": [INSTR]}))
    rules = read_json(os.path.join(fd, "rules.json5"))
    rules["facts"].append(NEVER)
    write_json(root, os.path.join(fd, "rules.json5"), rules)
    idx = read_json(os.path.join(fd, "index.json5"))
    idx["facts"] = sorted(set(idx["facts"]) | {INSTR["id"], NEVER["id"]})
    write_json(root, os.path.join(fd, "index.json5"), idx)


class Base(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()
        add_facts(self.root)
        derive(self.root)

    def tearDown(self):
        synth.cleanup(self.root)

    def put(self, rel, obj):
        full = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as fh:
            fh.write("// teste\n" + json.dumps(obj))
        return rel

    def pack(self, name):
        rel = ".swarm/tmp/facts/%s.json5" % name
        code, o, e = cs(self.root, "team", "facts", name, "--out", rel)
        self.assertEqual(code, 0, o + e)
        return read_json(os.path.join(self.root, rel))


class FactsPack(Base):
    def test_every_agent_receives_team_instructions(self):
        for name in sorted(team_of(self.root)):
            ids = [f["id"] for f in self.pack(name)["facts"]]
            self.assertIn(INSTR["id"], ids, "%s sem a instrução do time (escopo **)" % name)

    def test_gates_receive_never_rules_adr_and_ops(self):
        for name in ("security", "reviewer"):
            doc = self.pack(name)
            ids = [f["id"] for f in doc["facts"]]
            self.assertFalse(all(i.startswith("gap.") for i in ids), "%s só com gap.*: %s" % (name, ids))
            for want in (NEVER["id"], "rat.adr.money", "ops.test.unittest", INSTR["id"]):
                self.assertIn(want, ids, "%s sem %s" % (name, want))
        # o invariante negativo (eval) é invariante do gate de segurança (regra 8), não só contexto
        self.assertIn(NEVER["id"], team_of(self.root)["security"]["invariants"])
        self.assertEqual(cs(self.root, "team", "validate", "--stage", "derive")[0], 0)

    def test_po_and_architect_receive_ops_and_rationale(self):
        for name in ("po", "architect"):
            if name not in team_of(self.root):
                continue
            ids = [f["id"] for f in self.pack(name)["facts"]]
            for want in ("ops.test.unittest", "ops.lint.ruff", "rat.adr.money"):
                self.assertIn(want, ids, "%s sem %s" % (name, want))


class ApproveSimulated(Base):
    def test_team_approve_simulated(self):
        code, o, e = cs(self.root, "team", "approve", "--by", "eval-sim", "--simulated")
        self.assertEqual(code, 0, o + e)
        self.assertIn("simulad", o)
        with open(sp_path(self.root, "team-approvals.jsonl")) as fh:
            rec = json.loads(fh.read().splitlines()[-1])
        self.assertEqual(rec["approval"], "simulated")
        self.assertEqual(cs(self.root, "team", "approved")[0], 0)


class ReviseExistence(Base):
    def setUp(self):
        Base.setUp(self)
        self.put(".swarm/tmp/c.json5", card("dev-billing"))
        self.assertEqual(cs(self.root, "team", "card", "set", "dev-billing", "--file", ".swarm/tmp/c.json5")[0], 0)
        write_json(self.root, sp_path(self.root, "panel", "dev-billing.json5"), {"agent": "dev-billing"})

    def test_revise_refuses_missing_reference_and_unverified_command(self):
        bad = card("dev-billing")
        bad["anchors"] = ["src/billing/nao_existe.py"]
        self.put(".swarm/tmp/bad.json5", bad)
        code, o, e = cs(self.root, "team", "card", "revise", "dev-billing", "--file", ".swarm/tmp/bad.json5",
                        "--note", "rt.4")
        self.assertEqual(code, 2, o + e)
        self.assertIn("nao_existe.py", e)
        cmd = card("dev-billing")
        cmd["rules"] = [{"text": "rode `make deploy-agora` antes do PR", "facts": ["rat.adr.money"]}]
        self.put(".swarm/tmp/cmd.json5", cmd)
        code, o, e = cs(self.root, "team", "card", "revise", "dev-billing", "--file", ".swarm/tmp/cmd.json5",
                        "--note", "rt.4")
        self.assertEqual(code, 2, o + e)
        self.assertIn("deploy-agora", e)
        # nada gravado: a revisão única continua disponível para o cartão correto
        self.assertNotIn("revised", read_json(sp_path(self.root, "cards", "status.json5"))["dev-billing"])
        self.assertEqual(cs(self.root, "team", "card", "revise", "dev-billing", "--note", "rt.4 ok")[0], 0)

    def test_existence_fix_allowed_after_reexam_passed(self):
        self.assertEqual(cs(self.root, "team", "card", "revise", "dev-billing", "--note", "rt.4 ok")[0], 0)
        write_json(self.root, sp_path(self.root, "probes", "cycles.json5"),
                   {"dev-billing": [{"decision": "FAIL"}, {"decision": "PASS"}]})
        r1 = card("dev-billing")
        r1["mission"] = "refinado"
        self.put(".swarm/tmp/r1.json5", r1)
        self.assertEqual(cs(self.root, "team", "card", "revise", "dev-billing", "--file", ".swarm/tmp/r1.json5",
                            "--note", "validate.4 ciclo 1")[0], 0)
        # iteração 3 (py-billing qa): o cartão do refino chegou com um comando sem [unverified] (versão antiga da
        # CLI não conferia) e, com o reexame aprovado, `card revise` travava → G2 sem saída
        from team.cards import _sha, load_status, save_status
        t = read_json(sp_path(self.root, "team.json5"))
        ag = [a for a in t["agents"] if a["name"] == "dev-billing"][0]
        ag["card"]["rules"] = [{"text": "rode `git log --grep fix` antes", "facts": ["rat.adr.money"]},
                               {"text": "rode `make deploy-agora` antes do PR", "facts": ["rat.adr.money"]}]
        write_json(self.root, sp_path(self.root, "team.json5"), t)
        st = load_status(self.root)
        st["dev-billing"]["refines"][-1]["sha256"] = _sha(ag["card"])
        save_status(self.root, st)
        from team.cards import card_status
        row = [r for r in card_status(self.root) if r["agent"] == "dev-billing"][0]
        self.assertTrue(any("inexistente" in p for p in row["problems_revised"]), row)
        # revisão sem conserto continua recusada
        self.assertEqual(cs(self.root, "team", "card", "revise", "dev-billing", "--note", "de novo")[0], 2)
        fixed = dict(ag["card"])
        fixed["rules"] = [{"text": "rode `git log --grep fix` antes", "facts": ["rat.adr.money"]},
                          {"text": "rode a suíte `python3 -m unittest discover -s tests` antes do PR",
                           "facts": ["rat.adr.money"]}]
        self.put(".swarm/tmp/fix.json5", fixed)
        code, o, e = cs(self.root, "team", "card", "revise", "dev-billing", "--file", ".swarm/tmp/fix.json5",
                        "--note", "só existência")
        self.assertEqual(code, 0, o + e)
        row = [r for r in card_status(self.root) if r["agent"] == "dev-billing"][0]
        self.assertEqual(row["problems_revised"], [])
        # sem falta de existência, a válvula fecha de novo
        self.assertEqual(cs(self.root, "team", "card", "revise", "dev-billing", "--file", ".swarm/tmp/fix.json5",
                            "--note", "outra")[0], 2)


class CardStatusLatest(Base):
    def test_latest_revision_wins(self):
        self.put(".swarm/tmp/c.json5", card("dev-billing"))
        cs(self.root, "team", "card", "set", "dev-billing", "--file", ".swarm/tmp/c.json5")
        write_json(self.root, sp_path(self.root, "panel", "dev-billing.json5"), {"agent": "dev-billing"})
        self.assertEqual(cs(self.root, "team", "card", "revise", "dev-billing", "--note", "rt.4")[0], 0)
        write_json(self.root, sp_path(self.root, "probes", "cycles.json5"), {"dev-billing": [{"decision": "FAIL"}]})
        r1 = card("dev-billing")
        r1["mission"] = "refino 1"
        self.put(".swarm/tmp/r1.json5", r1)
        self.assertEqual(cs(self.root, "team", "card", "revise", "dev-billing", "--file", ".swarm/tmp/r1.json5",
                            "--note", "refino")[0], 0)
        # painel re-consolidado → nova revisão de mesa redonda (mais recente que o refino)
        write_json(self.root, sp_path(self.root, "panel", "dev-billing.json5"), {"agent": "dev-billing", "v": 2})
        r2 = card("dev-billing")
        r2["mission"] = "mesa redonda 2"
        self.put(".swarm/tmp/r2.json5", r2)
        code, o, e = cs(self.root, "team", "card", "revise", "dev-billing", "--file", ".swarm/tmp/r2.json5",
                        "--note", "rt.4 de novo")
        self.assertEqual(code, 0, o + e)
        from team.cards import card_status
        row = [r for r in card_status(self.root) if r["agent"] == "dev-billing"][0]
        self.assertEqual(row["problems_revised"], [], row)


class CoreDedup(Base):
    def set_s0(self, by_agent):
        t = read_json(sp_path(self.root, "team.json5"))
        for a in t["agents"]:
            if a["name"] in by_agent:
                a["camadas"] = {"s0_core": by_agent[a["name"]]}
        write_json(self.root, sp_path(self.root, "team.json5"), t)

    def core(self):
        return read_json(sp_path(self.root, "team.json5"))["core"]["lines"]

    def test_same_rule_three_versions(self):
        # iteração 3 (go-polyglot): "migração aplicada nunca é editada" em 3 redações → 3 linhas no core
        self.set_s0({
            "dev-billing": [{"text": "Migração aplicada nunca é editada: crie migração nova",
                             "facts": ["rat.adr.money"]}],
            "dev-orders": [{"text": "Nunca edite uma migração já aplicada — mudança vira migração nova (ADR)",
                            "facts": ["rat.adr.money", "hist.fix.abc1234"]}],
            "dev-catalog": [{"text": "Não edite migração.", "facts": ["br.refund.window"]}],
            "qa": [{"text": "Nao edite migracao", "facts": ["gl.invoice"]}]})
        code, o, e = cs(self.root, "team", "core", "from-panel")
        self.assertEqual(code, 0, o + e)
        texts = [l["text"] for l in self.core()]
        self.assertEqual(len(texts), 2, texts)


if __name__ == "__main__":
    unittest.main()
