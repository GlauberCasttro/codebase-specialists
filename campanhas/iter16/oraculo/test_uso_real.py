"""ORÁCULO campanha-iter16 — skill codebase-specialists: defeitos vistos em USO REAL (cobaia cobaia .NET, .NET).

As correções já foram feitas direto na skill (sem teste). Este oráculo PROVA cada defeito (falha com os arquivos
ANTERIORES) e PROVA a correção (passa com a skill viva). Mapa requisito→teste em ESPEC.md (mesma pasta).

  U1  BOM: C# salvo com BOM UTF-8 (`\\xef\\xbb\\xbf` antes de `namespace`/`using` na linha 1) — o scan enxerga o
      `using`/`namespace` da 1ª linha: a aresta do grafo existe e o arquivo não fica com in=0 indevido; texto sem
      BOM continua igual.
  U2  dotfile: no exame (`probes/exam.py`, PATH_RE/`cites`), `.editorconfig:3` e `src/.eslintrc:10` são caminho+linha;
      sem falso positivo óbvio (`e.g.`, `v1.2`, final de frase com ponto).
  U3  refino no --fast: sem painel (`.swarm/panel/<agente>.json5` ausente), agente REPROVADO com slot de refino aberto
      consegue `team card revise`; continua recusado sem refino e sem conserto de existência (mensagem do painel);
      o conserto de existência continua; a revisão do autor (rt.4) sem painel e sem refino continua recusada.
  U4  history: a sonda `history` pergunta pelo sha do commit cujo ASSUNTO é o citado (não diz "corrigiu") e o
      gabarito é esse próprio commit; `references/probes.md` coerente (linha HISTÓRIA).
  --- ampliação (2ª rodada cobaia .NET) ---
  U2b dotfile em fim de frase sem linha (`o arquivo é .editorconfig.`) é citado; `.NET 8` NÃO vira caminho.
  U5  check-diff (`harness/engine/guard.py`): delegação ACCEPTED com a task ainda aberta LIBERA os allowed_paths dela
      (janela para commitar o trabalho aceito); task fechada (`cs-state close`) → barra; BRIEFED/READY → barra;
      arquivo fora de qualquer allowed_paths → barra; `CS_GUARD_OFF=1` sem efeito. O orchestrator gerado instrui
      commitar os allowed_paths depois do gate PASS e ANTES do `cs-state close`.
  U6  aresta C# registra a LINHA do `using` correspondente (`scan/l1_graph.py` `edge_line`), não 0.
  U7  `using` dentro de string literal (depois da 1ª declaração de tipo) não é import (`CS_FIRST_TYPE`).
  U8  pergunta de `dependency` traz o critério de "importa" (`.cs`: `using` de namespace; demais: import de arquivo).
  U9  `why` não é gerada de tópico genérico ("O que foi feito") nem de tópico repetido em ≥3 fatos de rationale.
  U10 `why` sem `key_terms`: citar QUALQUER linha do documento-fonte passa no pré-check (mérito fica com o painel).
  U11 `probes check` NÃO apaga a cópia do exame enquanto houver painel `why` pendente; apaga no check seguinte.
  U12 `namespace X` dentro de string/raw string C# não declara X (`CS_NAMESPACE`): `using X;` de outro arquivo não
      vira aresta para o arquivo da string.

Comportamento observável: `cs.py` em subprocesso e funções públicas da skill, alvos em diretórios temporários.
Skill sob teste: $CS_SKILL_DIR, senão ~/.claude/skills/codebase-specialists.
Python 3.9+, unittest puro. Rodar (de dentro desta pasta):  python3 -m unittest -v test_uso_real
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

SKILL = os.path.realpath(os.environ.get("CS_SKILL_DIR") or os.path.expanduser("~/.claude/skills/codebase-specialists"))
SCRIPTS = os.path.join(SKILL, "scripts")
CS = os.path.join(SCRIPTS, "cs.py")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

BOM = b"\xef\xbb\xbf"
GIT_ENV = {"GIT_AUTHOR_NAME": "Ana", "GIT_AUTHOR_EMAIL": "ana@x", "GIT_COMMITTER_NAME": "Ana",
           "GIT_COMMITTER_EMAIL": "ana@x", "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
           "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z"}


def _load(name, rel):
    """Carrega um helper de teste da PRÓPRIA skill sob teste com nome único (scan/tests e team/tests têm `synth`)."""
    spec = importlib.util.spec_from_file_location(name, os.path.join(SCRIPTS, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def git(root, *args):
    p = subprocess.run(["git", "-C", root] + list(args), env=dict(os.environ, **GIT_ENV),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise AssertionError("git %s: %s" % (" ".join(args), p.stderr.decode()))
    return p.stdout.decode("utf-8", "replace")


def commit_all(root, msg):
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", msg)


def write_bytes(root, rel, data):
    full = os.path.join(root, rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "wb") as fh:
        fh.write(data)


def cs(root, *args):
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    p = subprocess.run([sys.executable, CS, "--target", root] + list(args), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, env=env, cwd=tempfile.gettempdir(), timeout=600)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def json5_load(path):
    from cslib import json5io
    return json5io.load(path)


# ================================================================================================ U1 — BOM
# Cada aresta isola UM lado do defeito:
#   Runner.cs  (sem BOM) `using Cobaia.Core;`  → SwiftMapException.cs (BOM + `namespace` na linha 1): lado NAMESPACE
#   Worker.cs  (BOM + `using` na linha 1)          → Log.cs (sem BOM):                                    lado USING
#   Plain.cs   (sem BOM) `using Cobaia.Infra;`  → Log.cs (sem BOM):                                    regressão
CS_FILES = {
    "src/Core/SwiftMapException.cs": BOM + (
        b"namespace Cobaia.Core;\n\npublic class SwiftMapException : System.Exception\n{\n}\n"),
    "src/Infra/Log.cs": (
        b"namespace Cobaia.Infra;\n\npublic static class Log\n{\n    public static void Info(string m) { }\n}\n"),
    "src/App/Runner.cs": (  # `using` da aresta na LINHA 2 (U6)
        b"using System;\nusing Cobaia.Core;\n\nnamespace Cobaia.App;\n\npublic class Runner\n{\n"
        b"    public void Go() { throw new SwiftMapException(); }\n}\n"),
    "src/App/Worker.cs": BOM + (
        b"using Cobaia.Infra;\n\nnamespace Cobaia.App;\n\npublic class Worker\n{\n"
        b"    public void Run() { Log.Info(\"x\"); }\n}\n"),
    "src/App/Plain.cs": (  # `using` da aresta na LINHA 2 (U6)
        b"// sem BOM\nusing Cobaia.Infra;\n\nnamespace Cobaia.App;\n\npublic class Plain\n{\n"
        b"    public void Run() { Log.Info(\"y\"); }\n}\n"),
    # U7: teste de source generator com código C# embutido em raw string DEPOIS da declaração do tipo
    "tests/Gen/GenTests.cs": (
        b"using System;\n\nnamespace Cobaia.Tests;\n\npublic sealed class GenTests\n{\n"
        b"    const string Src = \"\"\"\n        using Cobaia.Core;\n        namespace User { }\n        \"\"\";\n}\n"),
}
EXC, LOG, RUNNER, WORKER, PLAIN, GEN = ("src/Core/SwiftMapException.cs", "src/Infra/Log.cs", "src/App/Runner.cs",
                                        "src/App/Worker.cs", "src/App/Plain.cs", "tests/Gen/GenTests.cs")
EDGE_LINE = {(RUNNER, EXC): 2, (WORKER, LOG): 1, (PLAIN, LOG): 2}  # linha do `using` de cada aresta (U6)


def make_cs_repo():
    root = os.path.realpath(tempfile.mkdtemp(prefix="cs-iter16-bom-"))
    for rel, data in CS_FILES.items():
        write_bytes(root, rel, data)
    git(root, "init", "-q")
    commit_all(root, "init: cobaia .NET mínimo com BOM")
    return root


class TestU1BomGrafoDoScan(unittest.TestCase):
    """`cs.py scan --no-exec` num repo C# com BOM: grafo de dependências (`.swarm/facts/graph.json5`)."""

    @classmethod
    def setUpClass(cls):
        cls.root = make_cs_repo()
        code, out, err = cs(cls.root, "scan", "--no-exec")
        if code != 0:
            raise AssertionError("scan falhou (%d): %s" % (code, out + err))
        g = json5_load(os.path.join(cls.root, ".swarm", "facts", "graph.json5"))
        cls.edges = set((e[0], e[1]) for e in g["edges"])
        cls.edge_lines = {(e[0], e[1]): e[3] for e in g["edges"]}
        cls.nodes = {n["path"]: n for n in g["nodes"]}
        cls.external = g.get("external") or {}
        cls.ed_fields = list(g.get("edge_fields") or [])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def test_precondicao_fixture_tem_bom_so_onde_deve(self):
        for rel, data in CS_FILES.items():
            with open(os.path.join(self.root, rel), "rb") as fh:
                self.assertEqual(fh.read(3) == BOM, rel in (EXC, WORKER), rel)
        self.assertEqual(set(self.nodes), set(CS_FILES), "todos os .cs viram nó do grafo")
        self.assertEqual(self.ed_fields[3:4], ["line"], "edge_fields: 4º campo é a linha")

    def test_namespace_na_linha_1_com_bom_e_resolvido(self):
        """Lado NAMESPACE: `using Cobaia.Core;` (sem BOM) só resolve se o `namespace` do arquivo com BOM casou."""
        self.assertIn((RUNNER, EXC), self.edges)

    def test_arquivo_com_bom_nao_fica_com_in_zero(self):
        """O sintoma do cobaia .NET: SwiftMapException.cs com in=0 (gabarito de dependência errado)."""
        self.assertGreaterEqual(self.nodes[EXC]["in"], 1, self.nodes[EXC])

    def test_using_na_linha_1_com_bom_e_resolvido(self):
        """Lado USING: o `using` da linha 1 de um arquivo com BOM gera aresta (out ≥ 1)."""
        self.assertIn((WORKER, LOG), self.edges)
        self.assertGreaterEqual(self.nodes[WORKER]["out"], 1, self.nodes[WORKER])

    def test_namespace_interno_nao_vira_dependencia_externa(self):
        """Com o namespace perdido, `cobaia .NET` caía em imports externos (C#) — não pode."""
        self.assertNotIn("Cobaia", (self.external.get("csharp") or {}), self.external)

    def test_regressao_sem_bom_continua_igual(self):
        """Par só sem BOM (Plain → Log): a aresta existe e nada sai de Plain além dela."""
        self.assertIn((PLAIN, LOG), self.edges)
        self.assertEqual(self.nodes[PLAIN]["out"], 1, self.nodes[PLAIN])
        self.assertEqual(self.nodes[PLAIN]["in"], 0, self.nodes[PLAIN])

    def test_u6_aresta_csharp_registra_a_linha_do_using(self):
        """U6: a evidência da aresta C# é a linha do `using` que a cria (era sempre 0)."""
        got = {k: self.edge_lines.get(k) for k in EDGE_LINE}
        self.assertEqual(got, EDGE_LINE)

    def test_u7_using_em_string_literal_nao_e_import(self):
        """U7: `using Cobaia.Core;` dentro da raw string (depois de `public sealed class`) não vira aresta."""
        self.assertNotIn((GEN, EXC), self.edges)
        self.assertEqual(self.nodes[EXC]["in"], 1, self.nodes[EXC])
        self.assertEqual(self.nodes[GEN]["out"], 0, self.nodes[GEN])

    def test_grafo_exato(self):
        """Nem aresta a menos (BOM) nem a mais (o strip do BOM não inventa dependência)."""
        self.assertEqual(self.edges, {(RUNNER, EXC), (WORKER, LOG), (PLAIN, LOG)})
        self.assertEqual(self.nodes[LOG]["in"], 2, self.nodes[LOG])  # Plain (sem BOM) + Worker (com BOM)


class TestU1BomLeituraDoContexto(unittest.TestCase):
    """`scan.context.ScanContext.text/lines` — a leitura que o grafo (e as demais camadas) usam."""

    @classmethod
    def setUpClass(cls):
        cls.root = make_cs_repo()
        write_bytes(cls.root, "docs/meio.txt", "antes﻿depois\n".encode("utf-8"))  # U+FEFF fora do início
        write_bytes(cls.root, "docs/acento.txt", "ação é válida\r\nlinha 2\n".encode("utf-8"))
        commit_all(cls.root, "docs")
        from scan.context import Options, ScanContext
        cls.ctx = ScanContext(cls.root, Options(no_exec=True))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def test_bom_nao_aparece_no_texto(self):
        t = self.ctx.text(EXC)
        self.assertFalse(t.startswith("﻿"), repr(t[:20]))
        self.assertTrue(t.startswith("namespace Cobaia.Core;"), repr(t[:30]))

    def test_linha_1_com_bom_e_a_declaracao(self):
        self.assertEqual(self.ctx.lines(WORKER)[0], "using Cobaia.Infra;")
        self.assertEqual(len(self.ctx.lines(WORKER)), CS_FILES[WORKER].count(b"\n"), "numeração de linhas intacta")

    def test_regressao_texto_sem_bom_identico_ao_bruto(self):
        for rel in (LOG, RUNNER, PLAIN, "docs/acento.txt"):
            with open(os.path.join(self.root, rel), "rb") as fh:
                self.assertEqual(self.ctx.text(rel), fh.read().decode("utf-8"), rel)

    def test_regressao_feff_no_meio_e_preservado(self):
        self.assertEqual(self.ctx.text("docs/meio.txt"), "antes﻿depois\n")


# ================================================================================================ U2 — dotfile
def exam_mod():
    from probes import exam
    return exam


class TestU2DotfileNoExame(unittest.TestCase):
    """`probes.exam.cites` (PATH_RE): caminho+linha citados numa resposta de exame."""

    def cites(self, text):
        return exam_mod().cites(text)

    def test_editorconfig_na_raiz_com_linha(self):
        for text in (".editorconfig:3", "ver .editorconfig:3", "`.editorconfig:3`", "(.editorconfig:3)",
                     "a regra está em .editorconfig:3.", "vide .editorconfig:3, que impõe"):
            self.assertIn((".editorconfig", 3), self.cites(text), text)

    def test_outros_dotfiles_na_raiz(self):
        for text, want in ((".gitignore:2", (".gitignore", 2)), (".env:1", (".env", 1)),
                           (".eslintrc:10", (".eslintrc", 10)), (".prettierrc:4", (".prettierrc", 4))):
            self.assertIn(want, self.cites(text), text)

    def test_eslintrc_em_subpasta_com_linha(self):
        """`src/.eslintrc:10` (exigido pelo requisito; já casava antes pelo ramo `dir/nome` — regressão)."""
        for text in ("src/.eslintrc:10", "em src/.eslintrc:10 está a regra", "`src/.eslintrc:10`."):
            self.assertIn(("src/.eslintrc", 10), self.cites(text), text)

    def test_regressao_caminhos_normais_intactos(self):
        cases = {".github/workflows/ci.yml:7": [(".github/workflows/ci.yml", 7)],
                 "src/.eslintrc.json:3": [("src/.eslintrc.json", 3)],
                 "docs/.env.example:2": [("docs/.env.example", 2)],
                 "src/app.py:12": [("src/app.py", 12)],
                 "Makefile:4": [("Makefile", 4)],
                 "src/Core/SwiftMapException.cs:1": [("src/Core/SwiftMapException.cs", 1)],
                 "./src/app.py:3": [("src/app.py", 3)]}
        for text, want in cases.items():
            self.assertEqual(self.cites(text), want, text)

    def test_sem_falso_positivo_de_dotfile_em_prosa(self):
        """Prosa com ponto não vira dotfile nem caminho+linha (o ramo novo não pode inventar `.algo`)."""
        for text in ("e.g. isso vale", "i.e. nada", "versão v1.2 do pacote", "Fim de frase. Outra coisa.",
                     "etc. e tal", "isso... depois", "Termina aqui.", "Valor 3.14 e 2.0.1", "Ok.Próximo"):
            got = self.cites(text)
            self.assertFalse([c for c in got if c[0].startswith(".")], (text, got))
            self.assertFalse([c for c in got if c[1] is not None], (text, got))

    def test_u2b_dotfile_em_fim_de_frase_sem_linha(self):
        """U2b: dotfile sem linha no fim da frase (sonda de existência/proibição em nível de arquivo)."""
        for text in ("o arquivo é .editorconfig.", "A regra está no .editorconfig.", "Veja .gitignore."):
            got = self.cites(text)
            self.assertTrue([c for c in got if c[0] in (".editorconfig", ".gitignore")], (text, got))
            self.assertFalse([c for c in got if c[0].endswith(".")], (text, got))

    def test_u2b_dotnet_nao_vira_caminho(self):
        """U2b: `.NET 8` (o próprio stack da cobaia .NET) não é dotfile."""
        for text in ("usa .NET 8 e C# 12", "migrar para o .NET 9.", "(.NET Framework 4.8)"):
            got = self.cites(text)
            self.assertFalse([c for c in got if c[0].upper().startswith(".NET")], (text, got))

    def test_sonda_de_localizacao_em_dotfile_e_pontuada(self):
        """Efeito no exame: a sonda de localização com gabarito `.editorconfig:3` aprova quem cita `.editorconfig:3`."""
        tsynth = _load("cs_iter16_team_synth", "team/tests/synth.py")
        root = tsynth.make_repo(extra_files={".editorconfig": "root = true\n[*]\nindent_style = space\n"})
        try:
            ck = exam_mod().Checker(root)
            self.assertIn(".editorconfig", ck.files, "pré-condição: o dotfile está no inventário")
            probe = {"id": "P-x-1", "type": "location", "question": "Onde é imposta a indentação?",
                     "answer": {"exists": True, "path": ".editorconfig", "line": 3}}
            ans = {"id": "P-x-1", "answer": "Em `.editorconfig:3` (indent_style).", "evidence": [".editorconfig:3"]}
            passed, halluc, reason, _ = ck.score_one(probe, ans)
            self.assertTrue(passed, reason)
            self.assertFalse(halluc)
            wrong = dict(ans, answer="Em `.editorconfig:30`.")
            self.assertFalse(ck.score_one(probe, wrong)[0], "linha fora de ±3 continua reprovada")
        finally:
            tsynth.cleanup(root)


# ================================================================================================ U3 — refino sem painel
AGENT = "dev-billing"


def card(name, anchors=("src/billing/invoice.py",)):
    return {"description": "Use para mudar %s." % name, "mission": "Mantém %s correto." % name,
            "knows": [{"text": "Invoice é o termo canônico", "facts": ["gl.invoice"]}],
            "refuses": [{"text": "usar float para dinheiro", "why": "ADR 1", "facts": ["rat.adr.money"]}],
            "done_when": "`python3 -m unittest discover -s tests` sai 0",
            "playbooks": [], "rules": [], "footguns": [], "anchors": list(anchors)}


def cycle(decision):
    return {"at": "2026-10-05T00:00:00Z", "probes_sha256": "p" * 64, "answers_sha256": "a" * 64,
            "card_sha256": "c" * 64, "decision": decision, "retakes": 0}


class TestU3RefinoNoFastSemPainel(unittest.TestCase):
    """`cs.py team card revise` sem `.swarm/panel/<agente>.json5` (modo --fast: sem mesa redonda)."""

    def setUp(self):
        self.tsynth = _load("cs_iter16_team_synth", "team/tests/synth.py")
        self.root = self.tsynth.make_repo()
        from team.derive import derive
        derive(self.root)
        self.put(".swarm/tmp/card.json5", card(AGENT))
        code, o, e = cs(self.root, "team", "card", "set", AGENT, "--file", ".swarm/tmp/card.json5")
        self.assertEqual(code, 0, o + e)
        self.assertFalse(os.path.exists(self.panel()), "pré-condição: sem painel (--fast)")

    def tearDown(self):
        self.tsynth.cleanup(self.root)

    # ---- helpers
    def panel(self):
        from team._shared_tmp.common import sp_path
        return sp_path(self.root, "panel", "%s.json5" % AGENT)

    def put(self, rel, obj):
        full = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as fh:
            fh.write("// teste\n" + json.dumps(obj))
        return rel

    def cycles(self, data):
        from team._shared_tmp.common import sp_path
        p = sp_path(self.root, "probes", "cycles.json5")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as fh:
            fh.write("// ciclos de exame (fixture)\n" + json.dumps(data))

    def status(self):
        from team._shared_tmp.common import read_json, sp_path
        return read_json(sp_path(self.root, "cards", "status.json5"))[AGENT]

    def better(self):
        c = card(AGENT, anchors=("src/billing/invoice.py", "src/billing/refund.py"))
        c["mission"] = "Mantém %s correto (refinado após exame reprovado)." % AGENT
        return self.put(".swarm/tmp/better.json5", c)

    def assert_refused_panel(self, res):
        code, o, e = res
        self.assertEqual(code, 2, o + e)
        self.assertIn("não consolidado", e)
        self.assertIn(".swarm/panel/%s.json5" % AGENT, e)

    # ---- defeito: o refino liberado pelo exame reprovado era recusado sem painel
    def test_reprovado_com_refino_aberto_revisa_com_file(self):
        self.cycles({AGENT: [cycle("FAIL")]})
        code, o, e = cs(self.root, "team", "card", "revise", AGENT, "--file", self.better(), "--note", "refino 1")
        self.assertEqual(code, 0, o + e)
        st = self.status()
        self.assertEqual([r.get("cycle") for r in st.get("refines") or []], [1], st)
        self.assertTrue(st["refines"][0]["changed"])
        self.assertNotIn("revised", st, "refino não vira revisão do autor (rt.4)")
        self.assertFalse(st.get("existence_fixes"), "refino não é conserto de existência")
        from team.cards import card_status
        row = [r for r in card_status(self.root) if r["agent"] == AGENT][0]
        self.assertEqual(row["problems_drafted"], [], row)

    def test_reprovado_com_refino_aberto_revisa_sem_mudanca_com_note(self):
        self.cycles({AGENT: [cycle("FAIL")]})
        code, o, e = cs(self.root, "team", "card", "revise", AGENT, "--note", "cartão já certo; reexame")
        self.assertEqual(code, 0, o + e)
        self.assertEqual([r.get("cycle") for r in self.status().get("refines") or []], [1])

    def test_refino_e_unico_por_ciclo_reprovado(self):
        self.cycles({AGENT: [cycle("FAIL")]})
        self.assertEqual(cs(self.root, "team", "card", "revise", AGENT, "--file", self.better(),
                            "--note", "refino 1")[0], 0)
        self.assert_refused_panel(cs(self.root, "team", "card", "revise", AGENT, "--note", "de novo"))
        # novo exame reprovado libera exatamente mais uma
        self.cycles({AGENT: [cycle("FAIL"), cycle("FAIL")]})
        code, o, e = cs(self.root, "team", "card", "revise", AGENT, "--note", "refino 2")
        self.assertEqual(code, 0, o + e)
        self.assertEqual([r.get("cycle") for r in self.status()["refines"]], [1, 2])

    def test_refino_sem_painel_ainda_checa_existencia_do_cartao_novo(self):
        self.cycles({AGENT: [cycle("FAIL")]})
        worse = card(AGENT, anchors=("src/billing/inexistente_iter16.py",))
        code, o, e = cs(self.root, "team", "card", "revise", AGENT, "--file",
                        self.put(".swarm/tmp/worse.json5", worse), "--note", "x")
        self.assertEqual(code, 2, o + e)
        self.assertIn("inexistente_iter16.py", e)
        self.assertFalse(self.status().get("refines"), "nada gravado")

    # ---- sem brecha: continua recusado
    def test_sem_ciclo_sem_falta_rt4_sem_painel_recusada(self):
        """Revisão do autor (rt.4) sem painel, sem refino e sem conserto de existência → mensagem do painel."""
        self.assert_refused_panel(cs(self.root, "team", "card", "revise", AGENT, "--note", "rt.4"))
        self.assert_refused_panel(cs(self.root, "team", "card", "revise", AGENT, "--file", self.better(),
                                     "--note", "rt.4 com arquivo"))
        self.assertNotIn("revised", self.status())

    def test_exame_aprovado_nao_abre_refino(self):
        self.cycles({AGENT: [cycle("PASS")]})
        self.assert_refused_panel(cs(self.root, "team", "card", "revise", AGENT, "--file", self.better(),
                                     "--note", "x"))

    def test_reprovacao_de_outro_agente_nao_abre_refino(self):
        self.cycles({"dev-shop": [cycle("FAIL")], "qa": [cycle("FAIL")]})
        self.assert_refused_panel(cs(self.root, "team", "card", "revise", AGENT, "--note", "x"))

    def test_conserto_de_existencia_sem_painel_continua(self):
        bad = card(AGENT, anchors=("src/billing/invoice.py", "src/billing/nao_existe.py"))
        self.assertEqual(cs(self.root, "team", "card", "set", AGENT, "--file",
                            self.put(".swarm/tmp/bad.json5", bad))[0], 0)
        code, o, e = cs(self.root, "team", "card", "revise", AGENT, "--file",
                        self.put(".swarm/tmp/fix.json5", card(AGENT)), "--note", "conserto de existência")
        self.assertEqual(code, 0, o + e)
        st = self.status()
        self.assertEqual(len(st.get("existence_fixes") or []), 1, st)
        self.assertTrue(st["existence_fixes"][0]["existence_fix"])
        self.assertFalse(st.get("refines"))
        self.assertNotIn("revised", st)
        # consertado (sem falta) e sem refino: volta a exigir painel
        self.assert_refused_panel(cs(self.root, "team", "card", "revise", AGENT, "--file",
                                     ".swarm/tmp/fix.json5", "--note", "outra"))


# ================================================================================================ U4 — history
FIX_SUBJECT = "fix: bug no limite de itens porque o total estourava sem validação"
LATER_SUBJECT = "fix: corrige de novo o limite de itens (regressão do total)"


class TestU4SondaHistory(unittest.TestCase):
    """Repo real (git) → `cs.py scan --no-exec` → derive → `probes generate`; sondas `history` do banco."""

    @classmethod
    def setUpClass(cls):
        ssynth = _load("cs_iter16_scan_synth", "scan/tests/synth.py")
        cls.root = ssynth.make_repo()  # init + "fix: bug no limite de itens ..." (orders.py, money.py)
        # commit POSTERIOR que também "corrige" o mesmo assunto: quem lê "qual commit corrigiu X" cai nele
        with open(os.path.join(cls.root, "src/shop/orders.py")) as fh:
            ssynth.write(cls.root, "src/shop/orders.py", fh.read() + "\n# regressão\n")
        ssynth.commit(cls.root, LATER_SUBJECT)
        code, o, e = cs(cls.root, "scan", "--no-exec")
        if code != 0:
            raise AssertionError("scan falhou: %s" % (o + e))
        from team.derive import derive
        from probes.generate import generate, load_bank
        derive(cls.root)
        generate(cls.root)
        cls.bank = load_bank(cls.root)["probes"]
        cls.hist = [p for p in cls.bank if p["type"] == "history"]
        cls.sha_of = {}
        for ln in git(cls.root, "log", "--format=%H\t%s").splitlines():
            sha, subj = ln.split("\t", 1)
            cls.sha_of.setdefault(subj, []).append(sha)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def subject(self, p):
        m = re.search(r"\"(.+)\"", p["question"])
        self.assertTrue(m, p["question"])
        return m.group(1)

    def test_precondicao_ha_sonda_history(self):
        self.assertTrue(self.hist, "banco sem sonda history")
        self.assertEqual(len(self.sha_of[FIX_SUBJECT]), 1)

    def test_pergunta_e_pelo_sha_do_commit_com_aquele_assunto(self):
        for p in self.hist:
            q = re.sub(r"\"[^\"]*\"", "\"…\"", p["question"])  # o texto da PERGUNTA, fora do assunto citado
            self.assertNotRegex(q.lower(), r"corrigi|corrige|fixed|which commit fixed", q)
            self.assertRegex(q.lower(), r"\bassunto\b", q)
            self.assertRegex(q.lower(), r"\bsha\b", q)

    def test_gabarito_e_o_proprio_commit_do_assunto_citado(self):
        for p in self.hist:
            subj = self.subject(p)
            self.assertIn(subj, self.sha_of, "assunto citado não é assunto de commit: %r" % subj)
            self.assertEqual(self.sha_of[subj], [p["answer"]["sha"]], p)
        self.assertIn(FIX_SUBJECT, [self.subject(p) for p in self.hist])

    def test_exame_aprova_o_sha_do_assunto_e_reprova_o_commit_posterior(self):
        from probes.exam import Checker
        ck = Checker(self.root)
        p = [x for x in self.hist if self.subject(x) == FIX_SUBJECT][0]
        own = self.sha_of[FIX_SUBJECT][0]
        later = self.sha_of[LATER_SUBJECT][0]
        ok = ck.score_one(p, {"id": p["id"], "answer": own[:10], "evidence": ["git log --oneline"]})
        self.assertTrue(ok[0], ok)
        bad = ck.score_one(p, {"id": p["id"], "answer": later[:10], "evidence": ["git log --oneline"]})
        self.assertFalse(bad[0], bad)

    def test_probes_md_linha_historia_coerente(self):
        with open(os.path.join(SKILL, "references", "probes.md"), encoding="utf-8") as fh:
            rows = [ln for ln in fh if ln.startswith("|") and "`history`" in ln]
        self.assertEqual(len(rows), 1, rows)
        cols = [c.strip() for c in rows[0].strip().strip("|").split("|")]
        self.assertIn("HISTÓRIA", cols[0])
        question = cols[1].lower()
        self.assertNotIn("corrigiu", question, cols)
        self.assertRegex(question, r"\bsha\b.*\bassunto\b", cols)
        self.assertIn("history.fixes", cols[2])
        self.assertIn("prefixo", cols[3])


# ================================================================================================ U8–U11 — sondas
def _team_repo(extra_files=None):
    tsynth = _load("cs_iter16_team_synth", "team/tests/synth.py")
    return tsynth, tsynth.make_repo(extra_files=extra_files)


def _add_rationale(root, tsynth, facts):
    """Acrescenta fatos de rationale (e seus ids no índice) ao repo sintético de team/tests/synth.py."""
    fdir = os.path.join(root, ".swarm", "facts")
    rat = json5_load(os.path.join(fdir, "rationale.json5"))
    idx = json5_load(os.path.join(fdir, "index.json5"))
    for f in facts:
        rat["facts"].append(f)
        idx["facts"].append(f["id"])
    for name, data in (("rationale", rat), ("index", idx)):
        with open(os.path.join(fdir, name + ".json5"), "w") as fh:
            fh.write("// fixture iter16\n" + json.dumps(data))


DOCS = {
    "docs/sessions/2026-10-05.md": "# Sessão\n\n## O que foi feito\n\nAjustes diversos.\n",
    "docs/adr/0002-cache.md": "# ADR 2 — cache de preços\n\nStatus: aceito\n\n## Contexto\n\nCache em memória.\n",
    "docs/notes/a.md": "# A\n\n## Decisões tomadas\n\nx\n",
    "docs/notes/b.md": "# B\n\n## Decisões tomadas\n\ny\n",
    "docs/notes/c.md": "# C\n\n## Decisões tomadas\n\nz\n",
    "docs/adr/0003-longo.md": "".join("linha %d do ADR sobre filas\n" % i for i in range(1, 31)),
}


class TestU8aU10Sondas(unittest.TestCase):
    """Banco gerado (`probes.generate`) e pré-check do exame (`probes.exam.Checker`) no repo de team/tests/synth.py."""

    @classmethod
    def setUpClass(cls):
        cls.tsynth, cls.root = _team_repo(DOCS)
        f = cls.tsynth.fact
        _add_rationale(cls.root, cls.tsynth, [
            f("rat.doc.session", "rationale", "Sessão: o que foi feito",
              [{"file": "docs/sessions/2026-10-05.md", "line": 3}], ["src/**"], {"topic": "O que foi feito", "key_terms": []}),
            f("rat.adr.cache", "rationale", "Cache de preços (ADR 2)", [{"file": "docs/adr/0002-cache.md", "line": 1}],
              ["src/**"], {"topic": "cache de precos em memoria", "key_terms": []}),
        ] + [f("rat.doc.%s" % x, "rationale", "Decisões %s" % x, [{"file": "docs/notes/%s.md" % x, "line": 3}],
               ["src/**"], {"topic": "Decisões tomadas", "key_terms": []}) for x in "abc"])
        from team.derive import derive
        from probes.generate import generate, load_bank
        derive(cls.root)
        generate(cls.root)
        cls.bank = load_bank(cls.root)["probes"]

    @classmethod
    def tearDownClass(cls):
        cls.tsynth.cleanup(cls.root)

    def of(self, t):
        return [p for p in self.bank if p["type"] == t]

    def test_u8_dependency_traz_o_criterio_de_importa(self):
        deps = self.of("dependency")
        self.assertTrue(deps, "pré-condição: há sonda de dependência")
        for p in deps:
            self.assertRegex(p["question"], r"critério:.*import", p["question"])
            self.assertRegex(p["question"], r"string|coment", p["question"])

    def test_u9_why_sem_topico_generico_nem_repetido(self):
        qs = [p["question"] for p in self.of("why")]
        self.assertTrue([q for q in qs if "cache de precos" in q], "controle: tópico específico continua gerando why: %s" % qs)
        self.assertFalse([q for q in qs if "O que foi feito" in q], qs)
        self.assertFalse([q for q in qs if "Decisões tomadas" in q], "tópico em ≥3 fatos de rationale: %s" % qs)

    def _why(self, ck, cite, key_terms=()):
        probe = {"id": "P-w-1", "type": "why", "question": "Por que filas?",
                 "answer": {"exists": True, "key_terms": list(key_terms),
                            "sources": [{"file": "docs/adr/0003-longo.md", "line": 1}]}}
        return ck.score_one(probe, {"id": "P-w-1", "answer": "porque X (%s)" % cite, "evidence": [cite]})

    def test_u10_why_sem_key_terms_aceita_qualquer_linha_do_documento(self):
        from probes.exam import Checker
        ck = Checker(self.root)
        ok, halluc, reason, pend = self._why(ck, "docs/adr/0003-longo.md:20")
        self.assertTrue(ok, reason)
        self.assertTrue(pend, "o mérito continua com o painel (panel_pending)")

    def test_u10_regressao_outro_documento_e_key_terms_continuam_valendo(self):
        from probes.exam import Checker
        ck = Checker(self.root)
        self.assertFalse(self._why(ck, "docs/adr/0002-cache.md:1")[0], "documento errado não passa")
        self.assertTrue(self._why(ck, "docs/adr/0003-longo.md:1")[0], "linha do gabarito continua passando")
        self.assertFalse(self._why(ck, "docs/adr/0003-longo.md:20", key_terms=["centavos"])[0],
                         "com key_terms, a janela ±3 tem de conter o termo")


class TestU11CopiaDoExameComPainelPendente(unittest.TestCase):
    """`probes exam-pack --out` → respostas → `probes check`: a cópia `<out>/repo` fica enquanto houver `why` pendente."""

    AGENT = "dev-billing"

    def setUp(self):
        self.tsynth, self.root = _team_repo()
        from team.derive import derive
        from probes.generate import generate
        derive(self.root)
        generate(self.root)
        with open(os.path.join(self.root, ".gitignore"), "w") as fh:
            fh.write(".swarm/\n")
        git(self.root, "init", "-q")
        commit_all(self.root, "init")
        self.out = os.path.realpath(tempfile.mkdtemp(prefix="cs-iter16-exam-"))

    def tearDown(self):
        self.tsynth.cleanup(self.root)
        shutil.rmtree(self.out, ignore_errors=True)

    def report(self):
        return json5_load(os.path.join(self.root, ".swarm", "probes", "reports", "%s.json5" % self.AGENT))

    def test_copia_fica_com_painel_pendente_e_sai_depois_do_painel(self):
        from probes.generate import load_bank
        sys.path.insert(0, os.path.join(SCRIPTS, "team", "tests"))
        perfect = _load("cs_iter16_test_probes", "probes/tests/test_probes.py").perfect
        code, o, e = cs(self.root, "probes", "exam-pack", self.AGENT, "--out", self.out)
        self.assertEqual(code, 0, o + e)
        repo = os.path.join(self.out, "repo")
        self.assertTrue(os.path.isdir(repo))
        items = [perfect(p) for p in load_bank(self.root)["probes"] if p["agent"] == self.AGENT]
        answer_file = json5_load(os.path.join(self.out, "questions.json5"))["answer_file"]
        with open(answer_file, "w") as fh:
            fh.write(json.dumps(items))
        code, o, e = cs(self.root, "probes", "check", self.AGENT)
        self.assertIn(code, (0, 1), o + e)
        pend = self.report().get("panel_pending") or []
        self.assertTrue(pend, "pré-condição: o exame tem sonda why pendente de painel")
        self.assertTrue(os.path.isdir(repo), "cópia do exame apagada com painel why pendente (os juízes leem nela)")
        for pid in pend:
            code, o, e = cs(self.root, "panel", "why", self.AGENT, "--probe", pid, "--verdict", "PASS")
            self.assertEqual(code, 0, o + e)
        code, o, e = cs(self.root, "probes", "check", self.AGENT)
        self.assertIn(code, (0, 1), o + e)
        self.assertFalse(self.report().get("panel_pending"))
        self.assertFalse(os.path.exists(repo), "sem painel pendente a cópia sai (regressão da limpeza)")


# ================================================================================================ U5 — check-diff
ENGINE = os.path.join(SCRIPTS, "harness", "engine")
STATE_PY = os.path.join(ENGINE, "state.py")
GUARD_PY = os.path.join(ENGINE, "guard.py")
U5_TEAM = {"schema_version": 1, "agents": [
    {"name": "dev-billing", "kind": "dev", "territory": ["src/billing/**"]},
    {"name": "dev-users", "kind": "dev", "territory": ["src/users/**"]},
    {"name": "reviewer", "kind": "gate", "territory": []},
    {"name": "security", "kind": "gate", "territory": []}]}
U5_FILES = {
    "README.md": "# demo\n", ".gitignore": "__pycache__/\n*.pyc\n",
    "src/billing/total.py": "def total(items):\n    return sum(items)\n", "src/users/model.py": "AGE = 18\n",
    "tests/__init__.py": "",
    "tests/test_billing.py": "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
}
TASK_FILE = "src/billing/discount.py"
OUT_FILE = "src/users/extra.py"
CRIT = "AC-1|Dado pedido Quando aplico Então desconta|tests.test_billing"


def _env(extra=None):
    e = dict(os.environ)
    for k in ("CLAUDE_PROJECT_DIR", "CS_ACTOR", "CS_GUARD_OFF", "CS_ROOT"):
        e.pop(k, None)
    e.update(extra or {})
    return e


def _run(argv, cwd, env=None):
    p = subprocess.run(argv, cwd=cwd, env=env or _env(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


class TestU5CheckDiffDepoisDoAceite(unittest.TestCase):
    """Estado em árvore (`cs-state init`), task avulsa pela M2 inteira; `guard.py check-diff` = o pre-commit."""

    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="cs-iter16-diff-"))
        for rel, txt in U5_FILES.items():
            write_bytes(self.root, rel, txt.encode("utf-8"))
        write_bytes(self.root, ".swarm/team.json5", json.dumps(U5_TEAM).encode("utf-8"))
        write_bytes(self.root, ".swarm/facts/rules.json5", b'{"facts": []}')
        write_bytes(self.root, ".swarm/facts/business_rules.json5", b"[]")
        write_bytes(self.root, ".swarm/facts/glossary.json5", b"[]")
        write_bytes(self.root, ".swarm/knowledge/collision.json5", b'{"do_not_parallelize": []}')
        git(self.root, "init", "-q")
        commit_all(self.root, "init")
        self.ok("init")
        out = self.ok("new", "task", "--tipo", "US", "--agent", "dev-billing", "--title", "Aplicar desconto",
                      "--avulsa", "--allowed-path", TASK_FILE, "--verify-cmd", "python3 -m unittest discover -s tests -t .",
                      "--como", "cliente", "--quero", "desconto", "--para", "pagar menos", "--criterio", CRIT)
        m = re.search(r"^criad[oa] (\S+) em (\S+)\s*$", out, re.M)
        self.assertTrue(m, out)
        self.tid, self.tpath = m.group(1), m.group(2)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    # ---- helpers
    def cs_state(self, *args, actor=None):
        argv = [sys.executable, STATE_PY, "--root", self.root] + (["--actor", actor] if actor else []) + list(args)
        return _run(argv, self.root)

    def ok(self, *args, actor=None):
        code, out, err = self.cs_state(*args, actor=actor)
        self.assertEqual(code, 0, "cs-state %s → %d\n%s%s" % (" ".join(args), code, out, err))
        return out

    def check_diff(self, staged=False, env=None):
        argv = [sys.executable, GUARD_PY, "check-diff", "--root", self.root] + (["--staged"] if staged else [])
        return _run(argv, self.root, env=_env(env))

    def model(self):
        try:
            d = json5_load(os.path.join(self.root, self.tpath))
            stack = [d]
            while stack:
                x = stack.pop()
                if isinstance(x, dict):
                    r = x.get("route")
                    if isinstance(r, dict) and r.get("model"):
                        return r["model"]
                    stack.extend(x.values())
                elif isinstance(x, list):
                    stack.extend(x)
        except Exception:
            pass
        return "sonnet"

    def run_until_accepted(self, start=True):
        if start:
            self.ok("start", self.tid)
        self.ok("dispatch", self.tid, "--manual", "--model", self.model())
        write_bytes(self.root, TASK_FILE, b"RATE = 30\n")
        self.ok("submit", self.tid, "--files-changed", TASK_FILE, "--check", "unittest: OK", "--risk", "nenhum",
                "--handoff-notes", "ok", actor="dev-billing")
        self.ok("verify", self.tid)
        self.ok("review", self.tid, "--by", "reviewer", "--verdict", "PASS", "--findings", "conferido: teste verde")
        self.ok("accept", self.tid)

    def assert_free(self, res, why):
        code, out, err = res
        self.assertEqual(code, 0, "%s: check-diff deveria LIBERAR:\n%s%s" % (why, out, err))

    def assert_blocked(self, res, rel, why):
        code, out, err = res
        self.assertEqual(code, 1, "%s: check-diff deveria BARRAR %s (exit %d):\n%s%s" % (why, rel, code, out, err))
        self.assertIn("FORA: %s " % rel, out)

    # ---- defeito: sem janela para commitar o trabalho aceito
    def test_aceita_e_aberta_libera_os_allowed_paths(self):
        self.run_until_accepted()
        self.assert_free(self.check_diff(), "delegação ACCEPTED, task ainda aberta")

    def test_aceita_e_aberta_libera_no_pre_commit_staged(self):
        self.run_until_accepted()
        git(self.root, "add", TASK_FILE)
        self.assert_free(self.check_diff(staged=True), "pre-commit (--staged) do trabalho aceito")

    # ---- sem brecha
    def test_aceita_mas_arquivo_fora_continua_barrado(self):
        self.run_until_accepted()
        write_bytes(self.root, OUT_FILE, b"X = 1\n")
        res = self.check_diff()
        self.assert_blocked(res, OUT_FILE, "arquivo fora de qualquer allowed_paths")
        self.assertNotIn("FORA: %s" % TASK_FILE, res[1], "o arquivo da task aceita não é acusado junto")

    def test_fechada_barra(self):
        self.run_until_accepted()
        self.ok("close", self.tid, "--summary", "desconto entregue")
        self.assert_blocked(self.check_diff(), TASK_FILE, "task fechada (archive/)")
        git(self.root, "add", TASK_FILE)
        self.assert_blocked(self.check_diff(staged=True), TASK_FILE, "task fechada, --staged")

    def test_briefed_ou_ready_barra(self):
        write_bytes(self.root, TASK_FILE, b"RATE = 30\n")
        self.assert_blocked(self.check_diff(), TASK_FILE, "task criada (sem despacho)")
        self.ok("start", self.tid)
        self.assert_blocked(self.check_diff(), TASK_FILE, "task iniciada, delegação BRIEFED (sem despacho)")

    def test_guard_off_nao_afeta_o_check_diff(self):
        write_bytes(self.root, TASK_FILE, b"RATE = 30\n")
        self.ok("start", self.tid)
        self.assert_blocked(self.check_diff(env={"CS_GUARD_OFF": "1"}), TASK_FILE, "BRIEFED com CS_GUARD_OFF=1")
        os.remove(os.path.join(self.root, TASK_FILE))
        self.run_until_accepted(start=False)
        self.ok("close", self.tid, "--summary", "desconto entregue")
        self.assert_blocked(self.check_diff(env={"CS_GUARD_OFF": "1"}), TASK_FILE, "fechada com CS_GUARD_OFF=1")


class TestU5OrchestratorInstruiCommitAntesDoClose(unittest.TestCase):
    """Orchestrator GERADO (`cs.py init` + `harness install` + `emit`, claude-code): seção "Como o fluxo anda"."""

    @classmethod
    def setUpClass(cls):
        code = ("import sys; sys.dont_write_bytecode=True; sys.path.insert(0, %r); sys.path.insert(0, %r);"
                "import fixture; print(fixture.make_repo())"
                % (SCRIPTS, os.path.join(SCRIPTS, "emit", "tests")))
        rc, out, err = _run([sys.executable, "-c", code], tempfile.gettempdir())
        if rc != 0:
            raise AssertionError(err)
        cls.root = out.strip().splitlines()[-1]
        git(cls.root, "init", "-q")
        commit_all(cls.root, "init")
        for args in (("init", "--platforms", "claude-code"), ("harness", "install", "--allow-outside"),
                     ("emit", "--allow-outside")):
            c, o, e = cs(cls.root, *args)
            if c != 0:
                raise AssertionError("cs.py %s → %d\n%s%s" % (" ".join(args), c, o[-2000:], e[-2000:]))
        with open(os.path.join(cls.root, ".claude", "orchestrator.md"), encoding="utf-8") as fh:
            cls.orch = fh.read()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def section(self):
        m = re.search(r"(?ms)^## Como o fluxo anda\s*$(.*?)(?=^## )", self.orch)
        self.assertTrue(m, "orchestrator sem a seção `## Como o fluxo anda`")
        return m.group(1)

    def test_fluxo_manda_commitar_allowed_paths_depois_do_pass_e_antes_do_close(self):
        sec = self.section()
        steps = re.split(r"(?m)^\d+\.\s", sec)
        hit = [st for st in steps if re.search(r"(?i)\bcomm?it", st) and "allowed_paths" in st
               and "PASS" in st and "cs-state close" in st]
        self.assertTrue(hit, "nenhum passo de `Como o fluxo anda` manda commitar os allowed_paths após o PASS e "
                             "antes do `cs-state close`:\n%s" % sec)
        st = hit[0]
        self.assertLess(re.search(r"(?i)\bcomm?it", st).start(), st.index("cs-state close"),
                        "o commit vem ANTES do `cs-state close`: %s" % st)


# ================================================================================================ U12 — namespace em string
U12_FILES = {
    # teste de source generator: `namespace Fake.Ns;` só existe DENTRO da raw string (e numa string comum)
    "tests/Gen/G.cs": (b"namespace Cobaia.Tests;\n\npublic class G\n{\n    const string S = \"\"\"\n"
                       b"        namespace Fake.Ns;\n        public class Fake { }\n        \"\"\";\n"
                       b"    const string T = \"namespace Other.Ns { }\";\n}\n"),
    "src/U.cs": b"using Fake.Ns;\nusing Other.Ns;\nusing Real.Ns;\n\nnamespace App;\n\npublic class U { }\n",
    "src/Real.cs": b"namespace Real.Ns;\n\npublic class R { }\n",  # controle: namespace de verdade
}


class TestU12NamespaceEmStringCSharp(unittest.TestCase):
    """`cs.py scan --no-exec`: `namespace` declarado só dentro de string não é declaração do arquivo."""

    @classmethod
    def setUpClass(cls):
        cls.root = os.path.realpath(tempfile.mkdtemp(prefix="cs-iter16-ns-"))
        for rel, data in U12_FILES.items():
            write_bytes(cls.root, rel, data)
        git(cls.root, "init", "-q")
        commit_all(cls.root, "init")
        code, out, err = cs(cls.root, "scan", "--no-exec")
        if code != 0:
            raise AssertionError("scan falhou (%d): %s" % (code, out + err))
        g = json5_load(os.path.join(cls.root, ".swarm", "facts", "graph.json5"))
        cls.edges = set((e[0], e[1]) for e in g["edges"])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def test_namespace_em_string_nao_vira_alvo_de_using(self):
        self.assertNotIn(("src/U.cs", "tests/Gen/G.cs"), self.edges, self.edges)

    def test_regressao_namespace_real_continua_resolvendo(self):
        self.assertIn(("src/U.cs", "src/Real.cs"), self.edges, self.edges)


if __name__ == "__main__":
    unittest.main()
