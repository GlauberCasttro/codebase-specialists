"""Oráculo da frente harness-dev — o harness de DESENVOLVIMENTO da skill (comandos em português, ricos como o
harness de referência, mecânica em scripts). Contrato em ESPEC.md (esta pasta).

unittest puro, Python 3.9+, nos 2 Pythons:  cd <esta pasta> && python3 -m unittest -v test_harness_dev
Projeto sob teste: $CS_PROJETO; senão $CS_SKILL_DIR (se tiver .claude/tools — é o que o portao.sh passa); senão a raiz
do repositório desta pasta. Testes que ESCREVEM rodam numa CÓPIA temporária (.claude/ do projeto + produto mínimo,
repositório git novo, identidade "Ana") com HOME temporário; nunca tocam o projeto sob teste nem o HOME real.
Termos sensíveis montados por partes: este arquivo é público e passa pelo guard-privacidade.
"""
import hashlib
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
ORACULO = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
F = "demo-x"


def _projeto():
    p = os.environ.get("CS_PROJETO")
    if p:
        return os.path.realpath(p)
    s = os.environ.get("CS_SKILL_DIR")
    if s and os.path.isdir(os.path.join(s, ".claude", "tools")):
        return os.path.realpath(s)
    return os.path.realpath(os.path.join(ORACULO, "..", "..", ".."))


PROJ = _projeto()
SKILL_VIVA = os.path.realpath(os.path.join(ORACULO, "..", "..", ".."))
PRODUTO = ("SKILL.md", "MODO-DE-USO.md", "VERSION", "LICENSE", "scripts", "assets", "references", "docs", "evals",
           ".claude/package")
SKILLS = ["auto-correcao", "carregar-sessao", "criar-frente", "e2e-loop", "fechar-frente", "install", "package",
          "revisor", "rh", "salvar-sessao", "tech-lead"]
MUDAM_ESTADO = {"auto-correcao", "criar-frente", "fechar-frente", "install", "package", "salvar-sessao", "tech-lead"}
SO_LEITURA = {"carregar-sessao", "e2e-loop", "revisor", "rh"}
SUBSTITUIDAS = ["close-front", "load-session", "new-front", "save-session"]
SCRIPTS = {
    "frente.py": ["status", "criar", "checklist", "adotar", "task", "fechar"],
    "contrato.py": ["frente", "completo", "task", "etapa", "complexidade", "--sonda"],
    "tech_lead.py": ["plano", "proxima", "modelo", "snap"],
    "custo.py": ["medir", "registrar", "resumo"],
    "rh.py": ["ficha", "conferir", "elenco"],
    "e2e.py": ["regua", "selecionar", "rodar"],
    "campanha.py": ["etapa", "mudanca-oficial", "fechar"],
    "sessao.py": ["carimbo", "frescor", "briefing", "salvar"],
    "guard-estado.py": [],
    "exige-modelo.py": [],
}
DADOS = ["regras.json", "roteamento.json", "personas.json", "elenco.json", "regua.json"]
PLACEHOLDER = re.compile(r"\{[A-Za-zÀ-ú_ ]{3,}\}")
USUARIO_PRIVADO = "/" + "Users" + "/fulano" + "/proj"


# ------------------------------------------------------------------------------------------------ utilitários
def ler(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def escrever(base, rel, txt):
    p = os.path.join(base, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(txt)
    return p


def env_limpo(tmp, skill, extra=None):
    e = {k: v for k, v in os.environ.items()
         if not (k.startswith("CS_") or k.startswith("GIT_") or k.startswith("FAKE_AC") or k == "AC_FRASE_FILE")}
    home = os.path.join(tmp, "home")
    os.makedirs(home, exist_ok=True)
    e.update({"HOME": home, "XDG_CONFIG_HOME": os.path.join(tmp, "xdg"), "GIT_CONFIG_NOSYSTEM": "1",
              "CS_DEV_SKILL_DIR": skill, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1",
              "PYTHONIOENCODING": "utf-8"})
    e.update(extra or {})
    return e


def rodar(args, env, cwd, stdin=None):
    kw = {"input": stdin.encode("utf-8")} if stdin is not None else {"stdin": subprocess.DEVNULL}
    p = subprocess.run(args, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600, **kw)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def git(cwd, *a):
    p = subprocess.run(["git", "-C", cwd] + list(a), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")})
    return p.returncode, p.stdout.decode("utf-8", "replace").strip()


def jload(s):
    try:
        return json.loads(s)
    except ValueError:
        raise AssertionError("saída não é JSON:\n" + s[:2000])


def arvore(base, pular=(".git",)):
    h = hashlib.sha256()
    for d, dirs, files in os.walk(base):
        dirs[:] = sorted(x for x in dirs if not (d == base and x in pular) and x != "__pycache__")
        for f in sorted(files):
            p = os.path.join(d, f)
            h.update(os.path.relpath(p, base).encode())
            if os.path.islink(p):
                h.update(os.readlink(p).encode())
            else:
                with open(p, "rb") as fh:
                    h.update(fh.read())
    return h.hexdigest()


def frontmatter(txt):
    m = re.match(r"^---\n(.*?)\n---\n", txt, re.S)
    return m.group(1) if m else ""


# ------------------------------------------------------------------------------------------------ fixtures
WORKFLOW_FIX = "# WORKFLOW — teste\n\nNota humana do founder: fora do bloco gerado.\n"
RESUME_FIX = "# RESUME — teste\n\n## Onde paramos\n- início\n\n## Próximos passos\n1. nada\n"
BACKLOG_FIX = "# BACKLOG — teste\n\n| id | P | item |\n|---|---|---|\n| B-01 | P1 | algo |\n"
DECISIONS_FIX = "# Decisões — teste\n\n| id | data | decisão |\n|---|---|---|\n"
README_CAMP = "# campanhas\n\n| campanha | o quê | commit de entrega | decisão |\n|---|---|---|---|\n"

FRENTE_OK = """# demo-x — Exemplo de frente para o oráculo

FRENTE-ID: demo-x
Nome: Exemplo de frente para o oráculo

## História
Como mantenedor da skill, quero que `um()` e `dois()` devolvam o dobro, para provar o fluxo de frente.

## Problema / Contexto
Hoje `a/um.py:2` devolve 1 e `a/dois.py:2` devolve 2 (medido: 2 ocorrências de return em 2 arquivos).

## Valor de negócio
O fluxo de frente fica exercitado de ponta a ponta sem tocar o produto real.

## Personas / Stakeholders
- founder (aprova cada etapa)
- corretor (escreve só na cópia de trabalho)

## Critérios de Aceitação
- **CA-01 — um dobra.** DADO a função `um`, QUANDO chamada, ENTÃO devolve 2.
  Prova: `python3 -m unittest test_demo.TestUm`
- **CA-02 — dois dobra.** DADO a função `dois`, QUANDO chamada, ENTÃO devolve 4.
  Prova: `python3 -m unittest test_demo.TestDois`

## RNFs
- RNF-01: só biblioteca padrão; Python 3.9+.

## Edge cases
- chamada repetida devolve o mesmo valor.

## Dependências
- nenhuma

## Escopo IN
- `a/um.py`, `a/dois.py`

## Escopo OUT
- qualquer arquivo do produto real

## Escopo de escrita
- `a/um.py`
- `a/dois.py`

## Critério de parada
oráculo 2/2 verde nos 2 Pythons e 0 `def` removido

## Métrica de sucesso
2 de 2 CAs com prova verde.

## Aceite da Frente
### Aceite QA — PENDENTE
### Aceite Review — PENDENTE
"""

E1_OK = """# E1 — Análise da demanda
Demanda (literal): "quero que um e dois devolvam o dobro"
Problema por trás: o fluxo de frente nunca foi exercitado de ponta a ponta (dito pelo usuário).
O que NÃO é: não é mudança no produto real.
Perguntas abertas: 1. dobrar ou triplicar? → recomendo: dobrar — dito pelo usuário.
FRENTE-ID: demo-x
"""

E2_OK = """# E2 — Investigação medida
## Inventário
- `grep -n return a/*.py`: 2 ocorrências em 2 arquivos.
## Classificação
- muda: 2 · não muda: 0 · congelado: 0 (soma 2 = total)
## Exclusões
- nada fora de `a/` foi varrido: o escopo é só `a/`.
## Achados
- F1 — `a/um.py:2` devolve 1.
- F2 — `a/dois.py:2` devolve 2.
## Enforcement existente
- nenhum teste cobre `a/` hoje.
"""

E2_SEM_EVIDENCIA = """# E2
## Inventário
- acho que afeta pouca coisa
## Classificação
- muda tudo
## Exclusões
- nenhuma
## Achados
- F1 — parece errado
## Enforcement existente
- nenhum
"""

E5_OK = """# E5 — Abertura
## Ordem
01-TASK-ORACULO → (aprovação do founder) → 02-TASK-UM ∥ 03-TASK-DOIS → 04-TASK-QA → 05-TASK-REVIEW
## Primeira task
01-TASK-ORACULO, por agente separado.
## Escopo da campanha
- `a/um.py`
- `a/dois.py`
## Critério de parada
oráculo 2/2 verde nos 2 Pythons e 0 `def` removido
## Git
nada é commitado na criação.
"""


def task_md(nn, desc, tipo, grupo, ca, depends, arquivos, verif=None, goal=True, subtasks=2, complexidade="normal",
            handoff=""):
    tid = "%s-TASK-%s" % (nn, desc)
    verif = verif or "python3 -m unittest discover -s campanhas/demo-x/oraculo"
    corpo = ["# %s — tarefa %s" % (tid, desc.lower()), "",
             "id: %s" % tid, "frente: demo-x", "tipo: %s" % tipo, "grupo: %s" % grupo,
             "agente: %s" % {"ORACULO": "oraculo", "CORRECAO": "corretor", "QA": "qa", "REVIEW": "revisor"}[tipo],
             "CA: %s" % ca, "depends: %s" % depends, "status: PENDENTE", "gate: PENDENTE",
             "complexidade: %s" % complexidade, ""]
    if goal:
        corpo += ["## Goal", "Mudar o que a task pede e NÃO tocar nada fora dos arquivos permitidos.", ""]
    corpo += ["## Contexto", "%s; âncora `a/um.py:2`." % ca, "", "## Subtasks"]
    corpo += ["%d. passo %d" % (i, i) for i in range(1, subtasks + 1)]
    corpo += ["", "## Invariants", "- nenhum def removido.", "", "## Scope IN / OUT", "IN: a tarefa. OUT: o resto.",
              "", "## Arquivos permitidos"]
    corpo += ["- `%s`" % a for a in arquivos]
    corpo += ["", "## AC", "- o teste da tarefa falha antes e passa depois.", "", "## DoD", "- verificação verde.", "",
              "## Verificação", "```bash", verif, "```", "", "## Handoff", handoff, ""]
    return tid, "\n".join(corpo)


def tasks_ok():
    dep1 = "01-TASK-ORACULO (o oráculo congelado vem antes)"
    tf = ".claude/state/frentes/demo-x/TASKS/%s.md"
    return dict([
        task_md("01", "ORACULO", "ORACULO", "—", "CA-01, CA-02", "—", ["campanhas/demo-x/oraculo/test_demo.py"]),
        task_md("02", "UM", "CORRECAO", "G1", "CA-01", dep1, ["a/um.py"]),
        task_md("03", "DOIS", "CORRECAO", "G2", "CA-02", dep1, ["a/dois.py"]),
        task_md("04", "QA", "QA", "—", "CA-01, CA-02",
                "02-TASK-UM (precisa da correção), 03-TASK-DOIS (precisa da correção)", [tf % "04-TASK-QA"],
                verif="bash .claude/tools/portao.sh demo-x --dry-run -- a/um.py a/dois.py"),
        task_md("05", "REVIEW", "REVIEW", "—", "CA-01, CA-02", "04-TASK-QA (examina a matriz do QA)",
                [tf % "05-TASK-REVIEW"], verif="git diff --stat -- a/um.py a/dois.py"),
    ])


FAKE_AC = r'''import json, os, sys
a = sys.argv[1:]
log = os.environ.get("FAKE_AC_LOG")
if log:
    with open(log, "a") as fh:
        fh.write(json.dumps(a) + "\n")
w = None
if "--work" in a:
    i = a.index("--work"); w = a[i + 1]; a = a[:i] + a[i + 2:]
ok = set(x for x in os.environ.get("FAKE_AC_OK", "").split(",") if x)
c = a[0] if a else ""
if c in ("gate", "preauth", "frase"):
    sys.exit(9)
if c == "init":
    os.makedirs(os.path.join(w, ".auto-correcao"), exist_ok=True)
    sc = [a[i + 1] for i, x in enumerate(a) if x == "--scope"]
    with open(os.path.join(w, ".auto-correcao", "state.json"), "w") as fh:
        json.dump({"round": 0, "stage": "intake", "scope": sc, "done": {}, "gates": {}}, fh)
    print("campanha em %s (rodada 0, etapa intake)" % w)
elif c == "status":
    print("rodada: 0 · etapa: " + os.environ.get("FAKE_AC_ETAPA", "intake"))
elif c == "check":
    if a[1] in ok:
        print("ok"); sys.exit(0)
    sys.stderr.write("NÃO: %s\n" % a[1]); sys.exit(1)
elif c == "oracle" and a[1] == "verify":
    sys.exit(0 if "oracle" in ok else 1)
sys.exit(0)
'''


def montar(tmp):
    """Cópia temporária: .claude/ do projeto sob teste (estado zerado) + produto mínimo; repositório git novo."""
    sk = os.path.join(tmp, "proj")
    os.makedirs(sk)
    shutil.copytree(os.path.join(PROJ, ".claude"), os.path.join(sk, ".claude"), symlinks=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store", ".auto-correcao"))
    shutil.rmtree(os.path.join(sk, ".claude", "state"), ignore_errors=True)
    for rel, txt in ((".claude/state/WORKFLOW.md", WORKFLOW_FIX), (".claude/state/RESUME.md", RESUME_FIX),
                     (".claude/state/BACKLOG.md", BACKLOG_FIX), (".claude/state/DECISIONS.md", DECISIONS_FIX),
                     (".claude/state/logs/sessoes.jsonl", ""), ("VERSION", "0.0.0\n"),
                     ("SKILL.md", "---\nname: produto\ndescription: produto de teste\n---\n# produto\n"),
                     ("a/um.py", "def um():\n    return 1\n"), ("a/dois.py", "def dois():\n    return 2\n"),
                     ("campanhas/README.md", README_CAMP), (".gitignore", "local/\ndist/\n__pycache__/\n*.pyc\n"
                                                           "campanhas/*/.auto-correcao/\n")):
        escrever(sk, rel, txt)
    subprocess.run(["git", "init", "-q", sk], check=True)
    git(sk, "config", "user.name", "Ana")
    git(sk, "config", "user.email", "ana@exemplo.invalid")
    git(sk, "add", "-A")
    git(sk, "commit", "--no-verify", "-qm", "base")
    return sk


class Copia(unittest.TestCase):
    """Base: cópia temporária do projeto + helpers do fluxo criar-frente."""
    fake = False

    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="hd-"))
        self.sk = montar(self.tmp)
        self.st = os.path.join(self.sk, ".claude", "state")
        self.fd = os.path.join(self.st, "frentes", F)
        self.fake_py = escrever(self.tmp, "fake/ac.py", FAKE_AC)
        self.fake_log = os.path.join(self.tmp, "fake-ac.log")
        self.extra = {}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- execução
    def env(self, fake=None, ok="", extra=None):
        e = dict(self.extra)
        if fake if fake is not None else self.fake:
            e.update({"CS_DEV_AC": self.fake_py, "FAKE_AC_LOG": self.fake_log, "FAKE_AC_OK": ok})
        e.update(extra or {})
        return env_limpo(self.tmp, self.sk, e)

    def tool(self, nome):
        return os.path.join(self.sk, ".claude", "tools", nome)

    def py(self, script, *a, **kw):
        return rodar([PY, self.tool(script)] + list(a), self.env(kw.get("fake"), kw.get("ok", "")),
                     kw.get("cwd", self.sk), kw.get("stdin"))

    def sh(self, script, *a, **kw):
        return rodar(["bash", self.tool(script)] + list(a), self.env(kw.get("fake"), kw.get("ok", "")),
                     kw.get("cwd", self.sk))

    def ac(self, *a):
        return rodar([PY, self.tool("ac/ac.py")] + list(a), self.env(False), self.sk)

    def fr(self, *a, **kw):
        return self.py("frente.py", *a, **kw)

    def ok(self, r, msg=""):
        self.assertEqual(r[0], 0, "%s\nstdout:\n%s\nstderr:\n%s" % (msg, r[1][-3000:], r[2][-3000:]))
        return r

    # --- fluxo criar-frente
    def iniciar(self, demanda="quero que um e dois devolvam o dobro"):
        return self.fr("criar", "iniciar", F, "--demanda", demanda)

    def propor(self, etapa, arquivo=None):
        a = ["criar", "propor", F, "--etapa", etapa, "--json"]
        if arquivo:
            a += ["--arquivo", arquivo]
        return self.fr(*a)

    def aprovar(self, etapa, sha, palavra="ok"):
        return self.fr("criar", "aprovar", F, "--etapa", etapa, "--sha", sha, "--palavra", palavra,
                       "--produzido", "artefato da etapa %s" % etapa, "--medido", "2 arquivos",
                       "--proxima", "etapa seguinte", "--json")

    def preparar(self, etapa):
        if etapa == "E1":
            return escrever(self.tmp, "prop/E1.md", E1_OK)
        if etapa == "E2":
            return escrever(self.tmp, "prop/E2.md", E2_OK)
        if etapa == "E3":
            escrever(self.fd, "FRENTE.md", FRENTE_OK)
            return None
        if etapa == "E4":
            for tid, txt in tasks_ok().items():
                escrever(self.fd, "TASKS/%s.md" % tid, txt)
            return None
        return escrever(self.tmp, "prop/E5.md", E5_OK)

    def etapa_ok(self, etapa):
        r = self.ok(self.propor(etapa, self.preparar(etapa)), "propor " + etapa)
        sha = jload(r[1])["sha"]
        self.ok(self.aprovar(etapa, sha), "aprovar " + etapa)
        return sha

    def fluxo(self, ate="E5"):
        self.ok(self.iniciar(), "iniciar")
        for e in ("E1", "E2", "E3", "E4", "E5"):
            self.etapa_ok(e)
            if e == ate:
                return

    def abrir(self, **kw):
        self.fluxo()
        return self.ok(self.fr("criar", "abrir", F, "--json", **kw), "abrir")

    def checklist(self):
        return ler(os.path.join(self.fd, "CHECKLIST.md"))

    def frentes_json(self):
        p = os.path.join(self.st, "frentes.json")
        return jload(ler(p)) if os.path.exists(p) else {"ativas": [], "entregues": []}

    def ids_ativas(self):
        return [x["id"] for x in self.frentes_json().get("ativas", [])]

    def head(self):
        return git(self.sk, "rev-parse", "HEAD")[1]

    def campanha(self, nome, *scopes):
        a = ["--work", "campanhas/" + nome, "init", "--target", "."]
        for s in scopes:
            a += ["--scope", s]
        self.ok(self.ac(*(a + ["--problem", "p", "--stop", "s"])), "init " + nome)

    def handoff(self, tid):
        p = os.path.join(self.fd, "TASKS", tid + ".md")
        escrever(self.fd, "TASKS/%s.md" % tid, ler(p).rstrip() + "\n- entrega: %s concluída com evidência.\n" % tid)

    def marcar(self, tid, status="DONE", gate="PASS"):
        return self.fr("task", "marcar", F, tid, "--status", status, "--gate", gate)


# ================================================================================================ fronteira
class Fronteira(unittest.TestCase):
    """Só desenvolvimento: o produto não muda, o pacote não leva nada do harness, o portão roda o harness."""

    def test_produto_identico_ao_head(self):
        rc, top = git(SKILL_VIVA, "rev-parse", "--show-toplevel")
        if rc != 0:
            self.skipTest("pasta do oráculo fora de um repositório git")
        top = os.path.realpath(top)
        pfx = os.path.relpath(SKILL_VIVA, top)
        pfx = "" if pfx == "." else pfx + "/"
        rc, out = git(top, "ls-tree", "-r", "HEAD", "--", *[pfx + p for p in PRODUTO])
        self.assertEqual(rc, 0)
        head = {}
        for linha in out.splitlines():
            meta, caminho = linha.split("\t", 1)
            if meta.split()[1] == "blob":
                head[caminho[len(pfx):]] = meta.split()[2]
        self.assertGreater(len(head), 50)
        ruins = []
        for rel, blob in sorted(head.items()):
            p = os.path.join(PROJ, rel)
            if os.path.islink(p) or not os.path.isfile(p):
                ruins.append("AUSENTE " + rel)
                continue
            with open(p, "rb") as fh:
                dados = fh.read()
            if hashlib.sha1(b"blob %d\0" % len(dados) + dados).hexdigest() != blob:
                ruins.append("MUDOU " + rel)
        if PROJ != SKILL_VIVA:   # cópia (portão): nada novo nas pastas do produto
            for raiz in PRODUTO:
                base = os.path.join(PROJ, raiz)
                for d, dirs, files in os.walk(base):
                    dirs[:] = [x for x in dirs if x != "__pycache__"]
                    for f in files:
                        rel = os.path.relpath(os.path.join(d, f), PROJ).replace(os.sep, "/")
                        if rel not in head and not f.endswith(".pyc") and f != ".DS_Store":
                            ruins.append("NOVO " + rel)
        self.assertEqual(ruins, [], "a frente harness-dev não pode tocar o produto")

    def test_pacote_sem_nada_do_harness(self):
        tmp = os.path.realpath(tempfile.mkdtemp(prefix="hd-pk-"))
        try:
            sk = os.path.join(tmp, "proj")
            shutil.copytree(PROJ, sk, symlinks=True, ignore=shutil.ignore_patterns(
                ".git", "local", "dist", "__pycache__", "*.pyc", ".auto-correcao", "campanhas"))
            env = env_limpo(tmp, sk)
            rc, out, err = rodar(["bash", os.path.join(sk, ".claude/tools/package.sh"), "--worktree",
                                  "--sem-validar"], env, sk)
            self.assertEqual(rc, 0, out[-2000:] + err[-2000:])
            pk = os.path.join(sk, "dist", "codebase-specialists")
            dev = set()
            for d, _, fs in os.walk(os.path.join(sk, ".claude")):
                for f in fs:
                    with open(os.path.join(d, f), "rb") as fh:
                        dev.add(hashlib.sha256(fh.read()).hexdigest())
            ruins = []
            for d, dirs, fs in os.walk(pk):
                for f in fs:
                    rel = os.path.relpath(os.path.join(d, f), pk).replace(os.sep, "/")
                    if rel.startswith(".claude/") or "/.claude/" in rel:
                        ruins.append("caminho do harness: " + rel)
                    if f == "SKILL.md" and rel != "SKILL.md":
                        ruins.append("SKILL.md fora da raiz: " + rel)
                    with open(os.path.join(d, f), "rb") as fh:
                        dados = fh.read()
                    if len(dados) > 200 and hashlib.sha256(dados).hexdigest() in dev:
                        ruins.append("conteúdo copiado do harness: " + rel)
            self.assertEqual(ruins, [])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_validador_acusa_skill_de_dev_no_pacote(self):
        sys.path.insert(0, os.path.join(PROJ, ".claude", "tools"))
        try:
            import package_validar as pv
        finally:
            sys.path.pop(0)
        tmp = tempfile.mkdtemp()
        try:
            escrever(tmp, "SKILL.md", "x")
            escrever(tmp, ".claude/skills/criar-frente/SKILL.md", "x")
            self.assertIn(".claude/skills/criar-frente/SKILL.md", pv.vazamentos(tmp))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ================================================================================================ skills
class Skills(unittest.TestCase):
    """Os comandos do harness: em português, ricos na prosa do processo, finos na mecânica (só chamam scripts)."""

    @classmethod
    def setUpClass(cls):
        cls.base = os.path.join(PROJ, ".claude", "skills")
        cls.txt = {}
        if os.path.isdir(cls.base):
            for n in os.listdir(cls.base):
                p = os.path.join(cls.base, n, "SKILL.md")
                if os.path.isfile(p):
                    cls.txt[n] = ler(p)

    def s(self, n):
        self.assertIn(n, self.txt, "skill %s ausente" % n)
        return self.txt[n]

    def test_conjunto_exato_de_skills(self):
        self.assertEqual(sorted(x for x in os.listdir(self.base) if not x.startswith(".")), SKILLS)

    def test_substituidas_nao_existem(self):
        for n in SUBSTITUIDAS:
            self.assertFalse(os.path.exists(os.path.join(self.base, n)), n)

    def test_frontmatter_nome_e_descricao(self):
        for n in SKILLS:
            t = self.s(n)
            self.assertTrue(t.startswith("---\nname: %s\n" % n), n)
            self.assertRegex(frontmatter(t), r"(?m)^description:", n)

    def test_disable_model_invocation_onde_muda_estado(self):
        for n in SKILLS:
            fm = frontmatter(self.s(n))
            tem = bool(re.search(r"(?m)^disable-model-invocation:\s*true\s*$", fm))
            if n in MUDAM_ESTADO:
                self.assertTrue(tem, "%s muda estado: precisa de disable-model-invocation: true" % n)
            else:
                self.assertFalse(tem, "%s é só leitura: o modelo pode invocá-la" % n)

    def test_skills_finas_sem_logica_embutida(self):
        proibido = re.compile(r"<<\s*'?[A-Z]+|python3? -c |python3? - |^\s*def \w+\(|^\s*while IFS|^\s*for \w+ in .*; do",
                              re.M)
        for n in SKILLS:
            m = proibido.search(self.s(n))
            self.assertIsNone(m, "%s embute lógica (%r): vira script em .claude/tools/" % (n, m and m.group(0)))

    def test_scripts_citados_existem_e_subcomandos_existem(self):
        tools = os.path.join(PROJ, ".claude", "tools")
        for n in SKILLS:
            t = self.s(n)
            citados = set(re.findall(r"\.claude/tools/([A-Za-z0-9_./-]+\.(?:py|sh|json))", t))
            self.assertTrue(citados, "%s não chama nenhum script de .claude/tools/" % n)
            for c in citados:
                self.assertTrue(os.path.isfile(os.path.join(tools, c)), "%s cita %s, que não existe" % (n, c))
            for script, sub in re.findall(r"python3 \.claude/tools/([\w-]+\.py) ([a-z][a-z-]+)", t):
                if SCRIPTS.get(script):
                    self.assertIn(sub, SCRIPTS[script], "%s: %s não tem o subcomando %s" % (n, script, sub))

    def termos(self, n, termos):
        t = self.s(n)
        falta = [x for x in termos if x.lower() not in t.lower()]
        self.assertEqual(falta, [], "%s pobre: faltam %s" % (n, falta))

    def test_criar_frente_rica(self):
        self.termos("criar-frente", ["E0", "E1", "E2", "E3", "E4", "E5", "CHECKLIST", "frente.py criar iniciar",
                                     "frente.py criar propor", "frente.py criar aprovar", "frente.py criar rejeitar",
                                     "frente.py criar abrir", "contrato.py", "--sonda", "script-aprovacao.sh",
                                     "agente separado", "pare", "retom", "Medir antes de afirmar", "DADO",
                                     "Arquivos permitidos", "grupo"])
        self.assertRegex(self.s("criar-frente"), r"(?i)(nunca|não) commita")

    def test_fechar_frente_rica(self):
        self.termos("fechar-frente", ["frente.py fechar check", "frente.py fechar archive", "frente.py fechar entrega",
                                      "frente.py fechar limpar", "frente.py fechar idle", "frente.py fechar commit",
                                      "frente.py fechar plano", "conferir-commit", "frase conferir", "LAST_DELIVERY",
                                      "archive", "campanha.py fechar", "push", "idempot", "install"])

    def test_tech_lead_rica(self):
        self.termos("tech-lead", ["autônomo", "iterativo", "status", "tech_lead.py plano", "tech_lead.py modelo",
                                  "tech_lead.py snap", "custo.py registrar", "frente.py task marcar", "rh", "revisor",
                                  "e2e-loop", "auto-correcao", "criar-frente", "fechar-frente", "carregar-sessao",
                                  "LACUNAS", "IMPASSE", "NOT_RUN", "push"])

    def test_sessao_ricas(self):
        self.termos("carregar-sessao", ["sessao.py frescor", "sessao.py briefing", "Retomo daqui?", "cache-miss",
                                        "carimbo"])
        self.termos("salvar-sessao", ["sessao.py salvar", "--commit", "--dry-run", "push", "privacidade",
                                      "DECISIONS", "BACKLOG"])

    def test_rh_revisor_e2e(self):
        self.termos("rh", ["rh.py ficha", "rh.py conferir", "rh.py elenco", "SOMENTE LEITURA", "FAZER DIRETO",
                           "LACUNAS", "CONFIRMADO", "SUSPEITA"])
        self.termos("revisor", ["APPROVED", "CHANGES_REQUESTED", "BLOQUEANTE", "REGRESSÃO", "PRÉ-EXISTENTE",
                                "CONFIRMADO", "SUSPEITA", "LACUNAS", "CA-"])
        self.termos("e2e-loop", ["e2e.py regua", "e2e.py selecionar", "--fechamento", "NOT_RUN", "portao.sh"])

    def test_revisor_sem_escrita(self):
        fm = frontmatter(self.s("revisor"))
        m = re.search(r"(?m)^allowed-tools:(.*)$", fm)
        self.assertIsNotNone(m, "revisor precisa de allowed-tools (sem ferramentas de escrita)")
        for f in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
            self.assertNotRegex(m.group(1), r"\b%s\b" % f)

    def test_auto_correcao_usa_motor_embutido(self):
        t = self.s("auto-correcao")
        self.termos("auto-correcao", ["python3 .claude/tools/ac/ac.py", "campanha.py etapa",
                                      "campanha.py mudanca-oficial", "campanha.py fechar", "intake", "oraculo", "base",
                                      "diagnostico", "plano", "correcao", "integracao", "remedicao", "decisao",
                                      "oracle freeze", "frase conferir", "script-aprovacao.sh", "agente separado"])
        self.assertNotIn("skills/auto-correcao", t)
        self.assertNotIn("$AC/", t)

    def test_claude_md_cita_os_comandos(self):
        t = ler(os.path.join(PROJ, ".claude", "CLAUDE.md"))
        for n in SKILLS:
            self.assertIn(n, t, "CLAUDE.md não cita %s" % n)

    def test_nomes_substituidos_nao_aparecem_no_harness(self):
        ruins = []
        base = os.path.join(PROJ, ".claude")
        for d, dirs, fs in os.walk(base):
            rel_d = os.path.relpath(d, base).replace(os.sep, "/")
            if rel_d.startswith("state") or rel_d.startswith("tools/tests"):
                dirs[:] = []
                continue
            dirs[:] = [x for x in dirs if x != "__pycache__"]
            for f in fs:
                try:
                    t = ler(os.path.join(d, f))
                except (UnicodeDecodeError, OSError):
                    continue
                for n in ("new" + "-front", "close" + "-front", "skill load" + "-session", "skill save" + "-session",
                          "/load" + "-session", "/save" + "-session"):
                    if n in t:
                        ruins.append("%s/%s: %s" % (rel_d, f, n))
        self.assertEqual(ruins, [])

    def test_settings_liga_os_guards(self):
        s = jload(ler(os.path.join(PROJ, ".claude", "settings.json")))
        pares = [(m.get("matcher", ""), h["command"]) for ev in s["hooks"].values() for m in ev for h in m["hooks"]]
        self.assertTrue(any("Write" in m and "Edit" in m and "guard-estado.py" in c for m, c in pares))
        self.assertTrue(any("Agent" in m and "exige-modelo.py" in c for m, c in pares))
        for _, c in pares:
            for rel in re.findall(r"\.claude/tools/([A-Za-z0-9_./-]+\.(?:py|sh))", c):
                self.assertTrue(os.path.isfile(os.path.join(PROJ, ".claude", "tools", rel)), rel)


class Ajuda(unittest.TestCase):
    def test_scripts_existem_com_help(self):
        tools = os.path.join(PROJ, ".claude", "tools")
        for nome, subs in SCRIPTS.items():
            p = os.path.join(tools, nome)
            self.assertTrue(os.path.isfile(p), nome)
            rc, out, err = rodar([PY, p, "--help"], env_limpo(tempfile.gettempdir(), PROJ), PROJ)
            self.assertEqual(rc, 0, nome + err)
            for sub in subs:
                self.assertIn(sub, out, "%s --help não cita %s" % (nome, sub))
        for nome in ("frente.py", "sessao.py", "campanha.py"):
            rc, out, _ = rodar([PY, os.path.join(tools, nome), "--help"], env_limpo(tempfile.gettempdir(), PROJ),
                               PROJ)
            self.assertIn("--json", out, nome)
        rc, out, _ = rodar([PY, os.path.join(tools, "frente.py"), "--help"], env_limpo(tempfile.gettempdir(), PROJ),
                           PROJ)
        self.assertIn("--brief", out)

    def test_dados_json_validos(self):
        for nome in DADOS:
            jload(ler(os.path.join(PROJ, ".claude", "tools", nome)))
        r = jload(ler(os.path.join(PROJ, ".claude", "tools", "regras.json")))
        self.assertIn(r.get("max_frentes_ativas"), (1, 2))

    def test_motor_embutido_intacto(self):
        txt = ler(os.path.join(PROJ, ".claude", "tools", "ac", "ORIGEM.txt"))
        emb = txt.split("sha256 EMBUTIDO")[1]
        linhas = re.findall(r"^\s+([0-9a-f]{64})\s+(\S+)$", emb, re.M)
        self.assertEqual(len(linhas), 7)
        for sha, rel in linhas:
            with open(os.path.join(PROJ, ".claude", "tools", "ac", rel), "rb") as fh:
                self.assertEqual(hashlib.sha256(fh.read()).hexdigest(), sha, rel)


# ================================================================================================ contrato (guard de schema)
class Contrato(unittest.TestCase):
    """contrato.py: Bloco A (FRENTE.md), Bloco B (tasks), cobertura, grupos, depends, etapas E1/E2/E5, complexidade."""

    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="hd-ct-"))
        self.d = os.path.join(self.tmp, "frentes", F)
        escrever(self.d, "FRENTE.md", FRENTE_OK)
        for tid, txt in tasks_ok().items():
            escrever(self.d, "TASKS/%s.md" % tid, txt)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def c(self, *a):
        return rodar([PY, os.path.join(PROJ, ".claude", "tools", "contrato.py")] + list(a),
                     env_limpo(self.tmp, PROJ), self.tmp)

    def lacunas(self, *a):
        rc, out, err = self.c(*(list(a) + ["--json"]))
        self.assertIn(rc, (0, 2), out + err)
        j = jload(out)
        self.assertEqual(j["ok"], rc == 0)
        return rc, [x["codigo"] for x in j["lacunas"]]

    def task(self, tid, txt=None, apagar=False):
        p = os.path.join(self.d, "TASKS", tid + ".md")
        if apagar:
            os.remove(p)
        else:
            escrever(self.d, "TASKS/%s.md" % tid, txt)

    def reprova(self, pedaco):
        rc, cods = self.lacunas("completo", self.d)
        self.assertEqual(rc, 2, cods)
        self.assertTrue(any(pedaco in c for c in cods), "esperava lacuna com %r em %s" % (pedaco, cods))

    def test_frente_e_tasks_validas_passam(self):
        rc, cods = self.lacunas("completo", self.d)
        self.assertEqual((rc, cods), (0, []))
        rc, cods = self.lacunas("frente", os.path.join(self.d, "FRENTE.md"))
        self.assertEqual((rc, cods), (0, []))

    def test_sonda_negativa(self):
        rc, out, err = self.c("--sonda")
        self.assertEqual(rc, 0, out + err)

    def test_task_sem_goal_reprova(self):
        tid, txt = task_md("02", "UM", "CORRECAO", "G1", "CA-01", "01-TASK-ORACULO (o oráculo vem antes)",
                           ["a/um.py"], goal=False)
        self.task(tid, txt)
        self.reprova("Goal")

    def test_task_sem_ac_reprova(self):
        _, txt = task_md("02", "UM", "CORRECAO", "G1", "CA-01", "01-TASK-ORACULO (o oráculo vem antes)", ["a/um.py"])
        self.task("02-TASK-UM", txt.replace("## AC\n- o teste da tarefa falha antes e passa depois.\n", ""))
        self.reprova("AC")

    def test_arquivo_com_glob_reprova(self):
        _, txt = task_md("02", "UM", "CORRECAO", "G1", "CA-01", "01-TASK-ORACULO (o oráculo vem antes)", ["a/*.py"])
        self.task("02-TASK-UM", txt)
        self.reprova("arquivo_glob")

    def test_arquivo_fora_do_escopo_reprova(self):
        _, txt = task_md("02", "UM", "CORRECAO", "G1", "CA-01", "01-TASK-ORACULO (o oráculo vem antes)",
                         ["scripts/emit/render.py"])
        self.task("02-TASK-UM", txt)
        self.reprova("fora_do_escopo")

    def test_verificacao_trivial_reprova(self):
        _, txt = task_md("02", "UM", "CORRECAO", "G1", "CA-01", "01-TASK-ORACULO (o oráculo vem antes)", ["a/um.py"],
                         verif="echo ok")
        self.task("02-TASK-UM", txt)
        self.reprova("verificacao_trivial")

    def test_ca_orfao_reprova(self):
        escrever(self.d, "FRENTE.md", FRENTE_OK.replace(
            "## RNFs", "- **CA-03 — sobra.** DADO x, QUANDO y, ENTÃO z.\n  Prova: `python3 -m unittest test_demo`\n\n## RNFs"))
        self.reprova("ca_orfao")

    def test_sem_qa_e_sem_review_reprova(self):
        self.task("04-TASK-QA", apagar=True)
        self.reprova("qa_ausente")
        self.task("05-TASK-REVIEW", apagar=True)
        self.reprova("review_ausente")

    def test_sem_oraculo_ou_oraculo_fora_da_pasta_reprova(self):
        _, txt = task_md("01", "ORACULO", "ORACULO", "—", "CA-01, CA-02", "—", ["a/teste.py"])
        self.task("01-TASK-ORACULO", txt)
        self.reprova("oraculo_fora_da_pasta")
        self.task("01-TASK-ORACULO", apagar=True)
        self.reprova("oraculo_ausente")

    def test_correcao_escreve_no_oraculo_reprova(self):
        _, txt = task_md("02", "UM", "CORRECAO", "G1", "CA-01", "01-TASK-ORACULO (o oráculo vem antes)",
                         ["a/um.py", "campanhas/demo-x/oraculo/test_demo.py"])
        self.task("02-TASK-UM", txt)
        self.reprova("correcao_escreve_oraculo")

    def test_correcao_sem_depender_do_oraculo_reprova(self):
        _, txt = task_md("02", "UM", "CORRECAO", "G1", "CA-01", "—", ["a/um.py"])
        self.task("02-TASK-UM", txt)
        self.reprova("sem_depender_do_oraculo")

    def test_mesmo_arquivo_sem_ordem_reprova(self):
        dep1 = "01-TASK-ORACULO (o oráculo congelado vem antes)"
        _, txt = task_md("03", "DOIS", "CORRECAO", "G1", "CA-02", dep1, ["a/dois.py", "a/um.py"])
        self.task("03-TASK-DOIS", txt)
        self.reprova("mesmo_arquivo_sem_ordem")

    def test_grupos_colidem_reprova(self):
        dep = "01-TASK-ORACULO (o oráculo vem antes), 02-TASK-UM (mesmo arquivo depois da 02)"
        _, txt = task_md("03", "DOIS", "CORRECAO", "G2", "CA-02", dep, ["a/dois.py", "a/um.py"])
        self.task("03-TASK-DOIS", txt)
        self.reprova("grupos_colidem")

    def test_depends_sem_porque_e_inexistente_reprovam(self):
        _, txt = task_md("02", "UM", "CORRECAO", "G1", "CA-01", "01-TASK-ORACULO", ["a/um.py"])
        self.task("02-TASK-UM", txt)
        self.reprova("depends_sem_porque")
        _, txt = task_md("02", "UM", "CORRECAO", "G1", "CA-01",
                         "01-TASK-ORACULO (o oráculo vem antes), 09-TASK-NADA (não existe)", ["a/um.py"])
        self.task("02-TASK-UM", txt)
        self.reprova("depends_inexistente")

    def test_nome_de_task_invalido_reprova(self):
        _, txt = task_md("02", "UM", "CORRECAO", "G1", "CA-01", "01-TASK-ORACULO (o oráculo vem antes)", ["a/um.py"])
        self.task("02-TASK-UM", apagar=True)
        escrever(self.d, "TASKS/2-task-um.md", txt)
        self.reprova("task_nome_invalido")

    def test_ca_sem_prova_e_sem_dado_quando_entao_reprovam(self):
        escrever(self.d, "FRENTE.md", FRENTE_OK.replace("  Prova: `python3 -m unittest test_demo.TestUm`\n", ""))
        rc, cods = self.lacunas("frente", os.path.join(self.d, "FRENTE.md"))
        self.assertTrue(any("ca_sem_prova" in c and "CA-01" in c for c in cods), cods)
        escrever(self.d, "FRENTE.md", FRENTE_OK.replace("DADO a função `um`, QUANDO chamada, ENTÃO devolve 2.",
                                                        "um deve funcionar corretamente."))
        rc, cods = self.lacunas("frente", os.path.join(self.d, "FRENTE.md"))
        self.assertTrue(any("ca_sem_dado_quando_entao" in c for c in cods), cods)

    def test_campos_do_bloco_a_e_id(self):
        escrever(self.d, "FRENTE.md", FRENTE_OK.replace("## RNFs\n- RNF-01: só biblioteca padrão; Python 3.9+.\n", ""))
        rc, cods = self.lacunas("frente", os.path.join(self.d, "FRENTE.md"))
        self.assertEqual(rc, 2)
        self.assertTrue(any("campo_ausente" in c and "RNF" in c for c in cods), cods)
        escrever(self.d, "FRENTE.md", FRENTE_OK.replace("FRENTE-ID: demo-x", "FRENTE-ID: Demo_X"))
        rc, cods = self.lacunas("frente", os.path.join(self.d, "FRENTE.md"))
        self.assertTrue(any("id_invalido" in c for c in cods), cods)
        escrever(self.d, "FRENTE.md", FRENTE_OK.replace("- `a/um.py`\n- `a/dois.py`\n\n## Critério",
                                                        "- `**`\n\n## Critério"))
        rc, cods = self.lacunas("frente", os.path.join(self.d, "FRENTE.md"))
        self.assertTrue(any("escopo_amplo" in c for c in cods), cods)

    def test_etapas_e1_e2_e5(self):
        for etapa, txt in (("E1", E1_OK), ("E2", E2_OK), ("E5", E5_OK)):
            p = escrever(self.tmp, "e/%s.md" % etapa, txt)
            self.assertEqual(self.lacunas("etapa", etapa, p), (0, []), etapa)
        p = escrever(self.tmp, "e/E2b.md", E2_SEM_EVIDENCIA)
        rc, cods = self.lacunas("etapa", "E2", p)
        self.assertEqual(rc, 2)
        self.assertTrue(any("e2_sem_evidencia" in c for c in cods), cods)
        p = escrever(self.tmp, "e/E1b.md", E1_OK.replace("O que NÃO é: não é mudança no produto real.\n", ""))
        rc, cods = self.lacunas("etapa", "E1", p)
        self.assertTrue(rc == 2 and any("etapa_campo_ausente" in c for c in cods), cods)

    def test_complexidade_baixa(self):
        dep = "01-TASK-ORACULO (o oráculo vem antes)"
        casos = (("ok", ["a/um.py"], None, 0), ("tres", ["a/um.py", "a/dois.py", "a/tres.py"], None, 2),
                 ("sens", [".claude/tools/guard-estado.py"], None, 2), ("eco", ["a/um.py"], "echo feito", 2))
        for nome, arqs, verif, esperado in casos:
            _, txt = task_md("02", "UM", "CORRECAO", "G1", "CA-01", dep, arqs, verif=verif, complexidade="baixa")
            p = escrever(self.tmp, "t/%s.md" % nome, txt)
            self.assertEqual(self.c("complexidade", p)[0], esperado, nome)


# ================================================================================================ criar-frente
class CriarFrente(Copia):
    """E0→E5 com aprovação registrada entre cada etapa, checklist append-only, abertura sem commit."""

    def test_e0_aborta_sem_state(self):
        shutil.rmtree(self.st)
        rc, out, err = self.iniciar()
        self.assertEqual(rc, 1)
        self.assertIn("salvar-sessao", out + err)
        self.assertFalse(os.path.exists(self.st))

    def test_e0_cria_so_o_checklist(self):
        self.ok(self.iniciar())
        t = self.checklist()
        self.assertRegex(t, r"(?m)^- \[x\] \*\*E0\b.*OK")
        for e in ("E1", "E2", "E3", "E4", "E5"):
            self.assertRegex(t, r"(?m)^- \[ \] \*\*%s\b" % e)
        self.assertIn('Demanda: "quero que um e dois devolvam o dobro"', t)
        self.assertIn("### E0", t)
        self.assertFalse(os.path.exists(os.path.join(self.fd, "FRENTE.md")))
        self.assertFalse(os.path.exists(os.path.join(self.fd, "TASKS")))
        self.assertEqual(self.ids_ativas(), [])

    def test_e0_dry_run_nao_escreve(self):
        antes = arvore(self.sk)
        self.ok(self.fr("criar", "iniciar", F, "--demanda", "x", "--dry-run"))
        self.assertEqual(arvore(self.sk), antes)

    def test_e0_id_invalido_e_segunda_criacao(self):
        self.assertEqual(self.fr("criar", "iniciar", "Demo_X", "--demanda", "x")[0], 1)
        self.ok(self.iniciar())
        rc, out, err = self.fr("criar", "iniciar", "demo-y", "--demanda", "outra")
        self.assertEqual(rc, 1, out + err)
        self.assertFalse(os.path.exists(os.path.join(self.st, "frentes", "demo-y")))

    def test_limite_de_frentes_ativas(self):
        mx = jload(ler(self.tool("regras.json")))["max_frentes_ativas"]
        for i in range(mx):
            self.campanha("velha%d" % i, "b%d/x.py" % i)
            self.ok(self.fr("adotar", "velha%d" % i))
        rc, out, err = self.iniciar()
        self.assertEqual(rc, 1, out + err)
        self.assertIn("limite", (out + err).lower())
        self.assertFalse(os.path.exists(self.fd))

    def test_adotar_frente_legada(self):
        self.assertEqual(self.fr("adotar", "nada")[0], 1)
        self.campanha("velha", "b/x.py")
        self.ok(self.fr("adotar", "velha"))
        self.ok(self.fr("adotar", "velha"))
        j = jload(self.ok(self.fr("status", "--json"))[1])
        self.assertEqual([(x["id"], x["origem"]) for x in j["ativas"]], [("velha", "legado")])
        self.assertEqual(j["estado"], "IN_PROGRESS")

    def test_nao_avanca_sem_aprovacao(self):
        self.ok(self.iniciar())
        self.assertEqual(self.propor("E2", self.preparar("E2"))[0], 1, "E2 antes de E1 aprovada")
        sha = jload(self.ok(self.propor("E1", self.preparar("E1")))[1])["sha"]
        self.assertEqual(self.propor("E1", self.preparar("E1"))[0], 1, "proposta pendente sem decisão")
        self.assertEqual(self.propor("E2", self.preparar("E2"))[0], 1, "E2 sem aprovar E1")
        self.ok(self.aprovar("E1", sha))
        for e in ("E2", "E3", "E4"):
            self.etapa_ok(e)
        rc, out, err = self.fr("criar", "abrir", F)
        self.assertEqual(rc, 1, "abrir sem E5 aprovada: " + out + err)
        self.assertFalse(os.path.exists(os.path.join(self.sk, "campanhas", F, ".auto-correcao")))
        self.assertEqual(self.ids_ativas(), [])

    def test_aprovacao_exige_sha_atual_e_palavra_literal(self):
        self.ok(self.iniciar())
        sha = jload(self.ok(self.propor("E1", self.preparar("E1")))[1])["sha"]
        self.assertEqual(self.aprovar("E1", "0" * 64)[0], 1)
        self.assertEqual(self.aprovar("E1", sha, palavra="talvez")[0], 1)
        self.assertEqual(self.aprovar("E1", sha, palavra="")[0], 1)
        self.assertRegex(self.checklist(), r"(?m)^- \[ \] \*\*E1\b")
        self.ok(self.aprovar("E1", sha))
        self.assertRegex(self.checklist(), r"(?m)^- \[x\] \*\*E1\b.*OK")

    def test_checklist_marcado_a_cada_handoff_e_append_only(self):
        self.ok(self.iniciar())
        self.etapa_ok("E1")
        t1 = self.checklist()
        h1 = t1[t1.index("## Handoffs"):]
        self.assertRegex(h1, r'### E1 — .*\n(?:.*\n)*?- Aprovação: "ok"')
        self.etapa_ok("E2")
        t2 = self.checklist()
        self.assertTrue(t2[t2.index("## Handoffs"):].startswith(h1.rstrip("\n")), "handoffs são append-only")
        self.assertRegex(t2, r"(?m)^- \[x\] \*\*E2\b.*OK")
        self.assertRegex(t2, r"(?m)^- \[ \] \*\*E3\b")
        self.ok(self.fr("checklist", F, "--json"))

    def test_rejeicao_registrada_sem_marcar(self):
        self.ok(self.iniciar())
        self.etapa_ok("E1")
        sha = jload(self.ok(self.propor("E2", self.preparar("E2")))[1])["sha"]
        self.ok(self.fr("criar", "rejeitar", F, "--etapa", "E2", "--sha", sha, "--motivo", "investigar mais"))
        t = self.checklist()
        self.assertRegex(t, r"### E2 — REJEITADA.*investigar mais")
        self.assertRegex(t, r"(?m)^- \[ \] \*\*E2\b")
        self.assertEqual(self.aprovar("E2", sha)[0], 1, "proposta rejeitada não pode ser aprovada")
        sha2 = jload(self.ok(self.propor("E2", self.preparar("E2")))[1])["sha"]
        self.ok(self.aprovar("E2", sha2))

    def test_checklist_adulterado_detectado(self):
        self.fluxo(ate="E2")
        p = os.path.join(self.fd, "CHECKLIST.md")
        escrever(self.fd, "CHECKLIST.md", re.sub(r"(?m)^- \[ \] \*\*E3", "- [x] **E3", ler(p)))
        rc, out, _ = self.fr("checklist", F, "--json")
        self.assertEqual(rc, 2)
        self.assertFalse(jload(out)["ok"])

    def test_e2_sem_evidencia_e_bloco_a_pobre_recusados(self):
        self.ok(self.iniciar())
        self.etapa_ok("E1")
        rc, out, _ = self.propor("E2", escrever(self.tmp, "prop/E2b.md", E2_SEM_EVIDENCIA))
        self.assertEqual(rc, 2)
        self.etapa_ok("E2")
        escrever(self.fd, "FRENTE.md", FRENTE_OK.replace("## Edge cases\n- chamada repetida devolve o mesmo valor.\n",
                                                         ""))
        rc, out, _ = self.propor("E3")
        self.assertEqual(rc, 2)
        self.assertIn("Edge", out)

    def test_e3_aceita_ca_orfao_e4_exige_contrato_completo(self):
        self.fluxo(ate="E2")
        self.preparar("E3")
        sha = jload(self.ok(self.propor("E3"))[1])["sha"]   # sem tasks ainda: CA órfão espera a E4
        self.ok(self.aprovar("E3", sha))
        tasks = tasks_ok()
        _, sem_goal = task_md("02", "UM", "CORRECAO", "G1", "CA-01", "01-TASK-ORACULO (o oráculo vem antes)",
                              ["a/um.py"], goal=False)
        tasks["02-TASK-UM"] = sem_goal
        for tid, txt in tasks.items():
            escrever(self.fd, "TASKS/%s.md" % tid, txt)
        rc, out, _ = self.propor("E4")
        self.assertEqual(rc, 2)
        self.assertIn("Goal", out)

    def test_retomada(self):
        self.fluxo(ate="E2")
        rc, out, err = self.iniciar()
        self.assertEqual(rc, 0, out + err)
        self.assertIn("E3", out)
        j = jload(self.ok(self.fr("status", "--json"))[1])
        self.assertEqual(j["criacao"]["id"], F)
        self.assertEqual(j["criacao"]["proxima"], "E3")
        self.assertEqual(self.iniciar("outra demanda")[0], 1)

    def test_alteracao_depois_da_aprovacao_bloqueia_abertura(self):
        self.fluxo()
        escrever(self.fd, "FRENTE.md", FRENTE_OK + "\nlinha nova depois do ok\n")
        rc, out, err = self.fr("criar", "abrir", F)
        self.assertEqual(rc, 1, out + err)
        self.assertFalse(os.path.exists(os.path.join(self.sk, "campanhas", F, ".auto-correcao")))

    def test_abrir_dry_run_nao_escreve(self):
        self.fluxo()
        antes = arvore(self.sk)
        j = jload(self.ok(self.fr("criar", "abrir", F, "--dry-run", "--json"))[1])
        self.assertEqual(arvore(self.sk), antes)
        self.assertTrue(os.path.realpath(j["motor"]).endswith(os.path.join(".claude", "tools", "ac", "ac.py")))

    def test_abertura_cria_campanha_e_estado_sem_commit(self):
        h0 = self.head()
        j = jload(self.abrir()[1])
        self.assertTrue(j["aberta"])
        self.assertEqual(j["tasks"], 5)
        self.assertEqual(j["primeira"], "01-TASK-ORACULO")
        self.assertEqual(os.path.realpath(j["motor"]), os.path.realpath(self.tool("ac/ac.py")))
        rc, out, _ = self.ac("--work", "campanhas/" + F, "status")
        self.assertEqual(rc, 0)
        self.assertIn("etapa: intake", out)
        est = jload(ler(os.path.join(self.sk, "campanhas", F, ".auto-correcao", "state.json")))
        self.assertEqual(sorted(est["scope"]), ["a/dois.py", "a/um.py"])
        self.assertIn("dobro", est.get("problem", ""))
        self.assertIn("2/2", est.get("stop", ""))
        self.assertEqual(self.ids_ativas(), [F])
        wf = ler(os.path.join(self.st, "WORKFLOW.md"))
        self.assertIn("**Estado:** IN_PROGRESS", wf)
        self.assertIn(F, wf)
        self.assertIn("Nota humana do founder", wf)
        idx = ler(os.path.join(self.fd, "INDEX.md"))
        self.assertIn("Progresso: 0/5", idx)
        self.assertIn("01-TASK-ORACULO (o oráculo congelado vem antes)", idx)
        self.assertEqual(len(re.findall(r"(?m)^\| 0[1-5]-TASK-", idx)), 5)
        hist = ler(os.path.join(self.fd, "HISTORICO.md"))
        self.assertIn("[NOTA]", hist)
        self.assertIn("F1", hist)
        self.assertTrue(os.path.isfile(os.path.join(self.st, "logs", F, F + ".md")))
        t = self.checklist()
        for e in ("E0", "E1", "E2", "E3", "E4", "E5"):
            self.assertRegex(t, r"(?m)^- \[x\] \*\*%s\b" % e)
        self.assertIn("Abertura", t)
        self.assertIn(F, ler(os.path.join(self.sk, "campanhas", "README.md")))
        self.assertEqual(self.head(), h0, "criação nunca commita")
        self.assertEqual(git(self.sk, "diff", "--cached", "--name-only")[1], "")
        self.assertEqual([x for x in os.listdir(os.path.join(self.sk, "local"))
                          if x.endswith(".sh")] if os.path.isdir(os.path.join(self.sk, "local")) else [], [])
        self.assertEqual(self.fr("criar", "abrir", F)[0], 1, "abrir duas vezes")

    def test_colisao_com_frente_ativa_recusa_abertura(self):
        self.campanha("outra", "a/um.py")
        self.ok(self.fr("adotar", "outra"))
        self.fluxo()
        rc, out, err = self.fr("criar", "abrir", F)
        self.assertEqual(rc, 1, out + err)
        self.assertRegex((out + err).lower(), r"colis|overlap|colide")
        self.assertFalse(os.path.exists(os.path.join(self.sk, "campanhas", F, ".auto-correcao")))
        self.assertEqual(self.ids_ativas(), ["outra"])

    def test_script_de_aprovacao_exige_oraculo_congelado(self):
        self.abrir()
        rc, out, err = self.sh("script-aprovacao.sh", F, "--por", "Ana", "--dry-run")
        self.assertNotEqual(rc, 0)
        self.assertRegex(out + err, r"(?i)congel")
        escrever(self.sk, "campanhas/%s/oraculo/test_demo.py" % F, "import unittest\n")
        self.ok(self.ac("--work", "campanhas/" + F, "oracle", "freeze", "--file",
                        "campanhas/%s/oraculo/test_demo.py" % F))
        self.ok(self.sh("script-aprovacao.sh", F, "--por", "Ana"))
        gerados = [x for x in os.listdir(os.path.join(self.sk, "local")) if x.endswith(".sh")]
        self.assertEqual(len(gerados), 1)
        self.assertTrue(os.access(os.path.join(self.sk, "local", gerados[0]), os.X_OK))

    def test_status_e_workflow_em_dia(self):
        self.abrir()
        rc, out, _ = self.fr("status", "--brief")
        self.assertEqual(rc, 0)
        self.assertLessEqual(len(out.splitlines()), 40)
        j = jload(self.fr("status", "--json")[1])
        self.assertEqual(j["ativas"][0]["progresso"], "0/5")
        self.assertTrue(j["workflow_em_dia"])
        p = os.path.join(self.st, "WORKFLOW.md")
        escrever(self.st, "WORKFLOW.md", ler(p).replace("IN_PROGRESS", "IDLE"))
        self.assertFalse(jload(self.fr("status", "--json")[1])["workflow_em_dia"])


# ================================================================================================ tech-lead
class TechLead(Copia):
    """Modo perguntado sempre; plano derivado do disco; corretor só depois da aprovação do founder; registro serial."""

    def tl(self, *a, **kw):
        return self.py("tech_lead.py", *a, **kw)

    def test_plano_exige_o_modo(self):
        self.abrir()
        rc, out, err = self.tl("plano", "--json")
        self.assertEqual(rc, 2, out + err)
        j = jload(out)
        self.assertTrue(j["precisa_modo"])
        self.assertEqual(sorted(j["opcoes"]), ["autonomo", "iterativo", "status"])
        rc, out, err = self.tl("plano")
        self.assertEqual(rc, 2)
        self.assertIn("autônomo", out + err)
        self.assertIn("iterativo", out + err)

    def test_plano_monta_caminho_critico_e_despacho(self):
        self.abrir()
        j = jload(self.ok(self.tl("plano", "--modo", "iterativo", "--json"))[1])
        self.assertEqual(j["modo"], "iterativo")
        fr = j["frentes"][0]
        self.assertEqual(fr["id"], F)
        self.assertEqual(fr["progresso"], "0/5")
        self.assertEqual(fr["proxima"], "01-TASK-ORACULO")
        self.assertEqual(fr["caminho_critico"][0], "01-TASK-ORACULO")
        self.assertEqual(fr["caminho_critico"][-1], "05-TASK-REVIEW")
        self.assertEqual(fr["despacho"]["papel"], "oraculo")
        self.assertEqual(fr["despacho"]["modelo"], "opus")
        self.assertIn("aprovacao_founder", fr["gates_humanos"])
        self.assertIn("aceite_humano", fr["gates_humanos"])
        rc, out, _ = self.tl("plano", "--modo", "autonomo", "--brief")
        self.assertEqual(rc, 0)
        self.assertLessEqual(len(out.splitlines()), 40)

    def test_marcar_task_exige_gate_e_handoff(self):
        self.abrir()
        self.assertEqual(self.marcar("01-TASK-ORACULO", gate="PENDENTE")[0], 1)
        self.assertEqual(self.marcar("01-TASK-ORACULO")[0], 1, "DONE sem Handoff preenchido")
        self.handoff("01-TASK-ORACULO")
        self.ok(self.marcar("01-TASK-ORACULO"))
        t = ler(os.path.join(self.fd, "TASKS", "01-TASK-ORACULO.md"))
        self.assertRegex(t, r"(?m)^status: DONE$")
        self.assertRegex(t, r"(?m)^gate: PASS$")
        idx = ler(os.path.join(self.fd, "INDEX.md"))
        self.assertIn("Progresso: 1/5", idx)
        self.assertRegex(idx, r"(?m)^\| 01-TASK-ORACULO .*DONE")
        self.assertRegex(ler(os.path.join(self.fd, "HISTORICO.md")), r"(?m)^## \[PASS\] 01-TASK-ORACULO")

    def test_corretor_bloqueado_ate_aprovacao_do_founder(self):
        self.abrir()
        self.handoff("01-TASK-ORACULO")
        self.ok(self.marcar("01-TASK-ORACULO"))
        j = jload(self.ok(self.tl("proxima", "--json"))[1])
        self.assertEqual(j["elegiveis"], [])
        self.assertEqual(j["bloqueio"], "aprovacao_founder")
        j = jload(self.ok(self.tl("proxima", "--json", fake=True, ok="intake.3"))[1])
        self.assertEqual(j["elegiveis"], ["02-TASK-UM", "03-TASK-DOIS"])
        self.assertEqual(j["topologia"], "paralelo")
        log = ler(self.fake_log) if os.path.exists(self.fake_log) else ""
        self.assertNotRegex(log, r'"(gate|preauth|frase)"')

    def test_roteamento_por_papel(self):
        dep = "01-TASK-ORACULO (o oráculo vem antes)"
        _, baixa = task_md("02", "UM", "CORRECAO", "G1", "CA-01", dep, ["a/um.py"], complexidade="baixa")
        _, baixa_falsa = task_md("02", "UM", "CORRECAO", "G1", "CA-01", dep, ["a/um.py", "a/dois.py", "a/tres.py"],
                                 complexidade="baixa")
        _, sensivel = task_md("02", "UM", "CORRECAO", "G1", "CA-01", dep, [".claude/tools/guard-estado.py"])
        tb = escrever(self.tmp, "t/baixa.md", baixa)
        tf = escrever(self.tmp, "t/falsa.md", baixa_falsa)
        ts = escrever(self.tmp, "t/sens.md", sensivel)
        casos = [(["--papel", "executor"], "sonnet"), (["--papel", "executor", "--task", tb], "haiku"),
                 (["--papel", "executor", "--task", tf], "sonnet"),
                 (["--papel", "executor", "--task", tb, "--ciclo", "2"], "opus"),
                 (["--papel", "revisor"], "sonnet"), (["--papel", "revisor", "--task", ts], "opus"),
                 (["--papel", "qa"], "sonnet"), (["--papel", "review"], "opus"), (["--papel", "oraculo"], "opus"),
                 (["--papel", "rh:cetico"], "opus"), (["--papel", "rh:diagnosticador"], "sonnet"),
                 (["--papel", "rh:investigador-ambiente"], "haiku")]
        for args, esperado in casos:
            j = jload(self.ok(self.tl("modelo", *(args + ["--json"])), str(args))[1])
            self.assertEqual(j["modelo"], esperado, args)
            self.assertTrue(j.get("motivo"), args)
        self.assertEqual(self.tl("modelo", "--papel", "xpto")[0], 2)

    def test_exige_modelo_no_despacho(self):
        def h(payload):
            return self.py("exige-modelo.py", stdin=payload if isinstance(payload, str) else json.dumps(payload))
        base = {"tool_name": "Agent", "tool_input": {"description": "Executor 02-TASK-UM",
                                                     "prompt": "SEGREDO-PROMPT-123"}}
        rc, out, err = h(base)
        self.assertEqual(rc, 2)
        self.assertIn("02-TASK-UM", err)
        self.assertNotIn("SEGREDO-PROMPT-123", out + err)
        for model, esperado in (("sonnet", 0), ("inherit", 2), ("  ", 2)):
            p = json.loads(json.dumps(base))
            p["tool_input"]["model"] = model
            self.assertEqual(h(p)[0], esperado, model)
        self.assertEqual(h({"tool_name": "Agent", "tool_input": {"description": "explorar o repo"}})[0], 0)
        self.assertEqual(h({"tool_name": "Read", "tool_input": {"file_path": "x"}})[0], 0)
        self.assertEqual(h("{não é json")[0], 0)

    def test_snap_detecta_escrita_de_quem_so_le(self):
        s = os.path.join(self.tmp, "snap.txt")
        self.ok(self.tl("snap", "--out", s))
        self.assertEqual(self.tl("snap", "--comparar", s)[0], 0)
        escrever(self.sk, "a/novo.py", "x = 1\n")
        rc, out, _ = self.tl("snap", "--comparar", s, "--json")
        self.assertEqual(rc, 1)
        self.assertIn("a/novo.py", jload(out)["mudou"])


# ================================================================================================ custo
class Custo(Copia):
    TRANSCRIPT = "\n".join([
        json.dumps({"type": "user", "message": {"content": "SEGREDO-ABC"}}),
        json.dumps({"type": "assistant", "message": {"model": "claude-sonnet-x", "usage": {
            "input_tokens": 10, "cache_creation_input_tokens": 5, "cache_read_input_tokens": 100, "output_tokens": 7},
            "content": [{"type": "text", "text": "SEGREDO-ABC"}]}}),
        json.dumps({"type": "assistant", "message": {"model": "claude-sonnet-x", "usage": {
            "input_tokens": 20, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 200,
            "output_tokens": 9}}}),
        "isto não é json", ""])

    def setUp(self):
        Copia.setUp(self)
        self.proj = os.path.join(self.tmp, "projects")
        escrever(self.proj, "x/subagents/agent-abc123.jsonl", self.TRANSCRIPT)

    def test_medir_so_le_usage(self):
        rc, out, err = self.py("custo.py", "medir", "abc123", "--projects-dir", self.proj, "--json")
        self.assertEqual(rc, 0, err)
        j = jload(out)
        self.assertEqual((j["turnos"], j["contexto_primeiro_turno"], j["contexto_somado"], j["saida"]),
                         (2, 115, 335, 16))
        self.assertEqual(j["modelos"], ["claude-sonnet-x"])
        self.assertEqual(j["linhas_invalidas"], 1)
        self.assertNotIn("SEGREDO-ABC", out + err)
        escrever(self.proj, "y/agent-abc123.jsonl", self.TRANSCRIPT)
        self.assertNotEqual(self.py("custo.py", "medir", "abc123", "--projects-dir", self.proj)[0], 0)

    def test_registrar_e_resumo_por_modelo(self):
        self.ok(self.py("custo.py", "registrar", "abc123", "--frente", F, "--task", "02-TASK-UM", "--papel",
                        "executor", "--modelo", "sonnet", "--projects-dir", self.proj))
        self.ok(self.py("custo.py", "registrar", "zzz", "--frente", F, "--task", "03-TASK-DOIS", "--papel",
                        "executor", "--modelo", "sonnet", "--projects-dir", self.proj))
        linhas = [jload(x) for x in ler(os.path.join(self.st, "logs", "custo.jsonl")).splitlines() if x.strip()]
        self.assertEqual([x["status"] for x in linhas], ["OK", "NOT_RUN"])
        self.assertTrue(linhas[1]["motivo"])
        self.assertFalse(linhas[1].get("turnos"))
        self.assertNotIn("SEGREDO-ABC", ler(os.path.join(self.st, "logs", "custo.jsonl")))
        j = jload(self.ok(self.py("custo.py", "resumo", "--frente", F, "--json"))[1])
        self.assertEqual(j["por_modelo"]["sonnet"]["turnos"], 2)
        self.assertEqual(j["por_modelo"]["sonnet"]["contexto_somado"], 335)
        self.assertEqual(j["not_run"], 1)


# ================================================================================================ rh
class RH(Copia):
    def rh(self, *a):
        return self.py("rh.py", *a)

    def test_ficha_valida_e_conferida(self):
        args = ["ficha", "--persona", "diagnosticador", "--task", "02-TASK-UM", "--motivo",
                "verificação falhou em 2 ciclos com AssertionError"]
        j = jload(self.ok(self.rh(*(args + ["--json"])))[1])
        self.assertEqual(j["decisao"], "CONTRATAR")
        self.assertEqual(j["nome"], "rh-diagnosticador-02-TASK-UM-1")
        self.assertTrue(j["no_elenco"])
        self.assertEqual(j["modelo"], "sonnet")
        self.assertEqual(j["permissao"], "SOMENTE LEITURA")
        txt = self.ok(self.rh(*args))[1]
        for t in ("FICHA DE CONTRATAÇÃO", "Decisão: CONTRATAR", "Modelo: sonnet", "SOMENTE LEITURA",
                  "Critério de descarte", "Linha de log:", "LACUNAS", "CONFIRMADO", "SUSPEITA", "DADO"):
            self.assertIn(t, txt)
        m = re.search(r"--- PROMPT ---(.*?)--- FIM DO PROMPT ---", txt, re.S)
        self.assertIsNotNone(m)
        self.assertEqual(PLACEHOLDER.findall(m.group(1)), [])
        p = escrever(self.tmp, "ficha.md", txt)
        self.ok(self.rh("conferir", p))
        escrever(self.tmp, "f2.md", txt.replace("--- FIM DO PROMPT ---", "Leia {caminho do arquivo}\n--- FIM DO PROMPT ---"))
        self.assertEqual(self.rh("conferir", os.path.join(self.tmp, "f2.md"))[0], 2)
        escrever(self.tmp, "f3.md", txt.replace("--- FIM DO PROMPT ---",
                                                "Authorization: Bearer abcdefghijklmnopqrstuvwxyz0123\n--- FIM DO PROMPT ---"))
        self.assertEqual(self.rh("conferir", os.path.join(self.tmp, "f3.md"))[0], 2)

    def test_tipo_inexistente_recusado_ou_substituido_declarado(self):
        base = ["ficha", "--persona", "especialista-seguranca", "--task", "02-TASK-UM", "--motivo", "segunda lente",
                "--tipo", "security-architect"]
        rc, out, err = self.rh(*base)
        self.assertEqual(rc, 2)
        self.assertIn("inexistente", (out + err).lower())
        txt = self.ok(self.rh(*(base + ["--aceitar-substituicao"])))[1]
        self.assertRegex(txt, r"(?m)^Tipo:.*substitui.*security-architect")
        self.assertEqual(self.rh("ficha", "--persona", "astronauta", "--task", "02-TASK-UM", "--motivo", "x")[0], 2)

    def test_fazer_direto_no_limite_e_executor_com_paths(self):
        txt = self.ok(self.rh("ficha", "--persona", "cetico", "--task", "02-TASK-UM", "--motivo", "x",
                              "--contratados", "3"))[1]
        self.assertIn("FAZER DIRETO", txt)
        self.assertNotIn("--- PROMPT ---", txt)
        self.assertEqual(self.rh("ficha", "--persona", "executor", "--task", "02-TASK-UM", "--motivo", "x")[0], 2)
        j = jload(self.ok(self.rh("ficha", "--persona", "executor", "--task", "02-TASK-UM", "--motivo", "x",
                                  "--arquivos", "a/um.py", "--json"))[1])
        self.assertEqual(j["permissao"], "ESCRITA em a/um.py")
        self.assertIn("general-purpose", jload(self.ok(self.rh("elenco", "--json"))[1])["tipos"])


# ================================================================================================ e2e-loop
class E2E(unittest.TestCase):
    def e(self, *a):
        return rodar([PY, os.path.join(PROJ, ".claude", "tools", "e2e.py")] + list(a),
                     env_limpo(tempfile.gettempdir(), PROJ), PROJ)

    def todas(self):
        nomes = ["harness-dev"] + sorted(x for x in os.listdir(os.path.join(PROJ, "scripts"))
                                         if os.path.isdir(os.path.join(PROJ, "scripts", x, "tests")))
        if os.path.isdir(os.path.join(PROJ, "evals", "tests")):
            nomes.append("evals")
        return nomes

    def test_regua_lista_suites_e_pythons(self):
        rc, out, err = self.e("regua", "--json")
        self.assertEqual(rc, 0, err)
        j = jload(out)
        self.assertEqual(sorted(s["nome"] for s in j["suites"]), sorted(self.todas()))
        dirs = {s["nome"]: s["dir"] for s in j["suites"]}
        self.assertEqual(dirs["harness-dev"], ".claude/tools/tests")
        self.assertIn("python3", j["pythons"])
        self.assertIn("/usr/bin/python3", j["pythons"])
        self.assertLessEqual(len(self.e("regua", "--brief")[1].splitlines()), 40)

    def sel(self, *a):
        rc, out, err = self.e(*(["selecionar"] + list(a) + ["--json"]))
        self.assertEqual(rc, 0, err)
        return jload(out)

    def test_seleciona_pelo_arquivo_tocado(self):
        j = self.sel("--arquivos", ".claude/tools/frente.py", ".claude/skills/rh/SKILL.md")
        self.assertEqual((j["suites"], j["completa"]), (["harness-dev"], False))
        j = self.sel("--arquivos", "scripts/emit/render.py")
        self.assertIn("emit", j["suites"])
        self.assertNotIn("scan", j["suites"])
        self.assertFalse(j["completa"])

    def test_desconhecido_ou_fechamento_roda_tudo(self):
        j = self.sel("--arquivos", "qualquer/coisa.txt")
        self.assertTrue(j["completa"])
        self.assertEqual(sorted(j["suites"]), sorted(self.todas()))
        j = self.sel("--arquivos", ".claude/tools/frente.py", "--fechamento")
        self.assertTrue(j["completa"])
        self.assertEqual(sorted(j["suites"]), sorted(self.todas()))

    def test_rodar_dry_run(self):
        rc, out, err = self.e("rodar", "--suites", "harness-dev", "--dry-run")
        self.assertEqual(rc, 0, err)
        for t in ("python3", "/usr/bin/python3", ".claude/tools", "unittest"):
            self.assertIn(t, out)


# ================================================================================================ fechar-frente
class FecharFrente(Copia):
    """Gate de aceite + completude cruzada, archive único, LAST_DELIVERY, limpeza, IDLE, commit só da frente."""
    fake = True
    OK = "intake.3,integracao.3,oracle"

    def setUp(self):
        Copia.setUp(self)
        self.abrir(fake=False)
        escrever(self.sk, "campanhas/%s/oraculo/test_demo.py" % F, "import unittest\n")
        for tid in sorted(tasks_ok()):
            self.handoff(tid)
            self.ok(self.marcar(tid), tid)
        p = os.path.join(self.fd, "FRENTE.md")
        escrever(self.fd, "FRENTE.md", ler(p).replace("### Aceite QA — PENDENTE", "### Aceite QA — ACCEPT")
                 .replace("### Aceite Review — PENDENTE", "### Aceite Review — APPROVED"))
        novos = {"a/um.py": "def um():\n    return 2\n", "a/dois.py": "def dois():\n    return 4\n"}
        g = os.path.join(self.sk, "local", "portao-" + F)
        for rel, txt in novos.items():
            escrever(self.sk, rel, txt)
            escrever(g, "codebase-specialists/" + rel, txt)
        escrever(g, "arquivos.txt", "a/um.py\na/dois.py\n")
        escrever(g, "portao.out", "portão demo-x\nORACULO test_demo: Ran 2 tests OK\nRESULTADO: VERDE\nFIM\n")
        self.notas = escrever(self.tmp, "notas.md", "## Resumo\num e dois dobram.\n\n## Decisões técnicas\n- nenhuma\n"
                                                    "\n## Aprendizados\n- o fluxo inteiro roda em cópia.\n")

    def fc(self, *a, **kw):
        kw.setdefault("ok", self.OK)
        return self.fr(*(["fechar"] + list(a)), **kw)

    def arch(self):
        return os.path.join(self.st, "archive", F)

    def test_gate_passa_e_reprova_cada_falta_sem_escrever(self):
        j = jload(self.ok(self.fc("check", F, "--json"))[1])
        self.assertTrue(j["ok"])

        def reprova(pedaco, ok=self.OK):
            antes = arvore(self.sk)
            rc, out, err = self.fc("check", F, "--json", ok=ok)
            self.assertEqual(rc, 1, pedaco + out + err)
            cods = [x["codigo"] for x in jload(out)["falhas"]]
            self.assertTrue(any(pedaco in c for c in cods), "%s não está em %s" % (pedaco, cods))
            self.assertEqual(arvore(self.sk), antes, "o gate não escreve")

        def mexe(rel, de, para):
            p = os.path.join(self.sk, rel)
            orig = ler(p)
            escrever(self.sk, rel, orig.replace(de, para))
            return lambda: escrever(self.sk, rel, orig)

        fd = ".claude/state/frentes/%s/" % F
        tarefa = os.path.join(self.fd, "TASKS", "03-TASK-DOIS.md")
        guarda = ler(tarefa)
        os.remove(tarefa)
        reprova("completude")
        escrever(self.fd, "TASKS/03-TASK-DOIS.md", guarda)
        volta = mexe(fd + "TASKS/03-TASK-DOIS.md", "status: DONE", "status: IN_PROGRESS")
        reprova("task_aberta")
        volta()
        volta = mexe(fd + "FRENTE.md", "Aceite QA — ACCEPT", "Aceite QA — PENDENTE")
        reprova("aceite")
        volta()
        volta = mexe(fd + "HISTORICO.md", "## [PASS] 03-TASK-DOIS", "## [NOTA] 03-TASK-DOIS")
        reprova("gate")
        volta()
        volta = mexe("local/portao-%s/portao.out" % F, "RESULTADO: VERDE", "RESULTADO: VERMELHO")
        reprova("portao")
        volta()
        escrever(self.sk, "a/um.py", "def um():\n    return 3\n")
        reprova("conferir")
        escrever(self.sk, "a/um.py", "def um():\n    return 2\n")
        reprova("campanha", ok="integracao.3,oracle")
        self.ok(self.fc("check", F))

    def test_limpar_sem_archive_recusa(self):
        rc, out, err = self.fc("limpar", F)
        self.assertEqual(rc, 1, out + err)
        self.assertEqual(len(os.listdir(os.path.join(self.fd, "TASKS"))), 5)
        self.assertTrue(os.path.isfile(os.path.join(self.fd, "CHECKLIST.md")))
        self.assertEqual(self.fc("idle", F)[0], 1)

    def test_archive_unico_completo_e_idempotente(self):
        self.assertNotEqual(self.fc("archive", F)[0], 0, "sem --notas")
        self.ok(self.fc("archive", F, "--notas", self.notas))
        self.assertEqual(os.listdir(self.arch()), [F + ".md"])
        t = ler(os.path.join(self.arch(), F + ".md"))
        for s in ("### CA-01", "### CA-02", "Aceite QA — ACCEPT", "Aceite Review — APPROVED", "## Arquivos da frente",
                  "- `a/um.py`", "- `a/dois.py`", "## Como a frente nasceu", 'Aprovação: "ok"', "## Campanha",
                  "## Tasks", "## Aprendizados", "o fluxo inteiro roda em cópia", "## Oráculo",
                  "campanhas/demo-x/oraculo/test_demo.py"):
            self.assertIn(s, t)
        arqs = t.split("## Arquivos da frente")[1].split("\n## ")[0]
        self.assertNotIn("TASKS/", arqs)
        self.assertNotIn("oraculo", arqs)
        self.assertEqual(t.rstrip().splitlines()[-1], "<!-- fechar-frente:archive-completo -->")
        antes = arvore(self.sk)
        self.ok(self.fc("archive", F, "--notas", self.notas))
        self.assertEqual(arvore(self.sk), antes)

    def test_archive_recusa_com_gate_reprovado(self):
        p = os.path.join(self.fd, "FRENTE.md")
        escrever(self.fd, "FRENTE.md", ler(p).replace("Aceite Review — APPROVED", "Aceite Review — PENDENTE"))
        self.assertEqual(self.fc("archive", F, "--notas", self.notas)[0], 1)
        self.assertFalse(os.path.exists(self.arch()))

    def test_fechamento_completo_ate_idle_e_retomavel(self):
        etapas = lambda: {e["id"]: e["feita"] for e in jload(self.ok(self.fc("plano", F, "--json"))[1])["etapas"]}
        self.assertFalse(any(etapas().values()))
        self.ok(self.fc("archive", F, "--notas", self.notas))
        self.assertTrue(etapas()["archive"])
        self.assertFalse(etapas()["limpar"])
        self.ok(self.fc("entrega", F))
        corpo = [x for x in ler(os.path.join(self.st, "LAST_DELIVERY.md")).splitlines()[1:] if x.strip()]
        self.assertEqual(corpo[0], "**Frente-ID:** %s" % F)
        self.ok(self.fc("limpar", F))
        self.assertFalse(os.path.exists(self.fd))
        self.assertFalse(os.path.exists(os.path.join(self.st, "logs", F)))
        self.assertTrue(os.path.isfile(os.path.join(self.arch(), F + ".md")))
        self.ok(self.fc("idle", F))
        fj = self.frentes_json()
        self.assertEqual(fj["ativas"], [])
        self.assertEqual(fj["entregues"][-1]["id"], F)
        wf = ler(os.path.join(self.st, "WORKFLOW.md"))
        self.assertIn("**Estado:** IDLE", wf)
        self.assertIn("Nota humana do founder", wf)
        self.assertTrue(all(etapas().values()))
        antes = arvore(self.sk)
        for passo in (("archive", F, "--notas", self.notas), ("entrega", F), ("limpar", F), ("idle", F)):
            self.ok(self.fc(*passo), str(passo))
        self.assertEqual(arvore(self.sk), antes, "reexecutar não muda nada")

    def test_idle_recusa_archive_com_intruso(self):
        self.ok(self.fc("archive", F, "--notas", self.notas))
        self.ok(self.fc("entrega", F))
        self.ok(self.fc("limpar", F))
        escrever(self.arch(), "FRENTE.md", "snapshot solto")
        rc, out, err = self.fc("idle", F)
        self.assertEqual(rc, 1)
        self.assertIn("FRENTE.md", out + err)
        self.assertEqual(self.ids_ativas(), [F])

    def fechar_ate_idle(self):
        for passo in (("archive", F, "--notas", self.notas), ("entrega", F), ("limpar", F), ("idle", F)):
            self.ok(self.fc(*passo), str(passo))

    def test_commit_so_da_frente(self):
        self.fechar_ate_idle()
        escrever(self.sk, "x/terceiro.txt", "de outra sessão\n")
        git(self.sk, "add", "x/terceiro.txt")
        escrever(self.st, "DECISIONS.md", DECISIONS_FIX + "| D-99 | hoje | de outra sessão |\n")
        msg = escrever(self.tmp, "msg.txt", "harness: demo-x\n")
        h0 = self.head()
        j = jload(self.ok(self.fc("commit", F, "--mensagem", msg, "--dry-run", "--json"))[1])
        self.assertEqual(self.head(), h0)
        for p in ("a/um.py", "a/dois.py", "campanhas/demo-x/oraculo/test_demo.py", ".claude/state/LAST_DELIVERY.md"):
            self.assertTrue(any(x == p or p.startswith(x.rstrip("/") + "/") for x in j["paths"]), p)
        self.assertFalse(any("terceiro" in x or "DECISIONS" in x for x in j["paths"]))
        self.ok(self.fc("commit", F, "--mensagem", msg))
        self.assertEqual(git(self.sk, "rev-parse", "HEAD~1")[1], h0)
        nomes = git(self.sk, "show", "--name-only", "--format=", "HEAD")[1].splitlines()
        for p in ("a/um.py", "a/dois.py", "campanhas/demo-x/oraculo/test_demo.py",
                  ".claude/state/archive/demo-x/demo-x.md", ".claude/state/LAST_DELIVERY.md"):
            self.assertIn(p, nomes)
        self.assertNotIn("x/terceiro.txt", nomes)
        self.assertNotIn(".claude/state/DECISIONS.md", nomes)
        self.assertEqual(git(self.sk, "diff", "--cached", "--name-only")[1], "x/terceiro.txt")
        self.assertEqual(git(self.sk, "status", "--porcelain", "--", "a/um.py")[1], "")

    def test_commit_exige_preautorizacao(self):
        self.fechar_ate_idle()
        msg = escrever(self.tmp, "msg.txt", "harness: demo-x\n")
        h0 = self.head()
        self.assertEqual(self.fc("commit", F, "--mensagem", msg, ok="intake.3,oracle")[0], 1)
        self.assertEqual(self.head(), h0)
        log = ler(self.fake_log)
        self.assertNotRegex(log, r'"(gate|preauth|frase)"')


# ================================================================================================ guards
class Guards(Copia):
    """guard-estado.py: estado só por script, artefato só depois da aprovação certa, schema de task, archive único."""

    def g(self, rel, tool="Write", content=None, old=None, new=None, raw=None):
        if raw is None:
            ti = {"file_path": os.path.join(self.sk, rel)}
            if content is not None:
                ti["content"] = content
            if old is not None:
                ti.update({"old_string": old, "new_string": new})
            raw = json.dumps({"tool_name": tool, "tool_input": ti, "cwd": self.sk})
        rc, out, err = self.py("guard-estado.py", stdin=raw)
        self.assertEqual(rc, 0, err)
        if not out.strip():
            return "allow"
        return jload(out)["hookSpecificOutput"]["permissionDecision"]

    def test_arquivos_do_script_nunca_a_mao(self):
        self.ok(self.iniciar())
        fd = ".claude/state/frentes/%s/" % F
        for rel in (".claude/state/frentes.json", fd + "CHECKLIST.md", fd + "eventos.jsonl"):
            self.assertEqual(self.g(rel, "Edit", old="a", new="b"), "deny", rel)
        self.assertEqual(self.g(".claude/state/RESUME.md", "Edit", old="a", new="b"), "allow")
        self.assertEqual(self.g("a/um.py", "Write", content="x"), "allow")
        self.assertEqual(self.g(None, raw="{nada"), "deny")

    def test_artefato_so_depois_da_aprovacao(self):
        self.ok(self.iniciar())
        fd = ".claude/state/frentes/%s/" % F
        self.assertEqual(self.g(fd + "FRENTE.md", content=FRENTE_OK), "deny")
        self.etapa_ok("E1")
        self.etapa_ok("E2")
        self.assertEqual(self.g(fd + "FRENTE.md", content=FRENTE_OK), "allow")
        tid, txt = sorted(tasks_ok().items())[1]
        self.assertEqual(self.g(fd + "TASKS/%s.md" % tid, content=txt), "deny")
        self.etapa_ok("E3")
        self.assertEqual(self.g(fd + "TASKS/%s.md" % tid, content=txt), "allow")
        self.assertEqual(self.g(fd + "TASKS/2-task-um.md", content=txt), "deny")

    def test_task_done_sem_gate_ou_handoff(self):
        self.fluxo(ate="E3")
        fd = ".claude/state/frentes/%s/" % F
        tid, txt = sorted(tasks_ok().items())[1]
        done = txt.replace("status: PENDENTE", "status: DONE")
        self.assertEqual(self.g(fd + "TASKS/%s.md" % tid, content=done), "deny")
        bom = done.replace("gate: PENDENTE", "gate: PASS").rstrip() + "\n- entrega: feita com evidência.\n"
        self.assertEqual(self.g(fd + "TASKS/%s.md" % tid, content=bom), "allow")
        escrever(self.fd, "TASKS/%s.md" % tid, txt)
        self.assertEqual(self.g(fd + "TASKS/%s.md" % tid, "Edit", old="status: PENDENTE", new="status: DONE"), "deny")

    def test_archive_so_o_documento_unico(self):
        self.assertEqual(self.g(".claude/state/archive/%s/extra.md" % F, content="x"), "deny")
        self.assertEqual(self.g(".claude/state/archive/%s/%s.md" % (F, F), content="x"), "allow")


# ================================================================================================ sessão
class Sessao(Copia):
    def s(self, *a, **kw):
        return self.py("sessao.py", *a, **kw)

    def frescor(self):
        rc, out, err = self.s("frescor", "--json")
        self.assertEqual(rc, 0, err)
        return jload(out)

    def test_carimbo_e_frescor(self):
        self.assertEqual(self.frescor()["veredito"], "sem-carimbo")
        self.ok(self.s("carimbo", "--write"))
        r = ler(os.path.join(self.st, "RESUME.md"))
        m = re.search(r"<!-- resume-stamp\n(.*?)-->", r, re.S)
        self.assertIsNotNone(m)
        for campo in ("FRENTES:", "BRANCH:", "HEAD:", "PRODUTO:", "ESTADO:", "GATE:"):
            self.assertIn(campo, m.group(1))
        self.assertIn("## Onde paramos", r)
        self.assertEqual(self.frescor()["veredito"], "bate")
        escrever(self.sk, "SKILL.md", "# produto mudou\n")
        j = self.frescor()
        self.assertEqual(j["veredito"], "produto-mudou")
        self.assertIn("PRODUTO", j["divergentes"])
        self.ok(self.iniciar())
        j = self.frescor()
        self.assertEqual(j["veredito"], "cache-miss")
        self.assertIn("ESTADO", j["divergentes"])
        self.assertLessEqual(len(self.s("frescor", "--brief")[1].splitlines()), 40)

    def test_head_por_regra(self):
        self.ok(self.s("carimbo", "--write"))
        escrever(self.st, "BACKLOG.md", BACKLOG_FIX + "| B-02 | P2 | outro |\n")
        git(self.sk, "add", ".claude/state/BACKLOG.md")
        git(self.sk, "commit", "--no-verify", "-qm", "so estado")
        self.assertEqual(self.frescor()["veredito"], "bate", "commit só de estado não invalida")
        escrever(self.sk, "a/um.py", "def um():\n    return 9\n")
        git(self.sk, "add", "a/um.py")
        git(self.sk, "commit", "--no-verify", "-qm", "trabalho")
        j = self.frescor()
        self.assertEqual(j["veredito"], "cache-miss")
        self.assertIn("HEAD", j["divergentes"])

    def test_salvar(self):
        antes = arvore(self.sk)
        self.ok(self.s("salvar", "--resumo", "teste de salvar", "--dry-run"))
        self.assertEqual(arvore(self.sk), antes)
        self.ok(self.s("salvar", "--resumo", "teste de salvar"))
        ult = jload(ler(os.path.join(self.st, "logs", "sessoes.jsonl")).strip().splitlines()[-1])
        self.assertEqual(ult["evento"], "sessao-salva")
        self.assertEqual(ult["resumo"], "teste de salvar")
        self.assertEqual(ult["head"], git(self.sk, "rev-parse", "--short", "HEAD")[1])
        self.assertRegex(ult["data"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d")
        self.assertEqual(self.frescor()["veredito"], "bate", "salvar seguido de carregar tem de bater")

    def test_salvar_commit_so_estado_e_privacidade(self):
        escrever(self.sk, "x/t.txt", "terceiro\n")
        git(self.sk, "add", "x/t.txt")
        escrever(self.sk, "a/um.py", "def um():\n    return 5\n")
        msg = escrever(self.tmp, "m.txt", "state: sessão\n")
        h0 = self.head()
        self.ok(self.s("salvar", "--resumo", "com commit", "--commit", "--mensagem", msg))
        self.assertEqual(git(self.sk, "rev-parse", "HEAD~1")[1], h0)
        nomes = git(self.sk, "show", "--name-only", "--format=", "HEAD")[1].splitlines()
        self.assertTrue(nomes and all(n.startswith(".claude/state/") for n in nomes), nomes)
        self.assertEqual(git(self.sk, "diff", "--cached", "--name-only")[1], "x/t.txt")
        self.assertEqual(self.frescor()["veredito"], "bate")
        escrever(self.st, "RESUME.md", ler(os.path.join(self.st, "RESUME.md")) + "\nveja " + USUARIO_PRIVADO + "/x\n")
        h1 = self.head()
        self.assertNotEqual(self.s("salvar", "--resumo", "vaza", "--commit", "--mensagem", msg)[0], 0)
        self.assertEqual(self.head(), h1)

    def test_briefing(self):
        self.abrir()
        rc, out, err = self.s("briefing", "--brief")
        self.assertEqual(rc, 0, err)
        linhas = out.splitlines()
        self.assertLessEqual(len(linhas), 40)
        self.assertIn(F, out)
        self.assertIn("0/5", out)
        self.assertIn("Retomo daqui?", out)
        self.assertTrue(any("01-TASK-ORACULO" in x and "← PRÓXIMA" in x for x in linhas), out)
        self.assertFalse(any("[x]" in x and "TASK" in x for x in linhas))
        self.assertTrue(any("02-TASK-UM" in x and "oráculo congelado" in x for x in linhas), "depends com o porquê")


# ================================================================================================ auto-correcao
class AutoCorrecao(Copia):
    def cp(self, *a, **kw):
        return self.py("campanha.py", *a, **kw)

    def setUp(self):
        Copia.setUp(self)
        self.campanha(F, "a/um.py")

    def test_etapa_pelo_motor_embutido(self):
        j = jload(self.ok(self.cp("etapa", F, "--json"))[1])
        self.assertEqual(j["etapa"], "intake")
        self.assertEqual(os.path.realpath(j["motor"]), os.path.realpath(self.tool("ac/ac.py")))
        ctx = {p["id"]: p["ctx"] for p in j["pendentes"]}
        self.assertEqual(ctx.get("intake.3"), "user")
        self.assertTrue(j["proximo"])
        self.assertLessEqual(len(self.cp("etapa", F, "--brief")[1].splitlines()), 40)

    def test_mudanca_oficial_passa_todos_os_arquivos(self):
        o = "campanhas/%s/oraculo/" % F
        escrever(self.sk, o + "o1.py", "a = 1\n")
        escrever(self.sk, o + "o2.py", "b = 2\n")
        self.ok(self.ac("--work", "campanhas/" + F, "oracle", "freeze", "--file", o + "o1.py", "--file", o + "o2.py"))
        rc, out, err = self.cp("mudanca-oficial", F, "--porque", "teste errado", "--evidencia", "conferido", "--dry-run")
        self.assertNotEqual(rc, 0)
        self.assertIn("mudanca-oficial", out + err)
        escrever(self.sk, o + "mudanca-oficial/01-ajuste.patch", "--- a\n+++ b\n")
        escrever(self.sk, o + "mudanca-oficial/PORQUE.md", "# porque\nconferido à mão\n")
        rc, out, err = self.cp("mudanca-oficial", F, "--porque", "teste errado", "--evidencia", "conferido", "--dry-run")
        self.assertEqual(rc, 0, out + err)
        for t in ("oracle change", "--why", "--evidence"):
            self.assertIn(t, out)
        self.assertRegex(out, r"--file \S*o1\.py")
        self.assertRegex(out, r"--file \S*o2\.py")

    def test_fechar_segue_o_ciclo_e_deixa_o_humano_para_o_founder(self):
        r = escrever(self.tmp, "rel.md", "# relatório\n")
        rc, out, err = self.cp("fechar", F, "--relatorio", r, "--config", "sistema", "--decisao", "GO", "--dry-run")
        self.assertEqual(rc, 0, out + err)
        ordem = ["front report", "done correcao", "done integracao", "run record", "done remedicao", "frase conferir",
                 "done decisao"]
        pos = [out.find(x) for x in ordem]
        self.assertTrue(all(p >= 0 for p in pos), list(zip(ordem, pos)))
        self.assertEqual(pos, sorted(pos))
        linha = [x for x in out.splitlines() if "frase conferir" in x][0]
        self.assertIn("founder", linha.lower())
        self.assertNotRegex(out, r"(?m)ac\.py .*--work \S+ (gate|preauth) ")
        _, ajuda, _ = self.cp("--help")
        subs = re.search(r"\{([a-z,-]+)\}", ajuda)
        self.assertIsNotNone(subs, ajuda)
        self.assertEqual(sorted(subs.group(1).split(",")), ["etapa", "fechar", "mudanca-oficial"])


# ================================================================================================ ligações
class Ligacoes(Copia):
    """Textos e ligações das ferramentas que já existiam (carimbo, guard-entrega, script de aprovação, portão)."""

    def test_carimbo_brief_aponta_carregar_sessao(self):
        rc, out, err = self.sh("carimbo.sh", "--brief")
        self.assertEqual(rc, 0, err)
        self.assertIn("carregar-sessao", out)
        self.assertLessEqual(len(out.splitlines()), 40)

    def test_guard_entrega_e_script_de_aprovacao_citam_criar_frente(self):
        raw = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": os.path.join(self.sk, "SKILL.md")}})
        rc, out, _ = self.py("guard-entrega.py", stdin=raw)
        self.assertIn("criar-frente", out)
        rc, out, err = self.sh("script-aprovacao.sh", "nada")
        self.assertNotEqual(rc, 0)
        self.assertIn("criar-frente", out + err)

    def test_portao_roda_a_suite_do_harness(self):
        rc, out, err = self.sh("portao.sh", F, "--src", self.sk, "--dry-run", "--", "a/um.py")
        self.assertEqual(rc, 0, out + err)
        self.assertIn("harness-dev", out)


if __name__ == "__main__":
    unittest.main()
