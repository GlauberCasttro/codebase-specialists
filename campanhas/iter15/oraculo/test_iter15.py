"""ORÁCULO campanha-iter15 — skill codebase-specialists (0.8.0 → 0.9.0).

Quatro requisitos (contrato, interfaces FIXADAS e mapa requisito→teste em ESPEC.md, mesma pasta). Quem implementa
NÃO edita este arquivo.

  R1  As skills geradas passam a ter nome em inglês (verbo-objeto): salvar-sessao→save-session,
      carregar-sessao→load-session, corrigir→correct, planejar-sprint→plan-sprint, new-epico→new-epic,
      close-epico→close-epic. Em TODAS as plataformas emitidas e em toda referência textual (artefatos gerados,
      templates, docs, SKILL.md, MODO-DE-USO.md, orchestrator, mensagens). Prosa continua em português.
      (a) INIT: projeto novo pelo caminho real (`cs.py init` + `cs.py harness install` + `cs.py emit`) só tem
          os nomes novos, nas 4 plataformas.
  R2  (b) UPGRADE: alvo gerado pela 0.8.x (montado com a skill da 0.8.x extraída do git) → `cs.py upgrade`
      (plano) lista a troca sem escrever; `--apply` remove as pastas antigas que o manifesto do emit gerou, cria as
      novas, `emit validate` verde sem órfão, nenhum nome antigo sobra, pasta do usuário fora do manifesto fica.
      Catálogo `references/migrations.json5` com entrada 0.9.0 e VERSION ≥ 0.9.0.
  R3  MODO-DE-USO.md tem uma seção (entre `<!-- skills:begin -->` e `<!-- skills:end -->`) GERADA do código que
      explica cada skill gerada (nome, para que serve, quem roda, argumento); `cs.py skills-guide --check` reprova
      divergência; `--write` regenera.
  R4  Território com invariantes demais para o S2: o emit corta no top-N priorizado que cabe e acrescenta
      "Mais N invariante(s): lista completa e priorizada em `<arquivo>`" (arquivo que o emit gera), sem BudgetError.

Comportamento observável, sem mock: `cs.py`/`emit/cli.py` em subprocesso, alvos em diretórios temporários.
Skill sob teste: $CS_SKILL_DIR, senão ~/.claude/skills/codebase-specialists.
Skill 0.8.x de referência (para montar o alvo legado do R2 e o mapa de nomes do R1): extraída por `git archive`
do repositório $CS_SKILLS_REPO (padrão ~/.claude/skills), commit $CS_OLD_REF ou, se ausente, o commit mais recente
que toca codebase-specialists/ e cujo VERSION começa com "0.8." (hoje: HEAD).
Python 3.9+, unittest puro. Rodar (de dentro desta pasta):  python3 -m unittest -v test_iter15
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

SKILL = os.path.realpath(os.environ.get("CS_SKILL_DIR") or os.path.expanduser("~/.claude/skills/codebase-specialists"))
SKILLS_REPO = os.path.realpath(os.environ.get("CS_SKILLS_REPO") or os.path.expanduser("~/.claude/skills"))
SKILL_IN_REPO = "codebase-specialists"
SCRIPTS = os.path.join(SKILL, "scripts")
ALL = "claude-code,cursor,copilot,codex"
PLATFORMS = ("claude-code", "cursor", "copilot", "codex")
SKILL_DIRS = {"claude-code": ".claude/skills", "cursor": ".cursor/skills", "copilot": ".github/skills",
              "codex": ".agents/skills"}
GEN_TOKEN = "codebase-specialists:generated"
HUMAN_ONLY_TEXT = "só o humano executa"

# ====================================================================== R1 — interfaces fixadas
RENAMES = (("salvar-sessao", "save-session"), ("carregar-sessao", "load-session"), ("corrigir", "correct"),
           ("planejar-sprint", "plan-sprint"), ("new-epico", "new-epic"), ("close-epico", "close-epic"))
OLD = dict(RENAMES)
NEW_NAMES = tuple(n for _, n in RENAMES)
# Nome antigo como NOME de skill/comando (a prosa "corrigir" em português continua permitida):
#  - os 5 hifenizados em qualquer lugar (não são palavras do português);
#  - corrigir como `/corrigir` (comando ou caminho .../corrigir/), `corrigir` em crase, ou `name: corrigir`.
OLD_NAME_RE = re.compile(
    r"(?<![\w-])(?:salvar-sessao|carregar-sessao|planejar-sprint|new-epico|close-epico)(?![\w-])"
    r"|/corrigir(?![\w-]|\.md)"
    r"|`corrigir`"
    r"|(?m:^name:\s*[\"']?corrigir[\"']?\s*$)")
# Fontes da skill que não podem citar os nomes antigos (fora de seção de migração/legado nos guias).
SOURCE_GLOBS_ROOT = ("SKILL.md", "MODO-DE-USO.md")
SOURCE_DIRS = ("assets/templates", "references", "docs", "scripts")
SOURCE_EXT = (".md", ".py", ".json5", ".json", ".mdc", ".toml", ".sh", ".txt", ".yaml", ".yml", ".tmpl")
# Registros históricos (decisões/roteiro já tomados) e o lugar onde o mapa antigo→novo pode morar.
SOURCE_EXEMPT = ("references/migrations.json5", "docs/PONTOS-DO-FOUNDER.md", "docs/ROADMAP-rodada-seguinte.md")
SOURCE_EXEMPT_DIRS = ("scripts/upgrade/",)
MIGRATION_HEADING_RE = re.compile(r"migra|legad|0\.9", re.I)

# ====================================================================== R3 — interfaces fixadas
GUIDE = "MODO-DE-USO.md"
GUIDE_BEGIN = "<!-- skills:begin -->"
GUIDE_END = "<!-- skills:end -->"
GUIDE_COLS = {"skill": "skill", "serve": "para que serve", "quem": "quem roda", "arg": "argumento"}
NO_ARG = ("", "—", "-", "–", "nenhum", "(nenhum)", "sem argumento")
HINT_PROBE_OLD = '"<id da task> <resumo>"'          # argument-hint de close-task em scripts/emit/platforms.py
HINT_PROBE_NEW = '"<id-da-task> <resumo-do-oraculo-iter15>"'

# ====================================================================== R4 — interfaces fixadas
R4_PLAIN = 70                                        # invariantes "rules.*" (classe mais baixa)
R4_TOP = 3                                           # invariantes "rat.*" (decisão registrada: topo da prioridade)
MAIS_RE = re.compile(r"Mais (\d+) invariante\(s\): lista completa e priorizada em `([^`]+)`")
S2_FILES = {"claude-code": ".claude/rules/cs-dev-billing.md", "cursor": ".cursor/rules/cs-dev-billing.mdc",
            "copilot": ".github/instructions/cs-dev-billing.instructions.md"}


# ---------------------------------------------------------------------- utilitários

def _env():
    e = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    for k in ("CLAUDE_PROJECT_DIR", "CS_SKILL_VERSION_FILE", "CS_MIGRATIONS_FILE"):
        e.pop(k, None)
    return e


def run(argv, cwd=None, timeout=1800):
    p = subprocess.run(argv, cwd=cwd, env=_env(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def cs(skill, target, *args):
    return run([sys.executable, os.path.join(skill, "scripts", "cs.py"), "--target", target] + list(args),
               cwd=target)


def emit(skill, target, *args):
    return run([sys.executable, os.path.join(skill, "scripts", "emit", "cli.py")] + list(args)
               + ["--target", target], cwd=target)


def git(root, *args):
    return run(["git", "-C", root, "-c", "user.email=oraculo@iter15", "-c", "user.name=oraculo"] + list(args))


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def write(path, text):
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def tree_hash(root, skip=(".git",)):
    out = {}
    for d, dirs, files in os.walk(root):
        rel_d = os.path.relpath(d, root)
        dirs[:] = [x for x in dirs if os.path.normpath(os.path.join(rel_d, x)) not in skip]
        for x in dirs:
            out[os.path.normpath(os.path.join(rel_d, x)) + "/"] = "dir"
        for f in files:
            p = os.path.join(d, f)
            rel = os.path.normpath(os.path.join(rel_d, f))
            if os.path.islink(p):
                out[rel] = "link:" + os.readlink(p)
            else:
                with open(p, "rb") as fh:
                    out[rel] = hashlib.sha256(fh.read()).hexdigest()
    return out


def frontmatter(text):
    """→ (dict, body) de um SKILL.md (YAML simples: `chave: valor`, valores entre aspas duplas como JSON)."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text
    fm = {}
    for line in text[4:end].splitlines():
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not m:
            continue
        v = m.group(2).strip()
        if v.startswith('"'):
            try:
                v = json.loads(v)
            except ValueError:
                v = v.strip('"')
        elif v.startswith("'") and v.endswith("'"):
            v = v[1:-1]
        fm[m.group(1)] = v
    return fm, text[end + 4:]


def dmi(fm):
    return str(fm.get("disable-model-invocation", "")).strip().lower() == "true"


def skill_names(target, platform):
    """Nomes de skill gerados numa plataforma: <dir>/<n>/SKILL.md com marcador de gerado (sem `*-playbooks`)."""
    base = os.path.join(target, SKILL_DIRS[platform])
    out = {}
    if not os.path.isdir(base):
        return out
    for n in sorted(os.listdir(base)):
        p = os.path.join(base, n, "SKILL.md")
        if n.endswith("-playbooks") or not os.path.isfile(p):
            continue
        txt = read(p)
        if GEN_TOKEN in txt:
            out[n] = txt
    return out


def cited_bins(body):
    """{(binário, 1º subcomando)} citados como `.swarm/bin/<cs-x> <sub>` no corpo."""
    return set(re.findall(r"\.swarm/bin/(cs-[a-z]+)\s+([a-z-]+)", body))


def old_name_hits(text):
    return sorted(set(m.group(0) for m in OLD_NAME_RE.finditer(text)))


def scan_tree_for_old(root, skip_top=(".git",), only=None):
    """→ [(rel, [ocorrências])] em arquivos texto; também nomes de diretório/arquivo que SÃO um nome antigo."""
    bad = []
    for d, dirs, files in os.walk(root):
        rel_d = os.path.relpath(d, root)
        if rel_d == ".":
            dirs[:] = [x for x in dirs if x not in skip_top]
        dirs[:] = [x for x in dirs if x != "__pycache__"]
        for f in files:
            rel = os.path.normpath(os.path.join(rel_d, f)).replace(os.sep, "/")
            if only is not None and rel not in only:
                continue
            parts = rel.split("/")
            named = [x for x in parts[:-1] if x in OLD]
            try:
                with open(os.path.join(d, f), "rb") as fh:
                    txt = fh.read().decode("utf-8")
            except (OSError, UnicodeDecodeError):
                txt = ""
            hits = old_name_hits(txt)
            if named and (GEN_TOKEN in txt or only is not None):
                hits = hits + ["<pasta %s>" % "/".join(named)]
            if hits:
                bad.append((rel, hits))
    return bad


# ---------------------------------------------------------------------- skill 0.8.x de referência (git)

_CACHE = {}


def old_ref():
    if os.environ.get("CS_OLD_REF"):
        return os.environ["CS_OLD_REF"]
    rc, out, err = run(["git", "-C", SKILLS_REPO, "log", "--format=%H", "--", SKILL_IN_REPO])
    if rc != 0:
        raise RuntimeError("git log falhou em %s: %s" % (SKILLS_REPO, err))
    for h in out.split():
        rc, v, _ = run(["git", "-C", SKILLS_REPO, "show", "%s:%s/VERSION" % (h, SKILL_IN_REPO)])
        if rc == 0 and v.strip().startswith("0.8."):
            return h
    raise RuntimeError("nenhum commit com %s/VERSION 0.8.x em %s" % (SKILL_IN_REPO, SKILLS_REPO))


def old_skill():
    """Skill 0.8.x extraída por `git archive` numa pasta temporária (uma vez por processo)."""
    if "old_skill" not in _CACHE:
        tmp = tempfile.mkdtemp(prefix="cs-iter15-old-skill-")
        p = subprocess.run(["git", "-C", SKILLS_REPO, "archive", "--format=tar", old_ref(), SKILL_IN_REPO],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
        if p.returncode != 0:
            raise RuntimeError("git archive falhou: %s" % p.stderr.decode("utf-8", "replace"))
        with tarfile.open(fileobj=io.BytesIO(p.stdout)) as tf:
            try:
                tf.extractall(tmp, filter="data")
            except TypeError:                         # Python < 3.12 (sem `filter`)
                tf.extractall(tmp)
        _CACHE["old_skill"] = os.path.join(tmp, SKILL_IN_REPO)
        _CACHE.setdefault("tmps", []).append(tmp)
        v = read(os.path.join(_CACHE["old_skill"], "VERSION")).strip()
        assert v.startswith("0.8."), "skill de referência deveria ser 0.8.x, é %s" % v
    return _CACHE["old_skill"]


def make_fixture_repo(skill):
    """Repo-alvo sintético (team de scripts/emit/tests/fixture.py da skill dada), já com git e 1 commit."""
    code = ("import sys; sys.dont_write_bytecode=True; sys.path.insert(0, %r); sys.path.insert(0, %r);"
            "import fixture; print(fixture.make_repo())"
            % (os.path.join(skill, "scripts"), os.path.join(skill, "scripts", "emit", "tests")))
    rc, out, err = run([sys.executable, "-c", code])
    assert rc == 0, err
    root = out.strip().splitlines()[-1]
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "init")
    return root


def generate(skill, label):
    """Caminho real de geração de um projeto novo: cs.py init + harness install + emit, nas 4 plataformas."""
    root = make_fixture_repo(skill)
    steps = [cs(skill, root, "init", "--platforms", ALL),
             cs(skill, root, "harness", "install", "--allow-outside", "--git-hook"),
             cs(skill, root, "emit", "--allow-outside")]
    for i, (rc, out, err) in enumerate(steps):
        assert rc == 0, "%s: passo %d da geração falhou (rc=%d):\n%s\n%s" % (label, i, rc, out[-2000:], err[-2000:])
    git(root, "add", "-A")
    git(root, "commit", "-qm", "gerado por %s" % label)
    return root


def old_target():
    """Alvo PRISTINO gerado pela skill 0.8.x (não escreva nele: copie)."""
    if "old_target" not in _CACHE:
        _CACHE["old_target"] = generate(old_skill(), "skill 0.8.x")
        _CACHE.setdefault("tmps", []).append(_CACHE["old_target"])
    return _CACHE["old_target"]


def copy_target(src):
    dst = os.path.join(tempfile.mkdtemp(prefix="cs-iter15-copy-"), "t")
    shutil.copytree(src, dst, symlinks=True)
    return dst


def manifest_paths(target):
    p = os.path.join(target, ".swarm", "emit", "manifest.json5")
    txt = read(p)
    return sorted(set(re.findall(r'path:\s*"([^"]+)"', txt) + re.findall(r'"path":\s*"([^"]+)"', txt)))


def tearDownModule():
    for t in _CACHE.get("tmps", []):
        shutil.rmtree(t, ignore_errors=True)


def skill_version():
    return read(os.path.join(SKILL, "VERSION")).strip()


def semver(v):
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)", v)
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


# ====================================================================== R1 (a) — INIT, projeto novo

class TestR1InitProjetoNovo(unittest.TestCase):
    """Projeto novo pelo caminho real de geração com a skill sob teste: só os nomes novos, nas 4 plataformas."""

    @classmethod
    def setUpClass(cls):
        cls.old = old_target()
        cls.root = generate(SKILL, "skill sob teste")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def test_cada_plataforma_tem_os_nomes_novos_no_lugar_dos_antigos(self):
        errs = []
        for plat in PLATFORMS:
            old, new = skill_names(self.old, plat), skill_names(self.root, plat)
            for n in sorted(old):
                want = OLD.get(n, n)
                if want not in new:
                    errs.append("%s: %s (0.8.x: %s) não gerada" % (plat, want, n))
            for n in sorted(new):
                if n in OLD:
                    errs.append("%s: nome antigo gerado: %s/%s" % (plat, SKILL_DIRS[plat], n))
                fm, _ = frontmatter(new[n])
                if plat != "codex" or fm.get("name"):
                    if fm.get("name") != n:
                        errs.append("%s: %s/SKILL.md com name=%r (deveria ser o nome da pasta)" % (plat, n, fm.get("name")))
            renamed_here = [o for o in old if o in OLD]
            if plat == "claude-code" and sorted(renamed_here) != sorted(OLD):
                errs.append("pré-condição: a 0.8.x deveria gerar as 6 no Claude Code, gerou %s" % renamed_here)
        self.assertEqual(errs, [], "\n  ".join([""] + errs))

    def test_renomeadas_mantem_politica_argumento_e_comando(self):
        errs = []
        for plat in PLATFORMS:
            old, new = skill_names(self.old, plat), skill_names(self.root, plat)
            for o, n in RENAMES:
                if o not in old:
                    continue
                if n not in new:
                    errs.append("%s: %s ausente" % (plat, n))
                    continue
                fo, bo = frontmatter(old[o])
                fn, bn = frontmatter(new[n])
                for k in ("disable-model-invocation", "argument-hint", "allowed-tools", "arguments"):
                    if fo.get(k) != fn.get(k):
                        errs.append("%s/%s: %s mudou: %r → %r" % (plat, n, k, fo.get(k), fn.get(k)))
                if (HUMAN_ONLY_TEXT in bo.lower()) != (HUMAN_ONLY_TEXT in bn.lower()):
                    errs.append("%s/%s: texto '%s' não acompanha a 0.8.x" % (plat, n, HUMAN_ONLY_TEXT))
                if not cited_bins(bo) <= cited_bins(bn):
                    errs.append("%s/%s: comandos citados sumiram: %s" % (plat, n, sorted(cited_bins(bo) - cited_bins(bn))))
        self.assertEqual(errs, [], "\n  ".join([""] + errs))

    def test_nenhum_nome_antigo_em_nenhum_arquivo_gerado(self):
        bad = scan_tree_for_old(self.root)
        self.assertEqual(bad, [], "nome antigo de skill/comando no projeto gerado:\n  "
                         + "\n  ".join("%s: %s" % b for b in bad))

    def test_claude_md_e_orchestrator_citam_os_novos(self):
        claude_md = read(os.path.join(self.root, "CLAUDE.md"))
        for n in ("/save-session", "/load-session", "/correct", "/plan-sprint"):
            self.assertRegex(claude_md, re.escape(n) + r"(?![\w-])", "CLAUDE.md não cita %s" % n)
        orch = read(os.path.join(self.root, ".claude", "orchestrator.md"))
        self.assertRegex(orch, r"/correct(?![\w-])", ".claude/orchestrator.md não cita /correct")

    def test_emit_validate_verde(self):
        rc, out, err = cs(SKILL, self.root, "emit", "validate")
        self.assertEqual(rc, 0, out + err)


# ====================================================================== R1 — fontes da skill

def _section_ok_lines(text):
    """Linhas dentro de seção cujo título (ou ancestral) fala de migração/legado/0.9."""
    ok, stack, fence = set(), [], False
    for n, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            fence = not fence
        m = None if fence else re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            lvl = len(m.group(1))
            stack = [(l, t) for l, t in stack if l < lvl] + [(lvl, m.group(2))]
        if any(MIGRATION_HEADING_RE.search(t) for _, t in stack):
            ok.add(n)
    return ok


class TestR1FontesDaSkill(unittest.TestCase):
    def _files(self):
        out = [os.path.join(SKILL, f) for f in SOURCE_GLOBS_ROOT]
        for d in SOURCE_DIRS:
            for dp, dirs, files in os.walk(os.path.join(SKILL, d)):
                dirs[:] = [x for x in dirs if x not in ("__pycache__", "tests", "fixtures")]
                for f in files:
                    if f.endswith(SOURCE_EXT):
                        out.append(os.path.join(dp, f))
        return out

    def test_nenhum_nome_antigo_em_template_doc_guia_ou_codigo(self):
        bad = []
        for p in self._files():
            rel = os.path.relpath(p, SKILL).replace(os.sep, "/")
            if rel in SOURCE_EXEMPT or any(rel.startswith(d) for d in SOURCE_EXEMPT_DIRS):
                continue
            try:
                text = read(p)
            except (OSError, UnicodeDecodeError):
                continue
            allowed = _section_ok_lines(text) if rel.endswith(".md") else set()
            for n, line in enumerate(text.splitlines(), 1):
                if n in allowed:
                    continue
                hits = old_name_hits(line)
                if hits:
                    bad.append("%s:%d: %s" % (rel, n, ", ".join(hits)))
        self.assertEqual(bad, [], "nome antigo nas fontes da skill (fora de seção de migração):\n  " + "\n  ".join(bad))


# ====================================================================== R2 (b) — UPGRADE de alvo 0.8.x

USER_OUTSIDE_MANIFEST = {   # pastas do USUÁRIO com nome antigo que o emit da 0.8.x NUNCA gerou (fora do manifesto)
    ".cursor/skills/corrigir/SKILL.md": "---\nname: corrigir\ndescription: minha skill pessoal\n---\n\nnotas do dono\n",
    ".agents/skills/salvar-sessao/SKILL.md": "---\nname: salvar-sessao\ndescription: do usuário\n---\n\nnão apague\n",
    ".github/skills/planejar-sprint/LEIA.md": "pasta do usuário\n",
}
HUMAN_IN_GENERATED = ".claude/skills/corrigir/minhas-notas.md"   # arquivo humano dentro de pasta gerada


class TestR2UpgradeDe08(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        src = old_target()
        cls.old_manifest = manifest_paths(src)
        cls.old_skill_paths = [p for p in cls.old_manifest
                               if re.match(r"^\.(claude|cursor|github|agents)/skills/([^/]+)/SKILL\.md$", p)
                               and p.split("/")[2] in OLD]
        # alvo do PLANO
        cls.plan_t = copy_target(src)
        for rel, txt in USER_OUTSIDE_MANIFEST.items():
            write(os.path.join(cls.plan_t, rel), txt)
        git(cls.plan_t, "add", "-A")
        git(cls.plan_t, "commit", "-qm", "pastas do usuário")
        cls.plan_before = tree_hash(cls.plan_t)
        cls.plan_rc, cls.plan_out, cls.plan_err = cs(SKILL, cls.plan_t, "upgrade")
        cls.plan_after = tree_hash(cls.plan_t)
        # alvo do APPLY
        cls.t = copy_target(src)
        for rel, txt in USER_OUTSIDE_MANIFEST.items():
            write(os.path.join(cls.t, rel), txt)
        write(os.path.join(cls.t, HUMAN_IN_GENERATED), "notas humanas dentro da pasta gerada\n")
        git(cls.t, "add", "-A")
        git(cls.t, "commit", "-qm", "pastas do usuário")
        cls.user_before = {rel: read(os.path.join(cls.t, rel)) for rel in
                           list(USER_OUTSIDE_MANIFEST) + [HUMAN_IN_GENERATED]}
        cls.apply_rc, cls.apply_out, cls.apply_err = cs(SKILL, cls.t, "upgrade", "--apply", "--allow-outside")

    @classmethod
    def tearDownClass(cls):
        for t in (cls.plan_t, cls.t):
            shutil.rmtree(os.path.dirname(t), ignore_errors=True)

    def _applied(self):
        self.assertEqual(self.apply_rc, 0, "upgrade --apply falhou:\n%s\n%s"
                         % (self.apply_out[-3000:], self.apply_err[-3000:]))

    def test_precondicao_alvo_08_tem_as_antigas_no_manifesto(self):
        names = sorted(set(p.split("/")[2] for p in self.old_skill_paths))
        self.assertEqual(names, sorted(OLD), "o alvo 0.8.x deveria ter as 6 antigas no manifesto")

    def test_plano_lista_a_troca_e_nao_escreve(self):
        self.assertEqual(self.plan_rc, 0, self.plan_out + self.plan_err)
        self.assertEqual(self.plan_before, self.plan_after, "`cs.py upgrade` (plano) escreveu no alvo")
        errs = []
        for p in self.old_skill_paths:
            lines = [l for l in self.plan_out.splitlines() if p in l]
            if not lines:
                errs.append("plano não cita a remoção de %s" % p)
            elif not any(re.search(r"\b(delete|remove|remov)", l, re.I) for l in lines):
                errs.append("plano cita %s sem dizer que remove: %s" % (p, lines))
            parts = p.split("/")
            newp = "/".join(parts[:2] + [OLD[parts[2]]] + parts[3:])
            if not any(newp in l for l in self.plan_out.splitlines()):
                errs.append("plano não cita a criação de %s" % newp)
        self.assertEqual(errs, [], "\n  ".join([""] + errs) + "\n--- plano:\n" + self.plan_out[-4000:])

    def test_apply_remove_as_pastas_antigas_do_manifesto_e_cria_as_novas(self):
        self._applied()
        errs = []
        for p in self.old_skill_paths:
            d = os.path.dirname(os.path.join(self.t, p))
            parts = p.split("/")
            newp = os.path.join(self.t, *(parts[:2] + [OLD[parts[2]]] + parts[3:]))
            if os.path.lexists(os.path.join(self.t, p)):
                errs.append("SKILL.md antiga sobrou: %s" % p)
            if p != os.path.join(os.path.dirname(HUMAN_IN_GENERATED), "SKILL.md") and os.path.lexists(d):
                errs.append("pasta antiga sobrou: %s/ (%s)" % (os.path.dirname(p), os.listdir(d)))
            if not os.path.isfile(newp) or GEN_TOKEN not in read(newp):
                errs.append("nova não gerada: %s" % os.path.relpath(newp, self.t))
        self.assertEqual(errs, [], "\n  ".join([""] + errs))

    def test_apply_emit_validate_verde_sem_orfao_e_sem_nome_antigo(self):
        self._applied()
        rc, out, err = cs(SKILL, self.t, "emit", "validate")
        self.assertEqual(rc, 0, "emit validate depois do upgrade:\n" + out + err)
        man = manifest_paths(self.t)
        self.assertEqual([p for p in man if OLD_NAME_RE.search(p) or any("/%s/" % o in p for o in OLD)], [],
                         "manifesto ainda lista nome antigo")
        bad = scan_tree_for_old(self.t, only=set(man))
        bad += scan_tree_for_old(os.path.join(self.t, ".swarm", "bin"))
        bad += scan_tree_for_old(os.path.join(self.t, ".swarm", "harness"))
        self.assertEqual(bad, [], "nome antigo em artefato gerado depois do upgrade:\n  "
                         + "\n  ".join("%s: %s" % b for b in bad))
        orphans = []
        for plat, base in SKILL_DIRS.items():
            for o in OLD:
                p = os.path.join(self.t, base, o, "SKILL.md")
                if os.path.isfile(p) and GEN_TOKEN in read(p):
                    orphans.append(os.path.relpath(p, self.t))
        self.assertEqual(orphans, [], "skill antiga com marcador de gerado sobrou (órfão)")

    def test_apply_preserva_pasta_do_usuario_fora_do_manifesto(self):
        self._applied()
        for rel in USER_OUTSIDE_MANIFEST:
            p = os.path.join(self.t, rel)
            self.assertTrue(os.path.isfile(p), "arquivo do usuário apagado: %s" % rel)
            self.assertEqual(read(p), self.user_before[rel], "arquivo do usuário alterado: %s" % rel)

    def test_apply_preserva_arquivo_humano_dentro_de_pasta_gerada(self):
        self._applied()
        p = os.path.join(self.t, HUMAN_IN_GENERATED)
        self.assertTrue(os.path.isfile(p), "arquivo humano dentro da pasta gerada foi apagado")
        self.assertEqual(read(p), self.user_before[HUMAN_IN_GENERATED])
        self.assertFalse(os.path.lexists(os.path.join(os.path.dirname(p), "SKILL.md")),
                         "a SKILL.md gerada antiga deveria sair mesmo com arquivo humano na pasta")

    def test_apply_grava_versao_e_e_idempotente(self):
        self._applied()
        run_txt = read(os.path.join(self.t, ".swarm", "run.json5"))
        m = re.search(r'skill_version"?\s*:\s*"([^"]+)"', run_txt)
        self.assertTrue(m, "run.json5 sem skill_version")
        self.assertEqual(m.group(1), skill_version())
        before = tree_hash(self.t)
        rc, out, err = cs(SKILL, self.t, "upgrade")
        self.assertEqual(rc, 0, out + err)
        self.assertIn("nada a fazer", out, "depois do apply o plano deveria dizer 'nada a fazer'")
        self.assertEqual(before, tree_hash(self.t))

    def test_catalogo_tem_entrada_090_e_version(self):
        v = skill_version()
        self.assertGreaterEqual(semver(v), (0, 9, 0), "VERSION deveria ser ≥ 0.9.0, é %s" % v)
        cat = read(os.path.join(SKILL, "references", "migrations.json5"))
        self.assertRegex(cat, r'(?m)^\s*version:\s*"%s"' % re.escape(v), "migrations.json5 version ≠ VERSION")
        m = re.search(r'to:\s*"0\.9\.0"(.*?)(?=\n\s*\{\s*\n\s*to:|\Z)', cat, re.S)
        self.assertTrue(m, "migrations.json5 sem entrada {to: \"0.9.0\"}")
        entry = m.group(1)
        self.assertRegex(entry, r'kind:\s*"emit"', "entrada 0.9.0 sem a ação emit")
        self.assertTrue(any(n in entry for n in NEW_NAMES), "o `why` da 0.9.0 não cita os nomes novos")


# ====================================================================== R3 — guia gerado do código

def split_row(line):
    cells = re.split(r"(?<!\\)\|", line.strip())
    if cells and cells[0].strip() == "":
        cells = cells[1:]
    if cells and cells[-1].strip() == "":
        cells = cells[:-1]
    return [c.strip() for c in cells]


def norm_cell(c):
    c = c.replace("\\|", "|").replace("`", "")
    return " ".join(c.split())


def guide_block(text):
    nb, ne = text.count(GUIDE_BEGIN), text.count(GUIDE_END)
    if nb != 1 or ne != 1 or text.index(GUIDE_END) < text.index(GUIDE_BEGIN):
        return None
    return text[text.index(GUIDE_BEGIN) + len(GUIDE_BEGIN):text.index(GUIDE_END)]


def parse_guide(block):
    """→ ({nome: {serve, quem, arg}}, [erros]) da tabela dentro do bloco."""
    rows, errs, cols = {}, [], None
    for line in block.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = split_row(line)
        if cols is None:
            low = [norm_cell(c).lower() for c in cells]
            cols = {}
            for key, label in GUIDE_COLS.items():
                idx = [i for i, c in enumerate(low) if label in c]
                if not idx:
                    errs.append("cabeçalho sem coluna '%s': %s" % (label, line))
                    return rows, errs
                cols[key] = idx[0]
            continue
        if all(re.match(r"^:?-{3,}:?$", c.strip()) for c in cells if c.strip()):
            continue
        if len(cells) <= max(cols.values()):
            errs.append("linha com colunas a menos: %s" % line)
            continue
        names = re.findall(r"/([a-z0-9][a-z0-9-]*)", norm_cell(cells[cols["skill"]]))
        if len(names) != 1:
            errs.append("célula de skill deveria ter exatamente um `/nome`: %s" % line)
            continue
        if names[0] in rows:
            errs.append("skill repetida no guia: %s" % names[0])
        rows[names[0]] = {k: norm_cell(cells[i]) for k, i in cols.items()}
    if cols is None:
        errs.append("bloco sem tabela")
    return rows, errs


def emitted_truth(target):
    """Verdade observável: as skills que o emit gerou (todas as plataformas), com política e argumento."""
    truth = {}
    for plat in PLATFORMS:
        for n, txt in skill_names(target, plat).items():
            fm, body = frontmatter(txt)
            human = dmi(fm) or (plat == "codex" and HUMAN_ONLY_TEXT in body.lower())
            cur = truth.setdefault(n, {"human": human, "arg": None})
            if plat == "claude-code" or cur["arg"] is None:
                if fm.get("argument-hint") is not None:
                    cur["arg"] = norm_cell(str(fm["argument-hint"]))
            if plat == "claude-code":
                cur["human"] = dmi(fm)
    return truth


def check_guide_against(rows, truth):
    errs = []
    for n in sorted(set(truth) - set(rows)):
        errs.append("faltando no guia: /%s" % n)
    for n in sorted(set(rows) - set(truth)):
        errs.append("sobrando no guia (não é gerada): /%s" % n)
    for n in sorted(set(rows) & set(truth)):
        r, t = rows[n], truth[n]
        quem = r["quem"].lower()
        if t["human"]:
            if "só o humano" not in quem:
                errs.append("/%s: só o humano roda (disable-model-invocation), guia diz %r" % (n, r["quem"]))
        elif "só o humano" in quem or "modelo" not in quem:
            errs.append("/%s: o modelo pode rodar, guia diz %r" % (n, r["quem"]))
        if t["arg"] is None:
            if r["arg"].lower() not in NO_ARG:
                errs.append("/%s: sem argumento, guia diz %r" % (n, r["arg"]))
        elif r["arg"] != t["arg"]:
            errs.append("/%s: argumento %r, guia diz %r" % (n, t["arg"], r["arg"]))
        if len(r["serve"]) < 10:
            errs.append("/%s: 'para que serve' vazio ou curto: %r" % (n, r["serve"]))
    return errs


def copy_skill(dst):
    shutil.copytree(SKILL, dst, symlinks=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "evals", "iteration-*"))


def emit_fixture(skill):
    root = make_fixture_repo(skill)
    rc, out, err = emit(skill, root, "--platforms", ALL, "--allow-outside")
    assert rc == 0, "emit do fixture falhou: %s%s" % (out, err)
    return root


class TestR3GuiaGeradoDoCodigo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = emit_fixture(SKILL)
        cls.truth = emitted_truth(cls.root)
        cls.text = read(os.path.join(SKILL, GUIDE))
        cls.block = guide_block(cls.text)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def _rows(self):
        self.assertIsNotNone(self.block, "%s sem exatamente um par %s … %s" % (GUIDE, GUIDE_BEGIN, GUIDE_END))
        rows, errs = parse_guide(self.block)
        self.assertEqual(errs, [], "tabela do guia malformada:\n  " + "\n  ".join(errs))
        return rows

    def test_precondicao_verdade_tem_todas_as_familias(self):
        for n in NEW_NAMES + ("board", "close-task", "auto-status", "auto-approve", "feature-autonoma"):
            self.assertIn(n, self.truth, "pré-condição: o emit deveria gerar /%s" % n)

    def test_guia_cobre_cada_skill_gerada_com_quem_roda_e_argumento(self):
        errs = check_guide_against(self._rows(), self.truth)
        self.assertEqual(errs, [], "seção de skills do guia diverge do que o emit gera:\n  " + "\n  ".join(errs))

    def test_check_verde_na_skill(self):
        tmp = tempfile.mkdtemp(prefix="cs-iter15-cwd-")
        self.addCleanup(shutil.rmtree, tmp, True)
        rc, out, err = cs(SKILL, tmp, "skills-guide", "--check")
        self.assertEqual(rc, 0, "`cs.py skills-guide --check` deveria passar na skill:\n" + out + err)


class TestR3CheckReprovaDivergencia(unittest.TestCase):
    """Numa CÓPIA da skill: divergência plantada no guia ou no código → --check reprova nomeando a skill."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cs-iter15-skill-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.copy = os.path.join(self.tmp, "codebase-specialists")
        copy_skill(self.copy)
        self.cwd = os.path.join(self.tmp, "cwd")
        os.makedirs(self.cwd)
        self.guide = os.path.join(self.copy, GUIDE)
        self.orig = read(self.guide)
        self.block = guide_block(self.orig)
        self.assertIsNotNone(self.block, "%s sem o bloco %s … %s" % (GUIDE, GUIDE_BEGIN, GUIDE_END))

    def check(self):
        return cs(self.copy, self.cwd, "skills-guide", "--check")

    def _row_line(self, name):
        for line in self.block.splitlines():
            if line.strip().startswith("|") and re.search(r"/%s(?![\w-])" % re.escape(name), line):
                return line
        self.fail("linha de /%s não achada no bloco" % name)

    def _plant(self, new_block):
        write(self.guide, self.orig.replace(self.block, new_block))

    def _assert_fails_naming(self, name, why):
        rc, out, err = self.check()
        self.assertNotEqual(rc, 0, "--check não reprovou %s" % why)
        self.assertIn(name, out + err, "--check reprovou %s mas não nomeou %s:\n%s%s" % (why, name, out, err))

    def test_controle_copia_intacta_passa(self):
        rc, out, err = self.check()
        self.assertEqual(rc, 0, out + err)

    def test_reprova_skill_faltando(self):
        line = self._row_line("save-session")
        self._plant(self.block.replace(line + "\n", "", 1))
        self._assert_fails_naming("save-session", "skill faltando no guia")

    def test_reprova_skill_sobrando(self):
        line = self._row_line("board")
        fake = line.replace("/board", "/skill-fantasma-iter15", 1)
        self._plant(self.block.replace(line, line + "\n" + fake, 1))
        self._assert_fails_naming("skill-fantasma-iter15", "skill sobrando no guia")

    def test_reprova_politica_de_quem_roda_trocada(self):
        line = self._row_line("close-task")
        cells = re.split(r"(?<!\\)\|", line)
        hdr = [l for l in self.block.splitlines() if l.strip().startswith("|")][0]
        hcells = [norm_cell(c).lower() for c in re.split(r"(?<!\\)\|", hdr)]
        qi = [i for i, c in enumerate(hcells) if GUIDE_COLS["quem"] in c][0]
        cells[qi] = " o modelo pode chamar sozinho "
        self._plant(self.block.replace(line, "|".join(cells), 1))
        self._assert_fails_naming("close-task", "política de quem roda trocada")

    def test_write_regenera_e_preserva_o_resto(self):
        line = self._row_line("correct")
        self._plant(self.block.replace(line + "\n", "", 1))
        rc, out, err = cs(self.copy, self.cwd, "skills-guide", "--write")
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(read(self.guide), self.orig, "--write deveria restaurar exatamente o guia gerado")
        rc, out, err = cs(self.copy, self.cwd, "skills-guide", "--write")
        self.assertEqual((rc, read(self.guide)), (0, self.orig), "--write não é idempotente")

    def test_tabela_vem_do_codigo(self):
        """Muda o argument-hint de close-task no CÓDIGO da cópia: o guia fica velho (--check reprova) e --write
        põe o novo argumento na linha de /close-task."""
        pp = os.path.join(self.copy, "scripts", "emit", "platforms.py")
        src = read(pp)
        self.assertIn(HINT_PROBE_OLD, src, "pré-condição do oráculo: argument-hint de close-task em platforms.py")
        write(pp, src.replace(HINT_PROBE_OLD, HINT_PROBE_NEW, 1))
        self._assert_fails_naming("close-task", "guia velho depois de mudar o código")
        rc, out, err = cs(self.copy, self.cwd, "skills-guide", "--write")
        self.assertEqual(rc, 0, out + err)
        rows, errs = parse_guide(guide_block(read(self.guide)))
        self.assertEqual(errs, [])
        self.assertEqual(rows["close-task"]["arg"], norm_cell(json.loads(HINT_PROBE_NEW)))
        rc, out, err = self.check()
        self.assertEqual(rc, 0, out + err)


# ====================================================================== R4 — invariantes além do orçamento do S2

def r4_repo(skill, plain=R4_PLAIN, top=R4_TOP):
    root = make_fixture_repo(skill)
    team_p = os.path.join(root, ".swarm", "team.json5")
    team = json.loads(re.sub(r"^//[^\n]*\n", "", read(team_p)))
    ids = ["rules.inv%03d" % i for i in range(plain)] + ["rat.adr%d" % i for i in range(top)]
    team["agents"][0]["invariants"] = ids
    write(team_p, "// fixture iter15 R4\n" + json.dumps(team, ensure_ascii=False, indent=2))
    claims = {i: ("Invariante %s: o faturamento nunca viola a regra %s" % (i, i)) for i in ids}
    claims["rule.no-float-money"] = "Nenhum float em src/billing"
    facts = [{"id": i, "claim": c, "evidence": [{"file": "src/billing/money.py", "line": 1}]} for i, c in claims.items()]
    write(os.path.join(root, ".swarm", "facts", "rules.json5"), "// fixture iter15 R4\n" + json.dumps({"facts": facts}))
    return root, ids, claims


def invariant_section(text):
    m = re.search(r"(?ms)^#+ Invariantes\s*\n(.*?)(?=^#+ |\Z)", text)
    return m.group(1) if m else ""


class TestR4InvariantesAlemDoOrcamento(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, cls.ids, cls.claims = r4_repo(SKILL)
        cls.rc, cls.out, cls.err = emit(SKILL, cls.root, "--platforms", ALL, "--allow-outside")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def _emitted(self):
        self.assertEqual(self.rc, 0, "emit com %d invariantes falhou (BudgetError?):\n%s%s"
                         % (len(self.ids), self.out[-1500:], self.err[-1500:]))

    def test_emit_nao_falha_e_s2_no_orcamento(self):
        self._emitted()
        rc, out, err = emit(SKILL, self.root, "budget", "--platforms", ALL)
        self.assertEqual(rc, 0, "emit budget estourado:\n" + out + err)
        rc, out, err = emit(SKILL, self.root, "validate", "--platforms", ALL)
        self.assertEqual(rc, 0, "emit validate:\n" + out + err)

    def test_linha_mais_n_aponta_arquivo_gerado_completo(self):
        self._emitted()
        total = len(self.ids)
        for plat, rel in sorted(S2_FILES.items()):
            text = read(os.path.join(self.root, rel))
            sec = invariant_section(text)
            m = MAIS_RE.search(sec)
            self.assertTrue(m, "%s: seção Invariantes sem a linha 'Mais N invariante(s): …'" % rel)
            shown = [l for l in sec.splitlines() if l.startswith("- ") and not MAIS_RE.search(l)]
            self.assertGreater(len(shown), 0, "%s: nenhum invariante mostrado" % rel)
            self.assertEqual(int(m.group(1)), total - len(shown), "%s: N ≠ total − mostrados" % rel)
            path = os.path.join(self.root, m.group(2))
            self.assertTrue(os.path.isfile(path), "%s aponta para %s, que o emit não gerou" % (rel, m.group(2)))
            data = read(path)
            self.assertIn(GEN_TOKEN, data, "%s não é artefato gerado" % m.group(2))
            missing = [i for i in self.ids if self.claims[i] not in data]
            self.assertEqual(missing, [], "%s não traz a lista completa" % m.group(2))
            self.assertIn(m.group(2), manifest_paths(self.root), "%s fora do manifesto do emit" % m.group(2))

    def test_topo_e_o_de_maior_prioridade(self):
        self._emitted()
        sec = invariant_section(read(os.path.join(self.root, S2_FILES["claude-code"])))
        for i in self.ids[-R4_TOP:]:
            self.assertIn(self.claims[i], sec, "invariante de decisão registrada (%s) deveria estar no topo" % i)

    def test_codex_nested_ou_territorio_tambem_corta(self):
        self._emitted()
        cands = [os.path.join(self.root, "src", "billing", "AGENTS.md"),
                 os.path.join(self.root, ".swarm", "territories", "dev-billing.json5")]
        texts = [read(p) for p in cands if os.path.isfile(p)]
        self.assertTrue(texts, "Codex: nem AGENTS.md aninhado nem território compartilhado de dev-billing")
        if os.path.isfile(cands[0]):
            self.assertRegex(read(cands[0]), MAIS_RE, "src/billing/AGENTS.md sem a linha 'Mais N invariante(s)'")


class TestR4PoucosInvariantesSemCorte(unittest.TestCase):
    def test_sem_linha_mais_quando_cabe(self):
        root, ids, claims = r4_repo(SKILL, plain=2, top=1)
        self.addCleanup(shutil.rmtree, root, True)
        rc, out, err = emit(SKILL, root, "--platforms", ALL, "--allow-outside")
        self.assertEqual(rc, 0, out + err)
        sec = invariant_section(read(os.path.join(root, S2_FILES["claude-code"])))
        self.assertNotRegex(sec, MAIS_RE)
        for i in ids:
            self.assertIn(claims[i], sec)


if __name__ == "__main__":
    unittest.main()
