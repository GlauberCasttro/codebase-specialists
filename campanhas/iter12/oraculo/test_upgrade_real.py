"""Oráculo campanha-iter12 — `cs.py upgrade` em uso real (repositório-piloto (projeto-legado) legado `.specialists/`).

Python 3.9+, só stdlib. NUNCA escreve na fonte: cada teste trabalha numa CÓPIA do repositório-piloto em tmp
(sem node_modules, .venv, .env, logs e sem `.swarm/` residual da fonte).

Ambiente (sobrescrevível):
  CS_SKILL     raiz da skill sob teste   (default ~/.claude/skills/codebase-specialists)
  CS_PILOTO_SRC  repo legado a copiar (repositório-piloto; só leitura). Sem ele, o módulo é PULADO.

Requisitos (ver ESPEC.md):
  U-3  falha de verificação imprime o motivo (comando + saída) no fluxo de progresso, sem truncar a linha que
       explica a falha — não só exit 1.
  U-4  rollback completo: depois de restaurar, nada de `.swarm/` sobra; resíduo próprio da skill
       (`.swarm/state/selftest.json5` de um `harness selftest` rodado no legado) não bloqueia o próximo upgrade.
  U-5  causa raiz: o upgrade do repositório-piloto conclui (exit 0) com `emit validate` verde, emitidos sem caminho legado,
       e preserva entrevista/aprovações/cartões/memória, a cadeia de eventos e as tasks em andamento.

Rodar:  cd campanha-iter12/oraculo && python3 -m unittest -v test_upgrade_real
"""
import contextlib
import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HOME = os.path.expanduser("~")
SKILL = os.path.realpath(os.environ.get("CS_SKILL", os.path.join(HOME, ".claude", "skills", "codebase-specialists")))
PILOTO_SRC = os.path.realpath(os.environ["CS_PILOTO_SRC"]) if os.environ.get("CS_PILOTO_SRC") else ""
CS = os.path.join(SKILL, "scripts", "cs.py")
LEGACY, NEW = ".specialists", ".swarm"
LEGACY_RE = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(LEGACY) + r"(?![A-Za-z0-9_])")
SKIP_TOP = {"node_modules", ".venv", ".env", "logs", ".swarm", ".pytest_cache"}
PRESERVED = ("interview.jsonl", "team-approvals.jsonl", "approvals.jsonl", os.path.join("cards", "status.json5"),
             "memory")
UPGRADE_TIMEOUT = 1800
SENTINEL = "SENTINELA-U3-MOTIVO: G7 FALHOU (1 erro(s)) .claude/rules/x.md editado à mão"

sys.dont_write_bytecode = True                      # não suja a skill sob teste com __pycache__
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
if os.path.join(SKILL, "scripts") not in sys.path:
    sys.path.insert(0, os.path.join(SKILL, "scripts"))


def setUpModule():
    if not os.path.isfile(CS):
        raise RuntimeError("skill sem scripts/cs.py: %s (defina CS_SKILL)" % SKILL)
    if not PILOTO_SRC:
        raise unittest.SkipTest("repositório-piloto ausente (defina $CS_PILOTO_SRC)")
    if not os.path.isfile(os.path.join(PILOTO_SRC, LEGACY, "run.json5")):
        raise RuntimeError("fonte não é um alvo legado (%s/%s/run.json5 ausente): aponte PILOTO_SRC para uma "
                           "cópia do repositório-piloto ainda em %s/" % (PILOTO_SRC, LEGACY, LEGACY))


# ------------------------------------------------------------------ utilitários

def load5(p):
    from cslib import json5io
    return json5io.read(p)


def run(argv, cwd, timeout=UPGRADE_TIMEOUT):
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CS_GUARD_OFF", None)
    p = subprocess.run(argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def cs(target, *args, **kw):
    return run([sys.executable, CS, "--target", target] + list(args), cwd=target, **kw)


def copy_piloto(tag):
    """Cópia do repositório-piloto legado em tmp (symlinks preservados: .git/hooks/pre-commit é relativo)."""
    base = os.path.realpath(tempfile.mkdtemp(prefix="oraculo-iter12-%s-" % tag))
    dst = os.path.join(base, "piloto")

    def ignore(d, names):
        skip = set(n for n in names if n == "__pycache__")
        if os.path.realpath(d) == PILOTO_SRC:
            skip |= SKIP_TOP & set(names)
        return skip
    shutil.copytree(PILOTO_SRC, dst, symlinks=True, ignore=ignore)
    assert not os.path.lexists(os.path.join(dst, NEW))
    assert os.path.isdir(os.path.join(dst, LEGACY))
    return base, dst


def sha_tree(root, rels):
    out = {}
    for rel in rels:
        p = os.path.join(root, rel)
        files = [p] if os.path.isfile(p) else []
        if os.path.isdir(p):
            for d, _, fs in os.walk(p):
                files += [os.path.join(d, f) for f in fs]
        for f in files:
            with open(f, "rb") as fh:
                out[os.path.relpath(f, root)] = hashlib.sha256(fh.read()).hexdigest()
    return out


def apply_in_process(target, fail_argv=None, fail_out=""):
    """core.apply no próprio processo; com fail_argv, a verificação `cs.py <fail_argv>` devolve exit 1 + fail_out
    (falha induzida, independente da causa raiz do U-5). → (rc, stdout_do_progresso, stderr)."""
    from upgrade import core
    real = core.run_cs

    def fake(t, argv, timeout=core.CMD_TIMEOUT):
        if fail_argv is not None and tuple(argv) == tuple(fail_argv):
            return 1, fail_out, ""
        return real(t, argv, timeout=timeout)
    out, err = io.StringIO(), io.StringIO()
    old_env = os.environ.pop("CLAUDE_PROJECT_DIR", None)
    core.run_cs = fake
    try:
        with contextlib.redirect_stderr(err):
            rc = core.apply(target, allow_outside=True, out=out)
    finally:
        core.run_cs = real
        if old_env is not None:
            os.environ["CLAUDE_PROJECT_DIR"] = old_env
    return rc, out.getvalue(), err.getvalue()


# ------------------------------------------------------------------ U-3 motivo visível

class TestU3MotivoDaFalha(unittest.TestCase):
    """Falha de verificação induzida em `emit validate`: a saída do comando tem a linha do motivo NO TOPO,
    seguida de 20 linhas de ruído (como um validador real que lista gates ok depois do erro)."""

    @classmethod
    def setUpClass(cls):
        cls.base, cls.t = copy_piloto("u3")
        cls.fail_out = SENTINEL + "\n" + "\n".join("G%d ok: ruído %02d" % (i % 9, i) for i in range(20)) + "\n"
        cls.rc, cls.out, cls.err = apply_in_process(cls.t, ("emit", "validate"), cls.fail_out)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base, ignore_errors=True)

    def test_exit_1_e_restaurou(self):
        self.assertEqual(self.rc, 1, "falha de verificação deve sair 1 (restaurado)\n%s\n%s" % (self.out, self.err))

    def test_progresso_nomeia_o_comando_que_falhou(self):
        """No fluxo de progresso (stdout, onde estão as linhas `verificando:`), a etapa que falhou aparece
        como falha, com o comando — hoje o stdout termina em `harness validate ...: ok` e cala."""
        tail = self.out.split("verificando:", 1)[-1]
        lines = [l for l in tail.splitlines() if "emit validate" in l]
        self.assertTrue(lines and any(re.search(r"FALH|exit 1|erro", l, re.I) for l in lines),
                        "stdout não diz que `cs.py emit validate` falhou:\n%s" % tail[-1500:])

    def test_progresso_traz_a_saida_do_comando(self):
        self.assertTrue(SENTINEL in self.out,
                        "a saída do comando que falhou (linha do motivo) não aparece no stdout do upgrade; "
                        "fim do stdout:\n%s" % self.out[-400:])

    def test_motivo_nao_truncado(self):
        """A linha que explica a falha não pode ser cortada por um tail de N linhas (hoje _tail(n=8))."""
        both = self.out + "\n" + self.err
        self.assertTrue(SENTINEL in both, "linha do motivo perdida (truncada) em stdout+stderr; stderr:\n%s"
                        % self.err[-800:])


# ------------------------------------------------------------------ U-4 rollback completo / resíduo

class TestU4RollbackCompleto(unittest.TestCase):

    def setUp(self):
        self.base, self.t = copy_piloto("u4")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_falha_restaurada_nao_deixa_swarm(self):
        """Falha induzida na verificação → restaura: `.swarm/` não existe, o legado volta inteiro e o plano
        seguinte não acusa BLOQUEIO."""
        before = sha_tree(os.path.join(self.t, LEGACY), PRESERVED + (os.path.join("state", "board.json5"),
                                                                     os.path.join("state", "events.jsonl")))
        rc, out, err = apply_in_process(self.t, ("emit", "validate"), SENTINEL + "\n")
        self.assertEqual(rc, 1, out + err)
        self.assertFalse(os.path.lexists(os.path.join(self.t, NEW)),
                         "resíduo depois do rollback: %s" % sorted(
                             os.path.relpath(os.path.join(d, f), self.t)
                             for d, _, fs in os.walk(os.path.join(self.t, NEW)) for f in fs)[:10])
        after = sha_tree(os.path.join(self.t, LEGACY), PRESERVED + (os.path.join("state", "board.json5"),
                                                                    os.path.join("state", "events.jsonl")))
        self.assertEqual(before, after, "rollback não devolveu o legado byte a byte")
        rc, pout, perr = cs(self.t, "upgrade")
        self.assertEqual(rc, 0, perr)
        self.assertFalse("BLOQUEIO" in pout, "plano bloqueado depois de um rollback: %s"
                         % [l for l in pout.splitlines() if "BLOQUEIO" in l])

    def test_selftest_no_legado_nao_cria_swarm(self):
        """Origem do resíduo observado: `cs.py harness selftest` num alvo ainda legado cria
        `.swarm/state/selftest.json5` (e sai 1 com stderr vazio). Comando da skill num alvo legado não cria
        `.swarm/` — opera no legado ou recusa dizendo para rodar `cs.py upgrade`."""
        rc, out, err = cs(self.t, "harness", "selftest")
        self.assertFalse(os.path.lexists(os.path.join(self.t, NEW)),
                         "`harness selftest` no legado criou %s/ (rc=%d)" % (NEW, rc))
        if rc != 0:
            self.assertTrue((err.strip() or out.strip()), "selftest falhou sem motivo")
            self.assertTrue("upgrade" in out + err, "recusa no legado deve apontar `cs.py upgrade`")

    def test_residuo_proprio_nao_bloqueia_upgrade(self):
        """Com o resíduo próprio da skill (`.swarm/state/selftest.json5`, só isso) junto do legado, o plano não
        acusa BLOQUEIO e o --apply não é recusado com exit 3."""
        cs(self.t, "harness", "selftest")
        res = os.path.join(self.t, NEW, "state", "selftest.json5")
        if not os.path.isfile(res):                      # comando já corrigido: planta o resíduo observado no real
            os.makedirs(os.path.dirname(res), exist_ok=True)
            with open(res, "w", encoding="utf-8") as fh:
                fh.write('// selftest do motor\n{ok: false, failures: ["pre-commit"]}\n')
        rc, out, err = cs(self.t, "upgrade")
        self.assertEqual(rc, 0, err)
        self.assertFalse("BLOQUEIO" in out, "resíduo próprio bloqueou o plano: %s"
                         % [l for l in out.splitlines() if "BLOQUEIO" in l])
        rc, out, err = cs(self.t, "upgrade", "--apply", "--allow-outside")
        self.assertNotEqual(rc, 3, "upgrade recusado pelo resíduo próprio:\n%s" % err[-800:])


# ------------------------------------------------------------------ U-5 causa raiz: upgrade real conclui

class TestU5UpgradePilotoConclui(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.base, cls.t = copy_piloto("u5")
        lg = os.path.join(cls.t, LEGACY)
        cls.keep = sha_tree(lg, PRESERVED)
        with open(os.path.join(lg, "state", "events.jsonl"), "rb") as fh:
            cls.events_before = fh.read()
        cls.board = load5(os.path.join(lg, "state", "board.json5"))
        cls.rc, cls.out, cls.err = cs(cls.t, "upgrade", "--apply", "--allow-outside")
        cls.sd = os.path.join(cls.t, NEW)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base, ignore_errors=True)

    def _ok(self):
        self.assertEqual(self.rc, 0, "upgrade do repositório-piloto falhou (exit %d):\n%s\n%s"
                         % (self.rc, self.out[-600:], self.err[-1500:]))

    def test_upgrade_exit_0_com_emit_validate_ok(self):
        self._ok()
        self.assertTrue("cs.py emit validate: ok" in self.out, self.out[-400:])

    def test_emit_validate_verde_depois(self):
        self._ok()
        rc, out, err = cs(self.t, "emit", "validate")
        self.assertEqual(rc, 0, out[-1200:] + err[-600:])

    def test_emitidos_sem_caminho_legado(self):
        """Causa raiz: team.json5 (dado preservado) cita `.specialists/bin/cs-mem`; o emit o copia para
        .claude/rules/cs-dev-*.md e a passada de resíduo do rename-dir reescreve o emitido depois do emit,
        quebrando o hash do manifesto (G7). Requisito: emitidos coerentes com o manifesto E sem caminho legado
        (o comando citado tem de existir em .swarm/bin/)."""
        self._ok()
        man = load5(os.path.join(self.sd, "emit", "manifest.json5"))
        bad = []
        for f in man.get("files") or []:
            p = os.path.join(self.t, f["path"])
            if os.path.isfile(p):
                with open(p, "r", encoding="utf-8", errors="replace") as fh:
                    if LEGACY_RE.search(fh.read()):
                        bad.append(f["path"])
        self.assertEqual(bad, [], "emitidos ainda citam %s/: %s" % (LEGACY, bad))
        self.assertTrue(os.path.isfile(os.path.join(self.sd, "bin", "cs-mem")))

    def test_legado_movido_e_hook_aponta_para_swarm(self):
        self._ok()
        self.assertFalse(os.path.lexists(os.path.join(self.t, LEGACY)))
        hook = os.path.join(self.t, ".git", "hooks", "pre-commit")
        self.assertTrue(os.path.isfile(hook), "pre-commit quebrado")
        self.assertTrue(os.path.realpath(hook).startswith(os.path.realpath(self.sd) + os.sep))

    def test_run_registra_versao(self):
        self._ok()
        run = load5(os.path.join(self.sd, "run.json5"))
        with open(os.path.join(SKILL, "VERSION")) as fh:
            v = fh.read().strip()
        self.assertEqual(run.get("skill_version"), v)
        self.assertEqual((run.get("upgrade_history") or [{}])[-1].get("to"), v)

    def test_preservados_byte_a_byte(self):
        """entrevista, aprovações (roster e cartões), cards/status.json5 e memória: idênticos ao legado."""
        self._ok()
        self.assertEqual(self.keep, sha_tree(self.sd, PRESERVED))

    def test_cadeia_de_eventos_preservada(self):
        self._ok()
        with open(os.path.join(self.sd, "events.jsonl"), "rb") as fh:
            now = fh.read()
        self.assertTrue(now.startswith(self.events_before), "events.jsonl legado não é prefixo da cadeia nova")
        self.assertGreater(len(now), len(self.events_before))
        rc, out, err = cs(self.t, "harness", "validate", "--strict", "--allow-empty")
        self.assertEqual(rc, 0, out[-800:] + err[-400:])

    def test_arvore_tem_todo_item_legado_e_tasks_em_andamento(self):
        """Todo épico/feature/story do board legado vira item da árvore (legacy_id) e a story de cada task
        legada lista a task em legacy_tasks (KEY/OPS/AGT/QA em andamento)."""
        self._ok()
        tree = {}
        for z in ("backlog", "state", "archive"):
            for d, _, fs in os.walk(os.path.join(self.sd, z)):
                for f in fs:
                    if f.endswith(".json5"):
                        it = load5(os.path.join(d, f))
                        if isinstance(it, dict) and it.get("legacy_id"):
                            tree[it["legacy_id"]] = it
        want = [x["id"] for k in ("epics", "features", "stories") for x in self.board.get(k) or []]
        self.assertEqual(sorted(set(want) - set(tree)), [], "itens legados sem item na árvore")
        for t in self.board.get("tasks") or []:
            st = tree.get(t.get("story")) or {}
            self.assertIn(t["id"], st.get("legacy_tasks") or [], "task %s fora da árvore" % t["id"])

    def test_estado_das_tasks_e_stories_preservado_na_projecao(self):
        """status de cada task legada (ACCEPTED/BLOCKED/REJECTED/READY) e estado de cada story
        (IN_PROGRESS/IN_REVIEW...) continuam no motor depois da migração."""
        self._ok()
        proj = load5(os.path.join(self.sd, ".engine", "projection.json5"))
        got_t = {t["id"]: t.get("status") for t in proj.get("tasks") or []}
        got_s = {s["id"]: s.get("state") for s in proj.get("stories") or []}
        self.assertEqual(got_t, {t["id"]: t.get("status") for t in self.board.get("tasks") or []})
        self.assertEqual(got_s, {s["id"]: s.get("state") for s in self.board.get("stories") or []})


if __name__ == "__main__":
    unittest.main()
