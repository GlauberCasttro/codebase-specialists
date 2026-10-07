"""Testes de regressão do G2 da feature harness-dev (orquestração, campanha e régua): tech_lead.py, exige-modelo.py,
custo.py, rh.py, e2e.py, campanha.py, portao.sh e os dados JSON. Complementam o oráculo da feature com casos de borda.
Rodar nos 2 Pythons: cd .claude/tools && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import warnings

warnings.simplefilter("ignore", ResourceWarning)
TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.dirname(os.path.dirname(TOOLS))
PY = sys.executable


def run(args, stdin="", env=None, cwd=None):
    e = {k: v for k, v in os.environ.items() if not (k.startswith("CS_") or k.startswith("GIT_"))}
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    e.update(env or {})
    p = subprocess.run(args, input=stdin.encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=e,
                       cwd=cwd or TOOLS)
    return p.returncode, p.stdout.decode(), p.stderr.decode()


def py(script, *a, **kw):
    return run([PY, os.path.join(TOOLS, script)] + list(a), **kw)


def escrever(base, rel, txt):
    p = os.path.join(base, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(txt)
    return p


class Dados(unittest.TestCase):
    def test_personas_e_roteamento_coerentes(self):
        with open(os.path.join(TOOLS, "personas.json"), encoding="utf-8") as fh:
            ps = json.load(fh)["personas"]
        with open(os.path.join(TOOLS, "roteamento.json"), encoding="utf-8") as fh:
            validos = json.load(fh)["modelos_validos"]
        for n, p in ps.items():
            self.assertIn(p["modelo"], validos, n)
            self.assertIn(p["permissao"], ("leitura", "escrita", "escrita-oraculo"), n)
            self.assertNotRegex(p["missao"], r"\{[A-Za-zÀ-ú_ ]{3,}\}", n)
            self.assertTrue(p["retorno"], n)


class ExigeModelo(unittest.TestCase):
    def h(self, d):
        return py("exige-modelo.py", stdin=json.dumps(d))

    def test_id_sem_numero_e_modelo_explicito(self):
        rc, _, err = self.h({"tool_name": "Task", "tool_input": {"description": "diagnóstico TASK-90-02"}})
        self.assertEqual(rc, 2)
        self.assertIn("TASK-90-02", err)
        self.assertEqual(self.h({"tool_name": "Task", "tool_input": {"description": "TASK-90-02", "model": "opus"}})[0], 0)
        self.assertEqual(self.h({"tool_name": "Agent", "tool_input": "x"})[0], 0)


class TechLeadModelo(unittest.TestCase):
    def test_oraculista_e_ciclo(self):
        for args, esperado in ((["--papel", "rh:oraculista"], "opus"), (["--papel", "executor", "--ciclo", "3"], "opus"),
                               (["--papel", "qa"], "sonnet")):
            rc, out, _ = py("tech_lead.py", "modelo", *(args + ["--json"]))
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(out)["modelo"], esperado, args)
        self.assertEqual(py("tech_lead.py", "modelo", "--papel", "rh:astronauta")[0], 2)

    def test_snap_por_pasta(self):
        tmp = tempfile.mkdtemp()
        try:
            escrever(tmp, "c/a.py", "x = 1\n")
            s = os.path.join(tmp, "s.json")
            self.assertEqual(py("tech_lead.py", "snap", "--dir", os.path.join(tmp, "c"), "--out", s)[0], 0)
            self.assertEqual(py("tech_lead.py", "snap", "--dir", os.path.join(tmp, "c"), "--comparar", s)[0], 0)
            escrever(tmp, "c/a.py", "x = 2\n")
            rc, out, _ = py("tech_lead.py", "snap", "--dir", os.path.join(tmp, "c"), "--comparar", s, "--json")
            self.assertEqual((rc, json.loads(out)["mudou"]), (1, ["a.py"]))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class Custo(unittest.TestCase):
    def test_mesmo_turno_em_varias_linhas_conta_uma_vez(self):
        tmp = tempfile.mkdtemp()
        try:
            u = {"input_tokens": 1, "cache_creation_input_tokens": 2, "cache_read_input_tokens": 3, "output_tokens": 4}
            linhas = [json.dumps({"type": "assistant", "message": {"id": "m1", "model": "x", "usage": u}}),
                      json.dumps({"type": "assistant", "message": {"id": "m1", "model": "x", "usage": u}}),
                      json.dumps({"type": "assistant", "message": {"id": "m2", "model": "x", "usage": u}})]
            t = escrever(tmp, "agent-q.jsonl", "\n".join(linhas) + "\n")
            rc, out, _ = py("custo.py", "medir", "q", "--transcript", t, "--json")
            j = json.loads(out)
            self.assertEqual((rc, j["turnos"], j["contexto_somado"], j["saida"]), (0, 2, 12, 8))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class RH(unittest.TestCase):
    def test_oraculista_e_fazer_direto_conferido(self):
        self.assertEqual(py("rh.py", "ficha", "--persona", "oraculista", "--task", "01-TASK-ORACULO", "--motivo", "x")[0], 2)
        rc, out, _ = py("rh.py", "ficha", "--persona", "oraculista", "--task", "01-TASK-ORACULO", "--motivo", "x",
                        "--feature", "demo", "--json")
        self.assertEqual(json.loads(out)["permissao"], "ESCRITA em campanhas/demo/oraculo/")
        tmp = tempfile.mkdtemp()
        try:
            _, txt, _ = py("rh.py", "ficha", "--persona", "cetico", "--task", "02-TASK-UM", "--motivo", "x",
                           "--contratados", "3")
            self.assertEqual(py("rh.py", "conferir", escrever(tmp, "f.txt", txt))[0], 0)
            _, txt, _ = py("rh.py", "ficha", "--persona", "cetico", "--task", "02-TASK-UM", "--motivo", "x")
            ruim = txt.replace("Permissão: SOMENTE LEITURA", "Permissão: ESCRITA em a/um.py")
            self.assertEqual(py("rh.py", "conferir", escrever(tmp, "g.txt", ruim))[0], 2)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class E2E(unittest.TestCase):
    def sel(self, *a):
        rc, out, _ = py("e2e.py", "selecionar", *(list(a) + ["--json"]), env={"CS_DEV_SKILL_DIR": SKILL})
        self.assertEqual(rc, 0)
        return json.loads(out)

    def test_regras_de_borda(self):
        self.assertTrue(self.sel("--arquivos", ".claude/package/README.md")["completa"])
        self.assertTrue(self.sel("--arquivos", "scripts/cs.py")["completa"])
        self.assertTrue(self.sel("--arquivos", "SKILL.md")["completa"])
        j = self.sel("--arquivos", "./scripts/scan/x.py", "evals/fixtures/y.txt")
        self.assertEqual((sorted(j["suites"]), j["completa"]), (["evals", "scan"], False))

    def test_lista_e_suite_desconhecida(self):
        tmp = tempfile.mkdtemp()
        try:
            j = self.sel("--lista", escrever(tmp, "l.txt", ".claude/tools/rh.py\n\n"))
            self.assertEqual(j["suites"], ["harness-dev"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertEqual(py("e2e.py", "rodar", "--suites", "nada", "--dry-run", env={"CS_DEV_SKILL_DIR": SKILL})[0], 3)


class Campanha(unittest.TestCase):
    def test_help_so_tres_e_sem_campanha_recusa(self):
        _, out, _ = py("campanha.py", "--help")
        self.assertEqual(sorted(re.search(r"\{([a-z,-]+)\}", out).group(1).split(",")),
                         ["etapa", "fechar", "mudanca-oficial"])
        tmp = os.path.realpath(tempfile.mkdtemp())
        try:
            rc, _, err = py("campanha.py", "etapa", "nada", env={"CS_DEV_SKILL_DIR": tmp})
            self.assertEqual(rc, 1)
            self.assertIn("criar-feature", err)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class Portao(unittest.TestCase):
    def test_dry_run_com_suites_sem_harness(self):
        rc, out, err = run(["bash", os.path.join(TOOLS, "portao.sh"), "x", "--src", SKILL, "--suites", "emit",
                            "--dry-run", "--", "SKILL.md"], env={"CS_DEV_SKILL_DIR": SKILL})
        self.assertEqual(rc, 0, err)
        self.assertNotIn("harness-dev: .claude/tools/tests", out)
        rc, out, _ = run(["bash", os.path.join(TOOLS, "portao.sh"), "x", "--src", SKILL, "--suites", "harness-dev",
                          "--dry-run", "--", "SKILL.md"], env={"CS_DEV_SKILL_DIR": SKILL})
        self.assertIn("harness-dev: .claude/tools/tests", out)


if __name__ == "__main__":
    unittest.main()
