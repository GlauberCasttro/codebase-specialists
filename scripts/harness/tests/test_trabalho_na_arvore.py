"""ORÁCULO — D-0-13: trabalho de tentativa anterior já na árvore (retentativa / retomada sobre arquivo sujo).

Defeito observado (cobaia real repositório-piloto (projeto-legado), TASK-02-002-KEY): no `dispatch` o motor fotografa o sha de cada
arquivo sujo (inclusive os de allowed_paths) como "baseline" da delegação. Numa RETENTATIVA (reject → retry → dispatch)
ou numa RETOMADA (escalate → retry --decision → dispatch) o código da tentativa anterior continua modificado e não
commitado; o `verify` compara com essa baseline, não vê mudança e reprova com
"declarado em files_changed mas não alterado segundo git: <arquivo>". O código está certo, mas nunca passa.

Comportamento exigido (observável pela CLI real engine/state.py e pelo guard real engine/guard.py, em subprocesso, num
repo git temporário de fixture.make_repo; nada de mock do motor). Este arquivo é contrato: quem implementa não o edita.

BASE DA TASK (escolha deste oráculo, como comportamento observável — não prescreve implementação):
  * "Mudança da TASK" = arquivo de allowed_paths cujo conteúdo na árvore difere do conteúdo que ele tinha no commit
    HEAD vigente no PRIMEIRO dispatch da task (ausente no HEAD conta como diferente se existe na árvore; existente no
    HEAD e apagado conta como diferente). Ao longo de todas as delegações da mesma task (retry, retomada) essa base não
    muda. Nos testes o HEAD não se move entre as tentativas (ninguém commita), então "HEAD do 1º dispatch" e "sha anterior
    à 1ª escrita" coincidem — qualquer das duas implementações satisfaz o contrato.
  * Arquivo FORA de allowed_paths continua julgado contra a fotografia do dispatch DESTA delegação: sujeira alheia que já
    estava na árvore antes do (re)dispatch não vira mudança da task; escrita nova fora do território depois do dispatch
    continua reprovando com "alterado FORA de allowed_paths".
  * Declarar em files_changed um arquivo de allowed_paths que NÃO difere da base da task continua reprovando com
    "declarado em files_changed mas não alterado segundo git: <arquivo>".
  * Ondas paralelas: o arquivo de outra delegação em voo/fechada não é acusado como fora do território (como hoje).

Falha "legítima" da 1ª tentativa: o verification_command é `python3 -m unittest tests.test_gate`, que falha por
ASSERÇÃO (exit 1) enquanto um marcador FORA do repo não existe; "consertar" = criar o marcador (nenhum arquivo do repo
muda, então a árvore fica exatamente como o dev deixou).

Estado hoje: 1 e 2 (TestNovaTentativa, TestEscaladaRetomada) FALHAM pela mensagem do defeito; 3–5 (TestTerritorio,
TestDeclaracaoVazia, TestOndasParalelas) passam — são guardas de não regressão da correção.
"""
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import fixture  # noqa: E402
from test_workflow_e2e import E2E, AC, VERIFY, board, commit_all, deleg, hook, task, write_payload  # noqa: E402

VERIFY_GATE = "python3 -m unittest tests.test_gate"
DEFEITO = "declarado em files_changed mas não alterado segundo git"
FORA = "alterado FORA de allowed_paths"

TEST_GATE = """import os
import unittest

MARK = %r


class G(unittest.TestCase):
    def test_gate(self):
        self.assertTrue(os.path.exists(MARK), 'portao fechado: marcador ausente')
"""

TRACKED = "src/billing/tax.py"       # existe no HEAD: o dev MODIFICA e não commita (caso do repositório-piloto)
NEW = "src/billing/discount.py"      # não existe no HEAD: o dev CRIA e não commita
OUTSIDE = "src/users/model.py"       # território de outro agente


class Base(E2E):
    def gate_repo(self, open_gate=False):
        root = self.repo()
        mark = os.path.join(self.outside_dir(), "gate-open")
        fixture.write(root, "tests/test_gate.py", TEST_GATE % mark)
        commit_all(root, "portão de verify controlado por marcador externo")
        if open_gate:
            self.open_gate(mark)
        return root, mark

    @staticmethod
    def open_gate(mark):
        with open(mark, "w") as f:
            f.write("ok\n")

    def write_in_territory(self, root, tid, agent, rel, txt):
        code, _, err = hook(root, "pre-write", write_payload(root, rel, {"agent_id": "ag-%s" % tid, "agent_type": agent}))
        self.assertEqual(code, 0, "subagente %s escrevendo %s no próprio território: %s" % (agent, rel, err))
        fixture.write(root, rel, txt)

    def submit(self, root, tid, agent, *files):
        args = ["submit", "--task", tid]
        for f in files:
            args += ["--files-changed", f]
        self.ok(root, *(args + ["--check", "unittest: OK", "--risk", "nenhum", "--handoff-notes", "ok"]), actor=agent)
        self.assertEqual(deleg(root, tid)["state"], "RETURNED")

    def verify_out(self, root, tid):
        return self.ok(root, "verify", "--task", tid)

    def assert_pass(self, root, tid, why):
        out = self.verify_out(root, tid)
        self.assertNotIn(DEFEITO, out, "D-0-13: %s — o arquivo já alterado na árvore é mudança da TASK:\n%s" % (why, out))
        self.assertIn("verify PASS", out, "%s:\n%s" % (why, out))
        self.assertEqual(deleg(root, tid)["state"], "VERIFIED")

    def finish(self, root, tid):
        self.review(root, tid)
        self.accept(root, tid)
        self.close_session(root)
        self.assert_coerente(root)

    def first_attempt_rejected(self, rel, txt="RATE = 30\n"):
        """1ª tentativa: dev escreve `rel` (não commita), submete, verify reprova por ASSERÇÃO (portão fechado) → REJECTED
        → retry. Devolve (root, mark, tid) com a delegação BRIEFED de novo e `rel` ainda modificado na árvore."""
        root, mark = self.gate_repo()
        self.process(root, "pequena")
        t = self.add_task(root, "dev-billing", rel, "aplicar desconto", verify=VERIFY_GATE)
        self.ok(root, "session", "execute")
        self.dispatch(root, t, "dev-billing", "tu-1")
        self.write_in_territory(root, t, "dev-billing", rel, txt)
        self.submit(root, t, "dev-billing", rel)
        out = self.verify_fail(root, t)
        self.assertNotIn(DEFEITO, out, "1ª tentativa: %s foi escrito depois do dispatch" % rel)
        self.ok(root, "retry", "--task", t, "--findings", "portão fechado: ambiente consertado pelo lead")
        self.assertEqual(deleg(root, t)["state"], "BRIEFED")
        return root, mark, t


# ------------------------------------------------------------------ 1. NOVA-TENTATIVA (falha hoje)
class TestNovaTentativa(Base):
    def _caso(self, rel):
        root, mark, t = self.first_attempt_rejected(rel)
        with open(os.path.join(root, rel)) as f:
            antes = f.read()
        self.open_gate(mark)  # conserto fora do repo: a árvore fica como o dev deixou
        self.dispatch(root, t, "dev-billing", "tu-2")
        # o dev NÃO reescreve: o código da tentativa anterior já está certo e na árvore
        self.submit(root, t, "dev-billing", rel)
        self.assert_pass(root, t, "retry sobre %s já alterado" % rel)
        with open(os.path.join(root, rel)) as f:
            self.assertEqual(f.read(), antes)
        self.assertEqual(task(root, t)["attempts"], 2)
        self.finish(root, t)

    def test_retry_arquivo_rastreado_modificado_nao_precisa_reescrever(self):
        self._caso(TRACKED)

    def test_retry_arquivo_novo_nao_rastreado_nao_precisa_reescrever(self):
        self._caso(NEW)


# ------------------------------------------------------------------ 2. ESCALADA-RETOMADA (falha hoje)
class TestEscaladaRetomada(Base):
    def _caso(self, rel):
        root, _ = self.gate_repo(open_gate=True)
        self.process(root, "pequena")
        t = self.add_task(root, "dev-billing", rel, "aplicar desconto", verify=VERIFY_GATE)
        self.ok(root, "session", "execute")
        self.dispatch(root, t, "dev-billing", "tu-1")
        self.write_in_territory(root, t, "dev-billing", rel, "RATE = 30\n")
        self.ok(root, "escalate", "--task", t, "--reason", "AC-1 contradiz o épico")
        self.assertEqual((deleg(root, t)["state"], task(root, t)["status"]), ("ESCALATED", "BLOCKED"))
        self.ok(root, "retry", "--task", t, "--decision", "AC-1 vale como escrito; o código já feito serve")
        self.assertEqual(deleg(root, t)["state"], "BRIEFED")
        self.dispatch(root, t, "dev-billing", "tu-2")
        self.submit(root, t, "dev-billing", rel)  # sem reescrever
        self.assert_pass(root, t, "retomada (escalate → retry --decision) sobre %s já alterado" % rel)
        self.finish(root, t)

    def test_escalate_retomada_arquivo_rastreado(self):
        self._caso(TRACKED)

    def test_escalate_retomada_arquivo_novo(self):
        self._caso(NEW)


# ------------------------------------------------------------------ 3. TERRITÓRIO CONTINUA VALENDO (guarda)
class TestTerritorio(Base):
    def test_sujeira_alheia_antes_do_redispatch_nao_vira_mudanca_da_task(self):
        root, mark, t = self.first_attempt_rejected(TRACKED, "RATE = 10\n")
        fixture.write(root, OUTSIDE, "AGE = 21  # outra pessoa, fora da task\n")  # suja ANTES do redispatch
        self.open_gate(mark)
        self.dispatch(root, t, "dev-billing", "tu-2")
        self.write_in_territory(root, t, "dev-billing", TRACKED, "RATE = 30\n")
        self.submit(root, t, "dev-billing", TRACKED)
        out = self.verify_out(root, t)
        self.assertNotIn(OUTSIDE, out, "sujeira alheia pré-existente ao redispatch não é da task:\n" + out)
        self.assertIn("verify PASS", out, out)
        self.assertEqual(deleg(root, t)["state"], "VERIFIED")

    def test_escrita_nova_fora_do_territorio_depois_do_redispatch_reprova(self):
        root, mark, t = self.first_attempt_rejected(TRACKED, "RATE = 10\n")
        self.open_gate(mark)
        self.dispatch(root, t, "dev-billing", "tu-2")
        self.write_in_territory(root, t, "dev-billing", TRACKED, "RATE = 30\n")
        fixture.write(root, OUTSIDE, "AGE = 21  # escrita nova fora do território\n")
        self.submit(root, t, "dev-billing", TRACKED)
        out = self.verify_out(root, t)
        self.assertIn("REPROVOU", out, out)
        self.assertIn("%s: %s" % (FORA, OUTSIDE), out)
        self.assertEqual(deleg(root, t)["state"], "REJECTED")


# ------------------------------------------------------------------ 4. DECLARAÇÃO VAZIA CONTINUA REPROVANDO (guarda)
class TestDeclaracaoVazia(Base):
    def _assert_vazia(self, root, t, rel):
        out = self.verify_out(root, t)
        self.assertIn("REPROVOU", out, out)
        self.assertIn("%s: %s" % (DEFEITO, rel), out, "mensagem clara apontando o arquivo declarado e não feito")
        self.assertEqual(deleg(root, t)["state"], "REJECTED")

    def test_primeira_tentativa_sem_alteracao_reprova(self):
        root, _ = self.gate_repo(open_gate=True)
        self.process(root, "pequena")
        t = self.add_task(root, "dev-billing", TRACKED, "aplicar desconto", verify=VERIFY_GATE)
        self.ok(root, "session", "execute")
        self.dispatch(root, t, "dev-billing", "tu-1")
        self.submit(root, t, "dev-billing", TRACKED)
        self._assert_vazia(root, t, TRACKED)

    def test_retry_com_arquivo_revertido_ao_head_reprova(self):
        root, mark, t = self.first_attempt_rejected(TRACKED)
        fixture.git(root, "checkout", "--", TRACKED)  # a tentativa anterior foi desfeita: nada difere do HEAD da task
        self.open_gate(mark)
        self.dispatch(root, t, "dev-billing", "tu-2")
        self.submit(root, t, "dev-billing", TRACKED)
        self._assert_vazia(root, t, TRACKED)

    def test_retry_com_arquivo_novo_apagado_reprova(self):
        root, mark, t = self.first_attempt_rejected(NEW)
        os.remove(os.path.join(root, NEW))  # criado e apagado: igual ao HEAD (ausente)
        self.open_gate(mark)
        self.dispatch(root, t, "dev-billing", "tu-2")
        self.submit(root, t, "dev-billing", NEW)
        self._assert_vazia(root, t, NEW)


# ------------------------------------------------------------------ 5. ONDAS PARALELAS não regridem (guarda)
class TestOndasParalelas(Base):
    def _feature_com_po(self, root):
        self.process(root, "feature")
        po = self.add_task(root, "po", "docs/stories/US-1.md", "detalhar a story", wave=1, ref="docs/stories/README.md:1")
        t_bil = self.add_task(root, "dev-billing", NEW, "criar desconto", wave=2, verify=VERIFY)
        t_usr = self.add_task(root, "dev-users", "src/users/discount.py", "elegibilidade do desconto", wave=2,
                              verify=VERIFY, ref="src/users/model.py:1")
        self.ok(root, "session", "execute")
        self.full_task(root, po, "po", "docs/stories/US-1.md", "# US-1 detalhada\n", "tu-po")
        return t_bil, t_usr

    def test_duas_delegacoes_na_mesma_onda_nao_acusam_o_arquivo_uma_da_outra(self):
        root = self.repo()
        t_bil, t_usr = self._feature_com_po(root)
        self.dispatch(root, t_bil, "dev-billing", "tu-bil")
        self.dispatch(root, t_usr, "dev-users", "tu-usr")
        self.implement(root, t_bil, "dev-billing", NEW, "RATE = 30\n")
        self.implement(root, t_usr, "dev-users", "src/users/discount.py", "ELIGIBLE = True\n")
        for t in (t_bil, t_usr):
            out = self.verify_out(root, t)
            self.assertNotIn(FORA, out, out)
            self.assertIn("verify PASS", out, out)

    def test_retry_de_uma_com_a_irma_ja_aceita_e_nao_commitada(self):
        root = self.repo()
        t_bil, t_usr = self._feature_com_po(root)
        self.dispatch(root, t_bil, "dev-billing", "tu-bil")
        self.dispatch(root, t_usr, "dev-users", "tu-usr")
        self.implement(root, t_bil, "dev-billing", NEW, "RATE = 10\n")
        self.implement(root, t_usr, "dev-users", "src/users/discount.py", "ELIGIBLE = True\n")
        self.verify_pass(root, t_bil)
        self.review(root, t_bil, "FAIL")
        self.ok(root, "reject", "--task", t_bil, "--reason", "review FAIL: RATE deve ser 30")
        self.verify_pass(root, t_usr)
        self.review(root, t_usr)
        self.accept(root, t_usr)  # irmã ACCEPTED, arquivo dela continua não commitado na árvore
        self.ok(root, "retry", "--task", t_bil, "--findings", "RATE deve ser 30")
        self.dispatch(root, t_bil, "dev-billing", "tu-bil-2")
        self.implement(root, t_bil, "dev-billing", NEW, "RATE = 30\n")
        out = self.verify_out(root, t_bil)
        self.assertNotIn("src/users/discount.py", out, "arquivo da irmã aceita não é da task:\n" + out)
        self.assertIn("verify PASS", out, out)


if __name__ == "__main__":
    unittest.main()
