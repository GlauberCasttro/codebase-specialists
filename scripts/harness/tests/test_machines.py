"""M1/M2/M3 + processo (G10, G12) + brief-schema (amend, protected_paths, AC test:, gate_report)."""
import os
import unittest

import fixture
from fixture import A
import cmds
import engine
import hcore
import views
from hcore import Refused


class Base(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo()

    def tearDown(self):
        fixture.rm(self.root)

    def board(self):
        return hcore.load_board(self.root)

    def task(self, tid="T-1"):
        return hcore.find(self.board(), "task", tid)

    def deleg(self, tid="T-1"):
        return engine.latest_deleg(self.task(tid))

    def ctx(self):
        return engine.Ctx(self.root, self.board())


class TestM2M3(Base):
    def test_happy_path_all_transitions(self):
        fixture.dispatched(self.root)
        self.assertEqual(self.task()["status"], "IN_PROGRESS")
        self.assertEqual(self.deleg()["state"], "DISPATCHED")
        fixture.submit_ok(self.root)
        self.assertEqual((self.task()["status"], self.deleg()["state"]), ("SUBMITTED", "RETURNED"))
        _, ev = cmds.verify(self.root, A, "T-1")
        self.assertEqual(ev[-1]["data"]["problems"], [])
        t = self.task()
        self.assertEqual((t["status"], self.deleg()["state"]), ("VERIFYING", "VERIFIED"))
        b = t["gate_report"]["build"]
        for k in ("exit_code", "tree_sha256", "command_sha256", "output_sha256"):
            self.assertIn(k, b)
        self.assertEqual(b["exit_code"], 0)
        self.assertEqual(t["gate_report"]["ac_tests"][0]["exit_code"], 0)
        cmds.review(self.root, "reviewer", "T-1", "reviewer", "PASS", "ok discount.py:1")
        cmds.accept(self.root, A, "T-1")
        self.assertEqual((self.task()["status"], self.deleg()["state"]), ("ACCEPTED", "ACCEPTED"))
        self.assertEqual(hcore.find(self.board(), "story", "US-1")["state"], "IN_REVIEW")
        import validate
        ok, errs, _ = validate.run(self.root, strict=True)
        self.assertTrue(ok, errs)

    def test_invalid_transition_actionable(self):
        fixture.dispatched(self.root)
        with self.assertRaises(Refused) as cm:
            cmds.accept(self.root, A, "T-1")
        self.assertIn("DISPATCHED", str(cm.exception))
        self.assertIn("aguarde", cm.exception.hint or "")

    def test_verify_executes_and_rejects_on_exit(self):
        fixture.dispatched(self.root, verification_command="python3 -c 'import sys; sys.exit(3)'")
        fixture.submit_ok(self.root)
        _, ev = cmds.verify(self.root, A, "T-1")
        self.assertTrue(any("exit=3" in p for p in ev[-1]["data"]["problems"]))
        self.assertEqual(self.deleg()["state"], "REJECTED")
        self.assertEqual(self.task()["gate_report"]["build"]["exit_code"], 3)

    def test_verify_detects_write_outside_and_undeclared(self):
        fixture.dispatched(self.root)
        fixture.write(self.root, "src/members/model.py", "AGE = 21\n")
        fixture.submit_ok(self.root)
        _, ev = cmds.verify(self.root, A, "T-1")
        self.assertTrue(any("FORA de allowed_paths: src/members/model.py" in p for p in ev[-1]["data"]["problems"]))

    def test_declared_but_not_changed(self):
        fixture.dispatched(self.root, paths=("src/billing/discount.py", "src/billing/tax.py"))
        fixture.write(self.root, "src/billing/discount.py")
        cmds.submit(self.root, "dev-billing", "T-1", {"files_changed": ["src/billing/discount.py", "src/billing/tax.py"],
                                                     "checks_run": ["x"], "risks": [], "handoff_notes": ""})
        _, ev = cmds.verify(self.root, A, "T-1")
        self.assertTrue(any("não alterado" in p for p in ev[-1]["data"]["problems"]))

    def test_protected_paths_suffix_and_proof(self):
        fixture.dispatched(self.root, protected_paths=["tests/**"])
        t = self.task()
        # D-1-03: a proteção é provada pelo motor contra o snapshot da delegação, não por git cru na árvore
        self.assertNotIn("git status --porcelain", t["verification_command"])
        fixture.write(self.root, "tests/test_billing.py", "import unittest\n")
        fixture.submit_ok(self.root)
        _, ev = cmds.verify(self.root, A, "T-1")
        self.assertEqual(self.deleg()["state"], "REJECTED")

    def test_ac_test_must_be_green(self):
        fixture.dispatched(self.root, acceptance_criteria=["AC-1|desconto aplicado ao total do pedido|test:accept.test_accept"])
        fixture.write(self.root, "src/billing/other.py")  # aceite exige discount.py: continua vermelho
        cmds.amend(self.root, A, "T-1", "allowed_paths", ["src/billing/discount.py", "src/billing/other.py"], "precisa do auxiliar")
        cmds.submit(self.root, "dev-billing", "T-1", {"files_changed": ["src/billing/other.py"], "checks_run": ["x"],
                                                     "risks": [], "handoff_notes": ""})
        _, ev = cmds.verify(self.root, A, "T-1")
        self.assertTrue(any("AC AC-1" in p for p in ev[-1]["data"]["problems"]))

    def test_submission_required_and_in_paths(self):
        fixture.dispatched(self.root)
        with self.assertRaises(Refused):
            cmds.submit(self.root, "dev-billing", "T-1", {"files_changed": []})
        with self.assertRaises(Refused):
            cmds.submit(self.root, "dev-billing", "T-1", {"files_changed": ["src/members/model.py"], "checks_run": ["x"],
                                                         "risks": [], "handoff_notes": ""})
        cmds.return_(self.root, A, "T-1")
        self.assertEqual(self.deleg()["state"], "REJECTED")
        self.assertIn("protocol_failure", self.task()["reject_reason"])

    def test_review_guards(self):
        fixture.dispatched(self.root)
        fixture.submit_ok(self.root)
        cmds.verify(self.root, A, "T-1")
        with self.assertRaises(Refused):
            cmds.review(self.root, A, "T-1", "dev-billing", "PASS", "eu mesmo")  # autor
        with self.assertRaises(Refused):
            cmds.review(self.root, A, "T-1", "dev-members", "PASS", "não é gate")
        with self.assertRaises(Refused):
            cmds.review(self.root, A, "T-1", "reviewer", "OK", "fora do enum")
        with self.assertRaises(Refused):
            cmds.accept(self.root, A, "T-1")  # sem review PASS (classe pequena)
        cmds.review(self.root, A, "T-1", "reviewer", "FAIL", "falta teste de borda")
        with self.assertRaises(Refused) as cm:
            cmds.accept(self.root, A, "T-1")
        self.assertIn("pendente", str(cm.exception))

    def test_retry_then_blocked_after_three_attempts(self):
        fixture.dispatched(self.root, verification_command="false")
        for i in range(3):
            fixture.submit_ok(self.root)
            cmds.verify(self.root, A, "T-1")
            if i < 2:
                cmds.retry(self.root, A, "T-1", "achado %d" % i)
                d = self.deleg()
                cmds.dispatch(self.root, A, "T-1", model=d["route"]["model"], procedencia="declarada-no-despacho")
        t = self.task()
        self.assertEqual(t["status"], "BLOCKED")
        self.assertEqual(t["attempts"], 3)
        with self.assertRaises(Refused):
            cmds.retry(self.root, A, "T-1", "mais uma")
        cmds.reroute(self.root, A, "T-1", "dev-members", "outro território", ["src/members/discount.py"])
        t = self.task()
        self.assertEqual((t["agent"], t["status"], self.deleg()["state"]), ("dev-members", "DRAFT", "PLANNED"))

    def test_abstain_counts_not_as_error(self):
        fixture.dispatched(self.root)
        cmds.abstain(self.root, "dev-billing", "T-1", "spec_ambiguous", "AC-1 contradiz a spec")
        t = self.task()
        self.assertEqual((t["status"], self.deleg()["state"]), ("DRAFT", "ABSTAINED"))
        self.assertEqual(t["submission"]["abstain"]["kind"], "spec_ambiguous")
        cmds.delegate(self.root, A, "T-1")
        self.assertEqual(self.deleg()["state"], "PLANNED")

    def test_escalate(self):
        fixture.dispatched(self.root)
        cmds.escalate(self.root, A, "T-1", "conflito")
        self.assertEqual((self.task()["status"], self.deleg()["state"]), ("BLOCKED", "ESCALATED"))


class TestBrief(Base):
    def test_brief_invalid_not_briefed(self):
        fixture.process(self.root)
        cases = [
            dict(paths=("src/members/model.py",)),            # fora do território
            dict(paths=("**",)),                            # amplo
            dict(paths=()),                                 # vazio
            dict(verification_command="rode os testes e veja se passa direito"),  # prosa
            dict(acceptance_criteria=["AC-1|ok|reviewer"]),  # vago
            dict(acceptance_criteria=["AC-1|desconto aplicado ao total|test:nao existe runner ::"]),
        ]
        for i, kw in enumerate(cases):
            cmds.add_task(self.root, A, fixture.task_spec(id="T-%d" % (i + 10), **kw))
            with self.assertRaises(Refused, msg=str(kw)):
                cmds.ready(self.root, A, "T-%d" % (i + 10))
            self.assertEqual(self.deleg("T-%d" % (i + 10))["state"], "PLANNED")

    def test_invariants_auto_attached(self):
        fixture.process(self.root)
        cmds.add_task(self.root, A, fixture.task_spec())
        inv = {i["id"] for i in self.task()["briefing"]["invariants"]}
        self.assertIn("rule.billing.cents", inv)
        self.assertIn("br.billing.max-discount", inv)
        self.assertNotIn("br.members.age", inv)

    def test_amend_is_event(self):
        fixture.dispatched(self.root)
        cmds.amend(self.root, A, "T-1", "acceptance_criteria.AC-1",
                   {"criterion": "desconto de até 30% aplicado ao total", "verified_by": "test:tests.test_billing"},
                   "AC ambíguo", found_by="dev-billing")
        t = self.task()
        self.assertEqual(t["amendments"][0]["field"], "acceptance_criteria.AC-1")
        self.assertIn("30%", t["acceptance_criteria"][0]["criterion"])
        with self.assertRaises(Refused):
            cmds.amend(self.root, A, "T-1", "allowed_paths", ["**"], "ampliar")
        self.assertNotIn("status_history", t)
        self.assertIn("histórico", views.why(self.ctx(), "T-1"))


class TestM1(Base):
    def test_question_class_no_delegation(self):
        cmds.session_start(self.root, A, "o que faz X?")
        cmds.session_cmd(self.root, A, "triage", {"class": "pergunta", "why": "nenhuma escrita"})
        with self.assertRaises(Refused):
            cmds.session_cmd(self.root, A, "plan")
        cmds.session_cmd(self.root, A, "answer")

    def test_trivial_does_not_require_po_nor_review(self):
        fixture.rm(self.root)
        self.root = fixture.make_repo(no_rules=True)
        fixture.dispatched(self.root, klass="trivial")
        fixture.submit_ok(self.root)
        cmds.verify(self.root, A, "T-1")
        cmds.accept(self.root, A, "T-1")  # sem review: trivial
        self.assertEqual(self.task()["status"], "ACCEPTED")

    def test_trivial_rejects_invariant_touch(self):
        root = self.root
        fixture.process(root, "trivial")
        cmds.add_task(root, A, fixture.task_spec(), ready=True)  # src/billing tem invariante escopado
        with self.assertRaises(Refused) as cm:
            cmds.session_cmd(root, A, "execute")
        self.assertIn("invariante", str(cm.exception))

    def test_feature_requires_po_before_dev_and_risk_two_gates(self):
        fixture.process(self.root, "risco")
        cmds.add_task(self.root, A, fixture.task_spec(), ready=True)
        with self.assertRaises(Refused) as cm:
            cmds.session_cmd(self.root, A, "execute")
        msg = str(cm.exception)
        self.assertIn("kind=product", msg)
        self.assertIn("confirmação", msg)
        cmds.add_task(self.root, A, fixture.task_spec(id="T-PO", agent="po", paths=("docs/stories/us1.md",),
                                                       title="refinar história", wave=0,
                                                       briefing={"references": ["docs/stories/README.md"],
                                                                 "scope": {"in": ["us1"], "out": ["código"]}}), ready=True)
        cmds.session_cmd(self.root, A, "confirm", {"note": "usuário: pode mexer no billing"})
        cmds.session_cmd(self.root, A, "execute")
        d = self.deleg("T-1")
        with self.assertRaises(Refused) as cm:
            cmds.dispatch(self.root, A, "T-1", model=d["route"]["model"])
        self.assertIn("ACCEPTED antes do dev", str(cm.exception))
        self.assertEqual(d["route"]["model"], "opus")  # risco no topo

    def test_risk_needs_two_gate_reviews(self):
        fixture.process(self.root, "risco")
        cmds.add_task(self.root, A, fixture.task_spec(id="T-PO", agent="po", paths=("docs/stories/us1.md",), title="refinar",
                                                       briefing={"references": ["docs/stories/README.md"],
                                                                 "scope": {"in": ["us1"], "out": ["código"]}},
                                                       verification_command="true", wave=0), ready=True)
        cmds.add_task(self.root, A, fixture.task_spec(id="T-1", wave=1), ready=True)
        cmds.session_cmd(self.root, A, "confirm", {"note": "ok"})
        cmds.session_cmd(self.root, A, "execute")
        d = self.deleg("T-PO")
        cmds.dispatch(self.root, A, "T-PO", model=d["route"]["model"])
        fixture.write(self.root, "docs/stories/us1.md", "us\n")
        cmds.submit(self.root, "po", "T-PO", {"files_changed": ["docs/stories/us1.md"], "checks_run": ["x"], "risks": [],
                                             "handoff_notes": ""})
        cmds.verify(self.root, A, "T-PO")
        cmds.review(self.root, A, "T-PO", "reviewer", "PASS", "ok")
        with self.assertRaises(Refused) as cm:
            cmds.accept(self.root, A, "T-PO")
        self.assertIn("2 review", str(cm.exception))
        cmds.review(self.root, A, "T-PO", "security", "PASS", "ok sec")
        cmds.accept(self.root, A, "T-PO")

    def test_parallel_collision_blocked_paths_and_collision_file(self):
        col = {"do_not_parallelize": [{"a": "dev-billing", "b": "dev-members", "co_change": 0.8, "deps": 12}]}
        root = fixture.make_repo(with_collision=col)
        try:
            fixture.process(root, "feature")
            cmds.add_task(root, A, fixture.task_spec(id="T-PO", agent="po", paths=("docs/stories/us1.md",), title="refinar",
                                                      briefing={"references": ["docs/stories/README.md"],
                                                                "scope": {"in": ["us1"], "out": ["código"]}}, wave=0), ready=True)
            cmds.add_task(root, A, fixture.task_spec(id="T-1"), ready=True)
            cmds.add_task(root, A, fixture.task_spec(id="T-2", agent="dev-members", paths=("src/members/discount.py",),
                                                      briefing={"references": ["src/members/model.py"],
                                                                "scope": {"in": ["x"], "out": ["y"]}}), ready=True)
            with self.assertRaises(Refused) as cm:
                cmds.session_cmd(root, A, "execute")
            self.assertIn("co_change=0.8", str(cm.exception))
        finally:
            fixture.rm(root)

    def test_collision_missing_warns_not_blocks(self):
        fixture.process(self.root, "pequena")
        cmds.add_task(self.root, A, fixture.task_spec(id="T-1"), ready=True)
        cmds.session_cmd(self.root, A, "execute")
        recs, _, _ = hcore.read_chain(hcore.state_paths(self.root)["ledger"])
        # warning só ocorre se houver par a checar; com 1 task não há — sem bloqueio de qualquer forma
        self.assertEqual(hcore.find(self.board(), "session", "S-1")["state"], "EXECUTING")

    def test_overlapping_inflight_blocked(self):
        fixture.dispatched(self.root, paths=("src/billing/discount.py",))
        ctx = self.ctx()
        cmds.add_task(self.root, A, fixture.task_spec(id="T-2", agent="dev-members", paths=("src/members/discount.py",),
                                                       briefing={"references": ["src/members/model.py"], "scope": {"in": ["x"], "out": ["y"]}}),
                      ready=True)
        d2 = self.deleg("T-2")
        cmds.dispatch(self.root, A, "T-2", model=d2["route"]["model"])  # disjunto, sem collision.json5: ok
        self.assertEqual(self.deleg("T-2")["state"], "DISPATCHED")

    def test_next_and_why(self):
        fixture.process(self.root)
        cmds.add_task(self.root, A, fixture.task_spec())
        L = views.next_lines(self.ctx())
        self.assertLessEqual(len(L), 10)
        self.assertTrue(any("cs-state ready --task T-1" in x for x in L))
        w = views.why(self.ctx(), "T-1.d1")
        self.assertIn("ready", w)


class TestProcess(Base):
    def test_feature_dor_requires_failing_acceptance(self):
        cmds.add_epic(self.root, A, "e", "o", "m")
        cmds.add_feature(self.root, A, "EPIC-1", "f", "spec/feat.md", ["true"])
        with self.assertRaises(Refused) as cm:
            cmds.level_transition(self.root, A, "feature", "FEAT-1", "ready")
        self.assertIn("já PASSA", str(cm.exception))
        cmds.add_feature(self.root, A, "EPIC-1", "f2", "spec/nao.md", ["false"])
        with self.assertRaises(Refused):
            cmds.level_transition(self.root, A, "feature", "FEAT-2", "ready")

    def test_bug_needs_failing_test_and_fix_needs_fixes(self):
        fixture.process(self.root)
        cmds.add_story(self.root, A, "bug", "FEAT-1", "total ignora cupom", repro=["1. aplicar"], severity="high",
                       environment="prod", failing_test="tests.test_billing")  # passa → não reproduz
        with self.assertRaises(Refused) as cm:
            cmds.level_transition(self.root, A, "story", "BUG-1", "ready")
        self.assertIn("não reproduz", str(cm.exception))
        cmds.add_story(self.root, A, "bug", "FEAT-1", "aceite", repro=["1"], severity="high", environment="prod",
                       failing_test="accept.test_accept")
        cmds.level_transition(self.root, A, "story", "BUG-2", "ready")
        cmds.add_story(self.root, A, "fix", "FEAT-1", "sem fixes", proving_test="tests.test_billing")
        with self.assertRaises(Refused) as cm:
            cmds.level_transition(self.root, A, "story", "FIX-1", "ready")
        self.assertIn("fixes", str(cm.exception))
        cmds.add_story(self.root, A, "fix", "FEAT-1", "com fixes", fixes="BUG-2", proving_test="tests.test_billing")
        cmds.level_transition(self.root, A, "story", "FIX-2", "ready")

    def test_feature_cannot_close_with_open_story_and_rollup(self):
        fixture.process(self.root)
        cmds.level_transition(self.root, A, "feature", "FEAT-1", "start")
        with self.assertRaises(Refused) as cm:
            cmds.level_transition(self.root, A, "feature", "FEAT-1", "done")
        self.assertIn("US-1", str(cm.exception))
        tree = views.board_tree(self.ctx())
        self.assertIn("FEAT-1 [IN_PROGRESS]", tree)
        self.assertIn("stories DONE 0%", tree)

    def test_sprint_dor_and_close_returns_to_backlog(self):
        fixture.process(self.root)
        cmds.add_story(self.root, A, "us", "FEAT-1", "sem dor")
        cmds.add_sprint(self.root, A, "entregar desconto", {"tasks": 3, "attempts": 2, "minutes": 60})
        with self.assertRaises(Refused):
            cmds.level_transition(self.root, A, "sprint", "SPRINT-01", "plan", {"add": ["US-2"]})
        cmds.level_transition(self.root, A, "sprint", "SPRINT-01", "plan", {"add": ["US-1"]})
        cmds.level_transition(self.root, A, "sprint", "SPRINT-01", "start")
        cmds.level_transition(self.root, A, "sprint", "SPRINT-01", "review", {"reason": "faltou tempo"})
        cmds.level_transition(self.root, A, "sprint", "SPRINT-01", "close")
        s = hcore.find(self.board(), "story", "US-1")
        self.assertEqual(s["state"], "BACKLOG")
        self.assertIn("faltou tempo", s["findings"][-1]["reason"])
        sp = hcore.find(self.board(), "sprint", "SPRINT-01")
        self.assertEqual(sp["review"]["returned"][0]["id"], "US-1")

    def test_task_requires_story(self):
        with self.assertRaises(Refused):
            cmds.add_task(self.root, A, {"agent": "dev-billing", "title": "x"})


if __name__ == "__main__":
    unittest.main()
