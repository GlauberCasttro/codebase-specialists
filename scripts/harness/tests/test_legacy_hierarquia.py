"""ORÁCULO D-1-04 — incoerência de HIERARQUIA deixada pelo motor antigo não tem saída (repositório-piloto projeto-legado).

O motor antigo (atalho D-0-09, já fechado para o futuro) deixou story US-3 IN_PROGRESS com a feature FEAT-2 em BACKLOG
e o épico EPIC-2 PROPOSED. O motor novo, em `validate --strict`, acusa "story US-3 IN_PROGRESS com feature FEAT-2 em
BACKLOG (feature.start contornada)" e não há saída: `legacy-ack` só reconhece transição ilegal / ACCEPTED sem gate;
épico/feature não têm amend; `feature ready` exige teste de aceite vermelho (o código já existe).

Contrato (comportamento observável: CLI real engine/state.py em subprocesso + guard real; sem mock):
  1. LEGADO-RECONHECIDO: depois de `cs-state legacy-ack --reason ...` (humano), `validate --strict` passa e uma task
     da US-3 é despachada (hook pre-agent), submetida, verificada, revisada e aceita normalmente.
  2. NOVA-INCOERÊNCIA-CONTINUA-ACUSADA: incoerência de hierarquia criada DEPOIS do ack (outra story na mesma feature,
     ou feature IN_PROGRESS com épico não ACTIVE) volta a reprovar `validate --strict`.
  3. ACK-É-HUMANO: o guard continua bloqueando `cs-state legacy-ack` vindo de agente (regressão; passa hoje).
  4. ACK-LISTA-O-QUE-RECONHECEU: o evento harness.legacy_ack lista EXATAMENTE as incoerências de hierarquia
     reconhecidas (ids e estados), em `data.args.hierarchy`, além de reason/transitions/accepted que já lista hoje.

Simulação do legado: como test_atalho_guarda.TestValidateHierarquia — um evento `story.start` gravado pela cadeia
(engine.commit) com a op direta de estado, sem passar pela promoção do pai. A transição READY→IN_PROGRESS da story é
legal na máquina (o replay passa); o que sobra é exatamente a incoerência pai×filho que o motor antigo deixava.

Escolhas onde o contrato não fixa detalhe:
  * Formato de `data.args.hierarchy`: lista com um item por incoerência; o item é livre (dict ou string), mas os
    valores textuais dele têm de conter o id do filho, o estado do filho, o id do pai e o estado do pai.
  * Depois do ack, o estado final da FEAT-2 não é fixado (o motor pode deixar BACKLOG); só se exige que o trabalho
    da US-3 flua e que `validate --strict` siga verde.
"""
import json
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import fixture  # noqa: E402
from fixture import A  # noqa: E402
import cmds  # noqa: E402
import engine  # noqa: E402
import hcore  # noqa: E402
from engine import Event, ref  # noqa: E402
from test_faixas_aceite import (AC, VERIFY, agent_payload, bash_payload, board, cs, hook, latest_deleg,  # noqa: E402
                                advance_to_executing, dispatch_via_hook)

MSG_US3 = "story US-3 IN_PROGRESS com feature FEAT-2 em BACKLOG (feature.start contornada)"


def events(root):
    evs, _, _ = hcore.read_chain(hcore.state_paths(root)["events"])
    return evs


def old_motor_start(root, kind, eid):
    """O que o motor antigo gravava: transição do filho por op direta, sem promover (nem checar) o pai."""
    engine.commit(root, A, lambda ctx: [Event("%s.start" % kind, eid, [["set", ref(kind, eid), "state", "IN_PROGRESS"]])])


def _story(root, feature):
    cmds.add_story(root, A, "us", feature, "Como cliente quero algo", as_a="cliente", i_want="algo",
                   so_that="ganhar", criteria=[{"id": "AC-1", "gherkin": "Dado pedido Quando aplico Então desconta",
                                                "test": "tests.test_billing"}])


def legacy_board(root):
    """Board da cobaia: EPIC-1 ACTIVE/FEAT-1 READY/US-1 READY (fluxo canônico, sessão em PLANNING) +
    EPIC-2 PROPOSED, FEAT-2 BACKLOG, US-2 e US-3 READY na FEAT-2; US-3 posta IN_PROGRESS pelo atalho antigo."""
    fixture.process(root, "pequena")
    cmds.add_epic(root, A, "Orquestração", "orquestrar", "throughput")                      # EPIC-2 (PROPOSED)
    cmds.add_feature(root, A, "EPIC-2", "Legado", "spec/feat.md", ["python3 -m unittest accept.test_accept"],
                     ["accept/test_accept.py"])                                            # FEAT-2 (BACKLOG)
    _story(root, "FEAT-2")                                                                 # US-2
    _story(root, "FEAT-2")                                                                 # US-3
    cmds.level_transition(root, A, "story", "US-2", "ready")
    cmds.level_transition(root, A, "story", "US-3", "ready")
    old_motor_start(root, "story", "US-3")
    b = hcore.load_board(root)
    assert (hcore.find(b, "epic", "EPIC-2")["state"], hcore.find(b, "feature", "FEAT-2")["state"],
            hcore.find(b, "story", "US-3")["state"]) == ("PROPOSED", "BACKLOG", "IN_PROGRESS")


def flat_strings(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            for x in flat_strings(v):
                yield x
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            for x in flat_strings(v):
                yield x
    elif isinstance(obj, str):
        yield obj


def mentions(item, *needles):
    blob = " ".join(flat_strings(item)) if not isinstance(item, str) else item
    return all(n in blob for n in needles)


class Base(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo()
        legacy_board(self.root)

    def tearDown(self):
        fixture.rm(self.root)

    def ok(self, *args, actor=None):
        code, out, err = cs(self.root, *args, actor=actor)
        self.assertEqual(code, 0, "%s → exit %d\n%s%s" % (" ".join(args), code, out, err))
        return out

    def refused(self, *args, actor=None):
        code, out, err = cs(self.root, *args, actor=actor)
        self.assertEqual(code, 1, "%s deveria ser recusado (exit 1), deu %d\n%s%s" % (" ".join(args), code, out, err))
        return out + err

    def validate_cli(self):
        code, out, err = cs(self.root, "validate", "--strict")
        return code, out + err

    def assert_valid(self):
        import validate
        ok, errs, _ = validate.run(self.root, strict=True)
        self.assertTrue(ok, errs)
        code, txt = self.validate_cli()
        self.assertEqual(code, 0, txt)

    def assert_invalid(self, *needles):
        import validate
        ok, errs, _ = validate.run(self.root, strict=True)
        self.assertFalse(ok, "validate --strict deveria reprovar")
        for n in needles:
            self.assertTrue(any(n in e for e in errs), "esperado %r em %s" % (n, errs))
        code, txt = self.validate_cli()
        self.assertNotEqual(code, 0, txt)

    def ack(self, reason="motor antigo (atalho D-0-09) deixou US-3 IN_PROGRESS com FEAT-2 em BACKLOG"):
        return self.ok("legacy-ack", "--reason", reason)

    def ack_events(self):
        return [e for e in events(self.root) if e.get("type") == "harness.legacy_ack"]


class TestPrecondicao(Base):
    def test_legado_reprova_validate_como_na_cobaia(self):
        """Sanidade do cenário (passa hoje): é exatamente o erro visto na cobaia."""
        self.assert_invalid(MSG_US3)


class TestLegadoReconhecido(Base):
    def test_ack_reconhece_hierarquia_e_validate_passa(self):
        out = self.ack()
        self.assertIn("US-3", out, "a saída do ack deve citar o que reconheceu")
        self.assertIn("FEAT-2", out)
        self.assert_valid()
        self.refused("legacy-ack", "--reason", "de novo")  # nada mais a reconhecer

    def test_trabalho_da_us3_segue_ate_aceite(self):
        self.ack()
        self.ok("add", "task", "--story", "US-3", "--agent", "dev-billing", "--title", "criar desconto",
                "--goal", "aplicar desconto porque FEAT-2 exige", "--allowed-path", "src/billing/discount.py",
                "--verify-cmd", VERIFY, "--ac", AC, "--ref", "src/billing/total.py:1", "--in", "desconto",
                "--out", "tax: outra task", "--ready")
        advance_to_executing(self, self.root, "T-1")
        dispatch_via_hook(self, self.root, "T-1")
        self.assertEqual(hcore.find(board(self.root), "task", "T-1")["status"], "IN_PROGRESS")
        fixture.write(self.root, "src/billing/discount.py", "RATE = 30\n")
        self.ok("submit", "--task", "T-1", "--files-changed", "src/billing/discount.py", "--check", "unittest: OK",
                "--risk", "nenhum", "--handoff-notes", "ok", actor="dev-billing")
        self.ok("verify", "--task", "T-1")
        self.ok("review", "--task", "T-1", "--by", "reviewer", "--verdict", "PASS", "--findings", "ok discount.py:1",
                actor="reviewer")
        self.ok("accept", "--task", "T-1")
        t = hcore.find(board(self.root), "task", "T-1")
        self.assertEqual((latest_deleg(t)["state"], t["status"]), ("ACCEPTED", "ACCEPTED"))
        self.assert_valid()


class TestNovaIncoerenciaContinuaAcusada(Base):
    def test_outra_story_na_mesma_feature_depois_do_ack(self):
        self.ack()
        self.assert_valid()
        old_motor_start(self.root, "story", "US-2")   # mesmo pai legado, filho NOVO, depois do ack
        self.assert_invalid("story US-2 IN_PROGRESS com feature FEAT-2 em BACKLOG")

    def test_story_em_outra_feature_depois_do_ack(self):
        self.ack()
        _story(self.root, "FEAT-1")                    # US-4 na FEAT-1 (READY)
        cmds.level_transition(self.root, A, "story", "US-4", "ready")
        old_motor_start(self.root, "story", "US-4")
        self.assert_invalid("story US-4 IN_PROGRESS com feature FEAT-1 em READY")

    def test_feature_com_epico_proposed_depois_do_ack(self):
        self.ack()
        cmds.add_feature(self.root, A, "EPIC-2", "Outra", "spec/feat.md", ["python3 -m unittest accept.test_accept"],
                         ["accept/test_accept.py"])  # FEAT-3 (BACKLOG) no EPIC-2 PROPOSED
        b = hcore.load_board(self.root)
        self.assertEqual(hcore.find(b, "feature", "FEAT-3")["state"], "BACKLOG")
        # o atalho antigo: feature posta READY e IN_PROGRESS por op direta, sem feature_dor nem parent_epic_active
        engine.commit(self.root, A, lambda ctx: [Event("feature.ready", "FEAT-3", [["set", ref("feature", "FEAT-3"), "state", "READY"]])])
        old_motor_start(self.root, "feature", "FEAT-3")
        self.assert_invalid("feature FEAT-3 IN_PROGRESS com épico EPIC-2 em PROPOSED")


class TestAckEHumano(Base):
    def test_guard_bloqueia_legacy_ack_de_agente(self):
        n0 = len(events(self.root))
        cmd = ".swarm/bin/cs-state legacy-ack --reason x"
        for actor in ({}, {"agent_id": "ag-1", "agent_type": "dev-billing"}):
            code, _, err = hook(self.root, "pre-bash", bash_payload(self.root, cmd, actor))
            self.assertEqual(code, 2, "legacy-ack de agente deve ser bloqueado (%r): %s" % (actor, err))
        self.assertEqual(len(events(self.root)), n0)
        self.assertFalse(self.ack_events())


class TestAckListaOQueReconheceu(Base):
    def test_evento_lista_exatamente_as_incoerencias(self):
        old_motor_start(self.root, "story", "US-2")   # segunda incoerência legada, ANTES do ack
        self.assert_invalid(MSG_US3, "story US-2 IN_PROGRESS com feature FEAT-2 em BACKLOG")
        self.ack()
        acks = self.ack_events()
        self.assertEqual(len(acks), 1)
        args = (acks[0].get("data") or {}).get("args") or {}
        for k in ("reason", "transitions", "accepted"):   # o que já lista hoje
            self.assertIn(k, args, json.dumps(args, ensure_ascii=False))
        self.assertTrue(args["reason"].strip())
        self.assertEqual(args["transitions"], [], "nenhuma transição ilegal neste legado")
        self.assertEqual(args["accepted"], [], "nenhum aceite sem gate neste legado")
        hier = args.get("hierarchy")
        self.assertIsInstance(hier, list, "args.hierarchy deve listar as incoerências reconhecidas: %s" %
                              json.dumps(args, ensure_ascii=False))
        self.assertEqual(len(hier), 2, json.dumps(hier, ensure_ascii=False))
        self.assertEqual(sum(1 for h in hier if mentions(h, "US-3", "IN_PROGRESS", "FEAT-2", "BACKLOG")), 1, hier)
        self.assertEqual(sum(1 for h in hier if mentions(h, "US-2", "IN_PROGRESS", "FEAT-2", "BACKLOG")), 1, hier)
        for h in hier:  # nada além do que estava incoerente
            self.assertFalse(mentions(h, "US-1") or mentions(h, "FEAT-1") or mentions(h, "EPIC-1"), h)
        self.assert_valid()


if __name__ == "__main__":
    unittest.main()
