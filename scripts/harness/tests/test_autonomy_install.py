"""Modo autônomo (G11 parcial: loop, escalada, proibições) e install (settings merge, Makefile, selftest G6)."""
import json
import os
import subprocess
import unittest

import fixture
from fixture import A
import autonomy
import cmds
import hcore

GUARD = os.path.join(fixture.ENGINE, "guard.py")


def hook(root, mode, payload, env=None):
    e = dict(os.environ, CLAUDE_PROJECT_DIR=root)
    e.pop("CS_GUARD_OFF", None)
    e.update(env or {})
    p = subprocess.run(["python3", GUARD, mode], input=json.dumps(payload).encode(), env=e, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=60)
    return p.returncode, p.stdout.decode(), p.stderr.decode()


BUDGET = {"tasks": 5, "attempts": 2, "minutes": 60}


class TestAutonomy(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo(no_rules=True)
        fixture.process(self.root, "pequena")

    def tearDown(self):
        fixture.rm(self.root)

    def start(self):
        return autonomy.start(self.root, A, "FEAT-1", dict(BUDGET), klass="pequena")

    def test_refuses_green_or_missing_acceptance(self):
        cmds.add_feature(self.root, A, "EPIC-1", "verde", "spec/feat.md", ["true"])
        with self.assertRaises(hcore.Refused):
            autonomy.start(self.root, A, "FEAT-2", dict(BUDGET))  # BACKLOG (sem DoR)
        with self.assertRaises(hcore.Refused):
            autonomy.start(self.root, A, "FEAT-1", {"tasks": 1})  # orçamento incompleto
        with self.assertRaises(hcore.Refused):
            autonomy.start(self.root, A, "FEAT-1", dict(BUDGET), klass="risco")
        fixture.write(self.root, "src/billing/discount.py")  # aceite passaria hoje
        with self.assertRaises(hcore.Refused) as cm:
            autonomy.start(self.root, A, "FEAT-1", dict(BUDGET))
        self.assertIn("já passa", str(cm.exception))

    def test_stop_hook_continues_then_allows(self):
        m = self.start()
        self.assertEqual(m["state"], "ACTIVE")
        cmds.add_task(self.root, A, fixture.task_spec(), ready=True)
        code, out, _ = hook(self.root, "stop", {"hook_event_name": "Stop"})
        self.assertEqual(out.strip(), "")  # sessão em PLANNING: deixa parar
        cmds.session_cmd(self.root, A, "execute")
        code, out, _ = hook(self.root, "stop", {"hook_event_name": "Stop"})
        d = json.loads(out)
        self.assertEqual(d["decision"], "block")
        self.assertIn("continue: cs-state next", d["reason"])
        # anti-loop: sem progresso por N bloqueios → escala e deixa parar
        for _ in range(4):
            code, out, _ = hook(self.root, "stop", {"hook_event_name": "Stop"})
        self.assertEqual(out.strip(), "")
        self.assertEqual(autonomy.load(self.root)["escalation"]["condition"], "no_progress")

    def test_escalates_same_rejection_twice(self):
        self.start()
        cmds.add_task(self.root, A, fixture.task_spec(), ready=True)
        cmds.session_cmd(self.root, A, "execute")
        d = hcore.find(hcore.load_board(self.root), "deleg", "T-1.d1")
        for i in range(2):
            cmds.dispatch(self.root, A, "T-1", model=hcore.find(hcore.load_board(self.root), "deleg", "T-1.d1")["route"]["model"])
            fixture.submit_ok(self.root)
            cmds.reject(self.root, A, "T-1", "falta validar limite de desconto de 30 por cento")
            if i == 0:
                cmds.retry(self.root, A, "T-1")
        b = hcore.load_board(self.root)
        cond = autonomy.detect_escalation(self.root, b, autonomy.load(self.root))
        self.assertEqual(cond[0], "same_rejection_twice")

    def test_escalates_acceptance_changed_and_invariant(self):
        self.start()
        fixture.write(self.root, "accept/test_accept.py", "x = 1\n")
        b = hcore.load_board(self.root)
        self.assertEqual(autonomy.detect_escalation(self.root, b, autonomy.load(self.root))[0], "acceptance_test_changed")

    def test_invariant_escalation(self):
        root = fixture.make_repo()
        try:
            fixture.process(root, "pequena")
            autonomy.start(root, A, "FEAT-1", dict(BUDGET))
            cmds.add_task(root, A, fixture.task_spec(), ready=True)
            b = hcore.load_board(root)
            self.assertEqual(autonomy.detect_escalation(root, b, autonomy.load(root))[0], "invariant_or_frozen_touched")
        finally:
            fixture.rm(root)

    def test_prohibitions(self):
        self.start()
        cmds.add_task(self.root, A, fixture.task_spec(paths=("src/billing/discount.py",)), ready=True)
        self.assertEqual(hook(self.root, "pre-bash", {"tool_name": "Bash", "tool_input": {"command": "git push origin feat"}})[0], 2)
        # kill-switch ignorado (e registrado) em modo autônomo
        code, _, _ = hook(self.root, "pre-write", {"tool_name": "Write", "tool_input": {"file_path": os.path.join(self.root, "src/x.py")}},
                          {"CS_GUARD_OFF": "1"})
        self.assertEqual(code, 2)
        recs = hcore.read_chain(hcore.state_paths(self.root)["ledger"])[0]
        self.assertTrue(any(r.get("kind") == "killswitch_ignored" for r in recs))
        # teste de aceite aprovado não pode ser editado nem por quem tem o território
        self.assertEqual(autonomy.forbidden_write(self.root, "accept/test_accept.py") is not None, True)

    def test_budget_blocks_dispatch_and_report(self):
        autonomy.start(self.root, A, "FEAT-1", {"tasks": 0, "attempts": 2, "minutes": 60})
        cmds.add_task(self.root, A, fixture.task_spec(), ready=True)
        cmds.session_cmd(self.root, A, "execute")
        d = hcore.find(hcore.load_board(self.root), "deleg", "T-1.d1")
        with self.assertRaises(hcore.Refused) as cm:
            cmds.dispatch(self.root, A, "T-1", model=d["route"]["model"])
        self.assertIn("orçamento", str(cm.exception))
        rep = autonomy.stop(self.root, A, "teste")
        self.assertEqual(rep["acceptance_after"][0]["exit_code"] != 0, True)
        self.assertEqual(autonomy.load(self.root)["mode"], "assistido")

    def test_mandate_tamper_detected(self):
        self.start()
        import validate
        self.assertTrue(validate.run(self.root, strict=True)[0])
        m = autonomy.load(self.root)
        m["budget"]["tasks"] = 999
        autonomy.save(self.root, m)
        ok, errs, _ = validate.run(self.root, strict=True)
        self.assertFalse(ok)


class TestInstall(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo(with_state=False)
        with open(os.path.join(self.root, "Makefile"), "w") as f:
            f.write("build:\n\techo build-original\n\nnext:\n\techo mine\n")
        os.makedirs(os.path.join(self.root, ".claude"), exist_ok=True)
        with open(os.path.join(self.root, ".claude", "settings.json"), "w") as f:
            json.dump({"permissions": {"allow": ["Bash(ls)"]}, "hooks": {"PreToolUse": [
                {"matcher": "Bash", "hooks": [{"type": "command", "command": "mine.sh"}]}]}}, f)

    def tearDown(self):
        fixture.rm(self.root)

    def test_install_merge_makefile_selftest(self):
        import install
        res = install.install(self.root, platforms=["cursor"], allow_outside=True)
        s = json.load(open(os.path.join(self.root, ".claude", "settings.json")))
        self.assertEqual(s["permissions"]["allow"], ["Bash(ls)"])
        cmds_ = [h["command"] for g in s["hooks"]["PreToolUse"] for h in g["hooks"]]
        self.assertIn("mine.sh", cmds_)
        self.assertTrue(any("pre-agent" in c for c in cmds_))
        self.assertEqual(s["env"]["CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH"], "1")
        self.assertTrue(any(n.startswith("settings.json.bak-") for n in os.listdir(os.path.join(self.root, ".claude"))))
        res2 = install.install(self.root, platforms=["cursor"], allow_outside=True)
        self.assertEqual(res2["changes"], [])
        s2 = json.load(open(os.path.join(self.root, ".claude", "settings.json")))
        self.assertEqual(s, s2)
        out = subprocess.run(["make", "build"], cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode()
        self.assertIn("build-original", out)
        out = subprocess.run(["make", "next"], cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode()
        self.assertIn("mine", out)
        p = subprocess.run(["make", "cs-next"], cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("sessão", p.stdout.decode())
        self.assertTrue(os.path.isfile(os.path.join(self.root, ".swarm/harness/adapters/cursor.md")))
        import selftest
        r = selftest.run(self.root)
        self.assertTrue(r["ok"], [x for x in r["results"] if not x["ok"]])

    def test_no_makefile_creates_minimal(self):
        os.remove(os.path.join(self.root, "Makefile"))
        import install
        install.install(self.root, settings=False, allow_outside=True)
        p = subprocess.run(["make", "help"], cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("make next", p.stdout.decode())


if __name__ == "__main__":
    unittest.main()
