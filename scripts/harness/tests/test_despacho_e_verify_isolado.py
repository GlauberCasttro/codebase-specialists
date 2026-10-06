"""ORÁCULO — D-1-02 (despacho só de estado) e D-1-03 (verify olhando a árvore inteira), relatados na cobaia
repositório-piloto (projeto-legado).

Tudo pelo comportamento OBSERVÁVEL: CLI real (engine/state.py = cs-state, em subprocesso) e guard real
(engine/guard.py com payloads de hook), num repo git temporário (fixture.make_repo). Nada de mock do motor.
Este arquivo é contrato: quem implementa não o edita.

D-1-02 — `cs-state dispatch` pelo Bash muda a delegação para DISPATCHED (tool_use_id null) sem lançar subagente; a
tentativa é consumida sem ninguém trabalhar. Exigido:
  (a) PreToolUse Bash do agente principal com `cs-state dispatch` (qualquer forma, inclusive com um --tool-use-id
      inventado) é BLOQUEADO (exit 2) com mensagem que ensina o caminho certo (ferramenta Agent com o id da
      delegação na description). O CLI direto sem --tool-use-id também recusa (exit 1). Nada muda no board.
  (b) o despacho legítimo (hook pre-agent com tool_use_id) continua funcionando e grava o tool_use_id.
  (c) board legado com delegação DISPATCHED sem tool_use_id (despacho fantasma) tem saída no cs-state que NÃO
      consome tentativa: depois de reparar, a task tem a MESMA contagem de tentativas de antes do fantasma
      (`attempts` da task e `retries` da delegação) e ainda tem as 2 tentativas reais.
D-1-03 — o verification_command gerado traz `git status --porcelain -- <protected>` (árvore inteira): a sujeira
legítima de outra task em voo dentro de um protected_path faz o verify desta task sair 1. Exigido:
  (d) duas tasks em paralelo, territórios disjuntos; A deixa arquivo alterado (não commitado) no território dela, que
      é protected_paths de B; o verify de B PASSA se B só mexeu no próprio território (proteção relativa ao que a
      delegação de B mudou, não à árvore);
  (e) se B de fato altera um protected_path dela, o verify de B REPROVA com mensagem que nomeia o arquivo;
  (f) verificação adicional: o verification_command gerado não carrega checagem crua de árvore inteira para os
      protected_paths — OU, se carregar, rodá-lo no shell (como o subagente faz antes de submeter) com a sujeira de
      outra task respeita (d).

Escolhas onde o contrato não fixa detalhe:
  * Board legado (c): produzido em processo pelo caminho legado (`cmds.dispatch(..., tool_use_id=None)`, que é o que o
    `cs-state dispatch` do Bash fazia). Se o motor corrigido recusar esse caminho, o fantasma é escrito como um evento
    `delegation.dispatch` cru com as MESMAS ops do despacho legado (é exatamente o que existe no events.jsonl da cobaia).
  * Reparo (c): a interface é livre; o teste tenta, em ordem, (1) `cs-state retry --task T --findings ...` direto da
    delegação fantasma e (2) `cs-state return --task T --reason ...` seguido de `cs-state retry --task T --findings ...`.
    Vale o primeiro caminho que deixar a delegação mais recente em BRIEFED. Exige-se o efeito: tentativas intactas.
  * "Mensagem que ensina" (a): stderr cita a ferramenta `Agent` e a `description` (ou o id da delegação BRIEFED).
  * (d) com classe `feature` (2 territórios ⇒ task do po ACCEPTED antes do dev, como no WORKFLOW-E2E).
  * Recusa = exit 1 (hcore.Refused); bloqueio do guard = exit 2.
"""
import os
import shutil
import subprocess
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import fixture  # noqa: E402
import hcore  # noqa: E402
from test_faixas_aceite import agent_payload, bash_payload, board, hook  # noqa: E402
from test_workflow_e2e import (AC, E2E, TEST_DISCOUNT, VERIFY, VERIFY_ASSERT, commit_all, deleg,  # noqa: E402
                               task)

# teste de asserção FORA de tests/ (o VERIFY da task do po roda `discover -s tests` e não pode vê-lo)
VERIFY_B_ASSERT = "python3 -m unittest checks.test_discount"

LEAD = {}  # payload sem agent_id = agente principal


def _task_ids(root):
    return {t["id"] for t in board(root)["tasks"]}


class Base(E2E):
    def add_task_p(self, root, agent, path, title, wave=1, verify=VERIFY, protected=(), ref="src/billing/total.py:1"):
        before = _task_ids(root)
        args = ["add", "task", "--story", "US-1", "--agent", agent, "--title", title,
                "--goal", "%s porque FEAT-1 exige" % title, "--allowed-path", path, "--verify-cmd", verify,
                "--ac", AC, "--ref", ref, "--in", title, "--out", "tax: outra task", "--wave", str(wave), "--ready"]
        for p in protected:
            args += ["--protected-path", p]
        self.ok(root, *args)
        new = [t for t in _task_ids(root) if t not in before]
        self.assertEqual(len(new), 1, new)
        self.assertEqual(deleg(root, new[0])["state"], "BRIEFED")
        return new[0]

    def submit_only(self, root, tid, agent, rel, txt):
        """Subagente escreve no próprio território e submete (sem verify)."""
        self.implement(root, tid, agent, rel, txt)


# ====================================================================== D-1-02
class TestDespachoSoDeEstado(Base):
    def _briefed(self, verify=VERIFY):
        root = self.repo()
        if verify == VERIFY_ASSERT:
            fixture.write(root, "tests/test_discount.py", TEST_DISCOUNT)
            commit_all(root)
        self.process(root, "pequena")
        t = self.add_task(root, "dev-billing", "src/billing/discount.py", "criar desconto", verify=verify)
        self.ok(root, "session", "execute")
        return root, t

    # ---------------------------------------------------------------- (a)
    def test_a_lead_rodando_cs_state_dispatch_pelo_bash_e_bloqueado_com_mensagem_que_ensina(self):
        root, t = self._briefed()
        d = deleg(root, t)
        model = d["route"]["model"]
        cmds = [
            ".swarm/bin/cs-state dispatch --task %s --model %s" % (t, model),
            ".swarm/bin/cs-state dispatch %s --model %s" % (t, model),
            "cs-state dispatch --task %s --model %s" % (t, model),
            ".swarm/bin/cs-state dispatch --task %s --model %s --tool-use-id tu-inventado" % (t, model),
        ]
        for cmd in cmds:
            with self.subTest(cmd=cmd):
                code, _, err = hook(root, "pre-bash", bash_payload(root, cmd, LEAD))
                self.assertEqual(code, 2, "D-1-02: `%s` pelo Bash do agente principal deveria ser BLOQUEADO (despacho só "
                                          "de estado, sem subagente); exit %d %s" % (cmd, code, err))
                self.assertIn("Agent", err, "a mensagem deve ensinar o caminho certo (ferramenta Agent): " + err)
                self.assertTrue("description" in err or d["id"] in err,
                                "a mensagem deve dizer como despachar (id %s na description do Agent): %s" % (d["id"], err))
        b = deleg(root, t)
        self.assertEqual((b["state"], task(root, t)["attempts"]), ("BRIEFED", 0), "bloqueio não muda o board")
        # o resto da orquestração do lead pelo Bash continua liberado
        for cmd in (".swarm/bin/cs-state next", ".swarm/bin/cs-state status"):
            code, _, err = hook(root, "pre-bash", bash_payload(root, cmd, LEAD))
            self.assertEqual(code, 0, "%s deveria passar: %s" % (cmd, err))

    def test_a_cli_direto_sem_tool_use_id_recusa_dispatch(self):
        root, t = self._briefed()
        model = deleg(root, t)["route"]["model"]
        self.refused(root, "dispatch", "--task", t, "--model", model)
        self.assertEqual(deleg(root, t)["state"], "BRIEFED", "recusa não muda a delegação")
        self.assertEqual(task(root, t)["attempts"], 0, "recusa não consome tentativa")
        self.assertIsNone(deleg(root, t).get("tool_use_id"))

    # ---------------------------------------------------------------- (b)
    def test_b_despacho_legitimo_via_hook_grava_tool_use_id_e_segue_o_fluxo(self):
        root, t = self._briefed()
        self.dispatch(root, t, "dev-billing", "tu-legit-1")
        d = deleg(root, t)
        self.assertEqual((d["state"], d.get("tool_use_id"), task(root, t)["status"], task(root, t)["attempts"]),
                         ("DISPATCHED", "tu-legit-1", "IN_PROGRESS", 1))
        self.implement(root, t, "dev-billing", "src/billing/discount.py", "RATE = 30\n")
        self.verify_pass(root, t)
        self.review(root, t)
        self.accept(root, t)
        self.close_session(root)
        self.assert_coerente(root)

    # ---------------------------------------------------------------- (c)
    def _fantasma(self, root, t):
        """Board legado: delegação DISPATCHED com tool_use_id null (o que o `cs-state dispatch` do Bash produzia)."""
        import cmds
        import engine
        d = deleg(root, t)
        model = d["route"]["model"]
        try:
            cmds.dispatch(root, "lead", t, model=model, tool_use_id=None, procedencia="declarada-cli")
        except hcore.Refused:
            def build(ctx):
                tt = ctx.find("task", t)
                dd = engine.latest_deleg(tt)
                r = engine.ref
                base = engine.git_dirty(ctx.root)
                ops = [["set", r("deleg", dd["id"]), "state", "DISPATCHED"],
                       ["set", r("deleg", dd["id"]), "updated_at", hcore.now_iso()],
                       ["set", r("task", t), "status", "IN_PROGRESS"],
                       ["inc", r("task", t), "attempts", 1],
                       ["set", r("deleg", dd["id"]), "attempt", tt["attempts"] + 1],
                       ["set", r("deleg", dd["id"]), "dispatched_at", hcore.now_iso()],
                       ["set", r("deleg", dd["id"]), "tool_use_id", None],
                       ["set", r("deleg", dd["id"]), "model", {"name": model, "procedencia": "declarada-cli"}],
                       ["set", r("deleg", dd["id"]), "baseline", base if base is not None else {"__nogit__": True}],
                       ["set", r("task", t), "reject_reason", None]]
                if not tt.get("change_base") and hasattr(engine, "new_change_base"):
                    cb = engine.new_change_base(ctx.root, base)
                    if cb:
                        ops.append(["set", r("task", t), "change_base", cb])
                return [engine.Event("delegation.dispatch", dd["id"], ops,
                                     {"args": {"model": model, "tool_use_id": None}, "problems": []})]
            engine.commit(root, "lead", build)
        d = deleg(root, t)
        self.assertEqual((d["state"], d.get("tool_use_id")), ("DISPATCHED", None), "fixture: fantasma não montado")
        self.assertEqual(task(root, t)["attempts"], 1, "fixture: o fantasma consumiu a tentativa (o defeito)")

    def _reparar(self, root, t):
        why = "despacho fantasma: cs-state dispatch pelo Bash, nenhum subagente foi lançado"
        caminhos = [
            [("retry", "--task", t, "--findings", why)],
            [("return", "--task", t, "--reason", why), ("retry", "--task", t, "--findings", why)],
        ]
        tentados = []
        for caminho in caminhos:
            if deleg(root, t)["state"] == "BRIEFED":
                break
            for args in caminho:
                code, out, err = self.cs(root, *args)
                tentados.append("%s → %d %s" % (" ".join(args), code, (out + err).strip()[-200:]))
                if code != 0:
                    break
        self.assertEqual(deleg(root, t)["state"], "BRIEFED",
                         "D-1-02: a delegação fantasma (DISPATCHED sem tool_use_id) precisa de saída no cs-state que a "
                         "devolva a BRIEFED. Tentado:\n" + "\n".join(tentados))

    def cs(self, root, *args):
        from test_faixas_aceite import cs
        return cs(root, *args)

    def test_c_despacho_fantasma_reparado_nao_consome_tentativa(self):
        root, t = self._briefed()
        antes = (task(root, t)["attempts"], int(deleg(root, t).get("retries") or 0))
        self._fantasma(root, t)
        self._reparar(root, t)
        depois = (task(root, t)["attempts"], int(deleg(root, t).get("retries") or 0))
        self.assertEqual(depois, antes,
                         "D-1-02: reparar o despacho fantasma não pode consumir tentativa — (attempts, retries) antes=%r "
                         "depois=%r" % (antes, depois))

    def test_c_depois_do_reparo_a_task_ainda_tem_as_duas_tentativas_reais(self):
        root, t = self._briefed(verify=VERIFY_ASSERT)
        self._fantasma(root, t)
        self._reparar(root, t)
        # 1ª tentativa REAL (com subagente): reprova
        self.dispatch(root, t, "dev-billing", "tu-real-1")
        self.assertEqual(deleg(root, t).get("tool_use_id"), "tu-real-1")
        self.implement(root, t, "dev-billing", "src/billing/discount.py", "RATE = 10\n")
        self.verify_fail(root, t)
        self.assertNotEqual(task(root, t)["status"], "BLOCKED",
                            "1ª tentativa real reprovada não pode esgotar a task (o fantasma não conta)")
        self.ok(root, "retry", "--task", t, "--findings", "RATE deve ser 30 (tests/test_discount.py)")
        # 2ª tentativa REAL: passa
        self.dispatch(root, t, "dev-billing", "tu-real-2")
        self.implement(root, t, "dev-billing", "src/billing/discount.py", "RATE = 30\n")
        self.verify_pass(root, t)
        self.review(root, t)
        self.accept(root, t)
        self.assertEqual(task(root, t)["attempts"], 2, "só as duas tentativas com subagente contam")
        self.close_session(root)
        self.assert_coerente(root)


# ====================================================================== D-1-03
class TestVerifyIsolado(Base):
    def _paralelo(self, b_protected=("src/users/**",), verify_b=VERIFY):
        """classe feature: po ACCEPTED; A (dev-users) e B (dev-billing) na mesma onda, territórios disjuntos;
        protected_paths de B cobre o território de A."""
        root = self.repo()
        if verify_b == VERIFY_B_ASSERT:
            fixture.write(root, "checks/__init__.py", "")
            fixture.write(root, "checks/test_discount.py", TEST_DISCOUNT)
            commit_all(root)
        self.process(root, "feature")
        po = self.add_task_p(root, "po", "docs/stories/US-1.md", "detalhar a story", wave=1, ref="docs/stories/README.md:1")
        a = self.add_task_p(root, "dev-users", "src/users/discount.py", "elegibilidade do desconto", wave=2,
                            ref="src/users/model.py:1")
        b = self.add_task_p(root, "dev-billing", "src/billing/discount.py", "criar desconto", wave=2,
                            protected=b_protected, verify=verify_b)
        self.ok(root, "session", "execute")
        self.full_task(root, po, "po", "docs/stories/US-1.md", "# US-1 detalhada\n", "tu-po")
        return root, a, b

    def _fecha(self, root, *tids):
        for t in tids:
            if deleg(root, t)["state"] == "RETURNED":
                self.verify_pass(root, t)
            self.review(root, t)
            self.accept(root, t)
        self.close_session(root, final_review=True)
        self.assert_coerente(root)

    # ---------------------------------------------------------------- (d)
    def test_d_sujeira_da_task_irma_no_protected_de_b_nao_reprova_b(self):
        root, a, b = self._paralelo()
        self.dispatch(root, a, "dev-users", "tu-a")
        self.dispatch(root, b, "dev-billing", "tu-b")
        # A trabalha (não commitado) dentro do território dela == protected_paths de B
        self.submit_only(root, a, "dev-users", "src/users/discount.py", "ELIGIBLE = True\n")
        self.submit_only(root, b, "dev-billing", "src/billing/discount.py", "RATE = 30\n")
        out = self.ok(root, "verify", "--task", b)
        self.assertIn("verify PASS", out,
                      "D-1-03: B só mexeu no próprio território; a sujeira legítima de A (em voo, não commitada) em "
                      "src/users/** não pode reprovar B — proteção relativa à delegação de B, não à árvore:\n" + out)
        self.assertEqual(deleg(root, b)["state"], "VERIFIED")
        self._fecha(root, a, b)

    def test_d_sujeira_da_irma_ja_presente_antes_do_despacho_de_b_nao_reprova_b(self):
        root, a, b = self._paralelo()
        self.dispatch(root, a, "dev-users", "tu-a")
        self.submit_only(root, a, "dev-users", "src/users/discount.py", "ELIGIBLE = True\n")
        self.dispatch(root, b, "dev-billing", "tu-b")  # A já sujou a árvore antes de B sair
        self.submit_only(root, b, "dev-billing", "src/billing/discount.py", "RATE = 30\n")
        out = self.ok(root, "verify", "--task", b)
        self.assertIn("verify PASS", out, "D-1-03: sujeira pré-existente de A não é mudança de B:\n" + out)
        self._fecha(root, a, b)

    def test_d_retentativa_de_b_com_sujeira_da_irma_ainda_passa(self):
        """não regressão D-0-13: retry sobre trabalho já na árvore, com a irmã suja no protected de B."""
        root, a, b = self._paralelo(verify_b=VERIFY_B_ASSERT)
        self.dispatch(root, a, "dev-users", "tu-a")
        self.dispatch(root, b, "dev-billing", "tu-b1")
        self.submit_only(root, a, "dev-users", "src/users/discount.py", "ELIGIBLE = True\n")
        self.submit_only(root, b, "dev-billing", "src/billing/discount.py", "RATE = 10\n")
        self.verify_fail(root, b)  # reprova pela ASSERÇÃO (RATE errado) — hoje também pela árvore; ambos REPROVAM
        self.ok(root, "retry", "--task", b, "--findings", "RATE deve ser 30 (checks/test_discount.py)")
        self.dispatch(root, b, "dev-billing", "tu-b2")
        self.submit_only(root, b, "dev-billing", "src/billing/discount.py", "RATE = 30\n")
        out = self.ok(root, "verify", "--task", b)
        self.assertIn("verify PASS", out, "D-1-03 + D-0-13: retry de B com a irmã suja no protected:\n" + out)
        self.assertEqual(task(root, b)["attempts"], 2)
        self._fecha(root, a, b)

    # ---------------------------------------------------------------- (e)
    def test_e_b_alterando_o_proprio_protected_path_reprova_com_mensagem_clara(self):
        root, a, b = self._paralelo(b_protected=("src/billing/total.py",))
        self.dispatch(root, b, "dev-billing", "tu-b")
        fixture.write(root, "src/billing/total.py", "def total(items):\n    return round(sum(items))\n")  # escapou do guard
        self.submit_only(root, b, "dev-billing", "src/billing/discount.py", "RATE = 30\n")
        out = self.verify_fail(root, b)
        self.assertIn("src/billing/total.py", out, "a reprovação deve nomear o protected_path tocado:\n" + out)

    def test_e_b_alterando_protected_no_territorio_da_irma_reprova_mesmo_com_a_irma_suja(self):
        root, a, b = self._paralelo()
        self.dispatch(root, a, "dev-users", "tu-a")
        self.dispatch(root, b, "dev-billing", "tu-b")
        self.submit_only(root, a, "dev-users", "src/users/discount.py", "ELIGIBLE = True\n")
        fixture.write(root, "src/users/model.py", "AGE = 16\n")  # B tocou um protected seu (não é trabalho de A)
        self.submit_only(root, b, "dev-billing", "src/billing/discount.py", "RATE = 30\n")
        out = self.verify_fail(root, b)
        self.assertIn("src/users/model.py", out, "a reprovação deve nomear o protected_path tocado:\n" + out)
        self.assertNotIn("src/users/discount.py", out.split("REPROVOU", 1)[-1],
                         "o trabalho legítimo de A não pode ser citado como culpa de B:\n" + out)

    # ---------------------------------------------------------------- (f)
    def test_f_verification_command_nao_checa_a_arvore_inteira_para_protected(self):
        """Verificação adicional. Aceita: (1) o comando não traz `git status --porcelain`/`git diff --quiet` crus sobre
        protected_paths; OU (2) se trouxer, rodá-lo no shell (como o subagente faz antes de submeter) com a sujeira
        legítima da irmã no protected respeita (d) — sai 0."""
        root, a, b = self._paralelo()
        vc = task(root, b)["verification_command"]
        cru = ("git status --porcelain" in vc) or ("git diff --quiet" in vc)
        if not cru:
            return
        self.dispatch(root, a, "dev-users", "tu-a")
        self.dispatch(root, b, "dev-billing", "tu-b")
        self.submit_only(root, a, "dev-users", "src/users/discount.py", "ELIGIBLE = True\n")
        fixture.write(root, "src/billing/discount.py", "RATE = 30\n")
        p = subprocess.run(vc, shell=True, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        self.assertEqual(p.returncode, 0,
                         "D-1-03: o verification_command de B checa a árvore inteira (%r) e a sujeira legítima de A em "
                         "src/users/** o faz sair %d — o subagente B não consegue nem passar no próprio check"
                         % (vc, p.returncode))


if __name__ == "__main__":
    unittest.main()
