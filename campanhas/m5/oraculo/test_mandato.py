"""ORÁCULO campanha-M5 — modo autônomo `mandato` (máquina M5) sobre o estado em ÁRVORE (campanha iter10).

Fonte: codebase-specialists/docs/AUTONOMIA-DESENHO.md (§5–§12, 28 cenários AUTO-*), docs/PONTOS-DO-FOUNDER.md (B11, D6)
e a interface FIXADA da árvore em campanhas/iter10/oraculo/ESPEC.md.
Contrato e interfaces FIXADAS: ESPEC.md (mesma pasta). Quem implementa NÃO edita este arquivo.

Tudo pelo comportamento OBSERVÁVEL, sem mock do motor:
  * `cs-auto`  = scripts/harness/engine/auto.py   (subprocesso, --root <alvo>) — o PILOTO do mandato
  * `cs-state` = scripts/harness/engine/state.py  (subprocesso) — árvore (iter10) + M2
  * guard real = scripts/harness/engine/guard.py  (payloads de hook: pre-write, pre-bash, pre-agent, stop,
                 session-start, pre-compact), CLAUDE_PROJECT_DIR=<alvo>
  * disco/eventos: <alvo>/<STATE_DIR>/events.jsonl (cadeia; lido também em state/events.jsonl, legado)

Princípio do founder: o que é mecânico é SCRIPT (próxima ação, ondas, verify, accept, integração, progresso,
orçamento, parada, escalada); o modelo só executa nós de julgamento (plano, revisão, reflexão, despacho). Portões
humanos continuam humanos: o mandato NUNCA aprova/resolve um portão humano. A prova de humano (frase-senha) é de
outra campanha: o oráculo passa `--by founder` + os argumentos extras de $CS_HUMAN_PROOF_ARGS (vazio hoje).

Nome da pasta de estado: `from cslib.paths import STATE_DIR` (senão ".swarm"). Skill: $CS_SKILL_DIR, senão
~/.claude/skills/codebase-specialists. Python 3.9+, unittest puro, repositórios temporários.
Cobertura 100% de M5 (D6) NÃO é medida aqui: vive no oráculo oficial test_cobertura_maquinas.py, estendido pela
mudança oficial em mudanca-oficial/ (patch + m5_cenarios.py + PORQUE.md), com o mesmo observador das outras máquinas.
Rodar: python3 -m unittest -v test_mandato   (de dentro desta pasta)
"""
import collections
import glob
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.realpath(os.environ.get("CS_SKILL_DIR") or os.path.expanduser("~/.claude/skills/codebase-specialists"))
SCRIPTS = os.path.join(SKILL, "scripts")
HARNESS = os.path.join(SCRIPTS, "harness")
ENGINE = os.path.join(HARNESS, "engine")
STATE_PY = os.path.join(ENGINE, "state.py")
AUTO_PY = os.path.join(ENGINE, "auto.py")
GUARD_PY = os.path.join(ENGINE, "guard.py")
MACHINES = os.path.join(HARNESS, "machines.json5")
INSTALL_PY = os.path.join(HARNESS, "install.py")
TEMPLATES = os.path.join(SKILL, "assets", "templates")

if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
try:
    from cslib.paths import STATE_DIR as _SD  # noqa: E402
except ImportError:
    _SD = ".swarm"
SD = os.path.basename(str(_SD).rstrip("/")) or ".swarm"

from cslib import json5io  # noqa: E402

HUMAN = "founder"
OBJ = "Desconto no checkout"
REGRESSAO = "python3 -m unittest discover -s tests -t ."
GATES = ("reviewer", "security")
CREATED_RE = re.compile(r"^criad[oa] (\S+) em (\S+)\s*$", re.M)
MAN_RE = re.compile(r"\b(MAN-\d{3})\b")
GUARD_RE = re.compile(r"guarda ([a-z_]+)\s*:")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HUMAN_ACT_RE = re.compile(r"cs-auto\s+(approve|amend|resolve|abort|stop)\b|waive-verify|legacy-ack")
OPCOES = ("retomar", "trocar-agente", "emendar", "descartar-ramo", "encerrar", "abortar")
TERMINAIS = ("DONE", "HANDED_BACK", "ABORTED")
ORC = "despachos=20,tentativas=40,replanos=3,minutos=600,usd=50"


# ---------------------------------------------------------------- iter14 (mudança oficial): o approve pede a SENHA
# `cs-auto approve` passou a exigir a senha do humano, digitada num terminal (ver campanha-iter14/oraculo/ESPEC.md).
# O oráculo faz o papel do humano: roda o approve num pseudo-terminal REAL (pty.fork) e digita SENHA_TESTE a cada
# prompt `SENHA...:`. Não há bypass no produto: a senha só vale porque CS_SENHA_FILE aponta para um registro PBKDF2
# gerado com ela (formato da ESPEC iter14 §2.1). Todas as asserções seguem iguais; só muda COMO o approve é digitado.
import atexit as _atexit  # noqa: E402
import hashlib as _hashlib  # noqa: E402
import pty as _pty  # noqa: E402
import re as _re  # noqa: E402
import select as _select  # noqa: E402
import signal as _signal  # noqa: E402
import time as _time  # noqa: E402
import unicodedata as _ud  # noqa: E402

SENHA_TESTE = "Mandato-Seguro-2026"
_SENHA_PROMPT = _re.compile(rb"SENHA[^\r\n:]*:")
_SENHA_FILE = []


def senha_file():
    """Registro de senha de teste (PBKDF2-SHA256, 600000 iterações), num diretório temporário fora do alvo."""
    if not _SENHA_FILE:
        d = tempfile.mkdtemp(prefix="cs-senha-teste-")
        _atexit.register(shutil.rmtree, d, True)
        sv, sk = os.urandom(16).hex(), os.urandom(16).hex()
        nb = _ud.normalize("NFC", SENHA_TESTE.strip()).encode("utf-8")
        reg = {"versao": 1, "kdf": "pbkdf2-sha256", "iter": 600000, "salt_verificador": sv, "salt_chave": sk,
               "verificador": _hashlib.pbkdf2_hmac("sha256", nb, bytes.fromhex(sv), 600000, dklen=32).hex(),
               "criada_em": "2026-10-05T00:00:00Z"}
        p = os.path.join(d, "senha.json")
        with open(p, "w") as f:
            json.dump(reg, f)
        os.chmod(p, 0o600)
        _SENHA_FILE.append(p)
    return _SENHA_FILE[0]


def is_approve(args):
    """O subcomando (depois de --root/--actor) é `approve`?"""
    args, i = list(args), 0
    while i < len(args):
        if args[i] in ("--root", "--actor"):
            i += 2
            continue
        if args[i].startswith(("--root=", "--actor=")):
            i += 1
            continue
        return args[i] == "approve"
    return False


def run_tty(argv, cwd, env, timeout=300):
    """Roda argv num pty real (stdin = tty controlador) digitando SENHA_TESTE a cada prompt. (exit, saída)."""
    pid, fd = _pty.fork()
    if pid == 0:
        try:
            os.chdir(cwd)
            os.execve(argv[0], argv, env)
        finally:
            os._exit(127)
    buf, seen, deadline = b"", 0, _time.time() + timeout
    try:
        while True:
            if _time.time() > deadline:
                os.kill(pid, _signal.SIGKILL)
                raise AssertionError("approve no tty não terminou em %ss: %r" % (timeout, buf[-500:]))
            r, _, _ = _select.select([fd], [], [], 0.1)
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

# ---------------------------------------------------------------- máquina M5: interface FIXADA (ESPEC §2.1)
FIXED_STATES = {"PROPOSED", "CHARTERED", "PLANNING", "RUNNING", "INTEGRATING", "REPLANNING", "AWAITING_HUMAN",
                "PAUSED", "WRAPPING_UP", "DONE", "HANDED_BACK", "ABORTED"}
FIXED_TERMINAL = {"DONE", "HANDED_BACK", "ABORTED"}
W = ["PLANNING", "RUNNING", "INTEGRATING", "REPLANNING"]
FIXED_TRANSITIONS = {
    "propose": ([], "PROPOSED", ["target_exists", "class_allowed", "spec_present", "acceptance_executable",
                                 "acceptance_red", "no_open_mandate", "not_trivial"]),
    "approve": (["PROPOSED"], "CHARTERED", ["by_human", "acceptance_red"]),
    "amend": (["PROPOSED", "AWAITING_HUMAN"], "PROPOSED", ["by_human", "reason_present"]),
    "abort": (["PROPOSED", "AWAITING_HUMAN"], "ABORTED", ["by_human", "reason_present"]),
    "plan": (["CHARTERED"], "PLANNING", []),
    "plan_accept": (["PLANNING"], "RUNNING", ["not_trivial", "dag_acyclic", "dag_covers_acceptance", "nodes_in_territory",
                                              "nodes_fit_horizon", "plan_within_budget", "waves_computed",
                                              "lessons_consulted"]),
    "tick": (["RUNNING"], "=", []),
    "wave_closed": (["RUNNING"], "INTEGRATING", ["no_delegation_in_flight"]),
    "integrate_ok": (["INTEGRATING"], "RUNNING", ["regression_green", "pending_nodes"]),
    "integrate_replan": (["INTEGRATING"], "REPLANNING", ["replan_trigger", "replans_left"]),
    "integrate_done": (["INTEGRATING"], "DONE", ["acceptance_all_green", "final_review_pass"]),
    "next_feature": (["INTEGRATING"], "PLANNING", ["acceptance_all_green", "final_review_pass", "next_feature_queued"]),
    "replan_accept": (["REPLANNING"], "RUNNING", ["replan_cites_evidence", "accepted_nodes_untouched", "dag_acyclic",
                                                  "dag_covers_acceptance", "nodes_in_territory", "nodes_fit_horizon",
                                                  "plan_within_budget", "waves_computed", "plan_diff_recorded"]),
    "escalate": (W, "AWAITING_HUMAN", ["escalation_condition", "package_recorded"]),
    "resolve_resume": (["AWAITING_HUMAN"], "^", ["by_human", "choice_in_package", "decision_present"]),
    "resolve_reroute": (["AWAITING_HUMAN"], "^", ["by_human", "choice_in_package", "decision_present", "new_agent_valid"]),
    "resolve_drop": (["AWAITING_HUMAN"], "^", ["by_human", "choice_in_package", "decision_present"]),
    "pause": (W, "PAUSED", ["in_flight_marked"]),
    "resume": (["PAUSED"], "^", ["stamp_matches"]),
    "wrap_up": (W + ["AWAITING_HUMAN", "PAUSED"], "WRAPPING_UP", ["wrap_trigger"]),
    "hand_back": (["WRAPPING_UP"], "HANDED_BACK", ["no_delegation_in_flight", "report_generated", "open_items_returned"]),
}
# guardas que NÃO têm caminho legal para recusar (o motor as computa/garante) — exigidas só "vistas OK"
EXEMPT_REFUSAL = {"waves_computed", "lessons_consulted", "no_delegation_in_flight", "replan_trigger", "package_recorded",
                  "plan_diff_recorded", "in_flight_marked", "stamp_matches", "wrap_trigger", "report_generated",
                  "open_items_returned", "next_feature_queued"}

TEAM = {
    "schema_version": 1,
    "agents": [
        {"name": "dev-billing", "kind": "dev", "territory": ["src/billing/**", "src/shared/**"]},
        {"name": "dev-users", "kind": "dev", "territory": ["src/users/**", "src/shared/**"]},
        {"name": "qa", "kind": "qa", "territory": ["tests/**"]},
        {"name": "architect", "kind": "dev", "territory": ["docs/decisoes/**"]},
        {"name": "po", "kind": "product", "territory": ["docs/stories/**"]},
        {"name": "reviewer", "kind": "gate", "territory": []},
        {"name": "security", "kind": "gate", "territory": []},
    ],
}
RULES = {"facts": [
    {"id": "rule.billing.cents", "layer": "rules", "claim": "valores monetários em centavos inteiros",
     "scope": ["src/billing/**"], "evidence": [{"file": "src/billing/total.py", "line": 1}], "confidence": "high",
     "origin": "mechanical", "fingerprint": "x"},
    {"id": "rule.global.utf8", "layer": "rules", "claim": "arquivos em UTF-8", "scope": ["**"],
     "evidence": [{"file": "README.md"}], "confidence": "high", "origin": "mechanical", "fingerprint": "x"}]}
CONFIG = {"frozen_paths": ["src/shared/frozen/**"], "max_files_per_task": 3}
TEST_BILLING = ("import importlib.util\nimport unittest\n\n\nclass T(unittest.TestCase):\n    def test_total(self):\n"
                "        s = importlib.util.spec_from_file_location('total', 'src/billing/total.py')\n"
                "        m = importlib.util.module_from_spec(s)\n        s.loader.exec_module(m)\n"
                "        self.assertEqual(m.total([1, 2]), 3)\n")
FILES = {
    "README.md": "# demo\n",
    ".gitignore": "__pycache__/\n*.pyc\n",
    "src/billing/total.py": "def total(items):\n    return sum(items)\n",
    "src/users/model.py": "AGE = 18\n",
    "src/shared/util.py": "X = 0\n",
    "tests/__init__.py": "",
    "tests/test_billing.py": TEST_BILLING,
    "accept/__init__.py": "",
    "docs/decisoes/README.md": "decisões\n",
    "docs/stories/README.md": "stories\n",
    "spec/feature.md": "# Desconto no checkout\n\nAplicar desconto e perfil do cliente no checkout.\n",
}
ACS_STD = [("AC-1", "src/billing/discount.py"), ("AC-2", "src/users/profile.py"), ("AC-3", "tests/test_fluxo.py")]
ACS_2 = [("AC-1", "src/billing/discount.py"), ("AC-2", "src/users/profile.py")]


def ac_test_id(ac):
    return "accept.test_ac_%s" % ac.split("-")[1]


def ac_test_src(path):
    return ("import os\nimport unittest\n\n\nclass A(unittest.TestCase):\n    def test_ac(self):\n"
            "        p = %r\n        self.assertTrue(os.path.isfile(p) and 'OK' in open(p).read())\n" % path)


def crit(ac, path):
    """Formato da árvore (iter10 real, 0.7.0): critério testável = Dado/Quando/Então + test-id (senão "vago")."""
    return "%s|Dado o checkout Quando entrego %s Então tem OK|%s" % (ac, path, ac_test_id(ac))


def ok_text(path):
    b = os.path.basename(path)
    if b.startswith("test_") and b.endswith(".py"):
        return "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_ok(self):  # OK\n        self.assertTrue(True)\n"
    if path.endswith(".py"):
        return "OK = 1\n"
    return "OK\n"


# ====================================================================== observação (matriz de cobertura de M5)
MATRIX = {"edge": set(), "guard_ok": set(), "guard_no": set()}


def sd(root, *parts):
    return os.path.join(root, SD, *parts)


def rel(root, path):
    return os.path.relpath(path, root).replace(os.sep, "/")


def events_files(root):
    return [sd(root, "events.jsonl"), sd(root, "state", "events.jsonl")]


def _read_lines(p):
    if not os.path.isfile(p):
        return []
    out = []
    with open(p, "r", encoding="utf-8") as f:
        for x in f:
            x = x.strip()
            if not x:
                continue
            try:
                out.append(json.loads(x))
            except ValueError:
                pass
    return out


def all_events(root):
    out = []
    for p in events_files(root):
        out.extend(_read_lines(p))
    return out


def mevents(root, name=None):
    return [e for e in all_events(root) if isinstance(e, dict) and str(e.get("type") or "").startswith("mandato.")
            and (name is None or e.get("type") == "mandato." + name)]


def _account(e):
    if not isinstance(e, dict):
        return
    t = str(e.get("type") or "")
    if not t.startswith("mandato."):
        return
    d = e.get("data") if isinstance(e.get("data"), dict) else {}
    de = d.get("de")
    MATRIX["edge"].add((t.split(".", 1)[1], de if de not in ("", "∅") else None))
    for g in d.get("guardas") or []:
        MATRIX["guard_ok"].add(str(g))
    for r in d.get("guardas_recusadas") or []:
        if isinstance(r, dict) and r.get("guarda"):
            MATRIX["guard_no"].add(str(r["guarda"]))


def machines():
    return json5io.read(MACHINES)


def mandato_machine(M=None):
    """M5 mora DENTRO de machines.json5 → machines.mandato (desenho §5): vivacidade e cobertura oficiais a enxergam."""
    M = M or machines()
    mv = (M.get("machines") or {}).get("mandato")
    return mv if isinstance(mv, dict) else None


def m_edges(mv):
    """[(transição, de, para)] com "=" (mesmo estado) e "^" (volta ao estado de onde veio) expandidos."""
    tr = mv.get("transitions") or {}
    raw = []
    for name, t in tr.items():
        if not isinstance(t, dict):
            continue
        fr = t.get("from") or []
        for f in (fr if isinstance(fr, list) else [fr]):
            raw.append((name, f, t.get("to")))
    into = {}
    for name, f, to in raw:
        if to not in ("=", "^"):
            into.setdefault(to, set()).add(f)
    out = []
    for name, f, to in raw:
        if to == "=":
            out.append((name, f, f))
        elif to == "^":
            for prev in sorted(into.get(f, ())):
                out.append((name, f, prev))
        else:
            out.append((name, f, to))
    return out


# ====================================================================== infraestrutura
def walk_dicts(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            for x in walk_dicts(v):
                yield x
    elif isinstance(obj, list):
        for v in obj:
            for x in walk_dicts(v):
                yield x


def write(root, relp, txt):
    p = os.path.join(root, relp)
    os.makedirs(os.path.dirname(p) or root, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(txt)


def sha_file(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def git(root, *args):
    subprocess.run(["git"] + list(args), cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def folder_of(root, item_id, zone):
    out = []
    for dp, dns, fs in os.walk(sd(root, zone)):
        b = os.path.basename(dp)
        if (b == item_id or b.startswith(item_id + "-")) and any(f.endswith(".json5") for f in fs):
            out.append(rel(root, dp))
    return out


def files_with_text(root, zone, needle):
    out = []
    for dp, _, fs in os.walk(sd(root, zone)):
        for f in fs:
            if not f.endswith(".json5"):
                continue
            p = os.path.join(dp, f)
            try:
                with open(p, "r", encoding="utf-8") as fh:
                    txt = fh.read()
            except OSError:
                continue
            if needle in txt:
                out.append(p)
    return out


def has_reason(path):
    try:
        d = json5io.read(path)
    except Exception:
        return False
    for x in walk_dicts(d):
        for k, v in x.items():
            if re.search(r"motivo|reason|devolvid", str(k), re.I) and v:
                return True
    return False


class Fx(object):
    """Alvo de teste: raiz + ids da árvore + critérios."""

    def __init__(self, root, spr, feas, acs):
        self.root, self.spr, self.feas, self.acs = root, spr, feas, acs

    @property
    def fea(self):
        return self.feas[0]


class Base(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.roots = []
        self.clock = None
        self.human_calls = 0

    def tearDown(self):
        for r in self.roots:
            shutil.rmtree(r, ignore_errors=True)

    # ---------------------------------------------------------------- execução (observada)
    def _env(self, extra=None):
        e = dict(os.environ)
        for k in ("CLAUDE_PROJECT_DIR", "CS_ACTOR", "CS_GUARD_OFF", "CS_ROOT", "CS_NOW"):
            e.pop(k, None)
        if self.clock is not None:
            e["CS_NOW"] = self.clock.strftime("%Y-%m-%dT%H:%M:%SZ")
        e["CS_SENHA_FILE"] = senha_file()  # iter14: registro da senha de teste (fora do alvo)
        e.update(extra or {})
        return e

    def _run(self, root, argv, inp=None, env=None, is_auto=False):
        before = [len(_read_lines(p)) for p in events_files(root)]
        if is_auto and is_approve(argv[2:]):  # iter14: o approve é digitado num terminal, com a senha
            code, out = run_tty(argv, root, env or self._env())
            p = subprocess.CompletedProcess(argv, code)
            err = out
        else:
            p = subprocess.run(argv, cwd=root, env=env or self._env(), input=inp, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, timeout=300)
            out, err = p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
        for path, n in zip(events_files(root), before):
            for e in _read_lines(path)[n:]:
                _account(e)
        if is_auto and p.returncode == 1:
            for g in GUARD_RE.findall(err):
                MATRIX["guard_no"].add(g)
        return p.returncode, out, err

    def cs(self, root, *args, actor=None):
        argv = [sys.executable, STATE_PY, "--root", root] + (["--actor", actor] if actor else []) + list(args)
        return self._run(root, argv)

    def auto(self, root, *args, actor=None):
        argv = [sys.executable, AUTO_PY, "--root", root] + (["--actor", actor] if actor else []) + list(args)
        return self._run(root, argv, is_auto=True)

    def hook(self, root, mode, payload):
        return self._run(root, [sys.executable, GUARD_PY, mode], inp=json.dumps(payload).encode("utf-8"),
                         env=self._env({"CLAUDE_PROJECT_DIR": root}))

    # ---------------------------------------------------------------- asserções de CLI
    def ok_cs(self, root, *args, actor=None, msg=""):
        code, out, err = self.cs(root, *args, actor=actor)
        self.assertEqual(code, 0, "%s`cs-state %s` deveria passar (exit %d): %s%s" % (
            msg and msg + ": ", " ".join(args), code, out[-1500:], err[-1500:]))
        return out

    def ok_auto(self, root, *args, actor=None, msg=""):
        code, out, err = self.auto(root, *args, actor=actor)
        self.assertEqual(code, 0, "%s`cs-auto %s` deveria passar (exit %d): %s%s" % (
            msg and msg + ": ", " ".join(args), code, out[-1500:], err[-1500:]))
        return out

    def no_auto(self, root, *args, guard=None, contains=(), actor=None, msg=""):
        code, out, err = self.auto(root, *args, actor=actor)
        self.assertEqual(code, 1, "%s`cs-auto %s` deveria ser RECUSADO com exit 1 (veio %d): %s%s" % (
            msg and msg + ": ", " ".join(args), code, out[-1500:], err[-1500:]))
        if guard:
            self.assertIn(guard, GUARD_RE.findall(err), "%s`cs-auto %s`: a recusa deve vir da guarda `%s` "
                          "(stderr `guarda %s: <problema>`): %s" % (msg and msg + ": ", " ".join(args), guard, guard, err[-1500:]))
        for c in contains:
            self.assertIn(c, out + err, "%s`cs-auto %s`: a recusa deve citar %r: %s%s" % (
                msg and msg + ": ", " ".join(args), c, out[-800:], err[-800:]))
        return out + err

    def _human_argv(self, args):
        return list(args) + ["--by", HUMAN] + shlex.split(os.environ.get("CS_HUMAN_PROOF_ARGS", ""))

    def human(self, root, *args, msg=""):
        self.human_calls += 1
        return self.ok_auto(root, *self._human_argv(args), msg=msg or "ato HUMANO")

    def human_no(self, root, *args, guard=None, contains=(), msg=""):
        return self.no_auto(root, *self._human_argv(args), guard=guard, contains=contains, msg=msg)

    def tick(self, root):
        code, out, err = self.auto(root, "tick", "--json")
        self.assertEqual(code, 0, "`cs-auto tick --json` deveria passar (exit %d): %s%s" % (code, out[-1500:], err[-1500:]))
        try:
            t = json.loads(out)
        except ValueError:
            self.fail("`cs-auto tick --json` deve imprimir JSON puro: %r" % out[:800])
        self.assertIsInstance(t, dict, "tick --json é um objeto")
        return t

    def status(self, root):
        code, out, err = self.auto(root, "status", "--json")
        self.assertEqual(code, 0, "`cs-auto status --json` deveria passar (exit %d): %s%s" % (code, out[-1500:], err[-1500:]))
        try:
            st = json.loads(out)
        except ValueError:
            self.fail("`cs-auto status --json` deve imprimir JSON puro: %r" % out[:800])
        self.assertIsInstance(st, dict)
        return st

    def report(self, root):
        code, out, err = self.auto(root, "report", "--json")
        self.assertEqual(code, 0, "`cs-auto report --json` deveria passar (exit %d): %s%s" % (code, out[-1500:], err[-1500:]))
        try:
            return json.loads(out)
        except ValueError:
            self.fail("`cs-auto report --json` deve imprimir JSON puro: %r" % out[:800])

    def node(self, st, no):
        for n in (st.get("plano") or {}).get("nos") or []:
            if str(n.get("id")) == no:
                return n
        self.fail("nó %s ausente de status.plano.nos: %r" % (no, (st.get("plano") or {}).get("nos")))

    def esc_open(self, st):
        return [e for e in st.get("escaladas") or [] if e.get("aberta", True)]

    def stop_blocks(self, root):
        code, out, err = self.hook(root, "stop", {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": False})
        self.assertEqual(code, 0, "hook Stop não falha (exit %d): %s%s" % (code, out, err))
        try:
            d = json.loads(out) if out.strip() else {}
        except ValueError:
            d = {}
        return d.get("decision") == "block", str(d.get("reason") or "")

    def session_start(self, root, source="resume"):
        code, out, err = self.hook(root, "session-start", {"hook_event_name": "SessionStart", "source": source,
                                                           "session_id": "s2"})
        self.assertEqual(code, 0, "hook SessionStart (exit %d): %s%s" % (code, out, err))
        return out

    def pre_compact(self, root):
        code, out, err = self.hook(root, "pre-compact", {"hook_event_name": "PreCompact", "trigger": "auto",
                                                         "session_id": "s1"})
        self.assertEqual(code, 0, "hook PreCompact (guard.py pre-compact) deve existir e passar (exit %d): %s%s" % (code, out, err))
        return out

    def validate(self, root, strict=False, msg=""):
        args = ["validate"] + (["--strict"] if strict else [])
        code, out, err = self.cs(root, *args)
        self.assertEqual(code, 0, "%s`cs-state %s` deveria passar: %s%s" % (msg and msg + ": ", " ".join(args), out[-1500:], err[-1500:]))

    # ---------------------------------------------------------------- alvo de teste (árvore iter10)
    def make_repo(self, acs=ACS_STD, features=None, start_feature=True, collision=None):
        """features: [(título, [AC-ids])] — padrão: uma feature com todos os critérios."""
        root = os.path.realpath(tempfile.mkdtemp(prefix="cs-mandato-"))
        self.roots.append(root)
        for r, txt in FILES.items():
            write(root, r, txt)
        for ac, path in acs:
            write(root, "accept/test_ac_%s.py" % ac.split("-")[1], ac_test_src(path))
        write(root, os.path.join(SD, "team.json5"), json.dumps(TEAM, ensure_ascii=False, indent=1))
        write(root, os.path.join(SD, "facts", "rules.json5"), json.dumps(RULES, ensure_ascii=False))
        write(root, os.path.join(SD, "facts", "business_rules.json5"), "[]")
        write(root, os.path.join(SD, "facts", "glossary.json5"), "[]")
        write(root, os.path.join(SD, "knowledge", "collision.json5"),
              json.dumps(collision if collision is not None else {"do_not_parallelize": []}))
        git(root, "init", "-q")
        git(root, "config", "user.email", "t@t")
        git(root, "config", "user.name", "t")
        self.ok_cs(root, "init", msg="preparação")
        cfgp = sd(root, "harness", "config.json5")
        cfg = json5io.read(cfgp) if os.path.isfile(cfgp) else {}
        cfg = dict(cfg if isinstance(cfg, dict) else {}, **CONFIG)
        write(root, os.path.join(SD, "harness", "config.json5"), json.dumps(cfg, indent=1))
        out = self.ok_cs(root, "new", "sprint", "--meta", "entregar desconto", msg="preparação (árvore iter10)")
        got = CREATED_RE.findall(out)
        self.assertTrue(got, "`cs-state new sprint` imprime `criado SPR-nnn em <path>`: %r" % out)
        spr = got[0][0]
        self.ok_cs(root, "start", spr, msg="preparação (árvore iter10)")
        feas = []
        for title, ids in (features or [("Desconto no checkout", [a for a, _ in acs])]):
            aceite = "python3 -m unittest " + " ".join(ac_test_id(a) for a in ids)
            out = self.ok_cs(root, "new", "feature", "--title", title, "--sprint", spr, "--aceite", aceite,
                             msg="preparação (árvore iter10)")
            got = CREATED_RE.findall(out)
            self.assertTrue(got, "`cs-state new feature` imprime `criado FEA-nnn em <path>`: %r" % out)
            feas.append(got[0][0])
        if start_feature:
            self.ok_cs(root, "start", feas[0], msg="preparação (árvore iter10)")
        git(root, "add", "-A")
        git(root, "commit", "-qm", "base")
        return Fx(root, spr, feas, acs)

    def minimal_repo(self):
        """Só `cs-state init` (sem a árvore): para testes que não dependem da iter10."""
        root = os.path.realpath(tempfile.mkdtemp(prefix="cs-mandato-min-"))
        self.roots.append(root)
        for r, txt in FILES.items():
            write(root, r, txt)
        write(root, os.path.join(SD, "team.json5"), json.dumps(TEAM, ensure_ascii=False, indent=1))
        write(root, os.path.join(SD, "facts", "rules.json5"), json.dumps(RULES, ensure_ascii=False))
        write(root, os.path.join(SD, "facts", "business_rules.json5"), "[]")
        write(root, os.path.join(SD, "facts", "glossary.json5"), "[]")
        git(root, "init", "-q")
        self.ok_cs(root, "init", msg="preparação")
        return root

    def propose(self, fx, nos=3, classe=None, portoes=(), crits=None, extra=(), rigor=None):
        args = ["propose", "--feature", fx.fea, "--spec", "spec/feature.md", "--objetivo", OBJ, "--nos", str(nos),
                "--regressao", REGRESSAO]
        for c in (crits if crits is not None else [crit(a, p) for a, p in fx.acs]):
            args += ["--criterio", c]
        if classe:
            args += ["--classe", classe]
        for g in portoes:
            args += ["--portao", g]
        if rigor:
            args += ["--rigor", rigor]
        out = self.ok_auto(fx.root, *(args + list(extra)))
        m = MAN_RE.search(out)
        self.assertTrue(m, "`cs-auto propose` imprime o id `MAN-nnn`: %r" % out)
        st = self.status(fx.root)
        self.assertEqual(st.get("estado"), "PROPOSED", "propose → PROPOSED: %r" % st.get("estado"))
        self.assertEqual(st.get("mandato"), m.group(1))
        return m.group(1)

    def approve(self, fx, orc=ORC):
        self.human(fx.root, "approve", "--orcamento", orc)
        self.assertEqual(self.status(fx.root).get("estado"), "CHARTERED", "approve → CHARTERED")

    def add_node(self, root, n, drv=None):
        args = ["plan", "add-node", "--id", n["id"], "--tipo", n.get("tipo", "US"), "--agent", n["agent"],
                "--title", n.get("title", "N%s %s" % (n["id"], os.path.basename(n["paths"][0])))]
        for p in n["paths"]:
            args += ["--path", p]
        if n.get("deps"):
            args += ["--deps", ",".join(n["deps"])]
        args += ["--cobre", ",".join(n["cobre"])]
        if n.get("verify"):
            args += ["--verify-cmd", n["verify"]]
        if n.get("teste"):
            args += ["--teste", n["teste"]]
        self.ok_auto(root, *args, msg="add-node só valida sintaxe; guardas são do submit")
        if drv is not None:
            drv.nodes[n["id"]] = n

    def submit_plan(self, root, nodes, drv=None, motivo=None, evidencia=None):
        for n in nodes:
            self.add_node(root, n, drv)
        args = ["plan", "submit"]
        if motivo:
            args += ["--motivo", motivo]
        if evidencia:
            args += ["--evidencia", evidencia]
        return self.ok_auto(root, *args)

    def plan_refused(self, root, nodes, guard, contains=(), motivo=None, evidencia=None, msg=""):
        for n in nodes:
            self.add_node(root, n)
        args = ["plan", "submit"] + (["--motivo", motivo] if motivo else []) + (["--evidencia", evidencia] if evidencia else [])
        out = self.no_auto(root, *args, guard=guard, contains=contains, msg=msg)
        self.ok_auto(root, "plan", "reset", msg="descarta o rascunho recusado")
        return out

    def running(self, fx, nodes, orc=ORC, nos=None, **pk):
        self.propose(fx, nos=nos or max(2, len(nodes)), **pk)
        self.approve(fx, orc)
        t = self.tick(fx.root)
        self.assertEqual(t.get("acao"), "PLAN", "CHARTERED: o piloto dispara `plan` e pede o PLAN ao modelo: %r" % t)
        self.assertEqual(t.get("estado"), "PLANNING")
        self.assertIsInstance(t.get("licoes"), list, "PLAN traz as lições buscadas pelo motor (`licoes`, lista)")
        drv = Driver(self, fx.root, nodes)
        self.submit_plan(fx.root, nodes, drv)
        self.assertEqual(self.status(fx.root).get("estado"), "RUNNING", "plan_accept → RUNNING")
        return drv


# ====================================================================== o "modelo" simulado (executa só os nós de julgamento)
class Driver(object):
    """Lê `cs-auto tick --json` e executa a AÇÃO pedida, como o modelo faria. Não decide nada mecânico."""
    HANDLED = ("PLAN", "REPLAN", "DISPATCH", "IDLE_WAIT", "REVIEW", "REFLECT", "ANSWER_ORPHAN", "FINAL_REVIEW",
               "RESUME", "REPORT", "ASK_HUMAN", "FIM")

    def __init__(self, tc, root, nodes=None, behavior=None, content=None, on_replan=None, on_plan=None, on_reflect=None):
        self.tc, self.root = tc, root
        self.nodes = collections.OrderedDict((n["id"], n) for n in (nodes or []))
        self.behavior = behavior or {}
        self.content = content or {}
        self.on_replan, self.on_plan, self.on_reflect = on_replan, on_plan, on_reflect
        self.inflight = collections.OrderedDict()
        self.attempt = collections.Counter()
        self.dispatches = []
        self.parallel = []
        self.ticks = []
        self.after_step = None
        self.planned_once = False
        self.default_mode = "ok"

    def mode(self, no):
        b = self.behavior.get(no, self.default_mode)
        if isinstance(b, dict):
            return b.get(self.attempt[no], b.get("*", "ok"))
        if callable(b):
            return b(self.attempt[no])
        return b

    def files_for(self, no, mode, paths):
        att = self.attempt[no]
        if (no, att) in self.content:
            return self.content[(no, att)]
        if mode == "ok" and no in self.content:
            return self.content[no]
        txt = {"wrong": "ERRADO = 1\n", "partial": "PARCIAL = 1\n"}
        return {p: (txt[mode] if mode in txt else ok_text(p)) for p in paths}

    def deliver(self, task, keep=False):
        info = self.inflight[task]
        no, agent = info["no"], info["agent"]
        mode = self.mode(no)
        if mode == "hold":
            return
        if mode == "abstain":
            self.tc.ok_cs(self.root, "abstain", task, "--kind", "out_of_territory", "--reason",
                          "precisa de outro agente/território", actor=agent)
        else:
            files = self.files_for(no, mode, info["paths"])
            for p, txt in files.items():
                write(self.root, p, txt)
            args = ["submit", task]
            for p in files:
                args += ["--files-changed", p]
            args += ["--check", "unittest: OK", "--risk", "nenhum", "--handoff-notes", "ok"]
            self.tc.ok_cs(self.root, *args, actor=agent)
        if not keep:
            self.inflight.pop(task, None)

    def step(self, stop_on=()):
        """Executa a ação do tick — exceto se ela está em `stop_on` (aí o tick volta intacto para o teste agir)."""
        tc = self.tc
        t = tc.tick(self.root)
        self.ticks.append(t)
        act = t.get("acao")
        tc.assertIn(act, self.HANDLED, "ação desconhecida do piloto: %r (tick %r)" % (act, t))
        if act != "ASK_HUMAN":
            tc.assertFalse(HUMAN_ACT_RE.search(str(t.get("comando") or "")),
                           "o piloto NUNCA manda o modelo executar ato humano: %r" % t)
        if t.get("mandato"):
            tc.assertIn(OBJ, str(t.get("objetivo") or ""), "o objetivo vai em TODO tick (anti-deriva): %r" % t)
        if act in stop_on and act not in ("FIM", "ASK_HUMAN"):
            return t
        if act == "PLAN":
            if self.on_plan:
                self.on_plan(self, t)
            else:
                tc.assertFalse(self.planned_once, "PLAN repetido sem plano novo: %r" % t)
                self.planned_once = True
                tc.submit_plan(self.root, list(self.nodes.values()), self)
        elif act == "REPLAN":
            if not self.on_replan:
                tc.fail("REPLAN inesperado neste cenário: %r" % t)
            self.on_replan(self, t)
        elif act == "DISPATCH":
            task, no, agent = t.get("alvo"), str(t.get("no")), t.get("agente")
            tc.assertTrue(task and agent, "DISPATCH traz alvo (task) e agente: %r" % t)
            paths = (self.nodes.get(no) or {}).get("paths") or t.get("paths") or []
            tc.ok_cs(self.root, "dispatch", task, "--manual", "--model", t.get("model") or "sonnet")
            self.attempt[no] += 1
            self.inflight[task] = {"no": no, "agent": agent, "paths": paths}
            self.dispatches.append((task, no, agent))
            self.parallel.append(set(i["no"] for i in self.inflight.values()))
        elif act == "IDLE_WAIT":
            tc.assertTrue(self.inflight, "IDLE_WAIT sem nada em voo: %r" % t)
            for task in list(self.inflight):
                self.deliver(task)
        elif act == "REVIEW":
            gate = t.get("agente")
            tc.assertIn(gate, GATES, "REVIEW é de um gate: %r" % t)
            no = str(t.get("no"))
            p = ((self.nodes.get(no) or {}).get("paths") or ["README.md"])[0]
            tc.ok_cs(self.root, "review", t.get("alvo"), "--by", gate, "--verdict", "PASS", "--findings",
                     "conferido: %s:1 e verify verde" % p)
        elif act == "REFLECT":
            if self.on_reflect:
                self.on_reflect(self, t)
            else:
                ev = t.get("evidencia") or []
                tc.assertTrue(ev and ev[0].get("ref"), "REFLECT traz a evidência externa (evidencia[].ref): %r" % t)
                tc.ok_auto(self.root, "reflect", t.get("alvo"), "--texto",
                           "falhou: %s; por quê: saída do verify; muda: escrever o marcador OK" % ev[0]["ref"],
                           "--evidencia", ev[0]["ref"])
        elif act == "ANSWER_ORPHAN":
            tc.ok_auto(self.root, "orphan", t.get("alvo"))
            self.inflight.pop(t.get("alvo"), None)
        elif act == "FINAL_REVIEW":
            gate = t.get("agente")
            tc.assertIn(gate, GATES, "FINAL_REVIEW é de um gate: %r" % t)
            tc.ok_auto(self.root, "final-review", "--by", gate, "--verdict", "PASS", "--findings",
                       "aceite executado pelo motor, todos os critérios verdes; diff conferido")
        elif act == "RESUME":
            tc.ok_auto(self.root, "resume")
        elif act == "REPORT":
            tc.ok_auto(self.root, "report")
        elif act == "FIM":
            tc.assertIn(t.get("estado"), TERMINAIS, "FIM só em estado terminal: %r" % t)
        return t

    def run(self, stop_on=("FIM", "ASK_HUMAN"), until=None, max_steps=160):
        for _ in range(max_steps):
            t = self.step(stop_on)
            if self.after_step:
                self.after_step(self, t)
            if until is not None and until(self, t):
                return t
            if t.get("acao") in stop_on:
                return t
        self.tc.fail("o piloto não convergiu em %d ticks; últimas ações: %r" % (
            max_steps, [(x.get("estado"), x.get("acao"), x.get("alvo")) for x in self.ticks[-8:]]))

    def dispatched_nos(self):
        return [no for _, no, _ in self.dispatches]

    def idx(self, acao, no=None):
        return [i for i, t in enumerate(self.ticks) if t.get("acao") == acao and (no is None or str(t.get("no")) == no)]


def N(no, agent, paths, cobre, deps=(), **kw):
    d = {"id": no, "agent": agent, "paths": list(paths), "cobre": list(cobre), "deps": list(deps)}
    d.update(kw)
    return d


NODES_STD = [N("01", "dev-billing", ["src/billing/discount.py"], ["AC-1"]),
             N("02", "dev-users", ["src/users/profile.py"], ["AC-2"]),
             N("03", "qa", ["tests/test_fluxo.py"], ["AC-3"], deps=["01", "02"])]
NODES_2 = [N("01", "dev-billing", ["src/billing/discount.py"], ["AC-1"]),
           N("02", "dev-users", ["src/users/profile.py"], ["AC-2"])]
ACS_FROZEN = [("AC-1", "src/shared/frozen/rates.py"), ("AC-2", "src/users/profile.py"), ("AC-3", "tests/test_rates.py")]
NODES_FROZEN = [N("01", "dev-billing", ["src/shared/frozen/rates.py"], ["AC-1"]),
                N("02", "dev-users", ["src/users/profile.py"], ["AC-2"]),
                N("03", "qa", ["tests/test_rates.py"], ["AC-3"], deps=["01"])]


# ====================================================================== AUTO-LIVE
class TestAutoLive(Base):
    def _mv(self):
        mv = mandato_machine()
        self.assertIsNotNone(mv, "machines.json5 deve declarar a máquina M5 `mandato` (fonte única; ESPEC §2.1)")
        return mv

    def test_maquina_mandato_com_interface_fixada(self):
        mv = self._mv()
        self.assertEqual(set(mv.get("states") or []), FIXED_STATES, "estados de M5 (ESPEC §2.1)")
        self.assertEqual(mv.get("initial"), "PROPOSED")
        self.assertEqual(set(mv.get("terminal") or []), FIXED_TERMINAL)
        self.assertIn("AWAITING_HUMAN", mv.get("awaiting_human") or [], "AWAITING_HUMAN declarado como espera humana")
        tr = mv.get("transitions") or {}
        for name, (fr, to, guards) in FIXED_TRANSITIONS.items():
            self.assertIn(name, tr, "transição %s ausente" % name)
            t = tr[name]
            self.assertEqual(set(t.get("from") or []), set(fr), "%s.from" % name)
            self.assertEqual(t.get("to"), to, "%s.to" % name)
            self.assertTrue(set(guards) <= set(t.get("guards") or []), "%s.guards ⊇ %s (veio %s)" % (name, guards, t.get("guards")))

    def test_sem_beco_sem_saida_e_terminais_sem_saida(self):
        mv = self._mv()
        es = m_edges(mv)
        com_saida = {f for _, f, _ in es}
        terminal = set(mv.get("terminal") or [])
        for s in mv.get("states") or []:
            if s in terminal:
                self.assertNotIn(s, com_saida, "mandato.%s é terminal: não tem saída" % s)
            else:
                self.assertIn(s, com_saida, "mandato.%s não tem transição de saída e não é terminal" % s)

    def test_aguardando_humano_e_pausado_nao_terminais_com_saidas(self):
        mv = self._mv()
        es = m_edges(mv)
        terminal = set(mv.get("terminal") or [])
        for s in ("AWAITING_HUMAN", "PAUSED"):
            self.assertNotIn(s, terminal, "mandato.%s nunca é terminal" % s)
        dest = {to for _, f, to in es if f == "AWAITING_HUMAN"}
        for need, why in (("RUNNING", "retomar/trocar-agente/descartar-ramo"), ("PROPOSED", "emendar"),
                          ("WRAPPING_UP", "encerrar"), ("ABORTED", "abortar")):
            self.assertIn(need, dest, "AWAITING_HUMAN precisa de saída para %s (%s); destinos: %s" % (need, why, sorted(dest)))
        names = {n for n, f, _ in es if f == "AWAITING_HUMAN"}
        for n in ("resolve_resume", "resolve_reroute", "resolve_drop", "amend", "wrap_up", "abort"):
            self.assertIn(n, names)
        self.assertIn("resume", {n for n, f, _ in es if f == "PAUSED"}, "PAUSED sai por resume")

    def test_todo_estado_alcancavel(self):
        mv = self._mv()
        es = m_edges(mv)
        seen, stack = {"PROPOSED"}, ["PROPOSED"]
        while stack:
            cur = stack.pop()
            for _, f, to in es:
                if f == cur and to not in seen:
                    seen.add(to)
                    stack.append(to)
        self.assertFalse(set(mv.get("states") or []) - seen, "inalcançáveis: %s" % sorted(set(mv.get("states") or []) - seen))

    def test_m2_escalated_e_abstained_seguem_com_saidas(self):
        m2 = machines()["machines"]["delegation"]
        terminal = set(m2.get("terminal") or [])
        for s in ("ESCALATED", "ABSTAINED"):
            self.assertNotIn(s, terminal)
            dest = set()
            for name, t in (m2.get("transitions") or {}).items():
                if s in (t.get("from") or []):
                    dest.add(t.get("to"))
            self.assertIn("BRIEFED", dest, "%s: retomar" % s)
            self.assertIn("REROUTED", dest, "%s: trocar de agente" % s)
            self.assertTrue(dest & terminal, "%s: descartar" % s)


# ====================================================================== instalação e prosa (D12)
class TestInstalacao(Base):
    def test_cs_auto_instalavel_com_hook_pre_compact(self):
        self.assertTrue(os.path.isfile(AUTO_PY), "o piloto mora em scripts/harness/engine/auto.py")
        with open(INSTALL_PY, "r", encoding="utf-8") as f:
            txt = f.read()
        self.assertRegex(txt, r"ENGINE_FILES\s*=\s*\[[^\]]*\"auto\.py\"", "install copia auto.py")
        self.assertRegex(txt, r"BINS\s*=\s*\[[^\]]*\"cs-auto\"", "install cria o bin cs-auto")
        self.assertRegex(txt, r"\(\s*\"PreCompact\"\s*,[^)]*\"pre-compact\"", "install registra o hook PreCompact")
        self.pre_compact(self.minimal_repo())  # sem mandato: no-op, exit 0

    def test_prosa_nao_conduz_o_loop(self):
        with open(os.path.join(TEMPLATES, "feature-autonoma.md"), "r", encoding="utf-8") as f:
            fa = f.read()
        self.assertIn("cs-auto propose", fa, "o comando do autônomo usa o motor")
        self.assertIn("cs-auto tick", fa, "o loop é `cs-auto tick`, não o modelo")
        self.assertNotIn("até REPORTING", fa, "nada de 'siga next até REPORTING' (D12)")
        self.assertNotIn("Proponha o orçamento", fa, "orçamento é derivado pelo motor, não proposto pelo modelo")
        with open(os.path.join(TEMPLATES, "orchestrator.md"), "r", encoding="utf-8") as f:
            self.assertIn("cs-auto tick", f.read(), "kernel cita o piloto")


# ====================================================================== AUTO-START-1 / AUTO-START-2
class TestPropose(Base):
    def test_start1_recusas_acionaveis_e_nada_criado(self):
        fx = self.make_repo(acs=ACS_2)
        r = fx.root
        base = ["--spec", "spec/feature.md", "--objetivo", OBJ, "--nos", "2", "--regressao", REGRESSAO]
        good = ["--criterio", crit("AC-1", "src/billing/discount.py"), "--criterio", crit("AC-2", "src/users/profile.py")]
        self.no_auto(r, "propose", "--feature", "FEA-999", *(base + good), guard="target_exists", contains=("FEA-999",))
        self.no_auto(r, "propose", "--feature", fx.fea, "--spec", "spec/nao-existe.md", *(base[2:] + good),
                     guard="spec_present", contains=("spec",))
        self.no_auto(r, "propose", "--feature", fx.fea, *(base + ["--criterio", "AC-1|Dado x Quando y Então z|accept.test_nao_existe",
                                                                  "--criterio", crit("AC-2", "src/users/profile.py")]),
                     guard="acceptance_executable", contains=("accept.test_nao_existe",))
        self.no_auto(r, "propose", "--feature", fx.fea, *(base + ["--criterio", "AC-1|Dado x Quando y Então já verde|tests.test_billing",
                                                                  "--criterio", crit("AC-2", "src/users/profile.py")]),
                     guard="acceptance_red", contains=("AC-1",))
        self.no_auto(r, "propose", "--feature", fx.fea, *(base + good + ["--classe", "pergunta"]), guard="class_allowed")
        st = self.status(r)
        self.assertIsNone(st.get("mandato"), "recusas não criam mandato (status --json → mandato: null)")
        self.assertFalse(mevents(r, "propose"), "recusa não grava evento mandato.propose")
        self.propose(fx, nos=2)
        self.no_auto(r, "propose", "--feature", fx.fea, *(base + good), guard="no_open_mandate", contains=("MAN-",))

    def test_start2_um_no_e_classe_avulsa_recusam_use_task_avulsa(self):
        fx = self.make_repo(acs=ACS_2)
        r = fx.root
        args = ["propose", "--feature", fx.fea, "--spec", "spec/feature.md", "--objetivo", OBJ, "--regressao", REGRESSAO,
                "--criterio", crit("AC-1", "src/billing/discount.py"), "--criterio", crit("AC-2", "src/users/profile.py")]
        self.no_auto(r, *(args + ["--nos", "1"]), guard="not_trivial", contains=("avulsa",))
        for c in ("pequena", "trivial"):
            self.no_auto(r, *(args + ["--nos", "2", "--classe", c]), guard="class_allowed", contains=("avulsa",))
        self.propose(fx, nos=2)
        self.approve(fx)
        self.assertEqual(self.tick(r).get("acao"), "PLAN")
        self.plan_refused(r, [N("01", "dev-billing", ["src/billing/discount.py"], ["AC-1", "AC-2"])], "not_trivial",
                          contains=("avulsa",), msg="plano de 1 nó")
        self.assertEqual(self.status(r).get("estado"), "PLANNING")

    def test_proposta_orcamento_derivado_emenda_e_abort_humanos(self):
        fx = self.make_repo(acs=ACS_STD)
        r = fx.root
        self.propose(fx, nos=3)
        orc = self.status(r).get("orcamento") or {}
        for k in ("despachos", "tentativas", "replanos", "minutos"):
            self.assertIn(k, orc, "orçamento derivado pelo motor tem %s" % k)
            self.assertGreater(float(orc[k].get("limite") or 0), 0, "%s.limite > 0" % k)
            self.assertEqual(float(orc[k].get("usado") or 0), 0, "%s.usado = 0 na proposta" % k)
        self.assertGreaterEqual(int(orc["despachos"]["limite"]), 3, "despachos ≥ nós estimados")
        self.assertGreaterEqual(int(orc["tentativas"]["limite"]), int(orc["despachos"]["limite"]))
        self.human_no(r, "amend", guard="reason_present", msg="emenda sem motivo")
        self.human(r, "amend", "--reason", "ajusta orçamento", "--orcamento", "despachos=9,tentativas=18,replanos=2,minutos=90")
        st = self.status(r)
        self.assertEqual(st.get("estado"), "PROPOSED")
        self.assertEqual(int(st["orcamento"]["despachos"]["limite"]), 9, "emenda humana troca o orçamento")
        self.assertTrue([e for e in mevents(r, "amend") if (e.get("data") or {}).get("de") == "PROPOSED"])
        self.no_auto(r, "abort", "--by", "orchestrator", "--reason", "x", guard="by_human")
        self.human_no(r, "abort", guard="reason_present")
        self.human(r, "abort", "--reason", "humano rejeitou a proposta")
        self.assertEqual(self.status(r).get("estado"), "ABORTED")
        self.assertEqual(self.tick(r).get("acao"), "FIM")
        self.propose(fx, nos=3)  # terminal não bloqueia um mandato novo

    def test_approve_so_humano_e_com_aceite_ainda_vermelho_grava_baseline(self):
        fx = self.make_repo(acs=ACS_2)
        r = fx.root
        self.propose(fx, nos=2)
        for who in ("orchestrator", "lead", "dev-billing", "reviewer"):
            self.no_auto(r, "approve", "--by", who, guard="by_human", msg="approve por %s" % who)
        write(r, "src/billing/discount.py", "OK = 1\n")
        write(r, "src/users/profile.py", "OK = 1\n")
        self.human_no(r, "approve", guard="acceptance_red", msg="aceite ficou verde antes da aprovação")
        os.remove(os.path.join(r, "src/billing/discount.py"))
        os.remove(os.path.join(r, "src/users/profile.py"))
        self.approve(fx)
        st = self.status(r)
        b = st.get("baseline") or {}
        ac = b.get("aceite") or []
        self.assertEqual(sorted(x.get("id") for x in ac), ["AC-1", "AC-2"], "baseline do aceite por critério")
        for x in ac:
            self.assertFalse(x.get("verde"), "baseline: aceite vermelho")
            self.assertRegex(str(x.get("output_sha256")), HEX64)
        rg = b.get("regressao") or {}
        self.assertEqual(rg.get("exit"), 0, "baseline: regressão verde")
        self.assertRegex(str(rg.get("output_sha256")), HEX64)
        ap = mevents(r, "approve")
        self.assertTrue(ap and HEX64.match(str((ap[-1].get("data") or {}).get("assinatura"))), "approve grava assinatura sha256")


# ====================================================================== AUTO-PLAN-1/2/3
class TestPlano(Base):
    def test_plan1_recusas_com_o_problema_exato(self):
        fx = self.make_repo(acs=ACS_STD)
        r = fx.root
        self.propose(fx, nos=3)
        self.approve(fx)
        self.assertEqual(self.tick(r).get("acao"), "PLAN")
        a, b, c = NODES_STD
        cyc = [dict(a, deps=["02"]), dict(b, deps=["01"]), c]
        out = self.plan_refused(r, cyc, "dag_acyclic", msg="ciclo")
        self.assertTrue("01" in out and "02" in out, "a recusa cita os nós do ciclo: %s" % out[-500:])
        self.plan_refused(r, [a, b], "dag_covers_acceptance", contains=("AC-3",), msg="critério sem nó")
        self.plan_refused(r, [dict(a, paths=["src/users/x.py"]), b, c], "nodes_in_territory",
                          contains=("src/users/x.py",), msg="nó fora do território do agente")
        big = dict(a, paths=["src/billing/a.py", "src/billing/b.py", "src/billing/c.py", "src/billing/d.py"])
        self.plan_refused(r, [big, b, c], "nodes_fit_horizon", msg="nó maior que max_files_per_task")
        self.assertEqual(self.status(r).get("estado"), "PLANNING", "recusas não saem de PLANNING")
        self.assertFalse(mevents(r, "plan_accept"))
        self.submit_plan(r, NODES_STD)
        self.assertEqual(self.status(r).get("estado"), "RUNNING")

    def test_plan1_plano_acima_do_orcamento(self):
        fx = self.make_repo(acs=ACS_STD)
        self.propose(fx, nos=3)
        self.approve(fx, "despachos=2,tentativas=40,replanos=3,minutos=600")
        self.assertEqual(self.tick(fx.root).get("acao"), "PLAN")
        self.plan_refused(fx.root, NODES_STD, "plan_within_budget", msg="3 nós com 2 despachos")

    def test_plan2_ondas_calculadas_e_paralelo_real(self):
        acs = [("AC-1", "docs/decisoes/adr-001.md"), ("AC-2", "src/billing/discount.py"),
               ("AC-3", "src/users/profile.py"), ("AC-4", "tests/test_fluxo.py")]
        fx = self.make_repo(acs=acs)
        nodes = [N("01", "architect", ["docs/decisoes/adr-001.md"], ["AC-1"]),
                 N("02", "dev-billing", ["src/billing/discount.py"], ["AC-2"], deps=["01"]),
                 N("03", "dev-users", ["src/users/profile.py"], ["AC-3"], deps=["01"]),
                 N("04", "qa", ["tests/test_fluxo.py"], ["AC-4"], deps=["02", "03"])]
        drv = self.running(fx, nodes, nos=4)
        st = self.status(fx.root)
        self.assertEqual((st.get("plano") or {}).get("ondas"), [["01"], ["02", "03"], ["04"]], "ondas calculadas pelo motor")
        drv.run(until=lambda d, t: {"02", "03"} <= set(i["no"] for i in d.inflight.values()), stop_on=("FIM", "ASK_HUMAN"))
        self.assertTrue({"02", "03"} <= set(i["no"] for i in drv.inflight.values()), "02 e 03 em voo ao mesmo tempo")
        self.assertEqual(drv.dispatched_nos()[0], "01", "01 primeiro (dependência)")

    def _never_parallel(self, collision, nodes, acs):
        fx = self.make_repo(acs=acs, collision=collision)
        drv = self.running(fx, nodes, nos=2)
        ondas = (self.status(fx.root).get("plano") or {}).get("ondas") or []
        self.assertFalse([w for w in ondas if "01" in w and "02" in w], "01 e 02 em sub-ondas diferentes: %r" % ondas)
        self.assertEqual(sorted(x for w in ondas for x in w), ["01", "02"])
        drv.run()
        self.assertFalse([s for s in drv.parallel if {"01", "02"} <= s], "nunca em voo juntos")
        self.assertEqual(self.status(fx.root).get("estado"), "DONE")

    def test_plan3_arquivo_comum_vai_para_subondas(self):
        acs = [("AC-1", "src/shared/util.py"), ("AC-2", "src/users/profile.py")]
        self._never_parallel(None, [N("01", "dev-billing", ["src/shared/util.py"], ["AC-1"]),
                                    N("02", "dev-users", ["src/shared/util.py", "src/users/profile.py"], ["AC-2"])], acs)

    def test_plan3_par_do_not_parallelize_vai_para_subondas(self):
        col = {"do_not_parallelize": [{"a": "dev-billing", "b": "dev-users", "co_change": 7}]}
        self._never_parallel(col, NODES_2, ACS_2)


# ====================================================================== AUTO-HAPPY
class TestFluxoFeliz(Base):
    def test_happy_done_sem_toque_humano_apos_approve(self):
        fx = self.make_repo(acs=ACS_STD)
        r = fx.root
        drv = self.running(fx, NODES_STD)
        self.assertEqual((self.status(r).get("plano") or {}).get("ondas"), [["01", "02"], ["03"]])
        self.no_auto(r, "final-review", "--by", "reviewer", "--verdict", "PASS", "--findings", "cedo demais",
                     msg="revisão final antes do aceite verde")
        humans = self.human_calls
        seen = {"author": False}

        def after(d, t):
            if t.get("acao") == "FINAL_REVIEW" and not seen["author"]:
                seen["author"] = True
                self.assertNotIn(t.get("agente"), {"dev-billing", "dev-users", "qa"}, "revisor final ≠ autores")
                self.no_auto(r, "final-review", "--by", "dev-billing", "--verdict", "PASS", "--findings", "eu mesmo",
                             guard="final_review_pass", msg="autor revisando a frente")
        drv.after_step = after
        drv.run()
        self.assertTrue(seen["author"], "houve FINAL_REVIEW")
        self.assertEqual(self.human_calls, humans, "nenhum toque humano depois do approve")
        st = self.status(r)
        self.assertEqual(st.get("estado"), "DONE")
        self.assertEqual(((st.get("aceite") or {}).get("verdes"), (st.get("aceite") or {}).get("total")), (3, 3))
        for no in ("01", "02", "03"):
            self.assertEqual(self.node(st, no).get("estado"), "ACCEPTED")
        self.assertTrue(any("/3" in str(t.get("progresso") or "") for t in drv.ticks), "progresso 'x/3' nos ticks")
        self.assertTrue(mevents(r, "integrate_ok"), "2 ondas: houve integrate_ok")
        self.assertTrue(mevents(r, "integrate_done"))
        rep = self.report(r)
        self.assertEqual(rep.get("resultado"), "DONE")
        crs = rep.get("criterios") or []
        self.assertEqual(len(crs), 3)
        for c in crs:
            self.assertTrue(c.get("verde"), c)
            self.assertRegex(str(c.get("output_sha256")), HEX64, "relatório cita output_sha256 do aceite executado pelo motor")
        self.assertIn((rep.get("revisao_final") or {}).get("by"), GATES)
        self.assertFalse([e for e in all_events(r) if e.get("type") in ("delegation.waive_verify",)],
                         "o mandato nunca usa a exceção humana de verify")
        self.validate(r, msg="HAPPY")


# ====================================================================== AUTO-RETRY / AUTO-SAME-FAIL
class TestFalhaERecuperacao(Base):
    def test_retry_exige_reflexao_ancorada_e_grava_licao_candidata(self):
        fx = self.make_repo(acs=ACS_2)
        r = fx.root
        nodes = [N("01", "dev-billing", ["src/billing/discount.py"], ["AC-1"], verify="python3 -m unittest accept.test_ac_1"),
                 N("02", "dev-users", ["src/users/profile.py"], ["AC-2"])]
        drv = self.running(fx, nodes)
        drv.behavior = {"01": {1: "wrong", "*": "ok"}}
        token = "REFLEXAO-7Q"
        cand = {"ok": False}

        def on_reflect(d, t):
            ev = t.get("evidencia") or []
            self.assertTrue(ev and ev[0].get("ref"), "REFLECT traz evidencia[].ref do verify que falhou: %r" % t)
            self.no_auto(r, "reflect", t["alvo"], "--texto", "vou tentar de novo com mais cuidado",
                         contains=(), msg="reflexão sem citar o sinal externo")
            self.no_auto(r, "reflect", t["alvo"], "--texto", "acho que errei", "--evidencia", "nada-a-ver",
                         msg="evidência que não é do sinal externo")
            self.ok_auto(r, "reflect", t["alvo"], "--texto", "%s falhou %s: faltou o marcador OK; muda: escrever OK" % (
                token, ev[0]["ref"]), "--evidencia", ev[0]["ref"])

        def after(d, t):
            if not cand["ok"] and d.attempt["01"] >= 2:
                st = self.status(r)
                if self.node(st, "01").get("estado") == "ACCEPTED":
                    lc = st.get("licoes_candidatas") or []
                    self.assertTrue([x for x in lc if token in json.dumps(x, ensure_ascii=False)],
                                    "reflexão vira lição candidata após o retry passar: %r" % lc)
                    cand["ok"] = True
        drv.on_reflect = on_reflect
        drv.after_step = after
        drv.run()
        d1, rf, d2 = drv.idx("DISPATCH", "01"), drv.idx("REFLECT", "01"), None
        self.assertEqual(len(d1), 2, "um retry só")
        self.assertTrue(rf and d1[0] < rf[0] < d1[1], "REFLECT entre a falha e o retry: %r" % [(t.get("acao"), t.get("no")) for t in drv.ticks])
        self.assertTrue(cand["ok"])
        self.assertTrue(files_with_text(r, "state", token) + files_with_text(r, "archive", token),
                        "a reflexão entra no brief/registro da task do retry")
        self.assertEqual(self.status(r).get("estado"), "DONE")

    def test_same_fail_duas_vezes_nao_tenta_a_terceira_com_o_mesmo_agente(self):
        acs = [("AC-1", "src/shared/calc.py"), ("AC-2", "tests/test_fluxo.py")]
        fx = self.make_repo(acs=acs)
        nodes = [N("01", "dev-billing", ["src/shared/calc.py"], ["AC-1"], verify="python3 -m unittest accept.test_ac_1"),
                 N("02", "qa", ["tests/test_fluxo.py"], ["AC-2"])]
        drv = self.running(fx, nodes)
        drv.behavior = {"01": "wrong"}
        drv.on_replan = lambda d, t: None
        t = drv.run(until=lambda d, t: len(d.idx("DISPATCH", "01")) >= 3 or t.get("acao") == "REPLAN")
        by_billing = [x for x in drv.dispatches if x[1] == "01" and x[2] == "dev-billing"]
        self.assertEqual(len(by_billing), 2, "mesma falha 2× → não há 3ª tentativa com o mesmo agente")
        if t.get("acao") == "DISPATCH":
            self.assertNotEqual(t.get("agente"), "dev-billing", "reroute para outro agente do território")
        else:
            self.assertEqual(t.get("acao"), "REPLAN")
            self.assertEqual(t.get("estado"), "REPLANNING")


# ====================================================================== AUTO-REPLAN-1 / AUTO-REPLAN-CAP / AUTO-REGRESS
class TestReplano(Base):
    def _ate_replanning(self, orc=ORC):
        fx = self.make_repo(acs=ACS_STD)
        nodes = [N("01", "dev-billing", ["src/billing/discount.py"], ["AC-1"]),
                 N("02", "dev-users", ["src/users/profile.py"], ["AC-2"]),
                 N("03", "qa", ["tests/test_fluxo.py"], ["AC-3"], deps=["01"])]
        drv = self.running(fx, nodes, orc=orc)
        drv.behavior = {"02": "partial"}
        t = drv.run(stop_on=("REPLAN", "FIM", "ASK_HUMAN"))
        self.assertEqual(t.get("acao"), "REPLAN", "DAG esgotado com aceite 2/3: o mandato REPLANEJA, não para em silêncio")
        return fx, drv, t

    def test_replan1_dag_esgotado_replaneja_com_evidencia_e_nos_aceitos_intocados(self):
        fx, drv, t = self._ate_replanning()
        r = fx.root
        st = self.status(r)
        self.assertEqual(st.get("estado"), "REPLANNING")
        self.assertEqual(((st.get("aceite") or {}).get("verdes"), (st.get("aceite") or {}).get("total")), (2, 3))
        for no in ("01", "02", "03"):
            self.assertEqual(self.node(st, no).get("estado"), "ACCEPTED")
        blk, why = self.stop_blocks(r)
        self.assertTrue(blk and "REPLAN" in why, "Stop bloqueia em REPLANNING com a ação do tick: %r" % why)
        ir = mevents(r, "integrate_replan")
        rec = [g.get("guarda") for e in ir for g in ((e.get("data") or {}).get("guardas_recusadas") or [])]
        self.assertIn("pending_nodes", rec, "integrate_ok recusada por DAG esgotado (guardas_recusadas)")
        self.assertIn("acceptance_all_green", rec, "integrate_done recusada por aceite incompleto")
        ev = t.get("evidencia") or []
        self.assertTrue(ev and ev[0].get("ref"), "REPLAN traz evidencia[].ref: %r" % t)
        n4 = N("04", "dev-users", ["src/users/profile.py"], ["AC-2"])
        self.plan_refused(r, [n4], "replan_cites_evidence", motivo="acho que falta algo", msg="replano sem evidência")
        self.ok_auto(r, "plan", "edit-node", "--id", "02", "--path", "src/users/outro.py",
                     msg="edit-node só valida sintaxe; a guarda é do submit")
        self.no_auto(r, "plan", "submit", "--motivo", "AC-2 vermelho", "--evidencia", ev[0]["ref"],
                     guard="accepted_nodes_untouched", msg="replano mexe em nó ACCEPTED")
        self.ok_auto(r, "plan", "reset")
        self.plan_refused(r, [N("04", "qa", ["tests/test_x.py"], ["AC-3"])], "dag_covers_acceptance",
                          motivo="AC-2 vermelho", evidencia=ev[0]["ref"], msg="replano sem nó novo para o critério vermelho")
        self.submit_plan(r, [n4], drv, motivo="AC-2 segue vermelho após o DAG", evidencia=ev[0]["ref"])
        st = self.status(r)
        self.assertEqual(st.get("estado"), "RUNNING")
        self.assertEqual((st.get("plano") or {}).get("versao"), 2)
        p2 = os.path.join(r, st.get("pasta") or "", "plano.v2.json5")
        self.assertTrue(os.path.isfile(p2), "plano.v2.json5 gravado na pasta do mandato")
        with open(p2, "r", encoding="utf-8") as f:
            self.assertIn("AC-2 segue vermelho", f.read(), "diff/motivo do replano gravado")
        for no in ("01", "02", "03"):
            self.assertEqual(self.node(st, no).get("estado"), "ACCEPTED", "nós ACCEPTED intocados no v2")
        drv.run()
        self.assertEqual(self.status(r).get("estado"), "DONE")

    def test_replan_cap_esgotado_escala_suave_com_opcoes(self):
        fx, drv, t = self._ate_replanning(orc="despachos=20,tentativas=40,replanos=1,minutos=600")
        r = fx.root
        drv.behavior["04"] = "partial"
        self.submit_plan(r, [N("04", "dev-users", ["src/users/profile.py"], ["AC-2"])], drv,
                         motivo="AC-2 vermelho", evidencia=t["evidencia"][0]["ref"])
        t = drv.run()
        self.assertEqual(t.get("acao"), "ASK_HUMAN")
        st = self.status(r)
        self.assertEqual(st.get("estado"), "AWAITING_HUMAN")
        es = self.esc_open(st)
        self.assertTrue(es, "pacote de escalada aberto")
        self.assertEqual(es[-1].get("tipo"), "suave")
        self.assertEqual(es[-1].get("condicao"), "replans_exhausted")
        op = set(es[-1].get("opcoes") or [])
        self.assertTrue({"retomar", "emendar", "encerrar", "abortar"} <= op, "opções fechadas: %r" % op)
        self.assertFalse({"trocar-agente", "descartar-ramo"} & op, "escalada sem nó não oferece opção de nó: %r" % op)
        self.assertTrue(os.path.isfile(os.path.join(r, es[-1].get("pacote") or "-")), "pacote gravado em arquivo")
        rec = [g.get("guarda") for e in mevents(r, "escalate") for g in ((e.get("data") or {}).get("guardas_recusadas") or [])]
        self.assertIn("replans_left", rec)
        self.assertEqual(len(mevents(r, "replan_accept")), 1)

    def test_regress_onda_quebra_teste_verde_replano_com_no_fix_citando_o_teste(self):
        fx = self.make_repo(acs=ACS_2)
        r = fx.root
        nodes = [N("01", "dev-billing", ["src/billing/discount.py", "src/billing/total.py"], ["AC-1"],
                   verify="python3 -m unittest accept.test_ac_1"),
                 N("02", "dev-users", ["src/users/profile.py"], ["AC-2"])]
        drv = self.running(fx, nodes)
        drv.content = {"01": {"src/billing/discount.py": "OK = 1\n", "src/billing/total.py": "def total(items):\n    return 0\n"},
                       "03": {"src/billing/total.py": "def total(items):  # OK\n    return sum(items)\n"}}
        t = drv.run(stop_on=("REPLAN", "FIM", "ASK_HUMAN"))
        self.assertEqual(t.get("acao"), "REPLAN", "regressão vermelha → REPLANNING")
        self.assertIn("tests.test_billing", json.dumps(t, ensure_ascii=False), "o REPLAN cita o teste que quebrou")
        rec = [g.get("guarda") for e in mevents(r, "integrate_replan") for g in ((e.get("data") or {}).get("guardas_recusadas") or [])]
        self.assertIn("regression_green", rec)
        ref = t["evidencia"][0]["ref"]
        self.plan_refused(r, [N("03", "dev-billing", ["src/billing/total.py"], ["AC-1"])], "replan_cites_evidence",
                          motivo="corrigir total", evidencia=ref, msg="replano de regressão sem nó FIX citando o teste")
        self.submit_plan(r, [N("03", "dev-billing", ["src/billing/total.py"], ["AC-1"], tipo="FIX", teste="tests.test_billing")],
                         drv, motivo="regressão em tests.test_billing", evidencia=ref)
        drv.run()
        self.assertEqual(self.status(r).get("estado"), "DONE")


# ====================================================================== AUTO-ESC-*, AUTO-HACK, escalada manual
class TestEscalada(Base):
    def _ate_aguardar(self):
        fx = self.make_repo(acs=ACS_FROZEN)
        r = fx.root
        drv = self.running(fx, NODES_FROZEN)
        st = self.status(r)
        self.assertEqual(st.get("estado"), "RUNNING", "escalada LOCAL não para o mandato")
        self.assertEqual(set(st.get("congelados") or []), {"01", "03"}, "congela o nó e os descendentes")
        es = self.esc_open(st)
        self.assertTrue(es and es[0].get("tipo") == "dura_local" and es[0].get("condicao") == "frozen_write"
                        and "01" in (es[0].get("nos") or []), "pacote dura_local/frozen_write: %r" % es)
        t = drv.run()
        self.assertEqual(t.get("acao"), "ASK_HUMAN")
        self.assertEqual(self.node(self.status(r), "02").get("estado"), "ACCEPTED", "ramo independente seguiu até ACCEPTED")
        self.assertFalse({"01", "03"} & set(drv.dispatched_nos()), "ramo congelado nunca despachado")
        self.assertNotIn("AWAITING_HUMAN", [x.get("estado") for x in drv.ticks[:-1]],
                         "AWAITING_HUMAN só quando não sobra nó executável")
        return fx, drv

    def test_esc_local_congela_o_ramo_e_o_resto_segue(self):
        fx, drv = self._ate_aguardar()
        r = fx.root
        self.assertEqual(self.status(r).get("estado"), "AWAITING_HUMAN")
        self.assertFalse(self.stop_blocks(r)[0], "Stop deixa parar em AWAITING_HUMAN")
        for _ in range(2):
            t = self.tick(r)
            self.assertEqual((t.get("estado"), t.get("acao")), ("AWAITING_HUMAN", "ASK_HUMAN"), "o piloto não resolve sozinho")
        self.assertFalse([e for e in mevents(r) if e.get("type", "").startswith("mandato.resolve")])

    def test_esc_cite_brief_que_so_cita_invariante_nao_escala(self):
        fx = self.make_repo(acs=ACS_2)
        drv = self.running(fx, NODES_2)
        st = self.status(fx.root)
        self.assertEqual(self.esc_open(st), [], "citar invariante (rule.billing.cents) não escala")
        self.assertEqual(st.get("congelados") or [], [])
        self.assertEqual(drv.step().get("acao"), "DISPATCH")
        drv.run()
        self.assertEqual(self.status(fx.root).get("estado"), "DONE")
        self.assertFalse(mevents(fx.root, "escalate"))

    def _decision_in(self, root, name, decision):
        evs = mevents(root, name)
        self.assertTrue(evs, "evento mandato.%s gravado" % name)
        self.assertIn(decision, json.dumps(evs[-1], ensure_ascii=False), "decisão humana gravada no evento")
        self.assertEqual((evs[-1].get("data") or {}).get("de"), "AWAITING_HUMAN")

    def test_esc_resolve_retomar_com_recusas_de_portao_humano(self):
        fx, drv = self._ate_aguardar()
        r = fx.root
        self.no_auto(r, "resolve", "--choice", "retomar", "--decision", "x", "--by", "orchestrator", guard="by_human")
        self.human_no(r, "resolve", "--choice", "inventada", "--decision", "x", guard="choice_in_package")
        self.human_no(r, "resolve", "--choice", "retomar", guard="decision_present")
        self.human_no(r, "resolve", "--choice", "trocar-agente", "--agent", "qa", "--decision", "x", guard="new_agent_valid")
        self.assertEqual(self.status(r).get("estado"), "AWAITING_HUMAN", "recusas não destravam")
        dec = "DECISAO-RETOMAR pode escrever em frozen"
        self.human(r, "resolve", "--choice", "retomar", "--decision", dec)
        self._decision_in(r, "resolve_resume", dec)
        self.assertIn(self.status(r).get("estado"), ("RUNNING", "INTEGRATING"), "volta ao estado de onde escalou")
        drv.run()
        self.assertIn("01", drv.dispatched_nos())
        self.assertEqual(self.status(r).get("estado"), "DONE")
        self.assertTrue(files_with_text(r, "state", "DECISAO-RETOMAR") + files_with_text(r, "archive", "DECISAO-RETOMAR"),
                        "a decisão humana entra no brief da task retomada")

    def test_esc_resolve_trocar_agente(self):
        fx, drv = self._ate_aguardar()
        dec = "DECISAO-TROCA dev-users assume"
        self.human(fx.root, "resolve", "--choice", "trocar-agente", "--agent", "dev-users", "--decision", dec)
        self._decision_in(fx.root, "resolve_reroute", dec)
        drv.run()
        self.assertEqual([a for _, no, a in drv.dispatches if no == "01"][:1], ["dev-users"])
        self.assertEqual(self.status(fx.root).get("estado"), "DONE")

    def test_esc_resolve_emendar_volta_a_proposta_com_assinatura_encadeada(self):
        fx, drv = self._ate_aguardar()
        r = fx.root
        dec = "DECISAO-EMENDA libera frozen na spec"
        self.human(r, "resolve", "--choice", "emendar", "--decision", dec)
        self._decision_in(r, "amend", dec)
        self.assertEqual(self.status(r).get("estado"), "PROPOSED")
        sig = (mevents(r, "approve")[-1].get("data") or {}).get("assinatura")
        self.assertEqual((mevents(r, "amend")[-1].get("data") or {}).get("assinatura_anterior"), sig)
        self.approve(fx)

    def test_esc_resolve_descartar_ramo_entrega_parcial(self):
        fx, drv = self._ate_aguardar()
        r = fx.root
        dec = "DECISAO-DESCARTA ramo frozen"
        self.human(r, "resolve", "--choice", "descartar-ramo", "--decision", dec)
        self._decision_in(r, "resolve_drop", dec)
        t = drv.run()
        st = self.status(r)
        self.assertEqual(st.get("estado"), "HANDED_BACK", "descartar-ramo → entrega PARCIAL honesta: %r" % t)
        for no in ("01", "03"):
            self.assertEqual(self.node(st, no).get("estado"), "DROPPED")
        rep = self.report(r)
        self.assertEqual(rep.get("resultado"), "HANDED_BACK")
        self.assertIn("AC-1", rep.get("criterios_orfaos") or [])

    def test_esc_resolve_encerrar_devolve_abertos_ao_backlog(self):
        fx, drv = self._ate_aguardar()
        r = fx.root
        dec = "DECISAO-ENCERRA por ora"
        self.human(r, "resolve", "--choice", "encerrar", "--decision", dec)
        self._decision_in(r, "wrap_up", dec)
        drv.run()
        self.assertEqual(self.status(r).get("estado"), "HANDED_BACK")
        for title in ("N01", "N03"):
            got = files_with_text(r, "backlog", title)
            self.assertTrue(got, "nó aberto %s devolvido ao backlog/" % title)
            self.assertTrue(any(has_reason(p) for p in got), "devolvido com motivo")
        self.assertFalse(self.stop_blocks(r)[0], "terminal: Stop deixa parar")

    def test_esc_resolve_abortar(self):
        fx, drv = self._ate_aguardar()
        r = fx.root
        dec = "DECISAO-ABORTA"
        self.human(r, "resolve", "--choice", "abortar", "--decision", dec)
        self._decision_in(r, "abort", dec)
        self.assertEqual(self.status(r).get("estado"), "ABORTED")
        rep = self.report(r)
        self.assertEqual(rep.get("resultado"), "ABORTED")
        self.assertIn("git", str(rep.get("restaurar") or ""), "relatório dá o comando para voltar ao ponto seguro")
        self.assertEqual(self.tick(r).get("acao"), "FIM")

    def _hack_setup(self):
        fx = self.make_repo(acs=ACS_2)
        drv = self.running(fx, NODES_2)
        drv.run(until=lambda d, t: len(d.dispatches) >= 1)
        hs = {p: sha_file(os.path.join(fx.root, p)) for p in ("accept/test_ac_1.py", "spec/feature.md")}
        return fx, drv, hs

    def _assert_hard_global(self, fx, drv):
        r = fx.root
        t = self.tick(r)
        self.assertEqual((t.get("estado"), t.get("acao")), ("AWAITING_HUMAN", "ASK_HUMAN"), "escalada dura GLOBAL: %r" % t)
        es = self.esc_open(self.status(r))
        self.assertTrue(es and es[-1].get("tipo") == "dura_global" and es[-1].get("condicao") == "acceptance_changed",
                        "pacote dura_global/acceptance_changed: %r" % es)
        for task in list(drv.inflight):
            drv.deliver(task)
        self.assertEqual(self.tick(r).get("acao"), "ASK_HUMAN", "todo despacho congelado")
        st = self.status(r)
        accepted = [n for n in (st.get("plano") or {}).get("nos") or [] if n.get("estado") == "ACCEPTED"]
        self.assertFalse(accepted, "em voo termina e é verificado, não aceito, sob escalada global: %r" % accepted)

    def test_hack_tentativa_bloqueada_pelo_guard_escala_global(self):
        fx, drv, hs = self._hack_setup()
        r = fx.root
        sub = {"agent_id": "ag-1", "agent_type": drv.dispatches[0][2]}
        for relp in ("accept/test_ac_1.py", "spec/feature.md"):
            p = {"tool_name": "Write", "tool_use_id": "tu-w", "tool_input": {"file_path": os.path.join(r, relp)}, "cwd": r}
            p.update(sub)
            self.assertEqual(self.hook(r, "pre-write", p)[0], 2, "subagente editando %s é bloqueado" % relp)
        p = {"tool_name": "Bash", "tool_use_id": "tu-b", "tool_input": {"command": "echo x > accept/test_ac_1.py"}, "cwd": r}
        p.update(sub)
        self.assertEqual(self.hook(r, "pre-bash", p)[0], 2)
        for relp, h in hs.items():
            self.assertEqual(sha_file(os.path.join(r, relp)), h, "%s inalterado (hash)" % relp)
        self._assert_hard_global(fx, drv)
        esc = mevents(r, "escalate")
        self.assertEqual((esc[-1].get("data") or {}).get("de"), "RUNNING")

    def test_hack_aceite_alterado_por_fora_detectado_pelo_hash(self):
        fx, drv, hs = self._hack_setup()
        write(fx.root, "accept/test_ac_1.py", "import unittest\n\n\nclass A(unittest.TestCase):\n    def test_ac(self):\n"
                                              "        self.assertTrue(True)\n")
        self._assert_hard_global(fx, drv)
        self.assertNotIn("retomar", self.esc_open(self.status(fx.root))[-1].get("opcoes") or [],
                         "aceite adulterado: retomar não é opção (só emendar/encerrar/abortar)")
        self.human_no(fx.root, "resolve", "--choice", "retomar", "--decision", "segue", guard="choice_in_package")

    def test_escalada_manual_em_planning_e_replanning_e_retomada_ao_estado_de_origem(self):
        fx = self.make_repo(acs=ACS_2)
        r = fx.root
        self.propose(fx, nos=2)
        self.approve(fx)
        self.assertEqual(self.tick(r).get("acao"), "PLAN")
        self.no_auto(r, "escalate", "--condicao", "inventada", "--evidencia", "spec/feature.md:1", guard="escalation_condition")
        self.ok_auto(r, "escalate", "--condicao", "material_ambiguity", "--evidencia", "spec/feature.md:1")
        st = self.status(r)
        self.assertEqual(st.get("estado"), "AWAITING_HUMAN")
        self.assertEqual(self.esc_open(st)[-1].get("tipo"), "suave")
        self.assertEqual((mevents(r, "escalate")[-1].get("data") or {}).get("de"), "PLANNING")
        self.human_no(r, "resolve", "--choice", "trocar-agente", "--agent", "dev-users", "--decision", "x",
                      guard="choice_in_package", msg="escalada sem nó não oferece trocar-agente")
        self.human_no(r, "resolve", "--choice", "descartar-ramo", "--decision", "x", guard="choice_in_package")
        self.human(r, "resolve", "--choice", "retomar", "--decision", "a spec vale como está")
        self.assertEqual(self.status(r).get("estado"), "PLANNING", "retomar volta a PLANNING")
        fx2, drv, t = TestReplano._ate_replanning(self)
        self.ok_auto(fx2.root, "escalate", "--condicao", "material_ambiguity", "--evidencia", "spec/feature.md:1")
        self.assertEqual((mevents(fx2.root, "escalate")[-1].get("data") or {}).get("de"), "REPLANNING")
        self.human(fx2.root, "resolve", "--choice", "retomar", "--decision", "segue o replano")
        self.assertEqual(self.status(fx2.root).get("estado"), "REPLANNING")


# ====================================================================== AUTO-BUDGET-*, AUTO-USD, AUTO-NOPROG
class TestOrcamento(Base):
    def test_budget_soft_80_por_cento_encerra_com_entrega_parcial(self):
        acs = [("AC-%d" % i, p) for i, p in enumerate(["src/billing/a.py", "src/users/b.py", "src/billing/c.py",
                                                        "src/users/d.py", "src/billing/e.py"], 1)]
        fx = self.make_repo(acs=acs)
        r = fx.root
        ags = ["dev-billing", "dev-users", "dev-billing", "dev-users", "dev-billing"]
        nodes = [N("%02d" % i, ags[i - 1], [acs[i - 1][1]], [acs[i - 1][0]], deps=(["%02d" % (i - 1)] if i > 1 else []))
                 for i in range(1, 6)]
        drv = self.running(fx, nodes, orc="despachos=5,tentativas=20,replanos=3,minutos=600", nos=5)
        seen = {"w": False}

        def after(d, t):
            if t.get("estado") == "WRAPPING_UP" and not seen["w"]:
                seen["w"] = True
                task5 = self.node(self.status(r), "05").get("task")
                self.assertTrue(task5, "status.plano.nos[].task existe desde o plan_accept")
                code, out, err = self.cs(r, "dispatch", task5, "--manual", "--model", "sonnet")
                self.assertEqual(code, 1, "WRAPPING_UP: nenhum despacho novo (%s)" % (out + err)[-400:])
        drv.after_step = after
        drv.run()
        self.assertTrue(seen["w"], "passou por WRAPPING_UP")
        self.assertEqual(drv.dispatched_nos(), ["01", "02", "03", "04"], "o 4º despacho atinge 80%: nada depois")
        st = self.status(r)
        self.assertEqual(st.get("estado"), "HANDED_BACK")
        self.assertEqual(self.node(st, "04").get("estado"), "ACCEPTED", "o que estava em voo fecha")
        wu = mevents(r, "wrap_up")
        self.assertEqual((wu[-1].get("data") or {}).get("gatilho"), "budget_soft")
        got = files_with_text(r, "backlog", "N05")
        self.assertTrue(got and any(has_reason(p) for p in got), "nó aberto devolvido ao backlog/ com motivo")

    def test_budget_time_conta_so_minutos_ativos(self):
        fx = self.make_repo(acs=ACS_2)
        r = fx.root
        t0 = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(minutes=1)
        self.clock = t0
        self.propose(fx, nos=2)
        self.clock = t0 + timedelta(minutes=1)
        self.approve(fx, "despachos=20,tentativas=40,replanos=3,minutos=60")
        self.clock = t0 + timedelta(minutes=2)
        self.assertEqual(self.tick(r).get("acao"), "PLAN")
        self.clock = t0 + timedelta(minutes=3)
        self.submit_plan(r, NODES_2)
        self.clock = t0 + timedelta(minutes=5)
        self.assertEqual(self.tick(r).get("acao"), "DISPATCH")
        self.clock = t0 + timedelta(minutes=10)
        self.ok_auto(r, "pause", "--motivo", "fim da janela")
        self.assertEqual(self.status(r).get("estado"), "PAUSED")
        self.clock = t0 + timedelta(hours=8, minutes=10)
        self.session_start(r, "startup")
        self.clock = t0 + timedelta(hours=8, minutes=15)
        t = self.tick(r)
        st = self.status(r)
        self.assertEqual(st.get("estado"), "RUNNING", "8 h de pausa não estouram o limite de 60 min: %r" % t)
        self.assertLessEqual(float(st["orcamento"]["minutos"]["usado"]), 30, "minutos ATIVOS, não relógio de parede")
        self.clock = t0 + timedelta(hours=16, minutes=15)
        self.tick(r)
        st = self.status(r)
        self.assertEqual(st.get("estado"), "RUNNING", "lacuna longa sem tick também não conta")
        self.assertLessEqual(float(st["orcamento"]["minutos"]["usado"]), 40)

    def test_usd_autodeclarado_nao_e_controle(self):
        fx = self.make_repo(acs=ACS_2)
        r = fx.root
        self.running(fx, NODES_2, orc="despachos=20,tentativas=40,replanos=3,minutos=600,usd=10")
        before = self.status(r)["orcamento"]["usd"]
        code, out, err = self.auto(r, "spend", "--usd", "99999")
        self.assertIn(code, (0, 1), "spend: recusado (1) ou marcado autodeclarado (0): %s%s" % (out, err))
        st = self.status(r)
        usd = st["orcamento"]["usd"]
        self.assertEqual(float(usd.get("medido") or 0), float(before.get("medido") or 0), "custo medido não muda por declaração")
        if code == 0:
            self.assertGreaterEqual(float(usd.get("autodeclarado") or 0), 99999, "registrado como autodeclarado")
        self.assertEqual(st.get("estado"), "RUNNING", "valor autodeclarado não dispara parada nem escalada")

    def test_noprog_replaneja_uma_vez_e_encerra_sem_escalar(self):
        acs = [("AC-1", "src/billing/a.py"), ("AC-2", "src/users/b.py")]
        fx = self.make_repo(acs=acs)
        r = fx.root
        nodes = [N("01", "dev-billing", ["src/billing/a.py"], ["AC-1"]), N("02", "dev-users", ["src/users/b.py"], ["AC-2"])]
        drv = self.running(fx, nodes, orc="despachos=40,tentativas=80,replanos=5,minutos=600")
        drv.default_mode = "abstain"
        seq = {"n": 2}

        def on_replan(d, t):
            ev = t.get("evidencia") or []
            self.assertTrue(ev and ev[0].get("ref"), "REPLAN com evidência: %r" % t)
            a, b = "%02d" % (seq["n"] + 1), "%02d" % (seq["n"] + 2)
            seq["n"] += 2
            self.submit_plan(r, [N(a, "dev-billing", ["src/billing/a%s.py" % a], ["AC-1"]),
                                 N(b, "dev-users", ["src/users/b%s.py" % b], ["AC-2"])], d,
                             motivo="abstenção: redistribuir", evidencia=ev[0]["ref"])
        drv.on_replan = on_replan
        drv.run()
        st = self.status(r)
        self.assertEqual(st.get("estado"), "HANDED_BACK", "sem progresso → WRAPPING_UP → HANDED_BACK")
        self.assertEqual((mevents(r, "wrap_up")[-1].get("data") or {}).get("gatilho"), "no_progress")
        self.assertFalse(mevents(r, "escalate"), "sem progresso não escala")
        n = len(mevents(r, "replan_accept"))
        self.assertTrue(1 <= n < 5, "replanejou (≥1) e parou antes do teto de replanos (%d)" % n)
        self.assertFalse([x for x in (st.get("plano") or {}).get("nos") or [] if x.get("estado") == "DROPPED"],
                         "ABSTAINED espera decisão humana: o motor não descarta por conta própria")


# ====================================================================== AUTO-RESUME / AUTO-COMPACT / AUTO-STOPHOOK / pausas
class TestJanelas(Base):
    def _janela_morta(self, did_work):
        fx = self.make_repo(acs=ACS_2)
        r = fx.root
        drv = self.running(fx, NODES_2)
        drv.run(until=lambda d, t: len(d.dispatches) >= 1)
        task, no, agent = drv.dispatches[0]
        if did_work:
            for p, txt in drv.files_for(no, "ok", drv.inflight[task]["paths"]).items():
                write(r, p, txt)
        self.ok_auto(r, "pause", "--motivo", "fim da janela")
        self.assertEqual(self.status(r).get("estado"), "PAUSED")
        drv.inflight.clear()
        out = self.session_start(r, "startup")
        self.assertIn(OBJ, out, "SessionStart injeta o objetivo")
        self.assertIn("cs-auto", out, "SessionStart injeta o próximo comando")
        self.assertEqual(self.status(r).get("estado"), "RUNNING", "SessionStart → resume")
        code, brief, err = self.auto(r, "status", "--brief")
        self.assertEqual(code, 0, err)
        lines = [l for l in brief.splitlines() if l.strip()]
        self.assertLessEqual(len(lines), 20, "status --brief cabe em uma tela")
        self.assertIn(OBJ, brief)
        self.assertTrue([l for l in lines if "cs-auto" in l], "status --brief traz o comando do 1º passo")
        drv.run()
        self.assertEqual(self.status(r).get("estado"), "DONE")
        return drv, task

    def test_resume_orfa_sem_diff_volta_para_a_fila(self):
        drv, task = self._janela_morta(False)
        self.assertEqual(len([x for x in drv.dispatches if x[0] == task]), 2, "órfã sem diff → requeue (novo despacho)")

    def test_resume_orfa_com_diff_vai_para_verify(self):
        drv, task = self._janela_morta(True)
        self.assertEqual(len([x for x in drv.dispatches if x[0] == task]), 1, "órfã com diff → verify, sem redespacho")

    def test_compact_pausa_com_checkpoint_e_retoma_no_mesmo_passo(self):
        fx = self.make_repo(acs=ACS_2)
        r = fx.root
        self.running(fx, NODES_2)
        a, a2 = self.tick(r), self.tick(r)
        self.assertEqual((a.get("acao"), a.get("alvo")), (a2.get("acao"), a2.get("alvo")), "tick idempotente")
        code, txt, err = self.auto(r, "tick")
        self.assertEqual(code, 0, err)
        self.assertLessEqual(len(txt.splitlines()), 30, "tick humano ≤ 30 linhas")
        self.assertIn(OBJ, txt)
        sess = len(glob.glob(sd(r, "state", "sessoes", "*.json5")))
        self.pre_compact(r)
        self.assertEqual(self.status(r).get("estado"), "PAUSED")
        self.assertEqual((mevents(r, "pause")[-1].get("data") or {}).get("de"), "RUNNING")
        self.assertGreater(len(glob.glob(sd(r, "state", "sessoes", "*.json5"))), sess, "checkpoint de sessão gravado")
        self.session_start(r, "compact")
        self.assertEqual(self.status(r).get("estado"), "RUNNING")
        b = self.tick(r)
        self.assertEqual((b.get("acao"), b.get("alvo")), (a.get("acao"), a.get("alvo")), "mesmo próximo passo")

    def test_stophook_bloqueia_com_a_acao_e_tem_anti_loop(self):
        fx = self.make_repo(acs=ACS_2)
        r = fx.root
        self.running(fx, NODES_2)
        t = self.tick(r)
        blk, why = self.stop_blocks(r)
        self.assertTrue(blk, "RUNNING com nó pronto: Stop bloqueia")
        self.assertIn(t.get("acao"), why)
        self.assertIn(str(t.get("alvo")), why, "reason = ação do tick + alvo/comando")
        for _ in range(4):
            if self.status(r).get("estado") == "PAUSED":
                break
            self.stop_blocks(r)
        self.assertEqual(self.status(r).get("estado"), "PAUSED", "≥3 bloqueios do Stop sem transição → pause com diagnóstico")
        self.assertFalse(self.stop_blocks(r)[0], "PAUSED: Stop deixa parar")
        self.assertFalse(mevents(r, "escalate"), "anti-loop pausa, não escala")
        self.session_start(r)
        self.assertEqual(self.status(r).get("estado"), "RUNNING")
        self.assertTrue(self.stop_blocks(r)[0], "retomado, o Stop volta a conduzir")

    def test_pausa_e_retomada_em_planning_e_integrating(self):
        fx = self.make_repo(acs=ACS_2)
        r = fx.root
        self.propose(fx, nos=2)
        self.approve(fx)
        self.assertEqual(self.tick(r).get("acao"), "PLAN")
        self.ok_auto(r, "pause")
        self.assertEqual(self.status(r).get("estado"), "PAUSED")
        self.assertFalse(self.stop_blocks(r)[0])
        self.ok_auto(r, "resume")
        self.assertEqual(self.status(r).get("estado"), "PLANNING", "resume volta ao estado anterior")
        drv = Driver(self, r, NODES_2)
        drv.run(stop_on=("FINAL_REVIEW", "FIM", "ASK_HUMAN"))
        self.assertEqual(drv.ticks[-1].get("acao"), "FINAL_REVIEW")
        self.assertEqual(self.status(r).get("estado"), "INTEGRATING")
        self.ok_auto(r, "pause")
        self.assertEqual((mevents(r, "pause")[-1].get("data") or {}).get("de"), "INTEGRATING")
        self.ok_auto(r, "resume")
        self.assertEqual(self.status(r).get("estado"), "INTEGRATING")
        drv.run()
        self.assertEqual(self.status(r).get("estado"), "DONE")

    def test_stop_humano_em_planning_replanning_e_pausado(self):
        fx = self.make_repo(acs=ACS_2)
        r = fx.root
        self.propose(fx, nos=2)
        self.approve(fx)
        self.tick(r)
        self.no_auto(r, "stop", "--by", "orchestrator", "--reason", "x", msg="stop não humano")
        self.human(r, "stop", "--reason", "humano parou no planejamento")
        self.assertEqual((mevents(r, "wrap_up")[-1].get("data") or {}).get("de"), "PLANNING")
        Driver(self, r).run()
        self.assertEqual(self.status(r).get("estado"), "HANDED_BACK")
        fx2, drv, t = TestReplano._ate_replanning(self)
        r2 = fx2.root
        self.ok_auto(r2, "pause")
        self.assertEqual((mevents(r2, "pause")[-1].get("data") or {}).get("de"), "REPLANNING")
        self.ok_auto(r2, "resume")
        self.assertEqual(self.status(r2).get("estado"), "REPLANNING")
        self.human(r2, "stop", "--reason", "humano parou no replano")
        self.assertEqual((mevents(r2, "wrap_up")[-1].get("data") or {}).get("de"), "REPLANNING")
        drv.on_replan = None
        drv.run()
        self.assertEqual(self.status(r2).get("estado"), "HANDED_BACK")
        fx3 = self.make_repo(acs=ACS_2)
        r3 = fx3.root
        self.running(fx3, NODES_2)
        self.ok_auto(r3, "pause")
        self.human(r3, "stop", "--reason", "humano parou na pausa")
        self.assertEqual((mevents(r3, "wrap_up")[-1].get("data") or {}).get("de"), "PAUSED")
        self.assertEqual((mevents(r3, "wrap_up")[-1].get("data") or {}).get("gatilho"), "stop_humano")
        Driver(self, r3).run()
        self.assertEqual(self.status(r3).get("estado"), "HANDED_BACK")


# ====================================================================== AUTO-SPRINT / AUTO-LANE / AUTO-RISK
class TestSprintEFaixas(Base):
    def test_sprint_uma_feature_ativa_por_vez(self):
        fx = self.make_repo(acs=ACS_2, features=[("Desconto", ["AC-1"]), ("Perfil", ["AC-2"])], start_feature=False)
        r = fx.root
        f1, f2 = fx.feas
        self.ok_auto(r, "propose", "--sprint", fx.spr, "--spec", "spec/feature.md", "--objetivo", OBJ, "--nos", "4",
                     "--regressao", REGRESSAO)
        self.approve(fx)
        plans = {f1: [N("01", "dev-billing", ["src/billing/discount.py"], ["AC-1"]),
                      N("02", "qa", ["tests/test_desc.py"], ["AC-1"], deps=["01"])],
                 f2: [N("03", "dev-users", ["src/users/profile.py"], ["AC-1"]),
                      N("04", "qa", ["tests/test_perfil.py"], ["AC-1"], deps=["03"])]}
        done = []

        def on_plan(d, t):
            f = t.get("feature")
            self.assertIn(f, plans, "PLAN diz a feature ativa: %r" % t)
            self.assertNotIn(f, done, "cada feature planeja uma vez")
            done.append(f)
            self.submit_plan(r, plans[f], d)
        seen = {"f2_first": None}

        def after(d, t):
            on = [f for f in (f1, f2) if folder_of(r, f, "state")]
            self.assertLessEqual(len(on), 1, "uma feature ativa por vez em state/: %r" % on)
            if f2 in on and seen["f2_first"] is None:
                seen["f2_first"] = True
                self.assertFalse(folder_of(r, f1, "state"), "a 1ª fecha antes da 2ª começar")
        drv = Driver(self, r, on_plan=on_plan)
        drv.after_step = after
        drv.run(max_steps=220)
        self.assertEqual(done, [f1, f2])
        alvos = [task for task, _, _ in drv.dispatches]
        i2 = [i for i, a in enumerate(alvos) if str(a).startswith(f2)]
        i1 = [i for i, a in enumerate(alvos) if str(a).startswith(f1)]
        self.assertTrue(i1 and i2 and max(i1) < min(i2), "tasks paralelas só dentro da feature ativa: %r" % alvos)
        self.assertEqual(self.status(r).get("estado"), "DONE")
        self.assertTrue(mevents(r, "next_feature"))
        self.assertTrue(folder_of(r, f1, "archive"), "feature fechada pelo DoD vai para archive/")
        self.validate(r, msg="SPRINT")

    def test_lane_consulta_contada_e_avulsa_que_colide_recusada(self):
        fx = self.make_repo(acs=ACS_2)
        r = fx.root
        self.running(fx, NODES_2)
        u0 = int(self.status(r)["orcamento"]["despachos"]["usado"])
        out = self.ok_cs(r, "ask", "dev-billing", "onde o total é calculado?")
        m = re.search(r"\(([^:()\s]+): consulta", out)
        self.assertTrue(m, "ask imprime o id da consulta: %r" % out)
        p = {"tool_name": "Agent", "tool_use_id": "tu-ag", "tool_input": {"description": m.group(1), "prompt": "responda",
                                                                            "subagent_type": "dev-billing", "model": "haiku"}}
        code, o, e = self.hook(r, "pre-agent", p)
        self.assertEqual(code, 0, "consulta só-leitura permitida durante o mandato: %s%s" % (o, e))
        self.assertEqual(int(self.status(r)["orcamento"]["despachos"]["usado"]), u0 + 1, "consulta conta no orçamento")

        def avulsa(path, title):
            return self.cs(r, "new", "task", "--tipo", "US", "--agent", "dev-billing", "--title", title, "--avulsa",
                           "--allowed-path", path, "--verify-cmd", REGRESSAO, "--como", "c", "--quero", "q", "--para", "p",
                           "--criterio", "AC-1|Dado o pedido Quando somo Então o total confere|tests.test_billing")
        code, out, err = avulsa("src/billing/discount.py", "Hotfix desconto")
        if code == 0:
            tid = CREATED_RE.findall(out)[0][0]
            code, out, err = self.cs(r, "start", tid)
        self.assertEqual(code, 1, "avulsa que colide com o DAG ativo é recusada: %s%s" % (out, err))
        self.assertTrue("src/billing/discount.py" in out + err or MAN_RE.search(out + err), "recusa cita o conflito")
        code, out, err = avulsa("src/billing/outro.py", "Outro ajuste")
        self.assertEqual(code, 0, out + err)
        self.ok_cs(r, "start", CREATED_RE.findall(out)[0][0], msg="avulsa sem colisão segue")

    def test_risk_portoes_param_antes_do_dispatch_e_o_resto_roda(self):
        acs = [("AC-1", "src/billing/pagamento/core.py"), ("AC-2", "src/users/profile.py")]
        fx = self.make_repo(acs=acs)
        r = fx.root
        args = ["propose", "--feature", fx.fea, "--spec", "spec/feature.md", "--objetivo", OBJ, "--nos", "2",
                "--regressao", REGRESSAO, "--classe", "risco", "--criterio", crit(*acs[0]), "--criterio", crit(*acs[1])]
        self.no_auto(r, *args, guard="class_allowed", msg="risco sem portões declarados")
        nodes = [N("01", "dev-billing", ["src/billing/pagamento/core.py"], ["AC-1"]),
                 N("02", "dev-users", ["src/users/profile.py"], ["AC-2"])]
        drv = self.running(fx, nodes, classe="risco", portoes=["src/billing/pagamento/**"])
        task1 = self.node(self.status(r), "01").get("task")
        self.assertTrue(task1)
        code, out, err = self.cs(r, "dispatch", task1, "--manual", "--model", "sonnet")
        self.assertEqual(code, 1, "nó de risco não despacha antes do portão humano: %s%s" % (out, err))
        t = drv.run()
        self.assertEqual(t.get("acao"), "ASK_HUMAN")
        st = self.status(r)
        self.assertEqual(self.node(st, "02").get("estado"), "ACCEPTED", "os demais rodam")
        self.assertNotIn("01", drv.dispatched_nos())
        self.assertEqual(self.esc_open(st)[-1].get("condicao"), "risk_gate")
        self.human(r, "resolve", "--choice", "retomar", "--decision", "portão de risco aprovado pelo humano")
        drv.run()
        self.assertIn("01", drv.dispatched_nos())
        self.assertEqual(self.status(r).get("estado"), "DONE")


# ====================================================================== AUTO-TAMPER / AUTO-E2E
class TestIntegridade(Base):
    def test_tamper_mandato_e_plano_editados_a_mao(self):
        fx = self.make_repo(acs=ACS_2)
        r = fx.root
        self.running(fx, NODES_2)
        self.validate(r, msg="antes da adulteração")
        pasta = os.path.join(r, self.status(r).get("pasta") or "")
        for name in ("mandato.json5", "plano.v1.json5"):
            p = os.path.join(pasta, name)
            self.assertTrue(os.path.isfile(p), "%s existe na pasta do mandato" % name)
            pp = {"tool_name": "Write", "tool_use_id": "tu-w", "tool_input": {"file_path": p}, "cwd": r}
            self.assertEqual(self.hook(r, "pre-write", pp)[0], 2, "o modelo não escreve %s" % name)
            with open(p, "rb") as f:
                orig = f.read()
            d = json5io.read(p)
            d["adulterado"] = True
            write(r, rel(r, p), json.dumps(d))
            code, out, err = self.cs(r, "validate")
            self.assertEqual(code, 1, "validate acusa %s editado à mão" % name)
            self.assertIn(name, out + err)
            with open(p, "wb") as f:
                f.write(orig)
            self.validate(r, msg="restaurado %s" % name)

    def test_e2e_propose_ao_done_com_escalada_e_janela(self):
        acs = [("AC-1", "src/billing/discount.py"), ("AC-2", "src/shared/frozen/x.py"), ("AC-3", "tests/test_fluxo.py")]
        fx = self.make_repo(acs=acs)
        r = fx.root
        nodes = [N("01", "dev-billing", ["src/billing/discount.py"], ["AC-1"]),
                 N("02", "dev-users", ["src/shared/frozen/x.py"], ["AC-2"]),
                 N("03", "qa", ["tests/test_fluxo.py"], ["AC-3"], deps=["01"])]
        drv = self.running(fx, nodes)
        drv.run(until=lambda d, t: len(d.dispatches) >= 1)
        self.pre_compact(r)
        self.assertEqual(self.status(r).get("estado"), "PAUSED")
        self.session_start(r, "compact")
        self.assertEqual(self.status(r).get("estado"), "RUNNING")
        t = drv.run()
        self.assertEqual(t.get("acao"), "ASK_HUMAN")
        self.human(r, "resolve", "--choice", "retomar", "--decision", "pode escrever em frozen nesta frente")
        drv.run()
        self.assertEqual(self.status(r).get("estado"), "DONE")
        self.assertEqual(self.human_calls, 2, "toques humanos: approve + 1 resolve")
        self.validate(r, strict=True, msg="E2E")
        rep = self.report(r)
        self.assertEqual(rep.get("resultado"), "DONE")
        vs = rep.get("verificacoes") or []
        self.assertTrue(vs, "relatório lista as verificações previstas")
        for v in vs:
            self.assertTrue(v.get("executada") or v.get("motivo"), "nada pulado calado: %r" % v)
            if v.get("executada") and v.get("output_sha256"):
                self.assertRegex(str(v["output_sha256"]), HEX64)
        for c in rep.get("criterios") or []:
            self.assertTrue(c.get("verde"))
            self.assertRegex(str(c.get("output_sha256")), HEX64)


# ====================================================================== H-1: comando do motor via shell
class TestH1ComandoDoMotor(Base):
    """Defeito H-1 (0.7.0): engine.run_cmd só usa shell quando vê metacaractere; `PYTHONPATH=src python3 -m unittest`
    vira execve("PYTHONPATH=src") → 127 — e 127 parece "aceite vermelho". Exigido: todo verify-cmd/aceite/regressão
    roda via shell (/bin/sh -c) no cwd do alvo, com atribuição de variável, &&, aspas e pipes, e o exit REAL propagado."""
    CASES = [("PYTHONPATH=src python3 -m h1mod", 0), ("H1=1 python3 -m unittest -h", 0),
             ("PYTHONPATH=src python3 -c 'import h1mod'", 0), ("A=1 B=2 sh -c 'exit $((A+B))'", 3),
             ("PYTHONPATH=src python3 -c 'import sys; sys.exit(7)'", 7), ("true && exit 4", 4), ("false && true", 1),
             ('echo "a b" | grep -q "a b"', 0), ("printf x | grep -q y", 1), ("test -f src/h1mod.py", 0),
             ("comando-que-nao-existe-h1", 127)]

    def _root(self):
        root = os.path.realpath(tempfile.mkdtemp(prefix="cs-h1-"))
        self.roots.append(root)
        write(root, "src/h1mod.py", "OK = 1\n")
        return root

    def test_run_cmd_usa_shell_no_cwd_do_alvo_e_propaga_o_exit(self):
        code = ("import json, sys; sys.path[:0] = [%r, %r]; import engine; "
                "print(json.dumps([engine.run_cmd(sys.argv[1], c, 60)['exit_code'] for c in json.loads(sys.argv[2])]))"
                % (ENGINE, os.path.join(SCRIPTS, "memory")))
        root = self._root()
        p = subprocess.run([sys.executable, "-c", code, root, json.dumps([c for c, _ in self.CASES])], cwd=HERE,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self._env())
        self.assertEqual(p.returncode, 0, p.stderr.decode("utf-8", "replace")[-1500:])
        got = json.loads(p.stdout.decode("utf-8"))
        for (c, want), g in zip(self.CASES, got):
            self.assertEqual(g, want, "engine.run_cmd(%r) → exit %d (esperado %d: shell, cwd do alvo, exit real)" % (c, g, want))

    def test_verify_da_task_com_atribuicao_de_variavel_passa(self):
        fx = self.make_repo(acs=ACS_2)
        r = fx.root
        write(r, "src/h1mod.py", "OK = 1\n")
        write(r, "tests/test_h1.py", "import unittest\nimport h1mod\n\n\nclass H(unittest.TestCase):\n"
                                     "    def test_ok(self):\n        self.assertEqual(h1mod.OK, 1)\n")
        vc = "PYTHONPATH=src python3 -m unittest discover -s tests -t ."
        out = self.ok_cs(r, "new", "task", "--tipo", "US", "--agent", "dev-billing", "--title", "H1", "--feature", fx.fea,
                         "--allowed-path", "src/billing/discount.py", "--verify-cmd", vc, "--como", "c", "--quero", "q",
                         "--para", "p", "--criterio", "AC-1|Dado o pedido Quando somo Então o total confere|tests.test_billing")
        tid = CREATED_RE.findall(out)[0][0]
        self.ok_cs(r, "start", tid)
        self.ok_cs(r, "dispatch", tid, "--manual", "--model", "sonnet")
        write(r, "src/billing/discount.py", "OK = 1\n")
        self.ok_cs(r, "submit", tid, "--files-changed", "src/billing/discount.py", "--check", "unittest: OK", "--risk",
                   "nenhum", "--handoff-notes", "ok", actor="dev-billing")
        out = self.ok_cs(r, "verify", tid)
        self.assertIn("PASS", out, "verify-cmd com atribuição de variável roda via shell e passa: %s" % out[-600:])
        self.assertNotIn("127", out)

    def test_aceite_com_atribuicao_de_variavel_e_medido_de_verdade(self):
        fx = self.make_repo(acs=ACS_2, start_feature=False)
        r = fx.root
        write(r, "src/h1mod.py", "OK = 1\n")
        write(r, "accept/test_h1.py", "import unittest\nimport h1mod\n\n\nclass H(unittest.TestCase):\n"
                                      "    def test_ok(self):\n        self.assertEqual(h1mod.OK, 1)\n")
        out = self.ok_cs(r, "new", "feature", "--title", "H1 verde", "--sprint", fx.spr, "--aceite",
                         "PYTHONPATH=src python3 -m unittest accept.test_h1")
        fid = CREATED_RE.findall(out)[0][0]
        code, o, e = self.cs(r, "check", fid)
        self.assertEqual(code, 1, "aceite JÁ VERDE (via shell) tem de ser visto como verde — 127 não é 'vermelho': %s%s" % (o, e))
        self.assertIn("aceite", o + e)


# ====================================================================== portão humano: o mandato nunca o aprova
class TestPortaoHumano(Base):
    def test_mandato_nunca_aprova_portao_humano(self):
        fx = self.make_repo(acs=ACS_2)
        r = fx.root
        self.propose(fx, nos=2)
        for _ in range(2):
            t = self.tick(r)
            self.assertEqual((t.get("estado"), t.get("acao")), ("PROPOSED", "ASK_HUMAN"), "a aprovação é do humano: %r" % t)
        self.assertFalse(mevents(r, "approve"))
        cmds = ["cs-auto approve --by founder", "%s/bin/cs-auto resolve --choice retomar --by founder --decision x" % SD,
                "python3 %s approve --by founder" % AUTO_PY, "cs-auto amend --by founder --reason x",
                "cs-auto abort --by founder --reason x", "cs-auto stop --by founder --reason x"]
        for actor in ({}, {"agent_id": "ag-1", "agent_type": "dev-billing"}):
            for c in cmds:
                p = {"tool_name": "Bash", "tool_use_id": "tu-b", "tool_input": {"command": c}, "cwd": r}
                p.update(actor)
                code, out, err = self.hook(r, "pre-bash", p)
                self.assertEqual(code, 2, "ato HUMANO bloqueado para o %s: %s" % ("subagente" if actor else "principal", c))
        p = {"tool_name": "Bash", "tool_use_id": "tu-b", "tool_input": {"command": "cs-auto tick"}, "cwd": r}
        self.assertEqual(self.hook(r, "pre-bash", p)[0], 0, "o principal roda o piloto (cs-auto tick)")
        for who in ("orchestrator", "claude", "dev-billing", "reviewer"):
            self.no_auto(r, "approve", "--by", who, guard="by_human")
        self.assertEqual(self.status(r).get("estado"), "PROPOSED")
        self.assertFalse(mevents(r, "approve"), "nenhuma aprovação aconteceu")


if __name__ == "__main__":
    unittest.main()
