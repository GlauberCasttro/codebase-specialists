"""G14 roteamento, G9 sessão, S3 brief por fase, core (j5, cadeia, globs), validate."""
import os
import subprocess
import time
import unittest

import fixture
from fixture import A
import brief
import cmds
import engine
import hcore
import j5
import router
import session
import validate


class TestRouter(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo(no_rules=True)

    def tearDown(self):
        fixture.rm(self.root)

    def test_trivial_cheap_and_risk_top_and_retry_up(self):
        fixture.process(self.root, "trivial")
        cmds.add_task(self.root, A, fixture.task_spec(), ready=True)
        d = hcore.find(hcore.load_board(self.root), "deleg", "T-1.d1")
        self.assertEqual(d["route"]["model"], "haiku")
        ctx = engine.Ctx(self.root, hcore.load_board(self.root))
        t = ctx.find("task", "T-1")
        self.assertEqual(router.recommend(ctx, t, dict(d, retries=1), log=False)["model"], "sonnet")
        t2 = dict(t, **{"class": "risco"})
        self.assertEqual(router.recommend(ctx, t2, d, log=False)["model"], "opus")

    def test_gate_not_below_author(self):
        fixture.process(self.root, "pequena")
        cmds.add_task(self.root, A, fixture.task_spec(), ready=True)
        ctx = engine.Ctx(self.root, hcore.load_board(self.root))
        t = ctx.find("task", "T-1")
        d = dict(engine.latest_deleg(t), model={"name": "sonnet", "procedencia": "declarada-no-despacho"})
        self.assertTrue(router.review_model_problems(ctx, t, d, "haiku"))
        self.assertFalse(router.review_model_problems(ctx, t, d, "opus"))

    def test_outcome_without_provenance_does_not_train(self):
        fixture.dispatched(self.root, klass="trivial")
        before = router.priors(self.root)
        b = hcore.load_board(self.root)
        d = hcore.find(b, "deleg", "T-1.d1")
        d["model"] = {"name": "haiku", "procedencia": "recomendacao"}
        router.outcome_from_event(self.root, b, {"type": "delegation.accept", "entity": "T-1.d1"})
        self.assertEqual(router.priors(self.root), before)
        d["model"] = {"name": "haiku", "procedencia": "declarada-no-despacho"}
        rec = router.outcome_from_event(self.root, b, {"type": "delegation.accept", "entity": "T-1.d1"})
        self.assertNotEqual(router.priors(self.root), before)
        router.anular(self.root, rec["at"], "registro errado")
        self.assertEqual(router.priors(self.root), before)
        _, errs, _ = hcore.read_chain(router.ledger_path(self.root))
        self.assertEqual(errs, [])

    def test_accept_trains_with_declared_dispatch(self):
        fixture.dispatched(self.root, klass="trivial")
        fixture.submit_ok(self.root)
        cmds.verify(self.root, A, "T-1")
        cmds.accept(self.root, A, "T-1")
        recs = [r for r in router.read_ledger(self.root) if r.get("event") == "outcome"]
        self.assertTrue(recs and recs[-1]["trains"] and recs[-1]["success"])


class TestSession(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo()
        fixture.process(self.root)

    def tearDown(self):
        fixture.rm(self.root)

    def test_roundtrip_idempotent_and_budget(self):
        i1 = session.save(self.root, "criou US-1", "adicionar task")
        text, match = session.load(self.root)
        self.assertTrue(match)
        self.assertLessEqual(len(text.splitlines()), 30)
        self.assertLessEqual(session.estimate_tokens(text), 2000)
        self.assertIn("próximo passo", text)
        self.assertIn("comando:", text)
        i2 = session.save(self.root, "criou US-1", "adicionar task")
        self.assertEqual(i1["stamp"], i2["stamp"])
        ok, _ = session.check_saved(self.root)
        self.assertTrue(ok)

    def test_stamp_matches_after_state_only_commit(self):
        session.save(self.root, "x", "y", commit=True)
        _, match = session.load(self.root)
        self.assertTrue(match)

    def test_delta_after_new_event(self):
        session.save(self.root, "x", "y")
        cmds.add_task(self.root, A, fixture.task_spec())
        text, match = session.load(self.root)
        self.assertFalse(match)
        self.assertIn("DELTA", text)
        self.assertIn("task.add", text)
        self.assertIn("comando:", text)
        ok, _ = session.check_saved(self.root)
        self.assertFalse(ok)

    def test_one_line_inputs(self):
        with self.assertRaises(hcore.Refused):
            session.save(self.root, "x" * 300, "y")


class TestS3(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo()

    def tearDown(self):
        fixture.rm(self.root)

    def test_review_package_scoped_business_rules(self):
        fixture.dispatched(self.root)
        fixture.submit_ok(self.root)
        cmds.verify(self.root, A, "T-1")
        ctx = engine.Ctx(self.root, hcore.load_board(self.root))
        t = ctx.find("task", "T-1")
        pkg = brief.package(ctx, t, "review", "reviewer")
        self.assertIn("br.billing.max-discount", pkg)
        self.assertNotIn("br.members.age", pkg)
        self.assertIn("PASS | FAIL | NEEDS_SPECIALIST", pkg)
        self.assertIn("<<DADO", pkg)
        self.assertLessEqual(len(pkg), 10000)
        impl = brief.package(ctx, t, "implement")
        self.assertIn("allowed_paths", impl)
        ver = brief.package(ctx, t, "verify")
        self.assertIn("CONTA COMO PASS", ver)
        out = subprocess.run(["python3", os.path.join(fixture.ENGINE, "state.py"), "--root", self.root, "brief", "--task", "T-1",
                              "--phase", "review", "--agent", "reviewer"], stdout=subprocess.PIPE).stdout.decode()
        self.assertEqual(out.strip(), pkg.strip())

    def test_budget_respected(self):
        fixture.dispatched(self.root)
        ctx = engine.Ctx(self.root, hcore.load_board(self.root))
        t = ctx.find("task", "T-1")
        t["briefing"]["subtasks"] = ["passo %d %s" % (i, "x" * 300) for i in range(200)]
        self.assertLessEqual(len(brief.package(ctx, t, "implement", budget=3000)), 3000)


class TestCore(unittest.TestCase):
    def test_j5_roundtrip_and_rejects(self):
        obj = {"a": [1, {"b": "x//y", "c d": None}], "z": True, "id": "x"}
        self.assertEqual(j5.loads(j5.dumps(obj, header="h")), obj)
        self.assertEqual(j5.loads("{a: 1, // c\n b: [1,2,], /* x */}"), {"a": 1, "b": [1, 2]})
        for bad in ("{a: 'x'}", "{a: NaN}", "{a: 0x10}", "{a: \"x"):
            with self.assertRaises(ValueError, msg=bad):
                j5.loads(bad)

    def test_chain_detects_edit(self):
        root = fixture.make_repo()
        try:
            p = hcore.state_paths(root)["ledger"]
            for i in range(3):
                hcore.ledger_append(root, {"kind": "t", "i": i})
            self.assertEqual(hcore.read_chain(p)[1], [])
            data = open(p, "rb").read().replace(b'"i":1', b'"i":7')
            open(p, "wb").write(data)
            self.assertTrue(hcore.read_chain(p)[1])
        finally:
            fixture.rm(root)

    def test_globs(self):
        self.assertTrue(hcore.path_matches("src/a/b.py", "src/**"))
        self.assertTrue(hcore.path_matches("src/a.py", "src/*.py"))
        self.assertFalse(hcore.path_matches("src/a/b.py", "src/*.py"))
        self.assertTrue(hcore.path_matches("src/a/b.py", "src/a"))
        self.assertFalse(hcore.path_matches("src/ab.py", "src/a"))
        self.assertTrue(hcore.is_reserved(".swarm/x"))
        self.assertTrue(hcore.pattern_within("src/billing/x.py", ["src/billing/**"]))
        self.assertFalse(hcore.pattern_within("src/members/x.py", ["src/billing/**"]))
        with self.assertRaises(hcore.StateError):
            hcore.norm_rel("../x")

    def test_root_never_script_dir(self):
        old = os.environ.pop("CLAUDE_PROJECT_DIR", None)
        oldc = os.environ.pop("CS_ROOT", None)
        try:
            with self.assertRaises(hcore.StateError):
                hcore.resolve_root(None)
        finally:
            if old:
                os.environ["CLAUDE_PROJECT_DIR"] = old
            if oldc:
                os.environ["CS_ROOT"] = oldc


class TestValidate(unittest.TestCase):
    def test_empty_strict_fails_unless_allowed(self):
        root = fixture.make_repo()
        try:
            self.assertFalse(validate.run(root, strict=True)[0])
            self.assertTrue(validate.run(root, strict=True, allow_empty=True)[0])
        finally:
            fixture.rm(root)

    def test_missing_board_fails_and_verdict_enum(self):
        root = fixture.make_repo()
        try:
            fixture.dispatched(root)
            self.assertTrue(validate.run(root, strict=True)[0])
            p = hcore.state_paths(root)["board"]
            b = j5.load(p)
            b["tasks"][0]["reviews"].append({"by": "x", "verdict": "OK", "findings": "", "at": "t"})
            hcore.write_json5(p, b, "x")
            ok, errs, _ = validate.run(root, strict=True)
            self.assertFalse(ok)
            self.assertTrue(any("enum" in e for e in errs))
            os.remove(p)
            self.assertFalse(validate.run(root, strict=True)[0])
        finally:
            fixture.rm(root)


if __name__ == "__main__":
    unittest.main()
