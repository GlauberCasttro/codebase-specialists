"""Complemento (não-oráculo) de D-1-02 / D-1-03: casos de borda da correção.

D-1-02: CLI sem --tool-use-id recusa DEPOIS das guardas (a recusa por guarda continua nomeando a guarda); `next` aponta
a saída do despacho fantasma; subagente continua bloqueado de cs-state dispatch.
D-1-03: brief_valid recusa checagem crua da árvore sobre protected; o sufixo legado é removido na geração, no amend e
na execução do verify (board antigo continua verificável).
"""
import os
import shutil
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import fixture  # noqa: E402
import hcore  # noqa: E402
from test_faixas_aceite import bash_payload, board, cs, hook  # noqa: E402

A = fixture.A
LEGACY = ' && test -z "$(git status --porcelain -- \':(glob)src/users/**\')"'


class Base(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def task(self, tid="T-1"):
        return hcore.find(board(self.root), "task", tid)

    def deleg(self, tid="T-1"):
        return (self.task(tid).get("delegations") or [None])[-1]


class TestD102(Base):
    def _briefed(self):
        import cmds
        fixture.process(self.root)
        cmds.add_task(self.root, A, fixture.task_spec(), ready=True)
        return cmds

    def test_cli_recusa_por_guarda_antes_da_recusa_por_tool_use_id(self):
        self._briefed()
        code, out, err = cs(self.root, "dispatch", "--task", "T-1", "--model", self.deleg()["route"]["model"])
        self.assertEqual(code, 1)
        self.assertIn("EXECUTING", out + err, "sessão fora de EXECUTING: a guarda session_executing fala primeiro")

    def test_cli_com_tool_use_id_explicito_passa(self):
        cmds = self._briefed()
        cmds.session_cmd(self.root, A, "execute")
        code, out, err = cs(self.root, "dispatch", "--task", "T-1", "--model", self.deleg()["route"]["model"],
                            "--tool-use-id", "tu-adapter")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.deleg()["tool_use_id"], "tu-adapter")

    def test_cli_sem_tool_use_id_ensina_o_agent(self):
        cmds = self._briefed()
        cmds.session_cmd(self.root, A, "execute")
        code, out, err = cs(self.root, "dispatch", "--task", "T-1", "--model", self.deleg()["route"]["model"])
        self.assertEqual(code, 1)
        self.assertIn("Agent(", out + err)
        self.assertIn("T-1.d1", out + err)

    def test_next_aponta_saida_do_fantasma_e_return_retry_devolvem_tentativa(self):
        cmds = self._briefed()
        cmds.session_cmd(self.root, A, "execute")
        cmds.dispatch(self.root, A, "T-1", model=self.deleg()["route"]["model"], procedencia="declarada-cli")
        self.assertEqual(self.task()["attempts"], 1)
        code, out, _ = cs(self.root, "next")
        self.assertEqual(code, 0)
        self.assertIn("FANTASMA", out)
        self.assertIn("cs-state return --task T-1", out)
        cmds.return_(self.root, A, "T-1", "despacho fantasma")
        self.assertEqual((self.task()["attempts"], self.task().get("change_base")), (0, None))
        cmds.retry(self.root, A, "T-1", findings="despacho fantasma")
        d = self.deleg()
        self.assertEqual((d["state"], int(d.get("retries") or 0)), ("BRIEFED", 0))
        self.assertFalse(d["phantom_dispatch"]["pending_retry"])
        import validate
        ok, errs, _ = validate.run(self.root, strict=True)
        self.assertTrue(ok, errs)

    def test_return_de_despacho_real_continua_consumindo(self):
        fixture.dispatched(self.root)
        import cmds
        cmds.return_(self.root, A, "T-1")
        cmds.retry(self.root, A, "T-1", findings="entregue com submission")
        self.assertEqual((self.task()["attempts"], int(self.deleg()["retries"])), (1, 1))

    # ------------------------------------------------ --manual (plataforma sem hook pre-agent)
    def _exec(self):
        cmds = self._briefed()
        cmds.session_cmd(self.root, A, "execute")
        return self.deleg()["route"]["model"]

    def test_manual_despacha_grava_origem_e_consome_tentativa(self):
        model = self._exec()
        code, out, err = cs(self.root, "dispatch", "--task", "T-1", "--manual", "--model", model)
        self.assertEqual(code, 0, out + err)
        d = self.deleg()
        self.assertEqual((d["state"], d["dispatch_origin"], self.task()["attempts"]), ("DISPATCHED", "manual", 1))
        self.assertTrue(d["tool_use_id"].startswith("manual:"), d["tool_use_id"])

    def test_sem_flag_recusa_com_dica_de_manual(self):
        model = self._exec()
        code, out, err = cs(self.root, "dispatch", "--task", "T-1", "--model", model)
        self.assertEqual(code, 1)
        self.assertIn("--manual", out + err)
        self.assertEqual((self.deleg()["state"], self.task()["attempts"]), ("BRIEFED", 0))

    def test_manual_e_tool_use_id_sao_excludentes(self):
        model = self._exec()
        code, out, err = cs(self.root, "dispatch", "--task", "T-1", "--manual", "--tool-use-id", "tu-x", "--model", model)
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.deleg()["state"], "BRIEFED")

    def test_guard_bloqueia_manual_no_bash_do_principal(self):
        model = self._exec()
        for cmd in (".swarm/bin/cs-state dispatch --task T-1 --manual --model %s" % model,
                    "cs-state dispatch T-1 --manual"):
            with self.subTest(cmd=cmd):
                code, _, err = hook(self.root, "pre-bash", bash_payload(self.root, cmd, {}))
                self.assertEqual(code, 2, err)
                self.assertIn("Agent", err)
        self.assertEqual(self.deleg()["state"], "BRIEFED")

    def test_fluxo_completo_apos_despacho_manual(self):
        model = self._exec()
        code, out, err = cs(self.root, "dispatch", "--task", "T-1", "--manual", "--model", model)
        self.assertEqual(code, 0, out + err)
        fixture.write(self.root, "src/billing/discount.py", "RATE = 30\n")
        for args, actor in ((("submit", "--task", "T-1", "--files-changed", "src/billing/discount.py", "--check",
                              "unittest: OK", "--risk", "nenhum", "--handoff-notes", "ok"), "dev-billing"),
                            (("verify", "--task", "T-1"), None),
                            (("review", "--task", "T-1", "--by", "reviewer", "--verdict", "PASS", "--findings",
                              "ok discount.py:1"), "reviewer"),
                            (("accept", "--task", "T-1"), None)):
            code, out, err = cs(self.root, *args, actor=actor)
            self.assertEqual(code, 0, "%s → %s%s" % (args[0], out, err))
        self.assertEqual((self.deleg()["state"], self.task()["status"], self.task()["attempts"]),
                         ("ACCEPTED", "ACCEPTED", 1))
        import validate
        ok, errs, _ = validate.run(self.root, strict=True)
        self.assertTrue(ok, errs)

    def test_subagente_continua_bloqueado(self):
        fixture.dispatched(self.root)
        sub = {"agent_id": "ag-1", "agent_type": "dev-billing"}
        code, _, err = hook(self.root, "pre-bash", bash_payload(self.root, ".swarm/bin/cs-state dispatch --task T-1", sub))
        self.assertEqual(code, 2, err)


class TestD103(Base):
    def test_brief_valid_recusa_checagem_crua_da_arvore(self):
        import cmds
        fixture.process(self.root)
        for vc in ("python3 -m unittest discover -s tests -t . && git diff --quiet -- tests/",
                   'python3 -m unittest discover -s tests -t . && test -z "$(git status --porcelain tests/)"'):
            with self.subTest(vc=vc):
                with self.assertRaises(hcore.Refused) as cm:
                    cmds.add_task(self.root, A, fixture.task_spec(protected_paths=["tests/**"], verification_command=vc),
                                  ready=True)
                self.assertIn("checagem crua", str(cm.exception))

    def test_geracao_e_amend_removem_o_sufixo_legado(self):
        import cmds
        fixture.process(self.root)
        base = "python3 -m unittest discover -s tests -t ."
        cmds.add_task(self.root, A, fixture.task_spec(protected_paths=["src/users/**"], verification_command=base + LEGACY),
                      ready=True)
        self.assertEqual(self.task()["verification_command"], base)
        cmds.amend(self.root, A, "T-1", "verification_command", base + LEGACY, "legado")
        self.assertEqual(self.task()["verification_command"], base)

    def test_board_legado_com_sufixo_verifica_pelo_motor(self):
        """Task de motor antigo (sufixo cru gravado no board): o verify roda sem o sufixo e prova os protected."""
        import cmds
        import engine
        fixture.dispatched(self.root, protected_paths=["src/users/**"])

        def build(ctx):  # simula o board antigo: o vc gravado com o sufixo cru
            vc = ctx.find("task", "T-1")["verification_command"] + LEGACY
            return [engine.Event("task.amend", "T-1", [["set", engine.ref("task", "T-1"), "verification_command", vc]])]
        engine.commit(self.root, A, build)
        # escrita depois do despacho, fora de qualquer allowed_path → é desta delegação (reprova nomeando o arquivo)
        fixture.write(self.root, "src/users/outra_task.py", "X = 1\n")
        fixture.submit_ok(self.root)
        _, ev = cmds.verify(self.root, A, "T-1")
        probs = ev[-1]["data"]["problems"]
        self.assertEqual(self.deleg()["state"], "REJECTED")
        self.assertTrue(any("protected_path alterado por esta delegação: src/users/outra_task.py" in p for p in probs), probs)
        self.assertFalse(any("verification_command exit" in p for p in probs), "o sufixo cru não pode rodar: %r" % probs)


if __name__ == "__main__":
    unittest.main()
