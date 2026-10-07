"""estado_lib.py — biblioteca comum dos scripts do harness de desenvolvimento (frente, contrato, guard-estado, sessao,
tech_lead, campanha). Não é comando: só importável. Stdlib, Python 3.9+.

O que mora aqui (uma fonte para todos):
  - caminhos: raiz do projeto ($CS_DEV_SKILL_DIR; padrão: dois níveis acima de .claude/tools), estado, motor
    ($CS_DEV_AC — variável de TESTE; padrão: o motor embutido .claude/tools/ac/ac.py);
  - leitura dos formatos da ESPEC §3: frentes.json, eventos.jsonl, FRENTE.md (Bloco A), tasks (Bloco B), INDEX;
  - o bloco gerado do WORKFLOW.md (entre <!-- frentes:inicio --> e <!-- frentes:fim -->; o resto é humano);
  - git e motor por subprocess (nunca shell).
"""
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ID_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+){0,5}$")
TASK_NOME_RE = re.compile(r"^(\d{2})-(TASK|BUG|GAP|DEBT)-([A-Z0-9]+(?:-[A-Z0-9]+)*)\.md$")
TIPOS_TASK = ("ORACULO", "CORRECAO", "QA", "REVIEW")
CAB_TASK = ("id", "frente", "tipo", "grupo", "agente", "CA", "depends", "status", "gate")
SECOES_TASK = ("Goal", "Contexto", "Subtasks", "Invariants", "Scope IN / OUT", "Arquivos permitidos", "AC", "DoD",
               "Verificação", "Handoff")
ETAPAS = ("E1", "E2", "E3", "E4", "E5")
NOMES_ETAPA = {"E0": "Pré-condição", "E1": "Analisar a demanda", "E2": "Investigação medida",
               "E3": "FRENTE.md (Bloco A)", "E4": "Tasks (Bloco B)", "E5": "Abertura"}
WF_INI = "<!-- frentes:inicio (gerado por .claude/tools/frente.py; não edite à mão) -->"
WF_FIM = "<!-- frentes:fim -->"
MARCADOR_ARCHIVE = "<!-- fechar-frente:archive-completo -->"
# área sensível (roteia opus no revisor; impede complexidade baixa) e texto de protocolo (idem)
SENSIVEIS = (".claude/tools/ac/", "scripts/harness/")
SENSIVEIS_NOME = ("guard", "hook", "frase")
PROTOCOLO = (".claude/skills/", ".claude/CLAUDE.md", ".claude/state/", "SKILL.md", "references/")
TRIVIAIS = ("ls", "echo", "tbd", "true", "cat", ":", "printf")


# ------------------------------------------------------------------ caminhos

def raiz():
    d = os.environ.get("CS_DEV_SKILL_DIR")
    return os.path.realpath(d) if d else os.path.realpath(os.path.join(TOOLS, "..", ".."))


def motor():
    m = os.environ.get("CS_DEV_AC")
    return os.path.realpath(m) if m else os.path.join(TOOLS, "ac", "ac.py")


def state(r=None):
    return os.path.join(r or raiz(), ".claude", "state")


def frente_dir(fid, r=None):
    return os.path.join(state(r), "frentes", fid)


def campanha_dir(fid, r=None):
    return os.path.join(r or raiz(), "campanhas", fid)


def rel(p, r=None):
    return os.path.relpath(p, r or raiz()).replace(os.sep, "/")


def regras(r=None):
    p = os.path.join(TOOLS, "regras.json")
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def agora():
    return datetime.datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


# ------------------------------------------------------------------ arquivos

def ler(p, padrao=None):
    try:
        with open(p, encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return padrao


def gravar(p, txt):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(txt)
    os.replace(tmp, p)


def apensar(p, txt):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(txt)


def sha_txt(txt):
    return hashlib.sha256(txt.encode("utf-8")).hexdigest()


def sha_arquivos(paths, base):
    """sha256 de uma lista de arquivos (caminho relativo + conteúdo), em ordem; ausente entra como ausente."""
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(rel(p, base).encode())
        dados = b"<ausente>"
        if os.path.isfile(p):
            with open(p, "rb") as fh:
                dados = fh.read()
        h.update(hashlib.sha256(dados).digest())
    return h.hexdigest()


def sha_arvore(base, raizes, pular=("__pycache__", ".auto-correcao")):
    """sha1 do conteúdo de várias raízes (arquivo ou pasta) relativas a base; ignora .pyc e .DS_Store."""
    h = hashlib.sha1()
    for r0 in raizes:
        p0 = os.path.join(base, r0)
        if os.path.isfile(p0):
            itens = [p0]
        elif os.path.isdir(p0):
            itens = []
            for d, dirs, fs in os.walk(p0):
                dirs[:] = sorted(x for x in dirs if x not in pular)
                for f in sorted(fs):
                    if f.endswith(".pyc") or f == ".DS_Store" or f.endswith(".tmp"):
                        continue
                    itens.append(os.path.join(d, f))
        else:
            h.update(("<ausente>" + r0).encode())
            continue
        for p in itens:
            h.update(rel(p, base).encode())
            with open(p, "rb") as fh:
                h.update(hashlib.sha1(fh.read()).digest())
    return h.hexdigest()


# ------------------------------------------------------------------ git e motor

def git(r, *args, env=None):
    e = dict(os.environ)
    e.update(env or {})
    p = subprocess.run(["git", "-C", r] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=e)
    return p.returncode, p.stdout.decode("utf-8", "replace").rstrip(), p.stderr.decode("utf-8", "replace").strip()


def ac(work, *args, r=None):
    """Roda o motor (embutido ou $CS_DEV_AC) com --work absoluto; devolve (rc, out, err). Nunca gate/preauth/frase."""
    if args and args[0] in ("gate", "preauth", "frase"):
        raise SystemExit("estado_lib.ac: '%s' é do founder, no terminal dele — nenhum script do harness o roda"
                         % args[0])
    p = subprocess.run([sys.executable, motor(), "--work", work] + list(args), cwd=r or raiz(),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def ac_ok(fid, sub, r=None):
    """`ac.py --work campanhas/<fid> check <sub>` passou? (o motor recusa sem a evidência)."""
    w = campanha_dir(fid, r)
    if not os.path.isdir(os.path.join(w, ".auto-correcao")):
        return False
    return ac(w, "check", sub, r=r)[0] == 0


def campanha_estado(fid, r=None):
    p = os.path.join(campanha_dir(fid, r), ".auto-correcao", "state.json")
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


# ------------------------------------------------------------------ frentes.json e eventos

def frentes(r=None):
    d = None
    t = ler(os.path.join(state(r), "frentes.json"))
    if t:
        try:
            d = json.loads(t)
        except ValueError:
            d = None
    d = d if isinstance(d, dict) else {}
    d.setdefault("schema", 1)
    d.setdefault("ativas", [])
    d.setdefault("entregues", [])
    return d


def salvar_frentes(d, r=None):
    gravar(os.path.join(state(r), "frentes.json"), json.dumps(d, ensure_ascii=False, indent=1) + "\n")


def ids_ativas(r=None):
    return [x["id"] for x in frentes(r)["ativas"]]


def eventos(fid, r=None):
    t = ler(os.path.join(frente_dir(fid, r), "eventos.jsonl"), "")
    out = []
    for linha in t.splitlines():
        if linha.strip():
            try:
                out.append(json.loads(linha))
            except ValueError:
                out.append({"tipo": "invalido", "linha": linha})
    return out


def em_criacao(r=None):
    """ids com eventos.jsonl e sem evento de abertura (criação em andamento)."""
    base = os.path.join(state(r), "frentes")
    out = []
    if os.path.isdir(base):
        for n in sorted(os.listdir(base)):
            ev = eventos(n, r)
            if ev and not any(e.get("tipo") == "abertura" for e in ev):
                out.append(n)
    return out


def aprovadas(ev):
    """{etapa: evento de aprovação} — a última aprovação de cada etapa."""
    out = {}
    for e in ev:
        if e.get("tipo") == "aprovacao":
            out[e["etapa"]] = e
    return out


def etapa_corrente(ev):
    ap = aprovadas(ev)
    for e in ETAPAS:
        if e not in ap:
            return e
    return None


def proposta_pendente(ev, etapa):
    """o último evento de proposta da etapa se ainda não há decisão depois dele."""
    pend = None
    for e in ev:
        if e.get("etapa") != etapa:
            continue
        if e.get("tipo") == "proposta":
            pend = e
        elif e.get("tipo") in ("aprovacao", "rejeicao"):
            pend = None
    return pend


# ------------------------------------------------------------------ Markdown: seções

def secoes(txt):
    """{título de '## ': corpo} (primeira ocorrência), na ordem."""
    out = {}
    atual, buf = None, []
    for linha in txt.splitlines():
        m = re.match(r"^## (.+?)\s*$", linha)
        if m:
            if atual is not None and atual not in out:
                out[atual] = "\n".join(buf).strip("\n")
            atual, buf = m.group(1), []
        elif atual is not None:
            buf.append(linha)
    if atual is not None and atual not in out:
        out[atual] = "\n".join(buf).strip("\n")
    return out


def itens_codigo(corpo):
    """caminhos de itens `- \\`x\\``."""
    return [m.group(1).strip() for m in re.finditer(r"(?m)^\s*-\s+`([^`]+)`", corpo or "")]


# ------------------------------------------------------------------ FRENTE.md

def ler_frente(p):
    txt = ler(p)
    if txt is None:
        return None
    m = re.search(r"(?m)^FRENTE-ID:\s*(\S*)\s*$", txt)
    n = re.search(r"(?m)^Nome:\s*(.+?)\s*$", txt)
    sc = secoes(txt)
    cas = []
    corpo = sc.get("Critérios de Aceitação", "")
    blocos = re.split(r"(?m)^(?=- \*\*CA-\d+)", corpo)
    for b in blocos:
        mm = re.match(r"- \*\*(CA-\d+)\s*[—–-]?\s*(.*?)\*\*(.*)", b, re.S)
        if mm:
            prova = re.search(r"Prova:\s*`([^`]+)`", b)
            cas.append({"id": mm.group(1), "titulo": mm.group(2).strip().rstrip("."), "texto": b.strip(),
                        "prova": prova.group(1) if prova else None})
    aceite = sc.get("Aceite da Frente", "")
    qa = re.search(r"(?m)^### Aceite QA\s*[—–-]\s*(\S+)", aceite)
    rv = re.search(r"(?m)^### Aceite Review\s*[—–-]\s*(\S+)", aceite)
    return {"txt": txt, "id": m.group(1) if m else None, "nome": n.group(1) if n else None, "secoes": sc,
            "cas": cas, "escopo": itens_codigo(sc.get("Escopo de escrita", "")),
            "parada": sc.get("Critério de parada", "").strip(), "historia": sc.get("História", "").strip(),
            "aceite_qa": qa.group(1) if qa else None, "aceite_review": rv.group(1) if rv else None}


# ------------------------------------------------------------------ tasks

def parse_depends(v):
    """'—' | 'ID (porquê), ID (porquê)' → [(id, porquê|None)]."""
    v = (v or "").strip()
    if v in ("", "—", "-", "–", "nenhum", "nenhuma"):
        return []
    partes, buf, nivel = [], "", 0
    for c in v:
        if c == "(":
            nivel += 1
        elif c == ")":
            nivel = max(0, nivel - 1)
        if c == "," and nivel == 0:
            partes.append(buf)
            buf = ""
        else:
            buf += c
    partes.append(buf)
    out = []
    for p in partes:
        p = p.strip()
        if not p:
            continue
        m = re.match(r"^(\S+)\s*(?:\((.*)\))?\s*$", p, re.S)
        if m:
            out.append((m.group(1), (m.group(2) or "").strip() or None))
        else:
            out.append((p.split()[0], None))
    return out


def ler_task(p):
    txt = ler(p)
    if txt is None:
        return None
    cab = {}
    titulo = None
    for linha in txt.splitlines():
        if linha.startswith("## "):
            break
        m = re.match(r"^# (\S+)\s*[—–-]\s*(.*)$", linha)
        if m and titulo is None:
            titulo = (m.group(1), m.group(2).strip())
            continue
        m = re.match(r"^([A-Za-z]+):\s?(.*)$", linha)
        if m and m.group(1) in CAB_TASK + ("complexidade",):
            cab.setdefault(m.group(1), m.group(2).strip())
    sc = secoes(txt)
    verif = sc.get("Verificação", "")
    blocos = re.findall(r"```[a-z]*\n(.*?)```", verif, re.S)
    cmds = []
    for b in blocos:
        cmds += [x.strip() for x in b.splitlines() if x.strip() and not x.strip().startswith("#")]
    if not blocos:
        cmds = [x.strip() for x in verif.splitlines() if x.strip()]
    nome = os.path.basename(p)
    return {"arquivo": p, "nome": nome, "stem": nome[:-3] if nome.endswith(".md") else nome, "txt": txt,
            "cab": cab, "titulo": titulo, "entrega": titulo[1] if titulo else "", "secoes": sc,
            "arquivos": itens_codigo(sc.get("Arquivos permitidos", "")), "verificacao": cmds,
            "depends": parse_depends(cab.get("depends")), "status": cab.get("status", ""),
            "gate": cab.get("gate", ""), "tipo": cab.get("tipo", ""), "grupo": cab.get("grupo", ""),
            "cas": re.findall(r"CA-\d+", cab.get("CA", "")),
            "handoff": sc.get("Handoff", "").strip()}


def ler_tasks(fd):
    d = os.path.join(fd, "TASKS")
    out = []
    if os.path.isdir(d):
        for n in sorted(os.listdir(d)):
            if n.endswith(".md"):
                t = ler_task(os.path.join(d, n))
                if t:
                    out.append(t)
    return out


def verificacao_trivial(cmds):
    if not cmds:
        return True
    for c in cmds:
        w = c.split()[0].lower() if c.split() else ""
        if w not in TRIVIAIS:
            return False
    return True


def sensivel(path):
    p = path.replace(os.sep, "/")
    if any(p.startswith(s) for s in SENSIVEIS):
        return True
    return any(s in os.path.basename(p).lower() for s in SENSIVEIS_NOME)


def protocolo(path):
    p = path.replace(os.sep, "/")
    return any(p.startswith(s) or p == s.rstrip("/") or p.endswith("/" + s.rstrip("/")) for s in PROTOCOLO)


def arquivo_da_propria_task(t, path):
    return path.replace(os.sep, "/").endswith("/TASKS/" + t["nome"])


def arquivos_reais(t):
    """Arquivos permitidos sem o próprio arquivo da task (isento)."""
    return [a for a in t["arquivos"] if not arquivo_da_propria_task(t, a)]


def fecho_depends(tasks):
    """{id: conjunto de ids de que depende, transitivo}."""
    diretos = {t["stem"]: [d for d, _ in t["depends"]] for t in tasks}
    memo = {}

    def vis(i, pilha):
        if i in memo:
            return memo[i]
        if i in pilha:
            return set()
        s = set()
        for d in diretos.get(i, []):
            s.add(d)
            s |= vis(d, pilha | {i})
        memo[i] = s
        return s

    return {i: vis(i, frozenset()) for i in diretos}


def tem_ciclo(tasks):
    diretos = {t["stem"]: [d for d, _ in t["depends"]] for t in tasks}
    cor = {}

    def dfs(i):
        cor[i] = 1
        for d in diretos.get(i, []):
            if d not in diretos:
                continue
            if cor.get(d) == 1:
                return True
            if cor.get(d) is None and dfs(d):
                return True
        cor[i] = 2
        return False

    return any(cor.get(i) is None and dfs(i) for i in diretos)


def feitas(tasks):
    return {t["stem"] for t in tasks if t["status"] == "DONE"}


def elegiveis(tasks):
    f = feitas(tasks)
    return [t for t in tasks if t["status"] != "DONE" and all(d in f for d, _ in t["depends"])]


def progresso(tasks):
    return "%d/%d" % (len(feitas(tasks)), len(tasks)) if tasks else "—"


# ------------------------------------------------------------------ INDEX e WORKFLOW

def render_index(fid, tasks):
    el = elegiveis(tasks)
    prox = el[0]["stem"] if el else "—"
    linhas = ["# INDEX — frente %s" % fid, "", "<!-- gerado por .claude/tools/frente.py a partir dos cabeçalhos das "
              "tasks; não edite à mão -->", "",
              "Progresso: %s · próxima: %s" % (progresso(tasks), prox), "",
              "| id | entrega | tipo | grupo | CAs | depends | status |", "|---|---|---|---|---|---|---|"]
    for t in tasks:
        linhas.append("| %s | %s | %s | %s | %s | %s | %s |" % (
            t["stem"], t["entrega"].replace("|", "/"), t["tipo"], t["grupo"] or "—", t["cab"].get("CA", "—"),
            (t["cab"].get("depends") or "—").replace("|", "/"), t["status"] or "—"))
    return "\n".join(linhas) + "\n"


def linhas_index(fid, r=None):
    t = ler(os.path.join(frente_dir(fid, r), "INDEX.md"), "")
    return [l.split("|")[1].strip() for l in t.splitlines() if re.match(r"^\| \d{2}-(TASK|BUG|GAP|DEBT)-", l)]


def render_bloco_workflow(d):
    at = d.get("ativas") or []
    linhas = [WF_INI, "**Estado:** %s" % ("IN_PROGRESS" if at else "IDLE")]
    if at:
        linhas.append("**Frentes ativas:** " + ", ".join("%s (%s)" % (x["id"], x.get("origem", "?")) for x in at))
    else:
        linhas.append("**Frentes ativas:** nenhuma")
    if d.get("entregues"):
        u = d["entregues"][-1]
        linhas.append("**Última entrega:** %s (%s) — %s" % (u["id"], u.get("fechada_em", "?"), u.get("archive", "")))
    linhas.append(WF_FIM)
    return "\n".join(linhas)


def bloco_workflow_atual(txt):
    if txt and WF_INI in txt and WF_FIM in txt:
        i = txt.index(WF_INI)
        return txt[i:txt.index(WF_FIM, i) + len(WF_FIM)]
    return None


def regravar_workflow(d, r=None):
    p = os.path.join(state(r), "WORKFLOW.md")
    txt = ler(p, "# WORKFLOW\n")
    bloco = render_bloco_workflow(d)
    atual = bloco_workflow_atual(txt)
    if atual is not None:
        novo = txt.replace(atual, bloco, 1)
    else:
        linhas = txt.split("\n", 1)
        novo = linhas[0] + "\n\n" + bloco + "\n" + ("\n" + linhas[1].lstrip("\n") if len(linhas) > 1 else "")
    if novo != txt:
        gravar(p, novo)
    return novo != txt


def workflow_em_dia(d, r=None):
    txt = ler(os.path.join(state(r), "WORKFLOW.md"), "")
    atual = bloco_workflow_atual(txt)
    if atual is None:
        return not d.get("ativas") and not d.get("entregues")
    return atual == render_bloco_workflow(d)


# ------------------------------------------------------------------ saída

def saida(obj, a, texto, brief=None):
    """--json imprime obj; --brief imprime brief (≤ 40 linhas); senão texto."""
    if getattr(a, "json", False):
        print(json.dumps(obj, ensure_ascii=False, indent=1))
    elif getattr(a, "brief", False) and brief is not None:
        print("\n".join(brief.splitlines()[:40]))
    else:
        print(texto)
