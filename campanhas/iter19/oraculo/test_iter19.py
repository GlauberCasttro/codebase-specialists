"""ORÁCULO campanha-iter19 — B-14 (0.11.0): estado legível em JSON, chaves em inglês, amend refletido no arquivo,
`cs-state show` e migração automática no upgrade.

Mapa CA → teste e critérios em ESPEC.md (mesma pasta). Resumo:

  CA-01  todo arquivo de estado de entidade (épico, sprint, feature, story, task, sessão) e a projeção são `.json`
         que `json.loads` aceita, indentados com 2 espaços, um item de lista por linha, chaves na ordem de leitura,
         `_generated_by` como campo; reserializar dá os mesmos bytes; o validate continua verde.
  CA-02  nenhuma chave de entidade em português (mapa POR CAMINHO: `para` da story → `so_that`, `para` do histórico
         → `to`); o motor novo lê um alvo com chaves pt (sem migrar) e grava em inglês.
  CA-03  `cs-state amend` de acceptance_criteria em task INICIADA chega ao arquivo, ao `history` (antes, depois,
         motivo) e não volta no reopen; em task NÃO iniciada é aceito e refletido.
  CA-04  `cs-state show <id|alias>` imprime Markdown (título, agente, escopo, critérios, estado, histórico) sem
         escrever nada; id inexistente sai com erro citando o id.
  CA-05  alvo 0.10.1 REAL (skill extraída por `git archive` do commit da 0.10.1; ≥ 30 eventos; itens em backlog/,
         state/ e archive/): `cs.py upgrade` (plano) não escreve e lista a 0.11.0; `upgrade --apply` converte todo
         `.json5` de estado de entidade em `.json` por UM evento encadeado novo, sem reescrever os antigos; validate e
         cadeia íntegros; 2ª execução não muda nada; o commit passa no pre-commit sem --no-verify.
  CA-06  logs JSONL, config JSON5, memória do cs-mem e chaves do mandato M5 iguais; VERSION 0.11.0 e a migração
         `to: "0.11.0"` no catálogo.

Comportamento observável: CLIs reais em subprocesso (`cs.py`, `.swarm/harness/state.py|session.py|mem.py|auto.py`
instalados no alvo), hook git real, repos git temporários, bytes dos arquivos e `json.loads`. Nada de mock.
Skill sob teste: $CS_SKILL_DIR, senão a raiz deste projeto. Skill 0.10.1 (versão antiga do alvo): $CS_OLD_SKILL_DIR,
senão `git archive 97a1718` deste repositório. Python 3.9+, unittest puro, só stdlib.
Rodar (desta pasta): python3 -m unittest -v test_iter19
"""
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.realpath(os.path.join(HERE, "..", "..", ".."))
SKILL = os.path.realpath(os.environ.get("CS_SKILL_DIR") or PROJECT)
SCRIPTS = os.path.join(SKILL, "scripts")
OLD_COMMIT = "97a1718"          # "0.10.1: pre-commit aceita o resultado do próprio upgrade (B-13, iter20)"
OLD_VERSION = "0.10.1"
NEW_VERSION = "0.11.0"

GIT_ENV = {"GIT_AUTHOR_NAME": "Ana", "GIT_AUTHOR_EMAIL": "ana@x", "GIT_COMMITTER_NAME": "Ana",
           "GIT_COMMITTER_EMAIL": "ana@x"}
SD = ".swarm"
ZONES = ("backlog", "state", "archive")
GENESIS = "0" * 64

VERIFY = "python3 -m unittest tests.test_ok"
ACEITE = "python3 -m unittest accept.test_accept"          # vermelho: a feature tem o que entregar
G1 = "Dado pedido Quando aplico Então desconta"
G2 = "Dado cupom vencido Quando aplico Então recusa"
G3 = "Dado cupom duplo Quando aplico Então aplica um"
C1 = "AC-1|%s|tests.test_ok" % G1
C2 = "AC-2|%s|tests.test_ok" % G2
CREATED_RE = re.compile(r"^criad[oa] (\S+) em (\S+)\s*$", re.M)

# Chaves em português que o B-14 traduz (E2 F3). Não inclui as do mandato M5 (ficam pt, fora desta varredura).
PT_KEYS = {"tipo", "como", "quero", "para", "criterios", "teste", "reproducao", "motivo", "aceite", "epico",
           "objetivo", "metrica", "meta", "reaberta", "reaberturas", "historico", "acao", "de", "entregue",
           "devolvido", "metricas", "origem", "tentativas", "status_m2", "blocos", "titulo", "linhas"}
# Ordem de leitura (CA-01): as presentes aparecem nesta ordem e ANTES de qualquer outra chave; history por último.
READ_ORDER = ["id", "kind", "type", "title", "agent", "allowed_paths", "protected_paths", "as_a", "i_want", "so_that",
              "acceptance_criteria"]
ENTITY_KINDS = ("epico", "sprint", "feature", "story", "task")

_TMP = {}


# ================================================================================================ infraestrutura
def _env(extra=None):
    e = dict(os.environ)
    for k in ("CLAUDE_PROJECT_DIR", "CS_ACTOR", "CS_GUARD_OFF", "CS_ROOT", "CS_SKILL_VERSION_FILE",
              "CS_MIGRATIONS_FILE", "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        e.pop(k, None)
    e.update(GIT_ENV)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    e.update(extra or {})
    return e


def _run(argv, cwd, timeout=900):
    p = subprocess.run(argv, cwd=cwd, env=_env(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def git(root, *args):
    code, out, err = _run(["git", "-C", root] + list(args), root)
    if code != 0:
        raise AssertionError("git %s: %s%s" % (" ".join(args), out, err))
    return out


def cs(skill, target, *args):
    return _run([sys.executable, os.path.join(skill, "scripts", "cs.py"), "--target", target] + list(args), target)


def cs_ok(skill, target, *args):
    code, out, err = cs(skill, target, *args)
    if code != 0:
        raise AssertionError("cs.py %s → %d\n%s\n%s" % (" ".join(args), code, out[-3000:], err[-3000:]))
    return out


def tool(root, name, *args, actor=None):
    """CLI do motor INSTALADO no alvo (.swarm/harness/<name>.py) — o caminho oficial do alvo."""
    argv = [sys.executable, os.path.join(root, SD, "harness", name + ".py"), "--root", root]
    if actor:
        argv += ["--actor", actor]
    return _run(argv + list(args), root)


def st(root, *args, actor=None):
    return tool(root, "state", *args, actor=actor)


def st_ok(root, *args, actor=None):
    code, out, err = st(root, *args, actor=actor)
    if code != 0:
        raise AssertionError("cs-state %s → %d\n%s%s" % (" ".join(args), code, out[-3000:], err[-3000:]))
    return out


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


def json5io():
    if SCRIPTS not in sys.path:
        sys.path.insert(0, SCRIPTS)
    from cslib import json5io as j
    return j


def load_any(path):
    """Leitura TOLERANTE (JSON ou JSON5): usada onde o CA não é o formato, para o teste falhar pelo motivo certo."""
    txt = read_text(path)
    try:
        return json.loads(txt)
    except ValueError:
        return json5io().loads(txt)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def _base_tmp():
    if "base" not in _TMP:
        _TMP["base"] = os.path.realpath(tempfile.mkdtemp(prefix="oraculo-iter19-"))
    return _TMP["base"]


def tearDownModule():
    if "base" in _TMP:
        shutil.rmtree(_TMP["base"], ignore_errors=True)


def new_dir(name):
    _TMP["n"] = _TMP.get("n", 0) + 1
    return os.path.join(_base_tmp(), "%s-%d" % (name, _TMP["n"]))


def copy_target(tpl, name):
    d = new_dir(name)
    shutil.copytree(tpl, d, symlinks=True)
    return d


# ---------------------------------------------------------------------------------------------- leitura do estado
def entity_files(root, include_sessions=True):
    """Arquivos de estado de entidade nas zonas (relativos a .swarm/): itens da árvore + carimbos de sessão.
    Fora: logs (*.jsonl), INDEX/markdown, memória do cs-mem (state/memory/) e visões do mandato (mandatos/)."""
    out = []
    for z in ZONES:
        base = os.path.join(root, SD, z)
        for dp, dns, fns in os.walk(base):
            rel_dp = os.path.relpath(dp, os.path.join(root, SD)).replace(os.sep, "/")
            if rel_dp.startswith("state/memory") or "/mandatos" in "/" + rel_dp:
                dns[:] = []
                continue
            for f in fns:
                if f.endswith(".jsonl") or f.endswith(".md") or f.startswith("."):
                    continue
                rel = rel_dp + "/" + f
                if not include_sessions and rel.startswith("state/sessoes/"):
                    continue
                out.append(rel)
    return sorted(out)


def item_files(root):
    return [r for r in entity_files(root, include_sessions=False)]


def sd_path(root, rel):
    return os.path.join(root, SD, rel)


def find_path(root, ident):
    """Caminho (relativo ao alvo) do arquivo do item, pelo `cs-state find` do motor do alvo."""
    out = st_ok(root, "find", ident)
    for ln in out.splitlines():
        m = re.match(r"^(\S+) \[[^\]]*\] .* — (\S+)\s*$", ln)
        if m and m.group(1) == ident:
            return m.group(2)
    raise AssertionError("cs-state find %s não achou o item:\n%s" % (ident, out))


def item(root, ident):
    return load_any(os.path.join(root, find_path(root, ident)))


def walk_keys(obj, path=""):
    """(caminho, chave) de todas as chaves de dicionário, recursivo."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield path, k
            for x in walk_keys(v, path + "." + k):
                yield x
    elif isinstance(obj, list):
        for v in obj:
            for x in walk_keys(v, path + "[]"):
                yield x


def crit_ids(d):
    return [c.get("id") for c in (d.get("acceptance_criteria") or d.get("criterios") or [])]


def history(d):
    return d.get("history") or d.get("historico") or []


def action(h):
    return h.get("action") or h.get("acao")


def snapshot(root, skip=(".git/",)):
    snap = {}
    for dp, dns, fns in os.walk(root):
        for f in fns:
            full = os.path.join(dp, f)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if any(rel.startswith(s) for s in skip) or os.path.islink(full):
                continue
            snap[rel] = sha(read_bytes(full))
    return snap


def chain_errors(root):
    """Confere a cadeia de events.jsonl por fora do motor: seq = índice, prev = sha256 da linha anterior."""
    raw = [ln for ln in read_bytes(sd_path(root, "events.jsonl")).split(b"\n") if ln.strip()]
    errs, prev = [], GENESIS
    for i, ln in enumerate(raw):
        rec = json.loads(ln.decode("utf-8"))
        if rec.get("seq") != i:
            errs.append("linha %d: seq=%r" % (i, rec.get("seq")))
        if rec.get("prev") != prev:
            errs.append("linha %d: prev quebrado" % i)
        prev = sha(ln)
    return errs, len(raw)


def validate(root):
    code, out, err = st(root, "validate")
    return code, out + err


# ================================================================================================ fixtures
def old_skill():
    """A skill 0.10.1 real: $CS_OLD_SKILL_DIR ou `git archive` do commit da 0.10.1 deste projeto (sem escrever no repo)."""
    if "old" in _TMP:
        return _TMP["old"]
    d = os.environ.get("CS_OLD_SKILL_DIR")
    if not d:
        d = os.path.join(_base_tmp(), "skill-0.10.1")
        p = subprocess.run(["git", "-C", PROJECT, "archive", "--format=tar", OLD_COMMIT], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=300)
        if p.returncode != 0:
            raise AssertionError("não consegui extrair a skill 0.10.1 (git archive %s em %s): %s — defina "
                                 "$CS_OLD_SKILL_DIR" % (OLD_COMMIT, PROJECT, p.stderr.decode()))
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


def commit_all(root, msg):
    """`git add -A` + commit SEM --no-verify, com o hook do alvo (hooksPath explícito)."""
    git(root, "add", "-A")
    if not git(root, "diff", "--cached", "--name-only").strip():
        return
    code, out, err = _run(["git", "-C", root, "-c", "core.hooksPath=" + os.path.join(root, ".git", "hooks"),
                           "commit", "-q", "-m", msg], root)
    if code != 0:
        raise AssertionError("fixture: o pre-commit barrou %r:\n%s%s" % (msg, out[-3000:], err[-3000:]))


def make_target(skill, dest):
    """Repo da fixture do emit (time: dev-billing, dev-web, reviewer, qa) + testes próprios; init + harness install
    + emit pela skill dada; tudo commitado; depois o pre-commit ligado (`harness install --git-hook`)."""
    code = ("import sys; sys.dont_write_bytecode=True; sys.path.insert(0, %r); sys.path.insert(0, %r);"
            "import fixture; print(fixture.make_repo())"
            % (os.path.join(skill, "scripts"), os.path.join(skill, "scripts", "emit", "tests")))
    rc, out, err = _run([sys.executable, "-c", code], _base_tmp())
    if rc != 0:
        raise AssertionError("fixture do emit: %s%s" % (out, err))
    shutil.rmtree(dest, ignore_errors=True)
    shutil.move(out.strip().splitlines()[-1], dest)
    write(dest, "tests/__init__.py", "")
    write(dest, "tests/test_ok.py", "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n"
                                    "        self.assertTrue(True)\n")
    write(dest, "accept/__init__.py", "")
    write(dest, "accept/test_accept.py", "import os\nimport unittest\n\n\nclass A(unittest.TestCase):\n"
                                         "    def test_feature(self):\n"
                                         "        self.assertTrue(os.path.exists('src/billing/cupom.py'))\n")
    write(dest, "spec/feature.md", "# Cupom no checkout\n")
    git(dest, "init", "-q")
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "init")
    cs_ok(skill, dest, "init", "--platforms", "claude-code")
    cs_ok(skill, dest, "harness", "install", "--allow-outside")
    cs_ok(skill, dest, "emit", "--allow-outside")
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "gerado pela skill")
    cs_ok(skill, dest, "harness", "install", "--allow-outside", "--git-hook")
    hook = os.path.join(dest, ".git", "hooks", "pre-commit")
    if not os.path.islink(hook) or not os.readlink(hook).endswith("cs-precommit"):
        raise AssertionError("pre-commit não ficou ligado ao cs-precommit")
    return dest


def _new(root, *args):
    out = st_ok(root, "new", *args)
    got = CREATED_RE.findall(out)
    if not got:
        raise AssertionError("`new` deveria imprimir `criado <ID> em <path>`: %r" % out)
    return got


def _us(root, parent, title, path, crits=(C1,), agent="dev-billing"):
    a = ["task", "--tipo", "US", "--agent", agent, "--title", title] + list(parent) + [
        "--allowed-path", path, "--verify-cmd", VERIFY, "--como", "cliente", "--quero", "cupom", "--para", "pagar menos"]
    for c in crits:
        a += ["--criterio", c]
    return _new(root, *a)[0][0]


def pipeline(root, tid, rel_file, agent="dev-billing", close=True, commit=True):
    """M2 inteira, sem atalho: dispatch (manual) → submit → verify → review → accept [→ commit → close]."""
    st_ok(root, "dispatch", tid, "--manual", "--model", "sonnet")
    write(root, rel_file, "# entregue por %s\n" % tid, mode="a")
    st_ok(root, "submit", tid, "--files-changed", rel_file, "--check", "unittest: OK", "--risk", "nenhum",
          "--handoff-notes", "ok", actor=agent)
    st_ok(root, "verify", tid)
    st_ok(root, "review", tid, "--by", "reviewer", "--verdict", "PASS", "--findings", "conferido: teste verde")
    st_ok(root, "accept", tid)
    if commit:
        commit_all(root, "entrega %s" % tid)
    if close:
        st_ok(root, "close", tid, "--summary", "entregue")


def populate(root):
    """Estado REALISTA pelo motor instalado no alvo (≥ 30 eventos; itens em backlog/, state/ e archive/).
    Devolve os ids. Tudo commitado pelo pre-commit do alvo (sem --no-verify)."""
    ids = {}
    st_ok(root, "init")
    _new(root, "epico", "--title", "Cobrança", "--objetivo", "cobrar certo", "--metrica", "0 erros")
    _new(root, "sprint", "--meta", "entregar cupom", "--epico", "EPC-001")
    st_ok(root, "start", "EPC-001")
    st_ok(root, "start", "SPR-001")
    _new(root, "feature", "--title", "Cupom", "--sprint", "SPR-001", "--aceite", ACEITE)
    st_ok(root, "start", "FEA-001")
    ids["started"] = _us(root, ["--feature", "FEA-001"], "Aplicar cupom", "src/billing/coupons.py", crits=(C1, C2))
    st_ok(root, "start", ids["started"])                          # iniciada com AC-1 e AC-2 (alvo do amend)
    ids["closed"] = _us(root, ["--feature", "FEA-001"], "Total com cupom", "src/billing/total.py")
    st_ok(root, "start", ids["closed"])
    pipeline(root, ids["closed"], "src/billing/total.py")         # fechada → archive/ (mesma árvore)
    got = _new(root, "story", "--tipo", "US", "--title", "Cupom na tela", "--feature", "FEA-001",
               "--agents", "dev-billing", "--agents", "dev-web", "--como", "cliente", "--quero", "ver o cupom",
               "--para", "confiar no total", "--criterio", C1, "--verify-cmd", VERIFY)
    ids["story"], ids["story_task"] = got[0][0], got[1][0]
    st_ok(root, "amend", ids["story_task"], "--field", "allowed_paths", "--after", '["src/billing/cupom_tela.py"]',
          "--reason", "estreitar o escopo (DoR)")                 # task não iniciada: emenda o item (R7, iter18)
    ids["avulsa"] = _us(root, ["--avulsa"], "Ajusta boleto", "src/billing/boleto.py")
    st_ok(root, "start", ids["avulsa"])
    pipeline(root, ids["avulsa"], "src/billing/boleto.py")        # avulsa fechada → archive/tasks/<ano>/<mês>/
    ids["reopened"] = _us(root, ["--avulsa"], "Ajusta frete", "src/billing/money.py")
    st_ok(root, "start", ids["reopened"])
    pipeline(root, ids["reopened"], "src/billing/money.py")
    st_ok(root, "reopen", ids["reopened"], "--reason", "regrediu em producao")
    ids["bug"] = _new(root, "task", "--tipo", "BUG", "--agent", "dev-web", "--title", "Rota quebra", "--backlog",
                      "--allowed-path", "src/web/app.py", "--verify-cmd", VERIFY, "--reproducao", "accept.test_accept")[0][0]
    ids["sprint_task"] = _us(root, ["--sprint", "SPR-001"], "Cupom do sprint", "src/billing/coupons.py")
    chore = _new(root, "task", "--tipo", "CHORE", "--agent", "dev-billing", "--title", "Limpa money", "--backlog",
                 "--allowed-path", "src/billing/money.py", "--verify-cmd", VERIFY, "--motivo", "manutencao tecnica")[0][0]
    out = st_ok(root, "plan", chore, "--sprint", "SPR-001")
    m = re.search(r"\(novo id (\S+)\)", out)
    if not m:
        raise AssertionError("plan deveria imprimir o novo id: %r" % out)
    ids["chore_alias"], ids["chore"] = chore, m.group(1)
    _new(root, "feature", "--title", "Boleto novo", "--backlog", "--aceite", ACEITE)
    st_ok(root, "move", "FEA-002", "--to", "SPR-001")              # histórico com `para` (→ `to`)
    ids["moved_feature"] = "FEA-002"
    code, out, err = tool(root, "mem", "add", "--agent", "dev-billing", "--rule", "nunca usar float para dinheiro")
    if code != 0:
        raise AssertionError("cs-mem add: %s%s" % (out, err))
    code, out, err = tool(root, "auto", "propose", "--feature", "FEA-001", "--spec", "spec/feature.md", "--objetivo",
                          "Cupom no checkout", "--nos", "2", "--regressao", VERIFY, "--criterio",
                          "AC-1|%s|accept.test_accept" % G1)
    if code != 0 or "MAN-001" not in out:
        raise AssertionError("cs-auto propose: %s%s" % (out, err))
    code, out, err = tool(root, "session", "save")
    if code != 0:
        raise AssertionError("cs-session save: %s%s" % (out, err))
    commit_all(root, "estado")
    if git(root, "status", "--porcelain", "--untracked-files=all").strip():
        raise AssertionError("fixture: alvo não ficou limpo:\n" + git(root, "status", "--porcelain"))
    errs, n = chain_errors(root)
    if errs or n < 30:
        raise AssertionError("fixture: cadeia %s, %d eventos (precisa ≥ 30)" % (errs, n))
    zones = {r.split("/", 1)[0] for r in item_files(root)}
    if zones != set(ZONES):
        raise AssertionError("fixture: itens só em %s" % sorted(zones))
    code, out = validate(root)
    if code != 0:
        raise AssertionError("fixture: validate reprovou:\n" + out)
    return ids


def template(which):
    """'new' = alvo gerado e povoado pela skill SOB TESTE; 'old' = pela skill 0.10.1 real. Construído 1 vez."""
    key = "tpl-" + which
    if key not in _TMP:
        skill = SKILL if which == "new" else old_skill()
        d = make_target(skill, os.path.join(_base_tmp(), "alvo-" + which))
        _TMP[key] = (d, populate(d))
    return _TMP[key]


def applied():
    """Cópia do alvo 0.10.1 com o retrato ANTES, o plano e o `upgrade --apply` da skill sob teste (1 vez)."""
    if "applied" in _TMP:
        return _TMP["applied"]
    tpl, ids = template("old")
    root = copy_target(tpl, "aplicado")
    r = {"root": root, "ids": ids}
    r["entities_before"] = entity_files(root)
    r["items_before"] = item_files(root)
    r["data_before"] = {p: load_any(sd_path(root, p)) for p in r["entities_before"]}
    r["text_before"] = {p: read_text(sd_path(root, p)) for p in r["entities_before"]}
    r["events_before"] = read_bytes(sd_path(root, "events.jsonl"))
    r["validate_before"] = validate(root)
    r["chain_before"] = chain_errors(root)
    r["snap_before"] = snapshot(root)
    r["jsonl_before"] = {k: read_bytes(os.path.join(root, k)) for k in r["snap_before"]
                         if k.endswith(".jsonl") and not k.startswith(SD + "/backups/")}
    r["mem_before"] = read_bytes(sd_path(root, "state/memory/agents/dev-billing.json5"))
    r["mandato_before"] = mandato_data(root)
    r["team_before"] = read_bytes(sd_path(root, "team.json5"))
    r["plan"] = cs(SKILL, root, "upgrade")
    r["snap_after_plan"] = snapshot(root)
    r["apply"] = cs(SKILL, root, "upgrade", "--apply", "--allow-outside")
    _TMP["applied"] = r
    return r


def mandato_data(root):
    d = sd_path(root, "state/mandatos/MAN-001")
    files = [f for f in sorted(os.listdir(d)) if re.match(r"^mandato\.json5?$", f)] if os.path.isdir(d) else []
    if len(files) != 1:
        raise AssertionError("visão do mandato MAN-001: esperado 1 arquivo mandato.json[5], veio %s" % files)
    return load_any(os.path.join(d, files[0]))


def json_twin(rel):
    return rel[:-1] if rel.endswith(".json5") else rel


# ================================================================================================ asserts comuns
class Base(unittest.TestCase):
    maxDiff = 4000

    def assert_strict_json(self, root, rel):
        p = sd_path(root, rel)
        self.assertTrue(rel.endswith(".json") and not rel.endswith(".json5"), "%s: estado de entidade deve ser .json" % rel)
        txt = read_text(p)
        try:
            d = json.loads(txt)
        except ValueError as e:
            self.fail("%s: json.loads recusa (%s):\n%s" % (rel, e, txt[:400]))
        return txt, d

    def assert_layout(self, rel, txt, d):
        """indent 2, um item de lista por linha e mesmos bytes ao reserializar (ponto fixo do json.dumps)."""
        body = txt[:-1] if txt.endswith("\n") else txt
        ok = [json.dumps(d, indent=2, ensure_ascii=False), json.dumps(d, indent=2, ensure_ascii=True)]
        self.assertIn(body, ok, "%s: o arquivo não é o JSON indentado com 2 espaços (um item por linha) do próprio "
                                "conteúdo — reserializar daria outros bytes:\n%s" % (rel, txt[:600]))

    def assert_order(self, rel, d):
        keys = [k for k in d if k != "_generated_by"]
        self.assertTrue(keys, "%s: entidade vazia" % rel)
        self.assertEqual(keys[0], "id", "%s: a primeira chave deve ser id: %s" % (rel, keys))
        known = [k for k in keys if k in READ_ORDER]
        self.assertEqual(known, [k for k in READ_ORDER if k in known], "%s: ordem de leitura: %s" % (rel, keys))
        self.assertEqual(keys[:len(known)], known, "%s: %s devem vir antes das demais chaves: %s"
                         % (rel, known, keys))
        if "history" in keys:
            self.assertEqual(keys[-1], "history", "%s: history por último: %s" % (rel, keys))

    def assert_no_pt(self, rel, d):
        bad = sorted({"%s.%s" % (p, k) for p, k in walk_keys(d) if k in PT_KEYS})
        self.assertEqual(bad, [], "%s: chaves em português: %s" % (rel, bad))


# ================================================================================================ CA-01
class TestCA01(Base):
    """JSON padrão, em ordem de leitura, indent 2, `_generated_by`, mesmos bytes; validate verde."""

    @classmethod
    def setUpClass(cls):
        tpl, cls.ids = template("new")
        cls.root = tpl

    def test_ca01_entidades_e_sessao_sao_json(self):
        files = entity_files(self.root)
        self.assertGreaterEqual(len(files), 13, "fixture: arquivos de entidade %s" % files)
        bad = [r for r in files if not r.endswith(".json")]
        self.assertEqual(bad, [], "estado de entidade fora do .json: %s" % bad)
        for rel in files:
            self.assert_strict_json(self.root, rel)
        sess = [r for r in files if r.startswith("state/sessoes/")]
        self.assertTrue(sess, "o carimbo de sessão deve estar em state/sessoes/*.json")
        kinds = {load_any(sd_path(self.root, r)).get("kind") for r in files}
        for k in ENTITY_KINDS:
            self.assertIn(k, kinds, "fixture sem %s" % k)

    def test_ca01_indent_2_um_item_por_linha_mesmos_bytes(self):
        for rel in entity_files(self.root):
            txt, d = self.assert_strict_json(self.root, rel)
            self.assert_layout(rel, txt, d)

    def test_ca01_ordem_de_leitura_history_por_ultimo(self):
        for rel in item_files(self.root):
            txt, d = self.assert_strict_json(self.root, rel)
            self.assert_order(rel, d)
        t = self.assert_strict_json(self.root, find_path(self.root, self.ids["started"])[len(SD) + 1:])[1]
        keys = [k for k in t if k != "_generated_by"]
        for a, b in (("acceptance_criteria", "created_at"), ("acceptance_criteria", "started_at"),
                     ("so_that", "acceptance_criteria"), ("title", "agent")):
            self.assertLess(keys.index(a), keys.index(b), "task iniciada: %s antes de %s: %s" % (a, b, keys))

    def test_ca01_generated_by_e_campo(self):
        for rel in entity_files(self.root):
            txt, d = self.assert_strict_json(self.root, rel)
            self.assertIsInstance(d.get("_generated_by"), str, "%s: falta o campo _generated_by" % rel)
            self.assertTrue(d["_generated_by"].strip(), rel)
            self.assertFalse(txt.lstrip().startswith("//"), "%s: comentário de cabeçalho não é JSON" % rel)

    def test_ca01_projecao_json(self):
        eng = os.path.join(self.root, SD, ".engine")
        self.assertFalse(os.path.exists(os.path.join(eng, "projection.json5")), "projeção ainda em .json5")
        rel = ".engine/projection.json"
        self.assertTrue(os.path.isfile(os.path.join(eng, "projection.json")), "falta %s" % rel)
        txt, d = self.assert_strict_json(self.root, rel)
        self.assert_layout(rel, txt, d)

    def test_ca01_gravacoes_seguintes_sao_json(self):
        r = copy_target(self.root, "ca01-ops")
        st_ok(r, "start", self.ids["story_task"])
        st_ok(r, "new", "task", "--tipo", "CHORE", "--agent", "qa", "--title", "Mais testes", "--backlog",
              "--allowed-path", "tests/test_mais.py", "--verify-cmd", VERIFY, "--motivo", "cobertura")
        code, out, err = tool(r, "session", "save")
        self.assertEqual(code, 0, out + err)
        for rel in entity_files(r):
            txt, d = self.assert_strict_json(r, rel)
            self.assert_layout(rel, txt, d)
        self.assertEqual(validate(r)[0], 0, validate(r)[1])

    def test_ca01_validate_continua_verde(self):
        code, out = validate(self.root)
        self.assertEqual(code, 0, out)
        r = copy_target(self.root, "ca01-val")
        st_ok(r, "start", self.ids["story_task"])
        code, out = validate(r)
        self.assertEqual(code, 0, "validate depois de gravar: %s" % out)


# ================================================================================================ CA-02
class TestCA02(Base):
    """Chaves em inglês (mapa por caminho); leitura das antigas em pt."""

    @classmethod
    def setUpClass(cls):
        cls.root, cls.ids = template("new")

    def get(self, ident):
        return item(self.root, ident)

    def test_ca02_nenhuma_chave_pt_nas_entidades(self):
        files = entity_files(self.root)
        self.assertGreaterEqual(len(files), 13)
        for rel in files:
            self.assert_no_pt(rel, load_any(sd_path(self.root, rel)))

    def test_ca02_task_story_com_chaves_em_ingles(self):
        t = self.get(self.ids["started"])
        self.assertEqual(t.get("type"), "US", "tipo → type: %s" % sorted(t))
        self.assertEqual((t.get("as_a"), t.get("i_want"), t.get("so_that")), ("cliente", "cupom", "pagar menos"))
        ac = t.get("acceptance_criteria")
        self.assertEqual([c.get("id") for c in ac or []], ["AC-1", "AC-2"], "criterios → acceptance_criteria")
        self.assertEqual(ac[1], {"id": "AC-2", "gherkin": G2, "test": "tests.test_ok"}, "teste → test")
        self.assertTrue(all(action(h) and "action" in h for h in t.get("history") or [{}]), "historico/acao → history/action")
        s = self.get(self.ids["story"])
        self.assertEqual(s.get("so_that"), "confiar no total", "`para` da story → so_that: %s" % sorted(s))
        self.assertNotIn("to", s, "`para` da story NÃO vira `to`")
        self.assertEqual(self.get(self.ids["bug"]).get("failing_test"), "accept.test_accept", "reproducao → failing_test")
        self.assertEqual(self.get(self.ids["chore"]).get("reason"), "manutencao tecnica", "motivo → reason")

    def test_ca02_historico_para_vira_to_por_caminho(self):
        f = self.get(self.ids["moved_feature"])
        moves = [h for h in f.get("history") or [] if h.get("action") == "move"]
        self.assertTrue(moves, "feature movida deve ter history[].action == move: %s" % f)
        self.assertEqual(moves[-1].get("to"), "SPR-001", "`para` do histórico → to: %s" % moves[-1])
        self.assertNotIn("so_that", moves[-1], "`para` do histórico NÃO vira so_that")
        self.assertEqual(f.get("acceptance_cmd"), ACEITE, "aceite → acceptance_cmd")
        planned = self.get(self.ids["chore"])
        froms = [h.get("from") for h in planned.get("history") or []]
        self.assertIn(self.ids["chore_alias"], froms, "`de` do histórico → from: %s" % planned.get("history"))

    def test_ca02_epico_sprint_fechada_reaberta_sessao(self):
        e = self.get("EPC-001")
        self.assertEqual((e.get("objective"), e.get("metric")), ("cobrar certo", "0 erros"))
        s = self.get("SPR-001")
        self.assertEqual((s.get("goal"), s.get("epic")), ("entregar cupom", "EPC-001"))
        c = self.get(self.ids["closed"]).get("closed") or {}
        for k in ("delivered", "returned", "metrics"):
            self.assertIn(k, c, "closed.%s: %s" % (k, sorted(c)))
        self.assertIn("attempts", c.get("metrics") or {}, "metricas.tentativas → metrics.attempts")
        self.assertIn("m2_status", c.get("metrics") or {}, "metricas.status_m2 → metrics.m2_status")
        r = self.get(self.ids["reopened"])
        self.assertEqual(r.get("reopened"), 1, "reaberta → reopened")
        self.assertEqual(len(r.get("reopenings") or []), 1, "reaberturas → reopenings")
        sess = [x for x in entity_files(self.root) if x.startswith("state/sessoes/")]
        self.assertTrue(sess)
        d = load_any(sd_path(self.root, sess[-1]))
        self.assertTrue(d.get("blocks"), "blocos → blocks")
        self.assertTrue(all("title" in b and "lines" in b for b in d["blocks"]), "titulo/linhas → title/lines")

    def _old_with_new_engine(self):
        tpl, ids = template("old")
        r = copy_target(tpl, "ca02-pt")
        cs_ok(SKILL, r, "harness", "install", "--allow-outside")
        return r, ids

    def test_ca02_le_chaves_pt_e_grava_em_ingles(self):
        r, ids = self._old_with_new_engine()
        st_ok(r, "start", ids["story_task"])
        rel = find_path(r, ids["story_task"])
        d = load_any(os.path.join(r, rel))
        self.assert_no_pt(rel, d)
        self.assertEqual(d.get("type"), "US")
        self.assertEqual([(c.get("id"), c.get("gherkin"), c.get("test")) for c in d.get("acceptance_criteria") or []],
                         [("AC-1", G1, "tests.test_ok")], "o critério lido do arquivo pt deve chegar como novo: %s" % d)
        self.assertEqual(validate(r)[0], 0, validate(r)[1])

    def test_ca02_le_chaves_pt_brief_continua(self):
        r, ids = self._old_with_new_engine()
        st_ok(r, "start", ids["story_task"])
        out = st_ok(r, "brief", ids["story_task"])
        self.assertIn(G1, out, "o brief da task criada com chaves pt traz o critério")
        self.assertIn("src/billing", out)


# ================================================================================================ CA-03
AFTER_STARTED = json.dumps([{"id": "AC-1", "criterion": G1, "verified_by": "test:tests.test_ok"}], ensure_ascii=False)
AFTER_NOT_STARTED = json.dumps([{"id": "AC-1", "criterion": G1, "verified_by": "test:tests.test_ok"},
                                {"id": "AC-3", "criterion": G3, "verified_by": "test:tests.test_ok"}], ensure_ascii=False)
REASON = "AC-2 saiu do escopo (decisao da Ana)"


class TestCA03(Base):
    """`cs-state amend` refletido no arquivo da task (iniciada e não iniciada)."""

    def setUp(self):
        tpl, self.ids = template("new")
        self.root = copy_target(tpl, "ca03")
        self.addCleanup(shutil.rmtree, self.root, True)

    def amend_started(self):
        st_ok(self.root, "amend", self.ids["started"], "--field", "acceptance_criteria", "--after", AFTER_STARTED,
              "--reason", REASON)

    def test_ca03_amend_iniciada_some_do_arquivo(self):
        tid = self.ids["started"]
        self.assertEqual(crit_ids(item(self.root, tid)), ["AC-1", "AC-2"], "fixture: task iniciada com AC-1 e AC-2")
        self.amend_started()
        d = item(self.root, tid)
        self.assertEqual(crit_ids(d), ["AC-1"], "o arquivo da task deve deixar de listar o AC-2: %s" % crit_ids(d))
        self.assertNotIn(G2, json.dumps(d.get("acceptance_criteria") or d.get("criterios"), ensure_ascii=False))
        code, out = validate(self.root)
        self.assertEqual(code, 0, out)

    def test_ca03_amend_iniciada_historico_antes_depois_motivo(self):
        self.amend_started()
        h = [x for x in history(item(self.root, self.ids["started"])) if action(x) == "amend"]
        self.assertEqual(len(h), 1, "o history registra o amend: %s" % history(item(self.root, self.ids["started"])))
        h = h[0]
        self.assertEqual(h.get("reason"), REASON, "motivo no history: %s" % h)
        self.assertIn("before", h, h)
        self.assertIn("after", h, h)
        self.assertIn("AC-2", json.dumps(h["before"], ensure_ascii=False), "antes: com AC-2: %s" % h)
        self.assertNotIn("AC-2", json.dumps(h["after"], ensure_ascii=False), "depois: sem AC-2: %s" % h)
        self.assertIn("AC-1", json.dumps(h["after"], ensure_ascii=False), h)

    def test_ca03_reopen_nao_ressuscita_ac2(self):
        tid = self.ids["started"]
        self.amend_started()
        pipeline(self.root, tid, "src/billing/coupons.py", commit=False)
        st_ok(self.root, "reopen", tid, "--reason", "faltou caso de borda")
        self.assertNotIn("AC-2", crit_ids(item(self.root, tid)), "reopen: o arquivo não volta a ter o AC-2")
        st_ok(self.root, "start", tid)
        self.assertEqual(crit_ids(item(self.root, tid)), ["AC-1"], "restart: o arquivo não volta a ter o AC-2")
        out = st_ok(self.root, "brief", tid)
        self.assertNotIn(G2, out, "a nova M2 (brief) não ressuscita o AC-2")
        self.assertIn(G1, out)

    def test_ca03_amend_nao_iniciada_acceptance_criteria(self):
        tid = self.ids["sprint_task"]
        code, out, err = st(self.root, "amend", tid, "--field", "acceptance_criteria", "--after", AFTER_NOT_STARTED,
                            "--reason", "faltava o cupom duplo")
        self.assertEqual(code, 0, "amend de acceptance_criteria em task NÃO iniciada deve ser aceito:\n%s%s" % (out, err))
        d = item(self.root, tid)
        self.assertEqual(crit_ids(d), ["AC-1", "AC-3"], "refletido no arquivo: %s" % crit_ids(d))
        self.assertIn(G3, json.dumps(d, ensure_ascii=False))
        h = [x for x in history(d) if action(x) == "amend"]
        self.assertTrue(h and h[-1].get("reason") == "faltava o cupom duplo", history(d))
        st_ok(self.root, "start", tid)
        out = st_ok(self.root, "brief", tid)
        self.assertIn(G3, out, "o start usa o critério emendado")
        self.assertEqual(validate(self.root)[0], 0, validate(self.root)[1])

    def test_ca03_amend_allowed_paths_nao_iniciada_continua(self):
        tid = self.ids["sprint_task"]
        st_ok(self.root, "amend", tid, "--field", "allowed_paths", "--after",
              '["src/billing/coupons.py", "src/billing/extra.py"]', "--reason", "precisa do extra")
        self.assertIn("src/billing/extra.py", item(self.root, tid).get("allowed_paths") or [])

    def test_ca03_amend_campo_nao_espelhavel_continua(self):
        code, out, err = st(self.root, "amend", self.ids["started"], "--field", "goal", "--after", "cupom simples",
                            "--reason", "texto melhor")
        self.assertEqual(code, 0, "amend de campo só da M2 segue aceito: %s%s" % (out, err))
        self.assertEqual(validate(self.root)[0], 0, validate(self.root)[1])


# ================================================================================================ CA-04
class TestCA04(Base):
    """`cs-state show <id|alias>`: Markdown legível, sem escrever nada."""

    @classmethod
    def setUpClass(cls):
        tpl, cls.ids = template("new")
        cls.root = copy_target(tpl, "ca04")

    def show(self, ident):
        before = snapshot(self.root)
        code, out, err = st(self.root, "show", ident)
        self.assertEqual(snapshot(self.root), before, "`show %s` não pode escrever nada" % ident)
        return code, out, err

    def show_ok(self, ident):
        code, out, err = self.show(ident)
        self.assertEqual(code, 0, "`cs-state show %s` deveria passar: %s%s" % (ident, out, err))
        self.assertRegex(out, r"(?m)^#{1,3} ", "show imprime Markdown (título com #): %r" % out[:400])
        return out

    def test_ca04_show_task_iniciada(self):
        tid = self.ids["started"]
        out = self.show_ok(tid)
        self.assertRegex(out, r"(?m)^#{1,3} .*Aplicar cupom", "título")
        for s in (tid, "dev-billing", "src/billing/coupons.py", "AC-1", "AC-2", G1, G2):
            self.assertIn(s, out, "show: falta %r:\n%s" % (s, out))
        self.assertTrue("BRIEFED" in out or "READY" in out, "estado da task (M2):\n%s" % out)
        self.assertIn("start", out, "histórico resumido (ação start):\n%s" % out)

    def test_ca04_show_por_alias(self):
        out = self.show_ok(self.ids["chore_alias"])
        self.assertIn(self.ids["chore"], out, "o alias %s resolve para %s:\n%s" % (self.ids["chore_alias"],
                                                                                  self.ids["chore"], out))
        self.assertIn("Limpa money", out)

    def test_ca04_show_story_feature_e_arquivada(self):
        out = self.show_ok(self.ids["story"])
        self.assertIn("Cupom na tela", out)
        self.assertIn(G1, out, "story: critérios")
        out = self.show_ok("FEA-001")
        self.assertIn("Cupom", out)
        self.assertIn(ACEITE, out, "feature: comando de aceite")
        out = self.show_ok(self.ids["closed"])
        self.assertIn("Total com cupom", out)
        self.assertIn("archive", out.lower(), "item fechado: o estado mostra que está em archive/:\n%s" % out)

    def test_ca04_show_inexistente_sai_com_erro_citando_id(self):
        code, out, err = self.show("FEA-999/09")
        self.assertNotEqual(code, 0, "id inexistente deve sair com erro")
        self.assertIn("FEA-999/09", out + err, "o erro cita o id pedido:\n%s%s" % (out, err))


# ================================================================================================ CA-05
class TestCA05(Base):
    """Migração automática no upgrade de um alvo 0.10.1 realista."""

    @classmethod
    def setUpClass(cls):
        cls.r = applied()
        cls.root = cls.r["root"]

    def assert_applied(self):
        code, out, err = self.r["apply"]
        self.assertEqual(code, 0, "upgrade --apply falhou:\n%s%s" % (out[-3000:], err[-3000:]))
        left = [p for p in entity_files(self.root) if p.endswith(".json5")]
        self.assertEqual(left, [], "o apply deveria converter todo .json5 de estado de entidade: %s" % left)

    def test_ca05_alvo_realista_antes_continua(self):
        code, out = self.r["validate_before"]
        self.assertEqual(code, 0, "validate antes: %s" % out)
        errs, n = self.r["chain_before"]
        self.assertEqual(errs, [])
        self.assertGreaterEqual(n, 30)
        self.assertEqual({p.split("/", 1)[0] for p in self.r["items_before"]}, set(ZONES))
        self.assertTrue(all(p.endswith(".json5") for p in self.r["entities_before"]), "alvo 0.10.1 em .json5")

    def test_ca05_plano_nao_escreve_continua(self):
        code, out, err = self.r["plan"]
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.r["snap_after_plan"], self.r["snap_before"], "o plano (sem --apply) não escreve nada")

    def test_ca05_plano_lista_a_migracao_de_formato(self):
        code, out, err = self.r["plan"]
        self.assertIn("versão do alvo:  %s" % OLD_VERSION, out)
        self.assertRegex(out, r"(?m)^\s+0\.11\.0 — ", "o plano lista a migração 0.11.0:\n%s" % out)
        self.assertRegex(out, r"(?i)\bjson\b", "o plano diz que o estado vira JSON:\n%s" % out)

    def test_ca05_apply_converte_estado_para_json_ingles(self):
        self.assert_applied()
        for old in self.r["entities_before"]:
            new = json_twin(old)
            self.assertFalse(os.path.exists(sd_path(self.root, old)), "sobrou %s" % old)
            self.assertTrue(os.path.isfile(sd_path(self.root, new)), "%s → %s não existe" % (old, new))
            txt, d = self.assert_strict_json(self.root, new)
            self.assert_layout(new, txt, d)
            self.assert_no_pt(new, d)
            self.assertIn("_generated_by", d, new)
            o = self.r["data_before"][old]
            if o.get("kind") in ENTITY_KINDS:
                self.assert_order(new, d)
                self.assertEqual((d.get("id"), d.get("title"), d.get("kind")), (o.get("id"), o.get("title"), o.get("kind")))
                self.assertEqual(crit_ids(d), crit_ids(o), "%s: critérios preservados" % new)
                self.assertEqual(d.get("so_that"), o.get("para"), "%s: para → so_that" % new)
                self.assertGreaterEqual(len(d.get("history") or []), len(o.get("historico") or []), new)
                self.assertEqual(d.get("path"), json_twin(o.get("path")), "%s: path do item aponta o .json" % new)
        eng = sd_path(self.root, ".engine")
        self.assertFalse(os.path.exists(os.path.join(eng, "projection.json5")), "projeção ainda .json5")
        self.assertTrue(os.path.isfile(os.path.join(eng, "projection.json")), "projeção .json")
        json.loads(read_text(os.path.join(eng, "projection.json")))

    def test_ca05_um_evento_encadeado_novo_sem_reescrever(self):
        self.assert_applied()
        now = read_bytes(sd_path(self.root, "events.jsonl"))
        before = self.r["events_before"]
        self.assertTrue(now.startswith(before), "eventos antigos reescritos: a migração só ANEXA")
        new_lines = [ln.decode("utf-8") for ln in now[len(before):].split(b"\n") if ln.strip()]
        self.assertTrue(new_lines, "nenhum evento novo")
        maps = [ln for ln in new_lines
                if all(old in ln and ('%s"' % json_twin(old)) in ln for old in self.r["items_before"])]
        self.assertEqual(len(maps), 1, "UM evento novo traz o mapa de TODOS os caminhos .json5 → .json "
                                       "(%d eventos novos)" % len(new_lines))
        errs, n = chain_errors(self.root)
        self.assertEqual(errs, [], "cadeia íntegra depois")
        code, out = validate(self.root)
        self.assertEqual(code, 0, "validate depois: %s" % out)

    def test_ca05_segunda_execucao_nao_muda_nada(self):
        self.assert_applied()
        r = copy_target(self.root, "ca05-idem")
        self.addCleanup(shutil.rmtree, r, True)
        keep = lambda s: {k: v for k, v in s.items()
                          if k.startswith(SD + "/") and not k.startswith(SD + "/backups/")
                          and not k.endswith("harness-ledger.jsonl") and not k.startswith(SD + "/.engine/evidence")}
        before = keep(snapshot(r))
        code, out, err = cs(SKILL, r, "upgrade", "--apply", "--allow-outside")
        self.assertEqual(code, 0, out + err)
        after = keep(snapshot(r))
        diff = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
        self.assertEqual(diff, [], "2ª execução mudou: %s" % diff)
        code, out, err = cs(SKILL, r, "upgrade")
        self.assertNotRegex(out, r"(?m)^\s+0\.11\.0 — ", "migração já aplicada não volta ao plano")

    def test_ca05_commit_do_resultado_passa_no_pre_commit(self):
        self.assert_applied()
        r = copy_target(self.root, "ca05-commit")
        self.addCleanup(shutil.rmtree, r, True)
        git(r, "add", "-A")
        staged = git(r, "diff", "--cached", "--name-only").split()
        self.assertTrue(any(s.endswith(".json") and "/state/" in s for s in staged), "nada de estado staged")
        head = git(r, "rev-parse", "HEAD").strip()
        code, out, err = _run(["git", "-C", r, "-c", "core.hooksPath=" + os.path.join(r, ".git", "hooks"),
                               "commit", "-q", "-m", "upgrade 0.11.0"], r)
        self.assertEqual(code, 0, "o pre-commit deveria LIBERAR o resultado do upgrade:\n%s" % (out + err)[-4000:])
        self.assertNotEqual(git(r, "rev-parse", "HEAD").strip(), head)
        self.assertIn("validate", out + err, "o hook rodou")

    def test_ca05_json5_orfao_e_acusado(self):
        self.assert_applied()
        r = copy_target(self.root, "ca05-orfao")
        self.addCleanup(shutil.rmtree, r, True)
        old = self.r["items_before"][0]
        write(r, os.path.join(SD, old), self.r["text_before"][old])
        code, out = validate(r)
        self.assertNotEqual(code, 0, "um .json5 de estado que sobrou deve ser acusado pelo validate")
        self.assertIn(os.path.basename(old), out, out)

    def test_ca05_motor_opera_depois_da_migracao(self):
        self.assert_applied()
        r = copy_target(self.root, "ca05-ops")
        self.addCleanup(shutil.rmtree, r, True)
        tid = self.r["ids"]["story_task"]
        st_ok(r, "start", tid)
        rel = find_path(r, tid)
        self.assertTrue(rel.endswith(".json"), rel)
        d = json.loads(read_text(os.path.join(r, rel)))
        self.assertEqual(crit_ids(d), ["AC-1"])
        self.assertEqual([p for p in entity_files(r) if p.endswith(".json5")], [])
        self.assertEqual(validate(r)[0], 0, validate(r)[1])


# ================================================================================================ CA-06
class TestCA06(Base):
    """O que não muda continua igual; VERSION 0.11.0 e a migração no catálogo."""

    def catalog(self):
        return json5io().read(os.path.join(SKILL, "references", "migrations.json5"))

    def test_ca06_version(self):
        self.assertEqual(read_text(os.path.join(SKILL, "VERSION")).strip(), NEW_VERSION)

    def test_ca06_catalogo_tem_a_0110(self):
        m = self.catalog()
        self.assertEqual(m["version"], NEW_VERSION)
        tos = [x["to"] for x in m["migrations"]]
        self.assertEqual(tos[-1], NEW_VERSION, "a última migração é a 0.11.0")
        self.assertEqual(tos.count(NEW_VERSION), 1)
        self.assertEqual(tos.index(NEW_VERSION), tos.index(OLD_VERSION) + 1, "0.11.0 vem logo depois da 0.10.1")
        self.assertTrue(m["migrations"][-1].get("actions"), "a 0.11.0 tem ações")

    def test_ca06_catalogo_e_config_continuam_json5(self):
        self.assertTrue(os.path.isfile(os.path.join(SKILL, "references", "migrations.json5")))
        self.assertFalse(os.path.exists(os.path.join(SKILL, "references", "migrations.json")))
        root, _ = template("new")
        for rel in ("team.json5", "run.json5", "harness/config.json5", "harness/machines.json5",
                    "harness/routing.json5"):
            self.assertTrue(os.path.isfile(sd_path(root, rel)), "config continua JSON5: %s" % rel)
            self.assertFalse(os.path.exists(sd_path(root, rel[:-1])), "config não ganha gêmeo .json: %s" % rel)
            json5io().read(sd_path(root, rel))

    def test_ca06_eventos_continuam_jsonl_canonico(self):
        root, _ = template("new")
        for i, ln in enumerate(read_text(sd_path(root, "events.jsonl")).splitlines()):
            rec = json.loads(ln)
            self.assertEqual(ln, json.dumps(rec, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
                             "events.jsonl linha %d deixou de ser canônica (sort_keys)" % i)

    def test_ca06_memoria_e_mandato_novos_continuam(self):
        root, _ = template("new")
        p = sd_path(root, "state/memory/agents/dev-billing.json5")
        self.assertTrue(os.path.isfile(p), "memória do cs-mem continua .json5")
        d = mandato_data(root)
        for k in ("alvo", "criterios", "objetivo", "orcamento", "regressao"):
            self.assertIn(k, d, "chaves do mandato M5 continuam em pt: %s" % sorted(d))

    def test_ca06_upgrade_logs_jsonl_continuam_iguais(self):
        r = applied()
        self.assertEqual(r["apply"][0], 0, r["apply"][1] + r["apply"][2])
        for rel, b in sorted(r["jsonl_before"].items()):
            p = os.path.join(r["root"], rel)
            self.assertTrue(os.path.isfile(p), "log sumiu: %s" % rel)
            self.assertTrue(read_bytes(p).startswith(b), "log reescrito (só anexar): %s" % rel)
        for rel in (SD + "/memory/episodes.jsonl",):           # memória do cs-mem: nem anexa
            if rel in r["jsonl_before"]:
                self.assertEqual(read_bytes(os.path.join(r["root"], rel)), r["jsonl_before"][rel], rel)

    def test_ca06_upgrade_config_memoria_mandato_continuam(self):
        r = applied()
        self.assertEqual(r["apply"][0], 0, r["apply"][1] + r["apply"][2])
        root = r["root"]
        self.assertEqual(read_bytes(sd_path(root, "team.json5")), r["team_before"], "team.json5 igual")
        for rel in ("run.json5", "harness/config.json5", "harness/machines.json5", "harness/routing.json5"):
            self.assertTrue(os.path.isfile(sd_path(root, rel)), rel)
            self.assertFalse(os.path.exists(sd_path(root, rel[:-1])), rel)
        self.assertEqual(read_bytes(sd_path(root, "state/memory/agents/dev-billing.json5")), r["mem_before"],
                         "memória do cs-mem intacta")
        self.assertEqual(mandato_data(root), r["mandato_before"], "chaves e valores do mandato M5 iguais")


if __name__ == "__main__":
    unittest.main()
