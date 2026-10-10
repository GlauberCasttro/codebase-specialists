"""Oráculo de aceite da feature win-harness — harness de desenvolvimento no Windows nativo, sem o atalho `python3`.

Escrito por um agente SEPARADO de quem corrige (quem testa não constrói). Uma classe `TestCA<NN>` por CA do FEATURE.md
(filtro `-k CA<NN>`). Cada classe CA01..CA13 FALHA hoje no Windows nativo pelo motivo do defeito e passa quando a
entrega estiver feita; os testes `test_calibracao_*` passam hoje e continuam passando (provam que a classe não está
vermelha por acaso: a saída boa conhecida passa e a saída vazia/errada reprova). CA14 roda no WSL/macOS/Linux e passa
hoje (regressão). Contrato, ambiente simulado e RED medido: ESPEC.md.

unittest puro, stdlib, Python 3.9+. Variáveis (env do processo de teste):
  CS_DEV_SKILL_DIR  raiz do projeto testado; senão ORACULO_SKILL; senão CS_SKILL_DIR (a cópia limpa do portão);
                    senão três pastas acima deste arquivo.
  ORACULO_GIT_RAIZ  raiz do Git for Windows (padrão: achada a partir do `git` do PATH; senão %ProgramFiles%\\Git).

Ambiente "sem atalho" (Windows): o PATH de cada subprocesso é montado AQUI só com a pasta do Python real
(`sys.executable`), `<Git>\\cmd`, `<Git>\\usr\\bin` e `System32`, sem PYTHONUTF8/PYTHONIOENCODING; HOME e USERPROFILE
apontam para um perfil temporário. O bash é sempre o do Git, por caminho explícito (nunca `bash` do PATH: no Windows
cai no WSL). Tudo em `tempfile.mkdtemp()`, apagado no fim; nada é escrito no projeto nem no perfil real. Nenhum teste
roda `gate`, `preauth` nem `frase` do motor: o comando de aprovação do CA01 é uma STRING de payload entregue ao hook.
"""
import importlib
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.dont_write_bytecode = True

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.realpath(
    os.environ.get("CS_DEV_SKILL_DIR")
    or os.environ.get("ORACULO_SKILL")
    or os.environ.get("CS_SKILL_DIR")
    or os.path.join(AQUI, "..", "..", "..")
)
TOOLS = os.path.join(RAIZ, ".claude", "tools")
AC = os.path.join(TOOLS, "ac", "ac.py")
SETTINGS = os.path.join(RAIZ, ".claude", "settings.json")
WINDOWS = os.name == "nt"
PY = os.path.realpath(sys.executable)
PYDIR = os.path.dirname(PY)
POSIX_2PY = (not WINDOWS) and bool(shutil.which("python3")) and os.path.isfile("/usr/bin/python3")
NOME = "codebase-specialists"
HOOKS_PY = ("hook_aprovacao.py", "guard-entrega.py", "guard-estado.py", "exige-modelo.py")
IO_REPARSE_TAG_MOUNT_POINT = 0xA0000003
SO_WINDOWS = "só no Windows nativo (o defeito e a correção são do Windows; no WSL/macOS/Linux vale o CA14)"
SO_POSIX = "só no WSL/macOS/Linux (python3 e /usr/bin/python3): o Windows nativo é medido pelos CA01..CA13"


# ------------------------------------------------------------------ utilitários

def _dec(b):
    return (b or b"").decode("utf-8", "replace")


def win(p):
    """Caminho para entregar a um script bash: no Windows, barras normais (C:/...) — o MSYS e o Python aceitam."""
    return p.replace("\\", "/") if WINDOWS else p


def norm_cmd(s):
    """Normaliza caminho/comando para comparação: minúsculas, barras normais, /c/... → c:/..."""
    s = s.strip().strip("'\"").replace("\\", "/").lower()
    m = re.match(r"^/([a-z])/(.*)$", s)
    return "%s:/%s" % (m.group(1), m.group(2)) if m else s


def git_raiz():
    cands = []
    if os.environ.get("ORACULO_GIT_RAIZ"):
        cands.append(os.environ["ORACULO_GIT_RAIZ"])
    g = shutil.which("git")
    if g:
        d = os.path.dirname(os.path.realpath(g))
        cands += [os.path.dirname(d), os.path.dirname(os.path.dirname(d))]
    cands.append(os.path.join(os.environ.get("ProgramFiles") or r"C:\Program Files", "Git"))
    for c in cands:
        if c and os.path.isfile(os.path.join(c, "usr", "bin", "bash.exe")) and \
                os.path.isfile(os.path.join(c, "cmd", "git.exe")):
            return os.path.realpath(c)
    return None


def sys32():
    return os.path.join(os.environ.get("SystemRoot") or os.environ.get("SYSTEMROOT") or r"C:\Windows", "System32")


def env_base(perfil=None, **extra):
    """Ambiente do processo menos o que desvia a medição (UTF-8 forçado, variáveis do harness e do Claude)."""
    tira = ("PYTHONUTF8", "PYTHONIOENCODING", "PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "BASH_ENV", "ENV")
    e = {k: v for k, v in os.environ.items()
         if k.upper() not in tira and not k.upper().startswith(("CS_", "CLAUDE_"))}
    if perfil:
        e["HOME"] = perfil
        e["USERPROFILE"] = perfil
    e.update({k: v for k, v in extra.items() if v is not None})
    return e


def rodar(argv, env, cwd=None, stdin=b"", timeout=600):
    p = subprocess.run(argv, input=stdin, env=env, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def escrever(base, rel, txt, modo=None):
    p = os.path.join(base, *rel.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as fh:
        fh.write(txt.encode("utf-8"))
    if modo:
        os.chmod(p, modo)
    return p


def git(d, *args, env=None):
    p = subprocess.run(["git", "-C", d, "-c", "user.name=Ana", "-c", "user.email=ana@exemplo.invalid",
                        "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false"] + list(args),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env or env_base())
    if p.returncode != 0:
        raise AssertionError("git %s falhou: %s" % (" ".join(args), _dec(p.stderr)))
    return _dec(p.stdout)


def repo_skill(d, arquivos, env=None):
    """Repositório git temporário com os arquivos dados, commitado (HEAD existe)."""
    os.makedirs(d, exist_ok=True)
    for rel, txt in arquivos.items():
        escrever(d, rel, txt)
    git(d, "init", "-q", env=env)
    git(d, "add", "--", *sorted(arquivos), env=env)
    git(d, "commit", "-qm", "base do oráculo", env=env)
    return d


def decisao_hook(out):
    for ln in reversed(out.strip().splitlines()):
        ln = ln.strip()
        if ln.startswith("{"):
            try:
                d = json.loads(ln)
            except ValueError:
                continue
            return (d.get("hookSpecificOutput") or {}).get("permissionDecision")
    return None


def negou(rc, out):
    """Hook negou: exit 2 (bloqueio com motivo no stderr) ou exit 0 com permissionDecision=deny no stdout."""
    return rc == 2 or (rc == 0 and decisao_hook(out) == "deny")


def hook_do_settings(trecho):
    """(matcher, command) da entrada do .claude/settings.json cujo command cita `trecho`."""
    with open(SETTINGS, encoding="utf-8") as fh:
        s = json.load(fh)
    for ms in (s.get("hooks") or {}).values():
        for m in ms:
            for h in m.get("hooks") or []:
                if trecho in (h.get("command") or ""):
                    return m.get("matcher", ""), h["command"]
    return None, None


def payload_negavel(nome):
    return {
        "hook_aprovacao.py": {"tool_name": "Bash", "tool_input": {
            "command": "python3 .claude/tools/ac/ac.py --work campanhas/x gate stop --by Ana --decision approve"}},
        "guard-entrega.py": {"tool_name": "Write", "cwd": RAIZ, "tool_input": {
            "file_path": os.path.join(RAIZ, "SKILL.md"), "content": "x"}},
        "guard-estado.py": {"tool_name": "Write", "cwd": RAIZ, "tool_input": {
            "file_path": os.path.join(RAIZ, ".claude", "state", "features.json"), "content": "{}"}},
        "exige-modelo.py": {"tool_name": "Agent", "tool_input": {
            "description": "01-TASK-ORACULO escrever o oráculo", "prompt": "x", "subagent_type": "general-purpose"}},
    }[nome]


def lista_pythons(out):
    d = json.loads(out)
    if isinstance(d, dict):
        d = d.get("pythons")
    if not isinstance(d, list) or not all(isinstance(x, str) and x.strip() for x in d):
        raise ValueError("esperado {\"pythons\": [str, ...]} ou [str, ...]; veio %r" % (d,))
    return d


def resumo_unittest(txt):
    """(ok, resumo): ok só com 'Ran N tests' (N>0), linha final OK e nenhum FAILED."""
    ran = re.findall(r"^Ran (\d+) tests?", txt, re.M)
    fim = [x for x in txt.splitlines() if x.startswith(("OK", "FAILED"))]
    resumo = "Ran %s · %s" % (ran[-1] if ran else "?", fim[-1] if fim else "SEM RESULTADO")
    ok = bool(ran) and int(ran[-1]) > 0 and bool(fim) and fim[-1].startswith("OK") and "FAILED" not in txt[-400:]
    return ok, resumo


def carimbo_ler(out, camp):
    """(valor da linha `python:`, (feitas, total) da campanha) — None onde faltar."""
    py = [x.strip()[len("python:"):].strip() for x in out.splitlines() if x.strip().startswith("python:")]
    m = re.search(re.escape(camp) + r": etapa \S+ \((\d+)/(\d+) etapas\)", out)
    return (py[0] if py else None), ((int(m.group(1)), int(m.group(2))) if m else None)


def etapas_do_status(txt):
    """(feitas, total) contadas na saída do `ac.py status`: uma linha por etapa; feita = marca ✓."""
    linhas = [x for x in txt.splitlines() if re.match(r"^ (.) ([a-z]+)\s+\d+/\d+\s*$", x)]
    return sum(1 for x in linhas if x[1] == "\u2713"), len(linhas)


def falha_utf8(saida, referencia):
    """None se `saida` (bytes, sem PYTHONUTF8) decodifica como UTF-8 e é idêntica à referência (com PYTHONUTF8=1)."""
    try:
        t = saida.decode("utf-8")
    except UnicodeDecodeError as e:
        return "saída não é UTF-8 (%s)" % e
    r = referencia.decode("utf-8", "replace")
    if t != r:
        i = next((k for k in range(min(len(t), len(r))) if t[k] != r[k]), min(len(t), len(r)))
        return "saída difere da referência UTF-8 a partir do caractere %d: %r ≠ %r" % (i, t[i:i + 40], r[i:i + 40])
    return None


def ps1_passos_ok(txt):
    """Lista de problemas do .ps1: os 3 passos em ordem e, depois de CADA um (antes do próximo), $LASTEXITCODE+throw."""
    passos = ["gate stop", "gate oracle:requisito", "preauth commit"]
    idx = [txt.find(p) for p in passos]
    prob = ["passo ausente: %s" % p for p, i in zip(passos, idx) if i < 0]
    if prob:
        return prob
    if idx != sorted(idx):
        return ["passos fora de ordem: %r" % idx]
    for k, p in enumerate(passos):
        seg = txt[idx[k]: idx[k + 1] if k + 1 < len(idx) else len(txt)]
        if "$LASTEXITCODE" not in seg or "throw" not in seg.lower():
            prob.append("depois de `%s` falta conferir $LASTEXITCODE com throw" % p)
    return prob


def _apagar(d):
    if WINDOWS:   # junções primeiro (rmdir tira só o link), para nunca descer no alvo
        for raiz, dirs, _ in os.walk(d):
            for x in list(dirs):
                p = os.path.join(raiz, x)
                try:
                    if getattr(os.lstat(p), "st_reparse_tag", 0) == IO_REPARSE_TAG_MOUNT_POINT:
                        os.rmdir(p)
                        dirs.remove(x)
                except OSError:
                    pass

    def _erro(fn, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            fn(p)
        except OSError:
            pass
    shutil.rmtree(d, onerror=_erro)


_MODS = {}


def modulo(nome):
    """Importa um tool de <raiz>/.claude/tools pelo nome (feature, estado_lib…); erro vira falha do teste."""
    if nome in _MODS:
        return _MODS[nome]
    if TOOLS not in sys.path:
        sys.path.insert(0, TOOLS)
    m = sys.modules.get(nome)
    if m is not None and os.path.dirname(os.path.realpath(getattr(m, "__file__", "") or "")) != os.path.realpath(TOOLS):
        del sys.modules[nome]
    _MODS[nome] = importlib.import_module(nome)
    return _MODS[nome]


def motor_mod():
    if "ac" not in _MODS:
        spec = importlib.util.spec_from_file_location("ac_oraculo_win_harness", AC)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _MODS["ac"] = m
    return _MODS["ac"]


class _Base(unittest.TestCase):
    maxDiff = 4000

    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="oraculo-win-harness-"))
        self.addCleanup(_apagar, self.tmp)
        self.perfil = os.path.join(self.tmp, "perfil")
        os.makedirs(self.perfil)

    # ---- ambiente
    def git_raiz(self):
        g = git_raiz()
        if not g:
            self.fail("LACUNA de ambiente: Git for Windows (usr\\bin\\bash.exe e cmd\\git.exe) não encontrado; "
                      "defina ORACULO_GIT_RAIZ")
        return g

    def bash(self):
        return os.path.join(self.git_raiz(), "usr", "bin", "bash.exe") if WINDOWS else "bash"

    def _path(self, *antes, com_python=True):
        g = self.git_raiz()
        partes = list(antes) + ([PYDIR] if com_python else []) + \
            [os.path.join(g, "cmd"), os.path.join(g, "usr", "bin"), sys32()]
        return os.pathsep.join(partes)

    def env_sem_atalho(self, **extra):
        """Windows: python sim, python3 não, sem PYTHONUTF8, perfil temporário."""
        path = self._path()
        self.assertIsNone(shutil.which("python3", path=path),
                          "precondição: python3 não pode estar no PATH montado (%s)" % path)
        self.assertTrue(shutil.which("python", path=path), "precondição: python no PATH montado (%s)" % path)
        return env_base(self.perfil, PATH=path, **extra)

    def env_sem_python(self, **extra):
        path = self._path(com_python=False)
        for n in ("python3", "python", "py"):
            self.assertIsNone(shutil.which(n, path=path), "precondição: %s não pode estar no PATH montado" % n)
        return env_base(self.perfil, PATH=path, **extra)

    def env_com_atalho(self, **extra):
        """Windows: o atalho de hoje (~/bin/python3 = sh que chama o python com PYTHONUTF8=1), num diretório
        temporário — a saída boa conhecida da calibração. Fora do Windows: o ambiente normal."""
        if not WINDOWS:
            return env_base(self.perfil, **extra)
        d = os.path.join(self.tmp, "atalho")
        escrever(d, "python3", '#!/bin/sh\nPYTHONUTF8=1 exec python "$@"\n', 0o755)
        return env_base(self.perfil, PATH=self._path(d), **extra)

    def env_nativo(self, **extra):
        return self.env_sem_atalho(**extra) if WINDOWS else env_base(self.perfil, **extra)

    # ---- execução
    def sh_c(self, comando, env, stdin=b"", timeout=120):
        """Roda o `command` de um hook como o Claude Code: no Windows pelo bash do Git; fora, `sh -c`."""
        argv = [self.bash(), "-c", comando] if WINDOWS else ["sh", "-c", comando]
        rc, out, err = rodar(argv, env, cwd=RAIZ, stdin=stdin, timeout=timeout)
        return rc, _dec(out), _dec(err)

    def script(self, nome, args, env, cwd=None, timeout=600):
        argv = [self.bash(), win(os.path.join(TOOLS, nome))] + list(args)
        rc, out, err = rodar(argv, env, cwd=cwd or self.tmp, timeout=timeout)
        return rc, _dec(out), _dec(err)

    def hook(self, nome, payload, env):
        matcher, cmd = hook_do_settings(nome)
        self.assertIsNotNone(cmd, "nenhum hook do settings.json cita %s" % nome)
        return self.sh_c(cmd, dict(env, CLAUDE_PROJECT_DIR=RAIZ), json.dumps(payload).encode("utf-8"))

    def resolver(self, py, path):
        r = shutil.which(py, path=path) or (py if os.path.isfile(py) else None)
        self.assertTrue(r, "interpretador da lista não encontrado no PATH montado: %r" % py)
        return r

    def e2e_pythons(self, env):
        rc, out, err = rodar([PY, os.path.join(TOOLS, "e2e.py"), "pythons", "--json"], env, cwd=RAIZ)
        self.assertEqual(rc, 0, "e2e.py pythons --json: exit %d\nstdout: %s\nstderr: %s"
                         % (rc, _dec(out)[-800:], _dec(err)[-800:]))
        try:
            return lista_pythons(_dec(out))
        except ValueError as e:
            self.fail("e2e.py pythons --json: %s" % e)

    # ---- campanha temporária
    def campanha(self, w, alvo):
        e = env_base(self.perfil, PYTHONUTF8="1")
        rc, out, err = rodar([PY, AC, "--work", w, "init", "--target", alvo, "--scope", "a/**", "--problem", "p",
                              "--stop", "14/14"], e, cwd=alvo)
        self.assertEqual(rc, 0, "ac.py init (fixture): %s" % _dec(err))
        orac = escrever(w, "oraculo/test_fixture.py", "import unittest\n")
        rc, out, err = rodar([PY, AC, "--work", w, "oracle", "freeze", "--file", orac], e, cwd=alvo)
        self.assertEqual(rc, 0, "ac.py oracle freeze (fixture): %s" % _dec(err))
        return w

    def estado(self, w):
        with open(os.path.join(w, ".auto-correcao", "state.json"), encoding="utf-8") as fh:
            return json.load(fh)

    def gravar_estado(self, w, st):
        with open(os.path.join(w, ".auto-correcao", "state.json"), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(st, fh, ensure_ascii=False, indent=1, sort_keys=True)


# ================================================================== CA-01
class TestCA01HooksPythonSemPython3(_Base):
    """CA-01: os 4 hooks Python, pelo comando exato do settings.json, negam sem python3 e saem 2 sem Python algum."""

    def _nega(self, nome):
        rc, out, err = self.hook(nome, payload_negavel(nome), self.env_sem_atalho())
        self.assertNotEqual(rc, 127, "%s: exit 127 (python3 não achado) — o guard ficou ABERTO; stderr: %s"
                            % (nome, err.strip()[-300:]))
        self.assertTrue(negou(rc, out), "%s sem python3 deveria negar; exit %d · stdout %r · stderr %r"
                        % (nome, rc, out[-300:], err[-300:]))

    @unittest.skipUnless(WINDOWS, SO_WINDOWS)
    def test_hook_aprovacao_nega_sem_python3(self):
        self._nega("hook_aprovacao.py")

    @unittest.skipUnless(WINDOWS, SO_WINDOWS)
    def test_guard_entrega_nega_sem_python3(self):
        self._nega("guard-entrega.py")

    @unittest.skipUnless(WINDOWS, SO_WINDOWS)
    def test_guard_estado_nega_sem_python3(self):
        self._nega("guard-estado.py")

    @unittest.skipUnless(WINDOWS, SO_WINDOWS)
    def test_exige_modelo_nega_sem_python3(self):
        self._nega("exige-modelo.py")

    @unittest.skipUnless(WINDOWS, SO_WINDOWS)
    def test_payload_permitido_passa_sem_python3(self):
        """O hook RODA (não é um lançador que sempre sai 2): payload inofensivo passa com exit 0 e sem deny."""
        env = self.env_sem_atalho()
        for nome in HOOKS_PY:
            with self.subTest(hook=nome):
                rc, out, err = self.hook(nome, {"tool_name": "Read", "tool_input": {"file_path": "x"}}, env)
                self.assertEqual(rc, 0, "%s com payload inofensivo, sem python3: exit %d · %r" % (nome, rc, err[-300:]))
                self.assertNotEqual(decisao_hook(out), "deny", "%s negou payload inofensivo: %r" % (nome, out))

    @unittest.skipUnless(WINDOWS, SO_WINDOWS)
    def test_sem_nenhum_python_sai_2_com_motivo(self):
        env = self.env_sem_python()
        for nome in HOOKS_PY:
            with self.subTest(hook=nome):
                rc, out, err = self.hook(nome, payload_negavel(nome), env)
                self.assertEqual(rc, 2, "%s sem Python nenhum: esperado exit 2 (falha fechada), veio %d; stderr %r"
                                 % (nome, rc, err[-300:]))
                self.assertTrue(err.strip(), "%s: exit 2 sem motivo no stderr" % nome)

    def test_calibracao_com_atalho_os_4_negam(self):
        """Saída boa conhecida: com o atalho de hoje, os 4 payloads são negados (o payload é negável)."""
        env = self.env_com_atalho()
        for nome in HOOKS_PY:
            with self.subTest(hook=nome):
                rc, out, err = self.hook(nome, payload_negavel(nome), env)
                self.assertTrue(negou(rc, out), "%s com o atalho: exit %d · %r · %r" % (nome, rc, out, err))
                rc, out, err = self.hook(nome, {"tool_name": "Read", "tool_input": {"file_path": "x"}}, env)
                self.assertEqual((rc, decisao_hook(out)), (0, None), "%s com o atalho, inofensivo: %r" % (nome, err))

    def test_calibracao_saida_vazia_nao_e_negacao(self):
        self.assertFalse(negou(0, ""))
        self.assertFalse(negou(127, ""))
        self.assertFalse(negou(0, '{"hookSpecificOutput":{"permissionDecision":"ask"}}'))
        self.assertTrue(negou(0, '{"hookSpecificOutput":{"permissionDecision":"deny"}}'))
        self.assertTrue(negou(2, ""))


# ================================================================== CA-02
class TestCA02GuardGitPowerShell(_Base):
    """CA-02: guard-git (pelo comando do settings.json) nega git perigoso vindo da ferramenta PowerShell."""

    PERIGOSOS = ["git push", "git reset --hard", "git clean -fd", "git stash", "git add -A", "git commit -a -m wip",
                 "git checkout -- x", "& git.exe push origin master", "& git.exe reset --hard HEAD~1",
                 "Set-Location x; git push", "cd x; git stash"]
    LEITURA = ["git status", "git log --oneline -5", 'Write-Host "git push"']

    def _guard(self, ferramenta, comando, env):
        return self.hook("guard-git", {"tool_name": ferramenta, "tool_input": {"command": comando}}, env)

    def test_matcher_inclui_powershell(self):
        matcher, cmd = hook_do_settings("guard-git")
        self.assertIsNotNone(cmd, "guard-git sumiu do settings.json")
        for ferramenta in ("Bash", "PowerShell"):
            self.assertTrue(re.fullmatch(matcher or "", ferramenta),
                            "matcher do guard-git %r não cobre %s" % (matcher, ferramenta))

    def test_powershell_perigosos_negados(self):
        env = self.env_nativo()
        for c in self.PERIGOSOS:
            with self.subTest(comando=c):
                rc, out, err = self._guard("PowerShell", c, env)
                self.assertTrue(negou(rc, out), "PowerShell %r deveria ser negado; exit %d · %r · %r"
                                % (c, rc, out[-300:], err[-300:]))

    def test_powershell_leitura_passa(self):
        env = self.env_nativo()
        for c in self.LEITURA:
            with self.subTest(comando=c):
                rc, out, err = self._guard("PowerShell", c, env)
                self.assertEqual(rc, 0, "PowerShell %r: exit %d · %r" % (c, rc, err[-300:]))
                self.assertNotIn(decisao_hook(out), ("deny", "ask"), "PowerShell %r não deveria barrar: %r" % (c, out))

    @unittest.skipUnless(WINDOWS, SO_WINDOWS)
    def test_bash_continua_negado_sem_python3(self):
        rc, out, err = self._guard("Bash", "git push", self.env_sem_atalho())
        self.assertTrue(negou(rc, out), "Bash `git push` sem python3 deveria negar (hoje pede `ask`); exit %d · %r"
                        % (rc, out[-300:]))

    def test_calibracao_bash_com_atalho_nega_e_status_passa(self):
        env = self.env_com_atalho()
        rc, out, _ = self._guard("Bash", "git push", env)
        self.assertTrue(negou(rc, out), "calibração: Bash git push com o atalho é negado hoje; %r" % out)
        rc, out, _ = self._guard("Bash", "git status", env)
        self.assertEqual((rc, decisao_hook(out)), (0, None))


# ================================================================== CA-03
class TestCA03PrivacidadeCaminhoWindows(_Base):
    """CA-03: guard_privacidade.py acusa caminho de usuário do Windows; placeholders passam."""

    BS = "\\"
    NOME = "ful" + "ano"   # montado em partes: este arquivo também é varrido pelo guard

    def _varrer(self, conteudo):
        termos = escrever(self.tmp, "termos-vazio.txt", "# sem termos\n")
        arq = escrever(self.tmp, "alvo/amostra.md", conteudo)
        env = env_base(self.perfil, CS_TERMOS_PRIVADOS=termos, PYTHONUTF8="1")
        rc, out, err = rodar([PY, os.path.join(TOOLS, "guard_privacidade.py"), arq], env, cwd=self.tmp)
        return rc, _dec(out), _dec(err)

    def caminhos(self):
        b, n = self.BS, self.NOME
        return {"barra invertida": "C:" + b + "Users" + b + n + b + "proj",
                "barra dupla (JSON/escape)": "C:" + b * 2 + "Users" + b * 2 + n + b * 2 + "proj",
                "minúsculas": "c:" + b + "users" + b + n + b + "proj"}

    def test_caminho_windows_com_nome_e_acusado(self):
        for rot, c in self.caminhos().items():
            with self.subTest(forma=rot):
                rc, out, err = self._varrer("o projeto fica em %s e roda\n" % c)
                self.assertEqual(rc, 1, "%s (%r) deveria ser acusado: exit %d · %s" % (rot, c, rc, out[-300:]))
                self.assertIn("amostra.md", out, "o achado deve citar o arquivo: %r" % out)

    def test_placeholders_passam(self):
        b = self.BS
        txt = "\n".join(["exemplo: C:" + b + "Users" + b + "x" + b + "proj",
                         "exemplo: C:" + b + "Users" + b + "<nome>" + b + "proj",
                         "exemplo: %USERPROFILE%" + b + "proj", ""])
        rc, out, err = self._varrer(txt)
        self.assertEqual(rc, 0, "placeholders não são achado: exit %d · %s" % (rc, out[-400:]))

    def test_calibracao_posix_e_acusado_e_vazio_passa(self):
        rc, out, _ = self._varrer("caminho /Users/" + self.NOME + "/proj\n")
        self.assertEqual(rc, 1, "calibração: o padrão macOS já é acusado hoje: %s" % out)
        rc, out, _ = self._varrer("")
        self.assertEqual(rc, 0, "calibração: arquivo vazio não é achado: %s" % out)


# ================================================================== CA-04
class TestCA04SaidaUtf8(_Base):
    """CA-04: sem PYTHONUTF8 e com stdout em pipe, `--help` de cada tool .py e `sessao.py briefing` saem 0 em UTF-8."""

    def _par(self, argv, env_extra=None, cwd=None):
        extra = dict(env_extra or {}, COLUMNS="120")
        ruim = self.env_nativo(**extra)
        bom = dict(ruim, PYTHONUTF8="1")
        r = rodar(argv, ruim, cwd=cwd or RAIZ, timeout=120)
        b = rodar(argv, bom, cwd=cwd or RAIZ, timeout=120)
        return r, b

    def tools(self):
        ts = sorted(x for x in os.listdir(TOOLS) if x.endswith(".py"))
        self.assertTrue(ts, "nenhum tool .py em %s" % TOOLS)
        return ts

    def test_help_de_cada_tool(self):
        ruins = []
        for t in self.tools():
            with self.subTest(tool=t):
                (rc, out, err), (rcb, outb, errb) = self._par([PY, os.path.join(TOOLS, t), "--help"])
                self.assertEqual(rcb, 0, "%s --help falha até com PYTHONUTF8=1: %s" % (t, _dec(errb)[-300:]))
                prob = None if rc == 0 else "exit %d: %s" % (rc, _dec(err).strip().splitlines()[-1:] or "")
                prob = prob or falha_utf8(out, outb)
                if prob:
                    ruins.append(t)
                self.assertIsNone(prob, "%s --help sem PYTHONUTF8: %s" % (t, prob))
        self.assertEqual(ruins, [], "tools com saída quebrada: %s" % ruins)

    def test_sessao_briefing(self):
        sk = repo_skill(os.path.join(self.tmp, "skill"), {"VERSION": "1.0.0\n"}, env=env_base(self.perfil))
        argv = [PY, os.path.join(TOOLS, "sessao.py"), "briefing"]
        (rc, out, err), (rcb, outb, errb) = self._par(argv, {"CS_DEV_SKILL_DIR": sk}, cwd=sk)
        self.assertEqual(rcb, 0, "briefing falha até com PYTHONUTF8=1: %s" % _dec(errb)[-300:])
        self.assertRegex(_dec(outb), "[^\x00-\x7f]", "calibração: a referência tem acento (Sequência)")
        self.assertEqual(rc, 0, "briefing sem PYTHONUTF8: exit %d · %s" % (rc, _dec(err)[-300:]))
        self.assertIsNone(falha_utf8(out, outb))

    def test_calibracao_cp1252_reprova_e_identica_passa(self):
        ref = "Sequência → ⇒ ação\n".encode("utf-8")
        self.assertIsNone(falha_utf8(ref, ref))
        self.assertIsNotNone(falha_utf8("Sequência\n".encode("cp1252"), "Sequência\n".encode("utf-8")))
        self.assertIsNotNone(falha_utf8(b"", ref))
        self.assertIsNotNone(falha_utf8("Sequ?ncia\n".encode("utf-8"), "Sequência\n".encode("utf-8")))


# ================================================================== CA-05
class TestCA05GravaEmLf(_Base):
    """CA-05: o que o harness grava sai em LF; .gitattributes fixa eol=lf em .claude/ e campanhas/."""

    def test_gravar_em_lf(self):
        L = modulo("estado_lib")
        p = os.path.join(self.tmp, "st", "RESUME.md")
        L.gravar(p, "linha 1\nlinha 2\n")
        with open(p, "rb") as fh:
            self.assertEqual(fh.read(), b"linha 1\nlinha 2\n", "estado_lib.gravar gravou com CRLF")

    def test_apensar_em_lf(self):
        L = modulo("estado_lib")
        p = os.path.join(self.tmp, "st", "logs", "sessoes.jsonl")
        L.apensar(p, '{"a": 1}\n')
        L.apensar(p, '{"b": 2}\n')
        with open(p, "rb") as fh:
            self.assertEqual(fh.read(), b'{"a": 1}\n{"b": 2}\n', "estado_lib.apensar gravou com CRLF")

    def test_publicar_regras_aplicar_em_lf(self):
        raiz = os.path.join(self.tmp, "pacote")
        escrever(raiz, "a.md", "linha um\nsegredo aqui\n")
        escrever(raiz, "docs/b.md", "outro texto\nfim\n")
        regras = escrever(self.tmp, "regras.json5", json.dumps(
            {"blocos": [["a.md", "segredo aqui", "neutro aqui"]], "gerais": [{"de": "outro", "para": "limpo"}]}))
        termos = escrever(self.tmp, "termos-vazio.txt", "# sem termos\n")
        env = env_base(self.perfil, CS_TERMOS_PRIVADOS=termos, PYTHONUTF8="1")
        rc, out, err = rodar([PY, os.path.join(TOOLS, "publicar_regras.py"), "aplicar", raiz, "--regras", regras],
                             env, cwd=self.tmp)
        self.assertEqual(rc, 0, "publicar_regras aplicar: exit %d · %s · %s" % (rc, _dec(out), _dec(err)))
        for rel, esperado in (("a.md", b"linha um\nneutro aqui\n"), ("docs/b.md", b"limpo texto\nfim\n")):
            with open(os.path.join(raiz, *rel.split("/")), "rb") as fh:
                dados = fh.read()
            self.assertNotIn(b"\r\n", dados, "%s regravado com CRLF" % rel)
            self.assertEqual(dados, esperado, "%s: a regra não foi aplicada (o teste não mediria nada)" % rel)

    def _check_attr(self, attr, *paths):
        d = os.path.join(self.tmp, "repo-attr")
        os.makedirs(d)
        git(d, "init", "-q", env=env_base(self.perfil))
        ga = os.path.join(RAIZ, ".gitattributes")
        if os.path.isfile(ga):
            shutil.copyfile(ga, os.path.join(d, ".gitattributes"))
        out = git(d, "check-attr", attr, "--", *paths, env=env_base(self.perfil))
        return {ln.split(": ")[0]: ln.split(": ")[-1].strip() for ln in out.splitlines() if ": " in ln}

    def test_gitattributes_eol_lf_em_claude_e_campanhas(self):
        paths = [".claude/state/RESUME.md", "campanhas/qualquer/oraculo/ESPEC.md"]
        r = self._check_attr("eol", *paths)
        for p in paths:
            self.assertEqual(r.get(p), "lf", "git check-attr eol %s = %r (esperado lf)" % (p, r.get(p)))

    def test_gitattributes_campanhas_text_auto(self):
        r = self._check_attr("text", "campanhas/qualquer/figura.png")
        self.assertEqual(r.get("campanhas/qualquer/figura.png"), "auto",
                         "campanhas/** com text=auto (binário não é convertido): %r" % r)

    def test_calibracao_ac_ja_e_lf(self):
        r = self._check_attr("eol", ".claude/tools/ac/ac.py")
        self.assertEqual(r.get(".claude/tools/ac/ac.py"), "lf", "calibração: a regra de hoje do motor")


# ================================================================== CA-06
class TestCA06ReguaComPythonsDaMaquina(_Base):
    """CA-06: `e2e.py pythons` lista os interpretadores da máquina; régua e portão usam a lista."""

    @unittest.skipUnless(WINDOWS, SO_WINDOWS)
    def test_pythons_lista_os_encontrados_sem_repetir(self):
        env = self.env_sem_atalho()
        pys = self.e2e_pythons(env)
        self.assertGreaterEqual(len(pys), 1)
        vistos = []
        for py in pys:
            r = self.resolver(py, env["PATH"])
            rc, out, err = rodar([r, "-c", "import sys;print(sys.executable)"], env)
            self.assertEqual(rc, 0, "%s não roda: %s" % (py, _dec(err)))
            vistos.append(os.path.normcase(os.path.realpath(_dec(out).strip())))
        self.assertEqual(len(vistos), len(set(vistos)), "o mesmo executável aparece mais de uma vez: %r" % pys)

    @unittest.skipUnless(WINDOWS, SO_WINDOWS)
    def test_python3_e_python_mesmo_executavel_viram_um(self):
        shim = os.path.join(self.tmp, "shim")
        escrever(shim, "python3.cmd", '@"%s" %%*\r\n' % PY)
        env = env_base(self.perfil, PATH=self._path(shim))
        self.assertTrue(shutil.which("python3", path=env["PATH"]), "precondição: python3 (shim) no PATH")
        pys = self.e2e_pythons(env)
        self.assertEqual(len(pys), 1, "python3 e python apontam para o mesmo executável: a régua roda uma vez; %r" % pys)

    @unittest.skipUnless(WINDOWS, SO_WINDOWS)
    def test_sem_nenhum_python_exit_2(self):
        self.e2e_pythons(self.env_sem_atalho())   # o subcomando existe (o exit 2 do argparse não conta)
        rc, out, err = rodar([PY, os.path.join(TOOLS, "e2e.py"), "pythons", "--json"], self.env_sem_python(), cwd=RAIZ)
        self.assertEqual(rc, 2, "sem python3/python/py no PATH: exit 2; veio %d · %s · %s"
                         % (rc, _dec(out)[-300:], _dec(err)[-300:]))
        self.assertNotIn("invalid choice", _dec(err), "exit 2 do argparse, não da busca de interpretadores")

    @unittest.skipUnless(WINDOWS, SO_WINDOWS)
    def test_rodar_dry_run_usa_a_lista(self):
        env = self.env_sem_atalho()
        pys = self.e2e_pythons(env)
        rc, out, err = rodar([PY, os.path.join(TOOLS, "e2e.py"), "rodar", "--suites", "harness-dev", "--dry-run"],
                             env, cwd=RAIZ)
        txt = _dec(out)
        self.assertEqual(rc, 0, _dec(err))
        self.assertNotIn("/usr/bin/python3", txt, "a régua no Windows não usa /usr/bin/python3:\n" + txt)
        linhas = [norm_cmd(x) for x in txt.splitlines() if x.strip()]
        for py in pys:
            self.assertTrue(any(norm_cmd(py) in x for x in linhas), "%s fora do plano da régua:\n%s" % (py, txt))

    @unittest.skipUnless(WINDOWS, SO_WINDOWS)
    def test_portao_dry_run_usa_a_lista(self):
        env = self.env_sem_atalho()
        pys = self.e2e_pythons(env)
        sk = repo_skill(os.path.join(self.tmp, "skill"), {"VERSION": "1.0.0\n"}, env=env_base(self.perfil))
        src = os.path.join(self.tmp, "src")
        escrever(src, "a.txt", "a\n")
        env = dict(env, CS_DEV_SKILL_DIR=win(sk), CS_DEV_WS=win(os.path.join(self.tmp, "local")))
        rc, out, err = self.script("portao.sh", ["wh-portao", "--src", win(src), "--dry-run", "--", "a.txt"], env)
        self.assertEqual(rc, 0, "portao.sh --dry-run: %s %s" % (out, err))
        self.assertNotIn("/usr/bin/python3", out, "o portão no Windows não usa /usr/bin/python3:\n" + out)
        for py in pys:
            self.assertIn(norm_cmd(py), norm_cmd(out), "%s fora do plano do portão:\n%s" % (py, out))

    @unittest.skipUnless(not WINDOWS, SO_POSIX)
    def test_posix_lista_de_hoje(self):
        pys = self.e2e_pythons(env_base(self.perfil))
        self.assertEqual(pys, ["python3", "/usr/bin/python3"])

    def test_calibracao_formato_da_lista(self):
        self.assertEqual(lista_pythons('{"pythons": ["python"]}'), ["python"])
        self.assertEqual(lista_pythons('["python3", "/usr/bin/python3"]'), ["python3", "/usr/bin/python3"])
        for ruim in ('{"pythons": [""]}', '{}', '"python"'):
            with self.assertRaises(ValueError):
                lista_pythons(ruim)
        self.assertEqual(norm_cmd("/c/Program Files/Python312/python.exe"), "c:/program files/python312/python.exe")


# ================================================================== CA-07
class TestCA07BashDoGitNuncaAliasWsl(_Base):
    """CA-07: bash_exe() descarta o alias %LOCALAPPDATA%\\Microsoft\\WindowsApps\\bash.exe; conferir_commit usa o
    argv[0] devolvido por bash_exe(). Plataforma simulada por mock (roda em qualquer SO)."""

    def setUp(self):
        super().setUp()
        self.f = modulo("feature")
        self.sysroot = os.path.join(self.tmp, "Windows")
        os.makedirs(self.sysroot)
        self.local = os.path.join(self.tmp, "AppData", "Local")
        self.alias = escrever(self.local, "Microsoft/WindowsApps/bash.exe", "")
        self.git_exe = escrever(self.tmp, "Git/cmd/git.exe", "")
        self.git_bash = escrever(self.tmp, "Git/bin/bash.exe", "")

    def _mocks(self, bash, local=None):
        mapa = {"bash": bash, "git": self.git_exe}

        def which(cmd, *a, **k):
            c = os.path.basename(str(cmd)).lower()
            return mapa.get(c[:-4] if c.endswith(".exe") else c)

        env = {"SystemRoot": self.sysroot, "SYSTEMROOT": self.sysroot,
               "LOCALAPPDATA": local or self.local, "LocalAppData": local or self.local}
        return [mock.patch.dict(os.environ, env), mock.patch.object(shutil, "which", side_effect=which),
                mock.patch.object(os, "name", "nt")]

    def _com(self, ms, fn):
        for m in ms:
            m.start()
        try:
            return fn()
        finally:
            for m in reversed(ms):
                m.stop()

    def _bash_exe(self, mod, bash, local=None):
        fn = getattr(mod, "bash_exe", None)
        self.assertTrue(callable(fn), "%s.bash_exe() não existe" % mod.__name__)

        def chama():
            try:
                return fn()
            except Exception as e:  # noqa: BLE001 — Recusa ou outro: o teste reporta
                return e
        return self._com(self._mocks(bash, local), chama)

    def assertGitBash(self, res, ctx):
        self.assertIsInstance(res, str, "%s: devolveu %r" % (ctx, res))
        self.assertNotIn("windowsapps", res.lower(), "%s: devolveu o alias do WSL %s" % (ctx, res))
        self.assertEqual(os.path.normcase(os.path.normpath(res)), os.path.normcase(self.git_bash), ctx)

    def test_feature_bash_exe_descarta_alias(self):
        self.assertGitBash(self._bash_exe(self.f, self.alias), "feature.bash_exe com o alias antes no PATH")

    def test_alias_com_outra_caixa_descartado(self):
        alias = os.path.join(self.tmp, "APPDATA", "LOCAL", "MICROSOFT", "WINDOWSAPPS", "BASH.EXE")
        self.assertGitBash(self._bash_exe(self.f, alias), "alias com outra caixa")

    def test_estado_lib_bash_exe_e_a_mesma_regra(self):
        L = modulo("estado_lib")
        self.assertGitBash(self._bash_exe(L, self.alias), "estado_lib.bash_exe com o alias antes no PATH")

    def test_conferir_commit_usa_argv0_de_bash_exe(self):
        chamadas = []

        def falso(args, *a, **k):
            chamadas.append([str(x) for x in args])
            return subprocess.CompletedProcess(args, 0, stdout=b"ok", stderr=b"")

        ms = self._mocks(self.alias) + [mock.patch.object(subprocess, "run", side_effect=falso)]
        esperado, r = self._com(ms, lambda: (self.f.bash_exe(), self.f.conferir_commit("wh-x", ["a.txt"], RAIZ)))
        conf = [c for c in chamadas if any(x.replace("\\", "/").endswith("conferir-commit.sh") for x in c)]
        self.assertTrue(conf, "conferir_commit não chamou o conferir-commit.sh por subprocess.run: %r" % chamadas)
        self.assertEqual(os.path.normcase(conf[0][0]), os.path.normcase(esperado),
                         "argv[0] (%s) ≠ bash_exe() (%s)" % (conf[0][0], esperado))
        self.assertGitBash(conf[0][0], "argv[0] do conferir-commit.sh")
        self.assertIsInstance(r, tuple)

    def test_calibracao_bash_fora_de_windowsapps_e_devolvido(self):
        usr = escrever(self.tmp, "Git/usr/bin/bash.exe", "")
        res = self._bash_exe(self.f, usr)
        self.assertEqual(os.path.normcase(res), os.path.normcase(usr), "calibração: bash do PATH comum é aceito hoje")


# ================================================================== CA-08
class TestCA08CarimboAnunciaInterpretador(_Base):
    """CA-08: `carimbo.sh --brief` sem python3 sai 0, anuncia `python: <interpretador>` e conta etapas como o motor."""

    CAMP = "wh-carimbo"

    def test_brief_sem_python3(self):
        env0 = env_base(self.perfil)
        sk = repo_skill(os.path.join(self.tmp, "skill"), {"VERSION": "1.0.0\n"}, env=env0)
        w = self.campanha(os.path.join(sk, "campanhas", self.CAMP), sk)
        st = self.estado(w)
        for s in ("intake.1", "intake.2", "intake.3", "oraculo.1"):
            st["done"][s] = "2020-01-01T00:00:00Z"
        st["stage"] = "oraculo"
        self.gravar_estado(w, st)
        rc, ref, err = rodar([PY, AC, "--work", w, "status"], dict(env0, PYTHONUTF8="1"), cwd=sk)
        esperado = etapas_do_status(_dec(ref))
        self.assertEqual(esperado, (1, 9), "fixture: intake ✓, oraculo … e 7 por fazer; status:\n%s" % _dec(ref))
        rc, out, err = self.script("carimbo.sh", ["--brief"], self.env_nativo(CS_DEV_SKILL_DIR=win(sk)), cwd=sk)
        self.assertEqual(rc, 0, "carimbo --brief: exit %d · %s" % (rc, err[-400:]))
        py, etapas = carimbo_ler(out, self.CAMP)
        self.assertTrue(py, "falta a linha `python: <interpretador>`:\n" + out)
        self.assertIn("py", py.lower(), "linha python: sem interpretador: %r" % py)
        if WINDOWS:
            self.assertIsNone(re.search(r"(^|[\\/\s])python3(\.exe)?(\s|$)", py),
                              "sem python3 no PATH, o anunciado não pode ser python3: %r" % py)
        self.assertEqual(etapas, esperado, "etapas do carimbo ≠ ac.py status (%s):\n%s" % (esperado, out))

    def test_calibracao_leitura(self):
        bom = "python: C:/Program Files/Python312/python.exe\ncampanhas ativas (1):\n  - wh-carimbo: etapa oraculo (1/9 etapas)\n"
        self.assertEqual(carimbo_ler(bom, self.CAMP), ("C:/Program Files/Python312/python.exe", (1, 9)))
        self.assertEqual(carimbo_ler("", self.CAMP), (None, None))
        st = " \u2713 intake       3/3\n \u2026 oraculo      1/4\n   base         0/3\n"
        self.assertEqual(etapas_do_status(st), (1, 3))


# ================================================================== CA-09
class TestCA09ScriptAprovacaoPs1(_Base):
    """CA-09: no Windows, script-aprovacao.sh gera local/aprovar-<f>.ps1 (interpretador resolvido, 3 passos, throw
    em $LASTEXITCODE) sem rodá-lo; fora do Windows, o .sh de hoje."""

    F = "wh-aprov"

    def _gerar(self, env):
        sk = repo_skill(os.path.join(self.tmp, "skill"), {"VERSION": "1.0.0\n"}, env=env_base(self.perfil))
        camp = os.path.join(self.tmp, "campanhas")
        w = self.campanha(os.path.join(camp, self.F), sk)
        ws = os.path.join(self.tmp, "local")
        env = dict(env, CS_DEV_SKILL_DIR=win(sk), CS_DEV_CAMP=win(camp), CS_DEV_WS=win(ws))
        rc, out, err = self.script("script-aprovacao.sh", [self.F, "--por", "Ana"], env, cwd=sk)
        return rc, out, err, w, ws

    @unittest.skipUnless(WINDOWS, SO_WINDOWS)
    def test_windows_gera_ps1(self):
        rc, out, err, w, ws = self._gerar(self.env_sem_atalho())
        self.assertEqual(rc, 0, "script-aprovacao.sh sem python3: exit %d · %s · %s" % (rc, out, err))
        p = os.path.join(ws, "aprovar-%s.ps1" % self.F)
        self.assertTrue(os.path.isfile(p), "não gerou %s; saída: %s" % (p, out))
        with open(p, encoding="utf-8-sig") as fh:
            txt = fh.read()
        self.assertEqual(ps1_passos_ok(txt), [], txt)
        n = norm_cmd(txt.replace("\\", "/"))
        alvo = norm_cmd(PY)
        self.assertTrue(alvo in n or alvo[:-4] in n, "o .ps1 não chama o interpretador resolvido (%s):\n%s" % (PY, txt))
        st = self.estado(w)
        self.assertEqual((st.get("gates") or {}, st.get("preauth") or {}), ({}, {}),
                         "gerar não pode rodar o script (gates/preauth mudaram)")

    @unittest.skipUnless(not WINDOWS, SO_POSIX)
    def test_posix_gera_sh_de_hoje(self):
        rc, out, err, w, ws = self._gerar(env_base(self.perfil))
        self.assertEqual(rc, 0, out + err)
        p = os.path.join(ws, "aprovar-%s.sh" % self.F)
        self.assertTrue(os.path.isfile(p), "não gerou %s" % p)
        with open(p, encoding="utf-8") as fh:
            txt = fh.read()
        self.assertTrue(txt.startswith("#!/bin/sh"))
        for passo in ("gate stop", "gate oracle:requisito", "preauth commit"):
            self.assertIn(passo, txt)
        self.assertIn('python3 "$M"', txt)
        self.assertFalse(os.path.exists(os.path.join(ws, "aprovar-%s.ps1" % self.F)))

    def test_calibracao_estrutura_ps1(self):
        bom = ("$ErrorActionPreference = 'Stop'\n& 'C:/py/python.exe' $M --work $W gate stop --by Ana\n"
               "if ($LASTEXITCODE -ne 0) { throw 'gate stop falhou' }\n"
               "& 'C:/py/python.exe' $M --work $W gate oracle:requisito\n"
               "if ($LASTEXITCODE -ne 0) { throw 'oracle falhou' }\n"
               "& 'C:/py/python.exe' $M --work $W preauth commit --requires a b\n"
               "if ($LASTEXITCODE -ne 0) { throw 'preauth falhou' }\n")
        self.assertEqual(ps1_passos_ok(bom), [])
        self.assertTrue(ps1_passos_ok(""))
        self.assertTrue(ps1_passos_ok(bom.replace("if ($LASTEXITCODE -ne 0) { throw 'oracle falhou' }\n", "")))


# ================================================================== CA-10
@unittest.skipUnless(WINDOWS, SO_WINDOWS)
class TestCA10InstalarComJuncao(_Base):
    """CA-10: instalar.sh no Windows sem Modo Desenvolvedor cria uma JUNÇÃO para dist/codebase-specialists (não
    cópia) e a checagem do _comum.sh a reconhece. Projeto, pacote e perfil temporários; package.sh trocado por um
    stub que monta dist/ a partir do HEAD do projeto temporário (a validação do PRODUTO no Windows é a B-14)."""

    STUB = ('#!/bin/bash\n# stub do oráculo win-harness: monta dist/ do HEAD do projeto temporário\nset -eu\n'
            'S="${CS_DEV_SKILL_DIR:?}"; D="$S/dist/codebase-specialists"\n'
            'rm -rf "$D"; mkdir -p "$D"\n'
            'git -C "$S" archive HEAD | tar -x -C "$D"\n'
            'git -C "$S" rev-parse HEAD > "$D/.origem"\n'
            'echo "pacote (stub do oráculo) em $D"\n')

    def _montar(self):
        sk = repo_skill(os.path.join(self.tmp, "skill"), {"SKILL.md": "# skill de teste\n", "VERSION": "9.9.9\n",
                                                          "scripts/cs.py": "print('uso: cs.py (stub)')\n"},
                        env=env_base(self.perfil))
        copia = os.path.join(self.tmp, "ferramentas", ".claude", "tools")
        shutil.copytree(TOOLS, copia, ignore=shutil.ignore_patterns("tests", "__pycache__"))
        escrever(copia, "package.sh", self.STUB, 0o755)
        env = self.env_sem_atalho(CS_DEV_SKILL_DIR=win(sk))
        return sk, copia, env

    def test_instala_juncao_reconhecida(self):
        sk, copia, env = self._montar()
        bash = self.bash()
        rc, out, err = rodar([bash, win(os.path.join(copia, "instalar.sh"))], env, cwd=sk, timeout=600)
        out, err = _dec(out), _dec(err)
        self.assertEqual(rc, 0, "instalar.sh: exit %d\n%s\n%s" % (rc, out[-1500:], err[-800:]))
        inst = os.path.join(self.perfil, ".claude", "skills", NOME)
        pk = os.path.join(sk, "dist", NOME)
        self.assertTrue(os.path.lexists(inst), "nada instalado em %s" % inst)
        self.assertEqual(getattr(os.lstat(inst), "st_reparse_tag", None), IO_REPARSE_TAG_MOUNT_POINT,
                         "o instalado não é uma junção (cópia ou symlink?)")
        self.assertEqual(os.path.normcase(os.path.realpath(inst)), os.path.normcase(os.path.realpath(pk)))
        escrever(pk, "marca-do-oraculo.txt", "x\n")
        self.assertTrue(os.path.isfile(os.path.join(inst, "marca-do-oraculo.txt")), "o instalado é uma cópia")
        rc, out, err = rodar([bash, win(os.path.join(copia, "instalar.sh")), "--check"], env, cwd=sk, timeout=300)
        out = _dec(out)
        self.assertNotIn("não é o link", out, "_comum.sh não reconhece a junção:\n" + out)
        self.assertEqual(rc, 0, "instalar.sh --check depois de instalar: exit %d\n%s%s" % (rc, out, _dec(err)))

    def test_calibracao_sem_privilegio_de_symlink(self):
        """Registra o ambiente: sem Modo Desenvolvedor, os.symlink falha (WinError 1314); a junção não precisa dele."""
        try:
            os.symlink(self.tmp, os.path.join(self.tmp, "lnk"), target_is_directory=True)
            simbolico = True
        except OSError:
            simbolico = False
        self.assertIn(simbolico, (True, False))


# ================================================================== CA-11
class TestCA11PerfilTemporarioCompleto(_Base):
    """CA-11: package_validar.py troca HOME e USERPROFILE; o expanduser('~') do subprocesso é o temporário."""

    def test_subprocesso_ve_o_home_temporario(self):
        reg = os.path.join(self.tmp, "registro.jsonl")
        pk = os.path.join(self.tmp, "pacote")
        escrever(pk, "SKILL.md", "# pacote falso\n")
        escrever(pk, "scripts/cs.py", "import json, os, sys\n"
                 "with open(os.environ['ORACULO_WH_REG'], 'a', encoding='utf-8') as fh:\n"
                 "    fh.write(json.dumps({'argv': sys.argv[1:], 'HOME': os.environ.get('HOME'),\n"
                 "        'USERPROFILE': os.environ.get('USERPROFILE'), 'til': os.path.expanduser('~')}) + '\\n')\n")
        fx = escrever(self.tmp, "fx/fixture.py", "import os, tempfile\n\n\ndef make_repo():\n"
                      "    d = tempfile.mkdtemp(prefix='wh-alvo-')\n"
                      "    open(os.path.join(d, 'LEIAME.md'), 'w').write('alvo\\n')\n    return d\n")
        pai = os.path.join(self.tmp, "perfil-pai")
        os.makedirs(pai)
        env = self.env_nativo(ORACULO_WH_REG=reg)
        env["HOME"] = env["USERPROFILE"] = pai
        rc, out, err = rodar([PY, os.path.join(TOOLS, "package_validar.py"), pk, "--fixture", fx], env, cwd=self.tmp)
        self.assertTrue(os.path.isfile(reg), "cs.py do pacote não rodou: exit %d · %s · %s" % (rc, _dec(out), _dec(err)))
        with open(reg, encoding="utf-8") as fh:
            regs = [json.loads(x) for x in fh if x.strip()]
        self.assertGreaterEqual(len(regs), 1)
        n = os.path.normcase
        for r in regs:
            with self.subTest(passo=" ".join(r["argv"][2:4])):
                self.assertNotEqual(n(r["til"]), n(pai), "expanduser('~') do subprocesso leu o perfil de quem chamou")
                self.assertEqual(n(r["til"]), n(r["HOME"] or ""), "expanduser('~') (%s) ≠ HOME temporário (%s)"
                                 % (r["til"], r["HOME"]))
                if WINDOWS:
                    self.assertEqual(n(r["USERPROFILE"] or ""), n(r["HOME"] or ""), "USERPROFILE não foi trocado")
        self.assertEqual(rc, 0, "validação do pacote falso: %s" % _dec(out)[-600:])

    def test_calibracao_expanduser_segue_userprofile_no_windows(self):
        alvo = os.path.join(self.tmp, "h")
        e = env_base(alvo)
        rc, out, _ = rodar([PY, "-c", "import os;print(os.path.expanduser('~'))"], e)
        self.assertEqual(os.path.normcase(_dec(out).strip()), os.path.normcase(alvo))
        if WINDOWS:
            e = dict(e, USERPROFILE=self.perfil)
            rc, out, _ = rodar([PY, "-c", "import os;print(os.path.expanduser('~'))"], e)
            self.assertEqual(os.path.normcase(_dec(out).strip()), os.path.normcase(self.perfil),
                             "calibração: no Windows quem manda é USERPROFILE, não HOME")


# ================================================================== CA-12
class TestCA12FecharComQualidade(_Base):
    """CA-12: `campanha.py fechar … --qualidade 14/14` leva a nota ao `run record` e o motor aceita `done remedicao`;
    sem --qualidade recusa antes de chamar o motor. Campanha temporária (fixture) no ponto da remedição."""

    F = "wh-fechar"

    def setUp(self):
        super().setUp()
        self.sk = os.path.join(self.tmp, "skill")
        os.makedirs(self.sk)
        self.w = self.campanha(os.path.join(self.sk, "campanhas", self.F), self.sk)
        cy = motor_mod().ciclo()
        st = self.estado(self.w)
        for etapa in cy["order"][:cy["order"].index("correcao")]:
            for s in cy["stages"][etapa]["substages"]:
                st["done"][s["id"]] = "2020-01-01T00:00:00Z"
        st["preauth"] = {"commit": {"by": "Ana", "requires": ["integracao.1", "integracao.2"],
                                    "note": "fixture do oráculo win-harness (temporária)"}}
        st["stage"] = "correcao"
        self.gravar_estado(self.w, st)
        escrever(self.w, ".auto-correcao/rounds/0/PLANO.json5",
                 json.dumps({"frentes": [{"nome": "fechamento", "escreve": ["a/**"]}], "decisoes": []}))
        self.rel = escrever(self.sk, "relatorio.md", "# relatório da fixture\n")
        self.env = self.env_nativo(CS_DEV_SKILL_DIR=self.sk)

    def _fechar(self, *extra):
        rc, out, err = rodar([PY, os.path.join(TOOLS, "campanha.py"), "fechar", self.F, "--relatorio", self.rel,
                              "--config", "sistema", "--decisao", "parar"] + list(extra), self.env, cwd=self.sk)
        return rc, _dec(out), _dec(err)

    def _bytes(self, *rel):
        p = os.path.join(self.w, ".auto-correcao", *rel)
        if not os.path.isfile(p):
            return None
        with open(p, "rb") as fh:
            return fh.read()

    def test_com_qualidade_motor_aceita_remedicao(self):
        rc, out, err = self._fechar("--qualidade", "14/14")
        self.assertEqual(rc, 0, "fechar --qualidade 14/14: exit %d\n%s\n%s" % (rc, out[-1200:], err[-800:]))
        st = self.estado(self.w)
        self.assertTrue(st["done"].get("remedicao.1") and st["done"].get("remedicao.2"),
                        "done remedicao não registrado: %r" % sorted(st["done"]))
        self.assertEqual(st.get("stage"), "decisao")
        runs = [json.loads(x) for x in (self._bytes("rounds", "0", "runs.jsonl") or b"").decode().splitlines() if x]
        self.assertTrue(runs, "nenhum run record")
        self.assertEqual(runs[-1].get("quality"), {"passed": 14, "total": 14}, "nota no run record: %r" % runs[-1])

    def test_sem_qualidade_recusa_antes_do_motor(self):
        antes = (self._bytes("state.json"), self._bytes("ledger.jsonl"))
        rc, out, err = self._fechar()
        self.assertNotEqual(rc, 0, "sem --qualidade deveria recusar: %s" % out)
        self.assertEqual((self._bytes("state.json"), self._bytes("ledger.jsonl")), antes,
                         "recusou DEPOIS de chamar o motor (estado/ledger mudaram)")
        self.assertIsNone(self._bytes("rounds", "0", "fronts", "fechamento.md"), "front report já foi gravado")

    def _passos_motor(self, grading):
        e = dict(self.env, PYTHONUTF8="1")
        rel = os.path.relpath(self.rel, self.sk)
        for p in (["front", "report", "--file", rel, "fechamento"], ["done", "correcao"],
                  ["set", "integration.tests_green", "true"], ["done", "integracao"]):
            rc, out, err = rodar([PY, AC, "--work", self.w] + p, e, cwd=self.sk)
            self.assertEqual(rc, 0, "fixture: %s → %s" % (p, _dec(err)))
        time.sleep(1.1)
        rr = ["run", "record", "--config", "sistema", "--decision", "parar"] + (["--grading", grading] if grading else [])
        rc, out, err = rodar([PY, AC, "--work", self.w] + rr, e, cwd=self.sk)
        self.assertEqual(rc, 0, _dec(err))
        return rodar([PY, AC, "--work", self.w, "done", "remedicao"], e, cwd=self.sk)[0]

    def test_calibracao_motor_aceita_com_nota(self):
        g = escrever(self.tmp, "grading.json", json.dumps({"summary": {"quality": {"passed": 14, "total": 14}}}))
        self.assertEqual(self._passos_motor(g), 0, "calibração: a fixture chega à remedição e o motor aceita com nota")

    def test_calibracao_motor_recusa_sem_nota(self):
        self.assertNotEqual(self._passos_motor(None), 0, "calibração: sem nota o motor recusa done remedicao")


# ================================================================== CA-13
@unittest.skipUnless(WINDOWS, SO_WINDOWS)
class TestCA13SuiteHarnessDevVerdeNoWindows(_Base):
    """CA-13: a suíte .claude/tools/tests roda verde (0 falhas, 0 erros) em cada Python de `e2e.py pythons`, sem o
    atalho; skip só com motivo declarado."""

    def test_suite_verde_em_cada_python(self):
        env = self.env_sem_atalho(PYTHONDONTWRITEBYTECODE="1")
        pys = self.e2e_pythons(env)
        for py in pys:
            with self.subTest(python=py):
                r = self.resolver(py, env["PATH"])
                rc, out, err = rodar([r, "-m", "unittest", "discover", "-s", "tests", "-v"], env, cwd=TOOLS,
                                     timeout=3600)
                txt = _dec(out) + _dec(err)
                ok, resumo = resumo_unittest(txt)
                falhas = re.findall(r"^(?:FAIL|ERROR): .*$", txt, re.M)
                self.assertTrue(rc == 0 and ok, "harness-dev em %s: exit %d · %s\n%s"
                                % (py, rc, resumo, "\n".join(falhas[:40])))
                self.assertNotRegex(txt, r"skipped ''", "skip sem motivo declarado")

    def test_calibracao_resumo(self):
        self.assertEqual(resumo_unittest("Ran 3 tests in 0.1s\n\nOK\n")[0], True)
        self.assertEqual(resumo_unittest("Ran 3 tests in 0.1s\n\nOK (skipped=1)\n")[0], True)
        self.assertEqual(resumo_unittest("")[0], False)
        self.assertEqual(resumo_unittest("Ran 0 tests in 0.0s\n\nOK\n")[0], False)
        self.assertEqual(resumo_unittest("Ran 83 tests in 455.7s\n\nFAILED (failures=33, errors=30)\n")[0], False)


# ================================================================== CA-14
@unittest.skipUnless(POSIX_2PY, SO_POSIX)
class TestCA14PosixInalterado(_Base):
    """CA-14: no WSL/macOS/Linux, harness-dev e os oráculos win-bash e win-motor-copia verdes nos 2 Pythons; os
    hooks continuam chamando python3."""

    PYS = ("python3", "/usr/bin/python3")

    def test_harness_dev_verde_nos_2_pythons(self):
        env = env_base(self.perfil, PYTHONDONTWRITEBYTECODE="1")
        for py in self.PYS:
            with self.subTest(python=py):
                rc, out, err = rodar([py, "-m", "unittest", "discover", "-s", "tests"], env, cwd=TOOLS, timeout=7200)
                ok, resumo = resumo_unittest(_dec(out) + _dec(err))
                self.assertTrue(rc == 0 and ok, "harness-dev em %s: %s\n%s" % (py, resumo, _dec(err)[-2000:]))

    def test_oraculos_win_bash_e_win_motor_copia_verdes(self):
        env = env_base(self.perfil, PYTHONDONTWRITEBYTECODE="1", ORACULO_SKILL=RAIZ, CS_SKILL_DIR=RAIZ)
        for py in self.PYS:
            for o in ("win-bash", "win-motor-copia"):
                with self.subTest(python=py, oraculo=o):
                    d = os.path.join(RAIZ, "campanhas", o, "oraculo")
                    rc, out, err = rodar([py, "-m", "unittest", "discover", "-s", d, "-p", "test_*.py"], env,
                                         cwd=RAIZ, timeout=3600)
                    ok, resumo = resumo_unittest(_dec(out) + _dec(err))
                    self.assertTrue(rc == 0 and ok, "oráculo %s em %s: %s\n%s" % (o, py, resumo, _dec(err)[-2000:]))

    def test_hooks_chamam_python3(self):
        real = shutil.which("python3")
        log = os.path.join(self.tmp, "interpretes.log")
        d = os.path.join(self.tmp, "espias")
        for n in ("python3", "python"):
            escrever(d, n, '#!/bin/sh\necho %s >> "$ORACULO_WH_LOG"\nexec "%s" "$@"\n' % (n, real), 0o755)
        env = env_base(self.perfil, PATH=d + os.pathsep + os.environ.get("PATH", ""), ORACULO_WH_LOG=log)
        inofensivos = {n: {"tool_name": "Read", "tool_input": {"file_path": "/x"}} for n in HOOKS_PY}
        inofensivos["guard-git"] = {"tool_name": "Bash", "tool_input": {"command": "git status"}}
        for nome, payload in inofensivos.items():
            with self.subTest(hook=nome):
                if os.path.exists(log):
                    os.remove(log)
                rc, out, err = self.hook(nome, payload, env)
                self.assertEqual(rc, 0, "%s: %s" % (nome, err))
                with open(log) as fh:
                    usados = fh.read().split()
                self.assertTrue(usados, "%s não chamou python3 nem python" % nome)
                self.assertEqual(set(usados), {"python3"}, "%s chamou %r (hoje: python3)" % (nome, usados))


if __name__ == "__main__":
    unittest.main()
