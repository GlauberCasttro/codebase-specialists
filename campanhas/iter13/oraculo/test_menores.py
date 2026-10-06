"""ORÁCULO campanha-iter13 — pendências menores da skill codebase-specialists.

Três requisitos (contrato e interfaces FIXADAS em ESPEC.md, mesma pasta). Quem implementa NÃO edita este arquivo.

  R1  EMIT multiplataforma das 23 skills finas (14 de estado `cs-state` + 9 do mandato `cs-auto`) para Cursor,
      GitHub Copilot e Codex, com a política de invocação mantida e coberta pelo `emit validate` (G7).
  R2  `reroute` e `retry` do cs-state numa task da ÁRVORE atualizam `agent`/`route` no ARQUIVO da task e o evento
      registra o antigo (`de`) e o novo (`para`); `cs-state validate` continua verde.
  R3  Alvo novo (`cs.py init` + `cs.py harness install`, o caminho SWARM-DIR-1) nasce com o estado em ÁRVORE
      (backlog/ state/ archive/, sem board plano legado) e `cs-state tree` funciona sem `migrate`.

Comportamento observável: emissor real (`emit.cli.main`, em processo, igual a scripts/emit/tests), CLI real do
motor (`engine/state.py`) e `cs.py` em subprocesso, alvos em diretórios temporários. Nada de mock.
Skill: $CS_SKILL_DIR, senão ~/.claude/skills/codebase-specialists. Python 3.9+, unittest puro.
Rodar (de dentro desta pasta):  python3 -m unittest -v test_menores   (e com /usr/bin/python3)
"""
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.realpath(os.environ.get("CS_SKILL_DIR") or os.path.expanduser("~/.claude/skills/codebase-specialists"))
SCRIPTS = os.path.join(SKILL, "scripts")
CS_PY = os.path.join(SCRIPTS, "cs.py")
ENGINE = os.path.join(SCRIPTS, "harness", "engine")
STATE_PY = os.path.join(ENGINE, "state.py")
EMIT_TESTS = os.path.join(SCRIPTS, "emit", "tests")

for _p in (SCRIPTS, EMIT_TESTS, ENGINE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from cslib.paths import STATE_DIR as _SD  # noqa: E402
except ImportError:
    _SD = ".swarm"
SD = os.path.basename(str(_SD).rstrip("/")) or ".swarm"

import fixture as emit_fixture  # noqa: E402  (team sintético dos testes do emissor)
from cslib import json5io  # noqa: E402
from emit import cli as emit_cli  # noqa: E402
from emit.common import GEN_TOKEN, FrontmatterError, parse_frontmatter  # noqa: E402

# ====================================================================== R1 — interfaces fixadas
# (nome, só-humano?, binário, subcomando principal que o corpo tem de citar como `.swarm/bin/<bin> <sub>`)
SKILLS = (
    ("board", False, "cs-state", "board"),
    ("new-epic", False, "cs-state", "new epico"),
    ("new-sprint", False, "cs-state", "new sprint"),
    ("new-feature", False, "cs-state", "new feature"),
    ("new-task", False, "cs-state", "new task"),
    ("new-story", False, "cs-state", "new story"),
    ("close-task", True, "cs-state", "close"),
    ("close-feature", True, "cs-state", "close"),
    ("close-sprint", True, "cs-state", "close"),
    ("close-epic", True, "cs-state", "close"),
    ("close-story", True, "cs-state", "close"),
    ("reopen", True, "cs-state", "reopen"),
    ("park", True, "cs-state", "park"),
    ("move", True, "cs-state", "move"),
    ("auto-status", False, "cs-auto", "status"),
    ("auto-plan", False, "cs-auto", "plan"),
    ("auto-tick", False, "cs-auto", "tick"),
    ("auto-report", False, "cs-auto", "report"),
    ("auto-approve", True, "cs-auto", "approve"),
    ("auto-amend", True, "cs-auto", "amend"),
    ("auto-resolve", True, "cs-auto", "resolve"),
    ("auto-stop", True, "cs-auto", "stop"),
    ("auto-abort", True, "cs-auto", "abort"),
)
# Caminho de saída por plataforma (FIXADO — ver ESPEC.md §2.1).
OUT = {
    "claude-code": ".claude/skills/{n}/SKILL.md",   # já existe (regressão)
    "cursor": ".cursor/skills/{n}/SKILL.md",
    "copilot": ".github/skills/{n}/SKILL.md",
    "codex": ".agents/skills/{n}/SKILL.md",
}
NEW_PLATFORMS = ("cursor", "copilot", "codex")
DMI_PLATFORMS = ("claude-code", "cursor", "copilot")  # têm `disable-model-invocation` no frontmatter de skill
HUMAN_ONLY_TEXT = "só o humano executa"              # Codex (sem o campo): o corpo diz isso, explicitamente
ALL = "claude-code,cursor,copilot,codex"


def emit_run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = emit_cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def cited_commands(body, binary):
    """Trechos em crase que começam por `.swarm/bin/<binary> `."""
    return [m.group(1) for m in re.finditer(r"`(\.swarm/bin/%s [^`]+)`" % re.escape(binary), body)]


class EmitBase(unittest.TestCase):
    maxDiff = None
    platforms = ALL

    def setUp(self):
        self.root = emit_fixture.make_repo()
        code, out, err = emit_run("--target", self.root, "--platforms", self.platforms, "--allow-outside")
        self.assertEqual(code, 0, "emit deveria passar: %s%s" % (out, err))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def p(self, rel):
        return os.path.join(self.root, rel)

    def skill_file(self, platform, name):
        rel = OUT[platform].format(n=name)
        path = self.p(rel)
        self.assertTrue(os.path.isfile(path), "%s: skill %s não emitida em %s" % (platform, name, rel))
        return rel, read(path)

    def fm_body(self, rel, text):
        try:
            return parse_frontmatter(text)
        except FrontmatterError as exc:
            self.fail("%s: frontmatter inválido (%s)" % (rel, exc))

    def validate(self, platforms=ALL):
        return emit_run("validate", "--target", self.root, "--platforms", platforms)


class TestR1EmitSkillsMultiplataforma(EmitBase):
    def _check_platform(self, platform):
        for name, human, binary, sub in SKILLS:
            rel, text = self.skill_file(platform, name)
            self.assertIn(GEN_TOKEN, text, "%s sem marcador de gerado (poda/validate dependem dele)" % rel)
            fm, body = self.fm_body(rel, text)
            self.assertEqual(fm.get("name"), name, "%s: name deve ser o nome do diretório" % rel)
            d = fm.get("description")
            self.assertTrue(isinstance(d, str) and d.strip(), "%s: description obrigatória" % rel)
            cmd = ".swarm/bin/%s %s" % (binary, sub)
            self.assertIn(cmd, body, "%s deve citar o comando real `%s`" % (rel, cmd))
            dmi = fm.get("disable-model-invocation")
            if platform in DMI_PLATFORMS:
                if human:
                    self.assertIs(dmi, True, "%s muda estado/é portão humano: disable-model-invocation: true" % rel)
                else:
                    self.assertIsNot(dmi, True, "%s é consulta/criação: tem de ser invocável pelo modelo" % rel)
            else:
                low = body.casefold()
                if human:
                    self.assertIn(HUMAN_ONLY_TEXT, low, "%s (sem disable-model-invocation na plataforma) deve dizer "
                                  "explicitamente '%s'" % (rel, HUMAN_ONLY_TEXT))
                else:
                    self.assertNotIn(HUMAN_ONLY_TEXT, low, "%s é invocável pelo modelo: não pode dizer '%s'" % (
                        rel, HUMAN_ONLY_TEXT))

    def test_cursor_23_skills_com_politica_e_comando_real(self):
        self._check_platform("cursor")

    def test_copilot_23_skills_com_politica_e_comando_real(self):
        self._check_platform("copilot")

    def test_codex_23_skills_com_texto_so_humano_e_comando_real(self):
        self._check_platform("codex")

    def test_claude_code_continua_igual(self):
        self._check_platform("claude-code")

    def test_guard_continua_bloqueando_os_comandos_humanos_citados(self):
        """O texto não é a única barreira: o comando `cs-auto` humano que cada skill não-Claude cita continua sendo
        reconhecido como ato HUMANO pelo guard (decide_bash → auto.human_act_in_command)."""
        import auto  # noqa: E402  (motor da skill)
        for platform in NEW_PLATFORMS:
            for name, human, binary, sub in SKILLS:
                if binary != "cs-auto" or not human:
                    continue
                rel, text = self.skill_file(platform, name)
                cmds = [c for c in cited_commands(text, "cs-auto") if c.split()[1:2] == [sub]]
                self.assertTrue(cmds, "%s não cita `.swarm/bin/cs-auto %s ...`" % (rel, sub))
                for c in cmds:
                    self.assertTrue(auto.human_act_in_command(c), "guard deixaria passar %r (%s)" % (c, rel))


class TestR1CadaPlataformaSozinha(unittest.TestCase):
    def test_emit_so_da_plataforma_gera_as_23_sem_depender_do_claude(self):
        for platform in NEW_PLATFORMS:
            root = emit_fixture.make_repo()
            try:
                code, out, err = emit_run("--target", root, "--platforms", platform, "--allow-outside")
                self.assertEqual(code, 0, "%s: %s%s" % (platform, out, err))
                for name, _, _, _ in SKILLS:
                    rel = OUT[platform].format(n=name)
                    self.assertTrue(os.path.isfile(os.path.join(root, rel)), "%s sozinho: %s ausente" % (platform, rel))
                self.assertFalse(os.path.isdir(os.path.join(root, ".claude", "skills")),
                                 "%s sozinho não escreve .claude/skills/" % platform)
                code, out, err = emit_run("validate", "--target", root, "--platforms", platform)
                self.assertEqual(code, 0, "%s: validate deveria passar: %s%s" % (platform, out, err))
            finally:
                shutil.rmtree(root, ignore_errors=True)

    def test_dry_run_lista_as_skills_no_bloco_outside(self):
        root = emit_fixture.make_repo()
        try:
            code, out, err = emit_run("--target", root, "--platforms", ALL, "--dry-run")
            self.assertEqual(code, 0, err)
            block = out.split("outside:", 1)[1] if "outside:" in out else ""
            for platform in NEW_PLATFORMS:
                rel = OUT[platform].format(n="close-task")
                self.assertIn(rel, block, "escrita fora de %s/ precisa aparecer no bloco outside: %s" % (SD, rel))
        finally:
            shutil.rmtree(root, ignore_errors=True)


class TestR1ValidateCobre(EmitBase):
    def _fails_naming(self, rel, why):
        code, out, err = self.validate()
        self.assertNotEqual(code, 0, "validate deveria falhar (%s) em %s" % (why, rel))
        self.assertIn(rel, out + err, "validate deve nomear %s (%s): %s%s" % (rel, why, out, err))

    def test_validate_verde_logo_apos_emit(self):
        for platform in NEW_PLATFORMS:
            self.skill_file(platform, "board")  # precondição: as saídas existem
        code, out, err = self.validate()
        self.assertEqual(code, 0, out + err)

    def test_validate_acusa_skill_ausente(self):
        for platform in NEW_PLATFORMS:
            rel, _ = self.skill_file(platform, "close-task")
            os.remove(self.p(rel))
            self._fails_naming(rel, "ausente")
            emit_run("--target", self.root, "--platforms", ALL, "--allow-outside")

    def test_validate_acusa_edicao_que_tira_a_politica(self):
        for platform in NEW_PLATFORMS:
            rel, text = self.skill_file(platform, "auto-approve")
            if platform in DMI_PLATFORMS:
                bad = re.sub(r"(?m)^disable-model-invocation:.*\n", "", text)
            else:
                bad = re.sub(re.escape(HUMAN_ONLY_TEXT), "o modelo pode executar", text, flags=re.I)
            self.assertNotEqual(bad, text, "%s: precondição — a política está no arquivo" % rel)
            with open(self.p(rel), "w", encoding="utf-8") as fh:
                fh.write(bad)
            self._fails_naming(rel, "política de invocação removida à mão")
            emit_run("--target", self.root, "--platforms", ALL, "--allow-outside", "--force")

    def test_validate_acusa_orfao_gerado(self):
        for platform in NEW_PLATFORMS:
            src_rel, text = self.skill_file(platform, "board")
            rel = OUT[platform].format(n="skill-que-saiu")
            os.makedirs(os.path.dirname(self.p(rel)), exist_ok=True)
            with open(self.p(rel), "w", encoding="utf-8") as fh:
                fh.write(re.sub(r"(?m)^name:.*$", "name: skill-que-saiu", text, count=1))
            self._fails_naming(rel, "órfão com marcador de gerado")
            os.remove(self.p(rel))


# ====================================================================== R2 — reroute/retry na árvore
VERIFY = "python3 -m unittest discover -s tests -t ."
ACEITE = "python3 -m unittest accept.test_accept"
CRIT = "AC-1|Dado pedido Quando aplico Então desconta|tests.test_billing"
CREATED_RE = re.compile(r"^criad[oa] (\S+) em (\S+)\s*$", re.M)
SR = "dev-billing-sr"
TEAM = {
    "schema_version": 1,
    "agents": [
        {"name": "dev-billing", "kind": "dev", "territory": ["src/billing/**", "src/shared/**"]},
        {"name": SR, "kind": "dev", "territory": ["src/billing/**", "src/shared/**"]},
        {"name": "qa", "kind": "qa", "territory": ["tests/**"]},
        {"name": "reviewer", "kind": "gate", "territory": []},
    ],
}
RULES = {"facts": [{"id": "rule.global.utf8", "layer": "rules", "claim": "arquivos em UTF-8", "scope": ["**"],
                    "evidence": [{"file": "README.md"}], "confidence": "high", "origin": "mechanical",
                    "fingerprint": "x"}]}
FILES = {
    "README.md": "# demo\n",
    ".gitignore": "__pycache__/\n*.pyc\n",
    "src/billing/total.py": "def total(items):\n    return sum(items)\n",
    "src/shared/util.py": "X = 0\n",
    "tests/__init__.py": "",
    "tests/test_billing.py": "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
    "accept/__init__.py": "",
    "accept/test_accept.py": ("import os, unittest\nclass A(unittest.TestCase):\n    def test_feature(self):\n"
                              "        self.assertTrue(os.path.exists('src/billing/discount.py'))\n"),
}


def _env(extra=None):
    e = dict(os.environ)
    for k in ("CLAUDE_PROJECT_DIR", "CS_ACTOR", "CS_GUARD_OFF", "CS_ROOT", "CS_SKILL_VERSION_FILE",
              "CS_MIGRATIONS_FILE"):
        e.pop(k, None)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    e.update(extra or {})
    return e


def _run(argv, cwd, timeout=600):
    p = subprocess.run(argv, cwd=cwd, env=_env(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def cs_state(root, *args, actor=None):
    argv = [sys.executable, STATE_PY, "--root", root] + (["--actor", actor] if actor else [])
    return _run(argv + list(args), root)


def git(root, *args):
    subprocess.run(["git", "-c", "user.email=o@o", "-c", "user.name=oraculo", "-c", "commit.gpgsign=false"]
                   + list(args), cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def write(root, rel, txt="X = 1\n"):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(txt)


def events(root):
    p = os.path.join(root, SD, "events.jsonl")
    if not os.path.isfile(p):
        return []
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def current_deleg(root, m2_id):
    """Delegação vigente da task M2 (projeção do motor; leitura apenas)."""
    import hcore  # noqa: E402
    b = hcore.load_board(root)
    t = [x for x in b.get("tasks") or [] if x.get("id") == m2_id]
    assert t, "task M2 %s ausente da projeção" % m2_id
    return t[0]["delegations"][-1]


def route_of(r):
    return {"model": (r or {}).get("model"), "band": (r or {}).get("band")}


class TreeBase(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="cs-iter13-"))
        for rel, txt in FILES.items():
            write(self.root, rel, txt)
        write(self.root, os.path.join(SD, "team.json5"), json.dumps(TEAM, ensure_ascii=False, indent=1))
        write(self.root, os.path.join(SD, "facts", "rules.json5"), json.dumps(RULES))
        write(self.root, os.path.join(SD, "facts", "business_rules.json5"), "[]")
        write(self.root, os.path.join(SD, "facts", "glossary.json5"), "[]")
        write(self.root, os.path.join(SD, "knowledge", "collision.json5"), json.dumps({"do_not_parallelize": []}))
        git(self.root, "init", "-q")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "init")
        self.ok("init")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def ok(self, *args, actor=None):
        code, out, err = cs_state(self.root, *args, actor=actor)
        self.assertEqual(code, 0, "`cs-state %s` deveria passar (exit %d): %s%s" % (" ".join(args), code, out, err))
        return out

    def new1(self, *args):
        got = CREATED_RE.findall(self.ok("new", *args))
        self.assertTrue(got, "`new` deve imprimir `criado <ID> em <path>`")
        return got[0]

    def started_task(self, rel_file, title):
        """SPR + FEA ativas, task US de dev-billing iniciada e despachada (manual). → (tid, caminho do arquivo)."""
        if not getattr(self, "_fea", None):
            sid, _ = self.new1("sprint", "--meta", "entregar pix")
            self.ok("start", sid)
            fid, _ = self.new1("feature", "--title", "Pagamento Pix", "--sprint", sid, "--aceite", ACEITE)
            self.ok("start", fid)
            self._fea = fid
        tid, path = self.new1("task", "--tipo", "US", "--agent", "dev-billing", "--title", title, "--feature",
                              self._fea, "--allowed-path", rel_file, "--verify-cmd", VERIFY, "--como", "cliente",
                              "--quero", "pagar", "--para", "concluir a compra", "--criterio", CRIT)
        self.ok("start", tid)
        it = self.item(path)
        self.ok("dispatch", tid, "--manual", "--model", (it.get("route") or {}).get("model") or "sonnet")
        return tid, path

    def item(self, path):
        return json5io.read(os.path.join(self.root, path))

    def appended_since(self, n):
        return events(self.root)[n:]

    def de_para(self, evs, tid):
        """Eventos novos que citam a task e trazem data.de / data.para (dicts)."""
        out = []
        for e in evs:
            d = e.get("data") or {}
            if isinstance(d.get("de"), dict) and isinstance(d.get("para"), dict) and tid in json.dumps(e):
                out.append(d)
        return out

    def assert_validate(self, why):
        code, out, err = cs_state(self.root, "validate")
        self.assertEqual(code, 0, "%s: `cs-state validate` deveria seguir verde: %s%s" % (why, out, err))


class TestR2RerouteRetryNaArvore(TreeBase):
    def test_reroute_atualiza_agent_no_arquivo_e_evento_de_para(self):
        tid, path = self.started_task("src/billing/discount.py", "Confirmar pagamento")
        self.ok("escalate", tid, "--reason", "precisa de alguém sênior em billing")
        n = len(events(self.root))
        self.ok("reroute", tid, "--agent", SR, "--decision", "passa para o sênior")
        it = self.item(path)
        self.assertEqual(it.get("agent"), SR, "arquivo da task na árvore ainda diz o agente antigo depois do reroute")
        dp = [d for d in self.de_para(self.appended_since(n), tid)
              if d["de"].get("agent") == "dev-billing" and d["para"].get("agent") == SR]
        self.assertTrue(dp, "o reroute deve gravar evento com data.de.agent=dev-billing e data.para.agent=%s" % SR)
        board = self.ok("board")
        line = [l for l in board.splitlines() if tid in l]
        self.assertTrue(line and SR in line[0], "board (lido da árvore) deve mostrar o novo agente: %r" % line)
        self.assert_validate("depois do reroute")
        self.ok("ready", tid)
        d = current_deleg(self.root, it.get("m2") or tid)
        self.assertEqual(d.get("agent"), SR)
        self.assertEqual(route_of(self.item(path).get("route")), route_of(d.get("route")),
                         "route do arquivo da task = route da delegação vigente (depois do ready da nova)")
        self.assert_validate("depois do ready da nova delegação")

    def test_retry_atualiza_route_no_arquivo_e_evento_de_para(self):
        rel = "src/billing/other.py"
        tid, path = self.started_task(rel, "Outra coisa")
        old = route_of(self.item(path).get("route"))
        write(self.root, rel)
        self.ok("submit", tid, "--files-changed", rel, "--check", "unittest: OK", "--risk", "nenhum",
                "--handoff-notes", "ok", actor="dev-billing")
        self.ok("verify", tid)
        self.ok("review", tid, "--by", "reviewer", "--verdict", "FAIL", "--findings", "falta o caso de cupom")
        self.ok("reject", tid, "--reason", "falta o caso de cupom")
        n = len(events(self.root))
        self.ok("retry", tid, "--findings", "cubra o caso de cupom")
        it = self.item(path)
        d = current_deleg(self.root, it.get("m2") or tid)
        new = route_of(d.get("route"))
        self.assertNotEqual(new, old, "precondição: retry sobe o tier (regra fixa do roteador)")
        self.assertEqual(route_of(it.get("route")), new, "arquivo da task na árvore com route velho depois do retry")
        dp = [x for x in self.de_para(self.appended_since(n), tid)
              if route_of(x["de"].get("route")) == old and route_of(x["para"].get("route")) == new]
        self.assertTrue(dp, "o retry deve gravar evento com data.de.route=%s e data.para.route=%s" % (old, new))
        self.assert_validate("depois do retry")

    def test_retry_por_decisao_humana_mantem_arquivo_coerente(self):
        tid, path = self.started_task("src/billing/third.py", "Terceira coisa")
        self.ok("escalate", tid, "--reason", "dúvida de regra")
        n = len(events(self.root))
        self.ok("retry", tid, "--decision", "siga com a regra atual")
        it = self.item(path)
        d = current_deleg(self.root, it.get("m2") or tid)
        self.assertEqual(route_of(it.get("route")), route_of(d.get("route")))
        self.assertEqual(it.get("agent"), d.get("agent"))
        self.assertTrue(self.de_para(self.appended_since(n), tid),
                        "retomada (retry --decision) também registra de/para no evento")
        self.assert_validate("depois do retry --decision")


# ====================================================================== R3 — alvo novo nasce em árvore
def cs_py(target, *args):
    return _run([sys.executable, CS_PY, "--target", target] + list(args), target, timeout=900)


def new_target():
    root = os.path.realpath(tempfile.mkdtemp(prefix="cs-iter13-init-"))
    for rel, txt in {"README.md": "# demo\n", "src/app/main.py": "def main():\n    return 1\n",
                     "tests/test_main.py": "import unittest\n", ".gitignore": "__pycache__/\n"}.items():
        write(root, rel, txt)
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "init")
    return root


def fresh_install(root):
    """Mesmo caminho do SWARM-DIR-1 (scripts/harness/tests/test_swarm_dir.py)."""
    return [cs_py(root, "init", "--platforms", "claude-code"),
            cs_py(root, "harness", "install", "--allow-outside", "--git-hook")]


def wrapper(root, *args):
    return _run([os.path.join(root, SD, "bin", "cs-state")] + list(args), root)


def files_named(base, name):
    out = []
    for d, _, fs in os.walk(base):
        if name in fs:
            out.append(os.path.relpath(os.path.join(d, name), base))
    return out


class TestR3InitNasceEmArvore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = new_target()
        cls.res = fresh_install(cls.root)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def setUp(self):
        for rc, out, err in self.res:
            self.assertEqual(rc, 0, out + err)
        self.sd = os.path.join(self.root, SD)

    def test_zonas_da_arvore_e_nenhum_board_plano(self):
        for z in ("backlog", "state", "archive"):
            self.assertTrue(os.path.isdir(os.path.join(self.sd, z)), "zona da árvore ausente: %s/%s" % (SD, z))
        self.assertEqual(files_named(self.sd, "board.json5"), [], "board plano legado criado (nem em backup)")
        self.assertTrue(os.path.isfile(os.path.join(self.sd, "events.jsonl")), "%s/events.jsonl ausente" % SD)

    def test_nasce_em_arvore_sem_migracao(self):
        evs = events(self.root)
        self.assertTrue(evs, "cadeia de eventos vazia")
        first = evs[0]
        self.assertEqual(first.get("type"), "init", first)
        self.assertEqual((first.get("data") or {}).get("layout"), "tree", "1º evento deve ser init com layout tree")
        self.assertFalse([e.get("type") for e in evs if "migra" in str(e.get("type"))],
                         "alvo novo não passa por migrate")

    def test_cs_state_tree_e_board_funcionam_sem_migrate(self):
        code, out, err = wrapper(self.root, "tree")
        self.assertEqual(code, 0, "cs-state tree deveria funcionar sem migrate: %s%s" % (out, err))
        code, out, err = wrapper(self.root, "tree", "--json")
        self.assertEqual(code, 0, out + err)
        json.loads(out)
        code, out, err = wrapper(self.root, "board")
        self.assertEqual(code, 0, out + err)

    def test_arvore_utilizavel_e_validate_verde(self):
        code, out, err = wrapper(self.root, "new", "epico", "--title", "Checkout v2", "--objetivo", "pagar com pix")
        self.assertEqual(code, 0, out + err)
        m = CREATED_RE.search(out)
        self.assertTrue(m and m.group(2).startswith("%s/backlog/" % SD), "épico nasce em backlog/: %r" % out)
        code, out, err = wrapper(self.root, "validate")
        self.assertEqual(code, 0, out + err)

    def test_reinstalar_mantem_arvore(self):
        n = len(events(self.root))
        for rc, out, err in fresh_install(self.root):
            self.assertEqual(rc, 0, out + err)
        self.assertEqual(files_named(self.sd, "board.json5"), [])
        self.assertFalse([e for e in events(self.root)[n:] if "migra" in str(e.get("type"))])
        code, out, err = wrapper(self.root, "tree")
        self.assertEqual(code, 0, out + err)

    def test_selftest_verde(self):
        code, out, err = cs_py(self.root, "harness", "selftest")
        self.assertEqual(code, 0, out + err)


if __name__ == "__main__":
    unittest.main()
