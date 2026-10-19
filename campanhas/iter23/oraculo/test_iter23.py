"""ORÁCULO campanha-iter23 (0.13.0) — árvore sem itens presos, comandos certos, auto-memória e versão visível.

Mapa requisito → teste e critérios em ESPEC.md (mesma pasta). Tudo pelo caminho REAL: alvo da fixture do emit
(init + harness install + emit pela skill), estado em MODO ÁRVORE (`cs-state init`), comandos pelo `cs-state` do
próprio alvo (`.swarm/harness/state.py`, o mesmo que `.swarm/bin/cs-state` chama) e o hook REAL
`CLAUDE_PROJECT_DIR=<alvo> python3 <alvo>/.swarm/harness/guard.py pre-write` com payload do agente PRINCIPAL (sem
agent_id) e de SUBAGENTE (agent_id/agent_type, delegação DISPATCHED de verdade).

Itens presos (como na cobaia): o alvo LEGADO é instalado pela skill 0.12.2 real (`git archive b757d1f` ou
$CS_OLD_SKILL_DIR), cujo `new task` aceita task com DoR incompleto (FIX sem --fixes/--teste, CHORE sem --motivo,
allowed_path em `.claude/agent-memory/...`, US sem como/quero/para, BUG sem --reproducao, task sem --verify-cmd);
depois é atualizado pela skill sob teste (`cs.py upgrade` e `upgrade --apply`).

  CA-01  drop de task da árvore não iniciada (com/sem DoR) → archive DROPPED com motivo; sem --reason recusa.
  CA-02  amend de motivo/fixes/teste/reproducao/verify_cmd/como/quero/para em task não iniciada; depois start passa.
  CA-03  close de sprint com tasks DROPPED; com task aberta recusa e lista.
  CA-04  uma sprint aberta por épico (new e start); drop de sprint vazia.
  CA-05  DoR estático no `new task` (e --dry-run): recusa antes de criar.
  CA-06  `plan <story> --sprint` na árvore; `sprint plan` funciona na árvore ou aponta `cs-state plan`.
  CA-07  textos emitidos sem `cs-state add epic|feature|story`; todo comando de criação/planejamento citado executa.
  CA-08  upgrade de alvo 0.12.x lista os itens presos com o comando de descarte/emenda, sem alterá-los; VERSION ≥ 0.13.0.
  CA-09  auto-memória do Claude Code (~/.claude/projects/<slug>/memory/) liberada ao principal, só a dele.
  CA-10  `cs-state version` e MANIFEST.json5 `version` == VERSION da skill == run.json5 skill_version.

Versão sempre RELATIVA (≥). Skill sob teste: $CS_SKILL_DIR, senão a raiz deste projeto. Temporários: $CS_ORACLE_TMP,
senão o TMPDIR do sistema (o `harness install` RECUSA alvo dentro da própria skill, então `local/` não serve).
Python 3.9+, unittest, só stdlib. Rodar (desta pasta): python3 -m unittest -v test_iter23
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
import unittest

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.realpath(os.path.join(HERE, "..", "..", ".."))
SKILL = os.path.realpath(os.environ.get("CS_SKILL_DIR") or PROJECT)
OLD_COMMIT = "b757d1f"          # "0.12.2: guard sem portas laterais (iter24)"
OLD_PREFIX = (0, 12)            # alvo legado: qualquer 0.12.x
NEW_VERSION = (0, 13, 0)

GIT_ENV = {"GIT_AUTHOR_NAME": "Ana", "GIT_AUTHOR_EMAIL": "ana@x", "GIT_COMMITTER_NAME": "Ana",
           "GIT_COMMITTER_EMAIL": "ana@x"}
SD = ".swarm"
AGENT = "dev-billing"
VERIFY = "python3 -m unittest tests.test_ok"
RED = "tests.test_red"
ACEITE_RED = "python3 -m unittest tests.test_red"
C1 = "AC-1|Dado pedido Quando aplico Então desconta|tests.test_ok"
RESERVED = ".claude/agent-memory/dev-billing/notas.md"
CREATED_RE = re.compile(r"^criad[oa] (\S+) em (\S+)\s*$", re.M)
SUB = {"agent_id": "ag-iter23", "agent_type": AGENT}
MAIN = {}

_TMP = {}


# ================================================================================================ infraestrutura
def _env(extra=None):
    e = dict(os.environ)
    for k in ("CLAUDE_PROJECT_DIR", "CS_ACTOR", "CS_GUARD_OFF", "CS_ROOT", "CS_SKILL_VERSION_FILE",
              "CS_MIGRATIONS_FILE", "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        e.pop(k, None)
    e.update(GIT_ENV)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    # sem gc/maintenance automático em segundo plano: o clone (copytree) da fixture não pode correr com o git
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


def st(root, *args):
    """`cs-state` do próprio alvo (o `.swarm/bin/cs-state` chama este state.py)."""
    return _run([sys.executable, os.path.join(root, SD, "harness", "state.py"), "--root", root] + list(args), root)


def st_ok(root, *args):
    code, out, err = st(root, *args)
    if code != 0:
        raise AssertionError("cs-state %s → %d\n%s%s" % (" ".join(args), code, out[-3000:], err[-3000:]))
    return out


def new_id(root, *args):
    out = st_ok(root, "new", *args)
    got = CREATED_RE.findall(out)
    if not got:
        raise AssertionError("`new` deveria imprimir `criado <ID> em <path>`: %r" % out)
    return got[0][0]


def hook(root, mode, payload, actor=None, extra=None):
    p = dict(payload)
    p.setdefault("cwd", root)
    p.setdefault("session_id", "s-iter23")
    p.update(actor or {})
    env = {"CLAUDE_PROJECT_DIR": root}
    env.update(extra or {})
    return _run([sys.executable, os.path.join(root, SD, "harness", "guard.py"), mode], root, timeout=120,
                extra=env, stdin=json.dumps(p).encode())


def hook_write(root, path, actor=None, tool="Write", home=None):
    if tool == "Write":
        ti = {"file_path": path, "content": "x\n"}
    else:
        ti = {"file_path": path, "old_string": "a", "new_string": "b"}
    return hook(root, "pre-write", {"tool_name": tool, "tool_use_id": "tu-w", "tool_input": ti}, actor,
                extra={"HOME": home} if home else None)


def read_text(path):
    with open(path, encoding="utf-8") as f:
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


def item_files(root):
    """{path relativo: conteúdo} de todos os itens da árvore + events.jsonl (para provar que nada mudou)."""
    snap = {}
    base = os.path.join(root, SD)
    for zone in ("backlog", "state", "archive"):
        for dp, _, fns in os.walk(os.path.join(base, zone)):
            for fn in fns:
                p = os.path.join(dp, fn)
                with open(p, "rb") as f:
                    snap[os.path.relpath(p, root)] = f.read()
    ev = os.path.join(base, "events.jsonl")
    if os.path.exists(ev):
        with open(ev, "rb") as f:
            snap["events.jsonl"] = f.read()
    return snap


def find_item(root, iid, zones=("backlog", "state", "archive")):
    """[(zona, path)] dos arquivos .json/.json5 cujo `id` é iid."""
    got = []
    for zone in zones:
        for dp, _, fns in os.walk(os.path.join(root, SD, zone)):
            for fn in fns:
                if not fn.endswith((".json", ".json5")):
                    continue
                p = os.path.join(dp, fn)
                try:
                    d = _strip_json5(read_text(p))
                except Exception:
                    continue
                if isinstance(d, dict) and d.get("id") == iid:
                    got.append((zone, p))
    return got


# Contrato de disco da 0.11.0 (B-14, hcore.ITEM_SCHEMA): o arquivo do item grava as chaves em INGLÊS.
# O oráculo fala em português; a leitura traduz (sem sobrescrever uma chave em português que já exista).
ITEM_KEYS_EN_PT = (("reason", "motivo"), ("failing_test", "reproducao"), ("as_a", "como"), ("i_want", "quero"),
                   ("so_that", "para"), ("proving_test", "teste"))


def item(root, iid):
    got = find_item(root, iid)
    if len(got) != 1:
        raise AssertionError("item %s: esperado 1 arquivo, achei %s" % (iid, got))
    d = _strip_json5(read_text(got[0][1]))
    if isinstance(d, dict):
        for en, pt in ITEM_KEYS_EN_PT:
            if en in d and pt not in d:
                d[pt] = d[en]
    return got[0][0], got[0][1], d


def board_open(root):
    """Saída do `board` ANTES de `fechados recentes` (o que está aberto)."""
    out = st_ok(root, "board")
    return out.split("fechados recentes")[0]


# ================================================================================================ fixtures
def _base_tmp():
    if "base" not in _TMP:
        _TMP["base"] = os.path.realpath(tempfile.mkdtemp(prefix="oraculo-iter23-",
                                                         dir=os.environ.get("CS_ORACLE_TMP") or None))
    return _TMP["base"]


def tearDownModule():
    if "base" in _TMP and not os.environ.get("CS_ORACLE_KEEP"):
        shutil.rmtree(_TMP["base"], ignore_errors=True)


def old_skill():
    """A skill 0.12.x real: $CS_OLD_SKILL_DIR ou `git archive` do commit da 0.12.2 (sem escrever no repo)."""
    if "old" in _TMP:
        return _TMP["old"]
    d = os.environ.get("CS_OLD_SKILL_DIR")
    if not d:
        d = os.path.join(_base_tmp(), "skill-antiga")
        p = subprocess.run(["git", "-C", PROJECT, "archive", "--format=tar", OLD_COMMIT], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=300)
        if p.returncode != 0:
            raise AssertionError("não consegui extrair a skill 0.12.x (git archive %s): %s — defina $CS_OLD_SKILL_DIR"
                                 % (OLD_COMMIT, p.stderr.decode()))
        os.makedirs(d)
        with tarfile.open(fileobj=io.BytesIO(p.stdout)) as tf:
            if hasattr(tarfile, "data_filter"):
                tf.extractall(d, filter="data")
            else:
                tf.extractall(d)
    d = os.path.realpath(d)
    v = read_text(os.path.join(d, "VERSION")).strip()
    if vtuple(v)[:2] != OLD_PREFIX:
        raise AssertionError("skill antiga em %s tem VERSION %s (esperado 0.12.x)" % (d, v))
    _TMP["old"] = d
    return d


def make_target(skill, name):
    """Alvo da fixture do emit; init + harness install + emit pela skill dada; estado em árvore iniciado; testes
    tests.test_ok (verde) e tests.test_red (vermelho). Sem itens."""
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
    for f in ("coupons.py", "pix.py", "frete.py", "taxa.py", "cupom2.py", "boleto.py", "nota.py", "q.py"):
        write(dest, "src/billing/" + f, "X = 1\n")
    git(dest, "init", "-q")
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "init")
    cs_ok(skill, dest, "init", "--platforms", "claude-code")
    cs_ok(skill, dest, "harness", "install", "--allow-outside")
    cs_ok(skill, dest, "emit", "--allow-outside")
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


def fresh_base():
    if "fresh" not in _TMP:
        _TMP["fresh"] = make_target(SKILL, "base-nova")
    return _TMP["fresh"]


_N = [0]


def fresh(tag):
    _N[0] += 1
    return clone(fresh_base(), "nova-%s-%d" % (tag, _N[0]))


def _us(title, path, *extra):
    return ["--tipo", "US", "--agent", AGENT, "--title", title, "--allowed-path", path, "--verify-cmd", VERIFY,
            "--como", "cliente", "--quero", "cupom", "--para", "pagar menos", "--criterio", C1] + list(extra)


def legacy_base():
    """Alvo instalado pela skill 0.12.x com os itens PRESOS da cobaia, criados pelo `new` antigo (que não valida):
    EPC-001 ativo › SPR-001 ativa (tasks direto na sprint) + FEA-001 (backlog) com task FIX e story US-001;
    SPR-002 ativa sem épico só com tasks presas; SPR-003 do EPC-001 no backlog (2ª sprint aberta do épico)."""
    if "legacy" in _TMP:
        return _TMP["legacy"]
    root = make_target(old_skill(), "base-legado")
    ids = {}
    ids["epc"] = new_id(root, "epico", "--title", "Pagamentos da Ana", "--objetivo", "pix")
    ids["spr"] = new_id(root, "sprint", "--meta", "pix da Ana", "--epico", ids["epc"])
    st_ok(root, "start", ids["epc"])
    st_ok(root, "start", ids["spr"])
    S = ["--sprint", ids["spr"]]
    ids["fix"] = new_id(root, "task", "--tipo", "FIX", "--agent", AGENT, "--title", "Fix sem fixes",
                        "--allowed-path", "src/billing/pix.py", "--verify-cmd", VERIFY, *S)
    ids["chore"] = new_id(root, "task", "--tipo", "CHORE", "--agent", AGENT, "--title", "Chore sem motivo",
                          "--allowed-path", "src/billing/frete.py", "--verify-cmd", VERIFY, *S)
    ids["reserved"] = new_id(root, "task", *_us("Notas na memoria do agente", RESERVED, *S))
    ids["us_hist"] = new_id(root, "task", "--tipo", "US", "--agent", AGENT, "--title", "US sem historia",
                            "--allowed-path", "src/billing/taxa.py", "--verify-cmd", VERIFY, "--criterio", C1, *S)
    ids["bug"] = new_id(root, "task", "--tipo", "BUG", "--agent", AGENT, "--title", "Bug sem reproducao",
                        "--allowed-path", "src/billing/cupom2.py", "--verify-cmd", VERIFY, *S)
    ids["noverify"] = new_id(root, "task", "--tipo", "US", "--agent", AGENT, "--title", "US sem verify",
                             "--allowed-path", "src/billing/boleto.py", "--como", "cliente", "--quero", "x",
                             "--para", "y", "--criterio", C1, *S)
    ids["good"] = new_id(root, "task", *_us("US pronta", "src/billing/nota.py", *S))
    ids["started"] = new_id(root, "task", *_us("US iniciada", "src/billing/coupons.py", *S))
    st_ok(root, "start", ids["started"])
    ids["fea"] = new_id(root, "feature", "--title", "Pix da Ana", "--backlog", "--aceite", ACEITE_RED)
    ids["fea_fix"] = new_id(root, "task", "--tipo", "FIX", "--agent", AGENT, "--title", "Fix da feature",
                            "--allowed-path", "src/billing/pix.py", "--verify-cmd", VERIFY, "--feature", ids["fea"])
    ids["story"] = new_id(root, "story", "--tipo", "US", "--title", "Story da Ana", "--feature", ids["fea"],
                          "--agents", AGENT, "--agents", "dev-web", "--allowed-path", "src/billing/q.py", "--verify-cmd", VERIFY,
                          "--como", "cliente", "--quero", "x", "--para", "y", "--criterio", C1)
    ids["spr2"] = new_id(root, "sprint", "--meta", "limpeza da Ana")
    st_ok(root, "start", ids["spr2"])
    ids["s2_chore"] = new_id(root, "task", "--tipo", "CHORE", "--agent", AGENT, "--title", "Chore presa",
                             "--allowed-path", "src/billing/frete.py", "--verify-cmd", VERIFY, "--sprint", ids["spr2"])
    ids["s2_fix"] = new_id(root, "task", "--tipo", "FIX", "--agent", AGENT, "--title", "Fix presa",
                           "--allowed-path", "src/billing/pix.py", "--verify-cmd", VERIFY, "--sprint", ids["spr2"])
    ids["spr3"] = new_id(root, "sprint", "--meta", "segunda do epico", "--epico", ids["epc"])
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "itens da Ana")
    # os itens presos têm de estar mesmo presos no motor antigo (a fixture reproduz o relato)
    for k in ("fix", "chore", "us_hist", "bug", "noverify", "fea_fix", "s2_chore", "s2_fix"):
        code, out, err = st(root, "check", ids[k])
        if code == 0:
            raise AssertionError("fixture: %s (%s) deveria falhar no DoR do motor antigo: %s" % (ids[k], k, out))
    ids["stuck"] = ["fix", "chore", "reserved", "us_hist", "bug", "noverify", "fea_fix", "s2_chore", "s2_fix"]
    _TMP["legacy"] = (root, ids)
    return _TMP["legacy"]


def upgraded_base():
    """Clone do legado ANTES do upgrade, `cs.py upgrade` (plano) e `upgrade --apply` pela skill sob teste."""
    if "up" not in _TMP:
        src, ids = legacy_base()
        root = clone(src, "base-legado-atualizado")
        r = {"root": root, "ids": ids, "before": item_files(root)}
        r["plan"] = cs(SKILL, root, "upgrade")
        r["after_plan"] = item_files(root)
        r["apply"] = cs(SKILL, root, "upgrade", "--apply", "--allow-outside")
        r["after_apply"] = item_files(root)
        _TMP["up"] = r
    return _TMP["up"]


_L = [0]


def legacy(tag):
    """Clone do legado já atualizado pela skill sob teste (o motor do alvo é o novo, os itens presos continuam)."""
    _L[0] += 1
    r = upgraded_base()
    return clone(r["root"], "leg-%s-%d" % (tag, _L[0])), r["ids"]


# ================================================================================================ CA-01
class TestCA01(unittest.TestCase):
    def _assert_dropped(self, root, iid, reason):
        zone, path, d = item(root, iid)
        self.assertEqual(zone, "archive", "%s descartada deveria ir para archive/ (está em %s: %s)" % (iid, zone, path))
        blob = json.dumps(d, ensure_ascii=False)
        self.assertIn("DROPPED", blob.upper(), "%s no archive deveria estar como DROPPED: %s" % (iid, blob[:800]))
        self.assertIn(reason, blob, "o motivo do descarte deveria estar no histórico de %s" % iid)
        self.assertNotIn(iid + " ", board_open(root), "%s descartada não deveria aparecer aberta no board" % iid)
        nxt = st_ok(root, "next")
        self.assertNotIn(iid, nxt, "%s descartada não deveria aparecer no next" % iid)
        code, out, err = st(root, "validate", "--strict")
        self.assertEqual(code, 0, "validate --strict depois do drop: %s%s" % (out, err))

    def test_ca01_drop_task_nao_iniciada_com_dor_incompleto(self):
        root, ids = legacy("ca01a")
        for k in ("fix", "chore", "fea_fix"):
            reason = "descartada pela Ana (%s)" % k
            code, out, err = st(root, "drop", ids[k], "--reason", reason)
            self.assertEqual(code, 0, "drop %s (%s, não iniciada, DoR incompleto) → %d: %s%s"
                             % (ids[k], k, code, out, err))
            self._assert_dropped(root, ids[k], reason)

    def test_ca01_drop_task_nao_iniciada_com_dor_completo(self):
        root, ids = legacy("ca01b")
        reason = "a Ana desistiu"
        code, out, err = st(root, "drop", ids["good"], "--reason", reason)
        self.assertEqual(code, 0, "drop %s (não iniciada, DoR ok) → %d: %s%s" % (ids["good"], code, out, err))
        self._assert_dropped(root, ids["good"], reason)

    def test_ca01_drop_sem_reason_recusa_e_pede_o_motivo(self):
        root, ids = legacy("ca01c")
        before = item_files(root)
        code, out, err = st(root, "drop", ids["chore"])
        self.assertNotEqual(code, 0, "drop sem --reason deveria recusar")
        self.assertTrue(re.search(r"--reason|motivo", out + err), "a recusa deveria pedir --reason: %s%s" % (out, err))
        self.assertEqual(item_files(root), before, "recusa não altera nada")

    def test_ca01_controle_task_iniciada_continua_pelo_fluxo_atual(self):
        root, ids = legacy("ca01d")
        code, out, err = st(root, "drop", ids["started"], "--reason", "x")
        self.assertNotEqual(code, 0, "task iniciada (BRIEFED) não sai por drop direto: fluxo M2 atual")
        zone, _, _ = item(root, ids["started"])
        self.assertEqual(zone, "state", "task iniciada continua em state/")


# ================================================================================================ CA-02
class TestCA02(unittest.TestCase):
    def _amend(self, root, iid, field, value):
        code, out, err = st(root, "amend", iid, "--field", field, "--after", value, "--reason", "DoR da Ana")
        return code, out + err

    def _check_amended(self, root, iid, fields):
        bad = []
        for field, value in fields:
            code, txt = self._amend(root, iid, field, value)
            if code != 0:
                bad.append("amend %s --field %s → %d: %s" % (iid, field, code, txt.strip()[-300:]))
                continue
            _, path, d = item(root, iid)
            if str(d.get(field)) != value:
                bad.append("%s: campo %s = %r depois do amend (esperado %r)" % (iid, field, d.get(field), value))
        return bad

    def test_ca02_amend_campos_do_dor_e_start_aceita(self):
        root, ids = legacy("ca02a")
        plan = [("chore", [("motivo", "manutencao pedida pela Ana")]),
                ("bug", [("reproducao", RED)]),
                ("us_hist", [("como", "cliente"), ("quero", "pagar"), ("para", "concluir")]),
                ("noverify", [("verify_cmd", VERIFY)])]
        bad = []
        for k, fields in plan:
            bad += self._check_amended(root, ids[k], fields)
        bad += self._check_amended(root, ids["fix"], [("fixes", ids["bug"]), ("teste", RED)])
        self.assertEqual(bad, [], "emendas do DoR em task não iniciada:\n  " + "\n  ".join(bad))
        for k in ("chore", "bug", "us_hist", "noverify", "fix"):
            code, out, err = st(root, "start", ids[k])
            if code != 0:
                bad.append("start %s (%s) depois da emenda → %d: %s" % (ids[k], k, code, (out + err).strip()[-300:]))
        self.assertEqual(bad, [], "start deveria aceitar depois de completar o DoR:\n  " + "\n  ".join(bad))

    def test_ca02_historico_registra_a_emenda(self):
        root, ids = legacy("ca02b")
        code, txt = self._amend(root, ids["chore"], "motivo", "manutencao pedida pela Ana")
        self.assertEqual(code, 0, txt)
        _, path, d = item(root, ids["chore"])
        raw = read_text(path)
        self.assertGreaterEqual(raw.count("motivo"), 2, "o histórico de %s deveria citar a emenda de motivo: %s"
                                % (ids["chore"], raw[-800:]))
        self.assertIn("DoR da Ana", raw, "o motivo da emenda deveria estar no histórico")

    def test_ca02_controle_task_iniciada_mantem_regras(self):
        root, ids = legacy("ca02c")
        before = item(root, ids["started"])[2].get("motivo")
        code, txt = self._amend(root, ids["started"], "motivo", "x")
        self.assertNotEqual(code, 0, "task iniciada não emenda motivo pelo caminho da árvore: %s" % txt)
        self.assertEqual(item(root, ids["started"])[2].get("motivo"), before)

    def test_ca02_controle_allowed_paths_continua_emendavel(self):
        root, ids = legacy("ca02d")
        code, txt = self._amend(root, ids["reserved"], "allowed_paths", '["src/billing/coupons2.py"]')
        self.assertEqual(code, 0, txt)


# ================================================================================================ CA-03
class TestCA03(unittest.TestCase):
    def test_ca03_sprint_fecha_com_tasks_dropped(self):
        root, ids = legacy("ca03a")
        for k in ("s2_chore", "s2_fix"):
            code, out, err = st(root, "drop", ids[k], "--reason", "fora do escopo da Ana")
            self.assertEqual(code, 0, "drop %s → %d: %s%s" % (ids[k], code, out, err))
        code, out, err = st(root, "close", ids["spr2"], "--summary", "sprint da Ana encerrada")
        self.assertEqual(code, 0, "close %s com todas as tasks DROPPED → %d: %s%s" % (ids["spr2"], code, out, err))
        self.assertEqual(item(root, ids["spr2"])[0], "archive", "sprint fechada vai para archive/")

    def test_ca03_com_task_aberta_recusa_e_lista(self):
        root, ids = legacy("ca03b")
        code, out, err = st(root, "drop", ids["s2_chore"], "--reason", "fora do escopo")
        self.assertEqual(code, 0, "drop %s → %d: %s%s" % (ids["s2_chore"], code, out, err))
        code, out, err = st(root, "close", ids["spr2"], "--summary", "x")
        self.assertNotEqual(code, 0, "close com %s aberta deveria recusar" % ids["s2_fix"])
        self.assertIn(ids["s2_fix"], out + err, "a recusa lista a task aberta")
        self.assertNotIn(ids["s2_chore"] + "\n", out + err, "a DROPPED não conta como aberta")

    def test_ca03_controle_sem_drop_recusa_listando(self):
        root, ids = legacy("ca03c")
        code, out, err = st(root, "close", ids["spr2"], "--summary", "x")
        self.assertNotEqual(code, 0)
        for k in ("s2_chore", "s2_fix"):
            self.assertIn(ids[k], out + err, "a recusa lista %s" % ids[k])


# ================================================================================================ CA-04
class TestCA04(unittest.TestCase):
    def test_ca04_segunda_sprint_aberta_no_epico_recusada_no_new(self):
        root = fresh("ca04a")
        epc = new_id(root, "epico", "--title", "Epico da Ana", "--objetivo", "x")
        s1 = new_id(root, "sprint", "--meta", "primeira", "--epico", epc)
        before = item_files(root)
        for extra in (["--dry-run"], []):
            code, out, err = st(root, "new", "sprint", "--meta", "segunda", "--epico", epc, *extra)
            self.assertNotEqual(code, 0, "2ª sprint aberta no %s (%s) deveria recusar%s"
                                % (epc, s1, " (dry-run)" if extra else ""))
            self.assertIn(s1, out + err, "a recusa cita a sprint aberta %s: %s%s" % (s1, out, err))
        self.assertEqual(item_files(root), before, "recusa não cria nada")

    def test_ca04_start_de_segunda_sprint_no_epico_recusado(self):
        root, ids = legacy("ca04b")   # legado: SPR-003 do mesmo épico criada pelo motor antigo, SPR-001 ativa
        code, out, err = st(root, "start", ids["spr3"])
        self.assertNotEqual(code, 0, "start de %s com %s aberta no mesmo épico deveria recusar" % (ids["spr3"], ids["spr"]))
        self.assertIn(ids["spr"], out + err, "a recusa cita a aberta: %s%s" % (out, err))

    def test_ca04_drop_de_sprint_vazia(self):
        root = fresh("ca04c")
        spr = new_id(root, "sprint", "--meta", "vazia da Ana")
        code, out, err = st(root, "drop", spr, "--reason", "a Ana não vai usar")
        self.assertEqual(code, 0, "drop de sprint vazia não iniciada → %d: %s%s" % (code, out, err))
        zone, _, d = item(root, spr)
        self.assertEqual(zone, "archive")
        blob = json.dumps(d, ensure_ascii=False)
        self.assertIn("DROPPED", blob.upper(), "sprint descartada (não entregue): %s" % blob[:600])
        self.assertIn("a Ana não vai usar", blob)
        code, out, err = st(root, "validate", "--strict")
        self.assertEqual(code, 0, out + err)

    def test_ca04_controle_sprint_em_outro_epico(self):
        root = fresh("ca04d")
        e1 = new_id(root, "epico", "--title", "Um", "--objetivo", "x")
        e2 = new_id(root, "epico", "--title", "Dois", "--objetivo", "y")
        new_id(root, "sprint", "--meta", "a", "--epico", e1)
        new_id(root, "sprint", "--meta", "b", "--epico", e2)


# ================================================================================================ CA-05
class TestCA05(unittest.TestCase):
    CASES = [
        ("allowed_path reservado", ("reservad", ".claude"),
         _us("Notas", RESERVED, "--backlog")),
        ("FIX sem --fixes/--teste", ("fixes", "teste"),
         ["--tipo", "FIX", "--agent", AGENT, "--title", "Fix", "--allowed-path", "src/billing/pix.py",
          "--verify-cmd", VERIFY, "--backlog"]),
        ("CHORE sem --motivo", ("motivo",),
         ["--tipo", "CHORE", "--agent", AGENT, "--title", "Chore", "--allowed-path", "src/billing/frete.py",
          "--verify-cmd", VERIFY, "--backlog"]),
        ("US sem critério", ("crit",),
         ["--tipo", "US", "--agent", AGENT, "--title", "US", "--allowed-path", "src/billing/taxa.py",
          "--verify-cmd", VERIFY, "--como", "a", "--quero", "b", "--para", "c", "--backlog"]),
        ("US sem como/quero/para", ("como",),
         ["--tipo", "US", "--agent", AGENT, "--title", "US", "--allowed-path", "src/billing/taxa.py",
          "--verify-cmd", VERIFY, "--criterio", C1, "--backlog"]),
        ("BUG sem --reproducao", ("reproducao",),
         ["--tipo", "BUG", "--agent", AGENT, "--title", "Bug", "--allowed-path", "src/billing/cupom2.py",
          "--verify-cmd", VERIFY, "--backlog"]),
        ("task sem --verify-cmd", ("verify",),
         ["--tipo", "US", "--agent", AGENT, "--title", "US", "--allowed-path", "src/billing/boleto.py",
          "--como", "a", "--quero", "b", "--para", "c", "--criterio", C1, "--backlog"]),
    ]

    def _refused(self, root, extra):
        bad = []
        before = item_files(root)
        for label, words, args in self.CASES:
            code, out, err = st(root, "new", "task", *(args + extra))
            txt = (out + err).lower()
            if code == 0:
                bad.append("%s: `new task%s` passou (exit 0): %s" % (label, " ".join([""] + extra), out.strip()[-200:]))
            elif not all(w in txt for w in words):
                bad.append("%s: a recusa não cita %s: %s" % (label, words, txt.strip()[-300:]))
        if item_files(root) != before:
            bad.append("recusa criou/alterou itens ou eventos")
        return bad

    def test_ca05_new_recusa_dor_estatico(self):
        root = fresh("ca05a")
        bad = self._refused(root, [])
        self.assertEqual(bad, [], "new task com DoR estático incompleto:\n  " + "\n  ".join(bad))

    def test_ca05_new_dry_run_recusa_dor_estatico(self):
        root = fresh("ca05b")
        bad = self._refused(root, ["--dry-run"])
        self.assertEqual(bad, [], "new task --dry-run com DoR estático incompleto:\n  " + "\n  ".join(bad))

    def test_ca05_controle_campos_certos_criam(self):
        root = fresh("ca05c")
        bug = new_id(root, "task", "--tipo", "BUG", "--agent", AGENT, "--title", "Bug da Ana",
                     "--allowed-path", "src/billing/cupom2.py", "--verify-cmd", VERIFY, "--reproducao", RED,
                     "--backlog")
        new_id(root, "task", *_us("US da Ana", "src/billing/taxa.py", "--backlog"))
        new_id(root, "task", "--tipo", "CHORE", "--agent", AGENT, "--title", "Chore da Ana", "--allowed-path",
               "src/billing/frete.py", "--verify-cmd", VERIFY, "--motivo", "manutencao", "--backlog")
        new_id(root, "task", "--tipo", "FIX", "--agent", AGENT, "--title", "Fix da Ana", "--allowed-path",
               "src/billing/pix.py", "--verify-cmd", VERIFY, "--fixes", bug, "--teste", RED, "--backlog")
        # BUG cujo teste já passa: é parte DINÂMICA do DoR, continua no start (o new cria)
        new_id(root, "task", "--tipo", "BUG", "--agent", AGENT, "--title", "Bug verde", "--allowed-path",
               "src/billing/nota.py", "--verify-cmd", VERIFY, "--reproducao", "tests.test_ok", "--backlog")


# ================================================================================================ CA-06
def _tree_with_story(tag):
    root = fresh(tag)
    epc = new_id(root, "epico", "--title", "Epico da Ana", "--objetivo", "x")
    spr = new_id(root, "sprint", "--meta", "sprint da Ana", "--epico", epc)
    st_ok(root, "start", epc)
    st_ok(root, "start", spr)
    fea = new_id(root, "feature", "--title", "Pix da Ana", "--backlog", "--aceite", ACEITE_RED)
    us = new_id(root, "story", "--tipo", "US", "--title", "Story da Ana", "--feature", fea, "--agents", AGENT, "--agents", "dev-web",
                "--allowed-path", "src/billing/q.py", "--verify-cmd", VERIFY, "--como", "cliente", "--quero", "x",
                "--para", "y", "--criterio", C1)
    return root, epc, spr, fea, us


def _linked_in_board(board, spr, us):
    lines = board.splitlines()
    for i, ln in enumerate(lines):
        if us in ln and spr in ln:
            return True
    for i, ln in enumerate(lines):
        if spr in ln:
            ind = len(ln) - len(ln.lstrip())
            for nx in lines[i + 1:]:
                if not nx.strip():
                    break
                if len(nx) - len(nx.lstrip()) <= ind:
                    break
                if us in nx:
                    return True
    return False


class TestCA06(unittest.TestCase):
    def test_ca06_plan_story_na_sprint(self):
        root, epc, spr, fea, us = _tree_with_story("ca06a")
        code, out, err = st(root, "plan", us, "--sprint", spr)
        self.assertEqual(code, 0, "plan %s --sprint %s → %d: %s%s" % (us, spr, code, out, err))
        _, spath, sd = item(root, spr)
        self.assertIn(us, json.dumps(sd), "a sprint deveria referenciar %s: %s" % (us, sd))
        _, upath, _ = item(root, us)
        self.assertIn("features", os.path.relpath(upath, root).replace(os.sep, "/"),
                      "a story continua dentro da feature: %s" % upath)
        self.assertTrue(_linked_in_board(st_ok(root, "board"), spr, us), "o board deveria mostrar %s na %s" % (us, spr))
        self.assertIn(us, st_ok(root, "next"), "o next deveria mostrar o trabalho da story planejada")

    def test_ca06_close_da_sprint_considera_story(self):
        root, epc, spr, fea, us = _tree_with_story("ca06b")
        code, out, err = st(root, "plan", us, "--sprint", spr)
        self.assertEqual(code, 0, out + err)
        code, out, err = st(root, "close", spr, "--summary", "x")
        self.assertNotEqual(code, 0, "sprint com a story aberta não fecha")
        self.assertIn(us, out + err, "a recusa cita a story/tasks: %s%s" % (out, err))

    def test_ca06_sprint_plan_na_arvore_funciona_ou_aponta_plan(self):
        root, epc, spr, fea, us = _tree_with_story("ca06c")
        code, out, err = st(root, "sprint", "plan", "--goal", "meta da Ana", "--budget", "10", "--stories", us)
        txt = out + err
        if code == 0:
            self.assertIn(us, json.dumps(item(root, spr)[2]) + json.dumps(find_item(root, us)),
                          "sprint plan passou mas não vinculou %s: %s" % (us, txt))
        else:
            self.assertRegex(txt, r"cs-state plan\b", "sprint plan recusado na árvore deveria apontar `cs-state plan "
                                                      "<id> --sprint <SPR>`: %s" % txt)

    def test_ca06_controle_plan_de_task_na_sprint(self):
        root, epc, spr, fea, us = _tree_with_story("ca06d")
        tid = new_id(root, "task", *_us("Task da Ana", "src/billing/coupons.py", "--backlog"))
        st_ok(root, "plan", tid, "--sprint", spr)


# ================================================================================================ CA-07
CMD_RE = re.compile(r"cs-state\s+(add|new|sprint\s+plan|plan|move)\b(\s+(?:[a-z]+|\.\.\.|<[^>]+>))?")
FORBIDDEN_RE = re.compile(r"cs-state\s+add\s+(epic|feature|story)\b")


def emitted_texts(root):
    files = ["CLAUDE.md", ".claude/orchestrator.md", ".claude/skills/plan-sprint/SKILL.md", "Makefile",
             "specialists.mk"]
    ad = os.path.join(root, ".claude", "agents")
    files += [".claude/agents/" + f for f in sorted(os.listdir(ad)) if f.endswith(".md")] if os.path.isdir(ad) else []
    return {f: read_text(os.path.join(root, f)) for f in files if os.path.isfile(os.path.join(root, f))}


def cited_commands(root):
    """{(verbo, tipo|None): [arquivo:linha]} dos comandos de criação/planejamento citados."""
    got = {}
    for f, txt in emitted_texts(root).items():
        for n, ln in enumerate(txt.splitlines(), 1):
            for m in CMD_RE.finditer(ln):
                verb = re.sub(r"\s+", " ", m.group(1))
                kind = (m.group(2) or "").strip() or None
                if verb not in ("add", "new"):
                    kind = None
                got.setdefault((verb, kind), []).append("%s:%d" % (f, n))
    return got


class TestCA07(unittest.TestCase):
    def test_ca07_textos_sem_add_epic_feature_story(self):
        root = fresh("ca07a")
        hits = ["%s:%d: %s" % (f, n, ln.strip()[:160]) for f, txt in emitted_texts(root).items()
                for n, ln in enumerate(txt.splitlines(), 1) if FORBIDDEN_RE.search(ln)]
        self.assertEqual(hits, [], "textos emitidos ainda mandam `cs-state add epic|feature|story`:\n  " +
                         "\n  ".join(hits))
        self.assertGreater(len(emitted_texts(root)), 4, "a varredura precisa achar os textos emitidos")

    def test_ca07_todo_comando_citado_executa_na_arvore(self):
        root, epc, spr, fea, us = _tree_with_story("ca07b")
        cmds = cited_commands(root)
        self.assertTrue(cmds, "nenhum comando de criação/planejamento citado nos textos emitidos")
        st_ok(root, "session", "start", "--request", "pedido da Ana")
        st_ok(root, "session", "triage", "--class", "pequena", "--why", "uma linha")
        n = [0]

        def nm():
            n[0] += 1
            return "item %d da Ana" % n[0]

        def task_backlog():
            return new_id(root, "task", *_us(nm(), "src/billing/coupons.py", "--backlog"))

        def us_new():
            return new_id(root, "story", "--tipo", "US", "--title", nm(), "--feature", fea, "--agents", AGENT, "--agents", "dev-web",
                          "--allowed-path", "src/billing/q.py", "--verify-cmd", VERIFY, "--como", "a",
                          "--quero", "b", "--para", "c", "--criterio", C1)
        concrete = {
            ("new", "epico"): lambda: ["new", "epico", "--title", nm(), "--objetivo", "x"],
            ("new", "sprint"): lambda: ["new", "sprint", "--meta", nm()],
            ("new", "feature"): lambda: ["new", "feature", "--title", nm(), "--backlog", "--aceite", ACEITE_RED],
            ("new", "task"): lambda: ["new", "task"] + _us(nm(), "src/billing/taxa.py", "--backlog"),
            ("new", "story"): lambda: ["new", "story", "--tipo", "US", "--title", nm(), "--feature", fea, "--agents",
                                       AGENT, "--agents", "dev-web", "--allowed-path", "src/billing/q.py", "--verify-cmd", VERIFY,
                                       "--como", "a", "--quero", "b", "--para", "c", "--criterio", C1],
            ("add", "task"): lambda: ["add", "task", "--quick", "--agent", AGENT, "--title", nm(), "--allowed-path",
                                      "src/billing/frete.py", "--verify-cmd", VERIFY],
            ("plan", None): lambda: ["plan", task_backlog(), "--sprint", spr],
            ("move", None): lambda: ["move", task_backlog(), "--avulsa"],
            ("sprint plan", None): lambda: ["sprint", "plan", "--goal", "meta", "--budget", "10", "--stories",
                                            us_new()],
        }
        concrete[("new", "epic")] = concrete[("new", "epico")]   # 0.14.0 (iter26, CA-04): `new epic` é o canônico
        concrete[("new", None)] = concrete[("new", "epico")]
        for k in ("...", "<tipo>", "<kind>"):
            concrete[("new", k)] = concrete[("new", "epico")]
        bad = []
        for key, where in sorted(cmds.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")):
            label = "cs-state %s%s (%s)" % (key[0], " " + key[1] if key[1] else "", ", ".join(where[:3]))
            mk = concrete.get(key)
            if mk is None:
                bad.append("%s: não é comando de criação/planejamento do modo árvore" % label)
                continue
            argv = mk()
            code, out, err = st(root, *argv)
            if code != 0:
                bad.append("%s → `cs-state %s` exit %d: %s" % (label, " ".join(argv), code,
                                                               (out + err).strip()[-200:]))
        self.assertEqual(bad, [], "comandos citados nos textos emitidos que não executam num alvo em árvore:\n  " +
                         "\n  ".join(bad))

    def test_ca07_controle_new_citado_executa(self):
        root = fresh("ca07c")
        self.assertTrue(cited_commands(root), "a varredura acha comandos citados")
        new_id(root, "epico", "--title", "Epico da Ana", "--objetivo", "x")
        new_id(root, "task", *_us("Task da Ana", "src/billing/taxa.py", "--backlog"))


# ================================================================================================ CA-08
class TestCA08(unittest.TestCase):
    def test_ca08_version_e_catalogo_0130(self):
        v = read_text(os.path.join(SKILL, "VERSION")).strip()
        self.assertGreaterEqual(vtuple(v), NEW_VERSION, "VERSION %s < 0.13.0" % v)
        cat = _strip_json5(read_text(os.path.join(SKILL, "references", "migrations.json5")))
        self.assertGreaterEqual(vtuple(cat.get("version", "0.0.0")), NEW_VERSION)
        ents = [m for m in cat.get("migrations") or [] if str(m.get("to")) == "0.13.0"]
        self.assertEqual(len(ents), 1, "catálogo deveria ter exatamente uma entrada to: 0.13.0")
        kinds = [a.get("kind") for a in ents[0].get("actions") or []]
        self.assertIn("harness", kinds, "a 0.13.0 precisa reinstalar o motor (ação harness): %s" % kinds)

    def _lists_stuck(self, txt, ids):
        bad = []
        for k in ids["stuck"]:
            iid = ids[k]
            lines = [ln for ln in txt.splitlines() if iid in ln]
            if not lines:
                bad.append("%s (%s) não listado" % (iid, k))
                continue
            near = "\n".join(txt.splitlines()[max(0, txt.splitlines().index(lines[0]) - 1):
                                              txt.splitlines().index(lines[0]) + 4])
            if not re.search(r"cs-state (drop|amend) " + re.escape(iid), near):
                bad.append("%s (%s) sem o comando `cs-state drop|amend %s ...` junto" % (iid, k, iid))
        return bad

    def test_ca08_plano_lista_itens_presos_com_comando(self):
        r = upgraded_base()
        code, out, err = r["plan"]
        self.assertEqual(code, 0, out + err)
        self.assertIn("0.13.0", out + err, "o plano deveria listar a 0.13.0")
        bad = self._lists_stuck(out + err, r["ids"])
        self.assertEqual(bad, [], "o plano do upgrade deveria apontar os itens presos:\n  " + "\n  ".join(bad))
        self.assertEqual(r["after_plan"], r["before"], "o plano não altera nada")

    def test_ca08_apply_relata_itens_presos_sem_alterar(self):
        r = upgraded_base()
        code, out, err = r["apply"]
        self.assertEqual(code, 0, "upgrade --apply → %d: %s%s" % (code, out[-2000:], err[-2000:]))
        bad = self._lists_stuck(out + err, r["ids"])
        rep = os.path.join(r["root"], SD, "upgrade-report.md")
        if bad and os.path.isfile(rep):
            bad = self._lists_stuck(read_text(rep), r["ids"])
        self.assertEqual(bad, [], "o relatório do apply deveria apontar os itens presos:\n  " + "\n  ".join(bad))
        # Mudança oficial 02 (D-39): o item preso fica no MESMO caminho e o JSON, sem `status` e sem `_generated_by`,
        # é igual ao de antes; se `status` existir depois, é código do vocabulário canônico (D-37).
        canon = re.compile(r"^(TODO|BACKLOG|ACTIVE|DONE|DROPPED)(/[A-Za-z0-9_-]+)?$")

        def _strip(raw):
            obj = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
            if isinstance(obj, dict):
                obj = dict((kk, vv) for kk, vv in obj.items() if kk not in ("status", "_generated_by"))
            return obj

        changed = []
        for k in r["ids"]["stuck"]:
            iid = r["ids"][k]
            for p, data in r["before"].items():
                if p.endswith(".json") and ('"id": "%s"' % iid).encode() in data:
                    after = r["after_apply"].get(p)
                    if after is None:
                        changed.append(p + " (sumiu ou mudou de lugar)")
                        continue
                    if after == data:
                        continue
                    try:
                        obj_after = json.loads(after.decode("utf-8") if isinstance(after, bytes) else after)
                        same = _strip(after) == _strip(data)
                    except ValueError:
                        changed.append(p + " (JSON inválido depois)")
                        continue
                    if not same:
                        changed.append(p)
                    elif isinstance(obj_after, dict) and "status" in obj_after and \
                            not canon.match(str(obj_after["status"])):
                        changed.append("%s (status fora do vocabulário: %r)" % (p, obj_after["status"]))
        self.assertEqual(changed, [], "o upgrade não pode alterar os itens presos: %s" % changed)

    def test_ca08_controle_upgrade_aplica(self):
        r = upgraded_base()
        self.assertEqual(r["apply"][0], 0, r["apply"][1][-1500:] + r["apply"][2][-1500:])


# ================================================================================================ CA-09
def slug(root):
    """Regra do Claude Code (medida em ~/.claude/projects/): caminho ABSOLUTO real do projeto com todo caractere
    fora de [A-Za-z0-9] trocado por '-' (/ . _ espaço → '-'), sem colapsar repetições."""
    return re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(root))


def dispatched(tag):
    root = fresh(tag)
    tid = new_id(root, "task", *_us("Cupom da Ana", "src/billing/coupons.py", "--avulsa"))
    st_ok(root, "start", tid)
    code, out, err = hook(root, "pre-agent", {"tool_name": "Agent", "tool_use_id": "tu-a", "tool_input": {
        "subagent_type": AGENT, "model": "sonnet", "description": "%s.d1: cupom da Ana" % tid, "prompt": "faça"}})
    if code != 0:
        raise AssertionError("fixture: despacho pelo hook pre-agent recusado (%d): %s%s" % (code, out, err))
    home = os.path.join(_base_tmp(), "home-%s" % tag)
    mem = os.path.join(home, ".claude", "projects", slug(root), "memory")
    os.makedirs(mem, exist_ok=True)
    os.makedirs(os.path.join(home, "fora"), exist_ok=True)
    os.makedirs(os.path.join(home, ".claude", "projects", "-outro-projeto-da-Ana", "memory"), exist_ok=True)
    return root, home, mem


class TestCA09(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, cls.home, cls.mem = dispatched("ca09")

    def w(self, path, actor, tool="Write"):
        return hook_write(self.root, path, actor, tool, home=self.home)[0]

    def test_ca09_principal_escreve_na_propria_memoria(self):
        bad = []
        for tool in ("Write", "Edit"):
            for rel in ("x.md", "MEMORY.md"):
                p = os.path.join(self.mem, rel)
                if self.w(p, MAIN, tool) != 0:
                    bad.append("%s %s" % (tool, p.replace(self.home, "<HOME>")))
        self.assertEqual(bad, [], "principal escrevendo na auto-memória do próprio projeto deveria passar:\n  " +
                         "\n  ".join(bad))

    def test_ca09_subagente_na_memoria_continua_recusado(self):
        self.assertEqual(self.w(os.path.join(self.mem, "x.md"), SUB), 2)

    def test_ca09_outro_projeto_continua_recusado(self):
        p = os.path.join(self.home, ".claude", "projects", "-outro-projeto-da-Ana", "memory", "x.md")
        self.assertEqual(self.w(p, MAIN), 2)

    def test_ca09_ponto_ponto_saindo_da_memory_continua_recusado(self):
        bad = []
        for p in (os.path.join(self.mem, "..", "x.md"), os.path.join(self.mem, "..", "..", "-outro-projeto-da-Ana",
                                                                     "memory", "x.md"),
                  os.path.join(self.mem, "..", "..", "..", "settings.json")):
            if self.w(p, MAIN) != 2:
                bad.append(p.replace(self.home, "<HOME>"))
        self.assertEqual(bad, [], "`..` saindo da memory/ deveria recusar: %s" % bad)

    def test_ca09_symlink_na_memory_para_fora_continua_recusado(self):
        ln_dir = os.path.join(self.mem, "atalho")
        ln_file = os.path.join(self.mem, "nota.md")
        if not os.path.lexists(ln_dir):
            os.symlink(os.path.join(self.home, "fora"), ln_dir)
        if not os.path.lexists(ln_file):
            os.symlink(os.path.join(self.home, "fora", "alvo.md"), ln_file)
        bad = [p.replace(self.home, "<HOME>") for p in (os.path.join(ln_dir, "x.md"), ln_file)
               if self.w(p, MAIN) != 2]
        self.assertEqual(bad, [], "symlink dentro da memory/ apontando para fora deveria recusar: %s" % bad)

    def test_ca09_controle_fora_da_raiz_continua_recusado(self):
        bad = [p.replace(self.home, "<HOME>") for p in (
            os.path.join(self.home, ".claude", "settings.json"),
            os.path.join(self.home, ".claude", "projects", slug(self.root), "x.md"),
            os.path.join(self.home, "fora", "y.md")) if self.w(p, MAIN) != 2]
        self.assertEqual(bad, [], "fora da raiz (e fora da memory/) segue recusado: %s" % bad)

    def test_ca09_controle_escrita_no_projeto(self):
        self.assertEqual(self.w(os.path.join(self.root, SD, "knowledge", "notas-da-ana.md"), MAIN), 0)
        self.assertEqual(self.w(os.path.join(self.root, "src", "billing", "coupons.py"), SUB), 0)


# ================================================================================================ CA-10
def _manifest_version(root):
    return _strip_json5(read_text(os.path.join(root, SD, "harness", "MANIFEST.json5"))).get("version")


def _run_version(root):
    return _strip_json5(read_text(os.path.join(root, SD, "run.json5"))).get("skill_version")


class TestCA10(unittest.TestCase):
    def setUp(self):
        self.v = read_text(os.path.join(SKILL, "VERSION")).strip()

    def _cs_version(self, root):
        code, out, err = st(root, "version")
        self.assertEqual(code, 0, "`cs-state version` → %d: %s%s" % (code, out, err))
        self.assertIn(self.v, out, "`cs-state version` deveria mostrar %s: %s" % (self.v, out))
        self.assertEqual(_run_version(root), self.v, "run.json5 skill_version == VERSION")

    def _manifest(self, root):
        self.assertEqual(_manifest_version(root), self.v, "MANIFEST.json5 `version` == VERSION da skill")
        self.assertEqual(_run_version(root), self.v, "run.json5 skill_version == VERSION")

    def test_ca10_cs_state_version_alvo_instalado(self):
        self._cs_version(fresh_base())

    def test_ca10_manifest_version_alvo_instalado(self):
        self._manifest(fresh_base())

    def test_ca10_cs_state_version_alvo_atualizado(self):
        self._cs_version(upgraded_base()["root"])

    def test_ca10_manifest_version_alvo_atualizado(self):
        self._manifest(upgraded_base()["root"])

    def test_ca10_controle_run_json5_skill_version(self):
        self.assertEqual(_run_version(fresh_base()), self.v)


if __name__ == "__main__":
    unittest.main()
