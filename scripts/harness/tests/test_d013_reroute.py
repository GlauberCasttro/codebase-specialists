"""D-0-13 — reroute (troca de agente) sobre trabalho que já está na árvore.

Mesmo princípio do oráculo test_trabalho_na_arvore.py: a base de "mudança da TASK" é fixada no 1º dispatch da task
(guardada na TASK, não na delegação) e sobrevive à troca de agente. O novo agente herda o código que o anterior deixou
modificado e não commitado; declarar esse arquivo não reprova com "não alterado segundo git". Território e declaração
vazia continuam valendo. Também cobre o fallback de board antigo (task sem change_base): a base é derivada do 1º evento
delegation.dispatch da task.

CLI real (engine/state.py) e guard real (engine/guard.py) em subprocesso, repo git temporário de fixture.make_repo.
"""
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import fixture  # noqa: E402
import hcore  # noqa: E402
import j5  # noqa: E402
from test_trabalho_na_arvore import DEFEITO, FORA, NEW, OUTSIDE, TRACKED, VERIFY_GATE, Base  # noqa: E402
from test_workflow_e2e import commit_all, deleg, task  # noqa: E402

SR = "dev-billing-sr"  # segundo agente com o MESMO território de billing


class Reroute(Base):
    def repo(self, **kw):
        root = super(Reroute, self).repo(**kw)
        p = os.path.join(root, hcore.STATE_DIR, "team.json5")
        with open(p) as f:
            team = j5.loads(f.read())
        team["agents"].append({"name": SR, "kind": "dev", "territory": ["src/billing/**"]})
        with open(p, "w") as f:
            f.write(j5.dumps(team))
        commit_all(root, "time com segundo dev de billing")
        return root

    def escalated_then_rerouted(self, rel, txt="RATE = 30\n"):
        """dev-billing escreve `rel` (não commita), escala; humano troca para SR. Devolve (root, tid) BRIEFED p/ SR."""
        root, _ = self.gate_repo(open_gate=True)
        self.process(root, "pequena")
        t = self.add_task(root, "dev-billing", rel, "aplicar desconto", verify=VERIFY_GATE)
        self.ok(root, "session", "execute")
        self.dispatch(root, t, "dev-billing", "tu-1")
        self.write_in_territory(root, t, "dev-billing", rel, txt)
        self.ok(root, "escalate", "--task", t, "--reason", "precisa de alguém sênior em billing")
        self.ok(root, "reroute", "--task", t, "--agent", SR, "--decision", "passa para o sênior; código feito serve")
        self.assertEqual(task(root, t)["agent"], SR)
        self.ok(root, "ready", "--task", t)
        self.assertEqual(deleg(root, t)["state"], "BRIEFED")
        return root, t

    def _caso(self, rel):
        root, t = self.escalated_then_rerouted(rel)
        cb = task(root, t).get("change_base")
        self.dispatch(root, t, SR, "tu-2")
        self.assertEqual(task(root, t).get("change_base"), cb, "base da TASK não muda no reroute")
        self.submit(root, t, SR, rel)  # sem reescrever
        self.assert_pass(root, t, "reroute sobre %s já alterado" % rel)
        self.finish(root, t)

    def test_reroute_arquivo_rastreado(self):
        self._caso(TRACKED)

    def test_reroute_arquivo_novo(self):
        self._caso(NEW)

    def test_reroute_escrita_nova_fora_reprova(self):
        root, t = self.escalated_then_rerouted(TRACKED)
        self.dispatch(root, t, SR, "tu-2")
        fixture.write(root, OUTSIDE, "AGE = 21\n")
        self.submit(root, t, SR, TRACKED)
        out = self.verify_out(root, t)
        self.assertIn("%s: %s" % (FORA, OUTSIDE), out, out)
        self.assertEqual(deleg(root, t)["state"], "REJECTED")

    def test_reroute_sujeira_alheia_anterior_nao_conta(self):
        root, t = self.escalated_then_rerouted(TRACKED)
        fixture.write(root, OUTSIDE, "AGE = 21\n")  # antes do redispatch
        self.dispatch(root, t, SR, "tu-2")
        self.submit(root, t, SR, TRACKED)
        out = self.verify_out(root, t)
        self.assertNotIn(OUTSIDE, out, out)
        self.assertIn("verify PASS", out, out)

    def test_reroute_com_trabalho_desfeito_reprova(self):
        root, t = self.escalated_then_rerouted(NEW)
        os.remove(os.path.join(root, NEW))
        self.dispatch(root, t, SR, "tu-2")
        self.submit(root, t, SR, NEW)
        out = self.verify_out(root, t)
        self.assertIn("%s: %s" % (DEFEITO, NEW), out, out)
        self.assertEqual(deleg(root, t)["state"], "REJECTED")


class BoardAntigo(Base):
    """Task despachada por motor antigo (sem change_base): retentativa usa a base derivada do 1º evento de dispatch."""

    def _strip_change_base(self, root, tid):
        p = hcore.state_paths(root)["board"]
        with open(p) as f:
            b = j5.loads(f.read())
        for t in b["tasks"]:
            if t["id"] == tid:
                t.pop("change_base", None)
        with open(p, "w") as f:
            f.write(j5.dumps(b))

    def test_retry_em_board_antigo_passa_com_codigo_na_arvore(self):
        root, mark, t = self.first_attempt_rejected(TRACKED)
        self._strip_change_base(root, t)  # simula board gravado pelo motor antigo
        self.assertIsNone(task(root, t).get("change_base"))
        self.open_gate(mark)
        self.dispatch(root, t, "dev-billing", "tu-2")
        cb = task(root, t).get("change_base") or {}
        self.assertEqual(cb.get("source"), "fallback:first-dispatch-event", cb)
        self.submit(root, t, "dev-billing", TRACKED)
        self.assert_pass(root, t, "board antigo, retry sobre %s já alterado" % TRACKED)

    def test_board_antigo_declaracao_vazia_continua_reprovando(self):
        root, mark, t = self.first_attempt_rejected(TRACKED)
        self._strip_change_base(root, t)
        fixture.git(root, "checkout", "--", TRACKED)
        self.open_gate(mark)
        self.dispatch(root, t, "dev-billing", "tu-2")
        self.submit(root, t, "dev-billing", TRACKED)
        out = self.verify_out(root, t)
        self.assertIn("%s: %s" % (DEFEITO, TRACKED), out, out)


if __name__ == "__main__":
    unittest.main()
