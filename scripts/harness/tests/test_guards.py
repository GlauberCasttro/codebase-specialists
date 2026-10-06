"""Guards (hooks) — fail-closed, realpath, ledger, kill-switch, Bash conservador, despacho, S3."""
import json
import os
import subprocess
import unittest

import fixture
from fixture import A
import bashscan
import cmds
import hcore

GUARD = os.path.join(fixture.ENGINE, "guard.py")
SUB = {"agent_id": "ag-1", "agent_type": "dev-billing"}


def hook(root, mode, payload, env=None, root_env=True):
    e = dict(os.environ)
    e.pop("CS_GUARD_OFF", None)
    e.pop("CLAUDE_PROJECT_DIR", None)
    if root_env:
        e["CLAUDE_PROJECT_DIR"] = root
    e.update(env or {})
    p = subprocess.run(["python3", GUARD, mode], input=json.dumps(payload).encode(), env=e, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=60)
    return p.returncode, p.stdout.decode(), p.stderr.decode()


def W(root, rel, actor=None):
    p = {"tool_name": "Write", "tool_use_id": "tu", "tool_input": {"file_path": os.path.join(root, rel)}, "cwd": root}
    p.update(actor or {})
    return p


def B(root, cmd, actor=None):
    p = {"tool_name": "Bash", "tool_use_id": "tu", "tool_input": {"command": cmd}, "cwd": root}
    p.update(actor or {})
    return p


def ledger(root):
    return hcore.read_chain(hcore.state_paths(root)["ledger"])[0]


class GuardBase(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo()
        fixture.dispatched(self.root)

    def tearDown(self):
        fixture.rm(self.root)


class TestWriteGuard(GuardBase):
    def test_main_cannot_write_product_but_can_specialists(self):
        self.assertEqual(hook(self.root, "pre-write", W(self.root, "src/billing/discount.py"))[0], 2)
        self.assertEqual(hook(self.root, "pre-write", W(self.root, ".swarm/team.json5"))[0], 0)
        self.assertEqual(hook(self.root, "pre-write", W(self.root, ".swarm/state/board.json5"))[0], 2)

    def test_subagent_territory(self):
        self.assertEqual(hook(self.root, "pre-write", W(self.root, "src/billing/discount.py", SUB))[0], 0)
        self.assertEqual(hook(self.root, "pre-write", W(self.root, "src/billing/tax.py", SUB))[0], 2)
        other = {"agent_id": "x", "agent_type": "dev-users"}
        self.assertEqual(hook(self.root, "pre-write", W(self.root, "src/billing/discount.py", other))[0], 2)

    def test_x01_symlink_resolved(self):
        os.makedirs(os.path.join(self.root, "src/billing"), exist_ok=True)
        os.symlink(os.path.join(self.root, "src/users/model.py"), os.path.join(self.root, "src/billing/discount.py"))
        code, _, err = hook(self.root, "pre-write", W(self.root, "src/billing/discount.py", SUB))
        self.assertEqual(code, 2, err)

    def test_outside_project(self):
        self.assertEqual(hook(self.root, "pre-write", W(self.root, "../fora.py", SUB))[0], 2)

    def test_state_missing_blocks_and_logs(self):
        os.remove(hcore.state_paths(self.root)["board"])
        n = len(ledger(self.root))
        self.assertEqual(hook(self.root, "pre-write", W(self.root, ".swarm/team.json5"))[0], 2)
        self.assertEqual(hook(self.root, "pre-bash", B(self.root, "touch src/billing/discount.py", SUB))[0], 2)
        self.assertEqual(hook(self.root, "pre-bash", B(self.root, "ls src"))[0], 0)
        self.assertEqual(len(ledger(self.root)), n + 2)

    def test_no_project_dir_blocks(self):
        self.assertEqual(hook(self.root, "pre-write", W(self.root, "x"), root_env=False)[0], 2)

    def test_garbage_payload_blocks(self):
        e = dict(os.environ, CLAUDE_PROJECT_DIR=self.root)
        p = subprocess.run(["python3", GUARD, "pre-write"], input=b"{not json", env=e, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(p.returncode, 2)

    def test_killswitch_logged(self):
        n = len(ledger(self.root))
        code, _, _ = hook(self.root, "pre-write", W(self.root, "src/billing/tax.py"), {"CS_GUARD_OFF": "1", "USER": "fulano"})
        self.assertEqual(code, 0)
        rec = ledger(self.root)[n:]
        self.assertEqual(rec[0]["kind"], "killswitch")
        self.assertEqual(rec[0]["user"], "fulano")
        self.assertTrue(rec[0]["at"])

    def test_every_block_logged_with_tool_use_id(self):
        n = len(ledger(self.root))
        hook(self.root, "pre-write", W(self.root, "src/billing/tax.py", SUB))
        r = ledger(self.root)[n]
        self.assertEqual((r["kind"], r["tool_use_id"], r["agent_type"]), ("block", "tu", "dev-billing"))


class TestBashGuard(GuardBase):
    def code(self, cmd, actor=SUB):
        return hook(self.root, "pre-bash", B(self.root, cmd, actor))[0]

    def test_g01_cannot_delete_own_state(self):
        for cmd in ("rm -f .swarm/state/board.json5", "rm -rf .swarm", "mv .swarm/state/events.jsonl /tmp/x",
                    "echo > .swarm/state/ledger.jsonl", "truncate -s0 .swarm/state/board.json5"):
            self.assertEqual(self.code(cmd), 2, cmd)
            self.assertEqual(self.code(cmd, {}), 2, cmd)

    def test_writes_outside(self):
        for cmd in ("echo x > src/billing/tax.py", "tee src/users/model.py < /dev/null", "sed -i '' 's/a/b/' src/users/model.py",
                    "cp README.md src/users/model.py", "cd src && rm users/model.py", "dd if=/dev/zero of=src/users/model.py"):
            self.assertEqual(self.code(cmd), 2, cmd)

    def test_writes_inside_ok(self):
        self.assertEqual(self.code("echo x > src/billing/discount.py"), 0)
        self.assertEqual(self.code("python3 -m unittest discover -s tests 2>/dev/null"), 0)

    def test_unanalyzable(self):
        for cmd in ("bash -c 'touch src/users/model.py'", "eval rm x", "python3 -c 'open(\"x\",\"w\")'", "echo $(ls) > a",
                    "cat <<EOF > src/billing/discount.py\nx\nEOF", "find . -delete", "ls | xargs rm", "$CMD x", "echo `id`"):
            self.assertEqual(self.code(cmd), 2, cmd)

    def test_git_rules(self):
        self.assertEqual(self.code("git status"), 0)
        self.assertEqual(self.code("git checkout -- src"), 2)
        self.assertEqual(self.code("git commit -m x"), 2)  # subagente não roda git de escrita
        self.assertEqual(self.code("git commit -m x", {}), 0)
        self.assertEqual(self.code("git reset --hard", {}), 2)

    def test_harness_cli_permissions(self):
        st = ".swarm/bin/cs-state"
        self.assertEqual(self.code("cs-state accept --task T-1"), 2)
        self.assertEqual(self.code("%s submit --task T-1 --files-changed src/billing/discount.py" % st), 0)
        self.assertEqual(self.code("cs-state review --task T-1 --by reviewer --verdict PASS", {}), 2)
        gate = {"agent_id": "g", "agent_type": "reviewer"}
        self.assertEqual(self.code("cs-state review --task T-1 --by reviewer --verdict PASS --findings x", gate), 0)
        self.assertEqual(self.code("cs-state review --task T-1 --by security --verdict PASS --findings x", gate), 2)
        self.assertEqual(self.code("cs-mem add --agent reviewer --rule 'x' --why y", gate), 0)  # gate grava a própria lição
        self.assertEqual(self.code("cs-mem add --agent dev-billing --rule 'x' --why y", gate), 2)
        self.assertEqual(self.code("cs-mem search 'desconto'"), 0)
        self.assertEqual(self.code("cs-session save --did x --next y"), 2)

    def test_scan_unit(self):
        s = bashscan.scan("FOO=1 nohup cp a b > out.txt 2>&1", self.root, self.root, {})
        self.assertEqual(sorted(t for t, _ in s.writes), ["b", "out.txt"])
        s = bashscan.scan("ls 2>/dev/null; cat x >> /dev/null", self.root, self.root, {})
        self.assertEqual(s.writes, [])


class TestAgentGuard(GuardBase):
    def setUp(self):
        self.root = fixture.make_repo()
        fixture.process(self.root, "pequena")
        cmds.add_task(self.root, A, fixture.task_spec(), ready=True)
        cmds.session_cmd(self.root, A, "execute")
        self.d = hcore.find(hcore.load_board(self.root), "deleg", "T-1.d1")

    def P(self, desc, st="dev-billing", model=None, actor=None):
        ti = {"description": desc, "prompt": "faça", "subagent_type": st}
        if model:
            ti["model"] = model
        p = {"tool_name": "Agent", "tool_use_id": "tu-9", "tool_input": ti}
        p.update(actor or {})
        return p

    def test_dispatch_requires_id_and_model(self):
        self.assertEqual(hook(self.root, "pre-agent", self.P("faz o desconto"))[0], 2)
        code, _, err = hook(self.root, "pre-agent", self.P("T-1.d1: desconto"))
        self.assertEqual(code, 2)
        self.assertIn("sem model", err)
        wrong = "opus" if self.d["route"]["model"] != "opus" else "haiku"
        self.assertEqual(hook(self.root, "pre-agent", self.P("T-1.d1: desconto", model=wrong))[0], 2)
        code, _, err = hook(self.root, "pre-agent", self.P("T-1.d1: desconto", model=self.d["route"]["model"]))
        self.assertEqual(code, 0, err)
        d = hcore.find(hcore.load_board(self.root), "deleg", "T-1.d1")
        self.assertEqual((d["state"], d["tool_use_id"], d["model"]["procedencia"]), ("DISPATCHED", "tu-9", "declarada-no-despacho"))

    def test_override_with_reason(self):
        import router
        cmds.override_model(self.root, A, "T-1", "opus", "área sensível")
        self.assertEqual(hook(self.root, "pre-agent", self.P("T-1.d1: x", model="opus"))[0], 0)

    def test_subagent_cannot_dispatch(self):
        self.assertEqual(hook(self.root, "pre-agent", self.P("T-1.d1: x", model="sonnet", actor=SUB))[0], 2)

    def test_wrong_agent_and_readonly(self):
        self.assertEqual(hook(self.root, "pre-agent", self.P("T-1.d1: x", st="dev-users", model="sonnet"))[0], 2)
        self.assertEqual(hook(self.root, "pre-agent", self.P("explorar", st="Explore", model="haiku"))[0], 0)
        self.assertEqual(hook(self.root, "pre-agent", self.P("explorar", st="Explore"))[0], 2)

    def test_parallel_collision_hook(self):
        cmds.session_cmd(self.root, A, "replan")
        cmds.add_task(self.root, A, fixture.task_spec(id="T-2", paths=("src/billing/discount.py", "src/billing/tax.py"),
                                                       agent="dev-billing", wave=2), ready=True)
        cmds.session_cmd(self.root, A, "execute")
        self.assertEqual(hook(self.root, "pre-agent", self.P("T-1.d1: x", model=self.d["route"]["model"]))[0], 0)
        d2 = hcore.find(hcore.load_board(self.root), "deleg", "T-2.d1")
        code, _, err = hook(self.root, "pre-agent", self.P("T-2.d1: y", model=d2["route"]["model"]))
        self.assertEqual(code, 2)
        self.assertTrue("em voo" in err or "colide" in err, err)


class TestOtherHooks(GuardBase):
    def test_subagent_start_package(self):
        code, out, _ = hook(self.root, "subagent-start", {"hook_event_name": "SubagentStart", **SUB})
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("<<DADO", ctx)
        self.assertIn("src/billing/discount.py", ctx)
        self.assertIn("rule.billing.cents", ctx)
        self.assertNotIn("br.users.age", ctx)
        self.assertLessEqual(len(ctx), 10000)

    def test_subagent_stop_requires_submission(self):
        code, out, _ = hook(self.root, "subagent-stop", {"hook_event_name": "SubagentStop", **SUB})
        self.assertEqual(json.loads(out)["decision"], "block")
        hook(self.root, "subagent-stop", dict({"hook_event_name": "SubagentStop", "stop_hook_active": True}, **SUB))
        d = hcore.find(hcore.load_board(self.root), "deleg", "T-1.d1")
        self.assertEqual(d["state"], "REJECTED")

    def test_user_prompt_advisory_never_blocks(self):
        code, out, _ = hook(self.root, "user-prompt", {"prompt": "isso está errado, deveria ser em centavos"})
        self.assertEqual(code, 0)
        self.assertIn("cs-mem correct", out)
        code, out, _ = hook(self.root, "user-prompt", {"prompt": "bom dia"})
        self.assertEqual((code, out.strip()), (0, ""))

    def test_session_start_injects_orchestrator(self):
        fixture.write(self.root, ".claude/orchestrator.md", "# ORQUESTRADOR\nregra X\n")
        code, out, _ = hook(self.root, "session-start", {"hook_event_name": "SessionStart"})
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("ORQUESTRADOR", ctx)
        self.assertIn("próximo passo", ctx)

    def test_post_edit_reports(self):
        cfgp = hcore.state_paths(self.root)["config"]
        hcore.write_json5(cfgp, {"post_edit_checks": [{"name": "lint", "glob": ["src/**"], "argv": ["python3", "-c", "import sys; sys.exit(1)"]}]}, "t")
        code, out, _ = hook(self.root, "post-edit", W(self.root, "src/billing/discount.py", SUB))
        self.assertEqual(code, 0)
        self.assertIn("lint", out)


if __name__ == "__main__":
    unittest.main()
