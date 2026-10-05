"""Regressão: promoção implícita de pai passa pela transição da máquina do pai (guardas avaliadas).

Bug (oráculo test_cobertura_maquinas.TestAtalhoDeGuarda): `story start` emitia `feature.start` direto e `dispatch`
punha story/feature em IN_PROGRESS por op de estado — `parent_epic_active` era contornada e `validate --strict`
aceitava feature IN_PROGRESS com épico PROPOSED.
"""
import os
import subprocess
import sys
import unittest

import fixture
from fixture import A
import cmds
import engine
import hcore
import validate
from engine import Event, ref
from hcore import Refused

STATE = os.path.join(fixture.ENGINE, "state.py")


def proposed_process(root):
    """Como fixture.process, mas o épico fica PROPOSED (nunca ativado)."""
    cmds.add_epic(root, A, "Billing", "cobrar certo", "receita")
    cmds.add_feature(root, A, "EPIC-1", "Desconto", "spec/feat.md", ["python3 -m unittest accept.test_accept"],
                     ["accept/test_accept.py"])
    cmds.level_transition(root, A, "feature", "FEAT-1", "ready")
    cmds.add_story(root, A, "us", "FEAT-1", "Como cliente quero desconto", as_a="cliente", i_want="desconto",
                   so_that="pagar menos",
                   criteria=[{"id": "AC-1", "gherkin": "Dado pedido Quando aplico Então desconta", "test": "tests.test_billing"}])
    cmds.level_transition(root, A, "story", "US-1", "ready")


class Base(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo()

    def tearDown(self):
        fixture.rm(self.root)

    def b(self):
        return hcore.load_board(self.root)

    def st(self, kind, eid):
        return hcore.find(self.b(), kind, eid)["state" if kind != "task" else "status"]

    def events(self):
        evs, _, _ = hcore.read_chain(hcore.state_paths(self.root)["events"])
        return evs


class TestStoryStart(Base):
    def test_cli_story_start_recusa_com_guarda_do_pai(self):
        proposed_process(self.root)
        p = subprocess.run([sys.executable, STATE, "--root", self.root, "story", "start", "--id", "US-1"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out = p.stdout.decode("utf-8") + p.stderr.decode("utf-8")
        self.assertEqual(p.returncode, 1, out)
        self.assertIn("épico EPIC-1 não está ACTIVE", out)
        self.assertEqual((self.st("story", "US-1"), self.st("feature", "FEAT-1")), ("READY", "READY"))
        ok, errs, _ = validate.run(self.root, strict=True)
        self.assertTrue(ok, errs)

    def test_story_start_com_epico_active_promove_pela_transicao(self):
        proposed_process(self.root)
        cmds.level_transition(self.root, A, "epic", "EPIC-1", "activate")
        cmds.level_transition(self.root, A, "story", "US-1", "start")
        self.assertEqual((self.st("story", "US-1"), self.st("feature", "FEAT-1")), ("IN_PROGRESS", "IN_PROGRESS"))
        fs = [e for e in self.events() if e["type"] == "feature.start"]
        self.assertEqual(len(fs), 1)
        self.assertEqual(fs[0]["data"].get("problems"), [])   # evento de transição nomeada, não op solta
        ok, errs, _ = validate.run(self.root, strict=True)
        self.assertTrue(ok, errs)

    def test_story_start_com_feature_backlog_recusa(self):
        cmds.add_epic(self.root, A, "E", "o", "receita")
        cmds.level_transition(self.root, A, "epic", "EPIC-1", "activate")
        cmds.add_feature(self.root, A, "EPIC-1", "F", "spec/feat.md", ["python3 -m unittest accept.test_accept"],
                         ["accept/test_accept.py"])
        cmds.add_story(self.root, A, "us", "FEAT-1", "t", as_a="c", i_want="d", so_that="p",
                       criteria=[{"id": "AC-1", "gherkin": "Dado a Quando b Então c", "test": "tests.test_billing"}])
        cmds.level_transition(self.root, A, "story", "US-1", "ready")
        with self.assertRaises(Refused) as cm:
            cmds.level_transition(self.root, A, "story", "US-1", "start")
        self.assertIn("BACKLOG", str(cm.exception))
        self.assertEqual(self.st("story", "US-1"), "READY")


class TestDispatch(Base):
    def _plan_task(self):
        cmds.session_start(self.root, A, "implementar desconto")
        cmds.session_cmd(self.root, A, "triage", {"class": "pequena", "why": "teste"})
        cmds.session_cmd(self.root, A, "plan")
        cmds.add_task(self.root, A, fixture.task_spec(), ready=True)
        cmds.session_cmd(self.root, A, "execute")
        return hcore.find(self.b(), "deleg", "T-1.d1")

    def test_dispatch_recusa_com_epico_proposed(self):
        proposed_process(self.root)
        d = self._plan_task()
        with self.assertRaises(Refused) as cm:
            cmds.dispatch(self.root, A, "T-1.d1", model=d["route"]["model"], tool_use_id="tu-1")
        self.assertIn("épico EPIC-1 não está ACTIVE", str(cm.exception))
        self.assertEqual(hcore.find(self.b(), "deleg", "T-1.d1")["state"], "BRIEFED")
        self.assertEqual((self.st("task", "T-1"), self.st("story", "US-1"), self.st("feature", "FEAT-1")),
                         ("READY", "READY", "READY"))

    def test_dispatch_feliz_emite_eventos_de_transicao(self):
        fixture.dispatched(self.root)
        types = [e["type"] for e in self.events()]
        i = types.index("delegation.dispatch")
        self.assertEqual(types[i:i + 3], ["delegation.dispatch", "story.start", "feature.start"])
        disp = self.events()[i]
        self.assertFalse([op for op in disp["ops"] if op[0] == "set" and op[1].split(":")[0] in ("story", "feature")
                          and op[2] == "state"], "dispatch não muda estado de story/feature por op direta")
        ok, errs, _ = validate.run(self.root, strict=True)
        self.assertTrue(ok, errs)


class TestAccept(Base):
    def test_accept_promove_story_por_story_review(self):
        fixture.dispatched(self.root)
        fixture.submit_ok(self.root)
        cmds.verify(self.root, A, "T-1")
        cmds.review(self.root, "reviewer", "T-1", "reviewer", "PASS", "ok discount.py:1")
        cmds.accept(self.root, A, "T-1")
        evs = self.events()
        self.assertEqual([e["type"] for e in evs[-2:]], ["delegation.accept", "story.review"])
        self.assertFalse([op for op in evs[-2]["ops"] if op[1].startswith("story:") and op[2] == "state"])
        self.assertEqual(self.st("story", "US-1"), "IN_REVIEW")
        ok, errs, _ = validate.run(self.root, strict=True)
        self.assertTrue(ok, errs)


class TestValidateHierarquia(Base):
    def _raw(self, typ, kind, eid, to):
        engine.commit(self.root, A, lambda ctx: [Event(typ, eid, [["set", ref(kind, eid), "state", to]])])

    def test_validate_acusa_feature_in_progress_com_epico_nao_active(self):
        proposed_process(self.root)
        self._raw("feature.start", "feature", "FEAT-1", "IN_PROGRESS")   # o atalho antigo (op direta)
        ok, errs, _ = validate.run(self.root, strict=True)
        self.assertFalse(ok)
        self.assertTrue(any("FEAT-1 IN_PROGRESS com épico EPIC-1 em PROPOSED" in e for e in errs), errs)

    def test_validate_acusa_story_in_progress_com_feature_fora(self):
        proposed_process(self.root)
        self._raw("story.start", "story", "US-1", "IN_PROGRESS")
        ok, errs, _ = validate.run(self.root, strict=True)
        self.assertFalse(ok)
        self.assertTrue(any("US-1 IN_PROGRESS com feature FEAT-1 em READY" in e for e in errs), errs)


if __name__ == "__main__":
    unittest.main()
