"""Saídas de ESCALATED/ABSTAINED (bug real do founder, 2026-10-03: "escalate --task TASK-02-001-AGT → ESCALATED; nenhuma
transição sai de ESCALATED"). Tudo pelo comportamento observável: CLI real (engine/state.py em subprocesso) e guard real
(engine/guard.py com payloads de hook), como test_faixas_aceite.

Cenários:
  * escalate → retry --decision → BRIEFED, task destravada (READY, sem block_reason), sem consumir tentativa; despacho
    pelo guard volta a funcionar. Sem decisão: recusado.
  * retries esgotados (task BLOCKED) → escalate → retry --decision destrava.
  * escalate → reroute --decision → REROUTED (nova delegação PLANNED para o outro agente).
  * abstain → drop → DROPPED, task DROPPED (fechada), sessão consegue verificar; drop sem --reason recusado.
  * next/why de uma delegação ESCALATED mostram as três saídas com comando pronto.
  * modo autônomo ESCALATED → resume --decision → ACTIVE (Stop volta a bloquear); stop de ESCALATED → STOPPED.
"""
import json
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import fixture  # noqa: E402
import hcore  # noqa: E402
from test_faixas_aceite import (AC, VERIFY, agent_payload, bash_payload, board, cs, hook, latest_deleg,  # noqa: E402
                                advance_to_executing, dispatch_via_hook, write_payload)


def task(root, tid="T-1"):
    return hcore.find(board(root), "task", tid)


def deleg(root, tid="T-1"):
    return latest_deleg(task(root, tid))


class Base(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo()

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

    def dispatched(self):
        fixture.process(self.root, "pequena")
        self.ok("add", "task", "--story", "US-1", "--agent", "dev-billing", "--title", "criar desconto",
                "--goal", "aplicar desconto porque FEAT-1 exige", "--allowed-path", "src/billing/discount.py",
                "--verify-cmd", VERIFY, "--ac", AC, "--ref", "src/billing/total.py:1", "--in", "desconto",
                "--out", "tax: outra task", "--ready")
        advance_to_executing(self, self.root, "T-1")
        dispatch_via_hook(self, self.root, "T-1")

    def assert_valid(self):
        import validate
        ok, errs, _ = validate.run(self.root, strict=True)
        self.assertTrue(ok, errs)


class TestEscalada(Base):
    def test_escalate_retry_com_decisao_destrava_e_despacha(self):
        self.dispatched()
        out = self.ok("escalate", "--task", "T-1", "--reason", "conflito de spec: AC-1 contradiz o épico")
        self.assertEqual((deleg(self.root)["state"], task(self.root)["status"]), ("ESCALATED", "BLOCKED"))
        for cmd in ("cs-state retry --task T-1 --decision", "cs-state reroute --task T-1", "cs-state drop --task T-1"):
            self.assertIn(cmd, out, "escalate deve listar as três saídas")
        nxt = self.ok("next")
        why = self.ok("why", "T-1.d1")
        for txt in (nxt, why):
            for cmd in ("retomar: cs-state retry --task T-1 --decision", "trocar de agente: cs-state reroute --task T-1",
                        "descartar: cs-state drop --task T-1 --reason"):
                self.assertIn(cmd, txt, txt)
        self.assertIn("retry", why)
        # sem decisão humana: recusado
        err = self.refused("retry", "--task", "T-1")
        self.assertIn("decisão", err)
        # outras transições continuam recusadas (só as três saídas valem)
        self.refused("accept", "--task", "T-1")
        self.refused("reject", "--task", "T-1", "--reason", "x")
        retries0 = int(deleg(self.root).get("retries") or 0)
        self.ok("retry", "--task", "T-1", "--decision", "seguir o épico; AC-1 vale como escrito")
        d, t = deleg(self.root), task(self.root)
        self.assertEqual((d["state"], t["status"]), ("BRIEFED", "READY"))
        self.assertFalse(t.get("block_reason"))
        self.assertEqual(int(d.get("retries") or 0), retries0, "retomada por decisão humana não consome tentativa")
        self.assertTrue(d["findings_in"][-1].get("decision"))
        self.assertIn("seguir o épico", d["findings_in"][-1]["findings"])
        # despacho volta a funcionar pelo guard real
        code, _, err = hook(self.root, "pre-agent", agent_payload("%s: implementar" % d["id"], "dev-billing",
                                                                  model=d["route"]["model"], tuid="tu-2"))
        self.assertEqual(code, 0, err)
        self.assertEqual(deleg(self.root)["state"], "DISPATCHED")
        self.assert_valid()

    def test_retries_esgotados_escala_e_decisao_destrava(self):
        self.dispatched()
        for i in range(3):
            self.ok("return", "--task", "T-1", "--reason", "sem submission %d" % i)
            if i < 2:
                self.ok("retry", "--task", "T-1", "--findings", "achado %d" % i)
                d = deleg(self.root)
                code, _, err = hook(self.root, "pre-agent", agent_payload("%s: implementar" % d["id"], "dev-billing",
                                                                          model=d["route"]["model"], tuid="tu-r%d" % i))
                self.assertEqual(code, 0, err)
        self.assertEqual(task(self.root)["status"], "BLOCKED")
        self.refused("retry", "--task", "T-1", "--findings", "mais uma")
        self.ok("escalate", "--task", "T-1", "--reason", "tentativas esgotadas")
        self.ok("retry", "--task", "T-1", "--decision", "mais uma tentativa com o limite explicado no brief")
        self.assertEqual((deleg(self.root)["state"], task(self.root)["status"]), ("BRIEFED", "READY"))
        self.assert_valid()

    def test_escalate_reroute_troca_de_agente(self):
        self.dispatched()
        self.ok("escalate", "--task", "T-1", "--reason", "é território de users")
        self.ok("reroute", "--task", "T-1", "--agent", "dev-users", "--allowed-path", "src/users/discount.py",
                "--decision", "mover para dev-users")
        t = task(self.root)
        ds = t["delegations"]
        self.assertEqual(ds[-2]["state"], "REROUTED")
        self.assertEqual((ds[-1]["state"], ds[-1]["agent"], t["status"], t["agent"]), ("PLANNED", "dev-users", "DRAFT", "dev-users"))
        self.assertFalse(t.get("block_reason"))
        self.ok("ready", "--task", "T-1")
        self.assertEqual(deleg(self.root)["state"], "BRIEFED")
        self.assert_valid()

    def test_abstain_drop_fecha_task(self):
        self.dispatched()
        out = self.ok("abstain", "--task", "T-1", "--kind", "spec_ambiguous", "--reason", "AC-1 contradiz a spec",
                      actor="dev-billing")
        self.assertIn("cs-state drop --task T-1", out)
        self.assertEqual(deleg(self.root)["state"], "ABSTAINED")
        why = self.ok("why", "T-1")
        self.assertIn("descartar: cs-state drop --task T-1", why)
        # drop sem --reason é recusado
        self.refused("drop", "--task", "T-1")
        self.assertEqual(deleg(self.root)["state"], "ABSTAINED")
        self.ok("drop", "--id", "T-1", "--reason", "o humano decidiu não fazer o desconto agora")
        t = task(self.root)
        self.assertEqual((deleg(self.root)["state"], t["status"]), ("DROPPED", "DROPPED"))
        self.assertIn("não fazer", t["drop_reason"])
        # DROPPED é terminal
        self.refused("retry", "--task", "T-1", "--decision", "volta")
        # task descartada não segura a sessão
        self.ok("session", "verify")
        self.assert_valid()

    def test_abstain_retry_com_decisao(self):
        self.dispatched()
        self.ok("abstain", "--task", "T-1", "--kind", "spec_ambiguous", "--reason", "AC-1 ambíguo", actor="dev-billing")
        self.ok("retry", "--task", "T-1", "--decision", "AC-1 significa desconto sobre o subtotal")
        self.assertEqual((deleg(self.root)["state"], task(self.root)["status"]), ("BRIEFED", "READY"))
        self.assert_valid()


VERIFY_ENV_SH = """#!/bin/sh
# dependência de AMBIENTE ausente (como httpx fora do venv): 127 até o marcador (fora do repo) existir
if [ ! -f "%s" ]; then
  echo "python: ModuleNotFoundError: No module named 'httpx'" >&2
  exit 127
fi
exec python3 -m unittest discover -s tests -t .
"""
TEST_RATE = """import os
import unittest


class D(unittest.TestCase):
    def test_rate(self):
        with open(os.path.join('src', 'billing', 'discount.py')) as f:
            self.assertIn('RATE = 30', f.read())
"""


class TestFalhaDeAmbiente(Base):
    """Segundo relato do founder: TASK-02-002-KEY presa em ESCALATED com código correto e verify falhando por AMBIENTE."""

    def env_repo(self, verify="sh tools/verify_env.sh", rate="RATE = 30\n"):
        import tempfile
        self.outside = os.path.realpath(tempfile.mkdtemp(prefix="cs-env-"))
        self.addCleanup(fixture.rm, self.outside)
        self.marker = os.path.join(self.outside, "ok")
        fixture.write(self.root, "tools/verify_env.sh", VERIFY_ENV_SH % self.marker)
        fixture.write(self.root, "tests/test_rate.py", TEST_RATE)
        fixture.git(self.root, "add", "-A")
        fixture.git(self.root, "commit", "-qm", "env")
        fixture.process(self.root, "pequena")
        self.ok("add", "task", "--story", "US-1", "--agent", "dev-billing", "--title", "criar desconto",
                "--goal", "aplicar desconto porque FEAT-1 exige", "--allowed-path", "src/billing/discount.py",
                "--verify-cmd", verify, "--ac", AC, "--ref", "src/billing/total.py:1", "--in", "desconto",
                "--out", "tax: outra task", "--ready")
        advance_to_executing(self, self.root, "T-1")
        dispatch_via_hook(self, self.root, "T-1")
        sub = {"agent_id": "ag-1", "agent_type": "dev-billing"}
        self.assertEqual(hook(self.root, "pre-write", write_payload(self.root, "src/billing/discount.py", sub))[0], 0)
        fixture.write(self.root, "src/billing/discount.py", rate)
        self.ok("submit", "--task", "T-1", "--files-changed", "src/billing/discount.py", "--check", "unittest: OK",
                "--risk", "nenhum", "--handoff-notes", "ok", actor="dev-billing")
        out = self.ok("verify", "--task", "T-1")
        self.assertIn("REPROVOU", out)
        self.assertEqual(deleg(self.root)["state"], "REJECTED")

    def waive(self, by, actor=None, evidence="saída do verify: ModuleNotFoundError: No module named 'httpx' (exit 127)"):
        args = ["waive-verify", "--task", "T-1", "--reason", "httpx ausente na máquina; 3/3 ACs verdes no ambiente certo",
                "--evidence", evidence]
        if by is not None:
            args += ["--by", by]
        return cs(self.root, *args, actor=actor)

    def test_exit_127_classifica_ambiente_e_next_sugere_reverify_waive(self):
        self.env_repo()
        gr = task(self.root)["gate_report"]
        self.assertEqual((gr["build"]["exit_code"], gr["failure_kind"]), (127, "environment"))
        self.assertIn("python:httpx", gr["missing_tools"])
        self.assertIn("AMBIENTE", task(self.root)["reject_reason"])
        for txt in (self.ok("next"), self.ok("why", "T-1")):
            self.assertIn("cs-state reverify --task T-1", txt, txt)
            self.assertIn("cs-state waive-verify --task T-1", txt, txt)

    def test_reverify_apos_consertar_ambiente_segue_para_review(self):
        self.env_repo()
        attempts = task(self.root)["attempts"]
        open(self.marker, "w").close()  # "instalou o httpx"
        out = self.ok("reverify", "--task", "T-1")
        self.assertIn("reverify PASS", out)
        self.assertEqual((deleg(self.root)["state"], task(self.root)["status"]), ("VERIFIED", "VERIFYING"))
        self.assertEqual(task(self.root)["attempts"], attempts, "reverify não é novo despacho")
        self.refused("accept", "--task", "T-1")  # pequena: review por gate continua
        self.ok("review", "--task", "T-1", "--by", "reviewer", "--verdict", "PASS", "--findings", "ok discount.py:1",
                actor="reviewer")
        self.ok("accept", "--task", "T-1")
        self.assertEqual(task(self.root)["status"], "ACCEPTED")
        self.assert_valid()

    def test_escalada_por_ambiente_reverify_destrava_a_task(self):
        # o caso do founder: REJECTED por ambiente → escalate → task BLOCKED; a TASK (não só a delegação) volta a andar
        self.env_repo()
        out = self.ok("escalate", "--task", "T-1", "--reason", "verify falhou por ambiente (httpx)")
        self.assertIn("cs-state reverify --task T-1", out)
        self.assertEqual(task(self.root)["status"], "BLOCKED")
        self.assertIn("AMBIENTE", self.ok("why", "T-1.d1"))
        self.refused("accept", "--task", "T-1")  # nunca accept direto de ESCALATED
        open(self.marker, "w").close()
        self.ok("reverify", "--task", "T-1")
        self.assertEqual((deleg(self.root)["state"], task(self.root)["status"]), ("VERIFIED", "VERIFYING"))
        self.assertFalse(task(self.root).get("block_reason"))
        self.assert_valid()

    def test_waive_sem_humano_recusado_e_com_humano_exige_review(self):
        self.env_repo()
        for by in (None, "lead", "dev-billing", "reviewer", "orchestrator"):
            code, out, err = self.waive(by)
            self.assertEqual(code, 1, "waive-verify --by %r deveria ser recusado: %s%s" % (by, out, err))
        code, out, err = self.waive("founder", actor="founder")  # ator do payload = --by: auto-dispensa
        self.assertEqual(code, 1, out + err)
        code, out, err = self.waive("founder", evidence="confia")  # evidência sem a ferramenta ausente
        self.assertEqual(code, 1, out + err)
        self.assertEqual(deleg(self.root)["state"], "REJECTED")
        for actor in ({}, {"agent_id": "ag-x", "agent_type": "dev-billing"}):  # principal e subagente: guard bloqueia
            code, _, _ = hook(self.root, "pre-bash", bash_payload(
                self.root, ".swarm/bin/cs-state waive-verify --task T-1 --by founder --reason x --evidence y", actor))
            self.assertEqual(code, 2)
        code, out, err = self.waive("founder")
        self.assertEqual(code, 0, out + err)
        t = task(self.root)
        self.assertEqual((deleg(self.root)["state"], t["status"]), ("VERIFIED", "VERIFYING"))
        self.assertEqual((t["verify_waiver"]["by"], t["verify_waiver"]["failure_kind"]), ("founder", "environment"))
        self.assertIn("DISPENSADO", self.ok("why", "T-1"))
        self.refused("accept", "--task", "T-1")
        self.assertIn("DISPENSADO", self.ok("next"))
        self.ok("review", "--task", "T-1", "--by", "reviewer", "--verdict", "PASS", "--findings", "ok discount.py:1",
                actor="reviewer")
        self.ok("accept", "--task", "T-1")
        self.assert_valid()

    def test_waive_recusado_para_falha_de_assercao(self):
        self.env_repo(verify="python3 -m unittest tests.test_rate", rate="RATE = 10\n")
        self.assertNotEqual(task(self.root)["gate_report"].get("failure_kind"), "environment")
        code, out, err = self.waive("founder", evidence="AssertionError httpx")
        self.assertEqual(code, 1, out + err)
        self.assertIn("AMBIENTE", out + err)
        self.refused("reverify", "--task", "T-1")  # falha de código: o caminho é retry
        self.assertIn("cs-state retry --task T-1", self.ok("next"))


class TestTaskVoltaAAndar(Base):
    def test_escalate_retry_task_chega_a_accepted(self):
        self.dispatched()
        self.ok("escalate", "--task", "T-1", "--reason", "dúvida")
        self.assertEqual(task(self.root)["status"], "BLOCKED")
        self.ok("retry", "--task", "T-1", "--decision", "segue")
        self.assertEqual(task(self.root)["status"], "READY")
        dispatch_via_hook(self, self.root, "T-1")
        self.assertEqual(task(self.root)["status"], "IN_PROGRESS")
        fixture.write(self.root, "src/billing/discount.py", "RATE = 30\n")
        self.ok("submit", "--task", "T-1", "--files-changed", "src/billing/discount.py", "--check", "unittest: OK",
                "--risk", "nenhum", "--handoff-notes", "ok", actor="dev-billing")
        self.ok("verify", "--task", "T-1")
        self.ok("review", "--task", "T-1", "--by", "reviewer", "--verdict", "PASS", "--findings", "ok discount.py:1",
                actor="reviewer")
        self.ok("accept", "--task", "T-1")
        self.assertEqual((deleg(self.root)["state"], task(self.root)["status"]), ("ACCEPTED", "ACCEPTED"))
        self.assert_valid()

    def test_rejected_nao_e_terminal_e_segura_a_sessao(self):
        import hcore as hc
        M = hc.machines()["machines"]
        self.assertNotIn("REJECTED", M["delegation"]["terminal"])
        self.assertNotIn("REJECTED", M["task"]["terminal"])
        self.assertNotIn(("BLOCKED", "ACCEPTED"), hc.legal_pairs("task"), "BLOCKED→ACCEPTED pularia verify/review")
        self.assertNotIn("ESCALATED", M["delegation"]["transitions"]["accept"]["from"])
        self.dispatched()
        self.ok("return", "--task", "T-1", "--reason", "sem submission")
        self.assertEqual(task(self.root)["status"], "REJECTED")
        err = self.refused("session", "verify")
        self.assertIn("T-1", err)
        self.ok("retry", "--task", "T-1", "--findings", "entregue com submission")  # REJECTED segue tendo saída


class TestLegacyAck(Base):
    """Harness hotfixado à mão (machines.json5 editado) → reinstala o motor canônico → histórico continua válido só
    depois de reconhecido pelo humano (evento harness.legacy_ack); transição nova ilegal continua recusada."""

    def test_hotfix_reconhecido_e_novo_atalho_recusado(self):
        import copy
        import cmds
        import hcore as hc
        self.dispatched()
        self.ok("escalate", "--task", "T-1", "--reason", "verify falhou por ambiente")
        orig = hc.machines()
        hot = copy.deepcopy(orig)  # o "hotfix": reject de ESCALATED e par BLOCKED→REJECTED
        hot["machines"]["delegation"]["transitions"]["reject"]["from"].append("ESCALATED")
        hot["machines"]["task"]["pairs"].append(["BLOCKED", "REJECTED"])
        hc._MACHINES = hot
        try:
            cmds.reject(self.root, "lead", "T-1", "hotfix: sai de ESCALATED")
        finally:
            hc._MACHINES = None
        self.assertEqual(deleg(self.root)["state"], "REJECTED")
        import validate
        ok, errs, _ = validate.run(self.root, strict=True)
        self.assertFalse(ok)
        self.assertTrue(any("ilegal" in e for e in errs), errs)
        # agente não reconhece histórico; humano sim
        code, _, _ = hook(self.root, "pre-bash", bash_payload(self.root, ".swarm/bin/cs-state legacy-ack --reason x", {}))
        self.assertEqual(code, 2)
        out = self.ok("legacy-ack", "--reason", "hotfix manual de 2026-10-03 substituído pelo motor canônico")
        self.assertIn("ESCALATED→REJECTED", out)
        self.assert_valid()
        self.refused("legacy-ack", "--reason", "de novo")  # nada mais a reconhecer
        # o atalho do hotfix não vale para eventos novos
        self.ok("escalate", "--task", "T-1", "--reason", "de novo")
        self.refused("reject", "--task", "T-1", "--reason", "atalho")
        self.assert_valid()


class TestAutonomiaEscalada(Base):
    def setUp(self):
        self.root = fixture.make_repo(no_rules=True)
        fixture.process(self.root, "pequena")

    def stop_hook(self):
        return hook(self.root, "stop", {"hook_event_name": "Stop"})

    def escalated(self):
        self.ok("autonomy", "start", "--feature", "FEAT-1", "--budget", "tasks=5,attempts=2,minutes=60", "--class", "pequena")
        self.ok("add", "task", "--story", "US-1", "--agent", "dev-billing", "--title", "criar desconto",
                "--goal", "aplicar desconto porque FEAT-1 exige", "--allowed-path", "src/billing/discount.py",
                "--verify-cmd", VERIFY, "--ac", AC, "--ref", "src/billing/total.py:1", "--in", "desconto",
                "--out", "tax: outra task", "--ready")
        self.ok("session", "execute")
        for _ in range(6):
            self.stop_hook()
        import autonomy
        m = autonomy.load(self.root)
        self.assertEqual(m["state"], "ESCALATED")
        return m

    def test_autonomia_escalada_retomada(self):
        import autonomy
        self.escalated()
        nxt = self.ok("next")
        self.assertIn("cs-state autonomy resume --decision", nxt)
        self.assertIn("cs-state autonomy stop", nxt)
        self.refused("autonomy", "resume")  # sem decisão
        self.ok("autonomy", "resume", "--decision", "pode seguir; o despacho é do lead")
        m = autonomy.load(self.root)
        self.assertEqual((m["state"], m["escalation"]), ("ACTIVE", None))
        self.assertEqual(m["decisions"][-1]["decision"], "pode seguir; o despacho é do lead")
        self.refused("autonomy", "resume", "--decision", "de novo")  # só sai de ESCALATED
        code, out, _ = self.stop_hook()
        self.assertEqual(json.loads(out)["decision"], "block", "mandato retomado volta a conduzir o loop")
        self.assert_valid()

    def test_autonomia_escalada_condicao_reconhecida_e_forja_detectada(self):
        import autonomy
        self.ok("autonomy", "start", "--feature", "FEAT-1", "--budget", "tasks=5,attempts=2,minutes=60", "--class", "pequena")
        fixture.write(self.root, "accept/test_accept.py", "x = 1\n")
        m = autonomy.load(self.root)
        cond, ev = autonomy.detect_escalation(self.root, board(self.root), m)
        autonomy.escalate(self.root, m, cond, ev)
        self.ok("autonomy", "resume", "--decision", "a mudança no teste de aceite foi minha; aceite")
        self.assertIsNone(autonomy.detect_escalation(self.root, board(self.root), autonomy.load(self.root)))
        self.assert_valid()
        m = autonomy.load(self.root)
        m["acknowledged"].append("f" * 64)  # reconhecimento sem decisão registrada
        autonomy.save(self.root, m)
        import validate
        ok, errs, _ = validate.run(self.root, strict=True)
        self.assertFalse(ok)
        self.assertTrue(any("autonomy.resume" in e for e in errs), errs)

    def test_autonomia_escalada_encerrada(self):
        import autonomy
        self.escalated()
        self.ok("autonomy", "stop", "--reason", "o humano encerrou")
        m = autonomy.load(self.root)
        self.assertEqual((m["state"], m["mode"]), ("STOPPED", "assistido"))
        self.refused("autonomy", "resume", "--decision", "volta")


if __name__ == "__main__":
    unittest.main()


class TestEnvfailParidadeComScan(unittest.TestCase):
    """envfail.py é cópia (o motor é instalado sem o scan): os padrões não podem divergir de scan/toolcheck.py."""

    def test_mesmos_padroes(self):
        scan = os.path.join(os.path.dirname(fixture.HARNESS), "scan")
        if not os.path.isfile(os.path.join(scan, "toolcheck.py")):
            self.skipTest("scan ausente (motor instalado)")
        import importlib.util
        spec = importlib.util.spec_from_file_location("toolcheck_ref", os.path.join(scan, "toolcheck.py"))
        tc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tc)
        import envfail
        self.assertEqual([r.pattern for r in envfail.NOT_FOUND], [r.pattern for r in tc.NOT_FOUND])
        self.assertEqual(envfail.PY_MISSING_MODULE.pattern, tc.PY_MISSING_MODULE.pattern)
        self.assertEqual(envfail.diagnose("x: command not found", 127), "x")
        self.assertIsNone(envfail.diagnose("AssertionError\nx: command not found", 127), "asserção nunca é ambiente")
