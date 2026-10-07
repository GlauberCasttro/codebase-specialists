"""ORÁCULO campanha-iter18 — skill codebase-specialists: achados de USO REAL (segunda cobaia .NET).

Mapa requisito → teste e critérios em ESPEC.md (mesma pasta). Resumo:

  R1  tree_sha256 do verify ignora artefato IGNORADO pelo git (bin/obj): build de outra task que regrava
      `obj/x.dll` dentro do escopo não trava o accept; arquivo RASTREADO ou não-rastreado-não-ignorado que muda
      depois do verify continua trancando (tree_unchanged).
  R2  sem impasse em VERIFIED/REVIEWED: `cs-state reverify --task` quando a árvore mudou depois do verify;
      files_changed iguais → reviews preservadas; files_changed mudaram → nova review; árvore intacta → recusado.
  R3  cartão emitido de gate manda registrar o veredito (`cs-state review --task … --verdict`) e diz que
      só-leitura = não editar arquivos (review/abstain são dele).
  R4  orchestrator (template + emitidos) proíbe ditar o veredito ao gate, manda redespachar revisão independente
      com o mesmo id `.dN` e não pedir ao usuário para carimbar.
  R5  pre-commit (`guard.py check-diff --staged`): allowed_paths de task aberta com delegação ≠ ACCEPTED barrados
      (DISPATCHED, RETURNED, VERIFIED, REVIEWED); ACCEPTED aberta libera (U5 da iter16); `.swarm/**` liberado.
  R6  bashscan: `git check-ignore`, `git ls-remote`, `git count-objects` = somente leitura.
  R7  allowed_paths = território inteiro do agente (ou glob que o contém) é recusado no DoR/despacho com dica de
      `cs-state amend --field allowed_paths`; o gerador da árvore (story sem --allowed-path) não produz task
      iniciável com o território inteiro.
  R8  versão 0.10.0 (VERSION, migrations.json5, README, docs/09-upgrade.md).

Comportamento observável: CLI real (`scripts/harness/engine/state.py` = cs-state, `guard.py`) em subprocesso,
emissor real (`scripts/emit`), repos git temporários. Skill sob teste: $CS_SKILL_DIR, senão a raiz deste projeto.
Python 3.9+, unittest puro. Rodar (desta pasta): python3 -m unittest -v test_iter18
"""
import contextlib
import importlib.util
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
SKILL = os.path.realpath(os.environ.get("CS_SKILL_DIR") or os.path.join(HERE, "..", "..", ".."))
SCRIPTS = os.path.join(SKILL, "scripts")
ENGINE = os.path.join(SCRIPTS, "harness", "engine")
STATE_PY = os.path.join(ENGINE, "state.py")
GUARD_PY = os.path.join(ENGINE, "guard.py")
for _p in (ENGINE, SCRIPTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

GIT_ENV = {"GIT_AUTHOR_NAME": "Ana", "GIT_AUTHOR_EMAIL": "ana@x", "GIT_COMMITTER_NAME": "Ana",
           "GIT_COMMITTER_EMAIL": "ana@x", "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
           "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z"}

TEAM = {"schema_version": 1, "agents": [
    {"name": "dev-billing", "kind": "dev", "territory": ["src/billing/**"]},
    {"name": "dev-users", "kind": "dev", "territory": ["src/users/**"]},
    {"name": "reviewer", "kind": "gate", "territory": []},
    {"name": "security", "kind": "gate", "territory": []}]}
# .gitignore como o de um projeto .NET: bin/ e obj/ são saída de build
FILES = {
    "README.md": "# demo\n", ".gitignore": "__pycache__/\n*.pyc\nbin/\nobj/\n",
    "src/billing/total.py": "def total(items):\n    return sum(items)\n",
    "src/billing/discount/__init__.py": "",
    "src/billing/discount/helper.py": "H = 1\n",          # RASTREADO, no escopo de A, fora dos files_changed
    "src/users/model.py": "AGE = 18\n",
    "tests/__init__.py": "",
    "tests/test_billing.py": "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self):\n"
                             "        self.assertTrue(True)\n",
}
VERIFY = "python3 -m unittest discover -s tests -t ."
CRIT = "AC-1|Dado pedido Quando aplico Então desconta|tests.test_billing"
SCOPE_A = "src/billing/discount/**"                        # diretório estreito (não é o território inteiro)
RATE = "src/billing/discount/rate.py"                     # o que a task A escreve (files_changed)
HELPER = "src/billing/discount/helper.py"
OBJ = "src/billing/discount/obj/x.dll"                    # IGNORADO (obj/), existe no verify
BIN_NEW = "src/billing/discount/bin/Debug/y.dll"          # IGNORADO (bin/), criado depois do verify
NOTES = "src/billing/discount/notes.txt"                  # não rastreado e NÃO ignorado, existe antes do dispatch


def write(root, rel, txt):
    full = os.path.join(root, rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "wb") as fh:
        fh.write(txt.encode("utf-8") if isinstance(txt, str) else txt)


def git(root, *args):
    p = subprocess.run(["git", "-C", root] + list(args), env=dict(os.environ, **GIT_ENV),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise AssertionError("git %s: %s" % (" ".join(args), p.stderr.decode()))
    return p.stdout.decode("utf-8", "replace")


def _env(extra=None):
    e = dict(os.environ)
    for k in ("CLAUDE_PROJECT_DIR", "CS_ACTOR", "CS_GUARD_OFF", "CS_ROOT"):
        e.pop(k, None)
    e.update(extra or {})
    return e


def _run(argv, cwd, env=None, stdin=None):
    p = subprocess.run(argv, cwd=cwd, env=env or _env(), input=stdin, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=300)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def blocks(text):
    """Parágrafos/itens de lista/linhas de tabela com espaços normalizados (frases-chave sem depender de quebra)."""
    out, cur = [], []
    for ln in text.splitlines():
        s = ln.strip()
        new_item = (not s) or re.match(r"^(\d+\.|[-*]|\||#)", s)
        if new_item and cur:
            out.append(" ".join(cur))
            cur = []
        if s:
            cur.append(s)
    if cur:
        out.append(" ".join(cur))
    return out


# ================================================================================================ base: estado em árvore
class TreeRepo(unittest.TestCase):
    """Repo git temporário com estado em árvore (`cs-state init`) e tasks avulsas pela M2 inteira."""

    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="cs-iter18-"))
        for rel, txt in FILES.items():
            write(self.root, rel, txt)
        write(self.root, ".swarm/team.json5", json.dumps(TEAM))
        write(self.root, ".swarm/facts/rules.json5", '{"facts": []}')
        write(self.root, ".swarm/facts/business_rules.json5", "[]")
        write(self.root, ".swarm/facts/glossary.json5", "[]")
        write(self.root, ".swarm/knowledge/collision.json5", '{"do_not_parallelize": []}')
        git(self.root, "init", "-q")
        git(self.root, "add", "--", *(list(FILES) + [".swarm"]))
        git(self.root, "commit", "-q", "-m", "init")
        self.ok("init")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    # ---- CLI
    def cs_state(self, *args, actor=None):
        argv = [sys.executable, STATE_PY, "--root", self.root] + (["--actor", actor] if actor else []) + list(args)
        return _run(argv, self.root)

    def ok(self, *args, actor=None):
        code, out, err = self.cs_state(*args, actor=actor)
        self.assertEqual(code, 0, "cs-state %s → %d\n%s%s" % (" ".join(args), code, out, err))
        return out

    def refused(self, *args, actor=None):
        code, out, err = self.cs_state(*args, actor=actor)
        self.assertNotEqual(code, 0, "cs-state %s deveria ser RECUSADO:\n%s%s" % (" ".join(args), out, err))
        self.assertNotEqual(code, 2, "exit 2 = erro de argparse, não recusa do motor:\n%s%s" % (out, err))
        return out + err

    def new_task(self, agent="dev-billing", paths=(SCOPE_A,), title="Aplicar desconto", expect_ok=True):
        args = ["new", "task", "--tipo", "US", "--agent", agent, "--title", title, "--avulsa",
                "--verify-cmd", VERIFY, "--como", "cliente", "--quero", "desconto", "--para", "pagar menos",
                "--criterio", CRIT]
        for p in paths:
            args += ["--allowed-path", p]
        code, out, err = self.cs_state(*args)
        if not expect_ok:
            return code, out + err, None
        self.assertEqual(code, 0, out + err)
        m = re.search(r"^criad[oa] (\S+) em (\S+)\s*$", out, re.M)
        self.assertTrue(m, out)
        return m.group(1)

    # ---- estado (leitura do board pelo motor da skill sob teste)
    def board(self):
        import hcore
        return hcore.load_board(self.root)

    def m2(self, tid):
        for it in (self.board().get("tree") or {}).values():
            if isinstance(it, dict) and it.get("id") == tid and it.get("m2"):
                return it["m2"]
        return tid

    def task(self, tid):
        mid = self.m2(tid)
        for t in self.board()["tasks"]:
            if t["id"] == mid:
                return t
        raise AssertionError("task %s (M2 %s) não está no board" % (tid, mid))

    def dstate(self, tid):
        return (self.task(tid).get("delegations") or [{}])[-1].get("state")

    def model(self, tid):
        d = (self.task(tid).get("delegations") or [{}])[-1]
        return ((d.get("route") or {}).get("model")) or "sonnet"

    # ---- pipeline
    def to_dispatched(self, tid):
        self.ok("start", tid)
        self.ok("dispatch", tid, "--manual", "--model", self.model(tid))

    def to_returned(self, tid, rel=RATE, txt="RATE = 30\n", agent="dev-billing"):
        write(self.root, rel, txt)
        self.ok("submit", tid, "--files-changed", rel, "--check", "unittest: OK", "--risk", "nenhum",
                "--handoff-notes", "ok", actor=agent)

    def verify(self, tid):
        out = self.ok("verify", tid)
        self.assertEqual(self.dstate(tid), "VERIFIED", out)
        return out

    def review(self, tid, by="reviewer"):
        self.ok("review", tid, "--by", by, "--verdict", "PASS", "--findings", "conferido: teste verde")

    def to_reviewed(self, tid, **kw):
        self.to_dispatched(tid)
        self.to_returned(tid, **kw)
        self.verify(tid)
        self.review(tid)
        self.assertEqual(self.dstate(tid), "REVIEWED")


# ================================================================================================ R1
class TestR1TreeShaIgnoraArtefatoIgnorado(TreeRepo):
    """A (dev-billing) verificada e revisada; a build de outra task (simulada) regrava artefatos IGNORADOS
    (`obj/`, `bin/`) dentro do escopo de A. O accept de A não pode travar por isso."""

    def setUp(self):
        super().setUp()
        write(self.root, OBJ, b"\x00build-1\x00")          # saída de build antiga, presente no verify
        write(self.root, NOTES, "anotação local\n")         # não rastreado, NÃO ignorado, antes do dispatch
        self.assertIn(OBJ, git(self.root, "status", "--porcelain", "--ignored", "--untracked-files=all"))
        self.tid = self.new_task()
        self.to_reviewed(self.tid)

    def test_r1a_artefato_ignorado_regravado_nao_trava_o_accept(self):
        write(self.root, OBJ, b"\x00build-2 (outra task compilou)\x00")
        write(self.root, BIN_NEW, b"\x00novo\x00")
        code, out, err = self.cs_state("accept", self.tid)
        self.assertEqual(code, 0, "accept recusado por artefato IGNORADO pelo git (%s):\n%s%s" % (OBJ, out, err))
        self.assertEqual(self.dstate(self.tid), "ACCEPTED")

    def test_r1b_arquivo_rastreado_mudado_continua_recusando(self):
        write(self.root, HELPER, "H = 2\n")
        self.refused("accept", self.tid)
        self.assertEqual(self.dstate(self.tid), "REVIEWED")

    def test_r1b_files_changed_mudado_continua_recusando(self):
        write(self.root, RATE, "RATE = 31\n")
        self.refused("accept", self.tid)
        self.assertEqual(self.dstate(self.tid), "REVIEWED")

    def test_r1c_nao_rastreado_nao_ignorado_continua_contando(self):
        write(self.root, NOTES, "anotação local mudou\n")
        self.refused("accept", self.tid)
        self.assertEqual(self.dstate(self.tid), "REVIEWED")

    def test_r1_controle_arvore_intacta_aceita(self):
        self.ok("accept", self.tid)
        self.assertEqual(self.dstate(self.tid), "ACCEPTED")


# ================================================================================================ R2
class TestR2ReverifySemImpasse(TreeRepo):
    """VERIFIED/REVIEWED com a árvore mudada depois do verify: hoje nada sai daí (accept recusa, reverify só de
    REJECTED/ESCALATED). Exigido: `cs-state reverify --task` reabre o verify; reviews preservadas se os
    files_changed não mudaram."""

    def setUp(self):
        super().setUp()
        self.tid = self.new_task()
        self.to_reviewed(self.tid)

    def test_r2_accept_recusado_aponta_reverify(self):
        write(self.root, HELPER, "H = 2\n")                 # no escopo, FORA dos files_changed
        msg = self.refused("accept", self.tid)
        self.assertIn("reverify", msg, "a recusa por árvore mudada tem de apontar `cs-state reverify --task`:\n" + msg)

    def test_r2_why_aponta_reverify(self):
        write(self.root, HELPER, "H = 2\n")
        self.refused("accept", self.tid)
        code, out, err = self.cs_state("why", self.tid)
        self.assertIn("reverify", out + err, "`cs-state why` no impasse tem de dar o comando de saída:\n%s%s"
                      % (out, err))

    def test_r2_reverify_preserva_reviews_quando_files_changed_iguais(self):
        write(self.root, HELPER, "H = 2\n")
        self.refused("accept", self.tid)
        attempts = self.task(self.tid)["attempts"]
        self.ok("reverify", "--task", self.tid)
        self.assertEqual(self.task(self.tid)["attempts"], attempts, "reverify não consome tentativa")
        self.ok("accept", self.tid)                       # sem nova review: a review PASS anterior vale
        self.assertEqual(self.dstate(self.tid), "ACCEPTED")

    def test_r2_reverify_de_verified_sem_review(self):
        """Mesmo impasse em VERIFIED (antes da review): reverify sai dele; depois review + accept."""
        t2 = self.new_task(agent="dev-users", paths=("src/users/extra.py",), title="Extra de usuário")
        self.to_dispatched(t2)
        self.to_returned(t2, rel="src/users/extra.py", txt="X = 1\n", agent="dev-users")
        self.verify(t2)
        write(self.root, "src/users/extra.py", "X = 2\n")
        self.refused("accept", t2)
        self.ok("reverify", "--task", t2)
        self.review(t2)
        self.ok("accept", t2)
        self.assertEqual(self.dstate(t2), "ACCEPTED")

    def test_r2_reverify_invalida_reviews_quando_files_changed_mudaram(self):
        write(self.root, RATE, "RATE = 31\n")               # o próprio entregável mudou depois da review
        self.refused("accept", self.tid)
        self.ok("reverify", "--task", self.tid)
        self.refused("accept", self.tid)                    # a review antiga julgou outro conteúdo
        self.assertNotEqual(self.dstate(self.tid), "ACCEPTED")
        self.review(self.tid)
        self.ok("accept", self.tid)
        self.assertEqual(self.dstate(self.tid), "ACCEPTED")

    def test_r2_reverify_com_arvore_intacta_recusado(self):
        """Critério: reverify de VERIFIED/REVIEWED só quando tree_unchanged falharia; árvore intacta → recusado."""
        self.refused("reverify", "--task", self.tid)
        self.assertEqual(self.dstate(self.tid), "REVIEWED")
        self.ok("accept", self.tid)


# ================================================================================================ R3 / R4 — emissão
ALL = "claude-code,cursor,copilot,codex"
GATE_CARDS = (".claude/agents/reviewer.md", ".cursor/agents/reviewer.md", ".github/agents/reviewer.agent.md",
              ".codex/agents/reviewer.toml")
DEV_CARDS = (".claude/agents/dev-billing.md", ".cursor/agents/dev-billing.md", ".github/agents/dev-billing.agent.md",
             ".codex/agents/dev-billing.toml")
ORCH_EMITTED = (".claude/orchestrator.md", ".cursor/rules/cs-orchestrator.mdc", ".github/copilot-instructions.md",
                "AGENTS.md")
ORCH_TEMPLATE = os.path.join(SKILL, "assets", "templates", "orchestrator.md")


class EmitBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        efix = _load("cs_iter18_emit_fixture", os.path.join(SCRIPTS, "emit", "tests", "fixture.py"))
        cls.root = str(efix.make_repo())
        from emit import cli
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = cli.main(["--target", cls.root, "--platforms", ALL, "--allow-outside"])
        if code != 0:
            raise AssertionError("emit falhou (%d): %s" % (code, out.getvalue()[-2000:]))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def text(self, rel):
        return read_text(os.path.join(self.root, rel))


class TestR3CartaoDoGateRegistraVeredito(EmitBase):
    def test_r3_gate_manda_registrar_com_cs_state_review(self):
        for rel in GATE_CARDS:
            t = self.text(rel)
            self.assertIn("cs-state review --task", t, rel)
            hit = [b for b in blocks(t) if "cs-state review --task" in b and "--verdict" in b]
            self.assertTrue(hit, "%s: a instrução `cs-state review --task … --verdict` não está junta" % rel)

    def test_r3_so_leitura_e_nao_editar_e_comandos_de_estado_sao_do_gate(self):
        for rel in GATE_CARDS:
            bs = blocks(self.text(rel))
            ro = [b for b in bs if re.search(r"(?i)s[óo][ -]?leitura|somente[ -]leitura|read-only", b)
                  and re.search(r"(?i)edit|alter", b) and re.search(r"(?i)cs-state|review|veredito", b)]
            self.assertTrue(ro, "%s: falta dizer que só-leitura = não editar arquivos (e não deixar de registrar "
                                "o veredito)" % rel)
            self.assertTrue([b for b in bs if "abstain" in b], "%s: `abstain` (comando de estado do gate) ausente" % rel)

    def test_r3_regressao_enum_de_veredito_continua(self):
        for rel in GATE_CARDS:
            self.assertIn("`PASS` | `FAIL` | `NEEDS_SPECIALIST`", self.text(rel), rel)

    def test_r3_regressao_dev_nao_recebe_comando_de_gate(self):
        for rel in DEV_CARDS:
            self.assertNotIn("cs-state review --task", self.text(rel), rel)


class TestR4OrquestradorNaoDitaVeredito(EmitBase):
    def docs(self):
        out = [("template", read_text(ORCH_TEMPLATE))]
        return out + [(rel, self.text(rel)) for rel in ORCH_EMITTED]

    def test_r4_nunca_dita_o_veredito_ao_gate(self):
        for name, t in self.docs():
            hit = [b for b in blocks(t) if re.search(r"\b[Nn]unca\b", b) and re.search(r"(?i)veredito", b)
                   and re.search(r"(?i)\bgate\b", b) and re.search(r"(?i)dit[ae]|escrev|redij|pass[ea]r?\b|sopr", b)]
            self.assertTrue(hit, "%s: falta \"Nunca\" + ditar/escrever o veredito para o gate" % name)

    def test_r4_redespacha_revisao_independente_com_mesmo_id(self):
        for name, t in self.docs():
            hit = [b for b in blocks(t) if re.search(r"(?i)redespach|despache de novo|novo despacho|despache outra", b)
                   and re.search(r"(?i)revis", b) and re.search(r"\.d(N|n|\d|<n>)\b|mesmo id", b)]
            self.assertTrue(hit, "%s: falta redespachar revisão independente com o mesmo id .dN se o gate não "
                                 "registrar" % name)

    def test_r4_nao_pede_ao_usuario_para_carimbar(self):
        for name, t in self.docs():
            hit = [b for b in blocks(t) if re.search(r"(?i)\bnunca\b|\bnão\b", b)
                   and re.search(r"(?i)usu[áa]rio|humano", b) and re.search(r"(?i)carimb", b)]
            self.assertTrue(hit, "%s: falta não pedir ao usuário/humano para carimbar o veredito" % name)


# ================================================================================================ R5
class TestR5PreCommitSoDepoisDoAceite(TreeRepo):
    """`guard.py check-diff --staged` (o pre-commit instalado): commit do trabalho de task aberta só depois do
    ACCEPTED. Caso real: commit feito com a delegação em REVIEWED passou."""

    TASK_FILE = "src/billing/discount/rate.py"

    def setUp(self):
        super().setUp()
        self.tid = self.new_task(paths=(self.TASK_FILE,))

    def check_staged(self, *rels):
        git(self.root, "add", "--", *rels)
        argv = [sys.executable, GUARD_PY, "check-diff", "--root", self.root, "--staged"]
        return _run(argv, self.root, env=_env())

    def assert_blocked(self, res, rel, why):
        code, out, err = res
        self.assertEqual(code, 1, "%s: pre-commit deveria BARRAR %s (exit %d):\n%s%s" % (why, rel, code, out, err))
        self.assertIn("FORA: %s " % rel, out)

    def assert_free(self, res, why):
        code, out, err = res
        self.assertEqual(code, 0, "%s: pre-commit deveria LIBERAR:\n%s%s" % (why, out, err))

    def test_r5_dispatched_barra(self):
        self.to_dispatched(self.tid)
        write(self.root, self.TASK_FILE, "RATE = 30\n")
        self.assert_blocked(self.check_staged(self.TASK_FILE), self.TASK_FILE, "DISPATCHED")

    def test_r5_returned_barra(self):
        self.to_dispatched(self.tid)
        self.to_returned(self.tid, rel=self.TASK_FILE)
        self.assertEqual(self.dstate(self.tid), "RETURNED")
        self.assert_blocked(self.check_staged(self.TASK_FILE), self.TASK_FILE, "RETURNED")

    def test_r5_verified_barra(self):
        self.to_dispatched(self.tid)
        self.to_returned(self.tid, rel=self.TASK_FILE)
        self.verify(self.tid)
        self.assert_blocked(self.check_staged(self.TASK_FILE), self.TASK_FILE, "VERIFIED")

    def test_r5_reviewed_barra_caso_real(self):
        self.to_reviewed(self.tid, rel=self.TASK_FILE)
        self.assert_blocked(self.check_staged(self.TASK_FILE), self.TASK_FILE, "REVIEWED (caso real)")

    def test_r5_regressao_accepted_aberta_libera(self):
        self.to_reviewed(self.tid, rel=self.TASK_FILE)
        self.ok("accept", self.tid)
        self.assert_free(self.check_staged(self.TASK_FILE), "ACCEPTED com a task aberta (U5 da iter16)")

    def test_r5_regressao_estado_do_harness_liberado(self):
        self.to_reviewed(self.tid, rel=self.TASK_FILE)
        self.assert_free(self.check_staged(".swarm"), "só arquivos de estado do harness (.swarm/**)")

    def test_r5_regressao_fechada_barra(self):
        self.to_reviewed(self.tid, rel=self.TASK_FILE)
        self.ok("accept", self.tid)
        self.ok("close", self.tid, "--summary", "desconto entregue")
        self.assert_blocked(self.check_staged(self.TASK_FILE), self.TASK_FILE, "task fechada")


# ================================================================================================ R6
class TestR6GitSomenteLeitura(TreeRepo):
    READ = ("check-ignore", "ls-remote", "count-objects")

    def test_r6_bashscan_classifica_como_leitura(self):
        import bashscan
        for sub in self.READ:
            self.assertEqual(bashscan.git_effect(sub), "read", sub)

    def test_r6_guard_libera_para_o_orquestrador(self):
        for cmd in ("git check-ignore -v %s" % OBJ, "git ls-remote origin", "git count-objects -v"):
            payload = {"tool_name": "Bash", "tool_use_id": "tu", "tool_input": {"command": cmd}, "cwd": self.root}
            code, out, err = _run([sys.executable, GUARD_PY, "pre-bash"], self.root,
                                  env=_env({"CLAUDE_PROJECT_DIR": self.root}), stdin=json.dumps(payload).encode())
            self.assertEqual(code, 0, "%s bloqueado:\n%s%s" % (cmd, out, err))

    def test_r6_regressao_escrita_continua_fora(self):
        import bashscan
        for sub in ("checkout", "reset", "clean", "gc", "stash"):
            self.assertEqual(bashscan.git_effect(sub), "tree", sub)
        for sub in ("status", "log", "diff", "ls-files"):
            self.assertEqual(bashscan.git_effect(sub), "read", sub)


# ================================================================================================ R7
class TestR7AllowedPathsNaoETerritorioInteiro(TreeRepo):
    def assert_amend_hint(self, msg):
        self.assertIn("amend", msg, "recusa sem dica de `cs-state amend --field allowed_paths`:\n" + msg)
        self.assertIn("allowed_paths", msg, msg)

    def test_r7_territorio_inteiro_recusado_no_start_e_no_check(self):
        tid = self.new_task(paths=("src/billing/**",))
        code, out, err = self.cs_state("check", tid)
        self.assertNotEqual(code, 0, "check deu DoR ok para allowed_paths = território inteiro:\n%s%s" % (out, err))
        self.assert_amend_hint(self.refused("start", tid))
        self.assertIsNone(self.m2_or_none(tid), "start recusado não pode criar a task M2")

    def test_r7_glob_que_contem_o_territorio_recusado(self):
        for glob in ("src/billing/**/*", "src/billing/"):
            code, msg, _ = self.new_task(paths=(glob,), title="t %s" % glob, expect_ok=False)
            if code != 0:
                continue                                # recusado já na criação: também atende
            tid = re.search(r"^criad[oa] (\S+) em", msg, re.M).group(1)
            self.assert_amend_hint(self.refused("start", tid))

    def test_r7_amend_sugerido_destrava(self):
        """A dica é acionável: emendar allowed_paths para um arquivo explícito deixa iniciar."""
        tid = self.new_task(paths=("src/billing/**",))
        self.refused("start", tid)
        self.ok("amend", tid, "--field", "allowed_paths", "--after", '["src/billing/discount/rate.py"]',
                "--reason", "estreitar ao arquivo da mudança")
        self.ok("start", tid)

    def test_r7_regressao_arquivo_explicito_e_diretorio_estreito_passam(self):
        for paths in (("src/billing/total.py",), (SCOPE_A,)):
            tid = self.new_task(paths=paths, title="ok %s" % paths[0])
            self.ok("check", tid)
            self.ok("start", tid)

    def test_r7_gerador_story_sem_allowed_path_nao_inicia_com_territorio(self):
        """`new story` sem --allowed-path (hoje: allowed_paths = território) — simples e composta."""
        self.ok("new", "sprint", "--meta", "m1")
        self.ok("start", "SPR-001")
        out = self.ok("new", "feature", "--title", "Desconto", "--sprint", "SPR-001", "--aceite",
                      "python3 -c 'import sys; sys.exit(1)'")
        fid = re.search(r"^criad[oa] (\S+) em", out, re.M).group(1)
        self.ok("start", fid)
        common = ["--tipo", "US", "--feature", fid, "--verify-cmd", VERIFY, "--como", "c", "--quero", "d",
                  "--para", "p", "--criterio", CRIT]
        made = []
        for agents, title in (("dev-billing", "Simples"), ("dev-billing,dev-users", "Composta")):
            code, out, err = self.cs_state("new", "story", "--title", title, "--agents", agents, *common)
            if code != 0:
                self.assertNotEqual(code, 2, err)
                continue                                # recusado na criação (pede --allowed-path): atende
            made += [m.group(1) for m in re.finditer(r"^criad[oa] (\S+/\d+) em", out, re.M)]
        for tid in made:
            it = [x for x in (self.board().get("tree") or {}).values() if x.get("id") == tid][0]
            terr = [a["territory"] for a in TEAM["agents"] if a["name"] == it.get("agent")][0]
            if sorted(it.get("allowed_paths") or []) != sorted(terr):
                continue                                # gerador já estreitou (ex.: arquivo citado na origem)
            code, o, e = self.cs_state("check", tid)
            self.assertNotEqual(code, 0, "%s gerada com o território inteiro passa no DoR:\n%s%s" % (tid, o, e))
            self.refused("start", tid)

    def test_r7_despacho_legado_recusa_territorio_inteiro(self):
        """Fluxo M1 (board plano: add task --ready) — o mesmo DoR do brief (brief_valid)."""
        fx = _load("cs_iter18_harness_fixture", os.path.join(SCRIPTS, "harness", "tests", "fixture.py"))
        import cmds
        import hcore
        root = fx.make_repo()
        try:
            fx.process(root, "pequena")
            with self.assertRaises(hcore.Refused) as cm:
                cmds.add_task(root, fx.A, fx.task_spec(paths=("src/billing/**",)), ready=True)
            msg = str(cm.exception) + " " + " ".join(getattr(cm.exception, "problems", None) or [])
            self.assert_amend_hint(msg)
            cmds.add_task(root, fx.A, fx.task_spec(paths=("src/billing/discount.py",), title="ok"), ready=True)
        finally:
            fx.rm(root)

    def m2_or_none(self, tid):
        for it in (self.board().get("tree") or {}).values():
            if isinstance(it, dict) and it.get("id") == tid:
                return it.get("m2")
        return None


# ================================================================================================ R8
class TestR8Versao(unittest.TestCase):
    V = "0.10.0"

    def test_r8_version(self):
        self.assertEqual(read_text(os.path.join(SKILL, "VERSION")).strip(), self.V)

    def test_r8_migrations(self):
        import j5
        m = j5.loads(read_text(os.path.join(SKILL, "references", "migrations.json5")))
        self.assertEqual(m["version"], self.V)
        mig = [x for x in m["migrations"] if x.get("to") == self.V]
        self.assertEqual(len(mig), 1, "uma migração to: %s" % self.V)
        kinds = {a.get("kind") for a in mig[0].get("actions") or []}
        self.assertTrue({"harness", "emit"} <= kinds, kinds)
        self.assertEqual(m["migrations"][-1]["to"], self.V, "a última migração é a da versão")

    def test_r8_readme(self):
        self.assertIn(self.V, read_text(os.path.join(SKILL, "README.md")))

    def test_r8_docs_upgrade(self):
        t = read_text(os.path.join(SKILL, "docs", "09-upgrade.md"))
        self.assertRegex(t, r"(?m)^#+ .*Migra[çc][ãa]o 0\.10\.0")


if __name__ == "__main__":
    unittest.main()
