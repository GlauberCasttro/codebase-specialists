"""ORÁCULO campanha-iter20 — B-13 (patch 0.10.1): o pre-commit do alvo barra o resultado do próprio upgrade.

Mapa requisito → teste e critérios em ESPEC.md (mesma pasta). Resumo:

  U1  reproduz a cobaia: alvo git gerado pela skill 0.9.0 REAL (git archive do commit da 0.9.0 deste projeto), com o
      pre-commit instalado como o install faz (`.git/hooks/pre-commit` → `.swarm/bin/cs-precommit`); `cs.py upgrade
      --apply` da skill sob teste, `git add` de tudo que mudou, `git commit` SEM --no-verify ⇒ passa. Variantes:
      `cs.py emit` avulso (re-emissão), `cs.py harness install` avulso, instalação inicial (init + install + emit) e
      upgrade junto com estado gravado pelo `cs-state` na mesma leva.
  U2  edição MANUAL de arquivo que o upgrade gravou (motor em .swarm/harness/, SKILL.md/orchestrator emitidos) ou
      remoção de um deles, na mesma leva do upgrade ⇒ commit barrado; edição manual de arquivo de estado (task em
      .swarm/state/) fora do cs-state ⇒ continua barrada (hoje: `validate` acusa "edição à mão").
  U3  arquivo fora do conjunto escrito pelo upgrade e fora de allowed_paths ⇒ barrado (fonte, skill nova em
      .claude/skills/, arquivo novo em .swarm/harness/). Não-regressão do R5 (iter18) e do U5 (iter16): o portão roda
      aqueles oráculos junto (ver ESPEC).
  U4  o atestado do upgrade não é reutilizável: depois do upgrade commitado, um 2º commit com edição manual de
      arquivo do motor/emitido é barrado; reexecutar `upgrade` sem migração pendente não abençoa a edição; o atestado
      não libera arquivo que o upgrade não escreveu (barra SÓ o intruso; sem ele, o commit passa).
  U5  versão 0.10.1 (VERSION, migrations.json5 com entrada `to: "0.10.1"` com {kind: harness}, README,
      docs/09-upgrade.md); alvo em 0.9.0 vai direto a 0.10.1 (plano lista 0.10.0 e 0.10.1; o apply registra as duas).

Comportamento observável: CLI real (`cs.py`) em subprocesso, hook git real, repos git temporários. Nada de formato
de manifesto: só "o commit passa/é barrado" e o que o pre-commit imprime (`FORA: <arquivo>`).
Skill sob teste: $CS_SKILL_DIR, senão a raiz deste projeto. Skill 0.9.0 (a versão antiga do alvo): $CS_OLD_SKILL_DIR,
senão `git archive 5617806` deste repositório. Python 3.9+, unittest puro.
Rodar (desta pasta): python3 -m unittest -v test_iter20
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
SCRIPTS = os.path.join(SKILL, "scripts")
CS = os.path.join(SCRIPTS, "cs.py")
OLD_COMMIT = "5617806"          # "codebase-specialists 0.9.0 — projeto completo de desenvolvimento"
OLD_VERSION = "0.9.0"
NEW_VERSION = "0.10.1"

GIT_ENV = {"GIT_AUTHOR_NAME": "Ana", "GIT_AUTHOR_EMAIL": "ana@x", "GIT_COMMITTER_NAME": "Ana",
           "GIT_COMMITTER_EMAIL": "ana@x"}

ENGINE_FILE = ".swarm/harness/guard.py"          # motor: o upgrade 0.9.0 → 0.10.x o regrava (mudou na iter18)
ENGINE_FILE2 = ".swarm/harness/views.py"         # idem (usado na remoção)
EMIT_CHANGED = ".claude/orchestrator.md"         # emitido que o upgrade muda
EMIT_SAME = ".claude/skills/board/SKILL.md"      # emitido que o emit regrava com o mesmo conteúdo
SRC_OUT = "src/web/app.py"                       # fonte do alvo, fora de qualquer allowed_paths
USER_SKILL = ".claude/skills/minha-skill/SKILL.md"   # skill do usuário: o upgrade não escreveu
ENGINE_NEW = ".swarm/harness/extra.py"           # arquivo novo no motor que o upgrade não escreveu

_TMP = {}


def _env(extra=None):
    e = dict(os.environ)
    for k in ("CLAUDE_PROJECT_DIR", "CS_ACTOR", "CS_GUARD_OFF", "CS_ROOT", "CS_SKILL_VERSION_FILE",
              "CS_MIGRATIONS_FILE", "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        e.pop(k, None)
    e.update(GIT_ENV)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    e.update(extra or {})
    return e


def _run(argv, cwd, timeout=600):
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


def read_text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def write(root, rel, txt):
    full = os.path.join(root, rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(txt)


def append(root, rel, txt):
    with open(os.path.join(root, rel), "a", encoding="utf-8") as fh:
        fh.write(txt)


def _base_tmp():
    if "base" not in _TMP:
        _TMP["base"] = os.path.realpath(tempfile.mkdtemp(prefix="oraculo-iter20-"))
    return _TMP["base"]


def tearDownModule():
    if "base" in _TMP:
        shutil.rmtree(_TMP["base"], ignore_errors=True)


def old_skill():
    """A skill 0.9.0 real: $CS_OLD_SKILL_DIR ou `git archive` do commit da 0.9.0 deste projeto (sem escrever no repo)."""
    if "old" in _TMP:
        return _TMP["old"]
    d = os.environ.get("CS_OLD_SKILL_DIR")
    if not d:
        d = os.path.join(_base_tmp(), "skill-0.9.0")
        p = subprocess.run(["git", "-C", PROJECT, "archive", "--format=tar", OLD_COMMIT], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=300)
        if p.returncode != 0:
            raise AssertionError("não consegui extrair a skill 0.9.0 (git archive %s em %s): %s — defina "
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


def make_source_repo(skill, dest):
    """Repo sintético da fixture do emit (time aprovado: 2 devs, gate, qa) + git init + commit inicial."""
    code = ("import sys; sys.dont_write_bytecode=True; sys.path.insert(0, %r); sys.path.insert(0, %r);"
            "import fixture; print(fixture.make_repo())"
            % (os.path.join(skill, "scripts"), os.path.join(skill, "scripts", "emit", "tests")))
    rc, out, err = _run([sys.executable, "-c", code], _base_tmp())
    if rc != 0:
        raise AssertionError("fixture do emit: %s%s" % (out, err))
    shutil.rmtree(dest, ignore_errors=True)
    shutil.move(out.strip().splitlines()[-1], dest)
    git(dest, "init", "-q")
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "init")
    return dest


def old_template():
    """Alvo gerado pela skill 0.9.0 (init + harness install + emit), TUDO commitado, e o pre-commit ligado como o
    `harness install --git-hook` faz. O commit da geração é feito antes de ligar o hook (o hook não é versionado),
    então a fixture não usa --no-verify."""
    if "tpl" in _TMP:
        return _TMP["tpl"]
    old = old_skill()
    t = make_source_repo(old, os.path.join(_base_tmp(), "alvo-0.9.0"))
    cs_ok(old, t, "init", "--platforms", "claude-code")
    cs_ok(old, t, "harness", "install", "--allow-outside")
    cs_ok(old, t, "emit", "--allow-outside")
    git(t, "add", "-A")
    git(t, "commit", "-q", "-m", "gerado pela skill 0.9.0")
    cs_ok(old, t, "harness", "install", "--allow-outside", "--git-hook")
    hook = os.path.join(t, ".git", "hooks", "pre-commit")
    if not os.path.islink(hook) or not os.readlink(hook).endswith("cs-precommit"):
        raise AssertionError("pre-commit não ficou ligado ao cs-precommit")
    if git(t, "status", "--porcelain", "--untracked-files=no").strip():
        raise AssertionError("ligar o hook mudou arquivo rastreado:\n" + git(t, "status", "--porcelain"))
    # o hook está ativo e barra algo de fato (anti-vácuo: sem isso todo "commit passa" seria trivial)
    with open(os.path.join(t, SRC_OUT), "a") as fh:
        fh.write("# sonda\n")
    git(t, "add", "--", SRC_OUT)
    code, out, err = _run(["git", "-C", t, "-c", "core.hooksPath=" + os.path.join(t, ".git", "hooks"),
                           "commit", "-q", "-m", "sonda"], t)
    if code == 0:
        raise AssertionError("o pre-commit da fixture não barrou %s: o hook não está rodando" % SRC_OUT)
    git(t, "reset", "-q", "--", SRC_OUT)
    git(t, "checkout", "--", SRC_OUT)
    run = read_text(os.path.join(t, ".swarm", "run.json5"))
    if not re.search(r'skill_version:\s*"%s"' % re.escape(OLD_VERSION), run):
        raise AssertionError("alvo antigo deveria estar em %s:\n%s" % (OLD_VERSION, run[:400]))
    _TMP["tpl"] = t
    return t


class Alvo(unittest.TestCase):
    """Cada teste recebe uma cópia do alvo 0.9.0 (com .git e o hook)."""
    n = 0

    def setUp(self):
        tpl = old_template()
        Alvo.n += 1
        self.root = os.path.join(_base_tmp(), "t%d" % Alvo.n)
        shutil.copytree(tpl, self.root, symlinks=True)
        self.addCleanup(shutil.rmtree, self.root, True)

    # ---- ações da skill sob teste
    def upgrade(self):
        out = cs_ok(SKILL, self.root, "upgrade", "--apply", "--allow-outside")
        self.assertIn("upgrade aplicado", out)
        return out

    def changed(self):
        """Arquivos que mudaram/apareceram/sumiram em relação ao HEAD (sem os ignorados pelo .gitignore)."""
        out = git(self.root, "status", "--porcelain", "--untracked-files=all")
        return [ln[3:] for ln in out.splitlines() if ln.strip()]

    def stage_all(self):
        git(self.root, "add", "-A")

    def commit(self, msg="commit"):
        """`git commit` SEM --no-verify, com o hook do alvo (hooksPath explícito: ignora config global da máquina)."""
        head = git(self.root, "rev-parse", "HEAD").strip()
        code, out, err = _run(["git", "-C", self.root, "-c", "core.hooksPath=" + os.path.join(self.root, ".git", "hooks"),
                               "commit", "-q", "-m", msg], self.root)
        moved = git(self.root, "rev-parse", "HEAD").strip() != head
        return code, out + err, moved

    def assert_commit_ok(self, why):
        staged = git(self.root, "diff", "--cached", "--name-only").split()
        self.assertTrue(staged, "%s: nada staged (teste vazio)" % why)
        code, out, moved = self.commit(why)
        self.assertEqual(code, 0, "%s: o pre-commit deveria LIBERAR o commit (sem --no-verify):\n%s" % (why, out[-4000:]))
        self.assertTrue(moved, "%s: HEAD não andou" % why)
        self.assertIn("validate", out, "%s: o hook não rodou?\n%s" % (why, out))

    def assert_commit_barred(self, why, rels=(), not_rels=()):
        code, out, moved = self.commit(why)
        self.assertNotEqual(code, 0, "%s: o pre-commit deveria BARRAR o commit:\n%s" % (why, out[-4000:]))
        self.assertFalse(moved, "%s: HEAD andou com o commit barrado" % why)
        for r in rels:
            self.assertIn(r, out, "%s: a recusa não cita %s:\n%s" % (why, r, out[-4000:]))
        for r in not_rels:
            self.assertNotIn("FORA: %s " % r, out, "%s: arquivo escrito pela ferramenta barrado (%s):\n%s"
                             % (why, r, out[-4000:]))
        return out

    def new_task_via_cs_state(self):
        """Grava estado pelo caminho oficial (cs-state do motor instalado) → caminho do arquivo da task."""
        code, out, err = _run([sys.executable, os.path.join(self.root, ".swarm", "harness", "state.py"),
                               "--root", self.root, "new", "task", "--tipo", "US", "--agent", "dev-billing",
                               "--title", "Aplicar desconto", "--avulsa", "--verify-cmd", "python3 -m unittest",
                               "--como", "cliente", "--quero", "desconto", "--para", "pagar menos",
                               "--criterio", "AC-1|Dado pedido Quando aplico Então desconta|tests.test_billing",
                               "--allowed-path", "src/billing/discount.py"], self.root)
        self.assertEqual(code, 0, out + err)
        m = re.search(r"^criad[oa] \S+ em (\S+)\s*$", out, re.M)
        self.assertTrue(m, out)
        return m.group(1)


# ================================================================================================ U1
class TestU1CommitDoResultadoDaFerramenta(Alvo):
    """O resultado do próprio upgrade/emit/install commita sem --no-verify."""

    def test_u1_upgrade_commita_sem_no_verify(self):
        self.upgrade()
        ch = self.changed()
        self.assertIn(ENGINE_FILE, ch, "o upgrade 0.9.0 → atual deveria regravar o motor (reprodução da cobaia)")
        self.assertIn(EMIT_CHANGED, ch, "o upgrade deveria reemitir o orchestrator")
        self.stage_all()
        self.assert_commit_ok("upgrade --apply")

    def test_u1_emit_avulso_commita(self):
        cs_ok(SKILL, self.root, "emit", "--allow-outside")
        self.assertIn(EMIT_CHANGED, self.changed())
        self.stage_all()
        self.assert_commit_ok("emit avulso (re-emissão)")

    def test_u1_harness_install_avulso_commita(self):
        cs_ok(SKILL, self.root, "harness", "install", "--allow-outside", "--git-hook")
        self.assertIn(ENGINE_FILE, self.changed())
        self.stage_all()
        self.assert_commit_ok("harness install avulso")

    def test_u1_upgrade_com_estado_do_cs_state_na_mesma_leva(self):
        self.upgrade()
        task = self.new_task_via_cs_state()
        self.assertIn(task, self.changed())
        self.stage_all()
        self.assert_commit_ok("upgrade + task criada pelo cs-state")


class TestU1InstalacaoInicial(unittest.TestCase):
    """Alvo novo gerado só pela skill sob teste: init + harness install --git-hook + emit → commit passa."""

    def test_u1_instalacao_inicial_commita(self):
        t = make_source_repo(SKILL, os.path.join(_base_tmp(), "alvo-novo-%d" % os.getpid()))
        self.addCleanup(shutil.rmtree, t, True)
        cs_ok(SKILL, t, "init", "--platforms", "claude-code")
        cs_ok(SKILL, t, "harness", "install", "--allow-outside", "--git-hook")
        cs_ok(SKILL, t, "emit", "--allow-outside")
        self.assertTrue(os.path.islink(os.path.join(t, ".git", "hooks", "pre-commit")))
        git(t, "add", "-A")
        head = git(t, "rev-parse", "HEAD").strip()
        code, out, err = _run(["git", "-C", t, "-c", "core.hooksPath=" + os.path.join(t, ".git", "hooks"),
                               "commit", "-q", "-m", "instalação"], t)
        self.assertEqual(code, 0, "instalação inicial: o pre-commit deveria LIBERAR:\n%s" % (out + err)[-4000:])
        self.assertNotEqual(git(t, "rev-parse", "HEAD").strip(), head)
        self.assertIn("validate", out + err)


# ================================================================================================ U2
class TestU2EdicaoManualNaMesmaLeva(Alvo):
    """Arquivo que a ferramenta gravou, alterado à mão antes do commit ⇒ barrado (hoje já barra: R)."""

    def test_u2_motor_editado_a_mao_continua_barrado(self):
        self.upgrade()
        append(self.root, ENGINE_FILE, "\n# editado à mão\n")
        self.stage_all()
        self.assert_commit_barred("motor editado à mão depois do upgrade", rels=["FORA: %s " % ENGINE_FILE])

    def test_u2_emitido_mudado_pelo_upgrade_editado_a_mao_continua_barrado(self):
        self.upgrade()
        append(self.root, EMIT_CHANGED, "\nlinha à mão\n")
        self.stage_all()
        self.assert_commit_barred("orchestrator editado à mão", rels=["FORA: %s " % EMIT_CHANGED])

    def test_u2_skill_emitida_editada_a_mao_continua_barrada(self):
        self.upgrade()
        append(self.root, EMIT_SAME, "\nlinha à mão\n")
        self.stage_all()
        self.assert_commit_barred("SKILL.md emitida editada à mão", rels=["FORA: %s " % EMIT_SAME])

    def test_u2_motor_removido_a_mao_barra(self):
        self.upgrade()
        os.remove(os.path.join(self.root, ENGINE_FILE2))
        self.stage_all()
        self.assert_commit_barred("arquivo do motor removido à mão", rels=[ENGINE_FILE2])

    def test_u2_estado_editado_fora_do_cs_state_continua_barrado(self):
        self.upgrade()
        task = self.new_task_via_cs_state()
        p = os.path.join(self.root, task)
        txt = read_text(p)
        self.assertIn("Aplicar desconto", txt)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(txt.replace("Aplicar desconto", "Aplicar desconto (à mão)"))
        self.stage_all()
        rel = os.path.relpath(p, self.root).replace(os.sep, "/")
        self.assert_commit_barred("task editada fora do cs-state", rels=[os.path.basename(rel)])


# ================================================================================================ U3
class TestU3ForaDoConjuntoEscrito(Alvo):
    """Fora do que a ferramenta escreveu e fora de allowed_paths ⇒ barrado (hoje já barra: R)."""

    def test_u3_fonte_fora_de_allowed_continua_barrada(self):
        self.upgrade()
        append(self.root, SRC_OUT, "# à mão\n")
        git(self.root, "add", "--", SRC_OUT)
        self.assert_commit_barred("fonte fora de allowed_paths", rels=["FORA: %s " % SRC_OUT])

    def test_u3_skill_do_usuario_continua_barrada(self):
        self.upgrade()
        write(self.root, USER_SKILL, "---\nname: minha-skill\n---\nfeita à mão\n")
        git(self.root, "add", "--", USER_SKILL)
        self.assert_commit_barred("skill nova fora do emit", rels=["FORA: %s " % USER_SKILL])

    def test_u3_arquivo_novo_no_motor_continua_barrado(self):
        self.upgrade()
        write(self.root, ENGINE_NEW, "X = 1\n")
        git(self.root, "add", "--", ENGINE_NEW)
        self.assert_commit_barred("arquivo novo em .swarm/harness/", rels=["FORA: %s " % ENGINE_NEW])


# ================================================================================================ U4
class TestU4AtestadoNaoReutilizavel(Alvo):
    def committed_upgrade(self):
        self.upgrade()
        self.stage_all()
        self.assert_commit_ok("upgrade --apply")

    def test_u4_segundo_commit_motor_a_mao_barra(self):
        self.committed_upgrade()
        append(self.root, ENGINE_FILE, "\n# editado à mão depois do commit do upgrade\n")
        git(self.root, "add", "--", ENGINE_FILE)
        self.assert_commit_barred("2º commit: motor à mão", rels=["FORA: %s " % ENGINE_FILE])

    def test_u4_segundo_commit_emitido_a_mao_barra(self):
        self.committed_upgrade()
        append(self.root, EMIT_CHANGED, "\nlinha à mão\n")
        append(self.root, EMIT_SAME, "\nlinha à mão\n")
        git(self.root, "add", "--", EMIT_CHANGED, EMIT_SAME)
        self.assert_commit_barred("2º commit: emitidos à mão", rels=["FORA: %s " % EMIT_CHANGED,
                                                                     "FORA: %s " % EMIT_SAME])

    def test_u4_reupgrade_sem_migracao_nao_abencoa_edicao(self):
        self.committed_upgrade()
        append(self.root, ENGINE_FILE, "\n# editado à mão\n")
        out = cs_ok(SKILL, self.root, "upgrade", "--apply", "--allow-outside")
        self.assertIn("nada a fazer", out)
        git(self.root, "add", "--", ENGINE_FILE)
        self.assert_commit_barred("upgrade sem migração pendente depois da edição", rels=["FORA: %s " % ENGINE_FILE])

    def test_u4_atestado_nao_libera_intruso(self):
        self.upgrade()
        written = [r for r in self.changed() if not r.startswith(".swarm/backups/")]
        self.assertIn(ENGINE_FILE, written)
        append(self.root, SRC_OUT, "# à mão\n")
        write(self.root, USER_SKILL, "---\nname: minha-skill\n---\nfeita à mão\n")
        write(self.root, ENGINE_NEW, "X = 1\n")
        self.stage_all()
        self.assert_commit_barred("upgrade + intrusos", rels=["FORA: %s " % r for r in (SRC_OUT, USER_SKILL, ENGINE_NEW)],
                                  not_rels=written)
        git(self.root, "reset", "-q", "--", SRC_OUT, USER_SKILL, ENGINE_NEW)
        self.assert_commit_ok("upgrade sem os intrusos")

    def test_u4_emit_avulso_nao_libera_motor_editado_continua(self):
        cs_ok(SKILL, self.root, "emit", "--allow-outside")
        append(self.root, ENGINE_FILE, "\n# editado à mão\n")
        self.stage_all()
        self.assert_commit_barred("emit avulso + motor à mão", rels=["FORA: %s " % ENGINE_FILE])


# ================================================================================================ U5
class TestU5Versao(unittest.TestCase):
    V = NEW_VERSION

    def catalog(self):
        if SCRIPTS not in sys.path:
            sys.path.insert(0, SCRIPTS)
        from cslib import json5io
        return json5io.read(os.path.join(SKILL, "references", "migrations.json5"))

    def test_u5_version(self):
        self.assertEqual(read_text(os.path.join(SKILL, "VERSION")).strip(), self.V)

    def test_u5_migrations(self):
        m = self.catalog()
        self.assertEqual(m["version"], self.V)
        mig = [x for x in m["migrations"] if x.get("to") == self.V]
        self.assertEqual(len(mig), 1, "uma migração to: %s" % self.V)
        kinds = {a.get("kind") for a in mig[0].get("actions") or []}
        self.assertIn("harness", kinds, "o pre-commit/motor muda ⇒ o alvo reinstala o harness: %s" % kinds)
        self.assertEqual(m["migrations"][-1]["to"], self.V, "a última migração é a da versão")
        tos = [x["to"] for x in m["migrations"]]
        self.assertIn("0.10.0", tos)
        self.assertEqual(tos.index(self.V), tos.index("0.10.0") + 1, "0.10.1 vem logo depois da 0.10.0")

    def test_u5_readme(self):
        self.assertIn(self.V, read_text(os.path.join(SKILL, "README.md")))

    def test_u5_docs_upgrade(self):
        t = read_text(os.path.join(SKILL, "docs", "09-upgrade.md"))
        self.assertRegex(t, r"(?m)^#+ .*Migra[çc][ãa]o 0\.10\.1")


class TestU5DeZeroNoveDireto(Alvo):
    def test_u5_plano_de_090_lista_0100_e_0101(self):
        before = git(self.root, "status", "--porcelain", "--untracked-files=all")
        code, out, err = cs(SKILL, self.root, "upgrade")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(git(self.root, "status", "--porcelain", "--untracked-files=all"), before,
                         "o plano (sem --apply) não escreve nada")
        self.assertIn("versão do alvo:  %s" % OLD_VERSION, out)
        self.assertIn("versão da skill: %s" % NEW_VERSION, out)
        self.assertRegex(out, r"migrações no intervalo \(2\)")
        self.assertRegex(out, r"(?m)^\s+0\.10\.0 — ")
        self.assertRegex(out, r"(?m)^\s+0\.10\.1 — ")

    def test_u5_apply_de_090_registra_as_duas_migracoes(self):
        self.upgrade()
        if SCRIPTS not in sys.path:
            sys.path.insert(0, SCRIPTS)
        from cslib import json5io
        run = json5io.read(os.path.join(self.root, ".swarm", "run.json5"))
        self.assertEqual(run.get("skill_version"), NEW_VERSION)
        last = (run.get("upgrade_history") or [{}])[-1]
        self.assertEqual(last.get("from"), OLD_VERSION)
        self.assertEqual(last.get("migrations"), ["0.10.0", NEW_VERSION])


if __name__ == "__main__":
    unittest.main()
