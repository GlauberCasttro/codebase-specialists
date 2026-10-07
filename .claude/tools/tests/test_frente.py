"""Testes de regressão do G1 da frente harness-dev (motor da frente e sessão): contrato.py, frente.py, guard-estado.py,
sessao.py, estado_lib.py. Complementam o oráculo da frente (campanhas/harness-dev/oraculo) com casos de borda.
Rodar nos 2 Pythons: cd .claude/tools && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests
Tudo em diretórios temporários; nunca toca o projeto vivo.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import warnings

warnings.simplefilter("ignore", ResourceWarning)
TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLAUDE = os.path.dirname(TOOLS)
PY = sys.executable
MODELOS = os.path.join(CLAUDE, "skills", "criar-frente", "references", "modelos")


def escrever(base, rel, txt):
    p = os.path.join(base, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(txt)
    return p


def ler(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def git(cwd, *a):
    e = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    p = subprocess.run(["git", "-C", cwd, "-c", "user.email=ana@exemplo.invalid", "-c", "user.name=Ana"] + list(a),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=e)
    return p.returncode, p.stdout.decode().strip()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="tf-"))
        self.sk = os.path.join(self.tmp, "proj")
        shutil.copytree(CLAUDE, os.path.join(self.sk, ".claude"), ignore=shutil.ignore_patterns(
            "__pycache__", "*.pyc", "state", ".DS_Store"))
        for rel, txt in ((".claude/state/WORKFLOW.md", "# WORKFLOW\n\nnota humana\n"),
                         (".claude/state/RESUME.md", "# RESUME\n\n## Onde paramos\n- x\n"),
                         ("SKILL.md", "# produto\n"), ("VERSION", "0.0.0\n"), ("a/um.py", "def um():\n    return 1\n"),
                         ("campanhas/README.md", "# campanhas\n"), (".gitignore", "local/\ncampanhas/*/.auto-correcao/\n")):
            escrever(self.sk, rel, txt)
        git(self.sk, "init", "-q")
        git(self.sk, "add", "-A")
        git(self.sk, "commit", "--no-verify", "-qm", "base")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_py(self, script, *a, stdin=None):
        env = {k: v for k, v in os.environ.items() if not (k.startswith("CS_") or k.startswith("GIT_"))}
        env.update({"CS_DEV_SKILL_DIR": self.sk, "PYTHONDONTWRITEBYTECODE": "1", "HOME": self.tmp})
        p = subprocess.run([PY, os.path.join(self.sk, ".claude", "tools", script)] + list(a), cwd=self.sk, env=env,
                           input=(stdin or "").encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return p.returncode, p.stdout.decode(), p.stderr.decode()

    def guard(self, rel, tool="Write", **ti):
        ti["file_path"] = os.path.join(self.sk, rel)
        rc, out, _ = self.run_py("guard-estado.py", stdin=json.dumps({"tool_name": tool, "tool_input": ti}))
        self.assertEqual(rc, 0)
        return json.loads(out)["hookSpecificOutput"]["permissionDecision"] if out.strip() else "allow"


class ContratoBordas(Base):
    def test_modelos_da_skill_passam_no_contrato(self):
        for e in ("E1", "E2", "E5"):
            self.assertEqual(self.run_py("contrato.py", "etapa", e, os.path.join(MODELOS, e + ".md"))[0], 0, e)
        self.assertEqual(self.run_py("contrato.py", "frente", os.path.join(MODELOS, "FRENTE.md"))[0], 0)
        self.assertEqual(self.run_py("contrato.py", "complexidade", os.path.join(MODELOS, "TASK.md"))[0], 0)

    def test_task_isolada_e_nome(self):
        txt = ler(os.path.join(MODELOS, "TASK.md"))
        bom = escrever(self.tmp, "t/02-TASK-MOTOR-SENHA.md", txt)
        self.assertEqual(self.run_py("contrato.py", "task", bom)[0], 0)
        ruim = escrever(self.tmp, "t/02-task-motor.md", txt)
        rc, out, _ = self.run_py("contrato.py", "task", ruim, "--json")
        self.assertEqual(rc, 2)
        self.assertTrue(any("task_nome_invalido" in x["codigo"] for x in json.loads(out)["lacunas"]))

    def test_sonda_e_uso(self):
        self.assertEqual(self.run_py("contrato.py", "--sonda")[0], 0)
        self.assertEqual(self.run_py("contrato.py")[0], 3)


class CriacaoBordas(Base):
    def test_e1_com_id_diferente_reprova(self):
        self.assertEqual(self.run_py("frente.py", "criar", "iniciar", "iter19-preauth-senha", "--demanda", "x")[0], 0)
        p = escrever(self.tmp, "E1.md", ler(os.path.join(MODELOS, "E1.md")).replace(
            "FRENTE-ID: iter19-preauth-senha", "FRENTE-ID: outra"))
        rc, out, _ = self.run_py("frente.py", "criar", "propor", "iter19-preauth-senha", "--etapa", "E1", "--arquivo",
                                 p, "--json")
        self.assertEqual(rc, 2)
        self.assertIn("id_difere", out)

    def test_status_idle_e_workflow_preservado_na_adocao(self):
        j = json.loads(self.run_py("frente.py", "status", "--json")[1])
        self.assertEqual((j["estado"], j["workflow_em_dia"]), ("IDLE", True))
        ac = os.path.join(self.sk, ".claude", "tools", "ac", "ac.py")
        subprocess.run([PY, ac, "--work", "campanhas/velha", "init", "--target", ".", "--scope", "b/x.py"],
                       cwd=self.sk, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(self.run_py("frente.py", "adotar", "velha", "--dry-run")[0], 0)
        self.assertFalse(os.path.exists(os.path.join(self.sk, ".claude", "state", "frentes.json")))
        self.assertEqual(self.run_py("frente.py", "adotar", "velha")[0], 0)
        wf = ler(os.path.join(self.sk, ".claude", "state", "WORKFLOW.md"))
        self.assertIn("nota humana", wf)
        self.assertIn("**Estado:** IN_PROGRESS", wf)
        self.assertTrue(json.loads(self.run_py("frente.py", "status", "--json")[1])["workflow_em_dia"])

    def test_help_cita_tudo(self):
        rc, out, _ = self.run_py("frente.py", "--help")
        self.assertEqual(rc, 0)
        for s in ("criar iniciar", "criar propor", "criar aprovar", "criar rejeitar", "criar abrir", "checklist",
                  "adotar", "task marcar", "fechar plano", "fechar commit", "--dry-run", "--json", "--brief"):
            self.assertIn(s, out)


class GuardBordas(Base):
    def test_propostas_multiedit_e_archive(self):
        self.assertEqual(self.guard(".claude/state/frentes/x/propostas/E1.md", content="x"), "deny")
        self.assertEqual(self.guard(".claude/state/archive/x/notas/extra.md", content="x"), "deny")
        self.assertEqual(self.guard(".claude/state/INDEX-solto.md", content="x"), "allow")
        self.assertEqual(self.guard(".claude/state/frentes/x/HISTORICO.md", content="x"), "allow")
        rc, out, _ = self.run_py("guard-estado.py", stdin=json.dumps({"tool_name": "Write", "tool_input": {}}))
        self.assertIn("deny", out)

    def test_multiedit_done_sem_gate(self):
        rc, _, _ = self.run_py("frente.py", "criar", "iniciar", "demo", "--demanda", "x")
        self.assertEqual(rc, 0)
        st = os.path.join(self.sk, ".claude", "state", "frentes", "demo")
        # frente aberta por adoção não existe aqui; simula a E3 aprovada pelo evento (o hook lê eventos.jsonl)
        with open(os.path.join(st, "eventos.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"seq": 9, "tipo": "aprovacao", "etapa": "E3", "sha": "0" * 64, "ts": "t"}) + "\n")
        tarefa = ".claude/state/frentes/demo/TASKS/02-TASK-UM.md"
        escrever(self.sk, tarefa, "# 02-TASK-UM — x\n\nstatus: PENDENTE\ngate: PENDENTE\n\n## Handoff\n")
        self.assertEqual(self.guard(tarefa, "MultiEdit", edits=[{"old_string": "status: PENDENTE",
                                                                  "new_string": "status: DONE"}]), "deny")
        self.assertEqual(self.guard(tarefa, "MultiEdit", edits=[
            {"old_string": "status: PENDENTE", "new_string": "status: DONE"},
            {"old_string": "gate: PENDENTE", "new_string": "gate: PASS"},
            {"old_string": "## Handoff\n", "new_string": "## Handoff\n- feito com evidência\n"}]), "allow")


class SessaoBordas(Base):
    def test_campo_head_e_sem_state(self):
        rc, out, _ = self.run_py("sessao.py", "carimbo", "--field", "HEAD")
        self.assertEqual(out.strip(), git(self.sk, "rev-parse", "--short", "HEAD")[1])
        shutil.rmtree(os.path.join(self.sk, ".claude", "state"))
        j = json.loads(self.run_py("sessao.py", "frescor", "--json")[1])
        self.assertEqual(j["veredito"], "sem-state")

    def test_salvar_inicializa_estado(self):
        shutil.rmtree(os.path.join(self.sk, ".claude", "state"))
        self.assertEqual(self.run_py("sessao.py", "salvar", "--resumo", "primeira")[0], 0)
        for n in ("RESUME.md", "WORKFLOW.md", "BACKLOG.md", "DECISIONS.md", "logs/sessoes.jsonl"):
            self.assertTrue(os.path.exists(os.path.join(self.sk, ".claude", "state", n)), n)

    def test_carimbo_write_regrava_sem_duplicar(self):
        self.run_py("sessao.py", "carimbo", "--write")
        self.run_py("sessao.py", "carimbo", "--write")
        self.assertEqual(ler(os.path.join(self.sk, ".claude", "state", "RESUME.md")).count("resume-stamp"), 1)


if __name__ == "__main__":
    unittest.main()
