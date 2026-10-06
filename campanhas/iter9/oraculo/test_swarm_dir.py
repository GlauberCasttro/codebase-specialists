"""ORÁCULO campanha-iter9 — pasta `.swarm/` + harness único (ROADMAP-proxima-rodada.md, "P1 da rodada 1 — renomear
a pasta gerada de `.specialists/` para `.swarm/`"; PONTOS-DO-FOUNDER.md C4: "um harness não pode existir junto com o
outro"). Cenários SWARM-DIR-1..4 + constante única + check de harness único. Contrato fixado em ESPEC.md.

Este arquivo é contrato: quem implementa NÃO o edita. Comportamento observável apenas (CLI real `cs.py` em
subprocesso, alvos em diretórios temporários). Nunca escreve no repo v8 original (cópia via `git archive`), nem em
`~/`, nem na skill (PYTHONDONTWRITEBYTECODE). O nome legado é montado em tempo de execução (LEGACY) para que este
arquivo não contenha o literal e possa ser copiado para dentro da skill sem disparar o próprio teste de constante.

Rodar: python3 test_swarm_dir.py -v   (também com /usr/bin/python3, 3.9+)
Overrides: $CS_SKILL_DIR (skill; default: este repositório), $CS_V8_REPO_SRC (repo git real com harness v8),
$CS_UPGRADE_LEGACY_TARGET (alvo legado). Sem as duas últimas, os cenários que dependem delas são PULADOS.
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

sys.dont_write_bytecode = True

SKILL = os.path.realpath(os.environ.get("CS_SKILL_DIR")
                         or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(SKILL, "scripts")
CS = os.path.join(SCRIPTS, "cs.py")
ENGINE = os.path.join(SCRIPTS, "harness", "engine")
V8_REPO_SRC = os.environ.get("CS_V8_REPO_SRC") or ""
LEGACY_SRC = os.environ.get("CS_UPGRADE_LEGACY_TARGET") or ""

NEW = ".swarm"
LEGACY = "." + "specialists"                       # nome legado (montado: ver docstring)
LEGACY_RE = re.compile(r"(?<![A-Za-z0-9_])\." + "specialists" + r"(?![A-Za-z0-9_])")
BACKUP_REL = os.path.join(NEW, "backups", "harness-anterior")
EXIT_REFUSED = 3                                    # "recusado sem escrever nada" (convenção de install/upgrade)
UNICO_RE = re.compile(r"harness[ _-]?[uú]nico", re.I)
TIMEOUT = 900

# ------------------------------------------------------------------------------------------------ helpers


def env_clean():
    e = dict(os.environ)
    for k in ("CLAUDE_PROJECT_DIR", "CS_SKILL_VERSION_FILE", "CS_MIGRATIONS_FILE", "CS_GUARD_OFF", "CS_ACTOR"):
        e.pop(k, None)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    return e


def cs(target, *args):
    p = subprocess.run([sys.executable, CS, "--target", target] + list(args), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, env=env_clean(), timeout=TIMEOUT)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def git(root, *args):
    subprocess.run(["git", "-c", "user.email=o@o", "-c", "user.name=oraculo", "-c", "commit.gpgsign=false"]
                   + list(args), cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def tree_hash(root, skip_dirs=(".git",)):
    """{rel: sha|link:<alvo>|dir} de toda a árvore (exceto .git), + .git/hooks e .git/config à parte."""
    out = {}
    for d, dirs, files in os.walk(root):
        rel_d = os.path.relpath(d, root)
        keep = []
        for x in sorted(dirs):
            rel = os.path.normpath(os.path.join(rel_d, x))
            if rel in skip_dirs:
                continue
            if os.path.islink(os.path.join(d, x)):
                out[rel] = "link:" + os.readlink(os.path.join(d, x))
                continue
            out[rel + "/"] = "dir"
            keep.append(x)
        dirs[:] = keep
        for f in files:
            p = os.path.join(d, f)
            rel = os.path.normpath(os.path.join(rel_d, f))
            out[rel] = ("link:" + os.readlink(p)) if os.path.islink(p) else sha(p)
    gh = os.path.join(root, ".git", "hooks")
    if os.path.isdir(gh):
        for f in sorted(os.listdir(gh)):
            p = os.path.join(gh, f)
            out[".git/hooks/" + f] = ("link:" + os.readlink(p)) if os.path.islink(p) else sha(p)
    if os.path.isfile(os.path.join(root, ".git", "config")):
        out[".git/config"] = sha(os.path.join(root, ".git", "config"))
    return out


def diff_trees(a, b):
    return {"criados": sorted(set(b) - set(a)), "removidos": sorted(set(a) - set(b)),
            "alterados": sorted(k for k in a if k in b and a[k] != b[k])}


def files_with_legacy(root, skip=lambda rel: False):
    """[(rel, motivo)] de todo arquivo/symlink do alvo que cita o nome legado (texto) ou aponta para ele (link),
    + diretório com o nome legado. .git só nos hooks. __pycache__ ignorado (gerado)."""
    hits = []
    for d, dirs, files in os.walk(root):
        rel_d = os.path.relpath(d, root)
        if rel_d == ".git" or rel_d.startswith(".git" + os.sep):
            dirs[:] = []
            continue
        keep = []
        for x in dirs:
            rel = os.path.normpath(os.path.join(rel_d, x))
            if x == ".git" and rel_d == ".":
                continue
            if x == "__pycache__" or skip(rel + "/"):
                continue
            if x == LEGACY:
                hits.append((rel + "/", "diretório legado"))
                continue
            keep.append(x)
        dirs[:] = keep
        for f in files:
            rel = os.path.normpath(os.path.join(rel_d, f))
            if skip(rel):
                continue
            p = os.path.join(d, f)
            if os.path.islink(p):
                if LEGACY_RE.search(os.readlink(p)):
                    hits.append((rel, "symlink → " + os.readlink(p)))
                continue
            try:
                with open(p, "rb") as fh:
                    txt = fh.read().decode("utf-8", "replace")
            except OSError:
                continue
            if LEGACY_RE.search(txt):
                hits.append((rel, "texto"))
    gh = os.path.join(root, ".git", "hooks")
    if os.path.isdir(gh):
        for f in os.listdir(gh):
            p = os.path.join(gh, f)
            if os.path.islink(p) and LEGACY_RE.search(os.readlink(p)):
                hits.append((".git/hooks/" + f, "symlink → " + os.readlink(p)))
            elif os.path.isfile(p) and not f.endswith(".sample"):
                with open(p, "rb") as fh:
                    if LEGACY_RE.search(fh.read().decode("utf-8", "replace")):
                        hits.append((".git/hooks/" + f, "texto"))
    return hits


def hook_commands(settings_path):
    with open(settings_path) as fh:
        data = json.load(fh)
    out = []
    for ev, groups in (data.get("hooks") or {}).items():
        for g in groups or []:
            for h in g.get("hooks") or []:
                out.append((ev, g.get("matcher"), h.get("command") or ""))
    return out


def new_repo(prefix="o-swarm-"):
    root = os.path.realpath(tempfile.mkdtemp(prefix=prefix))
    for rel, txt in {"README.md": "# demo\n", "src/app/main.py": "def main():\n    return 1\n",
                     "tests/test_main.py": "import unittest\n", ".gitignore": "__pycache__/\n"}.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as fh:
            fh.write(txt)
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "init")
    return root


def fresh_install(root):
    """init + harness install (o caminho do SWARM-DIR-1). → [(rc, out, err), ...]"""
    return [cs(root, "init", "--platforms", "claude-code"),
            cs(root, "harness", "install", "--allow-outside", "--git-hook")]


def copy_v8_repo(dst_parent):
    """Cópia do repo v8 (só leitura do original: `git archive HEAD`) num repo git novo."""
    dst = os.path.join(dst_parent, "repo-v8")
    os.makedirs(dst)
    arch = subprocess.run(["git", "-C", V8_REPO_SRC, "archive", "--format=tar", "HEAD"], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=True, timeout=300)
    subprocess.run(["tar", "-x", "-C", dst], input=arch.stdout, check=True, stdout=subprocess.PIPE,
                   stderr=subprocess.PIPE, timeout=300)
    git(dst, "init", "-q")
    git(dst, "add", "-A")
    git(dst, "commit", "-qm", "copia do repo v8 (oraculo)")
    return dst


def engine_state_paths(root):
    """hcore.state_paths(root) do motor DA SKILL, em subprocesso (onde eventos/ledger moram no layout vigente)."""
    p = subprocess.run([sys.executable, "-c", "import sys, json; sys.path.insert(0, %r); import hcore; "
                        "print(json.dumps(hcore.state_paths(%r)))" % (ENGINE, root)],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env_clean(), timeout=60)
    if p.returncode != 0:
        raise AssertionError("hcore.state_paths falhou: " + p.stderr.decode())
    return json.loads(p.stdout.decode())


def selftest(root):
    rc, out, err = cs(root, "harness", "selftest")
    return rc, out + err


def unico_line(text):
    for line in text.splitlines():
        if UNICO_RE.search(line) and re.match(r"^\s*(OK|FALHA)\b", line):
            return line.strip()
    return None


def load_json5(path):
    if SCRIPTS not in sys.path:
        sys.path.insert(0, SCRIPTS)
    from cslib import json5io  # leitura apenas
    return json5io.read(path)


def all_facts(root):
    """{id: (fato, arquivo)} de <alvo>/.swarm/facts/*.json5 (qualquer forma: lista, {facts: [...]})."""
    out = {}
    fdir = os.path.join(root, NEW, "facts")
    if not os.path.isdir(fdir):
        return out
    for fn in sorted(os.listdir(fdir)):
        if not fn.endswith(".json5") or fn == "index.json5":
            continue
        try:
            data = load_json5(os.path.join(fdir, fn))
        except Exception:  # noqa: BLE001 — camada ilegível não é fato
            continue
        items = data if isinstance(data, list) else (data.get("facts") or []) if isinstance(data, dict) else []
        for f in items:
            if isinstance(f, dict) and f.get("id"):
                out[f["id"]] = (f, fn)
    return out


def index_ids(root):
    p = os.path.join(root, NEW, "facts", "index.json5")
    if not os.path.isfile(p):
        return set()
    data = load_json5(p)
    if isinstance(data, dict) and isinstance(data.get("facts"), list):
        return set(data["facts"])
    if isinstance(data, dict):
        ids = set(k for k in data if k not in ("schema_version", "generator", "layers"))
        for v in data.values():
            if isinstance(v, dict):
                ids |= set(v)
            elif isinstance(v, list):
                ids |= set(x for x in v if isinstance(x, str))
        return ids
    return set()


def read_version():
    with open(os.path.join(SKILL, "VERSION")) as fh:
        return fh.read().strip()


# ------------------------------------------------------------------------------------------------ CONSTANTE ÚNICA

# Arquivos onde o nome legado PODE aparecer (migração/legado). Justificativa em ESPEC.md §Allowlist.
ALLOWLIST_FILES = {
    "scripts/cslib/paths.py",               # LEGACY_STATE_DIR (fonte única do nome legado)
    "scripts/harness/engine/hcore.py",      # espelho no motor copiado ao alvo (não importa cslib)
    "references/migrations.json5",          # catálogo: a migração rename-dir descreve o nome antigo
}
ALLOWLIST_PREFIXES = (
    "scripts/upgrade/",                     # o pacote da migração (rename-dir) e seus testes com alvo legado
)
ALLOWLIST_MAX_HITS = 6                      # paths.py/hcore.py: constante + prefixo reservado + docstring, não mais


def scan_skill(roots, extra_files=()):
    hits = {}
    paths_ = []
    for r in roots:
        base = os.path.join(SKILL, r)
        if os.path.isfile(base):
            paths_.append(r)
            continue
        for d, dirs, files in os.walk(base):
            dirs[:] = [x for x in dirs if x != "__pycache__"]
            for f in files:
                if f.endswith((".pyc", ".png", ".jpg", ".gif", ".ico")):
                    continue
                paths_.append(os.path.relpath(os.path.join(d, f), SKILL).replace(os.sep, "/"))
    paths_ += [x for x in extra_files if os.path.isfile(os.path.join(SKILL, x))]
    for rel in paths_:
        with open(os.path.join(SKILL, rel), "rb") as fh:
            n = len(LEGACY_RE.findall(fh.read().decode("utf-8", "replace")))
        if n:
            hits[rel] = n
    return hits


SECTION_OK_RE = re.compile(r"migra|legad", re.I)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def md_sections(text):
    """[(nº da linha, linha, [títulos ancestrais])] — fora de blocos ``` os títulos abrem/fecham seções."""
    out, stack, fence = [], [], False
    for n, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            fence = not fence
        m = None if fence else HEADING_RE.match(line)
        if m:
            lvl = len(m.group(1))
            stack = [(l, t) for l, t in stack if l < lvl] + [(lvl, m.group(2))]
        out.append((n, line, [t for _, t in stack]))
    return out


def allowed(rel):
    return rel in ALLOWLIST_FILES or rel.startswith(ALLOWLIST_PREFIXES) or rel.endswith("/test_swarm_dir.py")


class TestConstanteUnica(unittest.TestCase):
    def test_constante_em_cslib_paths(self):
        if SCRIPTS not in sys.path:
            sys.path.insert(0, SCRIPTS)
        from cslib import paths
        self.assertEqual(getattr(paths, "STATE_DIR", None), ".swarm", "cslib.paths.STATE_DIR deve ser '.swarm'")
        self.assertEqual(getattr(paths, "LEGACY_STATE_DIR", None), LEGACY,
                         "cslib.paths.LEGACY_STATE_DIR guarda o nome legado (só migração/detecção)")
        t = os.path.realpath(tempfile.gettempdir())
        self.assertEqual(paths.state_dir(t), os.path.join(t, ".swarm", "state"))
        self.assertEqual(paths.facts_dir(t), os.path.join(t, ".swarm", "facts"))
        self.assertTrue(paths.is_self(".swarm/state/board.json5"))
        self.assertTrue(paths.is_reserved(".swarm/harness/guard.py"))
        self.assertTrue(paths.is_reserved(LEGACY + "/state/board.json5"),
                        "o diretório legado continua reservado (o scan nunca o analisa)")
        self.assertFalse(paths.is_self(LEGACY + "/state/board.json5"),
                         "a saída da skill é .swarm/; o legado não é 'self'")

    def test_motor_espelha_a_constante(self):
        p = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, %r); import hcore; "
                            "print(getattr(hcore, 'STATE_DIR', None)); "
                            "print(hcore.state_paths('/r')['state_dir'])" % ENGINE],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env_clean(), timeout=60)
        out = p.stdout.decode().split()
        self.assertEqual(p.returncode, 0, p.stderr.decode())
        self.assertEqual(out, [".swarm", "/r/.swarm/state"], "hcore.STATE_DIR (espelho no motor) = '.swarm'")

    def test_nome_legado_so_na_allowlist_codigo_e_templates(self):
        hits = scan_skill(["scripts", "assets/templates", "references"])
        fora = {k: v for k, v in hits.items() if not allowed(k)}
        self.assertEqual(fora, {}, "nome legado fora da allowlist (%d arquivo(s)): %s"
                         % (len(fora), sorted(fora)[:25]))
        abuso = {k: v for k, v in hits.items() if k in ALLOWLIST_FILES and k != "references/migrations.json5"
                 and v > ALLOWLIST_MAX_HITS}
        self.assertEqual(abuso, {}, "allowlist usada como escape (> %d ocorrências)" % ALLOWLIST_MAX_HITS)

    def test_nome_legado_fora_de_docs_de_entrada_e_corretor(self):
        """evals/check_run.py: zero. SKILL.md/MODO-DE-USO.md: zero FORA de uma seção explícita de migração/legado
        (título markdown com 'migra' ou 'legad' — o mesmo detector de scripts/doctests/tests/test_guia_de_uso.py,
        que exige que essa seção nomeie a pasta legada e cite o `upgrade`)."""
        hits = scan_skill([], extra_files=["evals/check_run.py"])
        for g in ("SKILL.md", "MODO-DE-USO.md"):
            with open(os.path.join(SKILL, g), encoding="utf-8") as fh:
                fora = ["%d" % n for n, line, heads in md_sections(fh.read())
                        if LEGACY_RE.search(line) and not any(SECTION_OK_RE.search(h) for h in heads)]
            if fora:
                hits[g] = "linhas " + ",".join(fora)
        self.assertEqual(hits, {}, "nome legado fora de seção de migração/legado: %s" % hits)

    def test_templates_e_install_apontam_para_swarm(self):
        """Negativo do 'apagar em vez de renomear': os wrappers/hooks continuam existindo, agora em .swarm/."""
        tpl = os.path.join(SCRIPTS, "harness", "templates")
        txt = ""
        for d, _, files in os.walk(tpl):
            for f in files:
                with open(os.path.join(d, f), "rb") as fh:
                    txt += fh.read().decode("utf-8", "replace")
        self.assertIn(".swarm/harness/guard.py", txt.replace("../../", ""))
        with open(os.path.join(SCRIPTS, "harness", "install.py")) as fh:
            self.assertIn(".swarm/", fh.read(), "install.py deve citar o destino .swarm/")


# ------------------------------------------------------------------------------------------------ SWARM-DIR-1


class TestSwarmDir1InitNovo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = new_repo()
        cls.res = fresh_install(cls.root)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def _ok(self):
        for rc, out, err in self.res:
            self.assertEqual(rc, 0, out + err)

    def test_cria_swarm_com_wrappers_estado_e_run(self):
        self._ok()
        sw = os.path.join(self.root, NEW)
        for b in ("cs-state", "cs-mem", "cs-session", "cs-route", "cs-precommit"):
            p = os.path.join(sw, "bin", b)
            self.assertTrue(os.path.isfile(p) and os.access(p, os.X_OK), "wrapper ausente: .swarm/bin/" + b)
        self.assertTrue(os.path.isfile(os.path.join(sw, "run.json5")), ".swarm/run.json5 (cs.py init)")
        self.assertTrue(os.path.isfile(os.path.join(sw, "state", "board.json5")))
        self.assertTrue(os.path.isfile(os.path.join(sw, "harness", "guard.py")))

    def test_nenhum_nome_legado_no_alvo(self):
        self._ok()
        self.assertFalse(os.path.lexists(os.path.join(self.root, LEGACY)), "diretório legado criado")
        self.assertEqual(files_with_legacy(self.root), [])

    def test_hooks_e_precommit_apontam_para_swarm(self):
        self._ok()
        cmds = hook_commands(os.path.join(self.root, ".claude", "settings.json"))
        self.assertTrue(cmds)
        self.assertTrue(all("cs-guard.sh" in c for _, _, c in cmds), cmds)
        with open(os.path.join(self.root, ".claude", "hooks", "cs-guard.sh")) as fh:
            self.assertIn(".swarm/harness/guard.py", fh.read())
        link = os.readlink(os.path.join(self.root, ".git", "hooks", "pre-commit"))
        self.assertIn(".swarm/bin/cs-precommit", link)
        with open(os.path.join(self.root, "specialists.mk")) as fh:
            self.assertIn("CS_BIN = .swarm/bin", fh.read())

    def test_wrapper_funciona_e_guard_protege_swarm_state(self):
        self._ok()
        self.assertTrue(os.path.isfile(os.path.join(self.root, NEW, "bin", "cs-state")), ".swarm/bin/cs-state ausente")
        p = subprocess.run([os.path.join(self.root, NEW, "bin", "cs-state"), "next"], cwd=self.root,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env_clean(), timeout=120)
        self.assertEqual(p.returncode, 0, p.stderr.decode())
        e = env_clean()
        e["CLAUDE_PROJECT_DIR"] = self.root
        payload = {"hook_event_name": "PreToolUse", "tool_name": "Write", "tool_use_id": "o",
                   "tool_input": {"file_path": os.path.join(self.root, NEW, "state", "board.json5"), "content": "{}"},
                   "session_id": "o", "cwd": self.root}
        p = subprocess.run(["/bin/sh", os.path.join(self.root, ".claude", "hooks", "cs-guard.sh"), "pre-write"],
                           input=json.dumps(payload).encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=e,
                           timeout=120)
        self.assertEqual(p.returncode, 2, "escrita direta em .swarm/state/ tem de ser bloqueada: "
                         + p.stderr.decode())

    def test_selftest_verde_com_probe_harness_unico(self):
        self._ok()
        rc, out = selftest(self.root)
        self.assertEqual(rc, 0, out)
        line = unico_line(out)
        self.assertIsNotNone(line, "selftest sem a sonda 'harness único'")
        self.assertTrue(line.startswith("OK"), line)

    def test_reinstalar_no_proprio_swarm_nao_e_outro_harness(self):
        """Negativo (falso positivo): o harness desta skill em .swarm/ NÃO é 'outro harness'."""
        self._ok()
        for rc, out, err in fresh_install(self.root):
            self.assertEqual(rc, 0, "reinit/reinstall idempotente recusado: " + out + err)
            self.assertNotIn("--replace-harness", out + err)
        self.assertTrue(os.path.isfile(os.path.join(self.root, NEW, "run.json5")))
        self.assertFalse(os.path.lexists(os.path.join(self.root, LEGACY)))


# ------------------------------------------------------------------------------------------------ SWARM-DIR-2


def make_marker_repo(kind):
    """Alvo com UM sinal de harness estranho (ou legado), em pastas diferentes da nossa."""
    root = new_repo("o-marker-")
    def w(rel, txt):
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as fh:
            fh.write(txt)
    if kind == "instance-v8":
        w(".swarm/instance.json", json.dumps({"project": "x", "env_prefix": "X", "zones": {}, "roster": []}))
    elif kind == "scripts-harness":
        w("scripts/harness/transition.py", "# harness de terceiros\n")
    elif kind == "kernel":
        w(".claude/kernel/tech-lead.md", "# kernel de outro harness\n")
    elif kind == "hooks-terceiros":
        w(".claude/settings.json", json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
            {"type": "command", "command": "\"$CLAUDE_PROJECT_DIR/.claude/hooks/guard-bash-writes.sh\""}]}]}}))
        w(".claude/hooks/guard-bash-writes.sh", "#!/bin/sh\nexit 0\n")
    elif kind == "legado":
        w(LEGACY + "/run.json5", "{schema_version: 1}\n")
        w(LEGACY + "/state/board.json5", "{}\n")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "marcador " + kind)
    return root


class TestSwarmDir2OutroHarnessNaoEscreve(unittest.TestCase):
    MARKERS = ("instance-v8", "scripts-harness", "kernel", "hooks-terceiros")

    def _assert_recusa(self, root, argv, expect_in):
        before = tree_hash(root)
        rc, out, err = cs(root, *argv)
        txt = out + err
        self.assertEqual(tree_hash(root), before, "escreveu com outro harness presente: %s"
                         % diff_trees(before, tree_hash(root)))
        self.assertEqual(rc, EXIT_REFUSED, "exit esperado %d (recusado sem escrever); veio %d\n%s"
                         % (EXIT_REFUSED, rc, txt))
        for s in expect_in:
            self.assertIn(s, txt)

    def test_cada_sinal_sozinho_bloqueia_init_e_install(self):
        for kind in self.MARKERS:
            with self.subTest(sinal=kind):
                root = make_marker_repo(kind)
                self.addCleanup(shutil.rmtree, root, True)
                self._assert_recusa(root, ["init", "--platforms", "claude-code"],
                                    ["plano de substituição", "--replace-harness"])
                self._assert_recusa(root, ["harness", "install", "--allow-outside"], ["--replace-harness"])

    def test_legado_desta_skill_aponta_upgrade(self):
        root = make_marker_repo("legado")
        self.addCleanup(shutil.rmtree, root, True)
        self._assert_recusa(root, ["init", "--platforms", "claude-code"], ["upgrade"])
        self._assert_recusa(root, ["harness", "install", "--allow-outside"], ["upgrade"])

    def test_settings_sem_hooks_nao_e_harness(self):
        """Negativo (falso positivo): settings.json só com permissions/env não é harness → init segue em .swarm/."""
        root = new_repo()
        self.addCleanup(shutil.rmtree, root, True)
        os.makedirs(os.path.join(root, ".claude"))
        with open(os.path.join(root, ".claude", "settings.json"), "w") as fh:
            json.dump({"permissions": {"allow": ["Bash(make test)"]}, "env": {"X": "1"}}, fh)
        rc, out, err = cs(root, "init", "--platforms", "claude-code")
        self.assertEqual(rc, 0, out + err)
        self.assertTrue(os.path.isfile(os.path.join(root, NEW, "run.json5")))

    @unittest.skipUnless(bool(V8_REPO_SRC) and os.path.isdir(os.path.join(V8_REPO_SRC, ".git")),
                     "repo v8 real ausente (defina $CS_V8_REPO_SRC): " + (V8_REPO_SRC or "não definido"))
    def test_repo_v8_init_sem_flag_mostra_plano_e_nao_escreve(self):
        tmp = tempfile.mkdtemp(prefix="o-v8-")
        self.addCleanup(shutil.rmtree, tmp, True)
        root = copy_v8_repo(tmp)
        self._assert_recusa(root, ["init", "--platforms", "claude-code"],
                            ["plano de substituição", "--replace-harness", ".swarm/instance.json", "scripts/harness",
                             ".claude/kernel", ".claude/settings.json", BACKUP_REL.replace(os.sep, "/")])
        self._assert_recusa(root, ["harness", "install", "--allow-outside"], ["--replace-harness"])


# ------------------------------------------------------------------------------------------------ SWARM-DIR-3

PRESERVE_EQUAL = ("state/board.json5", "team.json5")
PRESERVE_APPEND = ("state/events.jsonl", "memory/episodes.jsonl", "interview.jsonl", "team-approvals.jsonl",
                   "approvals.jsonl", "state/harness-ledger.jsonl")


@unittest.skipUnless(bool(LEGACY_SRC) and os.path.isdir(os.path.join(LEGACY_SRC, "." + "specialists")),
                     "alvo legado ausente (defina $CS_UPGRADE_LEGACY_TARGET): " + (LEGACY_SRC or "não definido"))
class TestSwarmDir3UpgradeLegado(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="o-legado-")
        cls.root = os.path.join(cls.tmp, "t")
        shutil.copytree(LEGACY_SRC, cls.root, symlinks=True)
        old = os.path.join(cls.root, LEGACY)
        cls.before = {}
        for rel in PRESERVE_EQUAL + PRESERVE_APPEND:
            p = os.path.join(old, rel)
            if os.path.isfile(p):
                with open(p, "rb") as fh:
                    cls.before[rel] = fh.read()
        cls.plan_tree = tree_hash(cls.root)
        cls.plan = cs(cls.root, "upgrade")
        cls.plan_tree_after = tree_hash(cls.root)
        cls.res = cs(cls.root, "upgrade", "--apply", "--allow-outside")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _ok(self):
        rc, out, err = self.res
        self.assertEqual(rc, 0, out + err)

    def test_plano_anuncia_rename_e_nao_escreve(self):
        rc, out, err = self.plan
        self.assertEqual(rc, 0, out + err)
        self.assertIn("rename-dir", out)
        self.assertIn(".swarm/", out)
        self.assertEqual(self.plan_tree_after, self.plan_tree)

    def test_move_para_swarm_sem_sobrar_legado(self):
        self._ok()
        self.assertFalse(os.path.lexists(os.path.join(self.root, LEGACY)), "diretório legado sobrou")
        self.assertTrue(os.path.isfile(os.path.join(self.root, NEW, "run.json5")))
        run = load_json5(os.path.join(self.root, NEW, "run.json5"))
        self.assertEqual(run.get("skill_version"), read_version())
        self.assertIn("rename-dir", (run.get("upgrade_history") or [{}])[-1].get("actions") or [])

    def test_caminhos_reescritos_em_hooks_settings_makefile_emitidos(self):
        self._ok()
        sw = NEW + "/"

        def skip(rel):
            r = rel.replace(os.sep, "/")
            if not r.startswith(sw) or r == sw:
                return False
            # dentro de .swarm/ só o MECANISMO operante é cobrado; histórico/dados (ledgers append-only com cadeia
            # de hash, índices, handoffs, backups) podem citar o caminho antigo — ver ESPEC.md §SWARM-DIR-3
            return not r.startswith((sw + "bin/", sw + "harness/"))
        hits = files_with_legacy(self.root, skip=skip)
        self.assertEqual(hits, [], "%d arquivo(s) ainda citam o nome legado: %s" % (len(hits), hits[:20]))
        link = os.path.join(self.root, ".git", "hooks", "pre-commit")
        if os.path.islink(link):
            self.assertIn(".swarm/bin/cs-precommit", os.readlink(link))
            self.assertTrue(os.path.exists(link), "symlink do pre-commit quebrado")

    def test_preserva_board_eventos_memoria_aprovacoes(self):
        """iter10 (MIGRATE-1, upgrade 0.7.0): o estado plano vira árvore. Eventos e ledger do harness ficam onde o
        motor do alvo os fixa (hcore.state_paths: events → SD/events.jsonl, ledger → SD/.engine/…), append-only
        sobre os bytes legados; o board plano some do lugar e tem de estar BYTE A BYTE num backup em SD/backups/
        (assim como events e harness-ledger originais); memória/aprovações/entrevista/team no mesmo lugar."""
        self._ok()
        self.assertIn("state/events.jsonl", self.before)
        self.assertIn("state/board.json5", self.before)
        sp = engine_state_paths(self.root)
        moved = {"state/events.jsonl": sp["events"], "state/harness-ledger.jsonl": sp["ledger"]}
        backups = os.path.join(self.root, NEW, "backups")
        backup_blobs = set()
        for d, _, files in os.walk(backups):
            for f in files:
                fp = os.path.join(d, f)
                if os.path.islink(fp) or not os.path.isfile(fp):
                    continue                      # symlink guardado (ex.: pre-commit) não é o layout plano
                with open(fp, "rb") as fh:
                    backup_blobs.add(fh.read())
        for rel, old in self.before.items():
            with self.subTest(arquivo=rel):
                if rel in ("state/board.json5", "state/events.jsonl", "state/harness-ledger.jsonl"):
                    self.assertIn(old, backup_blobs, "layout plano original sem cópia fiel em .swarm/backups/: " + rel)
                if rel == "state/board.json5":
                    continue                      # projeção plana: a fonte agora é a árvore (+ cópia no backup)
                p = moved.get(rel) or os.path.join(self.root, NEW, rel)
                self.assertTrue(os.path.isfile(p), "sumiu: %s → %s" % (rel, os.path.relpath(p, self.root)))
                with open(p, "rb") as fh:
                    new = fh.read()
                if rel in PRESERVE_EQUAL:
                    self.assertEqual(new, old, "alterado: " + rel)
                else:
                    self.assertTrue(new.startswith(old), "ledger não é append-only: " + rel)
        rc, out, err = cs(self.root, "team", "approved")
        self.assertEqual(rc, 0, "roster/cartões perderam a aprovação: " + out + err)

    def test_selftest_e_validate_verdes_depois(self):
        self._ok()
        rc, out = selftest(self.root)
        self.assertEqual(rc, 0, out)
        self.assertIn("G6 VERDE", out)
        line = unico_line(out)
        self.assertTrue(line and line.startswith("OK"), "sonda 'harness único' ausente/vermelha: %s" % line)
        self.assertFalse(os.path.lexists(os.path.join(self.root, LEGACY)), "selftest verde, mas no diretório legado")
        rc, out, err = cs(self.root, "harness", "validate", "--strict", "--allow-empty")
        self.assertEqual(rc, 0, out + err)
        rc, out, err = cs(self.root, "upgrade")
        self.assertIn("nada a fazer", out, "segundo upgrade deveria ser no-op")

    def test_conflito_legado_mais_swarm_estranho_recusa_sem_escrever(self):
        """Negativo: legado + `.swarm/instance.json` de outro harness → upgrade não mescla às cegas."""
        t = os.path.join(self.tmp, "conflito")
        shutil.copytree(LEGACY_SRC, t, symlinks=True)
        self.addCleanup(shutil.rmtree, t, True)
        os.makedirs(os.path.join(t, NEW))
        with open(os.path.join(t, NEW, "instance.json"), "w") as fh:
            json.dump({"project": "v8"}, fh)
        before = tree_hash(t)
        rc, out, err = cs(t, "upgrade", "--apply", "--allow-outside")
        self.assertEqual(rc, EXIT_REFUSED, out + err)
        self.assertEqual(tree_hash(t), before, diff_trees(before, tree_hash(t)))


# ------------------------------------------------------------------------------------------------ SWARM-DIR-4

# Zonas que a substituição PODE mexer na cópia do repo v8; todo o resto é produto e fica byte a byte.
REPLACE_ZONES = (".swarm/", ".claude/", "scripts/harness/", ".tmp/", "docs/state/")
REPLACE_ZONE_FILES = ("lefthook.yml", "Makefile", "specialists.mk", "CLAUDE.md", "AGENTS.md", "HARNESS.md",
                      "ORCHESTRATION.md", "INSTANCE.md", ".gitignore")
V8_HARNESS = (".swarm/", "scripts/harness/", ".claude/hooks/", ".claude/kernel/")
V8_HARNESS_FILES = (".claude/settings.json", "lefthook.yml")


def in_zone(rel):
    r = rel.replace(os.sep, "/")
    return r.startswith(REPLACE_ZONES) or r.rstrip("/") in REPLACE_ZONE_FILES or r.rstrip("/") + "/" in REPLACE_ZONES


@unittest.skipUnless(bool(V8_REPO_SRC) and os.path.isdir(os.path.join(V8_REPO_SRC, ".git")),
                     "repo v8 real ausente (defina $CS_V8_REPO_SRC): " + (V8_REPO_SRC or "não definido"))
class TestSwarmDir4ReplaceHarness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="o-replace-")
        cls.root = copy_v8_repo(cls.tmp)
        cls.before = tree_hash(cls.root)
        cls.v8_files = sorted(k for k, v in cls.before.items() if v != "dir"
                              and (k.startswith(V8_HARNESS) or k in V8_HARNESS_FILES))
        with open(os.path.join(cls.root, ".swarm", "knowledge", "DOMAIN_INVARIANTS.yaml")) as fh:
            cls.invariants = re.findall(r'- id: (BIZ-\d+)\n\s+invariant: "([^"]+)"', fh.read())
        cls.v8_hooks = sorted(set(re.findall(r"\.claude/hooks/([A-Za-z0-9_.-]+\.sh)",
                                             " ".join(c for _, _, c in hook_commands(
                                                 os.path.join(cls.root, ".claude", "settings.json"))))))
        cls.res = [cs(cls.root, "init", "--platforms", "claude-code", "--replace-harness", "--allow-outside")]
        if cls.res[0][0] == 0:
            cls.res.append(cs(cls.root, "harness", "install", "--allow-outside"))
        cls.after = tree_hash(cls.root)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _ok(self):
        for rc, out, err in self.res:
            self.assertEqual(rc, 0, out + err)

    def test_pre_condicoes_da_copia(self):
        """Sanidade do oráculo (passa hoje): a cópia é um v8 de verdade."""
        self.assertEqual([i for i, _ in self.invariants], ["BIZ-1", "BIZ-2", "BIZ-3"])
        self.assertIn(".swarm/instance.json", self.v8_files)
        self.assertIn(".claude/kernel/tech-lead.md", self.v8_files)
        self.assertGreaterEqual(len(self.v8_hooks), 5)

    def test_backup_completo_do_harness_anterior(self):
        self._ok()
        bk = os.path.join(self.root, BACKUP_REL)
        self.assertTrue(os.path.isdir(bk), "backup ausente em " + BACKUP_REL)
        faltam = []
        for rel in self.v8_files:
            p = os.path.join(bk, rel)
            if not os.path.isfile(p) or ("link:" not in self.before[rel] and sha(p) != self.before[rel]):
                faltam.append(rel)
        self.assertEqual(faltam, [], "%d arquivo(s) do v8 sem cópia fiel no backup: %s" % (len(faltam), faltam[:15]))

    def test_hooks_kernel_scripts_do_v8_removidos(self):
        self._ok()
        for rel in ("scripts/harness", ".claude/kernel", ".swarm/instance.json", ".swarm/init",
                    ".swarm/knowledge/DOMAIN_INVARIANTS.yaml", ".swarm/knowledge/ORCHESTRATION_MAP.yaml",
                    ".swarm/state/init-validation.jsonl"):
            self.assertFalse(os.path.lexists(os.path.join(self.root, rel)), "resíduo do v8: " + rel)
        for h in self.v8_hooks:
            self.assertFalse(os.path.lexists(os.path.join(self.root, ".claude", "hooks", h)), "hook v8: " + h)
        self.assertEqual(sorted(os.listdir(os.path.join(self.root, ".claude", "hooks"))), ["cs-guard.sh"])

    def test_um_unico_conjunto_de_hooks_em_settings(self):
        self._ok()
        cmds = hook_commands(os.path.join(self.root, ".claude", "settings.json"))
        self.assertTrue(cmds)
        estranhos = [c for _, _, c in cmds if "cs-guard.sh" not in c]
        self.assertEqual(estranhos, [], "hooks de outro harness continuam ativos")
        evs = set(ev for ev, _, _ in cmds)
        self.assertTrue({"PreToolUse", "PostToolUse", "SessionStart"} <= evs, evs)

    def test_gate_precommit_e_makefile_do_v8_desinstalados_preservando_o_resto(self):
        self._ok()
        with open(os.path.join(self.root, "lefthook.yml")) as fh:
            lh = fh.read()
        self.assertNotIn("SWARM HARNESS v8", lh)
        self.assertNotIn("scripts/harness/", lh)
        self.assertIn("conventional:", lh, "regra do usuário fora do bloco gerado do v8 foi apagada")
        with open(os.path.join(self.root, "Makefile")) as fh:
            mk = fh.read()
        self.assertNotIn("scripts/harness/", mk, "Makefile ainda chama o harness v8 removido")
        self.assertIn("include specialists.mk", mk)

    def test_invariantes_do_v8_importados_como_fatos_citaveis(self):
        self._ok()
        facts = all_facts(self.root)
        idx = index_ids(self.root)
        for biz, text in self.invariants:
            with self.subTest(invariante=biz):
                cand = [(f, fn) for fid, (f, fn) in facts.items()
                        if biz.lower() in fid.lower() or text[:60] in str(f.get("claim") or "")]
                self.assertTrue(cand, "%s não virou fato em .swarm/facts/" % biz)
                f, fn = cand[0]
                self.assertIn(text[:60], str(f.get("claim") or ""), "claim não traz o texto do invariante")
                self.assertTrue(f.get("origin"), "fato importado sem origin")
                ev = [e for e in (f.get("evidence") or []) if isinstance(e, dict)
                      and str(e.get("file") or "").endswith("DOMAIN_INVARIANTS.yaml")]
                self.assertTrue(ev, "evidência não cita DOMAIN_INVARIANTS.yaml: %s" % f.get("evidence"))
                self.assertTrue(os.path.isfile(os.path.join(self.root, ev[0]["file"])),
                                "evidência aponta arquivo inexistente (não citável): %s" % ev[0]["file"])
                self.assertIn(f["id"], idx, "fato fora do facts/index.json5 (não citável)")

    def test_produto_intacto(self):
        self._ok()
        prod_before = {k: v for k, v in self.before.items()
                       if v != "dir" and not in_zone(k) and not k.startswith(".git/")}
        self.assertTrue(any(k.startswith("harness/") for k in prod_before), "harness/ da raiz é PRODUTO do repo v8")
        mudou = sorted(k for k, v in prod_before.items() if self.after.get(k) != v)
        self.assertEqual(mudou, [], "%d arquivo(s) de produto alterados/apagados: %s" % (len(mudou), mudou[:15]))

    def test_sem_nome_legado_e_selftest_verde_com_harness_unico(self):
        self._ok()
        self.assertEqual(files_with_legacy(self.root, skip=lambda r: r.replace(os.sep, "/").startswith(
            BACKUP_REL.replace(os.sep, "/") + "/")), [])
        rc, out = selftest(self.root)
        self.assertEqual(rc, 0, out)
        line = unico_line(out)
        self.assertIsNotNone(line, "selftest sem a sonda 'harness único'")
        self.assertTrue(line.startswith("OK"), line)

    def test_replace_e_idempotente_sem_destruir_o_backup(self):
        """Negativo: rodar de novo não acha 'outro harness' (o backup não conta como harness ativo)."""
        self._ok()
        bk_before = {k: v for k, v in tree_hash(self.root).items() if k.startswith(BACKUP_REL)}
        rc, out, err = cs(self.root, "init", "--platforms", "claude-code")
        self.assertEqual(rc, 0, out + err)
        bk_after = {k: v for k, v in tree_hash(self.root).items() if k.startswith(BACKUP_REL)}
        self.assertEqual(bk_after, bk_before)


# ------------------------------------------------------------------------------------------------ HARNESS ÚNICO


class TestHarnessUnicoPosInstalacao(unittest.TestCase):
    """Check pós-instalação: a sonda 'harness único' do selftest REPROVA resíduo de outro harness."""

    def _plant(self, root, kind):
        def w(rel, txt):
            p = os.path.join(root, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w") as fh:
                fh.write(txt)
        if kind == "kernel":
            w(".claude/kernel/tech-lead.md", "# kernel\n")
        elif kind == "scripts-harness":
            w("scripts/harness/transition.py", "# v8\n")
        elif kind == "instance-v8":
            w(".swarm/instance.json", "{\"project\": \"x\"}\n")
        elif kind == "legado":
            w(LEGACY + "/state/board.json5", "{}\n")
        elif kind == "hook-terceiro":
            sp = os.path.join(root, ".claude", "settings.json")
            with open(sp) as fh:
                data = json.load(fh)
            data["hooks"].setdefault("PreToolUse", []).append(
                {"matcher": "Bash", "hooks": [{"type": "command", "command": ".claude/hooks/guard-x.sh"}]})
            with open(sp, "w") as fh:
                json.dump(data, fh)

    def test_residuo_reprova_e_limpo_aprova(self):
        root = new_repo()
        self.addCleanup(shutil.rmtree, root, True)
        for rc, out, err in fresh_install(root):
            self.assertEqual(rc, 0, out + err)
        rc, out = selftest(root)
        line = unico_line(out)
        self.assertIsNotNone(line, "selftest sem a sonda 'harness único'\n" + out)
        self.assertTrue(line.startswith("OK"), line)
        self.assertEqual(rc, 0, out)
        snap = os.path.join(tempfile.mkdtemp(prefix="o-snap-"), "s")
        self.addCleanup(shutil.rmtree, os.path.dirname(snap), True)
        shutil.copytree(root, snap, symlinks=True)
        for kind in ("kernel", "scripts-harness", "instance-v8", "legado", "hook-terceiro"):
            with self.subTest(residuo=kind):
                t = os.path.join(os.path.dirname(snap), kind)
                shutil.copytree(snap, t, symlinks=True)
                self._plant(t, kind)
                rc, out = selftest(t)
                self.assertEqual(rc, 1, "resíduo %s não reprovou o selftest\n%s" % (kind, out))
                line = unico_line(out)
                self.assertIsNotNone(line, out)
                self.assertTrue(line.startswith("FALHA"), line)


if __name__ == "__main__":
    unittest.main()
