"""ORÁCULO campanha-iter10 — estado do harness como ÁRVORE DE PASTAS navegável.

Fonte: codebase-specialists/docs/ROADMAP-rodada-seguinte.md (§1–§10) + docs/PONTOS-DO-FOUNDER.md (B2–B9, D-0-12).
Contrato e interfaces FIXADAS: ESPEC.md (mesma pasta). Quem implementa NÃO edita este arquivo.

Tudo pelo comportamento OBSERVÁVEL, sem mock do motor:
  * CLI real `cs-state`  = scripts/harness/engine/state.py   (subprocesso, --root <alvo>)
  * CLI real `cs-session`= scripts/harness/engine/session.py (subprocesso, --root <alvo>)
  * guard real           = scripts/harness/engine/guard.py   (payloads de hook, CLAUDE_PROJECT_DIR=<alvo>)
  * disco: <alvo>/<STATE_DIR>/{backlog,state,archive}/..., <STATE_DIR>/events.jsonl, <STATE_DIR>/INDEX.md

Nome da pasta de estado: resiliente à campanha iter9 (rename .specialists → .swarm):
`from cslib.paths import STATE_DIR` e, se não existir, ".swarm". O nome antigo só aparece para LER o alvo congelado
da iteration-4 (dado de entrada da migração), nunca como pasta de estado do alvo de teste.

Skill alvo: $CS_SKILL_DIR, senão ~/.claude/skills/codebase-specialists. Python 3.9+, unittest puro, temporários.
Rodar: python3 -m unittest -v test_estado_arvore   (de dentro desta pasta)
"""
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
import time
import unittest
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.realpath(os.environ.get("CS_SKILL_DIR") or os.path.expanduser("~/.claude/skills/codebase-specialists"))
SCRIPTS = os.path.join(SKILL, "scripts")
ENGINE = os.path.join(SCRIPTS, "harness", "engine")
STATE_PY = os.path.join(ENGINE, "state.py")
SESSION_PY = os.path.join(ENGINE, "session.py")
GUARD_PY = os.path.join(ENGINE, "guard.py")
LEGACY_FLAT = os.path.join(HERE, "legacy_flat")
ITER4_TARGET = os.path.join(os.path.dirname(os.path.dirname(HERE)), "iteration-4", "ts-shop-setup-vague", "with_skill",
                            "target")

if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
try:
    from cslib.paths import STATE_DIR as _SD  # noqa: E402
except ImportError:
    _SD = ".swarm"
SD = os.path.basename(str(_SD).rstrip("/")) or ".swarm"

from cslib import json5io  # noqa: E402

VERIFY = "python3 -m unittest discover -s tests -t ."
ACEITE = "python3 -m unittest accept.test_accept"
CRIT = "AC-1|Dado pedido Quando aplico Então desconta|tests.test_billing"
REPRO_RED = "repro.test_repro"          # falha até existir src/billing/fixed.py
REPRO_GREEN = "tests.test_billing"      # passa hoje
HINT = "cs-state new task --tipo FIX --avulsa"
CREATED_RE = re.compile(r"^criad[oa] (\S+) em (\S+)\s*$", re.M)
HEADINGS = ["Fechado nesta sessão", "Frente atual", "Tasks da frente atual", "Em andamento", "Próximos passos",
            "Backlog imediato", "Decisões e pendências humanas", "Integridade"]
HEAD_RE = re.compile(r"^## ([1-8])\. (.+?)\s*$", re.M)
ITEM_FILES = ("epico.json5", "sprint.json5", "feature.json5", "story.json5")
ZONES = ("backlog", "state", "archive")
CLOSED_KEYS = ("at", "by", "summary", "entregue", "devolvido", "metricas")

TEAM = {
    "schema_version": 1,
    "agents": [
        {"name": "dev-billing", "kind": "dev", "territory": ["src/billing/**", "src/shared/**"]},
        {"name": "dev-users", "kind": "dev", "territory": ["src/users/**", "src/shared/**"]},
        {"name": "qa", "kind": "qa", "territory": ["tests/**"]},
        {"name": "po", "kind": "product", "territory": ["docs/stories/**"]},
        {"name": "reviewer", "kind": "gate", "territory": []},
        {"name": "security", "kind": "gate", "territory": []},
    ],
}
RULES = {"facts": [{"id": "rule.global.utf8", "layer": "rules", "claim": "arquivos em UTF-8", "scope": ["**"],
                    "evidence": [{"file": "README.md"}], "confidence": "high", "origin": "mechanical",
                    "fingerprint": "x"}]}
FILES = {
    "README.md": "# demo\n",
    ".gitignore": "__pycache__/\n*.pyc\n",
    "src/billing/total.py": "def total(items):\n    return sum(items)\n",
    "src/users/model.py": "AGE = 18\n",
    "src/shared/util.py": "X = 0\n",
    "tests/__init__.py": "",
    "tests/test_billing.py": "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
    "repro/__init__.py": "",
    "repro/test_repro.py": ("import os, unittest\nclass R(unittest.TestCase):\n    def test_bug(self):\n"
                            "        self.assertTrue(os.path.exists('src/billing/fixed.py'))\n"),
    "accept/__init__.py": "",
    "accept/test_accept.py": ("import os, unittest\nclass A(unittest.TestCase):\n    def test_feature(self):\n"
                              "        self.assertTrue(os.path.exists('src/billing/discount.py'))\n"),
    "docs/stories/README.md": "stories\n",
}


# ====================================================================== infraestrutura
def _env(extra=None):
    e = dict(os.environ)
    for k in ("CLAUDE_PROJECT_DIR", "CS_ACTOR", "CS_GUARD_OFF", "CS_ROOT"):
        e.pop(k, None)
    e.update(extra or {})
    return e


def _run(argv, cwd, env=None, inp=None, timeout=180):
    p = subprocess.run(argv, cwd=cwd, env=env or _env(), input=inp, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       timeout=timeout)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def cs(root, *args, actor=None):
    argv = [sys.executable, STATE_PY, "--root", root]
    if actor:
        argv += ["--actor", actor]
    return _run(argv + list(args), root)


def sess(root, *args):
    return _run([sys.executable, SESSION_PY, "--root", root] + list(args), root)


def hook(root, mode, payload):
    return _run([sys.executable, GUARD_PY, mode], root, env=_env({"CLAUDE_PROJECT_DIR": root}),
                inp=json.dumps(payload).encode())


def git(root, *args):
    subprocess.run(["git"] + list(args), cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def write(root, rel, txt="X = 1\n"):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(txt)


def sd(root, *parts):
    return os.path.join(root, SD, *parts)


def rel(root, path):
    return os.path.relpath(path, root).replace(os.sep, "/")


def read_item(path):
    return json5io.read(path)


def today_candidates():
    return {time.strftime("%Y-%m-%d"), datetime.now(timezone.utc).strftime("%Y-%m-%d")}


def events_bytes(root):
    p = sd(root, "events.jsonl")
    if not os.path.isfile(p):
        return b""
    with open(p, "rb") as f:
        return f.read()


def snapshot(root):
    """{relpath: sha256} de tudo em backlog/state/archive (fora state/sessoes) + events.jsonl."""
    out = {}
    for z in ZONES:
        for dp, _, fs in os.walk(sd(root, z)):
            if os.path.relpath(dp, sd(root)).replace(os.sep, "/").startswith("state/sessoes"):
                continue
            for f in fs:
                p = os.path.join(dp, f)
                with open(p, "rb") as fh:
                    out[rel(root, p)] = hashlib.sha256(fh.read()).hexdigest()
    return out


def tree_paths(root, zone=None):
    """Todos os arquivos (relpath ao alvo) sob as zonas (ou uma zona)."""
    out = []
    for z in ([zone] if zone else ZONES):
        for dp, _, fs in os.walk(sd(root, z)):
            for f in fs:
                out.append(rel(root, os.path.join(dp, f)))
    return sorted(out)


def item_files(root):
    """[(zona, relpath, dados)] de cada arquivo de ITEM (épico/sprint/feature/story/task) nas três zonas."""
    out = []
    for z in ZONES:
        for dp, _, fs in os.walk(sd(root, z)):
            r = os.path.relpath(dp, sd(root)).replace(os.sep, "/")
            if r.startswith("state/sessoes"):
                continue
            for f in fs:
                if not f.endswith(".json5"):
                    continue
                if f in ITEM_FILES or os.path.basename(dp) == "tasks" or "/tasks/" in (r + "/"):
                    p = os.path.join(dp, f)
                    out.append((z, rel(root, p), read_item(p)))
    return out


def folder_of(root, item_id, zone=None):
    """Pastas (relpath) cujo nome é <id> ou <id>-<slug>, que contêm um arquivo de item."""
    out = []
    for z in ([zone] if zone else ZONES):
        for dp, dns, fs in os.walk(sd(root, z)):
            b = os.path.basename(dp)
            if (b == item_id or b.startswith(item_id + "-")) and any(f in ITEM_FILES for f in fs):
                out.append(rel(root, dp))
    return out


def mentions(root, needle, zone):
    return [p for p in tree_paths(root, zone) if needle in p]


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


def route_model(path):
    try:
        for d in walk_dicts(read_item(path)):
            r = d.get("route")
            if isinstance(r, dict) and r.get("model"):
                return r["model"]
    except Exception:
        pass
    return "sonnet"


def parse_blocks(text):
    """→ [(n, título, [linhas não vazias])] na ordem do texto."""
    ms = list(HEAD_RE.finditer(text))
    out = []
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        body = [l.strip() for l in text[m.end():end].splitlines() if l.strip()]
        out.append((int(m.group(1)), m.group(2).strip(), body))
    return out


def estimate_tokens(text):
    return int(len(text) / 3.5 + 0.999)


def make_repo(collision=None, init=True, tc=None):
    root = os.path.realpath(tempfile.mkdtemp(prefix="cs-arvore-"))
    for r, txt in FILES.items():
        write(root, r, txt)
    write(root, os.path.join(SD, "team.json5"), json.dumps(TEAM, ensure_ascii=False, indent=1))
    write(root, os.path.join(SD, "facts", "rules.json5"), json.dumps(RULES, ensure_ascii=False))
    write(root, os.path.join(SD, "facts", "business_rules.json5"), "[]")
    write(root, os.path.join(SD, "facts", "glossary.json5"), "[]")
    write(root, os.path.join(SD, "knowledge", "collision.json5"),
          json.dumps(collision if collision is not None else {"do_not_parallelize": []}))
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@t")
    git(root, "config", "user.name", "t")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "init")
    if init and tc is not None:
        code, out, err = cs(root, "init")
        tc.assertEqual(code, 0, "cs-state init deveria iniciar o estado em árvore: %s%s" % (out, err))
    return root


# ====================================================================== base dos testes
class Base(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.roots = []

    def tearDown(self):
        for r in self.roots:
            shutil.rmtree(r, ignore_errors=True)

    def repo(self, collision=None, init=True):
        r = make_repo(collision=collision, init=False)
        self.roots.append(r)
        if init:
            code, out, err = cs(r, "init")
            self.assertEqual(code, 0, "cs-state init deveria iniciar o estado em árvore (exit %d): %s%s" % (code, out, err))
        return r

    # ---------------------------------------------------------------- criação
    def ok(self, root, *args, actor=None, msg=""):
        code, out, err = cs(root, *args, actor=actor)
        self.assertEqual(code, 0, "%s`cs-state %s` deveria passar (exit %d): %s%s" % (
            msg and msg + ": ", " ".join(args), code, out, err))
        return out

    def refused(self, root, *args, exit_code=1, msg=""):
        code, out, err = cs(root, *args)
        if exit_code is None:
            self.assertNotEqual(code, 0, "%s`cs-state %s` deveria ser recusado: %s%s" % (msg and msg + ": ", " ".join(args), out, err))
        else:
            self.assertEqual(code, exit_code, "%s`cs-state %s` deveria ser recusado com exit %d (veio %d): %s%s" % (
                msg and msg + ": ", " ".join(args), exit_code, code, out, err))
        return out + err

    def new(self, root, *args):
        """Roda `cs-state new ...`; → lista [(id, relpath)] das linhas `criado <ID> em <path>`."""
        out = self.ok(root, "new", *args)
        got = CREATED_RE.findall(out)
        self.assertTrue(got, "`new` deve imprimir `criado <ID> em <path>` (veio: %r)" % out)
        for _, p in got:
            self.assertTrue(os.path.exists(os.path.join(root, p)), "`new` imprimiu %s mas o arquivo não existe" % p)
        return got

    def new1(self, root, *args):
        got = self.new(root, *args)
        return got[0]

    def sprint(self, root, epico=None, start=True, meta="entregar pix"):
        args = ["sprint", "--meta", meta] + (["--epico", epico] if epico else [])
        sid, _ = self.new1(root, *args)
        self.assertRegex(sid, r"^SPR-\d{3}$")
        if start:
            self.ok(root, "start", sid)
        return sid

    def feature(self, root, sprint, title="Pagamento Pix", start=True):
        fid, _ = self.new1(root, "feature", "--title", title, "--sprint", sprint, "--aceite", ACEITE)
        self.assertRegex(fid, r"^FEA-\d{3}$")
        if start:
            self.ok(root, "start", fid)
        return fid

    def task(self, root, parent, tipo="US", title="Confirmar pagamento", agent="dev-billing",
             paths=("src/billing/discount.py",), crit=True, repro=REPRO_RED, fixes=None, teste=None, extra=(),
             motivo="manutencao tecnica sem valor de usuario", verify=VERIFY):
        """parent: ['--feature', FEA] | ['--sprint', SPR] | ['--avulsa'] | ['--backlog'] | ['--story', US-nnn]."""
        args = ["task", "--tipo", tipo, "--agent", agent, "--title", title] + list(parent)
        for p in paths:
            args += ["--allowed-path", p]
        if verify:
            args += ["--verify-cmd", verify]
        if tipo == "CHORE" and motivo:
            args += ["--motivo", motivo]
        if tipo == "US":
            args += ["--como", "cliente", "--quero", "pagar", "--para", "concluir a compra"]
            if crit:
                args += ["--criterio", CRIT]
        elif tipo == "BUG" and repro:
            args += ["--reproducao", repro]
        elif tipo == "FIX":
            if fixes:
                args += ["--fixes", fixes]
            args += ["--teste", teste or REPRO_RED]
        return self.new1(root, *(list(args) + list(extra)))

    # ---------------------------------------------------------------- pipeline de uma task (M2 inteira, sem atalho)
    def dispatch(self, root, tid, path):
        return self.ok(root, "dispatch", tid, "--manual", "--model", route_model(os.path.join(root, path)))

    def run_task(self, root, tid, path, agent="dev-billing", rel_file="src/billing/discount.py", start=True,
                 close=True, summary="entregue"):
        if start:
            self.ok(root, "start", tid)
        self.dispatch(root, tid, path)
        write(root, rel_file)
        self.ok(root, "submit", tid, "--files-changed", rel_file, "--check", "unittest: OK", "--risk", "nenhum",
                "--handoff-notes", "ok", actor=agent)
        self.ok(root, "verify", tid)
        self.ok(root, "review", tid, "--by", "reviewer", "--verdict", "PASS", "--findings", "conferido: teste verde")
        self.ok(root, "accept", tid)
        if close:
            self.ok(root, "close", tid, "--summary", summary)

    def assert_unchanged(self, root, before, msg):
        self.assertEqual(snapshot(root), before, msg + " — nada pode ter se movido/alterado")

    def assert_validate(self, root, msg="validate"):
        code, out, err = cs(root, "validate")
        self.assertEqual(code, 0, "%s: `cs-state validate` deveria passar: %s%s" % (msg, out, err))

    def assert_closed_obj(self, path):
        d = read_item(path)
        c = d.get("closed")
        self.assertIsInstance(c, dict, "%s fechado deve gravar `closed: {...}`" % path)
        for k in CLOSED_KEYS:
            self.assertIn(k, c, "%s: closed sem `%s`" % (path, k))


# ====================================================================== TREE-A/B/C/D
class TestArvorePorCaso(Base):
    def test_tree_a_epico_sprint_feature_tasks_story_composta_e_task_da_sprint(self):
        r = self.repo()
        eid, ep = self.new1(r, "epico", "--title", "Checkout v2", "--objetivo", "pagar com pix", "--metrica", "conversao")
        self.assertEqual(eid, "EPC-001")
        self.assertEqual(ep, "%s/backlog/epicos/EPC-001-checkout-v2/epico.json5" % SD, "épico nasce em backlog/epicos/")
        self.ok(r, "start", eid)
        E = "%s/state/epicos/EPC-001-checkout-v2" % SD
        self.assertTrue(os.path.isfile(os.path.join(r, E, "epico.json5")))
        self.assertFalse(folder_of(r, "EPC-001", "backlog"), "start move o épico: nada dele fica em backlog/")
        sid = self.sprint(r, epico=eid)
        self.assertEqual(sid, "SPR-001")
        S = E + "/sprints/SPR-001"
        self.assertTrue(os.path.isfile(os.path.join(r, S, "sprint.json5")), "sprint do épico mora em <épico>/sprints/SPR-nnn/")
        fid = self.feature(r, sid)
        self.assertEqual(fid, "FEA-001")
        F = S + "/features/FEA-001-pagamento-pix"
        self.assertTrue(os.path.isfile(os.path.join(r, F, "feature.json5")))
        t1, p1 = self.task(r, ["--feature", fid], "US", "Confirmar pagamento")
        t2, p2 = self.task(r, ["--feature", fid], "BUG", "QR expira cedo")
        t3, p3 = self.task(r, ["--feature", fid], "FIX", "QR expira cedo", fixes=t2)
        self.assertEqual((t1, t2, t3), ("FEA-001/01", "FEA-001/02", "FEA-001/03"))
        self.assertEqual(p1, F + "/tasks/01-US-confirmar-pagamento.json5")
        self.assertEqual(p2, F + "/tasks/02-BUG-qr-expira-cedo.json5")
        self.assertEqual(p3, F + "/tasks/03-FIX-qr-expira-cedo.json5")
        self.assertEqual(read_item(os.path.join(r, p3)).get("fixes"), t2, "FIX grava fixes: <id do BUG>")
        got = self.new(r, "story", "--tipo", "US", "--title", "Pagar com Pix", "--feature", fid,
                       "--agents", "dev-billing,qa", "--como", "cliente", "--quero", "pagar com pix",
                       "--para", "concluir", "--criterio", CRIT, "--verify-cmd", VERIFY)
        story = [g for g in got if re.match(r"^US-\d{3}$", g[0])]
        self.assertEqual(len(story), 1, "story composta imprime `criado US-nnn em .../story.json5`: %r" % got)
        sdir = os.path.dirname(os.path.join(r, story[0][1]))
        self.assertTrue(re.search(r"/features/FEA-001-pagamento-pix/stories/US-\d{3}-pagar-com-pix$", sdir), sdir)
        self.assertTrue(os.path.isfile(os.path.join(sdir, "story.json5")))
        ts = sorted(os.listdir(os.path.join(sdir, "tasks")))
        self.assertEqual(len(ts), 2, "uma task por agente: %r" % ts)
        self.assertTrue(ts[0].startswith("01-") and ts[1].startswith("02-"), ts)
        tb, pb = self.task(r, ["--sprint", sid], "BUG", "Erro tela resumo", agent="dev-users",
                           paths=("src/users/model.py",))
        self.assertEqual(tb, "SPR-001/01")
        self.assertEqual(pb, S + "/tasks/01-BUG-erro-tela-resumo.json5", "task da sprint sem feature (caso C dentro do A)")
        self.assert_validate(r, "TREE-A")

    def test_tree_b_sprint_feature_sem_epico(self):
        r = self.repo()
        sid = self.sprint(r)
        self.assertTrue(os.path.isfile(sd(r, "state", "sprints", "SPR-001", "sprint.json5")))
        fid = self.feature(r, sid, "Login SSO")
        F = "%s/state/sprints/SPR-001/features/FEA-001-login-sso" % SD
        self.assertTrue(os.path.isfile(os.path.join(r, F, "feature.json5")))
        _, p1 = self.task(r, ["--feature", fid], "US", "Entrar com Google")
        _, p2 = self.task(r, ["--feature", fid], "US", "Entrar com Microsoft")
        self.assertEqual(p1, F + "/tasks/01-US-entrar-com-google.json5")
        self.assertEqual(p2, F + "/tasks/02-US-entrar-com-microsoft.json5")
        self.assertFalse(mentions(r, "epicos", "state"), "caso B não cria épico")
        self.assert_validate(r, "TREE-B")

    def test_tree_c_sprint_so_com_tasks(self):
        r = self.repo()
        sid = self.sprint(r)
        _, p1 = self.task(r, ["--sprint", sid], "BUG", "Erro tela")
        _, p2 = self.task(r, ["--sprint", sid], "BUG", "Erro rota pessoas")
        self.assertEqual(p1, "%s/state/sprints/SPR-001/tasks/01-BUG-erro-tela.json5" % SD)
        self.assertEqual(p2, "%s/state/sprints/SPR-001/tasks/02-BUG-erro-rota-pessoas.json5" % SD)
        self.assertFalse(mentions(r, "/features/", "state"), "caso C não cria feature")
        self.assert_validate(r, "TREE-C")

    def test_tree_d_task_avulsa_e_o_minimo(self):
        r = self.repo()
        tid, p = self.task(r, ["--avulsa"], "US", "Ajusta timeout")
        self.assertRegex(tid, r"^\d{4}-\d{2}-\d{2}-01$")
        self.assertIn(tid[:10], today_candidates())
        self.assertEqual(p, "%s/state/tasks/%s-US-ajusta-timeout.json5" % (SD, tid))
        self.assertFalse(mentions(r, "sprints", None) + mentions(r, "epicos", None) + mentions(r, "features", None),
                         "task avulsa não cria épico/sprint/feature")
        self.assert_validate(r, "TREE-D")


# ====================================================================== TREE-INV
class TestCombinacoesInvalidas(Base):
    def _base(self):
        r = self.repo()
        eid, _ = self.new1(r, "epico", "--title", "Checkout v2", "--objetivo", "pagar com pix")
        sid = self.sprint(r)
        fid = self.feature(r, sid)
        return r, eid, sid, fid

    def test_sprint_dentro_de_feature_recusada(self):
        r, eid, sid, fid = self._base()
        before = snapshot(r)
        self.refused(r, "move", sid, "--to", fid, msg="sprint dentro de feature")
        self.assert_unchanged(r, before, "move SPR → FEA recusado")
        self.refused(r, "new", "sprint", "--meta", "x", "--feature", fid, exit_code=None, msg="sprint dentro de feature")
        self.assertFalse(folder_of(r, "SPR-002"), "nenhuma sprint pode ter sido criada")

    def test_epico_dentro_de_sprint_recusado(self):
        r, eid, sid, fid = self._base()
        before = snapshot(r)
        self.refused(r, "move", eid, "--to", sid, msg="épico dentro de sprint")
        self.assert_unchanged(r, before, "move EPC → SPR recusado")
        self.refused(r, "new", "epico", "--title", "Outro", "--objetivo", "x", "--sprint", sid, exit_code=None)
        self.assertFalse(folder_of(r, "EPC-002"))

    def test_task_com_dois_pais_recusada(self):
        r, eid, sid, fid = self._base()
        before = snapshot(r)
        for parents in (["--feature", fid, "--sprint", sid], ["--avulsa", "--sprint", sid], ["--avulsa", "--feature", fid]):
            code, out, err = cs(r, "new", "task", "--tipo", "US", "--agent", "dev-billing", "--title", "Dois pais",
                                "--allowed-path", "src/billing/discount.py", "--verify-cmd", VERIFY, "--como", "c",
                                "--quero", "q", "--para", "p", "--criterio", CRIT, *parents)
            self.assertNotEqual(code, 0, "task com dois pais (%s) deveria ser recusada: %s" % (parents, out))
        self.assert_unchanged(r, before, "task com dois pais")

    def test_feature_nunca_executa_fora_de_sprint(self):
        """Feature sem sprint em execução: ou o motor recusa (nada move) ou cria a sprint junto (§1) — nunca uma
        feature em state/ fora de state/**/sprints/SPR-nnn/features/."""
        r = self.repo()
        fid, fp = self.new1(r, "feature", "--title", "Solta", "--backlog", "--aceite", ACEITE)
        self.assertTrue(fp.startswith("%s/backlog/" % SD), "feature --backlog nasce em backlog/: %s" % fp)
        before = snapshot(r)
        code, out, err = cs(r, "start", fid)
        if code != 0:
            self.assertEqual(code, 1, "recusa semântica é exit 1: %s%s" % (out, err))
            self.assert_unchanged(r, before, "start de feature sem sprint recusado")
        for p in mentions(r, fid, "state"):
            self.assertRegex(p, r"/sprints/SPR-\d{3}/features/%s-" % fid, "feature em state/ fora de uma sprint: %s" % p)

    def test_feature_nao_iniciada_nunca_fica_em_state(self):
        r = self.repo()
        sid = self.sprint(r)
        fid = self.feature(r, sid, start=False)
        self.assertFalse(mentions(r, fid, "state"), "feature criada e não iniciada fica em backlog/ (uma ativa por vez)")
        self.assertTrue(mentions(r, fid, "backlog"))


# ====================================================================== TREE-TYPE
class TestTiposDeTask(Base):
    def _feat(self):
        r = self.repo()
        sid = self.sprint(r)
        fid = self.feature(r, sid)
        return r, fid

    def _not_start(self, r, tid, path, words, msg):
        with open(os.path.join(r, path), "rb") as f:
            before = f.read()
        txt = self.refused(r, "start", tid, msg=msg)
        self.assertTrue(any(w in txt.lower() for w in words), "%s: a recusa deve dizer o que falta (%s): %s" % (msg, words, txt))
        with open(os.path.join(r, path), "rb") as f:
            self.assertEqual(f.read(), before, "%s: recusa não altera a task" % msg)

    def test_bug_sem_teste_que_falha_nao_comeca(self):
        r, fid = self._feat()
        tid, p = self.task(r, ["--feature", fid], "BUG", "Sem repro", repro=None)
        self._not_start(r, tid, p, ("reprodu", "teste"), "BUG sem --reproducao")

    def test_bug_com_teste_que_passa_hoje_nao_comeca(self):
        r, fid = self._feat()
        tid, p = self.task(r, ["--feature", fid], "BUG", "Nao reproduz", repro=REPRO_GREEN)
        self._not_start(r, tid, p, ("passa", "reproduz", "vermelho"), "BUG cujo teste já passa")

    def test_bug_com_teste_vermelho_comeca(self):
        r, fid = self._feat()
        tid, _ = self.task(r, ["--feature", fid], "BUG", "Reproduz", repro=REPRO_RED)
        self.ok(r, "start", tid, msg="BUG com reprodução vermelha")

    def test_fix_sem_fixes_nao_comeca_e_com_fixes_comeca(self):
        r, fid = self._feat()
        bug, _ = self.task(r, ["--feature", fid], "BUG", "Reproduz", repro=REPRO_RED)
        tid, p = self.task(r, ["--feature", fid], "FIX", "Corrige sem alvo", fixes=None)
        self._not_start(r, tid, p, ("fixes",), "FIX sem fixes")
        tid2, _ = self.task(r, ["--feature", fid], "FIX", "Corrige", fixes=bug, agent="dev-users",
                            paths=("src/users/model.py",))
        self.ok(r, "start", tid2, msg="FIX com fixes")

    def test_us_sem_criterio_nao_comeca_e_com_criterio_comeca(self):
        r, fid = self._feat()
        tid, p = self.task(r, ["--feature", fid], "US", "Sem criterio", crit=False)
        self._not_start(r, tid, p, ("critério", "criterio"), "US sem critério")
        tid2, _ = self.task(r, ["--feature", fid], "US", "Com criterio", agent="dev-users", paths=("src/users/model.py",))
        self.ok(r, "start", tid2, msg="US com critério")

    def test_fix_so_fecha_com_o_teste_do_bug_verde(self):
        r, fid = self._feat()
        bug, _ = self.task(r, ["--feature", fid], "BUG", "Reproduz", repro=REPRO_RED)
        fix, fp = self.task(r, ["--feature", fid], "FIX", "Corrige", fixes=bug, paths=("src/billing/discount.py",),
                            teste=REPRO_RED)
        # entrega algo que NÃO conserta o BUG: verify/review/accept passam, close recusa (teste do BUG vermelho)
        self.run_task(r, fix, fp, rel_file="src/billing/discount.py", close=False)
        before = snapshot(r)
        txt = self.refused(r, "close", fix, "--summary", "x", msg="FIX com teste do BUG vermelho")
        self.assertIn(REPRO_RED, txt, "a recusa cita o teste do BUG que segue vermelho")
        self.assert_unchanged(r, before, "close de FIX recusado")


# ====================================================================== STORY-1
class TestStories(Base):
    def _feat(self):
        r = self.repo()
        sid = self.sprint(r)
        fid = self.feature(r, sid)
        return r, fid

    def test_story_com_um_agente_vira_task_tipada(self):
        r, fid = self._feat()
        got = self.new(r, "story", "--tipo", "US", "--title", "Pagar com Pix", "--feature", fid, "--agents", "dev-billing",
                       "--como", "cliente", "--quero", "pagar", "--para", "concluir", "--criterio", CRIT,
                       "--verify-cmd", VERIFY)
        self.assertEqual(len(got), 1, got)
        self.assertEqual(got[0][0], "FEA-001/01")
        self.assertTrue(got[0][1].endswith("/features/FEA-001-pagamento-pix/tasks/01-US-pagar-com-pix.json5"), got)
        self.assertFalse(mentions(r, "/stories/", None), "1 agente não cria pasta stories/")

    def test_story_com_dois_agentes_vira_pasta_com_uma_task_por_agente(self):
        r, fid = self._feat()
        got = self.new(r, "story", "--tipo", "US", "--title", "Pagar com Pix", "--feature", fid,
                       "--agents", "dev-billing,qa", "--como", "cliente", "--quero", "pagar", "--para", "concluir",
                       "--criterio", CRIT, "--verify-cmd", VERIFY)
        st = [g for g in got if re.match(r"^US-\d{3}$", g[0])]
        self.assertEqual(len(st), 1, got)
        story = read_item(os.path.join(r, st[0][1]))
        self.assertTrue(story.get("como") and story.get("quero") and story.get("para"), "story.json5 tem como/quero/para")
        self.assertTrue(story.get("criterios"), "story.json5 tem critérios")
        tdir = os.path.join(os.path.dirname(os.path.join(r, st[0][1])), "tasks")
        agents = sorted(read_item(os.path.join(tdir, f)).get("agent") for f in os.listdir(tdir))
        self.assertEqual(agents, ["dev-billing", "qa"], "uma task por agente")

    def test_promote_converte_simples_em_composta_mantendo_id_e_historico(self):
        r, fid = self._feat()
        tid, p = self.task(r, ["--feature", fid], "US", "Pagar com Pix")
        ev0 = events_bytes(r)
        self.ok(r, "promote", tid)
        self.assertFalse(os.path.exists(os.path.join(r, p)), "promote MOVE a task (não copia)")
        sts = [x for x in mentions(r, "/stories/", "state") if x.endswith("story.json5")]
        self.assertEqual(len(sts), 1, "promote cria stories/<TIPO>-nnn-<slug>/story.json5: %r" % sts)
        self.assertRegex(sts[0], r"/stories/US-\d{3}-pagar-com-pix/story\.json5$")
        moved = [x for x in mentions(r, "/stories/", "state") if "/tasks/" in x]
        self.assertEqual(len(moved), 1, moved)
        self.assertEqual(read_item(os.path.join(r, moved[0])).get("title"), "Pagar com Pix")
        out = self.ok(r, "find", tid, msg="id antigo continua resolvendo")
        self.assertIn(moved[0].split(SD + "/", 1)[1], out.replace(SD + "/", ""), "find <id antigo> aponta o novo lugar")
        ev1 = events_bytes(r)
        self.assertTrue(ev1.startswith(ev0) and len(ev1) > len(ev0), "histórico preservado (append-only) e promote registrado")
        self.assertIn(tid, ev1[len(ev0):].decode("utf-8"), "evento do promote cita o id antigo")
        self.assert_validate(r, "promote")


# ====================================================================== ONE-FEATURE
class TestUmaFeatureAtiva(Base):
    def test_segunda_feature_recusada_ate_close_ou_park(self):
        r = self.repo()
        sid = self.sprint(r)
        f1 = self.feature(r, sid, "Pagamento Pix")
        f2 = self.feature(r, sid, "Login SSO", start=False)
        before = snapshot(r)
        txt = self.refused(r, "start", f2, msg="segunda feature com uma em state/")
        self.assertIn(f1, txt, "a recusa nomeia a feature ativa")
        self.assertTrue("close" in txt and "park" in txt, "a recusa indica close ou park: %s" % txt)
        self.assert_unchanged(r, before, "start da 2ª feature recusado")
        self.ok(r, "park", f1, "--reason", "prioridade mudou")
        self.assertFalse(mentions(r, f1, "state"), "park devolve a feature ao backlog/")
        parked = [p for p in mentions(r, f1, "backlog") if p.endswith("feature.json5")]
        self.assertEqual(len(parked), 1)
        with open(os.path.join(r, parked[0]), encoding="utf-8") as f:
            self.assertIn("prioridade mudou", f.read(), "park grava o motivo no item")
        self.ok(r, "start", f2, msg="depois do park a outra feature começa")
        self.assert_validate(r, "ONE-FEATURE")

    def test_avulsa_e_task_da_sprint_nao_contam_como_feature_ativa(self):
        r = self.repo()
        sid = self.sprint(r)
        self.feature(r, sid)
        ta, _ = self.task(r, ["--avulsa"], "US", "Ajusta timeout", agent="dev-users", paths=("src/users/model.py",))
        self.ok(r, "start", ta, msg="avulsa com feature ativa")
        ts, _ = self.task(r, ["--sprint", sid], "BUG", "Erro tela", agent="qa", paths=("tests/test_extra.py",))
        self.ok(r, "start", ts, msg="task da sprint com feature ativa")


# ====================================================================== PARALLEL-1
class TestParalelismo(Base):
    def _two(self, collision=None, shared=False):
        r = self.repo(collision=collision)
        sid = self.sprint(r)
        fid = self.feature(r, sid)
        p1 = ("src/shared/util.py",) if shared else ("src/billing/discount.py",)
        p2 = ("src/shared/util.py",) if shared else ("src/users/age.py",)
        t1, f1 = self.task(r, ["--feature", fid], "US", "Parte um", agent="dev-billing", paths=p1)
        t2, f2 = self.task(r, ["--feature", fid], "US", "Parte dois", agent="dev-users", paths=p2)
        self.ok(r, "start", t1)
        self.ok(r, "start", t2)
        return r, (t1, f1), (t2, f2)

    def test_sem_arquivo_comum_despacham_em_paralelo(self):
        r, (t1, f1), (t2, f2) = self._two()
        self.assertEqual(read_item(os.path.join(r, f1)).get("wave"), 1)
        self.assertEqual(read_item(os.path.join(r, f2)).get("wave"), 1, "sem colisão: mesma wave")
        self.dispatch(r, t1, f1)
        self.dispatch(r, t2, f2)

    def test_arquivo_comum_manda_a_segunda_para_a_wave_seguinte(self):
        r, (t1, f1), (t2, f2) = self._two(shared=True)
        self.assertEqual(read_item(os.path.join(r, f1)).get("wave"), 1)
        self.assertEqual(read_item(os.path.join(r, f2)).get("wave"), 2, "mesmo arquivo: a 2ª vai para a wave seguinte")
        self.dispatch(r, t1, f1)
        txt = self.refused(r, "dispatch", t2, "--manual", "--model", route_model(os.path.join(r, f2)),
                           msg="despacho em paralelo com arquivo comum")
        self.assertIn(t1, txt, "a recusa cita a task em voo com que colide")

    def test_par_do_not_parallelize_manda_para_a_wave_seguinte(self):
        col = {"do_not_parallelize": [{"a": "dev-billing", "b": "dev-users", "co_change": 7}]}
        r, (t1, f1), (t2, f2) = self._two(collision=col)
        self.assertEqual(read_item(os.path.join(r, f2)).get("wave"), 2, "par em do_not_parallelize: wave seguinte")
        self.dispatch(r, t1, f1)
        self.refused(r, "dispatch", t2, "--manual", "--model", route_model(os.path.join(r, f2)),
                     msg="par do_not_parallelize em paralelo")


# ====================================================================== TREE-GUARD + escritor único
class TestGuard(Base):
    def _wp(self, r, relp, actor=None, tool="Write"):
        p = {"tool_name": tool, "tool_use_id": "tu-w", "tool_input": {"file_path": os.path.join(r, relp)}, "cwd": r}
        p.update(actor or {})
        return p

    def _bp(self, r, cmd, actor=None):
        p = {"tool_name": "Bash", "tool_use_id": "tu-b", "tool_input": {"command": cmd}, "cwd": r}
        p.update(actor or {})
        return p

    SUB = {"agent_id": "ag-1", "agent_type": "dev-billing"}

    def test_alteracao_de_produto_sem_task_bloqueada_com_a_dica(self):
        r = self.repo()
        for actor in (None, self.SUB):
            code, out, err = hook(r, "pre-write", self._wp(r, "src/billing/discount.py", actor))
            self.assertEqual(code, 2, "escrita de produto sem task deve ser bloqueada (%s)" % (actor or "principal"))
            self.assertIn(HINT, out + err, "o bloqueio traz a dica mínima `%s ...`" % HINT)

    def test_com_uma_task_avulsa_a_escrita_e_liberada(self):
        r = self.repo()
        tid, p = self.task(r, ["--avulsa"], "US", "Ajusta timeout")
        self.ok(r, "start", tid)
        self.dispatch(r, tid, p)
        code, out, err = hook(r, "pre-write", self._wp(r, "src/billing/discount.py", self.SUB))
        self.assertEqual(code, 0, "com 1 task avulsa em andamento a escrita do agente da task é liberada: " + out + err)
        code, _, _ = hook(r, "pre-write", self._wp(r, "src/users/model.py", self.SUB))
        self.assertEqual(code, 2, "fora do allowed_path da task continua bloqueado")

    def test_modelo_nunca_escreve_em_backlog_state_archive(self):
        r = self.repo()
        tid, p = self.task(r, ["--avulsa"], "US", "Ajusta timeout")
        self.ok(r, "start", tid)
        self.dispatch(r, tid, p)
        for z in ZONES:
            for actor in (None, self.SUB):
                for tool in ("Write", "Edit"):
                    code, _, _ = hook(r, "pre-write", self._wp(r, "%s/%s/tasks/x.json5" % (SD, z), actor, tool))
                    self.assertEqual(code, 2, "%s em %s/%s por %s deve ser bloqueado" % (tool, SD, z, actor or "principal"))
        for cmd in ("mv %s %s/archive/tasks/" % (p, SD), "cp %s %s/backlog/tasks/" % (p, SD),
                    "rm -rf %s/state" % SD, "echo x > %s/state/tasks/y.json5" % SD):
            code, _, _ = hook(r, "pre-bash", self._bp(r, cmd))
            self.assertEqual(code, 2, "Bash que mexe na árvore pelo modelo deve ser bloqueado: %s" % cmd)


# ====================================================================== integridade (TREE-HAND, coerência)
class TestIntegridade(Base):
    def _pop(self):
        r = self.repo()
        sid = self.sprint(r)
        fid = self.feature(r, sid)
        t1, p1 = self.task(r, ["--feature", fid], "US", "Confirmar pagamento")
        ta, pa = self.task(r, ["--avulsa"], "US", "Ajusta timeout", agent="dev-users", paths=("src/users/model.py",))
        return r, sid, fid, (t1, p1), (ta, pa)

    def test_arvore_coerente_com_eventos_board_e_index(self):
        r, sid, fid, (t1, p1), (ta, pa) = self._pop()
        self.assert_validate(r, "estado criado só por comandos")
        ev = events_bytes(r).decode("utf-8")
        items = item_files(r)
        self.assertGreaterEqual(len(items), 4, items)
        for z, p, d in items:
            iid = d.get("id")
            self.assertTrue(isinstance(iid, str) and iid, "%s sem `id`" % p)
            self.assertIn(iid, ev, "todo arquivo tem evento: %s (%s) não aparece em events.jsonl" % (p, iid))
        board = self.ok(r, "board")
        tree = self.ok(r, "tree")
        for iid in (sid, fid, t1, ta):
            self.assertIn(iid, board, "`cs-state board` (visão gerada) lista %s" % iid)
            self.assertIn(iid, tree, "`cs-state tree` lista %s" % iid)
        self.assertFalse(os.path.exists(sd(r, "state", "board.json5")) or os.path.exists(sd(r, "board.json5")),
                         "board.json5 deixa de existir (visões são geradas)")
        idx = sd(r, "INDEX.md")
        self.assertTrue(os.path.isfile(idx), "INDEX.md gerado")
        with open(idx, encoding="utf-8") as f:
            txt = f.read()
        for iid in (sid, fid, ta):
            self.assertIn(iid, txt)

    def test_eventos_sao_append_only(self):
        r, sid, fid, (t1, p1), (ta, pa) = self._pop()
        ev0 = events_bytes(r)
        self.ok(r, "start", t1)
        ev1 = events_bytes(r)
        self.assertTrue(ev1.startswith(ev0) and len(ev1) > len(ev0), "start acrescenta evento sem reescrever o passado")

    def test_edicao_a_mao_e_acusada(self):
        r, sid, fid, (t1, p1), (ta, pa) = self._pop()
        path = os.path.join(r, p1)
        d = read_item(path)
        d["title"] = "editado a mao"
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(d, ensure_ascii=False))
        code, out, err = cs(r, "validate")
        self.assertEqual(code, 1, "edição à mão de item deve reprovar validate: %s%s" % (out, err))
        self.assertTrue(os.path.basename(p1) in out + err or t1 in out + err, "validate aponta o item editado")

    def test_arquivo_orfao_e_acusado(self):
        r, sid, fid, (t1, p1), (ta, pa) = self._pop()
        orfao = sd(r, "state", "tasks", "2020-01-01-01-US-orfao.json5")
        with open(orfao, "w", encoding="utf-8") as f:
            f.write(json.dumps({"id": "2020-01-01-01", "tipo": "US", "title": "orfao"}))
        code, out, err = cs(r, "validate")
        self.assertEqual(code, 1, "arquivo de item sem evento (órfão) deve reprovar validate")
        self.assertIn("orfao", out + err)

    def test_fechado_dentro_de_state_e_acusado(self):
        r, sid, fid, (t1, p1), (ta, pa) = self._pop()
        self.run_task(r, ta, pa, agent="dev-users", rel_file="src/users/model.py")
        arch = [p for p in mentions(r, os.path.basename(pa), "archive")]
        self.assertEqual(len(arch), 1, "avulsa fechada vai para archive/: %r" % arch)
        dst = os.path.join(r, pa)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy(os.path.join(r, arch[0]), dst)  # alguém "devolve" o fechado para state/ à mão
        code, out, err = cs(r, "validate")
        self.assertEqual(code, 1, "item fechado dentro de state/ deve reprovar validate")


# ====================================================================== TREE-MOVE
class TestMoveEPlan(Base):
    def test_move_avulsa_para_sprint_mantem_id_e_historico(self):
        r = self.repo()
        sid = self.sprint(r)
        self.task(r, ["--sprint", sid], "BUG", "Erro tela")
        t2, p2 = self.task(r, ["--sprint", sid], "BUG", "Erro rota", agent="dev-users", paths=("src/users/model.py",))
        ta, pa = self.task(r, ["--avulsa"], "US", "Ajusta timeout", agent="qa", paths=("tests/test_extra.py",))
        ev0 = events_bytes(r)
        self.ok(r, "move", ta, "--to", sid)
        self.assertFalse(os.path.exists(os.path.join(r, pa)))
        dst = "%s/state/sprints/SPR-001/tasks/03-US-ajusta-timeout.json5" % SD
        self.assertTrue(os.path.isfile(os.path.join(r, dst)), "move dá o próximo nn do novo pai (03)")
        out = self.ok(r, "find", ta)
        self.assertIn("03-US-ajusta-timeout", out, "id antigo continua resolvendo após o move")
        ev1 = events_bytes(r)
        self.assertTrue(ev1.startswith(ev0) and ta in ev1[len(ev0):].decode("utf-8"), "move registrado, histórico preservado")
        # nn nunca reaproveitado: tira a 02 da sprint e cria outra → 04
        self.ok(r, "move", t2, "--avulsa")
        _, p4 = self.task(r, ["--sprint", sid], "BUG", "Outro erro", agent="po", paths=("docs/stories/x.md",))
        self.assertTrue(os.path.basename(p4).startswith("04-"), "nn nunca é reaproveitado: %s" % p4)
        self.assert_validate(r, "TREE-MOVE")

    def test_plan_leva_task_do_backlog_para_a_sprint(self):
        r = self.repo()
        sid = self.sprint(r)
        tb, pb = self.task(r, ["--backlog"], "BUG", "Esperando")
        self.assertTrue(pb.startswith("%s/backlog/tasks/" % SD), pb)
        self.assertRegex(os.path.basename(pb), r"^\d{2}-BUG-esperando\.json5$")
        self.ok(r, "plan", tb, "--sprint", sid)
        self.assertFalse(os.path.exists(os.path.join(r, pb)))
        self.assertTrue(os.path.isfile(sd(r, "state", "sprints", "SPR-001", "tasks", "01-BUG-esperando.json5")))
        self.assert_validate(r, "plan")


# ====================================================================== ARCHIVE-1..6
class TestFechamento(Base):
    def test_archive_1_close_sprint_com_tudo_fechado_move_arvore(self):
        r = self.repo()
        sid = self.sprint(r)
        fid = self.feature(r, sid)
        t1, p1 = self.task(r, ["--feature", fid], "US", "Confirmar pagamento")
        self.run_task(r, t1, p1)
        a1 = "%s/archive/%s" % (SD, p1.split("/state/", 1)[1])
        self.assertFalse(os.path.exists(os.path.join(r, p1)), "close task move o arquivo da task")
        self.assertTrue(os.path.isfile(os.path.join(r, a1)), "task fechada vai para archive/ na MESMA árvore: %s" % a1)
        self.assert_closed_obj(os.path.join(r, a1))
        self.ok(r, "close", fid, "--summary", "pix entregue")
        F = "%s/archive/sprints/SPR-001/features/FEA-001-pagamento-pix" % SD
        self.assertTrue(os.path.isfile(os.path.join(r, F, "feature.json5")))
        self.assert_closed_obj(os.path.join(r, F, "feature.json5"))
        self.ok(r, "close", sid, "--summary", "sprint entregue")
        self.assertTrue(os.path.isfile(sd(r, "archive", "sprints", "SPR-001", "sprint.json5")))
        self.assert_closed_obj(sd(r, "archive", "sprints", "SPR-001", "sprint.json5"))
        self.assertFalse(mentions(r, "SPR-001", "state"), "nada da sprint fica em state/")
        with open(sd(r, "INDEX.md"), encoding="utf-8") as f:
            self.assertIn(sid, f.read(), "INDEX.md regenerado lista o fechado")
        self.assert_validate(r, "ARCHIVE-1")

    def test_archive_2_close_sprint_com_task_aberta_devolve_ao_backlog(self):
        r = self.repo()
        sid = self.sprint(r)
        tb, pb = self.task(r, ["--sprint", sid], "BUG", "Erro tela")
        before = snapshot(r)
        txt = self.refused(r, "close", sid, "--summary", "x", msg="sprint com task aberta sem --devolver")
        self.assertIn(tb, txt, "a recusa lista o que falta")
        self.assert_unchanged(r, before, "close sprint recusado")
        self.ok(r, "close", sid, "--summary", "parcial", "--devolver", "--reason", "fica para a proxima")
        self.assertTrue(os.path.isfile(sd(r, "archive", "sprints", "SPR-001", "sprint.json5")), "sprint arquivada")
        back = [p for p in mentions(r, "-BUG-erro-tela", "backlog") if p.endswith(".json5")]
        self.assertEqual(len(back), 1, "task aberta volta ao backlog/: %r" % back)
        with open(os.path.join(r, back[0]), encoding="utf-8") as f:
            self.assertIn("fica para a proxima", f.read(), "devolução grava o motivo")
        self.assertFalse(mentions(r, "SPR-001", "state"))
        self.assert_validate(r, "ARCHIVE-2")

    def test_archive_3_close_feature_com_task_aberta_recusa_e_nada_move(self):
        r = self.repo()
        sid = self.sprint(r)
        fid = self.feature(r, sid)
        t1, _ = self.task(r, ["--feature", fid], "US", "Confirmar pagamento")
        before = snapshot(r)
        txt = self.refused(r, "close", fid, "--summary", "x", msg="feature com task aberta")
        self.assertIn(t1, txt, "a recusa lista a task aberta")
        self.assert_unchanged(r, before, "close feature recusado")

    def test_archive_4_avulsa_fechada_vai_para_ano_mes(self):
        r = self.repo()
        ta, pa = self.task(r, ["--avulsa"], "US", "Ajusta timeout")
        self.run_task(r, ta, pa)
        y, m = ta[:4], ta[5:7]
        dst = sd(r, "archive", "tasks", y, m, os.path.basename(pa))
        self.assertTrue(os.path.isfile(dst), "avulsa fechada → archive/tasks/<ano>/<mês>/: %s" % rel(r, dst))
        self.assertFalse(os.path.exists(os.path.join(r, pa)))
        self.assert_closed_obj(dst)
        self.assert_validate(r, "ARCHIVE-4")

    def test_archive_5_reopen_devolve_ao_state_com_historico(self):
        r = self.repo()
        ta, pa = self.task(r, ["--avulsa"], "US", "Ajusta timeout")
        self.run_task(r, ta, pa)
        ev0 = events_bytes(r)
        self.ok(r, "reopen", ta, "--reason", "regrediu em producao")
        self.assertTrue(os.path.isfile(os.path.join(r, pa)), "reopen devolve ao state/ no mesmo lugar")
        self.assertFalse(mentions(r, os.path.basename(pa), "archive"), "nada aberto dentro de archive/")
        ev1 = events_bytes(r)
        self.assertTrue(ev1.startswith(ev0) and len(ev1) > len(ev0), "cadeia preservada e estendida")
        self.assert_validate(r, "ARCHIVE-5")

    def test_archive_6_close_epico_so_com_todas_as_sprints_fechadas(self):
        r = self.repo()
        eid, _ = self.new1(r, "epico", "--title", "Checkout v2", "--objetivo", "pagar com pix")
        self.ok(r, "start", eid)
        sid = self.sprint(r, epico=eid)
        before = snapshot(r)
        txt = self.refused(r, "close", eid, "--summary", "x", msg="épico com sprint aberta")
        self.assertIn(sid, txt, "a recusa lista a sprint aberta")
        self.assert_unchanged(r, before, "close épico recusado")
        tb, pb = self.task(r, ["--sprint", sid], "US", "Confirmar pagamento")
        self.run_task(r, tb, pb)
        self.ok(r, "close", sid, "--summary", "sprint entregue")
        self.ok(r, "close", eid, "--summary", "checkout v2 no ar")
        E = sd(r, "archive", "epicos", "EPC-001-checkout-v2")
        self.assertTrue(os.path.isfile(os.path.join(E, "epico.json5")))
        self.assertTrue(os.path.isfile(os.path.join(E, "sprints", "SPR-001", "sprint.json5")), "árvore inteira arquivada")
        self.assertFalse(mentions(r, "EPC-001", "state"))
        self.assert_validate(r, "ARCHIVE-6")

    def test_close_sem_accept_e_recusado_nenhum_atalho(self):
        r = self.repo()
        ta, pa = self.task(r, ["--avulsa"], "US", "Ajusta timeout")
        self.ok(r, "start", ta)
        self.dispatch(r, ta, pa)
        before = snapshot(r)
        self.refused(r, "close", ta, "--summary", "x", msg="close de task em voo (atalho para ACCEPTED)")
        self.assert_unchanged(r, before, "close sem verify/review/accept")


class TestCloseStory(Base):
    """`close <story>` (coerente com §6): fecha a story composta quando todas as tasks estão fechadas; senão recusa
    listando as pendentes e nada se move; fechada → a pasta da story vai para archive/ na mesma árvore."""

    def test_close_story_recusa_com_task_aberta_e_arquiva_quando_tudo_fechado(self):
        r = self.repo()
        sid = self.sprint(r)
        fid = self.feature(r, sid)
        got = self.new(r, "story", "--tipo", "US", "--title", "Pagar com Pix", "--feature", fid,
                       "--agents", "dev-billing,qa", "--como", "cliente", "--quero", "pagar", "--para", "concluir",
                       "--criterio", CRIT, "--verify-cmd", VERIFY)
        st, sp = [g for g in got if re.match(r"^US-\d{3}$", g[0])][0]
        tks = sorted(g for g in got if g[0].startswith(st + "/"))
        self.assertEqual(len(tks), 2, got)
        by_agent = {read_item(os.path.join(r, p)).get("agent"): (t, p) for t, p in tks}
        before = snapshot(r)
        txt = self.refused(r, "close", st, "--summary", "x", msg="story com tasks abertas")
        for t, _ in tks:
            self.assertIn(t, txt, "a recusa lista a task pendente %s" % t)
        self.assert_unchanged(r, before, "close story recusado")
        t, p = by_agent["dev-billing"]
        self.run_task(r, t, p)
        txt = self.refused(r, "close", st, "--summary", "x", msg="story com 1 task aberta")
        self.assertIn(by_agent["qa"][0], txt)
        t, p = by_agent["qa"]
        self.run_task(r, t, p, agent="qa", rel_file="tests/test_extra.py")
        self.ok(r, "close", st, "--summary", "pix pago")
        dst = "%s/archive/%s" % (SD, sp.split("/state/", 1)[1])
        self.assertTrue(os.path.isfile(os.path.join(r, dst)), "story fechada → archive/ na mesma árvore: %s" % dst)
        self.assert_closed_obj(os.path.join(r, dst))
        self.assertFalse(mentions(r, "/stories/" + os.path.basename(os.path.dirname(sp)), "state"),
                         "nada da story fica em state/")
        self.assert_validate(r, "close story")


# ====================================================================== D-0-12
class TestD012FeatureDrop(Base):
    def test_feature_drop_com_task_em_andamento_recusado(self):
        r = self.repo()
        sid = self.sprint(r)
        fid = self.feature(r, sid)
        t1, p1 = self.task(r, ["--feature", fid], "US", "Confirmar pagamento")
        self.ok(r, "start", t1)
        self.dispatch(r, t1, p1)
        before = snapshot(r)
        txt = self.refused(r, "feature", "drop", "--id", fid, "--reason", "desistimos", msg="D-0-12")
        self.assertIn(t1, txt, "a recusa lista a story/task em andamento")
        self.assert_unchanged(r, before, "feature drop recusado")
        self.assert_validate(r, "D-0-12")

    def test_feature_drop_com_story_composta_em_andamento_recusado(self):
        r = self.repo()
        sid = self.sprint(r)
        fid = self.feature(r, sid)
        got = self.new(r, "story", "--tipo", "US", "--title", "Pagar com Pix", "--feature", fid,
                       "--agents", "dev-billing,qa", "--como", "cliente", "--quero", "pagar", "--para", "concluir",
                       "--criterio", CRIT, "--verify-cmd", VERIFY)
        st = [g for g in got if re.match(r"^US-\d{3}$", g[0])][0][0]
        tk = [g for g in got if g[0].startswith(st + "/")]
        self.assertTrue(tk, got)
        self.ok(r, "start", tk[0][0])
        before = snapshot(r)
        txt = self.refused(r, "feature", "drop", "--id", fid, "--reason", "desistimos", msg="D-0-12 story composta")
        self.assertTrue(st in txt or tk[0][0] in txt, "a recusa lista a story em andamento: %s" % txt)
        self.assert_unchanged(r, before, "feature drop recusado")

    def test_feature_drop_sem_nada_em_andamento_passa(self):
        r = self.repo()
        sid = self.sprint(r)
        fid = self.feature(r, sid)
        self.task(r, ["--feature", fid], "US", "Confirmar pagamento")
        self.ok(r, "feature", "drop", "--id", fid, "--reason", "fora de escopo")
        self.assertFalse(mentions(r, fid, "state"), "feature descartada sai de state/")
        self.assert_validate(r, "drop")


# ====================================================================== SESSION-1..3
class TestSessao(Base):
    def _frente(self):
        r = self.repo()
        sid = self.sprint(r)
        fid = self.feature(r, sid)
        t1, p1 = self.task(r, ["--feature", fid], "US", "Parte um")
        t2, p2 = self.task(r, ["--feature", fid], "US", "Parte dois", agent="dev-users", paths=("src/users/age.py",))
        t3, p3 = self.task(r, ["--feature", fid], "US", "Parte tres", paths=("src/billing/extra.py",))
        t4, p4 = self.task(r, ["--feature", fid], "US", "Parte quatro", agent="dev-users", paths=("src/users/x.py",))
        return r, sid, fid, [(t1, p1), (t2, p2), (t3, p3), (t4, p4)]

    def _sessoes(self, r):
        return sorted(glob.glob(sd(r, "state", "sessoes", "*.json5")))

    def test_session_1_save_gera_os_8_blocos(self):
        r, sid, fid, ts = self._frente()
        (t1, p1), (t2, p2), (t3, p3), (t4, p4) = ts
        self.run_task(r, t1, p1)
        self.run_task(r, t2, p2, agent="dev-users", rel_file="src/users/age.py")
        self.ok(r, "start", t3)
        self.dispatch(r, t3, p3)                              # delegação em voo
        self.ok(r, "start", t4)
        self.ok(r, "escalate", t4, "--reason", "decisao de produto pendente")   # portão humano pendente
        git(r, "add", "-A")
        git(r, "commit", "-qm", "estado")
        code, out, err = sess(r, "save")
        self.assertEqual(code, 0, "cs-session save: %s%s" % (out, err))
        self.assertLessEqual(estimate_tokens(out), 2000, "carimbo ≤2.000 tokens")
        bl = parse_blocks(out)
        self.assertEqual([(n, t) for n, t, _ in bl], list(zip(range(1, 9), HEADINGS)),
                         "8 blocos `## N. Título`, nesta ordem: %s" % out)
        b = {n: "\n".join(lines) for n, _, lines in bl}
        for n, _, lines in bl:
            self.assertTrue(lines, "bloco %d vazio (use 'nenhum' explícito)" % n)
        for t in (t1, t2):
            self.assertIn(t, b[1], "bloco 1 lista o fechado %s" % t)
        self.assertIn("archive/", b[1], "bloco 1 diz para onde foi em archive/")
        self.assertIn("%s › %s" % (sid, fid), b[2], "bloco 2: cadeia completa")
        self.assertIn("2/4", b[2], "bloco 2: progresso fechadas/total")
        lines3 = b[3].splitlines()
        for t in (t3, t4):
            self.assertEqual(len([l for l in lines3 if t in l]), 1, "bloco 3: 1 linha por task (%s)" % t)
        self.assertIn(t3, b[4])
        self.assertIn("dev-billing", b[4], "bloco 4: agente da delegação em voo")
        self.assert_steps(b[5])
        self.assertIn(t4, b[7], "bloco 7: portão humano pendente")
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=r, stdout=subprocess.PIPE).stdout.decode().strip()
        self.assertIn(head[:7], b[8], "bloco 8: HEAD no carimbo")
        self.assertEqual(len(self._sessoes(r)), 1, "grava state/sessoes/<timestamp>.json5")
        code, out2, err2 = sess(r, "save", "--check")
        self.assertEqual(code, 0, "save --check passa num carimbo íntegro: %s%s" % (out2, err2))

    def assert_steps(self, text):
        steps = [l for l in text.splitlines() if l.strip()]
        self.assertTrue(steps, "bloco 5 sem passos")
        for l in steps:
            self.assertRegex(l, r"^\d+\. ", "passo numerado: %r" % l)
            m = re.search(r"`([^`]+)`", l)
            self.assertTrue(m, "todo passo tem comando pronto entre crases: %r" % l)
            cmd = m.group(1)
            self.assertIn(os.path.basename(shlex.split(cmd)[0]), ("cs-state", "cs-session"), cmd)
            self.assertNotIn("<", cmd, "comando pronto (sem placeholder): %r" % cmd)
            self.assertNotIn("...", cmd, "comando pronto (sem reticências): %r" % cmd)

    def test_session_2_nenhum_explicito_e_check_falha_sem_comando_ou_com_bloco_vazio(self):
        r = self.repo()
        self.task(r, ["--avulsa"], "US", "Ajusta timeout")
        code, out, err = sess(r, "save")
        self.assertEqual(code, 0, out + err)
        b = {n: "\n".join(lines) for n, _, lines in parse_blocks(out)}
        for n in (1, 7):
            self.assertIn("nenhum", b.get(n, "").lower(), "bloco %d sem conteúdo diz 'nenhum' explicitamente" % n)
        code, o, e = sess(r, "save", "--check")
        self.assertEqual(code, 0, "check passa: %s%s" % (o, e))
        path = self._sessoes(r)[-1]
        orig = read_item(path)
        self.assertEqual(len(orig.get("blocos") or []), 8, "sessão gravada tem `blocos` (8)")

        def check_with(mut):
            d = json.loads(json.dumps(orig))
            mut(d)
            with open(path, "w", encoding="utf-8") as f:
                f.write(json.dumps(d, ensure_ascii=False))
            return sess(r, "save", "--check")

        code, o, e = check_with(lambda d: d["blocos"][4].__setitem__("linhas", ["1. rodar os testes"]))
        self.assertEqual(code, 1, "passo sem comando reprova save --check")
        self.assertTrue("Próximos passos" in o + e and "comando" in (o + e).lower(), o + e)
        code, o, e = check_with(lambda d: d["blocos"][5].__setitem__("linhas", []))
        self.assertEqual(code, 1, "bloco vazio sem 'nenhum' reprova save --check")
        self.assertTrue("Backlog imediato" in o + e and "nenhum" in (o + e).lower(), o + e)

    def test_session_3_sessao_nova_so_com_load_executa_o_passo_1(self):
        r, sid, fid, ts = self._frente()
        (t1, p1) = ts[0]
        self.ok(r, "start", t1)
        self.dispatch(r, t1, p1)
        write(r, "src/billing/discount.py")
        self.ok(r, "submit", t1, "--files-changed", "src/billing/discount.py", "--check", "unittest: OK", "--risk",
                "nenhum", "--handoff-notes", "ok", actor="dev-billing")
        code, out, err = sess(r, "save")
        self.assertEqual(code, 0, out + err)
        code, out, err = sess(r, "load")
        self.assertEqual(code, 0, out + err)
        b = {n: "\n".join(lines) for n, _, lines in parse_blocks(out)}
        self.assertIn(5, b, "load imprime o carimbo (8 blocos): %s" % out)
        self.assert_steps(b[5])
        first = re.search(r"`([^`]+)`", b[5].splitlines()[0]).group(1)
        self.assertIn(t1, first, "passo 1 = verificar a task submetida (%s): %r" % (t1, first))
        argv = shlex.split(first)
        tool = os.path.basename(argv[0])
        ev0 = events_bytes(r)
        code, o, e = (cs(r, *argv[1:]) if tool == "cs-state" else sess(r, *argv[1:]))
        self.assertEqual(code, 0, "o passo 1 copiado do load roda sem reler nada: %s%s" % (o, e))
        self.assertGreater(len(events_bytes(r)), len(ev0), "o passo 1 avançou o estado")
        # delta: algo muda depois do save → load mostra só o delta (cita o item novo)
        ta, _ = self.task(r, ["--avulsa"], "US", "Ajusta timeout", agent="dev-users", paths=("src/users/model.py",))
        code, out, err = sess(r, "load")
        self.assertEqual(code, 0, out + err)
        self.assertIn(ta, out, "load com carimbo divergente mostra o delta desde o save")


# ====================================================================== MIGRATE-1 (upgrade kind state-tree)
class TestMigracao(Base):
    def _legacy(self, src_dir):
        r = self.repo(init=False)
        os.makedirs(sd(r, "state"), exist_ok=True)
        for f in ("board.json5", "events.jsonl"):
            shutil.copy(os.path.join(src_dir, f), sd(r, "state", f))
        with open(sd(r, "state", "events.jsonl"), "rb") as f:
            return r, f.read()

    def _by_legacy(self, r):
        out = {}
        for z, p, d in item_files(r):
            if d.get("legacy_id"):
                out.setdefault(d["legacy_id"], []).append((z, p, d))
        return out

    def test_migrate_1_board_legado_vira_arvore_equivalente(self):
        r, ev_old = self._legacy(LEGACY_FLAT)
        self.ok(r, "migrate", "state-tree", msg="migração state-tree")
        ev = events_bytes(r)
        self.assertTrue(ev.startswith(ev_old) and len(ev) > len(ev_old),
                        "events.jsonl legado preservado byte a byte e estendido em %s/events.jsonl" % SD)
        self.assertFalse(os.path.exists(sd(r, "state", "board.json5")), "board.json5 sai de state/")
        bk = [p for p in glob.glob(sd(r, "**", "board.json5"), recursive=True)]
        self.assertTrue(bk, "backup do board.json5 legado guardado")
        m = self._by_legacy(r)
        for lid in ("EPIC-1", "FEAT-1", "US-1", "US-2"):
            self.assertEqual(len(m.get(lid, [])), 1, "%s migrado para exatamente 1 item com legacy_id: %r" % (lid, m.get(lid)))
        z, p, _ = m["EPIC-1"][0]
        self.assertTrue(z == "state" and p.endswith("epico.json5"), "épico ACTIVE → state/: %s" % p)
        z, p, _ = m["FEAT-1"][0]
        self.assertEqual(z, "state", "feature IN_PROGRESS → state/")
        self.assertRegex(p, r"/sprints/SPR-\d{3}/features/FEA-\d{3}-[^/]+/feature\.json5$", "feature mora numa sprint")
        z, p, _ = m["US-1"][0]
        self.assertEqual(z, "archive", "story DONE → task fechada em archive/")
        self.assertRegex(os.path.basename(p), r"-US-", "story US vira task do tipo US")
        z, p, _ = m["US-2"][0]
        self.assertIn(z, ("state", "backlog"), "story aberta → state/ ou backlog/")
        self.assertRegex(os.path.basename(p), r"-US-")
        self.assert_validate(r, "pós-migração")
        # idempotente
        snap, ev1 = snapshot(r), events_bytes(r)
        self.ok(r, "migrate", "state-tree", msg="2ª migração (idempotente)")
        self.assertEqual(snapshot(r), snap, "migração idempotente: árvore igual")
        self.assertEqual(events_bytes(r), ev1, "migração idempotente: nenhum evento novo")

    def test_migrate_1_alvo_real_da_iteration_4(self):
        src = os.path.join(ITER4_TARGET, ".specialists", "state")
        if not os.path.isfile(os.path.join(src, "board.json5")):
            self.skipTest("alvo de iteration-4 ausente: %s" % src)
        r, ev_old = self._legacy(src)
        self.ok(r, "migrate", "state-tree")
        self.assertTrue(events_bytes(r).startswith(ev_old))
        self.assert_validate(r, "iteration-4 migrado")

    def test_upgrade_cataloga_a_migracao_state_tree(self):
        from upgrade import version as V
        self.assertIn("state-tree", V.KINDS, "upgrade conhece o kind state-tree")
        self.assertNotIn("state-tree", V.RESERVED_KINDS, "state-tree implementado (não reservado)")
        cat = json5io.read(V.MIGRATIONS_FILE)
        kinds = [a.get("kind") for mg in cat.get("migrations") or [] for a in mg.get("actions") or []]
        self.assertIn("state-tree", kinds, "references/migrations.json5 tem uma migração com action kind state-tree")
        with open(os.path.join(SCRIPTS, "upgrade", "core.py"), encoding="utf-8") as f:
            src = f.read()
        m = re.search(r"^ORDER = \(([^)]*)\)", src, re.M)
        self.assertTrue(m and '"state-tree"' in m.group(1), "core.ORDER inclui state-tree")


# ====================================================================== CHORE (manutenção técnica)
class TestChore(Base):
    """CHORE: task de manutenção técnica sem valor de usuário (sem como/quero/para). DoR = --motivo + --verify-cmd;
    close exige o verify-cmd verde NO MOMENTO do close."""

    def _sprint(self):
        r = self.repo()
        return r, self.sprint(r)

    def _check(self, r, tid, expect, word=None):
        before = snapshot(r)
        code, out, err = cs(r, "check", tid)
        self.assertEqual(code, expect, "`cs-state check %s` deveria sair %d: %s%s" % (tid, expect, out, err))
        if word:
            self.assertIn(word, (out + err).lower(), "check lista o que falta: %s" % (out + err))
        self.assert_unchanged(r, before, "check é só leitura")

    def test_chore_sem_como_quero_para_com_motivo_comeca(self):
        r, sid = self._sprint()
        tid, p = self.task(r, ["--sprint", sid], "CHORE", "Subir lib requests")
        self.assertEqual(p, "%s/state/sprints/SPR-001/tasks/01-CHORE-subir-lib-requests.json5" % SD)
        d = read_item(os.path.join(r, p))
        self.assertTrue(d.get("motivo"), "CHORE grava o motivo")
        self._check(r, tid, 0)
        self.ok(r, "start", tid, msg="CHORE com motivo e verify-cmd")

    def test_chore_sem_motivo_nao_comeca(self):
        r, sid = self._sprint()
        tid, p = self.task(r, ["--sprint", sid], "CHORE", "Ajustar timeout", motivo=None)
        self._check(r, tid, 1, "motivo")
        before = snapshot(r)
        self.refused(r, "start", tid, msg="CHORE sem motivo")
        self.assert_unchanged(r, before, "start de CHORE sem motivo")

    def test_chore_sem_verify_cmd_nao_comeca(self):
        r, sid = self._sprint()
        tid, p = self.task(r, ["--sprint", sid], "CHORE", "Ajustar timeout", verify=None)
        self._check(r, tid, 1, "verify")
        self.refused(r, "start", tid, msg="CHORE sem verify-cmd")

    def test_close_de_chore_exige_verify_cmd_verde(self):
        r, sid = self._sprint()
        tid, p = self.task(r, ["--sprint", sid], "CHORE", "Gerar desconto", verify=ACEITE)
        self.run_task(r, tid, p, close=False)          # discount.py escrito → aceite verde → verify/accept passam
        os.remove(os.path.join(r, "src/billing/discount.py"))   # regrediu depois do accept
        before = snapshot(r)
        txt = self.refused(r, "close", tid, "--summary", "x", msg="close de CHORE com verify-cmd vermelho")
        self.assertIn("accept.test_accept", txt, "a recusa cita o verify-cmd que está vermelho")
        self.assert_unchanged(r, before, "close de CHORE recusado")
        write(r, "src/billing/discount.py")
        self.ok(r, "close", tid, "--summary", "desconto gerado")
        self.assertTrue(mentions(r, os.path.basename(p), "archive"), "CHORE fechado vai para archive/")


# ====================================================================== automação mecânica: --dry-run, check, --json
DRY_KEYS = ("ids", "criar", "mover", "eventos")


class TestDryRun(Base):
    """Toda mudança de estado aceita --dry-run: JSON {ids, criar, mover:[{id,de,para}], eventos} e NADA escrito."""

    def dry(self, root, *args):
        before = snapshot(root)
        code, out, err = cs(root, *(list(args) + ["--dry-run"]))
        self.assertEqual(code, 0, "`cs-state %s --dry-run` (exit %d): %s%s" % (" ".join(args), code, out, err))
        try:
            d = json.loads(out)
        except ValueError:
            self.fail("--dry-run imprime JSON puro no stdout: %r" % out[:400])
        for k in DRY_KEYS:
            self.assertIsInstance(d.get(k), list, "--dry-run: chave `%s` (lista) ausente: %r" % (k, d))
        self.assertTrue(d["eventos"], "--dry-run lista os eventos que gravaria")
        for m in d["mover"]:
            self.assertTrue(isinstance(m, dict) and m.get("de") and m.get("para"), "mover: {id, de, para}: %r" % m)
        self.assert_unchanged(root, before, "--dry-run de `%s`" % " ".join(args))
        return d

    def assert_moved_as_announced(self, root, d):
        files = tree_paths(root)
        for m in d["mover"]:
            self.assertTrue(any(f == m["para"] or f.startswith(m["para"].rstrip("/") + "/") for f in files),
                            "o comando real levou ao destino anunciado %s" % m["para"])
            self.assertFalse(any(f == m["de"] or f.startswith(m["de"].rstrip("/") + "/") for f in files),
                             "a origem anunciada %s ficou vazia" % m["de"])

    def test_dry_run_dos_new_bate_com_o_real(self):
        r = self.repo()
        cases = [
            ["epico", "--title", "Checkout v2", "--objetivo", "pagar com pix"],
            ["sprint", "--meta", "entregar pix"],
        ]
        for args in cases:
            d = self.dry(r, "new", *args)
            got = self.new(r, *args)
            self.assertEqual(d["ids"], [g[0] for g in got], "ids anunciados = criados (%s)" % args[0])
            self.assertEqual(set(d["criar"]), {g[1] for g in got}, "caminhos anunciados = criados (%s)" % args[0])
        self.ok(r, "start", "SPR-001")
        fargs = ["feature", "--title", "Pagamento Pix", "--sprint", "SPR-001", "--aceite", ACEITE]
        d = self.dry(r, "new", *fargs)
        got = self.new(r, *fargs)
        self.assertEqual(d["ids"], [g[0] for g in got])
        self.ok(r, "start", got[0][0])
        targs = ["task", "--tipo", "US", "--agent", "dev-billing", "--title", "Confirmar pagamento", "--feature",
                 "FEA-001", "--allowed-path", "src/billing/discount.py", "--verify-cmd", VERIFY, "--como", "c",
                 "--quero", "q", "--para", "p", "--criterio", CRIT]
        d = self.dry(r, "new", *targs)
        got = self.new(r, *targs)
        self.assertEqual((d["ids"], set(d["criar"])), ([g[0] for g in got], {g[1] for g in got}))
        sargs = ["story", "--tipo", "US", "--title", "Pagar com Pix", "--feature", "FEA-001", "--agents",
                 "dev-billing,qa", "--como", "c", "--quero", "q", "--para", "p", "--criterio", CRIT, "--verify-cmd", VERIFY]
        d = self.dry(r, "new", *sargs)
        got = self.new(r, *sargs)
        self.assertEqual(sorted(d["ids"]), sorted(g[0] for g in got), "story composta: story + uma task por agente")
        self.assertTrue({g[1] for g in got} <= set(d["criar"]))

    def test_dry_run_start_park_move_promote(self):
        r = self.repo()
        sid = self.sprint(r)
        fid = self.feature(r, sid, start=False)
        d = self.dry(r, "start", fid)
        self.ok(r, "start", fid)
        self.assert_moved_as_announced(r, d)
        d = self.dry(r, "park", fid, "--reason", "prioridade")
        self.ok(r, "park", fid, "--reason", "prioridade")
        self.assert_moved_as_announced(r, d)
        self.ok(r, "start", fid)
        ta, pa = self.task(r, ["--avulsa"], "US", "Ajusta timeout")
        d = self.dry(r, "move", ta, "--to", sid)
        self.assertEqual([m["de"] for m in d["mover"]], [pa])
        self.ok(r, "move", ta, "--to", sid)
        self.assert_moved_as_announced(r, d)
        t1, p1 = self.task(r, ["--feature", fid], "US", "Pagar com Pix", agent="dev-users", paths=("src/users/model.py",))
        d = self.dry(r, "promote", t1)
        self.ok(r, "promote", t1)
        self.assert_moved_as_announced(r, d)

    def test_dry_run_close_e_reopen(self):
        r = self.repo()
        ta, pa = self.task(r, ["--avulsa"], "US", "Ajusta timeout")
        self.run_task(r, ta, pa, close=False)
        d = self.dry(r, "close", ta, "--summary", "ok")
        self.assertEqual([m["de"] for m in d["mover"]], [pa])
        self.ok(r, "close", ta, "--summary", "ok")
        self.assert_moved_as_announced(r, d)
        d = self.dry(r, "reopen", ta, "--reason", "regrediu")
        self.ok(r, "reopen", ta, "--reason", "regrediu")
        self.assert_moved_as_announced(r, d)

    def test_dry_run_nao_contorna_guarda(self):
        r = self.repo()
        sid = self.sprint(r)
        fid = self.feature(r, sid)
        t1, _ = self.task(r, ["--feature", fid], "US", "Confirmar pagamento")
        before = snapshot(r)
        code, out, err = cs(r, "close", fid, "--summary", "x", "--dry-run")
        self.assertEqual(code, 1, "--dry-run de uma operação recusada também recusa (exit 1): %s%s" % (out, err))
        self.assertIn(t1, out + err)
        self.assert_unchanged(r, before, "dry-run recusado")


class TestCheckDoR(Base):
    """`cs-state check <id>`: DoR/pré-condições por script — exit 0 pronto, exit 1 listando o que falta; não escreve."""

    def check(self, root, tid, expect, words=()):
        before = snapshot(root)
        code, out, err = cs(root, "check", tid)
        self.assertEqual(code, expect, "`cs-state check %s` deveria sair %d: %s%s" % (tid, expect, out, err))
        for w in words:
            self.assertIn(w, (out + err).lower(), "check lista o que falta (%s): %s" % (w, out + err))
        self.assert_unchanged(root, before, "check é só leitura")

    def test_check_por_tipo(self):
        r = self.repo()
        sid = self.sprint(r)
        fid = self.feature(r, sid)
        us0, _ = self.task(r, ["--feature", fid], "US", "Sem criterio", crit=False)
        self.check(r, us0, 1, ("crit",))
        us1, _ = self.task(r, ["--feature", fid], "US", "Com criterio")
        self.check(r, us1, 0)
        b0, _ = self.task(r, ["--feature", fid], "BUG", "Nao reproduz", repro=REPRO_GREEN)
        self.check(r, b0, 1, ("passa",))
        b1, _ = self.task(r, ["--feature", fid], "BUG", "Reproduz", repro=REPRO_RED)
        self.check(r, b1, 0)
        f0, _ = self.task(r, ["--feature", fid], "FIX", "Sem alvo", fixes=None)
        self.check(r, f0, 1, ("fixes",))
        f1, _ = self.task(r, ["--feature", fid], "FIX", "Corrige", fixes=b1)
        self.check(r, f1, 0)
        self.ok(r, "start", us1, msg="check 0 ⇒ start passa (mesma regra)")

    def test_check_de_feature_exige_aceite_vermelho(self):
        r = self.repo()
        sid = self.sprint(r)
        fid = self.feature(r, sid, start=False)
        self.check(r, fid, 0)
        write(r, "src/billing/discount.py")  # aceite já passa → DoR de feature (teste vermelho) falha
        self.check(r, fid, 1, ("aceite",))


class TestLeituraCompacta(Base):
    def test_board_e_tree_em_json(self):
        r = self.repo()
        sid = self.sprint(r)
        fid = self.feature(r, sid)
        t1, p1 = self.task(r, ["--feature", fid], "US", "Confirmar pagamento")
        ta, pa = self.task(r, ["--avulsa"], "US", "Ajusta timeout", agent="dev-users", paths=("src/users/model.py",))
        for cmd in ("board", "tree"):
            out = self.ok(r, cmd, "--json")
            try:
                d = json.loads(out)
            except ValueError:
                self.fail("`cs-state %s --json` imprime JSON puro: %r" % (cmd, out[:300]))
            nodes = {x.get("id"): x for x in walk_dicts(d) if isinstance(x.get("id"), str)}
            for iid in (sid, fid, t1, ta):
                self.assertIn(iid, nodes, "%s --json lista %s" % (cmd, iid))
            if cmd == "tree":
                self.assertEqual(nodes[t1].get("path"), p1, "tree --json traz o caminho de cada item")
                self.assertEqual(nodes[ta].get("path"), pa)


# ====================================================================== skills emitidas (/new-*, /close-*, ...)
SKILLS_CLI = {
    "new-epic": "cs-state new epico", "new-sprint": "cs-state new sprint", "new-feature": "cs-state new feature",
    "new-task": "cs-state new task", "new-story": "cs-state new story",
    "close-task": "cs-state close", "close-feature": "cs-state close", "close-sprint": "cs-state close",
    "close-epic": "cs-state close", "close-story": "cs-state close",
    "reopen": "cs-state reopen", "park": "cs-state park", "move": "cs-state move", "board": "cs-state board",
}
CONSULTA = ("board",)
CRIACAO = ("new-epic", "new-sprint", "new-feature", "new-task", "new-story")
MUDANCA = ("close-task", "close-feature", "close-sprint", "close-epic", "close-story", "reopen", "park", "move")
MAX_SKILL_BODY_LINES = 40
# padrões que denunciam lógica que o motor já faz (montar caminho, mover à mão, calcular id)
HAND_LOGIC = (
    (r"(?<![\w-])(backlog|state|archive)/", "caminho de zona montado no texto"),
    (r"(?m)^\s*(mv|cp|mkdir|rm|touch)\s", "mover/criar arquivo à mão"),
    (r"\bnnn?\b|<nn>|próximo número|proximo numero", "calcular id/nn"),
)
DOR_FLAGS = {
    "new-epic": ("--objetivo",), "new-sprint": ("--meta",), "new-feature": ("--aceite",),
    "new-task": ("--como", "--quero", "--para", "--criterio", "--reproducao", "--fixes", "--teste"),
    "new-story": ("--como", "--quero", "--para", "--criterio", "--reproducao", "--fixes", "--teste"),
}


def _emit_fixture_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("emit_tests_fixture", os.path.join(SCRIPTS, "emit", "tests", "fixture.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def emit_target():
    """Alvo temporário com os dados do fixture dos testes de emit, gravados em SD/; roda `cs.py emit` (claude-code)."""
    F = _emit_fixture_module()
    root = os.path.realpath(tempfile.mkdtemp(prefix="cs-arvore-emit-"))
    for p in F.PRODUCT:
        write(root, p, "x = 1\n")
    write(root, os.path.join(SD, "team.json5"), json.dumps(F.team(), ensure_ascii=False))
    for n, d in list(F.facts().items()) + list(F.scan_facts().items()):
        write(root, os.path.join(SD, "facts", n if n.endswith(".json5") else n + "5"), json.dumps(d, ensure_ascii=False))
    for n, d in F.knowledge_maps().items():
        write(root, os.path.join(SD, "knowledge", n), json.dumps(d, ensure_ascii=False))
    code, out, err = _run([sys.executable, os.path.join(SCRIPTS, "cs.py"), "--target", root, "emit", "--platforms",
                           "claude-code", "--allow-outside"], root)
    return root, code, out + err


def frontmatter(text):
    """→ ({chave: valor sem aspas}, corpo) de um SKILL.md com frontmatter `---`."""
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "\t", "-")):
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm, m.group(2)


class TestSkillsEmitidas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, cls.code, cls.log = emit_target()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def skill(self, name):
        self.assertEqual(self.code, 0, "cs.py emit deveria passar no alvo temporário: %s" % self.log[-1500:])
        p = os.path.join(self.root, ".claude", "skills", name, "SKILL.md")
        self.assertTrue(os.path.isfile(p), "emit gera .claude/skills/%s/SKILL.md" % name)
        with open(p, encoding="utf-8") as f:
            return frontmatter(f.read())

    def test_emite_as_14_skills_e_cada_uma_cita_o_subcomando_real(self):
        for name, cli in sorted(SKILLS_CLI.items()):
            fm, body = self.skill(name)
            self.assertEqual(fm.get("name"), name)
            self.assertIn(cli, body + fm.get("allowed-tools", ""), "/%s chama `%s`" % (name, cli))

    def test_consulta_e_model_invocable(self):
        for name in CONSULTA:
            fm, _ = self.skill(name)
            self.assertNotEqual(fm.get("disable-model-invocation", "false").lower(), "true",
                                "/%s é consulta: o modelo pode invocar" % name)

    def test_criacao_e_model_invocable_e_mostra_antes_via_dry_run(self):
        for name in CRIACAO:
            fm, body = self.skill(name)
            self.assertNotEqual(fm.get("disable-model-invocation", "false").lower(), "true",
                                "/%s é criação: o modelo pode invocar" % name)
            lines = body.splitlines()
            cli = SKILLS_CLI[name]
            dry = [i for i, l in enumerate(lines) if cli in l and "--dry-run" in l]
            real = [i for i, l in enumerate(lines) if cli in l and "--dry-run" not in l]
            self.assertTrue(dry, "/%s mostra antes chamando `%s ... --dry-run` (não em prosa)" % (name, cli))
            self.assertTrue(real and min(dry) < min(real), "/%s: o --dry-run vem ANTES do comando real" % name)

    def test_criacao_decide_dor_pelo_script_check(self):
        for name in ("new-task", "new-story", "new-feature"):
            _, body = self.skill(name)
            self.assertIn("cs-state check", body, "/%s delega o DoR a `cs-state check` (decisão do script)" % name)

    def test_new_task_cita_chore_e_seu_dor(self):
        _, body = self.skill("new-task")
        for w in ("CHORE", "--motivo", "--verify-cmd"):
            self.assertIn(w, body, "/new-task cita o tipo CHORE e o DoR dele (%s)" % w)

    def test_skills_finas_sem_logica_do_motor(self):
        for name, cli in sorted(SKILLS_CLI.items()):
            _, body = self.skill(name)
            n = len(body.splitlines())
            self.assertLessEqual(n, MAX_SKILL_BODY_LINES, "/%s: corpo com %d linhas (máx %d)" % (name, n, MAX_SKILL_BODY_LINES))
            self.assertIn(cli, body, "/%s cita o comando do motor no corpo" % name)
            for pat, why in HAND_LOGIC:
                m = re.search(pat, body)
                self.assertIsNone(m, "/%s contém lógica do motor (%s): %r" % (name, why, m and m.group(0)))

    def test_mudanca_de_estado_nao_e_model_invocable(self):
        for name in MUDANCA:
            fm, _ = self.skill(name)
            self.assertEqual(fm.get("disable-model-invocation", "").lower(), "true",
                             "/%s muda estado: disable-model-invocation: true" % name)

    def test_skills_de_criacao_carregam_o_dor_do_tipo(self):
        for name, flags in sorted(DOR_FLAGS.items()):
            _, body = self.skill(name)
            for fl in flags:
                self.assertIn(fl, body, "/%s carrega o DoR: cita %s" % (name, fl))
        for name in ("new-task", "new-story"):
            _, body = self.skill(name)
            low = body.lower()
            for tipo, words in (("US", ("como", "quero", "para", "critério")), ("BUG", ("reprodução",)),
                                ("FIX", ("fixes",))):
                self.assertIn(tipo, body, "/%s explica o tipo %s" % (name, tipo))
                for w in words:
                    self.assertIn(w, low, "/%s: DoR de %s cita '%s'" % (name, tipo, w))


if __name__ == "__main__":
    unittest.main()
