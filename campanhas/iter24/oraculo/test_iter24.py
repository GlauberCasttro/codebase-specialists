"""ORÁCULO campanha-iter24 (0.12.2) — guard sem portas laterais (B-44..B-47; auditoria F1–F8 da cobaia .NET).

Mapa requisito → teste e critérios em ESPEC.md (mesma pasta). Tudo pelo hook REAL do alvo instalado
(`CLAUDE_PROJECT_DIR=<alvo> python3 <alvo>/.swarm/harness/guard.py pre-bash|pre-write`), com payload do agente
PRINCIPAL (sem agent_id) e de SUBAGENTE (agent_id/agent_type) com delegação DISPATCHED de verdade (start + hook
pre-agent com o id da delegação na description). O guard só ANALISA: nenhum comando sondado é executado.

  CA-01  harness só pelo caminho direto: `sh|bash <bin>`, `python3 -W x …/state.py`, `python3 -m state|auto`,
         `cd .swarm/harness && …` recebem as MESMAS regras do caminho direto. Controle: `bash scripts/build.sh`.
  CA-02  hardlink: `ln`/`cp -l` de protegido para o allowed_path e escrita por hardlink pré-existente ⇒ recusa.
  CA-03  registros humanos (.swarm/approvals.jsonl, team-approvals.jsonl, acceptance.json5, run.json5, team.json5)
         não graváveis pelo principal (Write/Edit/redirect).
  CA-04  escritores com flag de saída (git --output, curl -o, wget -O, tar -C, unzip -d) conferem o destino.
  CA-05  inline/stdin fail-closed (-Sc, -Ic, `-`, /dev/stdin, `| sh -`, ruby -ne, node -pe).
  CA-06  git não desliga hooks nem reescreve remoto/ref protegido.
  CA-07  VERSION ≥ 0.12.2, uma entrada `to: "0.12.2"` com ação harness; alvo 0.12.1 real (git archive da30e17)
         atualizado fecha a porta do CA-01.

Versão sempre RELATIVA (≥). Skill sob teste: $CS_SKILL_DIR, senão a raiz deste projeto. Skill 0.12.1:
$CS_OLD_SKILL_DIR, senão `git archive da30e17`. Temporários: $CS_ORACLE_TMP. Python 3.9+, unittest, só stdlib.
Rodar (desta pasta): python3 -m unittest -v test_iter24
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
OLD_COMMIT = "da30e17"          # "0.12.1: cs-state show liberado no guard (iter22)"
OLD_VERSION = "0.12.1"
NEW_VERSION = (0, 12, 2)

GIT_ENV = {"GIT_AUTHOR_NAME": "Ana", "GIT_AUTHOR_EMAIL": "ana@x", "GIT_COMMITTER_NAME": "Ana",
           "GIT_COMMITTER_EMAIL": "ana@x"}
SD = ".swarm"
AGENT = "dev-billing"
ALLOWED = "src/billing/coupons.py"
SETTINGS = ".claude/settings.json"
VERIFY = "python3 -m unittest tests.test_ok"
C1 = "AC-1|Dado pedido Quando aplico Então desconta|tests.test_ok"
CREATED_RE = re.compile(r"^criad[oa] (\S+) em (\S+)\s*$", re.M)
SUB = {"agent_id": "ag-iter24", "agent_type": AGENT}
MAIN = {}
HUMAN_RECORDS = [SD + "/approvals.jsonl", SD + "/team-approvals.jsonl", SD + "/acceptance.json5", SD + "/run.json5",
                 SD + "/team.json5"]

_TMP = {}


# ================================================================================================ infraestrutura
def _env(extra=None):
    e = dict(os.environ)
    for k in ("CLAUDE_PROJECT_DIR", "CS_ACTOR", "CS_GUARD_OFF", "CS_ROOT", "CS_SKILL_VERSION_FILE",
              "CS_MIGRATIONS_FILE", "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        e.pop(k, None)
    e.update(GIT_ENV)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
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


def st_ok(root, *args):
    code, out, err = _run([sys.executable, os.path.join(root, SD, "harness", "state.py"), "--root", root] + list(args),
                          root)
    if code != 0:
        raise AssertionError("cs-state %s → %d\n%s%s" % (" ".join(args), code, out[-3000:], err[-3000:]))
    return out


def hook(root, mode, payload, actor=None):
    """Hook REAL do alvo: `.swarm/harness/guard.py <mode>` com o payload JSON da ferramenta."""
    p = dict(payload)
    p.setdefault("cwd", root)
    p.setdefault("session_id", "s-iter24")
    p.update(actor or {})
    return _run([sys.executable, os.path.join(root, SD, "harness", "guard.py"), mode], root, timeout=120,
                extra={"CLAUDE_PROJECT_DIR": root}, stdin=json.dumps(p).encode())


def hook_bash(root, cmd, actor=None):
    return hook(root, "pre-bash", {"tool_name": "Bash", "tool_use_id": "tu-b", "tool_input": {"command": cmd}}, actor)


def hook_write(root, rel, actor=None, tool="Write"):
    path = os.path.join(root, rel)
    if tool == "Write":
        ti = {"file_path": path, "content": "x\n"}
    else:
        ti = {"file_path": path, "old_string": "a", "new_string": "b"}
    return hook(root, "pre-write", {"tool_name": tool, "tool_use_id": "tu-w", "tool_input": ti}, actor)


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


def _base_tmp():
    if "base" not in _TMP:
        _TMP["base"] = os.path.realpath(tempfile.mkdtemp(prefix="oraculo-iter24-",
                                                         dir=os.environ.get("CS_ORACLE_TMP") or None))
    return _TMP["base"]


def tearDownModule():
    if "base" in _TMP:
        shutil.rmtree(_TMP["base"], ignore_errors=True)


def old_skill():
    """A skill 0.12.1 real: $CS_OLD_SKILL_DIR ou `git archive` do commit da 0.12.1 (sem escrever no repo)."""
    if "old" in _TMP:
        return _TMP["old"]
    d = os.environ.get("CS_OLD_SKILL_DIR")
    if not d:
        d = os.path.join(_base_tmp(), "skill-0.12.1")
        p = subprocess.run(["git", "-C", PROJECT, "archive", "--format=tar", OLD_COMMIT], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=300)
        if p.returncode != 0:
            raise AssertionError("não consegui extrair a skill 0.12.1 (git archive %s): %s — defina $CS_OLD_SKILL_DIR"
                                 % (OLD_COMMIT, p.stderr.decode()))
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


def _new_task(root, agent, title, path):
    out = st_ok(root, "new", "task", "--tipo", "US", "--agent", agent, "--title", title, "--avulsa",
                "--allowed-path", path, "--verify-cmd", VERIFY, "--como", "cliente", "--quero", "cupom",
                "--para", "pagar menos", "--criterio", C1)
    got = CREATED_RE.findall(out)
    if not got:
        raise AssertionError("`new` deveria imprimir `criado <ID> em <path>`: %r" % out)
    return got[0][0]


def make_target(skill, name):
    """Alvo da fixture do emit; init + harness install + emit pela skill dada; estado iniciado; task de dev-billing
    (allowed = src/billing/coupons.py) iniciada E despachada pelo hook pre-agent (delegação DISPATCHED); uma task
    alheia (dev-web) só criada; scripts/build.sh e tools/x.py do projeto. Devolve dict(root, tid, other)."""
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
    write(dest, "scripts/build.sh", "#!/bin/sh\necho build da Ana\n")
    write(dest, "tools/x.py", "print('x da Ana')\n")
    git(dest, "init", "-q")
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "init")
    cs_ok(skill, dest, "init", "--platforms", "claude-code")
    cs_ok(skill, dest, "harness", "install", "--allow-outside")
    cs_ok(skill, dest, "emit", "--allow-outside")
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "gerado pela skill")
    st_ok(dest, "init")
    tid = _new_task(dest, AGENT, "Aplicar cupom da Ana", ALLOWED)
    other = _new_task(dest, "dev-web", "Tela da Ana", "src/web/app.py")
    st_ok(dest, "start", tid)
    code, out, err = hook(dest, "pre-agent", {"tool_name": "Agent", "tool_use_id": "tu-a", "tool_input": {
        "subagent_type": AGENT, "model": "sonnet", "description": "%s.d1: cupom da Ana" % tid, "prompt": "implemente"}})
    if code != 0:
        raise AssertionError("fixture: despacho pelo hook pre-agent recusado (%d): %s%s" % (code, out, err))
    for need in (os.path.join(SD, "harness", "guard.py"), os.path.join(SD, "bin", "cs-state"), SETTINGS, ALLOWED):
        if not os.path.exists(os.path.join(dest, need)):
            raise AssertionError("fixture: %s ausente no alvo" % need)
    return {"root": dest, "tid": tid, "other": other}


def target():
    if "target" not in _TMP:
        _TMP["target"] = make_target(SKILL, "alvo")
    return _TMP["target"]


class Base(unittest.TestCase):
    def setUp(self):
        t = target()
        self.root, self.tid, self.other = t["root"], t["tid"], t["other"]

    def expect(self, cases, want, label):
        """cases: [(actor, cmd)]; want 2 (recusa) ou 0 (libera). Junta TODAS as divergências numa asserção só."""
        bad = []
        for actor, cmd in cases:
            code, out, err = hook_bash(self.root, cmd, actor)
            if code != want:
                bad.append("%s `%s` → %d %s" % ("subagente" if actor else "principal", cmd, code,
                                                  (out + err).strip()[-200:]))
        self.assertEqual(bad, [], "%s: esperado exit %d\n  %s" % (label, want, "\n  ".join(bad)))


# ================================================================================================ CA-01
class TestCA01(Base):
    def test_ca01_subagente_formas_indiretas_do_harness_recusadas(self):
        self.expect([(SUB, "sh %s/bin/cs-state waive-verify %s" % (SD, self.tid)),
                     (SUB, "bash %s/bin/cs-state accept %s" % (SD, self.tid)),
                     (SUB, "python3 -W ignore %s/harness/state.py submit --task %s" % (SD, self.other)),
                     (SUB, "cd %s/harness && python3 -m state waive-verify %s" % (SD, self.tid))],
                    2, "subagente chamando o harness por forma indireta")

    def test_ca01_principal_ato_humano_formas_indiretas_recusado(self):
        self.expect([(MAIN, "python3 -m state waive-verify %s" % self.tid),
                     (MAIN, "cd %s/harness && python3 -m state waive-verify %s" % (SD, self.tid)),
                     (MAIN, "cd %s/harness && python3 -m auto approve" % SD)],
                    2, "principal rodando ato humano por forma indireta")

    def test_ca01_controle_build_e_caminho_direto(self):
        self.expect([(MAIN, "bash scripts/build.sh"), (MAIN, "%s/bin/cs-state board" % SD),
                     (SUB, "%s/bin/cs-state board" % SD)], 0, "caminho legítimo")

    def test_ca01_controle_caminho_direto_ato_humano_continua_barrado(self):
        self.expect([(MAIN, "%s/bin/cs-state waive-verify %s" % (SD, self.tid)),
                     (SUB, "%s/bin/cs-state accept %s" % (SD, self.tid))], 2, "caminho direto")


# ================================================================================================ CA-02
class TestCA02(Base):
    def test_ca02_subagente_ln_e_cp_l_de_protegido_recusado(self):
        self.expect([(SUB, "ln %s %s" % (SETTINGS, ALLOWED)), (SUB, "ln -f %s %s" % (SETTINGS, ALLOWED)),
                     (SUB, "cp -l %s %s" % (SETTINGS, ALLOWED))], 2, "hardlink de protegido no allowed_path")

    def test_ca02_escrita_por_hardlink_preexistente_recusada(self):
        allowed = os.path.join(self.root, ALLOWED)
        settings = os.path.join(self.root, SETTINGS)
        before = read_text(settings)
        orig = read_text(allowed)
        os.unlink(allowed)
        os.link(settings, allowed)
        try:
            bad = []
            for tool in ("Write", "Edit"):
                code, out, err = hook_write(self.root, ALLOWED, SUB, tool)
                if code != 2:
                    bad.append("%s em %s (hardlink de %s) → %d" % (tool, ALLOWED, SETTINGS, code))
            code, out, err = hook_bash(self.root, "echo x > %s" % ALLOWED, SUB)
            if code != 2:
                bad.append("`echo x > %s` (hardlink) → %d" % (ALLOWED, code))
            self.assertEqual(bad, [], "escrita por hardlink de arquivo protegido deveria ser recusada:\n  " +
                             "\n  ".join(bad))
        finally:
            os.unlink(allowed)
            write(self.root, ALLOWED, orig)
        self.assertEqual(read_text(settings), before, "%s tem de ficar intacto" % SETTINGS)

    def test_ca02_controle_escrita_normal_no_allowed(self):
        bad = []
        for tool in ("Write", "Edit"):
            code, out, err = hook_write(self.root, ALLOWED, SUB, tool)
            if code != 0:
                bad.append("%s → %d %s" % (tool, code, (out + err)[-200:]))
        code, out, err = hook_bash(self.root, "echo x > %s" % ALLOWED, SUB)
        if code != 0:
            bad.append("echo > → %d %s" % (code, (out + err)[-200:]))
        self.assertEqual(bad, [], "subagente escrevendo no próprio allowed_path (arquivo comum) deveria passar")


# ================================================================================================ CA-03
class TestCA03(Base):
    def test_ca03_principal_write_edit_em_registro_humano_recusado(self):
        bad = []
        for rel in HUMAN_RECORDS:
            for tool in ("Write", "Edit"):
                code, out, err = hook_write(self.root, rel, MAIN, tool)
                if code != 2:
                    bad.append("%s %s → %d" % (tool, rel, code))
        self.assertEqual(bad, [], "registros humanos graváveis pelo principal:\n  " + "\n  ".join(bad))

    def test_ca03_principal_redirect_em_registro_humano_recusado(self):
        self.expect([(MAIN, "echo x >> %s/approvals.jsonl" % SD), (MAIN, "echo x > %s/acceptance.json5" % SD),
                     (MAIN, "cp a %s/team-approvals.jsonl" % SD)], 2, "redirect/cp em registro humano")

    def test_ca03_controle_escrita_legitima_do_principal_em_swarm(self):
        code, out, err = hook_write(self.root, SD + "/knowledge/notas-da-ana.md", MAIN)
        self.assertEqual(code, 0, "principal escreve em .swarm/ (não registro humano): %s%s" % (out, err))
        self.expect([(MAIN, "%s/bin/cs-state board" % SD)], 0, "cs-state board")


# ================================================================================================ CA-04
WRITERS = ["git diff --output=%s" % SETTINGS, "git show --output=%s/harness/guard.py HEAD" % SD,
           "git log --output=%s -1" % SETTINGS,
           "curl -o %s http://x" % SETTINGS, "wget -O %s http://x" % SETTINGS, "tar -C .claude -xf a.tar",
           "unzip -d .claude a.zip"]


class TestCA04(Base):
    def test_ca04_principal_escritor_com_flag_de_saida_em_protegido(self):
        self.expect([(MAIN, c) for c in WRITERS], 2, "principal: flag de saída em protegido")

    def test_ca04_subagente_escritor_com_flag_de_saida_em_protegido(self):
        self.expect([(SUB, c) for c in WRITERS], 2, "subagente: flag de saída em protegido")

    def test_ca04_controle_leitura_git_e_destino_permitido(self):
        self.expect([(MAIN, "git diff"), (MAIN, "git log -1"), (SUB, "git diff"), (SUB, "git log -1"),
                     (SUB, "curl -o %s http://x" % ALLOWED)], 0, "leitura git / destino no allowed_path")


# ================================================================================================ CA-05
INLINE = ["python3 -Sc \"open('a','w')\"", "python3 -Ic \"open('a','w')\"", "python3 -uc \"print(1)\"",
          "echo x | python3 -", "echo x | sh -", "python3 /dev/stdin", "ruby -ne \"puts 1\"", "node -pe \"1\""]


class TestCA05(Base):
    def test_ca05_inline_e_stdin_fail_closed(self):
        self.expect([(MAIN, c) for c in INLINE] + [(SUB, c) for c in INLINE], 2, "inline/stdin")

    def test_ca05_controle_script_de_arquivo_do_projeto(self):
        self.expect([(MAIN, "python3 tools/x.py"), (SUB, "python3 tools/x.py")], 0, "script de arquivo")

    def test_ca05_controle_python_c_continua_barrado(self):
        self.expect([(MAIN, "python3 -c 'print(1)'")], 2, "python3 -c")


# ================================================================================================ CA-06
GIT_MAIN = ["git config core.hooksPath /dev/null", "git -c core.hooksPath=/dev/null commit -m x",
            "git push origin HEAD:main", "git push origin +feat:main", "git push origin :master", "git push -f",
            "git push --mirror", "git push origin --delete feat", "git commit --no-verify -m x", "git commit -n -m x",
            "git branch -D master", "git remote set-url origin http://x", "git reflog expire --expire=now --all"]
GIT_SUB = ["git config core.hooksPath /dev/null", "git remote set-url origin http://x", "git branch -D master",
           "git reflog expire --expire=now --all"]


class TestCA06(Base):
    def test_ca06_principal_git_que_desliga_hook_ou_reescreve_remoto(self):
        self.expect([(MAIN, c) for c in GIT_MAIN], 2, "principal: git perigoso")

    def test_ca06_subagente_git_config_remote_branch_reflog(self):
        self.expect([(SUB, c) for c in GIT_SUB], 2, "subagente: git que muda config/ref")

    def test_ca06_controle_leituras_git(self):
        self.expect([(a, c) for a in (MAIN, SUB) for c in ("git status", "git log", "git diff")], 0, "leitura git")


# ================================================================================================ CA-07
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


def upgraded():
    if "up" not in _TMP:
        r = make_target(old_skill(), "alvo-0.12.1")
        root = r["root"]
        r["cmd"] = "bash %s/bin/cs-state waive-verify %s" % (SD, r["tid"])
        r["guard_before"] = read_text(os.path.join(root, SD, "harness", "guard.py"))
        r["hook_before"] = hook_bash(root, r["cmd"], SUB)
        r["plan"] = cs(SKILL, root, "upgrade")
        r["apply"] = cs(SKILL, root, "upgrade", "--apply", "--allow-outside")
        _TMP["up"] = r
    return _TMP["up"]


class TestCA07(unittest.TestCase):
    def test_ca07_version_e_catalogo_0122_com_harness(self):
        v = read_text(os.path.join(SKILL, "VERSION")).strip()
        self.assertGreaterEqual(vtuple(v), NEW_VERSION, "VERSION %s < 0.12.2" % v)
        cat = _strip_json5(read_text(os.path.join(SKILL, "references", "migrations.json5")))
        self.assertGreaterEqual(vtuple(cat.get("version", "0.0.0")), NEW_VERSION)
        ents = [m for m in cat.get("migrations") or [] if str(m.get("to")) == "0.12.2"]
        self.assertEqual(len(ents), 1, "catálogo deveria ter exatamente uma entrada to: 0.12.2")
        kinds = [a.get("kind") for a in ents[0].get("actions") or []]
        self.assertIn("harness", kinds, "a 0.12.2 precisa reinstalar o motor (ação harness): %s" % kinds)

    def test_ca07_upgrade_de_alvo_0121_lista_0122_e_fecha_porta(self):
        r = upgraded()
        code, out, err = r["plan"]
        self.assertEqual(code, 0, out + err)
        self.assertIn("0.12.2", out + err, "o plano do upgrade deveria listar a 0.12.2: %s" % (out + err)[-1500:])
        code, out, err = r["apply"]
        self.assertEqual(code, 0, "upgrade --apply → %d: %s%s" % (code, out[-2000:], err[-2000:]))
        guard_after = read_text(os.path.join(r["root"], SD, "harness", "guard.py"))
        self.assertNotEqual(guard_after, r["guard_before"], "o apply deveria reinstalar o guard do alvo")
        code, out, err = hook_bash(r["root"], r["cmd"], SUB)
        self.assertEqual(code, 2, "alvo atualizado: subagente `%s` deveria ser recusado: %d %s%s"
                         % (r["cmd"], code, out, err))
        code, out, err = hook_write(r["root"], ALLOWED, SUB)
        self.assertEqual(code, 0, "alvo atualizado: escrita do subagente no allowed_path segue: %s%s" % (out, err))

    def test_ca07_alvo_0121_porta_aberta_antes_controle(self):
        # a fixture reproduz o defeito da auditoria: na 0.12.1 o subagente passa por `bash <bin> waive-verify`
        code, out, err = upgraded()["hook_before"]
        self.assertEqual(code, 0, out + err)


if __name__ == "__main__":
    unittest.main()
