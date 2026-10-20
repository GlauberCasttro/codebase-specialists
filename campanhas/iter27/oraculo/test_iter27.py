"""ORÁCULO campanha-iter27 (0.15.0) — CLI e motor inteiros em inglês (B-72 + B-68 + B-71).

Mapa requisito → teste e critérios em ESPEC.md (mesma pasta). Tudo pelo caminho REAL: alvo da fixture do emit
(init + harness install + emit pela skill), estado em MODO ÁRVORE (`cs-state init`), comandos pelos bins do PRÓPRIO
alvo (`.swarm/harness/<x>.py --root <alvo>`: state = cs-state, auto = cs-auto, router = cs-route, session =
cs-session) e pelo `cs.py` da skill sob teste.

  CA-01  TestCA01  cs-state: `new epic|sprint|feature|task|story`, `move`, `close` com as flags en criam/movem/fecham
                   igual ao pt (disco e saída comparados em dois clones); pt com aviso no stderr; help só en.
  CA-02  TestCA02  cs-auto (`propose`, `approve`, `amend`, `resolve`, `plan add-node|edit-node|submit`, `reflect`,
                   `escalate`, `pause`) e cs-route (`outcome`, `anular`) com flags en: mesmo efeito do pt; help só en.
  CA-03  TestCA03  uma linha de depreciação por chamada listando cada `pt → en`; pt+en ⇒ en vence, pt "ignorad".
  CA-04  TestCA04  `--include-emitted` em emit / harness install / upgrade --apply / init --replace-harness; recusa
                   cita a flag nova; `--allow-outside` alias com aviso; plano do upgrade cita `.swarm/events.jsonl`.
  CA-05  TestCA05  0 citação de flag pt nos textos (emitidos, SKILL, MODO-DE-USO, references, docs, código).
  CA-06  TestCA06  o doctest de comandos confere o cs-auto (citação inválida de cs-auto reprova).
  CA-07  TestCA07  `new … --dry-run` mantém {ids, criar, mover, eventos} + item en igual ao arquivo; nada escrito.
  CA-08  TestCA08  `hcore.load_board` do motor instalado: nenhuma chave pt de ITEM_SCHEMA/SESSION_SCHEMA nem
                   `kind: "epico"`; replay do histórico pt igual; eventos novos en; arquivo do item igual ao da 0.14.0.
  CA-09  TestCA09  alvo 0.14.0 real com `kind: "epico"` no disco → `upgrade --apply --include-emitted`: 0, `epic`,
                   validate --strict, events.jsonl intacto, textos sem flag pt, VERSION ≥ 0.15.0.

Versão sempre RELATIVA (≥). Skill sob teste: $CS_SKILL_DIR, senão a raiz deste projeto. Skill 0.14.0: $CS_OLD_SKILL_DIR
ou `git archive 9e908e0`; skill 0.13.1 (só para o `kind: "epico"` no disco do CA-09): $CS_OLDER_SKILL_DIR ou
`git archive bac0e0f`. Temporários: $CS_ORACLE_TMP, senão o TMPDIR do sistema. Python 3.9+, unittest, só stdlib.
Rodar (desta pasta): python3 -m unittest -v test_iter27
"""
import ast
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
OLD_COMMIT = "9e908e0"          # skill 0.14.0 real (iter26 entregue; o produto não mudou depois)
OLD_VERSION = (0, 14, 0)
OLDER_COMMIT = "bac0e0f"        # skill 0.13.1 real: grava `kind: "epico"` no disco (a 0.14.0 preserva na migração)
OLDER_VERSION = (0, 13, 1)
NEW_VERSION = (0, 15, 0)

GIT_ENV = {"GIT_AUTHOR_NAME": "Ana", "GIT_AUTHOR_EMAIL": "ana@x", "GIT_COMMITTER_NAME": "Ana",
           "GIT_COMMITTER_EMAIL": "ana@x"}
SD = ".swarm"
AGENT = "dev-billing"
OTHER = "dev-web"
VERIFY = "python3 -m unittest tests.test_ok"
ACEITE = "python3 -m unittest tests.test_red"
C1 = "AC-1|Dado pedido Quando aplico Então desconta|tests.test_ok"
CREATED_RE = re.compile(r"^criad[oa] (\S+) em (\S+)\s*$", re.M)
DEPREC = re.compile(r"deprec|obsolet|descontinuad", re.I)
IGNORED = re.compile(r"ignorad|ignored", re.I)
ISO_RX = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?"
                    r"|\d{8}T\d{6}\d*Z?")         # ISO e o compacto dos nomes de arquivo (escalada-<ts>-ESC-1.json)
DATE_RX = re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)")    # data do relógio em ids/caminhos (2026-10-19-01)
_TMP = {}

# ---------------------------------------------------------------- vocabulário (literal; NÃO importado do produto)
# nome pt de hoje (0.14.0) → nome en FIXADO na FEATURE.md (CA-01, CA-02, CA-04), por bin/subcomando
STATE_TREE_FLAGS = {"--objetivo": "--objective", "--metrica": "--metric", "--meta": "--goal", "--epico": "--epic",
                    "--aceite": "--accept-cmd", "--teste": "--proving-test", "--criterio": "--criterion",
                    "--avulsa": "--standalone", "--devolver": "--return"}
AUTO_FLAGS = {"--objetivo": "--objective", "--nos": "--nodes", "--criterio": "--criterion",
              "--regressao": "--regression", "--classe": "--class", "--portao": "--gate", "--orcamento": "--budget",
              "--escalada": "--escalation", "--tipo": "--type", "--cobre": "--covers", "--teste": "--proving-test",
              "--motivo": "--reason", "--evidencia": "--evidence", "--texto": "--text", "--condicao": "--condition",
              "--no": "--node"}
ROUTE_FLAGS = {"--procedencia": "--provenance", "--motivo": "--reason"}
ITER26_FLAGS = {"--tipo": "--type", "--como": "--as-a", "--quero": "--i-want", "--para": "--so-that",
                "--motivo": "--reason", "--reproducao": "--failing-test"}
PT_TO_EN = {}
for _m in (ITER26_FLAGS, ROUTE_FLAGS, AUTO_FLAGS, STATE_TREE_FLAGS):
    for _k, _v in _m.items():
        PT_TO_EN.setdefault(_k, set()).add(_v)
PT_NAMES = sorted(k[2:] for k in PT_TO_EN)
# flag pt citada: `--nome` inteiro (nem `--no-settings`, nem `--nos` quando se procura `--no`, nem `--metadata`)
PT_FLAG_RX = re.compile(r"(?<![\w-])--(%s)(?![\w-])" % "|".join(sorted(PT_NAMES, key=len, reverse=True)))
# chaves pt da forma interna da 0.14.0 (hcore.py:254-310 no HEAD 9e908e0), LITERAIS
ITEM_PT_KEYS = {"tipo", "como", "quero", "para", "criterios", "teste", "reproducao", "motivo", "aceite", "epico",
                "objetivo", "metrica", "meta", "reaberta", "reaberturas", "historico",
                "acao", "de",                                        # history[] (para → to também)
                "entregue", "devolvido", "metricas", "origem",       # closed
                "tentativas", "status_m2"}                           # closed.metrics
SESSION_PT_KEYS = {"blocos", "titulo", "linhas"}


# ================================================================================================ infraestrutura
def _env(extra=None):
    e = dict(os.environ)
    for k in list(e):
        if k.startswith("CS_") or k in ("CLAUDE_PROJECT_DIR", "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
            e.pop(k, None)
    e.update(GIT_ENV)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    e.update({"GIT_CONFIG_COUNT": "3", "GIT_CONFIG_KEY_0": "gc.auto", "GIT_CONFIG_VALUE_0": "0",
              "GIT_CONFIG_KEY_1": "maintenance.auto", "GIT_CONFIG_VALUE_1": "false",
              "GIT_CONFIG_KEY_2": "gc.autoDetach", "GIT_CONFIG_VALUE_2": "false"})
    e.update(extra or {})
    return e


def _run(argv, cwd, timeout=900, extra=None, stdin=None):
    p = subprocess.run(argv, cwd=cwd, env=_env(extra), input=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       timeout=timeout)
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


def tool(root, name, *args, actor=None, extra=None):
    """bin do motor INSTALADO no alvo (.swarm/harness/<name>.py --root <alvo>), o que .swarm/bin/cs-* chama."""
    argv = [sys.executable, os.path.join(root, SD, "harness", name + ".py"), "--root", root]
    if actor:
        argv += ["--actor", actor]
    return _run(argv + list(args), root, extra=extra)


def tool_ok(root, name, *args, actor=None):
    code, out, err = tool(root, name, *args, actor=actor)
    if code != 0:
        raise AssertionError("%s %s → %d\n%s%s" % (name, " ".join(args), code, out[-3000:], err[-3000:]))
    return out


def st(root, *args, actor=None):
    return tool(root, "state", *args, actor=actor)


def st_ok(root, *args, actor=None):
    return tool_ok(root, "state", *args, actor=actor)


def new_id(root, *args):
    out = st_ok(root, "new", *args)
    got = CREATED_RE.findall(out)
    if not got:
        raise AssertionError("`new` deveria imprimir `criado <ID> em <path>`: %r" % out)
    return got[0][0]


def read_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def write(root, rel, txt):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(txt)


def vtuple(v):
    return tuple(int(x) for x in str(v).strip().split("."))


def _strip_json5(txt):
    out, i, n, s = [], 0, len(txt), None
    while i < n:
        c = txt[i]
        if s:
            out.append(c)
            if c == "\\":
                out.append(txt[i + 1])
                i += 2
                continue
            if c == s:
                s = None
        elif c in "\"'":
            s = c
            out.append(c)
        elif txt.startswith("//", i):
            while i < n and txt[i] != "\n":
                i += 1
            continue
        elif txt.startswith("/*", i):
            i = txt.index("*/", i) + 2
            continue
        else:
            out.append(c)
        i += 1
    t = "".join(out)
    t = re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', t)
    t = re.sub(r",(\s*[}\]])", r"\1", t)
    return json.loads(t)


def load_any(path):
    txt = read_text(path)
    return json.loads(txt) if path.endswith(".json") else _strip_json5(txt)


def all_items(root):
    """{id: (zona, path, dict)} de todos os arquivos de item da árvore (backlog/state/archive)."""
    got = {}
    for zone in ("backlog", "state", "archive"):
        for dp, _, fns in os.walk(os.path.join(root, SD, zone)):
            for fn in fns:
                if not fn.endswith((".json", ".json5")):
                    continue
                p = os.path.join(dp, fn)
                try:
                    d = load_any(p)
                except Exception:
                    continue
                if isinstance(d, dict) and d.get("id") and d.get("kind"):
                    got[d["id"]] = (zone, p, d)
    return got


def item(root, iid):
    got = all_items(root)
    if iid not in got:
        raise AssertionError("item %s sem arquivo na árvore" % iid)
    return got[iid]


def walk_dicts(x):
    if isinstance(x, dict):
        yield x
        for v in x.values():
            for y in walk_dicts(v):
                yield y
    elif isinstance(x, list):
        for v in x:
            for y in walk_dicts(v):
                yield y


def norm_ts(x):
    """troca todo timestamp ISO por <T> e toda data AAAA-MM-DD (ids de task avulsa/backlog) por <D>, em valores e
    chaves — o resto tem de ser igual."""
    if isinstance(x, dict):
        return {norm_ts(k): norm_ts(v) for k, v in x.items()}
    if isinstance(x, list):
        return [norm_ts(v) for v in x]
    if isinstance(x, str):
        return DATE_RX.sub("<D>", ISO_RX.sub("<T>", x))
    return x


RUN_ID_RX = re.compile(r"(run_id\W{0,3})[0-9a-f]{16}")     # aleatório por init (cs.py init imprime)


def norm_text(s):
    return DATE_RX.sub("<D>", RUN_ID_RX.sub(r"\1<RUN>", ISO_RX.sub("<T>", s)))


def snapshot(root, skip=(".git",)):
    """{rel: sha256} de todo arquivo da árvore do alvo (fora .git)."""
    got = {}
    for dp, dns, fns in os.walk(root):
        rel_dp = os.path.relpath(dp, root)
        dns[:] = [d for d in dns if not (rel_dp == "." and d in skip)]
        for fn in fns:
            p = os.path.join(dp, fn)
            if os.path.islink(p):
                got[os.path.relpath(p, root)] = "link:" + os.readlink(p)
            else:
                got[os.path.relpath(p, root)] = hashlib.sha256(read_bytes(p)).hexdigest()
    return got


def items_by_rel(root):
    """{caminho relativo do arquivo do item: dict normalizado (timestamps → <T>)}."""
    return {norm_text(os.path.relpath(p, root)): norm_ts(d) for _, (z, p, d) in all_items(root).items()}


def dep_lines(err):
    return [ln for ln in err.splitlines() if DEPREC.search(ln)]


def no_dep(err):
    """stderr sem a(s) linha(s) de depreciação (o resto da saída do pt tem de ser igual à do en)."""
    return "\n".join(ln for ln in err.splitlines() if not DEPREC.search(ln))


def pair_text(pt, en):
    return re.compile(r"%s\s*(→|->)\s*%s(?![\w-])" % (re.escape(pt), re.escape(en)))


# ================================================================================================ fixtures
def _base_tmp():
    if "base" not in _TMP:
        _TMP["base"] = os.path.realpath(tempfile.mkdtemp(prefix="oraculo-iter27-",
                                                         dir=os.environ.get("CS_ORACLE_TMP") or None))
    return _TMP["base"]


def tearDownModule():
    if "base" in _TMP and not os.environ.get("CS_ORACLE_KEEP"):
        shutil.rmtree(_TMP["base"], ignore_errors=True)


def _archive(commit, env_name, version, name):
    """A skill real de `commit`: $<env_name> ou `git archive` extraído num temporário (sem escrever no repo)."""
    if name in _TMP:
        return _TMP[name]
    d = os.environ.get(env_name)
    if not d:
        d = os.path.join(_base_tmp(), name)
        p = subprocess.run(["git", "-C", PROJECT, "archive", "--format=tar", commit], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=300)
        if p.returncode != 0:
            raise AssertionError("não consegui extrair a skill (git archive %s): %s — defina $%s"
                                 % (commit, p.stderr.decode(), env_name))
        os.makedirs(d)
        with tarfile.open(fileobj=io.BytesIO(p.stdout)) as tf:
            if hasattr(tarfile, "data_filter"):
                tf.extractall(d, filter="data")
            else:
                tf.extractall(d)
    d = os.path.realpath(d)
    v = read_text(os.path.join(d, "VERSION")).strip()
    if vtuple(v) != version:
        raise AssertionError("skill em %s tem VERSION %s (esperado %s)" % (d, v, ".".join(map(str, version))))
    _TMP[name] = d
    return d


def old_skill():
    return _archive(OLD_COMMIT, "CS_OLD_SKILL_DIR", OLD_VERSION, "skill-0140")


def older_skill():
    return _archive(OLDER_COMMIT, "CS_OLDER_SKILL_DIR", OLDER_VERSION, "skill-0131")


ACCEPT_TEST = ("import os\nimport unittest\n\n\nclass A(unittest.TestCase):\n    def test_ac(self):\n"
               "        p = 'src/billing/discount.py'\n"
               "        self.assertTrue(os.path.isfile(p) and 'OK' in open(p).read())\n")


def make_target(skill, name, flag="--allow-outside"):
    """alvo da fixture do emit, gerado pela `skill` (init + harness install + emit) e em modo árvore."""
    dest = os.path.join(_base_tmp(), name)
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
    write(dest, "tests/test_red.py", "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_red(self):\n"
                                     "        self.assertTrue(False, 'bug da Ana')\n")
    write(dest, "accept/__init__.py", "")
    write(dest, "accept/test_ac_1.py", ACCEPT_TEST)
    write(dest, "spec/feature.md", "# Desconto da Ana\n\nDesconto no checkout da Ana.\n")
    for f in ("coupons.py", "pix.py", "frete.py", "taxa.py", "nota.py", "q.py", "bug.py", "flat.py", "solta.py"):
        write(dest, "src/billing/" + f, "X = 1\n")
    git(dest, "init", "-q")
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "init")
    cs_ok(skill, dest, "init", "--platforms", "claude-code")
    cs_ok(skill, dest, "harness", "install", flag)
    cs_ok(skill, dest, "emit", flag)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "gerado pela skill")
    st_ok(dest, "init")
    if not os.path.isfile(os.path.join(dest, SD, "events.jsonl")):
        raise AssertionError("fixture: o alvo não ficou em modo árvore (.swarm/events.jsonl ausente)")
    return dest


def clone(src, name):
    dst = os.path.join(_base_tmp(), name)
    for attempt in range(3):
        shutil.rmtree(dst, ignore_errors=True)
        try:
            shutil.copytree(src, dst, symlinks=True)
            return dst
        except shutil.Error:
            if attempt == 2:
                raise
    return dst


_N = [0]


def _uniq(tag):
    _N[0] += 1
    return "%s-%d" % (tag, _N[0])


def _us_pt(title, path, *extra):
    """flags pt (valem na 0.13.1, na 0.14.0 e, como alias depreciado, na 0.15.0) — a fixture roda nas três."""
    return ["--tipo", "US", "--agent", AGENT, "--title", title, "--allowed-path", path, "--verify-cmd", VERIFY,
            "--como", "cliente", "--quero", "cupom", "--para", "pagar menos", "--criterio", C1] + list(extra)


def populate(root):
    """Árvore da Ana pelas flags pt: EPC › SPR › FEA (iniciados); 1 task na sprint; 1 avulsa; 1 no backlog."""
    ids = {}
    ids["epc"] = new_id(root, "epico", "--title", "Pagamentos da Ana", "--objetivo", "pix", "--metrica", "conversao")
    ids["spr"] = new_id(root, "sprint", "--meta", "pix da Ana", "--epico", ids["epc"])
    st_ok(root, "start", ids["epc"])
    st_ok(root, "start", ids["spr"])
    ids["fea"] = new_id(root, "feature", "--title", "Pix da Ana", "--sprint", ids["spr"], "--aceite", ACEITE)
    st_ok(root, "start", ids["fea"])
    ids["task"] = new_id(root, "task", *_us_pt("Cupom da Ana", "src/billing/coupons.py", "--sprint", ids["spr"]))
    ids["avulsa"] = new_id(root, "task", *_us_pt("Solta da Ana", "src/billing/solta.py", "--avulsa"))
    ids["bkl"] = new_id(root, "task", *_us_pt("Nota da Ana", "src/billing/nota.py", "--backlog"))
    return ids


def fresh_base():
    """alvo gerado pela skill SOB TESTE, árvore da Ana, commitado. Construído 1 vez; cada teste usa um clone."""
    if "fresh" not in _TMP:
        root = make_target(SKILL, "base-nova")
        ids = populate(root)
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "arvore da Ana")
        _TMP["fresh"] = (root, ids)
    return _TMP["fresh"]


def fresh(tag):
    src, ids = fresh_base()
    return clone(src, "nova-" + _uniq(tag)), dict(ids)


# ================================================================================================ cs-auto (M5)
# O `approve` exige a SENHA digitada num terminal (iter14). O oráculo faz o papel do humano como a suíte do produto
# (scripts/harness/tests/test_cobertura_maquinas.py): registro PBKDF2 de TESTE num temporário fora do alvo
# ($CS_SENHA_FILE só no env do subprocesso) e o approve num pty real digitando a senha de teste a cada prompt.
SENHA_TESTE = "Mandato-da-Ana-2026"
_SENHA_PROMPT = re.compile(rb"SENHA[^\r\n:]*:")
HUMAN = "Ana"
ORC = "despachos=20,tentativas=40,replanos=3,minutos=600,usd=50"
ORC2 = "despachos=12,tentativas=30,replanos=2,minutos=300,usd=20"
CRIT_AUTO = "AC-1|Dado o checkout da Ana Quando entrego Então tem OK|accept.test_ac_1"


def senha_file():
    if "senha" not in _TMP:
        import unicodedata
        d = os.path.join(_base_tmp(), "senha-de-teste")
        os.makedirs(d, mode=0o700)
        sv, sk = os.urandom(16).hex(), os.urandom(16).hex()
        nb = unicodedata.normalize("NFC", SENHA_TESTE.strip()).encode("utf-8")
        reg = {"versao": 1, "kdf": "pbkdf2-sha256", "iter": 600000, "salt_verificador": sv, "salt_chave": sk,
               "verificador": hashlib.pbkdf2_hmac("sha256", nb, bytes.fromhex(sv), 600000, dklen=32).hex(),
               "criada_em": "2026-01-01T00:00:00Z"}
        p = os.path.join(d, "senha.json")
        with open(p, "w") as f:
            json.dump(reg, f)
        os.chmod(p, 0o600)
        _TMP["senha"] = p
    return _TMP["senha"]


def run_tty(argv, cwd, env, timeout=300):
    """argv num pty real (stdin = tty) digitando a senha de teste a cada prompt `SENHA…:`. → (exit, saída)."""
    import pty
    import select
    import signal
    import time
    pid, fd = pty.fork()
    if pid == 0:
        try:
            os.chdir(cwd)
            os.execve(argv[0], argv, env)
        finally:
            os._exit(127)
    buf, seen, deadline = b"", 0, time.monotonic() + timeout
    try:
        while True:
            if time.monotonic() > deadline:
                os.kill(pid, signal.SIGKILL)
                raise AssertionError("approve no tty não terminou em %ss: %r" % (timeout, buf[-500:]))
            r, _, _ = select.select([fd], [], [], 0.1)
            if not r:
                continue
            try:
                data = os.read(fd, 4096)
            except OSError:
                break
            if not data:
                break
            buf += data
            n = len(_SENHA_PROMPT.findall(buf))
            while seen < n:
                os.write(fd, (SENHA_TESTE + "\n").encode("utf-8"))
                seen += 1
    finally:
        _, status = os.waitpid(pid, 0)
        os.close(fd)
    code = os.WEXITSTATUS(status) if os.WIFEXITED(status) else 128 + os.WTERMSIG(status)
    return code, buf.decode("utf-8", "replace").replace("\r\n", "\n")


def auto(root, *args):
    return tool(root, "auto", *args)


def auto_ok(root, *args):
    return tool_ok(root, "auto", *args)


def approve(root, *flags):
    """`cs-auto approve --by Ana <flags>` no pty com a senha de teste → (exit, saída)."""
    argv = [sys.executable, os.path.join(root, SD, "harness", "auto.py"), "--root", root, "approve", "--by", HUMAN]
    return run_tty(argv + list(flags), root, _env({"CS_SENHA_FILE": senha_file()}))


def mandate(root, mid="MAN-001"):
    d = os.path.join(root, SD, "state", "mandatos", mid)
    fs = [f for f in sorted(os.listdir(d)) if re.match(r"^mandato\.json5?$", f)] if os.path.isdir(d) else []
    if len(fs) != 1:
        raise AssertionError("mandato %s: esperado 1 arquivo mandato.json[5], veio %s" % (mid, fs))
    return load_any(os.path.join(d, fs[0]))


def propose_args(fea, en=False):
    f = (lambda pt: AUTO_FLAGS[pt]) if en else (lambda pt: pt)
    return ["propose", "--feature", fea, "--spec", "spec/feature.md", f("--objetivo"), "Desconto da Ana",
            f("--nos"), "2", f("--regressao"), VERIFY, f("--criterio"), CRIT_AUTO, f("--classe"), "feature",
            f("--portao"), "reviewer"]


def node_args(cmd, no, en=False, **kw):
    f = (lambda pt: AUTO_FLAGS[pt]) if en else (lambda pt: pt)
    a = ["plan", cmd, "--id", no, f("--tipo"), "US", f("--cobre"), "AC-1"]
    for k in ("agent", "title", "path", "deps"):
        if kw.get(k):
            a += ["--" + k, kw[k]]
    if kw.get("teste"):
        a += [f("--teste"), kw["teste"]]
    return a


N01 = {"agent": AGENT, "title": "N01 da Ana", "path": "src/billing/discount.py", "teste": "accept.test_ac_1"}
N02 = {"agent": OTHER, "title": "N02 da Ana", "path": "src/web/desconto.py", "deps": "01"}


def _auto_stage(name):
    """cadeia do mandato pelas flags pt (valem na 0.14.0 e, como alias, na 0.15.0), cada etapa construída 1 vez:
    proposed (propose) → chartered (approve no pty) → planning (tick) → running (2 nós + submit)."""
    key = "auto-" + name
    if key in _TMP:
        return _TMP[key]
    if name == "proposed":
        src, ids = fresh_base()
        root = clone(src, "auto-proposed")
        auto_ok(root, *propose_args(ids["fea"]))
    elif name == "chartered":
        root = clone(_auto_stage("proposed")[0], "auto-chartered")
        code, out = approve(root, "--orcamento", ORC)
        if code != 0 or mandate(root).get("state") != "CHARTERED":
            raise AssertionError("fixture: approve no pty → %d\n%s" % (code, out[-2000:]))
    elif name == "planning":
        root = clone(_auto_stage("chartered")[0], "auto-planning")
        t = json.loads(auto_ok(root, "tick", "--json"))
        if t.get("acao") != "PLAN":
            raise AssertionError("fixture: CHARTERED → tick deveria pedir PLAN: %r" % t)
    elif name == "running":
        root = clone(_auto_stage("planning")[0], "auto-running")
        auto_ok(root, *node_args("add-node", "01", **N01))
        auto_ok(root, *node_args("add-node", "02", **N02))
        auto_ok(root, "plan", "submit")
        if mandate(root).get("state") != "RUNNING":
            raise AssertionError("fixture: plan submit deveria levar a RUNNING: %s" % mandate(root).get("state"))
    elif name == "awaiting":
        root = clone(_auto_stage("running")[0], "auto-awaiting")
        auto_ok(root, "escalate", "--condicao", "material_ambiguity", "--evidencia", "spec/feature.md:1", "--no", "01")
        if mandate(root).get("state") != "AWAITING_HUMAN":
            raise AssertionError("fixture: escalate deveria levar a AWAITING_HUMAN: %s" % mandate(root).get("state"))
    elif name == "reflect":
        root = clone(_auto_stage("running")[0], "auto-reflect")
        t = {}
        for _ in range(6):
            t = json.loads(auto_ok(root, "tick", "--json"))
            if t.get("acao") == "DISPATCH":
                st_ok(root, "dispatch", t["alvo"], "--manual", "--model", t.get("model") or "sonnet")
                write(root, "src/billing/discount.py", "ERRADO = 1\n")
                st_ok(root, "submit", t["alvo"], "--files-changed", "src/billing/discount.py", "--check",
                      "unittest: OK", "--risk", "nenhum", "--handoff-notes", "ok", actor=AGENT)
            elif t.get("acao") == "REVIEW":
                st_ok(root, "review", t["alvo"], "--by", t["agente"], "--verdict", "FAIL", "--findings",
                      "faltou o OK da Ana em src/billing/discount.py:1")
            else:
                break
        if t.get("acao") != "REFLECT":
            raise AssertionError("fixture: o nó rejeitado deveria pedir REFLECT: %r" % t)
        _TMP["reflect-task"] = t["alvo"]
    else:
        raise ValueError(name)
    _TMP[key] = (root, dict(fresh_base()[1]))
    return _TMP[key]


def auto_clone(stage, tag):
    src, ids = _auto_stage(stage)
    return clone(src, "%s-%s" % (stage, _uniq(tag))), dict(ids)


def _strip_top(d, keys=("relogio", "updated_at")):
    return {k: v for k, v in d.items() if k not in keys} if isinstance(d, dict) else d


def mandate_view(root, mid="MAN-001"):
    """{nome normalizado: conteúdo normalizado} da pasta do mandato (relógio e updated_at fora: medem duração)."""
    d = os.path.join(root, SD, "state", "mandatos", mid)
    out = {}
    for fn in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        p = os.path.join(d, fn)
        if os.path.isfile(p) and fn.endswith((".json", ".json5")):
            out[norm_text(fn)] = norm_ts(_strip_top(load_any(p)))
    return out


def auto_view(root):
    return {"mandato": mandate_view(root), "itens": items_by_rel(root)}


ROUTER_LOG = os.path.join(SD, ".engine", "model-router.jsonl")


def router_lines(root):
    p = os.path.join(root, ROUTER_LOG)
    return [json.loads(x) for x in read_text(p).splitlines() if x.strip()] if os.path.isfile(p) else []


# ================================================================================================ fixtures legadas
def legacy_0131():
    """alvo instalado e povoado pela skill 0.13.1 REAL (`kind: "epico"` no disco) + carimbo de sessão."""
    if "l0131" not in _TMP:
        root = make_target(older_skill(), "base-0131")
        ids = populate(root)
        tool_ok(root, "session", "save", "--did", "arvore da Ana", "--next", "upgrade")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "itens da Ana (0.13.1)")
        _TMP["l0131"] = (root, ids)
    return _TMP["l0131"]


def legacy_0140():
    """o alvo 0.13.1 atualizado pela skill 0.14.0 REAL (`upgrade --apply --allow-outside`; o `kind: "epico"` fica no
    disco) e trabalhado na 0.14.0 (task nova, move, carimbo): itens, sessões e eventos `tput` com chaves pt."""
    if "l0140" not in _TMP:
        src, ids = legacy_0131()
        root = clone(src, "base-0140-legada")
        cs_ok(old_skill(), root, "upgrade", "--apply", "--allow-outside")
        run = read_text(os.path.join(root, SD, "run.json5"))
        if not re.search(r'skill_version:\s*"0\.14\.0"', run):
            raise AssertionError("fixture: o alvo legado deveria estar na 0.14.0: %s" % run[:400])
        if item(root, ids["epc"])[2].get("kind") != "epico":
            raise AssertionError("fixture: o épico do alvo legado deveria ter `kind: \"epico\"` no disco")
        ids["task14"] = new_id(root, "task", *_us_pt("Frete da Ana", "src/billing/frete.py", "--sprint", ids["spr"]))
        st_ok(root, "move", ids["bkl"], "--avulsa")
        tool_ok(root, "session", "save", "--did", "trabalho na 0.14.0", "--next", "0.15.0")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "trabalho da Ana (0.14.0)")
        _TMP["l0140"] = (root, ids)
    return _TMP["l0140"]


def legacy_clone(tag):
    src, ids = legacy_0140()
    return clone(src, "legado-" + _uniq(tag)), dict(ids)


def fresh_old_base():
    """alvo gerado e povoado pela skill 0.14.0 REAL com os mesmos comandos do fresh_base (comparação byte a byte)."""
    if "fresh-old" not in _TMP:
        root = make_target(old_skill(), "base-0140-nova")
        ids = populate(root)
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "arvore da Ana")
        _TMP["fresh-old"] = (root, ids)
    return _TMP["fresh-old"]


def outside_view(root):
    """snapshot do que fica FORA de .swarm/ (e de .git)."""
    return snapshot(root, skip=(".git", SD))


def emitted_text_lines(root):
    """[(rel, nº, linha)] dos textos emitidos (CLAUDE.md, AGENTS.md, Makefile/*.mk, .claude/**, .cursor, .github,
    .swarm/emit), fora dos cadernos (.claude/agent-memory) — mesma lista da iter26."""
    got, cands = [], []
    for rel in ("CLAUDE.md", "AGENTS.md", "Makefile", "specialists.mk"):
        if os.path.isfile(os.path.join(root, rel)):
            cands.append(rel)
    for d in (".claude", ".cursor", ".github", os.path.join(SD, "emit")):
        for dp, _, fns in os.walk(os.path.join(root, d)):
            if "agent-memory" in dp:
                continue
            for fn in fns:
                if fn.endswith((".md", ".mdc", ".mk", ".txt", ".json", ".json5", ".sh")):
                    cands.append(os.path.relpath(os.path.join(dp, fn), root))
    for rel in cands:
        try:
            txt = read_text(os.path.join(root, rel))
        except (UnicodeDecodeError, OSError):
            continue
        for i, ln in enumerate(txt.splitlines(), 1):
            got.append((rel, i, ln))
    return got


# ---------------------------------------------------------------- varredura de flag pt (CA-05, CA-09)
def _alias_row(line, pt):
    """linha de TABELA Markdown (começa com `|`) que traz o pt E o seu en: tabela de alias (isenta)."""
    return line.lstrip().startswith("|") and any(re.search(re.escape(en) + r"(?![\w-])", line) for en in PT_TO_EN[pt])


def line_hits(rel, i, line):
    out = []
    for m in PT_FLAG_RX.finditer(line):
        pt = m.group(0)
        if not _alias_row(line, pt):
            out.append("%s:%d: %s  ← %s" % (rel, i, line.strip()[:150], pt))
    return out


def text_file_hits(path, rel):
    try:
        txt = read_text(path)
    except (UnicodeDecodeError, OSError):
        return []
    out = []
    for i, ln in enumerate(txt.splitlines(), 1):
        out += line_hits(rel, i, ln)
    return out


def tree_text_hits(base, rels, exts=None, skip=()):
    out = []
    for rel in rels:
        p = os.path.join(base, rel)
        files = [p] if os.path.isfile(p) else sorted(os.path.join(d, f) for d, _, fs in os.walk(p) for f in fs)
        for f in files:
            r = os.path.relpath(f, base)
            if "__pycache__" in r or r in skip or (exts and not r.endswith(exts)):
                continue
            out += text_file_hits(f, r)
    return out


def emitted_hits(root):
    out = []
    for rel, i, ln in emitted_text_lines(root):
        out += line_hits(rel, i, ln)
    return out


BARE_FLAG = re.compile(r"^-{1,2}[A-Za-z][\w-]*$")


def code_string_hits(src, rel):
    """strings do código (ast.Constant, inclusive partes de f-string) que citam flag pt. Isentas: docstrings e a
    string que é SÓ um nome de flag (`"--objetivo"`: tabela de alias / registro no argparse)."""
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return ["%s: não parseia (%s)" % (rel, e)]
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant) \
                    and isinstance(first.value.value, str):
                docs.add(id(first.value))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
            s = node.value
            if BARE_FLAG.match(s.strip()):
                continue
            for m in PT_FLAG_RX.finditer(s):
                out.append("%s:%s: %r  ← %s" % (rel, getattr(node, "lineno", "?"), s.strip()[:120], m.group(0)))
    return out


def code_hits(skill):
    """dicas e recusas do código do produto: scripts/**/*.py fora de testes (pastas tests/, test_*.py)."""
    out = []
    base = os.path.join(skill, "scripts")
    for d, dns, fns in os.walk(base):
        dns[:] = sorted(x for x in dns if x not in ("tests", "__pycache__"))
        for f in sorted(fns):
            if not f.endswith(".py") or f.startswith("test_"):
                continue
            p = os.path.join(d, f)
            out += code_string_hits(read_text(p), os.path.relpath(p, skill))
    return out


def scan_skill(skill):
    """{categoria: [citações pt]} da skill (CA-05)."""
    key = "scan-" + skill
    if key not in _TMP:
        _TMP[key] = _scan_skill(skill)
    return _TMP[key]


def _scan_skill(skill):
    return {
        "SKILL.md+MODO-DE-USO.md": tree_text_hits(skill, ["SKILL.md", "MODO-DE-USO.md"]),
        "references (fora migrations.json5)": tree_text_hits(skill, ["references"],
                                                             skip=(os.path.join("references", "migrations.json5"),)),
        "docs (*.md)": tree_text_hits(skill, ["docs"], exts=(".md",)),
        "assets/templates": tree_text_hits(skill, [os.path.join("assets", "templates")]),
        "código (dicas/recusas)": code_hits(skill),
    }


# ================================================================================================ CA-01
def twin(src, tag):
    return clone(src, "en-" + _uniq(tag)), clone(src, "pt-" + _uniq(tag))


def _unroot(r, root):
    code, out, err = r
    return code, out.replace(root, "<ALVO>"), err.replace(root, "<ALVO>")


class PairMixin(object):
    def assert_same(self, label, ra, rb, va, vb, A=None, B=None):
        """mesma chamada pela forma en (ra, alvo A) e pela pt (rb, alvo B): exit 0 nas duas, mesma saída (fora a
        linha de depreciação, timestamps e o caminho do alvo) e mesmo efeito (va == vb)."""
        if A and B:
            ra, rb = _unroot(ra, A), _unroot(rb, B)
        (ca, oa, ea), (cb, ob, eb) = ra, rb
        self.assertEqual(ca, 0, "%s: a forma en deveria ser aceita (exit 0); veio %d:\n%s%s"
                         % (label, ca, oa[-1500:], ea[-1500:]))
        self.assertEqual(cb, 0, "%s: a forma pt (alias) deveria seguir aceita; veio %d:\n%s%s"
                         % (label, cb, ob[-1500:], eb[-1500:]))
        self.assertEqual(norm_text(oa), norm_text(ob), "%s: stdout da forma en ≠ da forma pt" % label)
        self.assertEqual(norm_text(no_dep(ea)), norm_text(no_dep(eb)),
                         "%s: stderr (fora a linha de depreciação) da forma en ≠ da forma pt" % label)
        self.assertEqual(va, vb, "%s: o efeito no disco da forma en ≠ o da forma pt" % label)


def _f(en, pt_name, table=STATE_TREE_FLAGS):
    return table[pt_name] if en else pt_name


def _task_args(en, title, path, *extra):
    f = lambda n: _f(en, n)  # noqa: E731
    it = ITER26_FLAGS
    return [it["--tipo"] if en else "--tipo", "US", "--agent", AGENT, "--title", title, "--allowed-path", path,
            "--verify-cmd", VERIFY, it["--como"] if en else "--como", "cliente", it["--quero"] if en else "--quero",
            "cupom", it["--para"] if en else "--para", "pagar menos", f("--criterio"), C1, f("--teste"),
            "tests.test_ok"] + list(extra)


CA01_CMDS = {
    "new epic": lambda en, ids: ["new", "epic", "--title", "Fiscal da Ana", _f(en, "--objetivo"), "nota",
                                 _f(en, "--metrica"), "notas emitidas"],
    "new sprint": lambda en, ids: ["new", "sprint", _f(en, "--meta"), "fiscal da Ana", _f(en, "--epico"), "EPC-002"],
    "new feature": lambda en, ids: ["new", "feature", "--title", "Nota da Ana", "--sprint", ids["spr"],
                                    _f(en, "--aceite"), ACEITE],
    "new task (sprint)": lambda en, ids: ["new", "task"] + _task_args(en, "Pix en/pt da Ana", "src/billing/pix.py",
                                                                      "--sprint", ids["spr"]),
    "new task (avulsa)": lambda en, ids: ["new", "task"] + _task_args(en, "Avulsa en/pt da Ana", "src/billing/q.py",
                                                                      _f(en, "--avulsa")),
    "new story": lambda en, ids: ["new", "story"] + _task_args(en, "Story en/pt da Ana", "src/billing/q.py",
                                                               "--feature", ids["fea"], "--agents", AGENT,
                                                               "--agents", OTHER),
    "move": lambda en, ids: ["move", ids["bkl"], _f(en, "--avulsa")],
    "close": lambda en, ids: ["close", ids["fea"], "--summary", "fim da Ana", _f(en, "--devolver"), "--reason",
                              "fora do escopo da Ana"],
}
CA01_HELP = {("new", "epic"): ("--objective", "--metric"), ("new", "sprint"): ("--goal", "--epic"),
             ("new", "feature"): ("--accept-cmd",), ("new", "task"): ("--criterion", "--proving-test", "--standalone"),
             ("new", "story"): ("--criterion", "--proving-test"), ("move",): ("--standalone",), ("close",): ("--return",)}


def _pre_sprint(root, ids):
    """um épico sem sprint aberta (UMA sprint aberta por épico): EPC-002."""
    eid = new_id(root, "epico", "--title", "Fiscal da Ana", "--objetivo", "nota")
    if eid != "EPC-002":
        raise AssertionError("fixture: esperava EPC-002, veio %s" % eid)


def _pre_close(root, ids):
    """task aberta (não iniciada) na feature: o `close --devolver|--return` a devolve ao backlog."""
    new_id(root, "task", *_us_pt("Aberta da Ana", "src/billing/taxa.py", "--feature", ids["fea"]))


class TestCA01(PairMixin, unittest.TestCase):
    def _pair(self, name, pre=None, en=True):
        """A recebe a forma en (en=False: a pt, no controle pt × pt), B a pt; mesmo efeito e mesma saída."""
        src, ids = fresh_base()
        A, B = twin(src, "ca01")
        if pre:
            pre(A, ids)
            pre(B, ids)
        ra = st(A, *CA01_CMDS[name](en, ids))
        rb = st(B, *CA01_CMDS[name](False, ids))
        self.assert_same("cs-state " + name, ra, rb, items_by_rel(A), items_by_rel(B), A, B)

    def test_ca01_new_epic_en_igual_pt(self):
        self._pair("new epic")

    def test_ca01_new_sprint_en_igual_pt(self):
        self._pair("new sprint", pre=_pre_sprint)

    def test_ca01_new_feature_en_igual_pt(self):
        self._pair("new feature")

    def test_ca01_new_task_en_igual_pt(self):
        self._pair("new task (sprint)")

    def test_ca01_new_task_standalone_en_igual_pt(self):
        self._pair("new task (avulsa)")

    def test_ca01_new_story_en_igual_pt(self):
        self._pair("new story")

    def test_ca01_move_standalone_en_igual_pt(self):
        self._pair("move")

    def test_ca01_close_return_en_igual_pt(self):
        self._pair("close", pre=_pre_close)

    def test_ca01_pt_avisa_depreciacao(self):
        """cada comando pela forma pt: exit 0 e linha de depreciação no stderr citando cada flag pt da árvore usada."""
        bad = []
        for name, mk in sorted(CA01_CMDS.items()):
            root, ids = fresh("ca01pt")
            if name == "close":
                _pre_close(root, ids)
            if name == "new sprint":
                _pre_sprint(root, ids)
            args = mk(False, ids)
            code, out, err = st(root, *args)
            used = [a for a in args if a in STATE_TREE_FLAGS]
            dl = " ".join(dep_lines(err))
            miss = [u for u in used if not re.search(re.escape(u) + r"(?![\w-])", dl)]
            if code != 0 or not dl or miss:
                bad.append("%s → exit %d; sem aviso de depreciação para %s; stderr=%r" % (name, code, miss or used,
                                                                                        err[-300:]))
        self.assertEqual(bad, [], "a flag pt deveria seguir aceita COM aviso no stderr:\n  " + "\n  ".join(bad))

    def test_ca01_help_so_en(self):
        root, _ = fresh_base()
        bad = []
        for path, ens in sorted(CA01_HELP.items()):
            code, out, err = st(root, *(list(path) + ["--help"]))
            miss = [e for e in ens if not re.search(re.escape(e) + r"(?![\w-])", out)]
            pts = sorted(set(m.group(0) for m in PT_FLAG_RX.finditer(out)))
            if code != 0 or miss or pts:
                bad.append("cs-state %s --help → exit %d; en ausentes %s; pt presentes %s" % (" ".join(path), code,
                                                                                             miss, pts))
        self.assertEqual(bad, [], "o --help deveria trazer as flags en e nenhuma pt:\n  " + "\n  ".join(bad))

    def test_ca01_controle_par_pt_pt_e_deterministico(self):
        """calibração da comparação: os 8 comandos pela forma pt nos DOIS clones dão a mesma saída e o mesmo disco
        (a saída boa conhecida — en com o efeito do pt — passa; o que reprova o D é a forma en, não o relógio)."""
        pres = {"new sprint": _pre_sprint, "close": _pre_close}
        for name in sorted(CA01_CMDS):
            self._pair(name, pre=pres.get(name), en=False)

    def test_ca01_controle_pt_continua_criando(self):
        """controle: as flags pt de hoje continuam criando (exit 0) — a base do alias."""
        root, ids = fresh("ca01c")
        eid = new_id(root, *CA01_CMDS["new epic"](False, ids)[1:])
        d = item(root, eid)[2]
        self.assertEqual((d.get("kind"), d.get("objective"), d.get("metric")), ("epic", "nota", "notas emitidas"))


# ================================================================================================ CA-02
CA02_HELP = {
    ("auto", "propose"): ("--objective", "--nodes", "--criterion", "--regression", "--class", "--gate"),
    ("auto", "approve"): ("--budget",), ("auto", "amend"): ("--budget",), ("auto", "resolve"): ("--escalation",),
    ("auto", "plan", "add-node"): ("--type", "--covers", "--proving-test"),
    ("auto", "plan", "edit-node"): ("--type", "--covers", "--proving-test"),
    ("auto", "plan", "submit"): ("--reason", "--evidence"), ("auto", "reflect"): ("--text", "--evidence"),
    ("auto", "escalate"): ("--condition", "--evidence", "--node"), ("auto", "pause"): ("--reason",),
    ("router", "outcome"): ("--provenance",), ("router", "anular"): ("--reason",),
}


def _af(en, pt):
    return AUTO_FLAGS[pt] if en else pt


def _rf(en, pt):
    return ROUTE_FLAGS[pt] if en else pt


def _dispatched(root, ids):
    st_ok(root, "start", ids["task"])
    st_ok(root, "dispatch", ids["task"], "--manual", "--model", "sonnet")


class TestCA02(PairMixin, unittest.TestCase):
    def _auto_pair(self, label, stage, mk, pre=None, view=auto_view, en=True):
        if stage == "fresh":
            src, ids = fresh_base()
        else:
            src, ids = _auto_stage(stage)
        A, B = twin(src, "ca02")
        if pre:
            pre(A, ids)
            pre(B, ids)
        ra = auto(A, *mk(en, ids))
        rb = auto(B, *mk(False, ids))
        self.assert_same("cs-auto " + label, ra, rb, view(A), view(B), A, B)
        return A, B

    def test_ca02_propose_en_igual_pt(self):
        self._auto_pair("propose", "fresh", lambda en, ids: propose_args(ids["fea"], en=en))

    def test_ca02_approve_budget_en_igual_pt(self):
        src, _ = _auto_stage("proposed")
        A, B = twin(src, "ca02ap")
        ca, oa = approve(A, _af(True, "--orcamento"), ORC)
        cb, ob = approve(B, "--orcamento", ORC)
        self.assertEqual(ca, 0, "cs-auto approve --budget deveria ser aceito (exit 0); veio %d:\n%s" % (ca, oa[-1500:]))
        self.assertEqual(cb, 0, "cs-auto approve --orcamento (alias) deveria seguir aceito; veio %d:\n%s"
                         % (cb, ob[-1500:]))
        ma, mb = mandate(A), mandate(B)
        self.assertEqual((ma.get("state"), ma.get("orcamento")), (mb.get("state"), mb.get("orcamento")),
                         "approve: estado/orçamento da forma en ≠ da forma pt")

    def test_ca02_amend_budget_en_igual_pt(self):
        self._auto_pair("amend", "proposed", lambda en, ids: ["amend", "--by", HUMAN, _af(en, "--orcamento"), ORC2,
                                                                "--reason", "mais folga para a Ana"])

    def test_ca02_plan_add_edit_submit_en_igual_pt(self, en_a=True):
        src, ids = _auto_stage("planning")
        A, B = twin(src, "ca02pl")
        outs = {}
        for R, en in ((A, en_a), (B, False)):
            steps = [node_args("add-node", "01", en=en, **N01),
                     node_args("edit-node", "01", en=en, title="N01 editado pela Ana", teste="accept.test_ac_1"),
                     node_args("add-node", "02", en=en, **N02),
                     ["plan", "submit", _af(en, "--motivo"), "plano da Ana", _af(en, "--evidencia"),
                      "spec/feature.md:1"]]
            res = [auto(R, *s) for s in steps]
            outs[R] = res
        for i, lab in enumerate(("plan add-node", "plan edit-node", "plan add-node (2º)", "plan submit")):
            last = i == 3
            self.assert_same("cs-auto " + lab, outs[A][i], outs[B][i],
                             auto_view(A) if last else None, auto_view(B) if last else None, A, B)

    def test_ca02_reflect_en_igual_pt(self):
        tid = _auto_stage("reflect") and _TMP["reflect-task"]
        self._auto_pair("reflect", "reflect", lambda en, ids: ["reflect", tid, _af(en, "--texto"),
                                                               "faltou o OK da Ana; muda: escrever OK",
                                                               _af(en, "--evidencia"), "spec/feature.md:1"])

    def test_ca02_escalate_en_igual_pt(self):
        self._auto_pair("escalate", "running", lambda en, ids: ["escalate", _af(en, "--condicao"),
                                                                "material_ambiguity", _af(en, "--evidencia"),
                                                                "spec/feature.md:1", _af(en, "--no"), "01"])

    def test_ca02_controle_resolve_escalation_mesmo_efeito(self):
        """R: no HEAD o resolve ignora argumento desconhecido (PROOF_CMDS) e cai na última escalada aberta — o efeito
        é igual por acaso; aqui só guarda que o --escalation não muda o efeito do --escalada."""
        self._auto_pair("resolve", "awaiting", lambda en, ids: ["resolve", "--choice", "retomar", "--by", HUMAN,
                                                                "--decision", "segue a Ana",
                                                                _af(en, "--escalada"), "ESC-1"])

    def test_ca02_pause_en_igual_pt(self):
        self._auto_pair("pause", "running", lambda en, ids: ["pause", _af(en, "--motivo"), "almoco da Ana"])

    def test_ca02_route_outcome_en_igual_pt(self):
        src, ids = fresh_base()
        A, B = twin(src, "ca02ro")
        for R in (A, B):
            _dispatched(R, ids)
        n = len(router_lines(A))
        ra = tool(A, "router", "outcome", ids["task"], "--success", _rf(True, "--procedencia"), "declarada-no-despacho")
        rb = tool(B, "router", "outcome", ids["task"], "--success", "--procedencia", "declarada-no-despacho")
        strip = lambda R: [norm_ts({k: v for k, v in x.items() if k not in ("prev",)}) for x in router_lines(R)[n:]]  # noqa
        self.assert_same("cs-route outcome", ra, rb, strip(A), strip(B), A, B)

    def test_ca02_route_anular_en_igual_pt(self):
        src, ids = fresh_base()
        A, B = twin(src, "ca02ra")
        for R in (A, B):
            _dispatched(R, ids)
            tool_ok(R, "router", "outcome", ids["task"], "--success", "--procedencia", "declarada-no-despacho")
        n = len(router_lines(A))
        ra = tool(A, "router", "anular", "--at", router_lines(A)[-1]["at"], _rf(True, "--motivo"), "outcome errado da Ana")
        rb = tool(B, "router", "anular", "--at", router_lines(B)[-1]["at"], "--motivo", "outcome errado da Ana")
        strip = lambda R: [norm_ts({k: v for k, v in x.items() if k not in ("prev",)}) for x in router_lines(R)[n:]]  # noqa
        self.assert_same("cs-route anular", ra, rb, strip(A), strip(B), A, B)

    def test_ca02_pt_avisa_depreciacao(self):
        bad = []
        src, ids = fresh_base()
        cases = [("propose", "fresh", propose_args(ids["fea"])),
                 ("pause", "running", ["pause", "--motivo", "almoco da Ana"]),
                 ("escalate", "running", ["escalate", "--condicao", "material_ambiguity", "--no", "01"]),
                 ("plan add-node", "planning", node_args("add-node", "01", **N01))]
        for lab, stage, args in cases:
            R = clone(src, "ca02pt-" + _uniq("p")) if stage == "fresh" else auto_clone(stage, "ca02pt")[0]
            code, out, err = auto(R, *args)
            used = [a for a in args if a in AUTO_FLAGS]
            dl = " ".join(dep_lines(err))
            miss = [u for u in used if not re.search(re.escape(u) + r"(?![\w-])", dl)]
            if code != 0 or miss:
                bad.append("cs-auto %s → exit %d; sem aviso para %s; stderr=%r" % (lab, code, miss, err[-300:]))
        R = clone(src, "ca02pt-" + _uniq("r"))
        _dispatched(R, ids)
        code, out, err = tool(R, "router", "outcome", ids["task"], "--success", "--procedencia", "declarada-no-despacho")
        if code != 0 or not re.search(r"--procedencia(?![\w-])", " ".join(dep_lines(err))):
            bad.append("cs-route outcome --procedencia → exit %d; stderr=%r" % (code, err[-300:]))
        self.assertEqual(bad, [], "a flag pt deveria seguir aceita COM aviso no stderr:\n  " + "\n  ".join(bad))

    def test_ca02_help_so_en(self):
        root, _ = fresh_base()
        bad = []
        for path, ens in sorted(CA02_HELP.items()):
            code, out, err = tool(root, path[0], *(list(path[1:]) + ["--help"]))
            miss = [e for e in ens if not re.search(re.escape(e) + r"(?![\w-])", out)]
            pts = sorted(set(m.group(0) for m in PT_FLAG_RX.finditer(out)))
            if code != 0 or miss or pts:
                bad.append("%s %s --help → exit %d; en ausentes %s; pt presentes %s" % (
                    {"auto": "cs-auto", "router": "cs-route"}[path[0]], " ".join(path[1:]), code, miss, pts))
        self.assertEqual(bad, [], "o --help deveria trazer as flags en e nenhuma pt:\n  " + "\n  ".join(bad))

    def test_ca02_controle_par_pt_pt_e_deterministico(self):
        """calibração da comparação: propose, amend, plan, reflect, escalate, pause, resolve e cs-route outcome pela
        forma pt nos DOIS clones dão a mesma saída e o mesmo efeito (mandato, itens, ledger do roteador)."""
        src, ids = fresh_base()
        self._auto_pair("propose (pt×pt)", "fresh", lambda en, ids: propose_args(ids["fea"], en=en), en=False)
        self._auto_pair("amend (pt×pt)", "proposed", lambda en, ids: ["amend", "--by", HUMAN, "--orcamento", ORC2,
                                                                      "--reason", "mais folga para a Ana"], en=False)
        self.test_ca02_plan_add_edit_submit_en_igual_pt(en_a=False)
        tid = _auto_stage("reflect") and _TMP["reflect-task"]
        self._auto_pair("reflect (pt×pt)", "reflect", lambda en, ids: ["reflect", tid, "--texto", "faltou o OK da Ana",
                                                                       "--evidencia", "spec/feature.md:1"], en=False)
        self._auto_pair("escalate (pt×pt)", "running", lambda en, ids: ["escalate", "--condicao", "material_ambiguity",
                                                                        "--evidencia", "spec/feature.md:1", "--no",
                                                                        "01"], en=False)
        self._auto_pair("pause (pt×pt)", "running", lambda en, ids: ["pause", "--motivo", "almoco da Ana"], en=False)
        A, B = twin(src, "ca02ro-pp")
        for R in (A, B):
            _dispatched(R, ids)
        n = len(router_lines(A))
        ra = tool(A, "router", "outcome", ids["task"], "--success", "--procedencia", "declarada-no-despacho")
        rb = tool(B, "router", "outcome", ids["task"], "--success", "--procedencia", "declarada-no-despacho")
        strip = lambda R: [norm_ts({k: v for k, v in x.items() if k not in ("prev",)}) for x in router_lines(R)[n:]]  # noqa
        self.assert_same("cs-route outcome (pt×pt)", ra, rb, strip(A), strip(B), A, B)
        src2, _ = _auto_stage("proposed")
        A, B = twin(src2, "ca02ap-pp")
        ca, oa = approve(A, "--orcamento", ORC)
        cb, ob = approve(B, "--orcamento", ORC)
        self.assertEqual((ca, cb), (0, 0), oa[-800:] + ob[-800:])
        ma, mb = mandate(A), mandate(B)       # o approve grava atestado com sal aleatório: compara estado e orçamento
        self.assertEqual((ma.get("state"), ma.get("orcamento")), (mb.get("state"), mb.get("orcamento")),
                         "approve (pt×pt): estado/orçamento diferentes")

    def test_ca02_controle_chaves_internas_do_mandato_continuam(self):
        """D-20: as chaves internas do mandato não mudam (objetivo, criterios, regressao, portoes, orcamento...)."""
        root, _ = _auto_stage("proposed")
        m = mandate(root)
        for k in ("objetivo", "nos_estimados", "regressao", "criterios", "classe", "portoes", "orcamento"):
            self.assertIn(k, m, "chave interna do mandato %r sumiu (D-20)" % k)
        self.assertEqual(m["objetivo"], "Desconto da Ana")


# ================================================================================================ CA-03
def dep_line_problems(err, pairs, ignored=None):
    """critério do CA-03 sobre o stderr: exatamente UMA linha casando deprec|obsolet|descontinuad; ela traz cada par
    `pt → en` (ou `pt -> en`); com `ignored=<pt>`, ela cita esse pt e casa ignorad|ignored."""
    lines = dep_lines(err)
    if len(lines) != 1:
        return ["deveria haver UMA linha de depreciação no stderr; veio %d: %r" % (len(lines), err[-1200:])]
    P = ["a linha não lista `%s → %s`: %r" % (pt, en, lines[0]) for pt, en in pairs if not pair_text(pt, en).search(
        lines[0])]
    if ignored and not (re.search(re.escape(ignored) + r"(?![\w-])", lines[0]) and IGNORED.search(lines[0])):
        P.append("a linha deveria dizer que %s foi ignorado: %r" % (ignored, lines[0]))
    return P


def _one_dep_line(self, err, pairs, label, ignored=None):
    P = dep_line_problems(err, pairs, ignored)
    self.assertEqual(P, [], "%s: %s" % (label, "; ".join(P)))


class TestCA03(unittest.TestCase):
    def test_ca03_uma_linha_para_n_flags_pt_no_cs_state(self):
        root, ids = fresh("ca03a")
        code, out, err = st(root, "new", "task", *(_task_args(False, "Varias da Ana", "src/billing/q.py") +
                                                   ["--backlog"]))
        self.assertEqual(code, 0, out + err)
        pairs = [("--tipo", "--type"), ("--como", "--as-a"), ("--quero", "--i-want"), ("--para", "--so-that"),
                 ("--criterio", "--criterion"), ("--teste", "--proving-test")]
        _one_dep_line(self, err, pairs, "cs-state new task com 6 flags pt")

    def test_ca03_uma_linha_para_n_flags_pt_no_cs_auto(self):
        root, ids = fresh("ca03b")
        code, out, err = auto(root, *propose_args(ids["fea"]))
        self.assertEqual(code, 0, out + err)
        pairs = [(p, AUTO_FLAGS[p]) for p in ("--objetivo", "--nos", "--regressao", "--criterio", "--classe",
                                              "--portao")]
        _one_dep_line(self, err, pairs, "cs-auto propose com 6 flags pt")

    def test_ca03_en_vence_no_cs_state(self):
        root, ids = fresh("ca03c")
        code, out, err = st(root, "new", "epic", "--title", "Fiscal da Ana", "--objective", "nota-en", "--objetivo",
                            "nota-pt")
        self.assertEqual(code, 0, "pt e en juntos deveriam ser aceitos: %s%s" % (out, err))
        eid = CREATED_RE.findall(out)[0][0]
        self.assertEqual(item(root, eid)[2].get("objective"), "nota-en", "o en deveria vencer o pt")
        _one_dep_line(self, err, [], "cs-state new epic --objective + --objetivo", ignored="--objetivo")

    def test_ca03_en_vence_no_cs_auto(self):
        root, ids = fresh("ca03d")
        args = propose_args(ids["fea"], en=True) + ["--objetivo", "objetivo-pt da Ana"]
        code, out, err = auto(root, *args)
        self.assertEqual(code, 0, "pt e en juntos deveriam ser aceitos: %s%s" % (out, err))
        self.assertEqual(mandate(root).get("objetivo"), "Desconto da Ana", "o en (--objective) deveria vencer o pt")
        _one_dep_line(self, err, [], "cs-auto propose --objective + --objetivo", ignored="--objetivo")

    def test_ca03_flag_pt_com_igual(self):
        root, ids = fresh("ca03e")
        code, out, err = st(root, "new", "epic", "--title", "Igual da Ana", "--objetivo=pix", "--metrica=conversao")
        self.assertEqual(code, 0, out + err)
        eid = CREATED_RE.findall(out)[0][0]
        d = item(root, eid)[2]
        self.assertEqual((d.get("objective"), d.get("metric")), ("pix", "conversao"))
        _one_dep_line(self, err, [("--objetivo", "--objective"), ("--metrica", "--metric")],
                      "cs-state new epic --objetivo=pix --metrica=conversao")

    def test_ca03_no_do_escalate_vira_node(self):
        root, _ = auto_clone("running", "ca03f")
        code, out, err = auto(root, "escalate", "--condicao", "material_ambiguity", "--no", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(mandate(root)["escaladas"][-1].get("no"), "01")
        _one_dep_line(self, err, [("--condicao", "--condition"), ("--no", "--node")], "cs-auto escalate --no 01")

    def test_ca03_controle_criterio_da_linha_unica(self):
        """calibração do critério: a forma boa passa; a de hoje (uma linha por flag), a vazia e a sem `ignorad`
        reprovam."""
        pairs = [("--tipo", "--type"), ("--criterio", "--criterion")]
        good = "cs-state: aviso: flags depreciadas (obsoletas): --tipo → --type, --criterio → --criterion\n"
        self.assertEqual(dep_line_problems(good, pairs), [])
        self.assertEqual(dep_line_problems("x: aviso: depreciada: --tipo -> --type; --criterio -> --criterion", pairs),
                         [])
        today = ("cs-state: aviso: --tipo está depreciada (obsoleta); use --type\n"
                 "cs-state: aviso: --criterio está depreciada (obsoleta); use --criterion\n")
        self.assertTrue(dep_line_problems(today, pairs))
        self.assertTrue(dep_line_problems("", pairs))
        both = "aviso: depreciada: --objetivo → --objective (ignorada: --objective também foi dado e vale)"
        self.assertEqual(dep_line_problems(both, [], ignored="--objetivo"), [])
        self.assertTrue(dep_line_problems("aviso: depreciada: --objetivo → --objective", [], ignored="--objetivo"))

    def test_ca03_controle_prefixo_no_dash_nao_e_alias(self):
        """controle: `--no-settings`/`--no-makefile` do `harness install` não são o `--no` do escalate."""
        root, _ = fresh("ca03g")
        code, out, err = cs(SKILL, root, "harness", "install", "--dry-run", "--no-settings", "--no-makefile")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(dep_lines(err), [], "prefixo --no-* não pode virar aviso de depreciação")
        self.assertNotIn("--node", out + err)


# ================================================================================================ CA-04
def marker_base():
    """repo da fixture do emit com um sinal de OUTRO harness (.claude/kernel/), ainda sem init."""
    if "marker" not in _TMP:
        code = ("import sys; sys.dont_write_bytecode=True; sys.path.insert(0, %r); sys.path.insert(0, %r);"
                "import fixture; print(fixture.make_repo())"
                % (os.path.join(SKILL, "scripts"), os.path.join(SKILL, "scripts", "emit", "tests")))
        rc, out, err = _run([sys.executable, "-c", code], _base_tmp())
        if rc != 0:
            raise AssertionError("fixture do emit: %s%s" % (out, err))
        dest = os.path.join(_base_tmp(), "base-marcador")
        shutil.move(out.strip().splitlines()[-1], dest)
        write(dest, ".claude/kernel/tech-lead.md", "# kernel de outro harness da Ana\n")
        git(dest, "init", "-q")
        git(dest, "add", "-A")
        git(dest, "commit", "-q", "-m", "repo com outro harness")
        _TMP["marker"] = dest
    return _TMP["marker"]


def events_path_problems(out):
    """critério do CA-04 (plano): cita `.swarm/events.jsonl` e TODA citação de `events.jsonl` é esse caminho (nem
    `events.jsonl` solto, nem `state/events.jsonl`)."""
    P = []
    if ".swarm/events.jsonl" not in out:
        P.append("o plano do upgrade deveria citar .swarm/events.jsonl")
    bad = [m.group(0) for m in re.finditer(r"[^\s(`'\"]*events\.jsonl", out)
           if not m.group(0).endswith(".swarm/events.jsonl")]
    if bad:
        P.append("log de eventos citado fora do caminho exato .swarm/events.jsonl: %s" % bad)
    return P


INCLUDE = "--include-emitted"
ALLOW = "--allow-outside"


class TestCA04(PairMixin, unittest.TestCase):
    def _pair_cs(self, label, src, pre, args, view=outside_view, flag_a=INCLUDE):
        A, B = twin(src, "ca04")
        for R in (A, B):
            pre(R)
        ra = cs(SKILL, A, *(args + [flag_a]))
        rb = cs(SKILL, B, *(args + [ALLOW]))
        self.assert_same(label, ra, rb, view(A), view(B), A, B)
        return A, B

    def test_ca04_emit_include_emitted_igual_alias(self):
        A, B = self._pair_cs("cs.py emit", fresh_base()[0],
                             lambda R: os.remove(os.path.join(R, ".claude", "orchestrator.md")), ["emit"])
        self.assertTrue(os.path.isfile(os.path.join(A, ".claude", "orchestrator.md")), "emit não reescreveu fora")

    def test_ca04_harness_install_include_emitted_igual_alias(self):
        A, B = self._pair_cs("cs.py harness install", fresh_base()[0],
                             lambda R: os.remove(os.path.join(R, ".claude", "hooks", "cs-guard.sh")),
                             ["harness", "install"])
        self.assertTrue(os.path.isfile(os.path.join(A, ".claude", "hooks", "cs-guard.sh")))

    def test_ca04_upgrade_apply_include_emitted_igual_alias(self):
        self._pair_cs("cs.py upgrade --apply", legacy_0140()[0], lambda R: None, ["upgrade", "--apply"])

    def test_ca04_init_replace_harness_include_emitted_igual_alias(self):
        A, B = self._pair_cs("cs.py init --replace-harness", marker_base(), lambda R: None,
                             ["init", "--platforms", "claude-code", "--replace-harness"])
        self.assertFalse(os.path.isdir(os.path.join(A, ".claude", "kernel")), "o outro harness deveria sair")

    def _refusal(self, root, args, label):
        code, out, err = cs(SKILL, root, *args)
        self.assertNotEqual(code, 0, "%s sem a flag deveria recusar a escrita fora de .swarm/: exit 0\n%s%s"
                            % (label, out[-1500:], err[-1500:]))
        self.assertRegex(out + err, re.escape(INCLUDE) + r"(?![\w-])",
                         "%s: a recusa deveria citar --include-emitted:\n%s" % (label, (out + err)[-1500:]))

    def test_ca04_recusa_do_emit_cita_include_emitted(self):
        root, _ = fresh("ca04r1")
        os.remove(os.path.join(root, ".claude", "orchestrator.md"))
        self._refusal(root, ["emit"], "cs.py emit")

    def test_ca04_recusa_do_harness_install_cita_include_emitted(self):
        root, _ = fresh("ca04r2")
        os.remove(os.path.join(root, ".claude", "hooks", "cs-guard.sh"))
        self._refusal(root, ["harness", "install"], "cs.py harness install")

    def test_ca04_recusa_do_upgrade_cita_include_emitted(self):
        root, _ = legacy_clone("ca04r3")
        self._refusal(root, ["upgrade", "--apply"], "cs.py upgrade --apply")

    def test_ca04_recusa_do_replace_harness_cita_include_emitted(self):
        root = clone(marker_base(), "marcador-" + _uniq("r4"))
        self._refusal(root, ["init", "--platforms", "claude-code", "--replace-harness"], "cs.py init --replace-harness")

    def test_ca04_allow_outside_avisa_depreciacao(self):
        root, _ = fresh("ca04d")
        os.remove(os.path.join(root, ".claude", "orchestrator.md"))
        code, out, err = cs(SKILL, root, "emit", ALLOW)
        self.assertEqual(code, 0, out + err)
        self.assertTrue([ln for ln in dep_lines(err) if ALLOW in ln],
                        "--allow-outside deveria seguir aceito COM aviso de depreciação no stderr: %r" % err[-800:])

    def test_ca04_plano_do_upgrade_cita_swarm_events_jsonl(self):
        root, _ = legacy_clone("ca04p")
        code, out, err = cs(SKILL, root, "upgrade")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(events_path_problems(out), [], "plano do upgrade:\n" + out)

    def test_ca04_recusa_do_upgrade_de_0131_cita_include_emitted(self):
        """alvo 0.13.1 (há o que atualizar também no HEAD): `upgrade --apply` sem a flag recusa citando a flag nova."""
        root = clone(legacy_0131()[0], "l0131-" + _uniq("r5"))
        self._refusal(root, ["upgrade", "--apply"], "cs.py upgrade --apply (alvo 0.13.1)")

    def test_ca04_plano_do_upgrade_de_0131_cita_swarm_events_jsonl(self):
        """alvo 0.13.1: o plano (`cs.py upgrade`) cita o log de eventos pelo caminho exato `.swarm/events.jsonl`."""
        root = clone(legacy_0131()[0], "l0131-" + _uniq("p2"))
        code, out, err = cs(SKILL, root, "upgrade")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(events_path_problems(out), [], "plano do upgrade:\n" + out)

    def test_ca04_controle_par_allow_allow_e_deterministico(self):
        """calibração da comparação: emit e upgrade --apply (alvo 0.13.1) com --allow-outside nos DOIS clones dão a
        mesma saída e o mesmo disco fora de .swarm/ (a forma boa conhecida passa)."""
        self._pair_cs("cs.py emit (allow×allow)", fresh_base()[0],
                      lambda R: os.remove(os.path.join(R, ".claude", "orchestrator.md")), ["emit"], flag_a=ALLOW)
        self._pair_cs("cs.py upgrade --apply 0.13.1 (allow×allow)", legacy_0131()[0], lambda R: None,
                      ["upgrade", "--apply"], flag_a=ALLOW)

    def test_ca04_controle_allow_outside_continua_escrevendo(self):
        root, _ = fresh("ca04c")
        os.remove(os.path.join(root, ".claude", "orchestrator.md"))
        cs_ok(SKILL, root, "emit", ALLOW)
        self.assertTrue(os.path.isfile(os.path.join(root, ".claude", "orchestrator.md")))

    def test_ca04_controle_plano_da_0140_cita_events_sem_caminho(self):
        """controle: o plano da 0.14.0 (num alvo 0.13.1) cita `events.jsonl` sem `.swarm/` — o D acima mede algo."""
        src, _ = legacy_0131()
        root = clone(src, "l0131-" + _uniq("plano"))
        out = cs_ok(old_skill(), root, "upgrade")
        self.assertTrue(events_path_problems(out), out)
        self.assertEqual(events_path_problems("board e eventos (.swarm/state/board.json, .swarm/events.jsonl)"), [])
        self.assertTrue(events_path_problems("eventos em .swarm/events.jsonl e state/events.jsonl"))
        self.assertTrue(events_path_problems(""))


# ================================================================================================ CA-05
class TestCA05(unittest.TestCase):
    def _none(self, hits, what):
        self.assertEqual(hits, [], "%s cita flag pt (%d):\n  %s" % (what, len(hits), "\n  ".join(hits[:40])))

    def test_ca05_textos_emitidos_sem_flag_pt(self):
        root, _ = fresh_base()
        self._none(emitted_hits(root), "texto emitido no alvo")

    def test_ca05_skill_e_modo_de_uso_sem_flag_pt(self):
        self._none(scan_skill(SKILL)["SKILL.md+MODO-DE-USO.md"], "SKILL.md/MODO-DE-USO.md")

    def test_ca05_references_sem_flag_pt(self):
        self._none(scan_skill(SKILL)["references (fora migrations.json5)"], "references/")

    def test_ca05_docs_sem_flag_pt(self):
        self._none(scan_skill(SKILL)["docs (*.md)"], "docs/")

    def test_ca05_templates_sem_flag_pt(self):
        self._none(scan_skill(SKILL)["assets/templates"], "assets/templates/ (fonte dos textos emitidos)")

    def test_ca05_dicas_e_recusas_do_codigo_sem_flag_pt(self):
        self._none(scan_skill(SKILL)["código (dicas/recusas)"], "string do código (dica/recusa)")

    def test_ca05_recusa_do_dor_cita_criterion(self):
        """US sem critério e sem história (como/quero/para): a recusa do DoR estático (`new task`/`new story`) cita
        --criterion e nenhuma flag pt."""
        root, ids = fresh("ca05dor")
        base = ["--type", "US", "--title", "Sem criterio da Ana", "--allowed-path", "src/billing/q.py",
                "--verify-cmd", VERIFY]
        for args in (["new", "task"] + base + ["--agent", AGENT, "--sprint", ids["spr"]],
                     ["new", "story"] + base + ["--agents", AGENT, "--feature", ids["fea"]]):
            code, out, err = st(root, *args)
            txt = out + err
            self.assertNotEqual(code, 0, "%s de US sem critério deveria recusar (DoR): %s" % (args[1], txt))
            self.assertRegex(txt, r"--criterion(?![\w-])", "a recusa do DoR (%s) deveria citar --criterion:\n%s"
                             % (args[1], txt))
            self.assertEqual(sorted(set(m.group(0) for m in PT_FLAG_RX.finditer(txt))), [],
                             "a recusa do DoR (%s) cita flag pt:\n%s" % (args[1], txt))

    def test_ca05_controle_varredura_acha_flag_pt_na_0140(self):
        """controle: a mesma varredura acha citações pt na skill 0.14.0 e nos textos emitidos por ela."""
        got = scan_skill(old_skill())
        empty = [k for k, v in got.items() if not v]
        self.assertEqual(empty, [], "a varredura deveria achar flag pt na 0.14.0 em todas as categorias")
        self.assertTrue(emitted_hits(legacy_0140()[0]), "textos emitidos pela 0.14.0 têm flag pt")

    def test_ca05_controle_criterio_da_tabela_de_alias(self):
        """controle do critério mecânico: tabela de alias isenta; dica com flag pt reprova."""
        self.assertEqual(line_hits("x.md", 1, "| `--objetivo` | `--objective` | depreciada |"), [])
        self.assertTrue(line_hits("x.md", 1, "| `--objetivo` | texto sem o en |"))
        self.assertTrue(line_hits("x.md", 1, "use cs-state new epic --objetivo X"))
        self.assertEqual(line_hits("x.md", 1, "cs.py harness install --no-settings"), [])
        self.assertEqual(code_string_hits('T = {"--objetivo": "--objective", "--no": "--node"}\n', "t.py"), [])
        self.assertTrue(code_string_hits('raise X("use --criterio AC-1|...")\n', "t.py"))
        self.assertTrue(code_string_hits('x = f"US sem --como {k}"\n', "t.py"))
        self.assertEqual(code_string_hits('def f():\n    """--objetivo é alias de --objective."""\n', "t.py"), [])


# ================================================================================================ CA-06
def skill_copy(name):
    dst = os.path.join(_base_tmp(), name)
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(SKILL, dst, symlinks=True, ignore=shutil.ignore_patterns(
        ".git", "__pycache__", "local", "dist", "campanhas", ".claude"))
    return dst


def doctest_run(skill):
    return _run([sys.executable, "-B", "-m", "unittest", "discover", "-s",
                 os.path.join(skill, "scripts", "doctests", "tests"), "-p", "test_commands_parse.py"], skill)


def inject(skill, line):
    p = os.path.join(skill, "assets", "templates", "state", "auto-plan.md")
    with open(p, "a", encoding="utf-8") as f:
        f.write("\n" + line + "\n")


class TestCA06(unittest.TestCase):
    def test_ca06_doctest_reprova_citacao_invalida_do_cs_auto(self):
        d = skill_copy("skill-ca06-auto")
        inject(d, "Rode `.swarm/bin/cs-auto plan add-node --id 01 --flag-da-ana-inexistente x` (citação inválida).")
        code, out, err = doctest_run(d)
        self.assertNotEqual(code, 0, "o doctest de comandos deveria conferir o cs-auto e reprovar a citação com flag "
                                     "inexistente; passou:\n%s" % (out + err)[-1500:])
        self.assertIn("flag-da-ana-inexistente", out + err)

    def test_ca06_controle_doctest_reprova_citacao_invalida_do_cs_state(self):
        """controle: a injeção é lida pelo doctest (o cs-state já é conferido no HEAD)."""
        d = skill_copy("skill-ca06-state")
        inject(d, "Rode `.swarm/bin/cs-state new task --flag-da-ana-inexistente x` (citação inválida).")
        code, out, err = doctest_run(d)
        self.assertNotEqual(code, 0, (out + err)[-1500:])
        self.assertIn("flag-da-ana-inexistente", out + err)

    def test_ca06_controle_doctest_passa_na_skill(self):
        """todo comando citado nos textos da skill sob teste parseia contra o argparse real (doctest do produto)."""
        code, out, err = doctest_run(skill_copy("skill-ca06-limpa"))
        self.assertEqual(code, 0, (out + err)[-3000:])


# ================================================================================================ CA-07
CA07_CMDS = {
    "epic": lambda ids: ["new", "epic", "--title", "Fiscal da Ana", "--objetivo", "nota"],
    "sprint": lambda ids: ["new", "sprint", "--meta", "fiscal da Ana"],
    "feature": lambda ids: ["new", "feature", "--title", "Nota da Ana", "--sprint", ids["spr"], "--aceite", ACEITE],
    "task": lambda ids: ["new", "task"] + _us_pt("Dry da Ana", "src/billing/q.py", "--sprint", ids["spr"]),
    "story": lambda ids: ["new", "story", "--tipo", "US", "--title", "Story da Ana", "--feature", ids["fea"],
                          "--agents", AGENT, "--agents", OTHER, "--allowed-path", "src/billing/q.py", "--verify-cmd",
                          VERIFY, "--como", "cliente", "--quero", "x", "--para", "y", "--criterio", C1],
}
CONTRACT = ("ids", "criar", "mover", "eventos")


def _dry(kind):
    """(saída JSON do --dry-run, snapshot antes, snapshot depois, item gravado pelo mesmo comando sem --dry-run)."""
    key = "dry-" + kind
    if key not in _TMP:
        src, ids = fresh_base()
        A, B = twin(src, "ca07" + kind)
        s0 = snapshot(A)
        code, out, err = st(A, *(CA07_CMDS[kind](ids) + ["--dry-run"]))
        s1 = snapshot(A)
        if code != 0:
            raise AssertionError("new %s --dry-run → %d: %s%s" % (kind, code, out, err))
        dry = json.loads(out)
        real = new_id(B, *CA07_CMDS[kind](ids)[1:])
        got = item(B, real)
        _TMP[key] = (dry, s0, s1, real, got, os.path.relpath(got[1], B).replace(os.sep, "/"))
    return _TMP[key]


def _file_form(d):
    return norm_ts({k: v for k, v in d.items() if k not in ("_generated_by", "status")})


def dry_item_problems(dry, real, disk):
    """critério do CA-07: fora de {ids, criar, mover, eventos}, algum dict com `id` = o id criado e `kind`, igual ao
    arquivo gravado pelo mesmo comando sem --dry-run (sem `_generated_by`/`status`, timestamps normalizados)."""
    if not isinstance(dry, dict) or (dry.get("ids") or [None])[0] != real:
        return ["o dry-run e o comando real deveriam dar o mesmo id (%s): %s" % (real, str(dry)[:300])]
    cands = [x for k, v in dry.items() if k not in CONTRACT for x in walk_dicts(v)
             if isinstance(x, dict) and x.get("id") == real and x.get("kind")]
    if not cands:
        return ["o dry-run deveria trazer o item %s que seria gravado (fora de %s): %s"
                % (real, CONTRACT, json.dumps(dry, ensure_ascii=False)[:800])]
    want = _file_form(disk)
    if want not in [_file_form(c) for c in cands]:
        return ["o item do dry-run deveria ter a mesma forma (chaves en) do arquivo gravado:\n  dry=%s\n  arq=%s"
                % (json.dumps(_file_form(cands[0]), ensure_ascii=False)[:900],
                   json.dumps(want, ensure_ascii=False)[:900])]
    return []


class TestCA07(unittest.TestCase):
    def _item_shown(self, kind):
        dry, s0, s1, real, (zone, path, disk), rel = _dry(kind)
        P = dry_item_problems(dry, real, disk)
        self.assertEqual(P, [], "new %s --dry-run: %s" % (kind, "; ".join(P)))

    def test_ca07_controle_criterio_do_item(self):
        """calibração: a saída de hoje (sem o item) e a vazia reprovam; a saída boa conhecida (a de hoje + o item
        com a forma do arquivo) passa; item com chave pt reprova."""
        dry, s0, s1, real, (zone, path, disk), rel = _dry("task")
        self.assertTrue(dry_item_problems(dry, real, disk))
        self.assertTrue(dry_item_problems({}, real, disk))
        good = dict(dry)
        good["item"] = {k: v for k, v in disk.items() if k not in ("_generated_by", "status")}
        self.assertEqual(dry_item_problems(good, real, disk), [])
        bad = dict(dry)
        bad["item"] = dict(good["item"])
        bad["item"]["tipo"] = bad["item"].pop("type")
        self.assertTrue(dry_item_problems(bad, real, disk))

    def test_ca07_dry_run_epic_mostra_o_item(self):
        self._item_shown("epic")

    def test_ca07_dry_run_sprint_mostra_o_item(self):
        self._item_shown("sprint")

    def test_ca07_dry_run_feature_mostra_o_item(self):
        self._item_shown("feature")

    def test_ca07_dry_run_task_mostra_o_item(self):
        self._item_shown("task")

    def test_ca07_dry_run_story_mostra_o_item(self):
        self._item_shown("story")

    def test_ca07_controle_dry_run_nao_escreve(self):
        bad = [k for k in sorted(CA07_CMDS) if _dry(k)[1] != _dry(k)[2]]
        self.assertEqual(bad, [], "o --dry-run escreveu no alvo: %s" % bad)

    def test_ca07_controle_contrato_ids_criar_mover_eventos(self):
        for k in sorted(CA07_CMDS):
            dry, _, _, real, _, rel = _dry(k)
            for c in CONTRACT:
                self.assertIn(c, dry, "new %s --dry-run perdeu `%s`" % (k, c))
            self.assertIn(real, dry["ids"], "new %s --dry-run: ids" % k)
            self.assertIn(rel, dry["criar"], "new %s --dry-run: criar deveria listar %s" % (k, rel))


# ================================================================================================ CA-08
TOP_PT = {"tipo", "como", "quero", "para", "criterios", "teste", "reproducao", "motivo", "aceite", "epico",
          "objetivo", "metrica", "meta", "reaberta", "reaberturas", "historico"}
CRIT_PT, HIST_PT = {"teste"}, {"acao", "de", "para"}
CLOSED_PT, CLOSED_METRICS_PT = {"entregue", "devolvido", "metricas", "origem"}, {"tentativas", "status_m2"}
assert TOP_PT | CRIT_PT | HIST_PT | CLOSED_PT | CLOSED_METRICS_PT == ITEM_PT_KEYS


def _closed_pt(c, where):
    bad = []
    if isinstance(c, dict):
        bad += ["%s.%s" % (where, k) for k in c if k in CLOSED_PT]
        for mk in ("metricas", "metrics"):
            if isinstance(c.get(mk), dict):
                bad += ["%s.%s.%s" % (where, mk, k) for k in c[mk] if k in CLOSED_METRICS_PT]
    return bad


def item_pt_paths(it, where):
    """chaves pt da forma interna (ITEM_SCHEMA da 0.14.0, por caminho) e `kind: "epico"` num item."""
    if not isinstance(it, dict):
        return []
    bad = ["%s.%s" % (where, k) for k in it if k in TOP_PT]
    if it.get("kind") == "epico":
        bad.append('%s.kind="epico"' % where)
    for ck in ("criterios", "acceptance_criteria"):
        for i, c in enumerate(it.get(ck) or []):
            if isinstance(c, dict):
                bad += ["%s.%s[%d].%s" % (where, ck, i, k) for k in c if k in CRIT_PT]
    for hk in ("historico", "history"):
        for i, h in enumerate(it.get(hk) or []):
            if isinstance(h, dict):
                bad += ["%s.%s[%d].%s" % (where, hk, i, k) for k in h if k in HIST_PT]
    bad += _closed_pt(it.get("closed"), where + ".closed")
    for rk in ("reaberturas", "reopenings"):
        for i, r in enumerate(it.get(rk) or []):
            if isinstance(r, dict):
                bad += _closed_pt(r.get("closed"), "%s.%s[%d].closed" % (where, rk, i))
    return bad


def session_pt_paths(rec, where):
    if not isinstance(rec, dict):
        return []
    bad = ["%s.%s" % (where, k) for k in rec if k == "blocos"]
    for bk in ("blocos", "blocks"):
        for i, b in enumerate(rec.get(bk) or []):
            if isinstance(b, dict):
                bad += ["%s.%s[%d].%s" % (where, bk, i, k) for k in b if k in ("titulo", "linhas")]
    return bad


MEASURE = r'''
import json, os, sys
sys.dont_write_bytecode = True
root, out = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(root, ".swarm", "harness"))
import hcore
res = {}
b = hcore.load_board(root)
res["tree"] = b.get("tree") or {}
res["sessions"] = b.get("sessions") or []
import session
p, rec = session.last_stamp(root)
res["stamp"] = rec
events, cerr, _ = hcore.read_chain(os.path.join(root, ".swarm", "events.jsonl"))
res["chain_err"] = cerr
res["n_events"] = len(events)
try:
    import validate as V
    legacy, _ = V.legacy_acks(events)
except Exception:
    legacy = {}
rp = hcore.new_board()
res["replay_err"] = None
try:
    for ev in (events[1:] if events and events[0].get("type") == "init" else events):
        try:
            hcore.apply_ops(rp, ev.get("ops") or [], check_legal=True, legacy=legacy.get(ev.get("seq")))
        except TypeError:
            hcore.apply_ops(rp, ev.get("ops") or [])
except Exception as e:
    res["replay_err"] = "%s: %s" % (type(e).__name__, e)
res["replay_tree"] = rp.get("tree") or {}
res["tree_as_en"] = dict((k, hcore.item_to_en(v)) for k, v in res["tree"].items())
with open(out, "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False, sort_keys=True)
'''


def measure(root):
    """forma interna pelo motor INSTALADO no alvo (subprocesso com sys.path = <alvo>/.swarm/harness)."""
    out = os.path.join(_base_tmp(), "medida-%s.json" % _uniq("m"))
    code, o, e = _run([sys.executable, "-B", "-c", MEASURE, root, out], root)
    if code != 0:
        raise AssertionError("medição da forma interna (hcore.load_board do motor do alvo) falhou: %s%s" % (o, e))
    with open(out, encoding="utf-8") as f:
        return json.load(f)


DEF_RX = re.compile(r"^\s*def ([A-Za-z_0-9]+)", re.M)


def defs_by_file(skill):
    """{scripts/<rel>.py: {nomes de def}} fora de testes (pastas tests/, test_*.py)."""
    key = "defs-" + skill
    if key not in _TMP:
        got = {}
        base = os.path.join(skill, "scripts")
        for d, dns, fns in os.walk(base):
            dns[:] = [x for x in dns if x not in ("tests", "__pycache__")]
            for f in fns:
                if f.endswith(".py") and not f.startswith("test_"):
                    p = os.path.join(d, f)
                    got[os.path.relpath(p, skill)] = set(DEF_RX.findall(read_text(p)))
        _TMP[key] = got
    return _TMP[key]


def canon(x):
    return json.dumps(x, sort_keys=True, ensure_ascii=False)


def tput_items(root, since=0):
    out = []
    for ln in read_text(os.path.join(root, SD, "events.jsonl")).splitlines()[since:]:
        ev = json.loads(ln)
        for op in ev.get("ops") or []:
            if op and op[0] == "tput" and len(op) > 3:
                out.append((ev.get("seq"), op[1], op[3]))
    return out


def ca08_state():
    """alvo 0.14.0 legado: a forma interna medida pelo motor 0.14.0 e, num clone, pelo motor da skill sob teste
    (instalado pelo `upgrade --apply --allow-outside`, o caminho oficial; no HEAD a 0.14.0 diz 'nada a fazer')."""
    if "ca08" not in _TMP:
        src, ids = legacy_0140()
        old = measure(src)
        root = clone(src, "ca08-atualizado")
        cs_ok(SKILL, root, "upgrade", "--apply", ALLOW)
        a = read_bytes(os.path.join(root, SD, "harness", "hcore.py"))
        b = read_bytes(os.path.join(SKILL, "scripts", "harness", "engine", "hcore.py"))
        if a != b:
            raise AssertionError("fixture: o motor instalado no alvo não é o da skill sob teste (hcore.py difere)")
        _TMP["ca08"] = (src, root, ids, old, measure(root))
    return _TMP["ca08"]


class TestCA08(unittest.TestCase):
    def test_ca08_arvore_em_memoria_sem_chave_pt(self):
        src, root, ids, old, new = ca08_state()
        bad = []
        for iid, it in sorted(new["tree"].items()):
            bad += item_pt_paths(it, iid)
        self.assertEqual(bad, [], "itens da árvore em memória com chave pt / kind epico (%d):\n  %s"
                         % (len(bad), "\n  ".join(bad[:40])))

    def test_ca08_sessao_em_memoria_sem_chave_pt(self):
        src, root, ids, old, new = ca08_state()
        self.assertIsInstance(new["stamp"], dict, "pré-condição: o alvo tem carimbo de sessão")
        bad = session_pt_paths(new["stamp"], "carimbo")
        for i, s in enumerate(new["sessions"]):
            bad += session_pt_paths(s, "sessions[%d]" % i)
        self.assertEqual(bad, [], "sessão em memória com chave pt: %s" % bad)

    def test_ca08_replay_do_historico_pt_sem_chave_pt_e_igual(self):
        src, root, ids, old, new = ca08_state()
        self.assertIsNone(new["replay_err"], "replay do events.jsonl legado falhou: %s" % new["replay_err"])
        self.assertEqual(canon(new["replay_tree"]), canon(new["tree"]), "replay ≠ projeção carregada")
        bad = []
        for iid, it in sorted(new["replay_tree"].items()):
            bad += item_pt_paths(it, iid)
        self.assertEqual(bad, [], "replay do histórico pt com chave pt em memória (%d):\n  %s"
                         % (len(bad), "\n  ".join(bad[:40])))

    def test_ca08_estado_igual_ao_da_0140_em_ingles(self):
        """o que a 0.14.0 tinha em memória, traduzido pelo próprio item_to_en dela, É a memória do motor novo."""
        src, root, ids, old, new = ca08_state()
        diff = sorted(k for k in set(old["tree_as_en"]) | set(new["tree"])
                      if canon(old["tree_as_en"].get(k)) != canon(new["tree"].get(k)))
        self.assertEqual(diff, [], "itens cuja forma em memória ≠ a da 0.14.0 em inglês: %s\n  ex.: 0.14.0=%s\n  nova=%s"
                         % (diff, canon(old["tree_as_en"].get(diff[0]) if diff else None)[:600],
                            canon(new["tree"].get(diff[0]) if diff else None)[:600]))

    def test_ca08_eventos_novos_gravam_item_en(self):
        src, root0, ids, old, new = ca08_state()
        root = clone(root0, "ca08-eventos-" + _uniq("e"))
        n = len(read_text(os.path.join(root, SD, "events.jsonl")).splitlines())
        new_id(root, "epico", "--title", "Nova da Ana", "--objetivo", "frete")
        tid = new_id(root, "task", *_us_pt("Nova task da Ana", "src/billing/taxa.py", "--sprint", ids["spr"]))
        st_ok(root, "start", tid)
        puts = tput_items(root, n)
        self.assertTrue(puts, "pré-condição: os comandos gravaram eventos tput")
        bad = []
        for seq, iid, it in puts:
            bad += item_pt_paths(it, "seq %s %s" % (seq, iid))
        self.assertEqual(bad, [], "evento novo grava o item com chave pt (%d):\n  %s" % (len(bad), "\n  ".join(bad[:40])))
        m = measure(root)
        self.assertIsNone(m["replay_err"], "replay misto (pt antigo + en novo) falhou: %s" % m["replay_err"])
        self.assertEqual(canon(m["replay_tree"]), canon(m["tree"]), "replay misto ≠ projeção")

    def test_ca08_controle_criterio_forma_do_arquivo_passa(self):
        """calibração: a forma en do disco (itens e carimbo gravados pela skill) passa no critério; a forma interna
        pt reprova."""
        root, ids = fresh_base()
        bad = []
        for iid, (z, p, d) in sorted(all_items(root).items()):
            bad += item_pt_paths({k: v for k, v in d.items() if k not in ("_generated_by", "status")}, iid)
        self.assertEqual(bad, [])
        src, _ = legacy_0140()
        sd = os.path.join(src, SD, "state", "sessoes")
        stamps = [load_any(os.path.join(sd, f)) for f in sorted(os.listdir(sd)) if f.endswith(".json")]
        self.assertTrue(stamps, "fixture sem carimbo .json")
        self.assertEqual(session_pt_paths(stamps[-1], "arquivo"), [])
        self.assertTrue(item_pt_paths({"id": "X", "kind": "epico", "historico": [{"acao": "criado"}]}, "X"))
        self.assertTrue(session_pt_paths({"blocos": [{"titulo": "a", "linhas": []}]}, "s"))

    def test_ca08_controle_historico_legado_tem_chave_pt(self):
        """controle: o events.jsonl do alvo legado tem `tput` com chaves pt e `kind: "epico"` (o D acima mede algo)."""
        src, ids = legacy_0140()
        bad = []
        for seq, iid, it in tput_items(src):
            bad += item_pt_paths(it, iid)
        self.assertTrue(any(".kind=" in b for b in bad), "fixture sem tput de épico com kind epico")
        self.assertTrue(any(b.endswith(".historico") for b in bad), "fixture sem tput com historico")

    def test_ca08_controle_nenhum_def_removido(self):
        """RNF-03: todo `def` de scripts/**/*.py (fora de testes) da 0.14.0 segue no mesmo arquivo (mesma regra do
        portão: nome do def por arquivo); `item_to_pt` e `session_to_pt` ficam no hcore."""
        old, new = old_skill(), SKILL
        bad = []
        for rel, names in sorted(defs_by_file(old).items()):
            miss = sorted(names - defs_by_file(new).get(rel, set()))
            if miss:
                bad.append("%s: %s" % (rel, ", ".join(miss)))
        self.assertEqual(bad, [], "def removido em relação à 0.14.0:\n  " + "\n  ".join(bad))
        self.assertTrue({"item_to_pt", "session_to_pt"} <= defs_by_file(new).get(
            os.path.join("scripts", "harness", "engine", "hcore.py"), set()))

    def test_ca08_controle_arquivo_do_item_igual_ao_da_0140(self):
        """mesmas operações na 0.14.0 real e na skill sob teste: cada arquivo de item é o mesmo texto (só os
        timestamps ISO normalizados)."""
        texts = []
        for base in (fresh_old_base, fresh_base):
            src, ids = base()
            root = clone(src, "ca08-bytes-" + _uniq("b"))
            st_ok(root, "move", ids["bkl"], "--avulsa")
            _pre_close(root, ids)
            st_ok(root, "close", ids["fea"], "--summary", "fim da Ana", "--devolver", "--reason", "fora do escopo")
            new_id(root, "task", "--tipo", "BUG", "--agent", AGENT, "--title", "Bug da Ana", "--allowed-path",
                   "src/billing/bug.py", "--verify-cmd", VERIFY, "--reproducao", "tests.test_red", "--sprint",
                   ids["spr"])
            texts.append(dict((norm_text(os.path.relpath(p, root)), norm_text(read_text(p)))
                              for _, (z, p, d) in all_items(root).items()))
        old, new = texts
        self.assertEqual(sorted(old), sorted(new), "conjunto de arquivos de item diferente da 0.14.0")
        diff = [k for k in sorted(old) if old[k] != new[k]]
        self.assertEqual(diff, [], "arquivo do item ≠ o da 0.14.0 para a mesma operação: %s\n--- 0.14.0\n%s\n--- nova\n%s"
                         % (diff, old[diff[0]][:1200] if diff else "", new[diff[0]][:1200] if diff else ""))


# ================================================================================================ CA-09
def ca09_state():
    if "ca09" not in _TMP:
        src, ids = legacy_0140()
        root = clone(src, "ca09-atualizado")
        r = {"root": root, "ids": ids, "events0": read_bytes(os.path.join(root, SD, "events.jsonl")),
             "kind0": item(root, ids["epc"])[2].get("kind")}
        r["apply"] = cs(SKILL, root, "upgrade", "--apply", INCLUDE)
        _TMP["ca09"] = r
    return _TMP["ca09"]


class TestCA09(unittest.TestCase):
    def _applied(self):
        r = ca09_state()
        code, out, err = r["apply"]
        self.assertEqual(code, 0, "upgrade --apply --include-emitted no alvo 0.14.0 deveria sair 0:\n%s%s"
                         % (out[-2000:], err[-2000:]))
        return r

    def test_ca09_apply_sai_0_e_validate_strict_passa(self):
        r = self._applied()
        code, out, err = st(r["root"], "validate", "--strict")
        self.assertEqual(code, 0, "validate --strict depois do upgrade: %s%s" % (out[-2000:], err[-2000:]))

    def test_ca09_disco_passa_a_kind_epic(self):
        r = self._applied()
        kinds = {iid: d.get("kind") for iid, (z, p, d) in all_items(r["root"]).items() if d.get("kind") in
                 ("epico", "epic")}
        self.assertTrue(kinds, "pré-condição: há épico no alvo")
        self.assertEqual(sorted(set(kinds.values())), ["epic"], "épico no disco depois do upgrade: %s" % kinds)

    def test_ca09_events_jsonl_intacto(self):
        r = self._applied()
        self.assertEqual(read_bytes(os.path.join(r["root"], SD, "events.jsonl")), r["events0"],
                         "o upgrade não pode reescrever events.jsonl")

    def test_ca09_textos_emitidos_sem_flag_pt(self):
        r = self._applied()
        hits = emitted_hits(r["root"])
        self.assertEqual(hits, [], "depois do upgrade os textos emitidos citam flag pt (%d):\n  %s"
                         % (len(hits), "\n  ".join(hits[:30])))

    def test_ca09_version_0150(self):
        v = read_text(os.path.join(SKILL, "VERSION")).strip()
        self.assertGreaterEqual(vtuple(v), NEW_VERSION, "VERSION %s < 0.15.0" % v)
        cat = _strip_json5(read_text(os.path.join(SKILL, "references", "migrations.json5")))
        ents = [m for m in cat.get("migrations") or [] if str(m.get("to")) == "0.15.0"]
        self.assertEqual(len(ents), 1, "o catálogo deveria ter exatamente uma entrada to: 0.15.0")
        r = self._applied()
        run = read_text(os.path.join(r["root"], SD, "run.json5"))
        m = re.search(r'skill_version:\s*"([\d.]+)"', run)
        self.assertTrue(m and vtuple(m.group(1)) >= NEW_VERSION, "run.json5 do alvo: %s" % (m and m.group(1)))

    def test_ca09_controle_legado_tem_epico_e_texto_pt(self):
        """controle: o alvo 0.14.0 legado tem `kind: "epico"` no disco, textos emitidos com flag pt e valida."""
        r = ca09_state()
        self.assertEqual(r["kind0"], "epico")
        src, _ = legacy_0140()
        self.assertTrue(emitted_hits(src))
        code, out, err = st(src, "validate", "--strict")
        self.assertEqual(code, 0, out + err)


if __name__ == "__main__":
    unittest.main()
