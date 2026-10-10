"""ORÁCULO campanha-iter21 — memória dos agentes (B-22 caderno, B-23 brief relevante, B-24 rastro da pesquisa).

Mapa requisito → teste e critérios em ESPEC.md (mesma pasta). Resumo:

  M1  `cs-mem correct|add` (lição de agente) gera `.claude/agent-memory/<agente>/MEMORY.md` com um BLOCO GERADO no
      topo, entre um par de marcadores HTML que contêm "cs-mem" (documentados em docs/ ou references/), com as seções
      Correções recebidas · Armadilhas do território · Quando pesquisar no cs-mem.
  M2  o bloco é regenerado a cada add/correct/archive(decaimento) DAQUELE agente; caderno de outro agente intacto;
      a ÁREA LIVRE (abaixo do bloco, ou notas que já existiam antes do 1º bloco) é preservada; regenerar sem mudança
      dá os mesmos bytes; caminho único cs-mem → caderno (o bloco deriva só das lições ativas; nota no caderno não é
      lição registrada).
  M3  o bloco cabe no que a plataforma injeta (≤ 200 linhas e ≤ 25 KB), mesmo com o teto de lições e 30 termos.
  M4  guard: o subagente escreve no caderno DELE fora do bloco (Edit/Write); editar o bloco ⇒ recusado ou restaurado;
      outro agente não escreve no caderno alheio; o orquestrador não escreve o bloco; o verify não conta o caderno
      do agente como escrita fora de allowed_paths.
  M5  pre-commit: commit do caderno (bloco = o que o cs-mem gera + área livre) passa SEM --no-verify; bloco
      adulterado ou removido ⇒ barrado.
  M6  emit / harness install / upgrade --apply não apagam nem mudam o caderno; alvo 0.10.1 REAL com lição já
      registrada: upgrade --apply gera o caderno e o commit passa.
  M7  brief (B-23): termos vêm de busca relevante (título + goal + allowed_paths), não do dump alfabético;
      "referências" e "fora de escopo" nunca saem com rótulo vazio; o brief já traz o resultado da busca da memória
      (o harness busca, não depende do agente).
  M8  Cursor/Copilot/Codex: o brief continua sendo o canal da lição (sem exigir MEMORY.md); o cartão claude-code
      continua com `memory: project`.
  M9  rastro (B-24): toda `cs-mem search` grava (agente, consulta, nº de hits) num log JSONL append-only.
  M10 submit: 'consultei: "TEMA" -> ID (efeito)' ou "consultei: nada — <motivo>" conferido contra o rastro (consulta
      citada que não foi feita, ou ID que não sai dessa busca ⇒ submit ou verify recusa); submit SEM a linha é aceito
      mas fica visível ao gate como "consultei: não declarado"; o brief de implementação ensina o formato.
  M11 /correct classifica quem errou (`cs-mem correct --fault brief|agent`): erro do brief ⇒ lição do lead
      (source brief), sem tocar o caderno do agente; erro do agente ⇒ lição e caderno do agente.
  M12 refinamento: `cs-mem correct --supersedes <id>` e `cs-mem retract <id> --reason` registram evento (JSONL) e
      a lição antiga nunca mais é injetada (brief, inject, bloco do caderno, busca como ativa); a nova fica ativa;
      /correct mostra errado/certo/porquê e pede confirmação ANTES de gravar (prévia, se houver, não grava).
  M13 sob orçamento estourado (glossário de 400 termos) a lição relevante e o resultado da busca continuam no brief e
      o glossário não é despejado; o `cs-mem check` como o cartão/brief o escrevem devolve a lição da delegação
      (diff em tests/**); no empate de count, a lição mais recente vem primeiro.

Comportamento observável: CLIs reais em subprocesso (`cs.py`, `.swarm/harness/{state,mem,guard}.py` instalados no
alvo), hook git real, repos git temporários, bytes dos arquivos. Nada de nome interno de função.
Skill sob teste: $CS_SKILL_DIR, senão a raiz deste projeto. Skill 0.10.1 (versão antiga do alvo): $CS_OLD_SKILL_DIR,
senão `git archive 97a1718` deste repositório. Temporários: $CS_ORACLE_TMP (padrão: o tempdir do Python).
Python 3.9+, unittest puro, só stdlib. Rodar (desta pasta): python3 -m unittest -v test_iter21
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unicodedata
import unittest

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.realpath(os.path.join(HERE, "..", "..", ".."))
SKILL = os.path.realpath(os.environ.get("CS_SKILL_DIR") or PROJECT)
SCRIPTS = os.path.join(SKILL, "scripts")
OLD_COMMIT = "97a1718"          # "0.10.1: pre-commit aceita o resultado do próprio upgrade (B-13, iter20)"
OLD_VERSION = "0.10.1"

GIT_ENV = {"GIT_AUTHOR_NAME": "Ana", "GIT_AUTHOR_EMAIL": "ana@x", "GIT_COMMITTER_NAME": "Ana",
           "GIT_COMMITTER_EMAIL": "ana@x"}
SD = ".swarm"
AGENT = "dev-cultivo"            # agente do território src/cultivo/**
OTHER = "dev-painel"             # outro agente (src/painel/**)
TERRITORY = "src/cultivo/**"
VERIFY = "python3 -m unittest tests.test_ok"
CREATED_RE = re.compile(r"^criad[oa] (\S+) em (\S+)\s*$", re.M)
MARK_RE = re.compile(r"<!--[^\n]*cs-mem[^\n]*-->")
FOOTGUN = "Dose de calcário lançada em quilos zerou a correção do solo"
SECTIONS = ("correcoes recebidas", "armadilhas do territorio", "quando pesquisar")
MAX_LINES, MAX_BYTES = 200, 25 * 1024

# --------------------------------------------------------------------------- domínio inventado (estufa/cultivo)
# 30 termos do território; o relevante para a task do M7 (vernalização) é o ÚLTIMO em ordem alfabética de id.
TERMS = [
    ("Alporquia", "propagação por enraizamento aéreo do ramo"),
    ("Bandeja", "suporte de células para semeadura"),
    ("Calagem", "quantidade de calcário em gramas por célula"),
    ("Canteiro", "faixa de solo preparada para plantio"),
    ("Desbaste", "remoção de plântulas excedentes"),
    ("Enxertia", "união de garfo e porta-enxerto"),
    ("Estiolamento", "crescimento alongado por falta de luz"),
    ("Fertirrigacao", "adubo dissolvido na água de rega"),
    ("Fotoperiodo", "horas de luz por dia"),
    ("Gotejador", "emissor de água gota a gota"),
    ("Hidroponia", "cultivo sem solo em solução nutritiva"),
    ("Inoculante", "bactéria aplicada ao grão antes do plantio"),
    ("Joeira", "peneira de separar grãos"),
    ("Lamina", "altura da água aplicada por evento"),
    ("Mergulhia", "propagação por ramo enterrado"),
    ("Mulching", "cobertura plástica do solo"),
    ("Nebulizador", "emissor de névoa para umidade"),
    ("Ombreira", "borda elevada do canteiro"),
    ("Perlita", "mineral expandido do substrato"),
    ("Pincamento", "corte do ápice da haste"),
    ("Quebravento", "barreira vegetal contra rajadas"),
    ("Repicagem", "transferência da plântula para recipiente maior"),
    ("Rustificacao", "exposição gradual ao ambiente externo"),
    ("Sombrite", "tela de sombreamento"),
    ("Tutoramento", "apoio vertical da haste"),
    ("Umidostato", "sensor que aciona umidificação"),
    ("Vermiculita", "mineral laminado de retenção hídrica"),
    ("Xaxim", "vaso de fibra"),
    ("Zeolita", "mineral de troca catiônica"),
    ("Vernalizacao", "exposição da semente ao frio para induzir floração"),
]
RELEVANT_TERM = "Vernalizacao"
BIG_N = 400                                  # M13: glossário na escala do alvo real (estoura o orçamento do brief)
RELEVANT_MARK = "induzir floração"          # só aparece no texto do termo relevante
M7_TITLE = "Ajustar a vernalização das sementes"
M7_GOAL = "a vernalização precisa durar seis semanas"
M7_PATH = "src/cultivo/vernalizacao.py"


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm(s):
    return " ".join(strip_accents(s or "").lower().split())


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", norm(s)).strip("-")


def domain_team():
    def card(desc, mission, **kw):
        c = {"description": desc, "mission": mission, "knows": [], "refuses": [], "done_when": "", "playbooks": [],
             "rules": [], "footguns": [], "anchors": []}
        c.update(kw)
        return c
    rw = ["Read", "Grep", "Glob", "Bash", "Edit", "Write"]
    return {
        "schema_version": 1,
        "repo": {"name": "estufa", "commit": "abc123", "root": "/x/estufa"},
        "platforms": ["claude-code", "cursor", "copilot", "codex"],
        "veredito_enum": ["PASS", "FAIL", "NEEDS_SPECIALIST"],
        "core": {"lines": [{"text": "Testes: `python3 -m unittest tests.test_ok` (exit 0)", "facts": ["ops.test"]}]},
        "agents": [
            {"name": AGENT, "kind": "dev", "territory": [TERRITORY], "reads": ["src/comum/**"], "tools": rw,
             "model": "inherit",
             "card": card("Use para mudar o cultivo: etapas, dependências entre etapas, calagem e vernalização em "
                          "src/cultivo.", "Mantém as regras de cultivo em src/cultivo corretas e cobertas por teste.",
                          knows=[{"text": "Massas em src/cultivo são int em gramas", "facts": ["conv.gramas"]}],
                          refuses=[{"text": "nunca usa float para massa", "why": "arredondamento quebrou a calagem",
                                    "facts": ["hist.fix.c00"]}],
                          done_when="`python3 -m unittest tests.test_ok` sai 0",
                          footguns=[{"text": FOOTGUN, "facts": ["hist.fix.c01"]}],
                          anchors=["src/cultivo/dependencias.py"]),
             "facts_used": ["conv.gramas"], "invariants": ["rule.gramas-int"]},
            {"name": OTHER, "kind": "dev", "territory": ["src/painel/**"], "reads": [], "tools": rw, "model": "sonnet",
             "card": card("Use para mudar telas do painel em src/painel.", "Mantém o painel fino.",
                          refuses=[{"text": "Calcular regra de cultivo na tela", "why": "regra mora em cultivo"}],
                          done_when="`python3 -m unittest tests.test_ok` sai 0",
                          footguns=[{"text": "Tela recalculando dose divergiu do cultivo", "facts": []}]),
             "facts_used": [], "invariants": []},
            {"name": "reviewer", "kind": "gate", "territory": [], "reads": ["src/**"],
             "tools": ["Read", "Grep", "Glob", "Bash"], "model": "inherit",
             "card": card("Use para revisar uma entrega antes do aceite; devolve PASS, FAIL ou NEEDS_SPECIALIST.",
                          "Revisa diffs contra invariantes e testes; não edita.",
                          refuses=[{"text": "editar código", "why": "gate não pode ser autor"}],
                          done_when="veredito gravado com evidência"),
             "facts_used": [], "invariants": ["rule.gramas-int"]},
            {"name": "qa", "kind": "ops", "territory": ["tests/**"], "reads": ["src/**"], "tools": rw,
             "model": "inherit",
             "card": card("Use para escrever ou consertar testes em tests/.", "Mantém tests/ como prova executável.",
                          refuses=[{"text": "Editar src/", "why": "QA não escreve produção"}],
                          done_when="`python3 -m unittest tests.test_ok` sai 0"),
             "facts_used": [], "invariants": []},
        ],
    }


PRODUCT = {
    "src/__init__.py": "",
    "src/cultivo/__init__.py": "",
    "src/cultivo/dependencias.py": (
        '"""Grafo de etapas do cultivo (lido pelo agendador)."""\n\n'
        "DEPENDE_DE = {\n"
        '    "triagem": ["lavagem"],\n'
        '    "etiquetagem": ["embalagem"],\n'
        "}\n"),
    "src/cultivo/bandejas.py": "CELULAS_PADRAO = 128\n",
    "src/cultivo/clima.py": "UMIDADE_ALVO = 70\n",
    "src/cultivo/vernalizacao.py": "SEMANAS = 4\n",
    "src/painel/__init__.py": "",
    "src/painel/app.py": "TITULO = 'painel'\n",
    "src/comum/__init__.py": "",
    "src/comum/util.py": "def nada():\n    return None\n",
    "tests/__init__.py": "",
    "tests/test_ok.py": "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n"
                        "        self.assertTrue(True)\n",
}


SYL = ("ba", "ce", "di", "fo", "gu", "la", "me", "ni", "po", "ru", "sa", "te", "vi", "xo", "za")


def big_terms(n):
    """n termos sintéticos do território, na escala do alvo real (centenas): nomes e definições sem nenhuma palavra
    das tasks dos testes."""
    out = []
    for i in range(n):
        a, b, c = SYL[i % 15], SYL[(i // 15) % 15], SYL[(i // 225) % 15]
        name = ("Q" + a + b + c + "x%03d" % i).capitalize()
        out.append((name, "registro interno %s do lote de mudas, campo %s%s" % (name.lower(), b, a)))
    return out


def domain_facts(extra_terms=0):
    terms, facts = [], []
    for i, (canon, definition) in enumerate(TERMS + big_terms(extra_terms)):
        where = "src/cultivo/%s.py" % slug(canon).replace("-", "_")
        terms.append({"canonical": canon, "term": canon.lower(), "definition": definition,
                      "where": "src/cultivo/bandejas.py:1", "count": 1 if canon == "Calagem" else 3 + (i % 5),
                      "kind": "business"})
        facts.append({"id": "gloss.%s" % slug(canon), "layer": "glossary",
                      "claim": "Termo '%s' (business): %s" % (canon, definition), "scope": [TERRITORY],
                      "evidence": [{"file": "src/cultivo/bandejas.py", "line": 1}],
                      "data": {"term": canon.lower(), "canonical": canon, "definition": definition}})
        del where
    files = [{"path": p, "category": "test" if p.startswith("tests/") else "product", "lang": "python", "loc": 3}
             for p in sorted(PRODUCT)]
    return {
        "rules.json5": {"facts": [{"id": "rule.gramas-int", "claim": "Massas em src/cultivo são int em gramas",
                                   "evidence": [{"file": "src/cultivo/bandejas.py", "line": 1}]}]},
        "glossary.json5": {"layer": "glossary", "terms": terms, "facts": facts},
        "business_rules.json5": {"rules": [
            {"rule": "Etapa só é agendada depois dos pré-requisitos", "where": "src/cultivo/dependencias.py:3",
             "source": "founder"}]},
        "inventory.json5": {"layer": "inventory", "files": files,
                            "languages": {"python": {"files": len(files), "loc": 40, "code": True}},
                            "ignored": {}, "facts": []},
        "graph.json5": {"layer": "graph", "nodes": [{"path": p, "pagerank": 0.1, "in": 1} for p in sorted(PRODUCT)],
                        "edges": [["src/painel/app.py", "src/cultivo/dependencias.py", 1]], "facts": []},
        "stack.json5": {"layer": "stack", "packages": [], "facts": []},
    }


def make_domain_repo(dest, extra_terms=0):
    """Repo do domínio inventado (estufa): produto + .swarm/team.json5 + .swarm/facts + mapas. Sem git."""
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest)
    for rel, txt in PRODUCT.items():
        write(dest, rel, txt)
    write(dest, SD + "/team.json5", "// fixture iter21\n" + json.dumps(domain_team(), ensure_ascii=False, indent=2))
    for name, data in domain_facts(extra_terms).items():
        write(dest, SD + "/facts/" + name, "// fixture iter21\n" + json.dumps(data, ensure_ascii=False))
    km = {"deps.json5": {"nodes": [{"id": AGENT}, {"id": OTHER}], "edges": [{"from": OTHER, "to": AGENT, "count": 1}]},
          "collision.json5": {"nodes": [{"id": AGENT}, {"id": OTHER}], "edges": [[OTHER, AGENT]]}}
    for name, data in km.items():
        write(dest, SD + "/knowledge/" + name, "// fixture iter21\n" + json.dumps(data, ensure_ascii=False))
    return dest


# ================================================================================================ infraestrutura
_TMP = {}


def base_tmp():
    if "base" not in _TMP:
        parent = os.environ.get("CS_ORACLE_TMP") or None
        if parent:
            os.makedirs(parent, exist_ok=True)
        _TMP["base"] = os.path.realpath(tempfile.mkdtemp(prefix="oraculo-iter21-", dir=parent))
    return _TMP["base"]


def tearDownModule():
    if "base" in _TMP and not os.environ.get("CS_ORACLE_KEEP"):
        shutil.rmtree(_TMP["base"], ignore_errors=True)


def _env(extra=None):
    e = dict(os.environ)
    for k in ("CLAUDE_PROJECT_DIR", "CS_ACTOR", "CS_GUARD_OFF", "CS_ROOT", "CS_SKILL_VERSION_FILE",
              "CS_MIGRATIONS_FILE", "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        e.pop(k, None)
    e.update(GIT_ENV)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    e["TMPDIR"] = base_tmp()
    e.update(extra or {})
    return e


def run(argv, cwd, stdin=None, extra=None, timeout=900):
    p = subprocess.run(argv, cwd=cwd, env=_env(extra), input=(stdin.encode("utf-8") if stdin is not None else None),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def git(root, *args):
    code, out, err = run(["git", "-C", root] + list(args), root)
    if code != 0:
        raise AssertionError("git %s: %s%s" % (" ".join(args), out, err))
    return out


def cs(skill, target, *args):
    return run([sys.executable, os.path.join(skill, "scripts", "cs.py"), "--target", target] + list(args), target)


def cs_ok(skill, target, *args):
    code, out, err = cs(skill, target, *args)
    if code != 0:
        raise AssertionError("cs.py %s → %d\n%s\n%s" % (" ".join(args), code, out[-3000:], err[-3000:]))
    return out


def tool(root, name, *args, actor=None):
    """CLI do motor INSTALADO no alvo (.swarm/harness/<name>.py)."""
    argv = [sys.executable, os.path.join(root, SD, "harness", name + ".py"), "--root", root]
    if actor:
        argv += ["--actor", actor]
    return run(argv + list(args), root)


def tool_ok(root, name, *args, actor=None):
    code, out, err = tool(root, name, *args, actor=actor)
    if code != 0:
        raise AssertionError("%s %s → %d\n%s%s" % (name, " ".join(args), code, out[-3000:], err[-3000:]))
    return out


def st_ok(root, *args, actor=None):
    return tool_ok(root, "state", *args, actor=actor)


def mem(root, *args):
    return tool(root, "mem", *args)


def mem_ok(root, *args):
    return tool_ok(root, "mem", *args)


def read_text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def write(root, rel, txt, mode="w"):
    full = os.path.join(root, rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, mode, encoding="utf-8") as fh:
        fh.write(txt)


def new_dir(name):
    _TMP["n"] = _TMP.get("n", 0) + 1
    return os.path.join(base_tmp(), "%s-%d" % (name, _TMP["n"]))


def copy_target(tpl, name):
    d = new_dir(name)
    shutil.copytree(tpl, d, symlinks=True)
    return d


def notebook_rel(agent):
    return ".claude/agent-memory/%s/MEMORY.md" % agent


def notebook_path(root, agent):
    return os.path.join(root, notebook_rel(agent))


def split_notebook(text):
    """(linha_ini, linha_fim, bloco, antes, depois) do 1º par de marcadores com 'cs-mem'; None se não houver par."""
    lines = text.split("\n")
    idx = [i for i, ln in enumerate(lines) if MARK_RE.search(ln)]
    if len(idx) < 2:
        return None
    a, b = idx[0], idx[1]
    return a, b, "\n".join(lines[a:b + 1]), "\n".join(lines[:a]), "\n".join(lines[b + 1:])


def block_of(root, agent):
    p = notebook_path(root, agent)
    if not os.path.isfile(p):
        raise AssertionError("caderno ausente: %s (o cs-mem deveria gerá-lo)" % notebook_rel(agent))
    sp = split_notebook(read_text(p))
    if sp is None:
        raise AssertionError("caderno %s sem par de marcadores <!-- ... cs-mem ... -->:\n%s"
                             % (notebook_rel(agent), read_text(p)[:1500]))
    return sp


def section_text(block, name):
    """Texto da seção cujo título (normalizado) contém `name`, até o próximo título markdown."""
    out, on = [], False
    for ln in block.split("\n"):
        if re.match(r"^\s*#{1,6}\s", ln):
            on = name in norm(ln)
            continue
        if on:
            out.append(ln)
    return "\n".join(out)


def correct(root, agent, right, wrong="fazer do jeito óbvio", why="convenção do dono", paths=(TERRITORY,)):
    args = ["correct", "--agent", agent, "--wrong", wrong, "--right", right, "--why", why]
    for p in paths:
        args += ["--paths", p]
    return mem_ok(root, *args)


def commit_all(root, msg, hooks=True):
    git(root, "add", "-A")
    if not git(root, "diff", "--cached", "--name-only").strip():
        return
    argv = ["git", "-C", root] + (["-c", "core.hooksPath=" + os.path.join(root, ".git", "hooks")] if hooks else []) + \
        ["commit", "-q", "-m", msg]
    code, out, err = run(argv, root)
    if code != 0:
        raise AssertionError("fixture: commit %r barrado:\n%s%s" % (msg, out[-3000:], err[-3000:]))


def try_commit(root, msg):
    head = git(root, "rev-parse", "HEAD").strip()
    code, out, err = run(["git", "-C", root, "-c", "core.hooksPath=" + os.path.join(root, ".git", "hooks"),
                          "commit", "-q", "-m", msg], root)
    return code, out + err, git(root, "rev-parse", "HEAD").strip() != head


def build_target(skill, dest, platforms="claude-code", hook=True, extra_terms=0):
    """Alvo do domínio: init + harness install + emit pela skill dada, cs-state init, tudo commitado; depois o
    pre-commit ligado (`harness install --git-hook`) e sondado (barra fonte fora de allowed_paths)."""
    make_domain_repo(dest, extra_terms)
    git(dest, "init", "-q")
    for k, v in (("gc.auto", "0"), ("gc.autoDetach", "false"), ("maintenance.auto", "false")):
        git(dest, "config", k, v)                # sem gc/maintenance em segundo plano (a cópia do alvo corre com ele)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "init")
    cs_ok(skill, dest, "init", "--platforms", platforms)
    cs_ok(skill, dest, "harness", "install", "--allow-outside")
    cs_ok(skill, dest, "emit", "--allow-outside")
    st_ok(dest, "init")
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "gerado pela skill")
    if hook:
        cs_ok(skill, dest, "harness", "install", "--allow-outside", "--git-hook")
        hk = os.path.join(dest, ".git", "hooks", "pre-commit")
        if not os.path.islink(hk) or not os.readlink(hk).endswith("cs-precommit"):
            raise AssertionError("pre-commit não ficou ligado ao cs-precommit")
        write(dest, "src/painel/app.py", "# sonda\n", mode="a")
        git(dest, "add", "--", "src/painel/app.py")
        code, out, _ = try_commit(dest, "sonda")
        if code == 0:
            raise AssertionError("o pre-commit da fixture não barrou src/painel/app.py: hook inativo")
        git(dest, "reset", "-q", "--", "src/painel/app.py")
        git(dest, "checkout", "--", "src/painel/app.py")
        if git(dest, "status", "--porcelain", "--untracked-files=all").strip():
            commit_all(dest, "pós-hook", hooks=False)
    return dest


def template(which):
    key = "tpl-" + which
    if key not in _TMP:
        if which == "new":
            _TMP[key] = build_target(SKILL, os.path.join(base_tmp(), "alvo-new"))
        elif which == "multi":
            _TMP[key] = build_target(SKILL, os.path.join(base_tmp(), "alvo-multi"), platforms="cursor,copilot,codex",
                                     hook=False)
        elif which == "big":
            _TMP[key] = build_target(SKILL, os.path.join(base_tmp(), "alvo-big"), hook=False, extra_terms=BIG_N)
        elif which == "old":
            _TMP[key] = build_target(old_skill(), os.path.join(base_tmp(), "alvo-old"))
    return _TMP[key]


def old_skill():
    if "old" in _TMP:
        return _TMP["old"]
    d = os.environ.get("CS_OLD_SKILL_DIR")
    if not d:
        d = os.path.join(base_tmp(), "skill-%s" % OLD_VERSION)
        p = subprocess.run(["git", "-C", PROJECT, "archive", "--format=tar", OLD_COMMIT], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=300)
        if p.returncode != 0:
            raise AssertionError("git archive %s falhou: %s — defina $CS_OLD_SKILL_DIR" % (OLD_COMMIT, p.stderr.decode()))
        os.makedirs(d)
        with tarfile.open(fileobj=io.BytesIO(p.stdout)) as tf:
            if hasattr(tarfile, "data_filter"):
                tf.extractall(d, filter="data")
            else:
                tf.extractall(d)
    d = os.path.realpath(d)
    v = read_text(os.path.join(d, "VERSION")).strip()
    if v != OLD_VERSION:
        raise AssertionError("skill antiga em %s tem VERSION %s (esperado %s)" % (d, v, OLD_VERSION))
    _TMP["old"] = d
    return d


def new_task(root, agent=AGENT, title="Ajustar etapa", path="src/cultivo/clima.py", goal=None):
    args = ["new", "task", "--tipo", "US", "--agent", agent, "--title", title, "--avulsa", "--verify-cmd", VERIFY,
            "--como", "produtor", "--quero", goal or title.lower(), "--para", "colher melhor",
            "--criterio", "AC-1|Dado lote Quando ajusto Então funciona|tests.test_ok", "--allowed-path", path]
    out = st_ok(root, *args)
    got = CREATED_RE.findall(out)
    if not got:
        raise AssertionError("`new task` deveria imprimir `criado <ID> em <path>`: %r" % out)
    return got[0][0]


def dispatched_task(root, agent=AGENT, path="src/cultivo/clima.py", title="Ajustar etapa", goal=None):
    tid = new_task(root, agent, title, path, goal)
    st_ok(root, "start", tid)
    st_ok(root, "dispatch", tid, "--manual", "--model", "sonnet")
    return tid


def guard(root, mode, payload):
    return run([sys.executable, os.path.join(root, SD, "harness", "guard.py"), mode], root,
               stdin=json.dumps(payload), extra={"CLAUDE_PROJECT_DIR": root})


def payload(root, tool_name, tool_input, agent=None):
    p = {"tool_name": tool_name, "tool_input": tool_input, "cwd": root, "session_id": "s-oraculo",
         "tool_use_id": "tu-%d" % (_TMP.setdefault("tu", 0) + 1)}
    _TMP["tu"] += 1
    if agent:
        p["agent_id"] = "ag-%s" % agent
        p["agent_type"] = agent
    return p


def trail_hits(root, token):
    """Linhas de arquivos de texto sob .swarm/ (fora do cache do índice) que contêm `token`: [(rel, linha)]."""
    out = []
    base = os.path.join(root, SD)
    for dp, dns, fns in os.walk(base):
        rel_dp = os.path.relpath(dp, root).replace(os.sep, "/")
        if rel_dp.startswith(SD + "/memory/index") or rel_dp.startswith(SD + "/harness"):
            dns[:] = []
            continue
        for fn in fns:
            p = os.path.join(dp, fn)
            try:
                if os.path.getsize(p) > 20 * 1024 * 1024:
                    continue
                txt = read_text(p)
            except (OSError, UnicodeDecodeError):
                continue
            for ln in txt.splitlines():
                if token in ln:
                    out.append((os.path.relpath(p, root).replace(os.sep, "/"), ln))
    return out


def json_values(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            for x in json_values(v):
                yield x
    elif isinstance(obj, list):
        for v in obj:
            for x in json_values(v):
                yield x
    else:
        yield obj


def json5io():
    if SCRIPTS not in sys.path:
        sys.path.insert(0, SCRIPTS)
    from cslib import json5io as j
    return j


# ================================================================================================ M1
class Alvo(unittest.TestCase):
    """Cada teste recebe uma cópia do alvo novo (com .git e o hook)."""
    which = "new"

    def setUp(self):
        self.root = copy_target(template(self.which), "t")
        self.addCleanup(shutil.rmtree, self.root, True)

    def nb(self, agent=AGENT):
        return notebook_path(self.root, agent)


class TestM1CadernoGerado(Alvo):
    def test_m1_correct_gera_caderno_com_bloco_no_topo(self):
        correct(self.root, AGENT, "use a chave do pré-requisito marcador-m1a")
        a, b, blk, before, after = block_of(self.root, AGENT)
        self.assertLessEqual(a, 2, "o bloco gerado fica no TOPO do MEMORY.md (marcador inicial nas 3 primeiras linhas)")
        self.assertFalse(before.strip() and MARK_RE.search(before), before)
        self.assertIn("marcador-m1a", blk, "a correção recebida está no bloco")

    def test_m1_add_licao_gera_caderno(self):
        mem_ok(self.root, "add", "--agent", AGENT, "--kind", "lesson", "--rule", "registre a etapa marcador-m1b",
               "--why", "convenção", "--paths", TERRITORY)
        self.assertIn("marcador-m1b", block_of(self.root, AGENT)[2])

    def test_m1_secoes_do_bloco(self):
        correct(self.root, AGENT, "use a chave do pré-requisito marcador-m1c")
        blk = block_of(self.root, AGENT)[2]
        nb = norm(blk)
        for s in SECTIONS:
            self.assertIn(s, nb, "seção %r ausente do bloco:\n%s" % (s, blk))
        self.assertIn("marcador-m1c", section_text(blk, "correcoes recebidas"))
        self.assertIn(norm(FOOTGUN), norm(section_text(blk, "armadilhas")), "armadilha do cartão no bloco")
        q = section_text(blk, "quando pesquisar")
        self.assertIn("cs-mem search", q, "gatilho de pesquisa com o comando")
        self.assertTrue(any(re.search(r"\b%s\b" % re.escape(norm(t)), norm(q)) for t, _ in TERMS),
                        "gatilho derivado de termo do território (scan):\n%s" % q)

    def test_m1_marcadores_documentados(self):
        correct(self.root, AGENT, "use a chave do pré-requisito marcador-m1d")
        a = block_of(self.root, AGENT)[0]
        first = read_text(self.nb()).split("\n")[a]
        tok = re.search(r"cs-mem[\w:.\-]*", first).group(0)
        docs = []
        for d in ("docs", "references"):
            for dp, _, fns in os.walk(os.path.join(SKILL, d)):
                docs += [os.path.join(dp, f) for f in fns if f.endswith(".md")]
        hits = [p for p in docs if tok in read_text(p) and "MEMORY.md" in read_text(p)]
        self.assertTrue(hits, "o marcador %r e o MEMORY.md documentados em docs/ ou references/" % tok)

    def test_m1_sem_correcao_nao_ha_vacuo_controle(self):
        """Calibração: um alvo recém-gerado sem lição não tem bloco com correção inventada."""
        p = self.nb()
        if os.path.isfile(p):
            sp = split_notebook(read_text(p))
            if sp:
                self.assertNotIn("marcador-", sp[2])


# ================================================================================================ M2
class TestM2Regeneracao(Alvo):
    def test_m2_correct_regenera_e_preserva_area_livre(self):
        correct(self.root, AGENT, "use a chave do pré-requisito marcador-m2a")
        write(self.root, notebook_rel(AGENT), "\n## Minhas notas\n- nota-livre-m2a\n", mode="a")
        correct(self.root, AGENT, "agende pelo grafo marcador-m2b plantio colheita")
        txt = read_text(self.nb())
        a, b, blk, before, after = block_of(self.root, AGENT)
        self.assertIn("marcador-m2a", blk)
        self.assertIn("marcador-m2b", blk)
        self.assertIn("nota-livre-m2a", after, "a área livre (abaixo do bloco) sobrevive à regeneração")
        self.assertEqual(txt.count("nota-livre-m2a"), 1)

    def test_m2_notas_anteriores_ao_primeiro_bloco_preservadas(self):
        write(self.root, notebook_rel(AGENT), "# Caderno\n\n- nota-antiga-m2c escrita pelo agente\n")
        correct(self.root, AGENT, "use a chave do pré-requisito marcador-m2c")
        a, b, blk, before, after = block_of(self.root, AGENT)
        self.assertIn("marcador-m2c", blk)
        self.assertIn("nota-antiga-m2c", before + after, "notas que já existiam continuam no caderno")
        self.assertNotIn("nota-antiga-m2c", blk, "a nota do agente fica fora do bloco")

    def test_m2_decaimento_tira_licao_do_bloco(self):
        correct(self.root, AGENT, "use a chave do pré-requisito marcador-m2d")
        correct(self.root, AGENT, "regue de manhã marcador-m2e sombreamento umidade")
        self.assertIn("marcador-m2d", block_of(self.root, AGENT)[2])
        lf = [os.path.join(dp, f) for dp, _, fns in os.walk(os.path.join(self.root, SD, "state", "memory", "agents"))
              for f in fns if f.split(".")[0] == AGENT]
        self.assertEqual(len(lf), 1, lf)
        data = json5io().loads(read_text(lf[0]))
        hit = 0
        for l in data["lessons"]:
            if "marcador-m2d" in l["rule"]:
                l["first_seen"] = l["last_hit"] = "2020-01-01T00:00:00Z"
                hit += 1
        self.assertEqual(hit, 1)
        with open(lf[0], "w", encoding="utf-8") as fh:
            fh.write(json.dumps(data, ensure_ascii=False, indent=1))
        mem_ok(self.root, "archive")
        blk = block_of(self.root, AGENT)[2]
        self.assertNotIn("marcador-m2d", blk, "lição arquivada por decaimento sai do bloco")
        self.assertIn("marcador-m2e", blk)

    def test_m2_outro_agente_intacto(self):
        correct(self.root, OTHER, "mostre a dose vinda do cultivo marcador-m2f", paths=("src/painel/**",))
        block_of(self.root, OTHER)
        before = read_bytes(self.nb(OTHER))
        correct(self.root, AGENT, "use a chave do pré-requisito marcador-m2g")
        mem_ok(self.root, "add", "--agent", AGENT, "--kind", "lesson", "--rule", "outra lição marcador-m2h vaso",
               "--why", "x", "--paths", TERRITORY)
        self.assertEqual(read_bytes(self.nb(OTHER)), before, "lição de outro agente não regrava este caderno")
        self.assertNotIn("marcador-m2g", read_text(self.nb(OTHER)))

    def test_m2_bloco_derivado_so_do_cs_mem(self):
        """Caminho único cs-mem → caderno: linha posta à mão no bloco some na regeneração; lição escrita só na área
        livre não vira lição registrada nem entra no bloco."""
        correct(self.root, AGENT, "use a chave do pré-requisito marcador-m2j")
        a, b, blk, before, after = block_of(self.root, AGENT)
        lines = read_text(self.nb()).split("\n")
        lines.insert(b, "- Faça: correção-a-mão-m2j")
        lines.append("- Faça: lição-só-no-caderno-m2k")
        write(self.root, notebook_rel(AGENT), "\n".join(lines))
        correct(self.root, AGENT, "regue de manhã marcador-m2l sombreamento")
        blk = block_of(self.root, AGENT)[2]
        self.assertNotIn("correção-a-mão-m2j", blk, "o bloco é regenerado das lições ativas do cs-mem")
        self.assertNotIn("lição-só-no-caderno-m2k", blk)
        self.assertIn("marcador-m2l", blk)
        rules = " ".join(l.get("rule", "") for l in lessons_of(self.root, AGENT))
        self.assertNotIn("m2k", rules, "nota no caderno não é correção registrada")

    def test_m2_regenerar_sem_mudanca_mesmos_bytes(self):
        correct(self.root, AGENT, "use a chave do pré-requisito marcador-m2i")
        block_of(self.root, AGENT)
        write(self.root, notebook_rel(AGENT), "\n- nota-m2i\n", mode="a")
        before = read_bytes(self.nb())
        mem_ok(self.root, "archive")
        self.assertEqual(read_bytes(self.nb()), before, "archive sem mudança não altera o caderno")


# ================================================================================================ M3
class TestM3Limite(Alvo):
    def test_m3_bloco_cabe_200_linhas_25kb(self):
        import random
        rnd = random.Random(21)
        alpha = "bcdfghjklmnpqrstvwxz"
        last = None
        for i in range(34):
            words = ["".join(rnd.choice(alpha) for _ in range(7)) for _ in range(30)]
            last = "marcador-m3-%02d %s" % (i, " ".join(words))
            correct(self.root, AGENT, last[:250], wrong=" ".join(words[:8]), why=" ".join(words[8:16]))
        a, b, blk, before, after = block_of(self.root, AGENT)
        self.assertLess(b, MAX_LINES, "o marcador final está dentro das %d linhas injetadas (linha %d)" % (MAX_LINES, b + 1))
        self.assertLessEqual(len(blk.encode("utf-8")), MAX_BYTES, "bloco ≤ 25 KB")
        self.assertIn("marcador-m3-33", blk, "a correção mais recente está no bloco")


# ================================================================================================ M4
class TestM4Guard(Alvo):
    def setUp(self):
        Alvo.setUp(self)
        correct(self.root, AGENT, "use a chave do pré-requisito marcador-m4")
        correct(self.root, OTHER, "mostre a dose vinda do cultivo marcador-m4o", paths=("src/painel/**",))
        self.tid = dispatched_task(self.root, AGENT, "src/cultivo/clima.py")
        self.otid = dispatched_task(self.root, OTHER, "src/painel/app.py", title="Ajustar painel")

    def pre(self, tool_name, ti, agent):
        return guard(self.root, "pre-write", payload(self.root, tool_name, ti, agent))

    def protected_or_restored(self, tool_name, ti, agent, apply_fn):
        """Bloco protegido: o pre-write recusa (exit 2) OU, aplicada a escrita, o post-edit (ou o fim do subagente /
        a parada) restaura o bloco que o cs-mem gerou."""
        code, out, err = self.pre(tool_name, ti, agent)
        if code == 2:
            return "recusado"
        self.assertEqual(code, 0, out + err)
        orig = block_of(self.root, agent or AGENT)[2] if agent else block_of(self.root, AGENT)[2]
        apply_fn()
        pl = payload(self.root, tool_name, ti, agent)
        pl["tool_response"] = {"filePath": ti.get("file_path"), "success": True}
        guard(self.root, "post-edit", pl)
        sp = split_notebook(read_text(ti["file_path"]))
        if not (sp and sp[2] == orig):
            guard(self.root, "subagent-stop" if agent else "stop", payload(self.root, None, {}, agent))
            sp = split_notebook(read_text(ti["file_path"]))
        self.assertTrue(sp and sp[2] == orig, "bloco editado à mão nem recusado nem restaurado:\n%s"
                        % read_text(ti["file_path"])[:1500])
        return "restaurado"

    def test_m4_subagente_edit_na_area_livre_liberado(self):
        p = self.nb()
        write(self.root, notebook_rel(AGENT), "\n## Notas\n- nota-m4a\n", mode="a")
        ti = {"file_path": p, "old_string": "- nota-m4a", "new_string": "- nota-m4a revisada"}
        code, out, err = self.pre("Edit", ti, AGENT)
        self.assertEqual(code, 0, "o subagente edita a área livre do PRÓPRIO caderno:\n%s%s" % (out, err))
        blk = block_of(self.root, AGENT)[2]
        write(self.root, notebook_rel(AGENT), read_text(p).replace("- nota-m4a", "- nota-m4a revisada"))
        pl = payload(self.root, "Edit", ti, AGENT)
        pl["tool_response"] = {"filePath": p, "success": True}
        guard(self.root, "post-edit", pl)
        self.assertIn("nota-m4a revisada", read_text(p), "a edição da área livre não é revertida")
        self.assertEqual(block_of(self.root, AGENT)[2], blk)

    def test_m4_subagente_write_preservando_bloco_liberado(self):
        p = self.nb()
        block_of(self.root, AGENT)
        content = read_text(p).rstrip("\n") + "\n\n## Notas\n- nota-m4b\n"
        code, out, err = self.pre("Write", {"file_path": p, "content": content}, AGENT)
        self.assertEqual(code, 0, "Write do próprio caderno com o bloco intacto é liberado:\n%s%s" % (out, err))

    def test_m4_subagente_edita_o_bloco_continua_protegido(self):
        p = self.nb()
        if os.path.isfile(p) and split_notebook(read_text(p)):
            blk = split_notebook(read_text(p))[2]
            line = [ln for ln in blk.split("\n") if "marcador-m4" in ln][0]
            ti = {"file_path": p, "old_string": line, "new_string": line.replace("marcador-m4", "adulterado-m4")}
        else:
            ti = {"file_path": p, "old_string": "marcador-m4", "new_string": "adulterado-m4"}
        self.protected_or_restored("Edit", ti, AGENT, lambda: write(
            self.root, notebook_rel(AGENT), read_text(p).replace(ti["old_string"], ti["new_string"], 1)))

    def test_m4_subagente_write_com_bloco_adulterado_continua_protegido(self):
        p = self.nb()
        cur = read_text(p) if os.path.isfile(p) else "<!-- cs-mem:inicio -->\n- marcador-m4\n<!-- cs-mem:fim -->\n"
        content = cur.replace("marcador-m4", "adulterado-m4", 1)
        self.protected_or_restored("Write", {"file_path": p, "content": content}, AGENT,
                                   lambda: write(self.root, notebook_rel(AGENT), content))

    def test_m4_outro_agente_nao_escreve_caderno_alheio_continua(self):
        p = self.nb()
        cur = read_text(p) if os.path.isfile(p) else ""
        code, out, err = self.pre("Write", {"file_path": p, "content": cur + "\n- intrusa\n"}, OTHER)
        self.assertEqual(code, 2, "dev-painel não escreve no caderno de dev-cultivo:\n%s%s" % (out, err))
        code, out, err = self.pre("Edit", {"file_path": p, "old_string": "x", "new_string": "y"}, OTHER)
        self.assertEqual(code, 2)

    def test_m4_outro_agente_bash_no_caderno_alheio_continua(self):
        pl = payload(self.root, "Bash", {"command": "echo intrusa >> %s" % notebook_rel(AGENT)}, OTHER)
        code, out, err = guard(self.root, "pre-bash", pl)
        self.assertEqual(code, 2, out + err)

    def test_m4_orquestrador_nao_escreve_o_bloco_continua(self):
        p = self.nb()
        cur = read_text(p) if os.path.isfile(p) else "<!-- cs-mem:inicio -->\n- marcador-m4\n<!-- cs-mem:fim -->\n"
        content = cur.replace("marcador-m4", "adulterado-m4", 1)
        self.protected_or_restored("Write", {"file_path": p, "content": content}, None,
                                   lambda: write(self.root, notebook_rel(AGENT), content))

    def test_m4_verify_nao_conta_o_caderno_do_agente_continua(self):
        """Durante a delegação o agente anota no caderno e o cs-mem o regenera (correção nova): o verify continua
        verde (o caderno não é escrita fora de allowed_paths)."""
        write(self.root, "src/cultivo/clima.py", "UMIDADE_ALVO = 72\n")
        write(self.root, notebook_rel(AGENT), "\n- nota durante a task m4v\n", mode="a")
        correct(self.root, AGENT, "regue de manhã marcador-m4v sombreamento")
        st_ok(self.root, "submit", self.tid, "--files-changed", "src/cultivo/clima.py", "--check", "unittest: OK",
              "--risk", "nenhum", "--handoff-notes", "consultei: nada — tarefa sem termo novo", actor=AGENT)
        code, out, err = tool(self.root, "state", "verify", self.tid)
        self.assertEqual(code, 0, "verify não pode reprovar pelo caderno do próprio agente:\n%s%s" % (out, err))


# ================================================================================================ M5
class TestM5PreCommit(Alvo):
    def test_m5_commit_do_caderno_passa_sem_no_verify(self):
        correct(self.root, AGENT, "use a chave do pré-requisito marcador-m5a")
        block_of(self.root, AGENT)
        write(self.root, notebook_rel(AGENT), "\n## Notas\n- nota-m5a\n", mode="a")
        git(self.root, "add", "-A")
        self.assertIn(notebook_rel(AGENT), git(self.root, "diff", "--cached", "--name-only"))
        code, out, moved = try_commit(self.root, "caderno")
        self.assertEqual(code, 0, "commit do caderno (bloco gerado + área livre) deveria passar:\n%s" % out[-3000:])
        self.assertTrue(moved)
        self.assertIn("validate", out, "o hook rodou")
        # 2º commit: só a área livre mudou
        write(self.root, notebook_rel(AGENT), "- nota-m5b\n", mode="a")
        git(self.root, "add", "--", notebook_rel(AGENT))
        code, out, moved = try_commit(self.root, "nota")
        self.assertEqual(code, 0, "área livre editada depois: commit passa:\n%s" % out[-3000:])

    def _barred(self, mutate):
        correct(self.root, AGENT, "use a chave do pré-requisito marcador-m5c")
        p = self.nb()
        if not os.path.isfile(p):
            write(self.root, notebook_rel(AGENT), "<!-- cs-mem:inicio -->\n- marcador-m5c\n<!-- cs-mem:fim -->\n")
        write(self.root, notebook_rel(AGENT), mutate(read_text(p)))
        git(self.root, "add", "-A")
        code, out, moved = try_commit(self.root, "caderno adulterado")
        self.assertNotEqual(code, 0, "bloco adulterado deveria ser barrado:\n%s" % out[-3000:])
        self.assertFalse(moved)
        self.assertIn(notebook_rel(AGENT), out, "a recusa cita o caderno")

    def test_m5_bloco_adulterado_continua_barrado(self):
        self._barred(lambda t: t.replace("marcador-m5c", "adulterado-m5c", 1))

    def test_m5_bloco_removido_continua_barrado(self):
        def strip(t):
            sp = split_notebook(t)
            return (sp[3] + "\n" + sp[4]) if sp else "# vazio\n"
        self._barred(strip)


# ================================================================================================ M6
class TestM6Sobrevive(Alvo):
    def test_m6_emit_install_upgrade_nao_mudam_o_caderno(self):
        correct(self.root, AGENT, "use a chave do pré-requisito marcador-m6a")
        write(self.root, notebook_rel(AGENT), "\n## Notas\n- nota-m6a\n", mode="a")
        before = read_bytes(self.nb())
        block_of(self.root, AGENT)
        for args in (("emit", "--allow-outside"), ("harness", "install", "--allow-outside"),
                     ("upgrade", "--apply", "--allow-outside")):
            cs_ok(SKILL, self.root, *args)
            self.assertTrue(os.path.isfile(self.nb()), "%s apagou o caderno" % " ".join(args))
            self.assertEqual(read_bytes(self.nb()), before, "%s mudou o caderno" % " ".join(args))


class TestM6UpgradeDe0101(Alvo):
    which = "old"

    def test_m6_upgrade_gera_caderno_de_licao_existente_e_commita(self):
        code, out, err = mem(self.root, "correct", "--agent", AGENT, "--wrong", "fazer do jeito óbvio", "--right",
                             "use a chave do pré-requisito marcador-m6b", "--why", "convenção", "--paths", TERRITORY)
        self.assertEqual(code, 0, out + err)
        commit_all(self.root, "lição na 0.10.1")
        self.assertFalse(os.path.isfile(self.nb()), "a 0.10.1 não tinha caderno (fixture)")
        cs_ok(SKILL, self.root, "upgrade", "--apply", "--allow-outside")
        self.assertIn("marcador-m6b", block_of(self.root, AGENT)[2], "o upgrade gera o caderno a partir da lição")
        git(self.root, "add", "-A")
        code, out, moved = try_commit(self.root, "upgrade")
        self.assertEqual(code, 0, "commit do upgrade (com o caderno) passa sem --no-verify:\n%s" % out[-3000:])
        self.assertTrue(moved)


# ================================================================================================ M7
class TestM7Brief(Alvo):
    def brief(self):
        tid = new_task(self.root, AGENT, M7_TITLE, M7_PATH, goal=M7_GOAL)
        st_ok(self.root, "start", tid)
        return tid, st_ok(self.root, "brief", tid)

    def test_m7_termo_relevante_primeiro_sem_dump(self):
        _, b = self.brief()
        nb = norm(b)
        self.assertIn(norm(RELEVANT_MARK), nb, "o termo relevante (título/goal) está no brief:\n%s" % b)
        pos = nb.index(norm(RELEVANT_MARK))
        irr = [t for t, _ in TERMS if t != RELEVANT_TERM and re.search(r"\b%s\b" % re.escape(norm(t)), nb)]
        self.assertLessEqual(len(irr), 8, "dump do glossário: %d termos sem relação no brief: %s" % (len(irr), irr))
        for t in irr:
            self.assertLess(pos, nb.index(norm(t)), "termo sem relação (%s) antes do relevante" % t)

    def test_m7_rotulos_referencias_e_fora_de_escopo_nao_vazios(self):
        _, b = self.brief()
        empty = re.findall(r"(?im)^.*(refer[eê]ncias|fora de escopo)[^:\n]*:\s*$", b)
        self.assertFalse(empty, "rótulo vazio no brief (preencha ou omita com motivo): %s\n%s" % (empty, b))

    def test_m7_brief_traz_resultado_da_busca_controle(self):
        mem_ok(self.root, "add", "--kind", "decision", "--text",
               "Vernalização das sementes dura seis semanas no lote frio (decisão do dono marcador-m7d)",
               "--scope", TERRITORY, "--founder", "Ana")
        _, b = self.brief()
        self.assertIn("marcador-m7d", b, "o harness busca na memória e põe o resultado no brief")

    def test_m7_licao_relevante_no_brief_controle(self):
        correct(self.root, AGENT, "vernalização conta semanas inteiras marcador-m7l")
        _, b = self.brief()
        self.assertIn("marcador-m7l", b)

    def test_m7_task_titulo_escopo_aceite_continua(self):
        _, b = self.brief()
        for s in (M7_TITLE, M7_PATH, "AC-1"):
            self.assertIn(s, b)


# ================================================================================================ M8
class TestM8OutrasPlataformas(Alvo):
    which = "multi"

    def test_m8_brief_e_o_canal_da_licao_controle(self):
        correct(self.root, AGENT, "use a chave do pré-requisito marcador-m8")
        tid = new_task(self.root, AGENT, "Registrar etapa", "src/cultivo/dependencias.py")
        st_ok(self.root, "start", tid)
        self.assertIn("marcador-m8", st_ok(self.root, "brief", tid), "Cursor/Copilot/Codex: a lição chega pelo brief")


class TestM8CartaoClaude(Alvo):
    def test_m8_cartao_declara_memory_project_continua(self):
        card = read_text(os.path.join(self.root, ".claude", "agents", AGENT + ".md"))
        self.assertRegex(card.split("---", 2)[1], r"(?m)^memory:\s*project\s*$")


# ================================================================================================ M9
class TestM9Rastro(Alvo):
    def search(self, q, agent=AGENT, js=True):
        args = ["search", q, "--agent", agent] + (["--json"] if js else [])
        return mem_ok(self.root, *args)

    def assert_trail(self, token, agent, n):
        hits = trail_hits(self.root, token)
        self.assertTrue(hits, "cs-mem search não deixou rastro com %r sob .swarm/" % token)
        recs = []
        for rel, ln in hits:
            try:
                recs.append((rel, json.loads(ln)))
            except ValueError:
                continue
        self.assertTrue(recs, "rastro não é JSONL: %s" % hits[:2])
        ok = [(rel, r) for rel, r in recs if isinstance(r, dict) and agent in list(json_values(r))
              and any(isinstance(v, str) and token in v for v in json_values(r))
              and any(type(v) is int and v == n for v in json_values(r))]
        self.assertTrue(ok, "registro sem (agente=%s, consulta, hits=%d): %s" % (agent, n, recs[:2]))
        return ok[0][0]

    def test_m9_search_registra_agente_consulta_hits(self):
        q = "vernalização sementes rastro-m9a"
        n = len(json.loads(self.search(q))["results"])
        self.assert_trail("rastro-m9a", AGENT, n)

    def test_m9_zero_hits_registrado(self):
        self.assert_trail("qzxwvk-m9b", AGENT, len(json.loads(self.search("qzxwvk-m9b"))["results"]))

    def test_m9_saida_texto_tambem_registra(self):
        self.search("calagem rastro-m9c", js=False)
        self.assertTrue(trail_hits(self.root, "rastro-m9c"))

    def test_m9_append_only(self):
        self.search("vernalização rastro-m9d")
        rel = trail_hits(self.root, "rastro-m9d")
        self.assertTrue(rel, "sem rastro")
        p = os.path.join(self.root, rel[0][0])
        first = read_bytes(p)
        self.search("calagem rastro-m9e", agent=OTHER)
        self.assertTrue(read_bytes(p).startswith(first), "o rastro só cresce (append-only)")
        self.assertTrue(trail_hits(self.root, "rastro-m9e"))

    def test_m9_busca_continua_respondendo_controle(self):
        res = json.loads(self.search("vernalização"))["results"]
        self.assertTrue(res, "a busca continua devolvendo resultados")


# ================================================================================================ M10
class TestM10Consultei(Alvo):
    def setUp(self):
        Alvo.setUp(self)
        self.tid = dispatched_task(self.root, AGENT, "src/cultivo/clima.py")
        write(self.root, "src/cultivo/clima.py", "UMIDADE_ALVO = 71\n")

    def submit(self, notes):
        return tool(self.root, "state", "submit", self.tid, "--files-changed", "src/cultivo/clima.py", "--check",
                    "unittest: OK", "--risk", "nenhum", "--handoff-notes", notes, actor=AGENT)

    def submit_verify(self, notes):
        code, out, err = self.submit(notes)
        if code != 0:
            return "submit", code, out + err
        code, out, err = tool(self.root, "state", "verify", self.tid)
        return "verify", code, out + err

    def searched_id(self, q):
        res = json.loads(mem_ok(self.root, "search", q, "--agent", AGENT, "--json"))["results"]
        self.assertTrue(res, "fixture: a busca %r deveria achar algo" % q)
        return res[0]["id"]

    def test_m10_consulta_real_aceita_controle(self):
        q = "vernalização sementes consulta-m10a"
        rid = self.searched_id(q)
        stage, code, out = self.submit_verify('consultei: "%s" -> %s (efeito: ajustei UMIDADE_ALVO)' % (q, rid))
        self.assertEqual(code, 0, "consulta registrada e ID saído dela: submit e verify passam (%s):\n%s" % (stage, out))

    def test_m10_consultei_nada_aceito_controle(self):
        stage, code, out = self.submit_verify("consultei: nada — tarefa sem termo novo")
        self.assertEqual(code, 0, "%s:\n%s" % (stage, out))

    def test_m10_consulta_inexistente_no_rastro_recusada(self):
        stage, code, out = self.submit_verify('consultei: "consulta-fantasma-m10c" -> gloss.calagem (efeito: nenhum)')
        self.assertNotEqual(code, 0, "consulta citada que não está no rastro deveria ser recusada (submit ou verify)")
        self.assertRegex(norm(out), r"consult|consulta-fantasma-m10c", out)

    def test_m10_id_que_nao_saiu_da_busca_recusado(self):
        q = "vernalização sementes consulta-m10e"
        self.searched_id(q)
        stage, code, out = self.submit_verify('consultei: "%s" -> gloss.inventado-m10e (efeito: x)' % q)
        self.assertNotEqual(code, 0, "o ID citado tem de sair da busca registrada/reexecutada (%s)" % stage)
        self.assertRegex(norm(out), r"consult|gloss\.inventado-m10e", out)

    def gate_view(self):
        """O que o gate vê da task: saída do verify, `cs-state why`, brief de revisão do reviewer e o estado gravado."""
        parts = []
        for args in (("verify", self.tid), ("why", self.tid), ("brief", self.tid, "--phase", "review", "--agent",
                                                                "reviewer")):
            code, out, err = tool(self.root, "state", *args)
            parts.append(out + err)
        for dp, dns, fns in os.walk(os.path.join(self.root, SD)):
            if os.path.relpath(dp, self.root).startswith(os.path.join(SD, "harness")):
                dns[:] = []
                continue
            for fn in fns:
                if self.tid in fn:
                    parts.append(read_text(os.path.join(dp, fn)))
        return "\n".join(parts)

    @staticmethod
    def undeclared(text):
        return [ln for ln in norm(text).split("\n") if "consultei" in ln and re.search(r"nao declarad|sem declarac", ln)]

    def test_m10_submit_sem_consultei_aceito_e_registrado_nao_declarado(self):
        code, out, err = self.submit("feito")
        self.assertEqual(code, 0, "submit sem 'consultei:' é ACEITO (oráculos congelados submetem sem):\n%s%s"
                         % (out, err))
        view = self.gate_view()
        self.assertTrue(self.undeclared(view), "o gate (verify/why/brief de revisão/estado) mostra 'consultei: não "
                                               "declarado':\n%s" % view[-3000:])

    def test_m10_declarado_nao_aparece_como_nao_declarado_controle(self):
        code, out, err = self.submit("consultei: nada — tarefa sem termo novo")
        self.assertEqual(code, 0, out + err)
        self.assertFalse(self.undeclared(self.gate_view()), "declaração feita não pode virar 'não declarado'")

    def test_m10_brief_ensina_consultei(self):
        self.assertIn("consultei:", st_ok(self.root, "brief", self.tid), "o brief de implementação mostra o formato")


# ================================================================================================ M11
FAULT_FLAG = "--fault"          # contrato mínimo (ESPEC, M11): quem errou — "brief" (a task mandava) | "agent"


def lessons_of(root, agent):
    d = os.path.join(root, SD, "state", "memory", "agents")
    fs = [os.path.join(d, f) for f in (os.listdir(d) if os.path.isdir(d) else []) if f.split(".")[0] == agent]
    out = []
    for f in fs:
        out += json5io().loads(read_text(f)).get("lessons") or []
    return out


class TestM11QuemErrou(Alvo):
    def corr(self, fault, mark):
        return mem(self.root, "correct", "--agent", AGENT, FAULT_FLAG, fault, "--wrong", "fazer do jeito pedido",
                   "--right", "pedir a chave do pré-requisito %s" % mark, "--why", "convenção", "--paths", TERRITORY)

    def test_m11_erro_do_brief_vai_para_o_lead(self):
        code, out, err = self.corr("brief", "marcador-m11b")
        self.assertEqual(code, 0, out + err)
        lead = [l for l in lessons_of(self.root, "lead") if "marcador-m11b" in l.get("rule", "")]
        self.assertTrue(lead, "a task mandava X e o agente fez X: a lição é do lead/orquestrador")
        self.assertEqual(lead[0].get("source"), "brief")
        self.assertFalse([l for l in lessons_of(self.root, AGENT) if "marcador-m11b" in l.get("rule", "")])
        p = self.nb()
        self.assertFalse(os.path.isfile(p) and "marcador-m11b" in read_text(p), "erro do brief não vai ao caderno")

    def test_m11_erro_do_agente_vai_para_o_caderno(self):
        code, out, err = self.corr("agent", "marcador-m11a")
        self.assertEqual(code, 0, out + err)
        self.assertTrue([l for l in lessons_of(self.root, AGENT) if "marcador-m11a" in l.get("rule", "")])
        self.assertIn("marcador-m11a", block_of(self.root, AGENT)[2])

    def test_m11_correct_skill_pergunta_quem_errou(self):
        txt = read_text(os.path.join(self.root, ".claude", "skills", "correct", "SKILL.md"))
        self.assertIn(FAULT_FLAG, txt, "o /correct gerado classifica de quem é o erro")
        self.assertIn("brief", txt)


# ================================================================================================ M12
SUPERSEDES_FLAG = "--supersedes"   # contrato mínimo (ESPEC, M12): correct --supersedes <id>; retract <id> --reason
PREVIEW_FLAGS = ("--dry-run", "--preview", "--plan")


def jsonl_texts(root):
    """{rel: bytes} dos .jsonl sob .swarm/ (fora do cache do índice) — onde a cadeia/ledger do cs-mem anexa."""
    out = {}
    for dp, dns, fns in os.walk(os.path.join(root, SD)):
        rel_dp = os.path.relpath(dp, root).replace(os.sep, "/")
        if rel_dp.startswith(SD + "/memory/index") or rel_dp.startswith(SD + "/harness"):
            dns[:] = []
            continue
        for fn in fns:
            if fn.endswith(".jsonl"):
                out[os.path.relpath(os.path.join(dp, fn), root)] = read_bytes(os.path.join(dp, fn))
    return out


def appended(before, after):
    return "\n".join((b[len(before.get(k, b"")):] if b.startswith(before.get(k, b"")) else b).decode("utf-8", "replace")
                     for k, b in after.items() if before.get(k) != b)


class TestM12Refinamento(Alvo):
    OLD = "use a chave do pré-requisito antiga-m12"
    NEW = "use a chave do pré-requisito e nomes em maiúsculas refinada-m12"

    def add(self, agent, right, *extra, paths=(TERRITORY,)):
        args = ["correct", "--agent", agent, "--wrong", "fazer do jeito óbvio", "--right", right, "--why", "dono"]
        for p in paths:
            args += ["--paths", p]
        code, out, err = mem(self.root, *(args + list(extra)))
        self.assertEqual(code, 0, out + err)
        return json.loads(out.strip().splitlines()[-1])["id"]

    def active(self, agent, mark):
        return [l for l in lessons_of(self.root, agent) if mark in l.get("rule", "") and l.get("status") == "active"]

    def injected(self, agent, path):
        tid = new_task(self.root, agent, "Registrar etapa nova", path)
        st_ok(self.root, "start", tid)
        brief = st_ok(self.root, "brief", tid)
        inj = mem_ok(self.root, "inject", "--agent", agent, "--paths", path, "--title", "registrar etapa")
        res = json.loads(mem_ok(self.root, "search", "chave pré-requisito antiga-m12 refinada-m12", "--agent", agent,
                                "--json"))["results"]
        return brief, inj, res

    def assert_gone(self, agent, oid, path):
        self.assertFalse(self.active(agent, "antiga-m12"), "a lição antiga não pode continuar active")
        brief, inj, res = self.injected(agent, path)
        self.assertNotIn("antiga-m12", brief, "a lição substituída/retratada não entra no brief")
        self.assertNotIn("antiga-m12", inj)
        for r in res:
            if r.get("id") == oid:
                self.assertNotEqual(r.get("status", "active"), "active", "a busca não a devolve como ativa: %s" % r)
        p = self.nb(agent)
        if os.path.isfile(p) and split_notebook(read_text(p)):
            self.assertNotIn("antiga-m12", split_notebook(read_text(p))[2], "o bloco é regenerado sem ela")

    def test_m12_supersede_em_dois_agentes(self):
        cases = ((AGENT, "src/cultivo/dependencias.py", TERRITORY), (OTHER, "src/painel/app.py", "src/painel/**"))
        olds = {a: self.add(a, self.OLD, paths=(g,)) for a, _, g in cases}
        for a, _, _ in cases:
            self.assertIn("antiga-m12", block_of(self.root, a)[2], "fixture: a antiga entrou no caderno")
        before = jsonl_texts(self.root)
        news = {a: self.add(a, self.NEW, SUPERSEDES_FLAG, olds[a], paths=(g,)) for a, _, g in cases}
        new_txt = appended(before, jsonl_texts(self.root))
        for a, path, _ in cases:
            self.assertIn(olds[a], new_txt, "a substituição registra evento (JSONL) citando a lição antiga")
            self.assert_gone(a, olds[a], path)
            self.assertTrue(self.active(a, "refinada-m12"), "a refinada fica active")
            brief, inj, _ = self.injected(a, path)
            self.assertIn("refinada-m12", brief)
            self.assertIn("refinada-m12", block_of(self.root, a)[2])
            self.assertNotEqual(news[a], olds[a])

    def test_m12_retract_com_motivo(self):
        oid = self.add(AGENT, self.OLD)
        before = jsonl_texts(self.root)
        code, out, err = mem(self.root, "retract", oid, "--reason", "regra errada motivo-m12r")
        self.assertEqual(code, 0, out + err)
        new_txt = appended(before, jsonl_texts(self.root))
        self.assertIn(oid, new_txt, "a retratação registra evento (JSONL)")
        self.assertIn("motivo-m12r", new_txt, "com o motivo")
        self.assert_gone(AGENT, oid, "src/cultivo/dependencias.py")

    def test_m12_retract_sem_motivo_recusado(self):
        oid = self.add(AGENT, self.OLD)
        code, out, err = mem(self.root, "retract", oid)
        self.assertNotEqual(code, 0, "retratar exige --reason")
        self.assertRegex(norm(out + err), r"reason|motivo", "a recusa pede o motivo (não é 'comando desconhecido')")
        self.assertTrue(self.active(AGENT, "antiga-m12"))

    def test_m12_licao_nova_ativa_e_injetada_controle(self):
        self.add(AGENT, self.NEW)
        self.assertTrue(self.active(AGENT, "refinada-m12"))
        brief, inj, _ = self.injected(AGENT, "src/cultivo/dependencias.py")
        self.assertIn("refinada-m12", brief)
        self.assertIn("refinada-m12", inj)

    def test_m12_correct_mostra_e_confirma_antes_de_gravar(self):
        txt = read_text(os.path.join(self.root, ".claude", "skills", "correct", "SKILL.md"))
        body = norm(txt.split("---", 2)[-1])
        i_cmd = body.find("cs-mem correct")
        i_conf = body.find("confirm")
        self.assertGreaterEqual(i_conf, 0, "o /correct pede confirmação ao humano")
        self.assertLess(i_conf, i_cmd, "a confirmação vem ANTES do `cs-mem correct`")
        for w in ("errado", "certo", "porque"):
            self.assertIn(w, body[:i_cmd], "mostra a lição formulada (%s) antes de gravar" % w)
        code, h, e = mem(self.root, "correct", "--help")
        flag = next((f for f in PREVIEW_FLAGS if f in h + e), None)
        if flag:
            before = json.dumps(lessons_of(self.root, AGENT), sort_keys=True)
            code, out, err = mem(self.root, "correct", "--agent", AGENT, "--wrong", "x", "--right", "previa-m12p",
                                 "--why", "y", flag)
            self.assertEqual(code, 0, out + err)
            self.assertIn("previa-m12p", out + err, "a prévia mostra a lição formulada")
            self.assertEqual(json.dumps(lessons_of(self.root, AGENT), sort_keys=True), before, "%s não grava" % flag)
            self.assertFalse(os.path.isfile(self.nb()) and "previa-m12p" in read_text(self.nb()))

# ================================================================================================ M13
def documented_check_cmds(root, agent, brief):
    """O comando `cs-mem check` EXATAMENTE como o cartão emitido e o brief mandam rodar (texto do artefato)."""
    out = []
    card = read_text(os.path.join(root, ".claude", "agents", agent + ".md"))
    for src, txt in (("cartão", card), ("brief", brief)):
        m = re.search(r"((?:\./)?(?:\.swarm/bin/)?cs-mem check[^`\n(]*)", txt)
        if m:
            cmd = m.group(1).strip()
            if not cmd.startswith((".swarm/", "./")):
                cmd = ".swarm/bin/" + cmd
            out.append((src, cmd))
    return out


def lesson_id_order(rule_old, rule_new, agent="qa"):
    """ids como o cs-mem gera (L-<agente>-<sha8 da regra normalizada>)."""
    import hashlib
    f = lambda r: "L-%s-%s" % (agent, hashlib.sha256(" ".join(r.split())[:300].encode("utf-8")).hexdigest()[:8])
    return f(rule_old), f(rule_new)


class TestM13BriefSobOrcamento(Alvo):
    which = "big"

    def test_m13_licao_e_busca_sobrevivem_ao_orcamento(self):
        correct(self.root, AGENT, "vernalização conta semanas inteiras marcador-m13a")
        mem_ok(self.root, "add", "--kind", "decision", "--text",
               "Vernalização das sementes dura seis semanas (decisão do dono marcador-m13b)", "--scope", TERRITORY,
               "--founder", "Ana")
        tid = new_task(self.root, AGENT, M7_TITLE, M7_PATH, goal=M7_GOAL)
        st_ok(self.root, "start", tid)
        b = st_ok(self.root, "brief", tid)
        self.assertIn("marcador-m13a", b, "lição relevante cortada pelo orçamento (glossário de %d termos)" % BIG_N)
        self.assertIn("marcador-m13b", b, "resultado da busca cortado pelo orçamento")
        nb = norm(b)
        big = [t for t, _ in big_terms(BIG_N) if norm(t) in nb]
        irr = [t for t, _ in TERMS if t != RELEVANT_TERM and re.search(r"\b%s\b" % re.escape(norm(t)), nb)]
        self.assertLessEqual(len(big) + len(irr), 8, "dump do glossário sob orçamento: %d termos sem relação"
                             % (len(big) + len(irr)))


class TestM13CheckDocumentado(Alvo):
    def setUp(self):
        Alvo.setUp(self)
        self.tid = dispatched_task(self.root, "qa", "tests/test_ok.py", title="Cobrir etapa")
        write(self.root, "tests/test_ok.py", "\n# cobertura nova\n", mode="a")

    def run_cmd(self, cmd):
        return run(["sh", "-c", cmd], self.root, extra={"CLAUDE_PROJECT_DIR": self.root})

    def test_m13_check_documentado_devolve_licao_da_delegacao(self):
        correct(self.root, "qa", "use fixture de lote marcador-m13c", paths=("tests/**",))
        brief = st_ok(self.root, "brief", self.tid)
        cmds = documented_check_cmds(self.root, "qa", brief)
        self.assertEqual(sorted(c for c, _ in cmds), ["brief", "cartão"], "cartão e brief mandam rodar cs-mem check")
        for src, cmd in cmds:
            self.assertNotIn("<", cmd, "o comando do %s tem placeholder que o agente não sabe preencher: %s" % (src, cmd))
            code, out, err = self.run_cmd(cmd)
            self.assertIn("marcador-m13c", out + err, "o comando do %s (%s), numa delegação com diff em tests/**, "
                                                      "deveria devolver a lição com trigger tests/**:\n%s%s"
                                                      % (src, cmd, out, err))

    def test_m13_check_empate_mais_recente_primeiro(self):
        import time
        # textos sem palavra em comum (o dedup do cs-mem funde lições parecidas: Jaccard ≥ 0,5)
        base_old = "monte fixture compartilhada estufa bandeja semente marcador-m13d"
        base_new = "parametrize casos limite tabela verdade relogio isolado marcador-m13e"
        k = 0
        while True:   # escolhe textos em que o id da ANTIGA ordena antes (hoje o desempate por id a põe primeiro)
            ro, rn = base_old + " v%d" % k, base_new + " v%d" % k
            io, i_n = lesson_id_order("Faça: %s — não: %s" % (ro, "errado-a"), "Faça: %s — não: %s" % (rn, "errado-b"))
            if io < i_n:
                break
            k += 1
        correct(self.root, "qa", ro, wrong="errado-a", why="cobertura antiga", paths=("tests/**",))
        time.sleep(1.2)
        correct(self.root, "qa", rn, wrong="errado-b", why="pedido recente", paths=("tests/**",))
        act = [l for l in lessons_of(self.root, "qa") if l.get("status") == "active"]
        self.assertEqual(len(act), 2, "fixture: duas lições ativas distintas de mesmo count: %s" % act)
        self.assertEqual(sorted(l["id"] for l in act)[0], io, "fixture: a antiga tem o menor id")
        code, out, err = mem(self.root, "check", "--agent", "qa", "--files", "tests/test_ok.py", "--no-run")
        self.assertIn("marcador-m13d", out)
        self.assertIn("marcador-m13e", out)
        self.assertLess(out.index("marcador-m13e"), out.index("marcador-m13d"),
                        "no empate de count, a lição mais recente vem primeiro:\n%s" % out)

if __name__ == "__main__":
    unittest.main()
