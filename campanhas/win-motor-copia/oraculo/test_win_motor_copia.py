"""Oráculo de aceite da feature win-motor-copia — o motor de campanhas embutido (`.claude/tools/ac/`) passa a ser o
motor corrigido do `auto-correcao` em `30e2da6` (Windows: frase no console, saída cp1252, hook vendo a ferramenta
PowerShell), com finais de linha LF fixados pelo `.gitattributes` e o registro do hook cobrindo `Bash|PowerShell`.

Escrito por um agente SEPARADO de quem corrige (quem testa não constrói). Cada classe CA01..CA05 FALHA hoje pelo motivo
do defeito e passa quando a entrega estiver feita; os testes `test_guarda_*` passam hoje e continuam passando (provam
que a classe não está vermelha por acaso). Contrato e tabela de hoje: ESPEC.md.

unittest puro, stdlib, Python 3.9+. O MESMO arquivo roda no Windows nativo e no Linux/WSL: o ramo Windows de
`frase.py` é exercitado por mocks (`_windows` forçado, `msvcrt` falso em `sys.modules`).

Variáveis (env do processo de teste):
  ORACULO_SKILL     raiz do projeto testado; senão CS_SKILL_DIR (a cópia limpa do portão); senão três pastas acima
                    deste arquivo.
  ORACULO_SCRIPTS   pasta do motor testado (padrão: <raiz>/.claude/tools/ac).
  ORACULO_FONTE_AC  raiz do clone do auto-correcao (padrão: <raiz>/../auto-correcao ou, se não existir,
                    <projeto deste oráculo>/../auto-correcao). Só se lê por `git -C <fonte> show 30e2da6:<caminho>`
                    — nunca a working tree da fonte. Fonte ausente = FALHA (não pula).

Isolamento: HOME, USERPROFILE, AC_FRASE_FILE e AC_AUDIT_LOG apontam para um temporário (tempfile.mkdtemp, apagado no
fim). Nenhum teste roda `gate`, `preauth` nem `frase` do ac.py: os comandos de aprovação aqui são STRINGS de payload
entregues ao `decide()` do hook. Git só roda em repositórios temporários.
"""
import base64
import contextlib
import difflib
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PROJETO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))  # projeto onde este oráculo mora
# CS_SKILL_DIR: a cópia limpa que o portão (`portao.sh`) passa aos oráculos
RAIZ = os.environ.get("ORACULO_SKILL") or os.environ.get("CS_SKILL_DIR") or PROJETO
MOTOR = os.environ.get("ORACULO_SCRIPTS") or os.path.join(RAIZ, ".claude", "tools", "ac")


def _fonte():
    if os.environ.get("ORACULO_FONTE_AC"):
        return os.environ["ORACULO_FONTE_AC"]
    cands = [os.path.join(os.path.dirname(os.path.abspath(r)), "auto-correcao") for r in (RAIZ, PROJETO)]
    return next((c for c in cands if os.path.isdir(c)), cands[0])


FONTE = _fonte()
COMMIT_FONTE = "30e2da6"

AC = os.path.join(MOTOR, "ac.py")
FRASE_PY = os.path.join(MOTOR, "frase.py")
HOOK = os.path.join(MOTOR, "hook_aprovacao.py")
ORIGEM = os.path.join(MOTOR, "ORIGEM.txt")
SETTINGS = os.path.join(RAIZ, ".claude", "settings.json")
GITATTRIBUTES = os.path.join(RAIZ, ".gitattributes")
TESTS_HARNESS = os.path.join(RAIZ, ".claude", "tools", "tests")

# embutido (relativo a MOTOR) -> caminho na fonte
MAPA = [
    ("ac.py", "scripts/ac.py"),
    ("frase.py", "scripts/frase.py"),
    ("hook_aprovacao.py", "scripts/hook_aprovacao.py"),
    ("references/ciclo.json5", "references/ciclo.json5"),
    ("references/formatos.json5", "references/formatos.json5"),
    ("references/licoes.json5", "references/licoes.json5"),
    ("references/prompts.json5", "references/prompts.json5"),
]
SHA_LINHA = re.compile(r"^\s+([0-9a-f]{64})\s+(\S+)\s*$", re.M)
SELFTEST_RE = re.compile(r"selftest:\s*(\d+)/(\d+)\s+ok")


# ---------------------------------------------------------------------------------------------------- utilidades

def lf(b):
    return b.replace(b"\r\n", b"\n")


def sha(b):
    return hashlib.sha256(b).hexdigest()


def ler_bytes(caminho):
    with open(caminho, "rb") as fh:
        return fh.read()


def apagar(caminho):
    """rmtree que também apaga arquivo somente-leitura (objetos do git no Windows)."""
    def _onerror(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except OSError:
            pass
    shutil.rmtree(caminho, onerror=_onerror)


def carregar(caminho, nome):
    spec = importlib.util.spec_from_file_location(nome, caminho)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def env_isolado(iso, encoding=None):
    e = dict(os.environ)
    e.pop("PYTHONUTF8", None)
    e.update(iso)
    if encoding:
        e["PYTHONIOENCODING"] = encoding
    return e


def git(cwd, *a, check=True):
    r = subprocess.run(["git", "-C", cwd, "-c", "user.email=t@t", "-c", "user.name=t", "-c", "init.defaultBranch=m",
                        "-c", "core.safecrlf=false"] + list(a),
                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    if check and r.returncode != 0:
        raise AssertionError("git %s falhou (%d): %s" % (" ".join(a), r.returncode,
                                                          r.stderr.decode("utf-8", "replace")))
    return r


def secoes_origem(texto):
    """(origem, embutido): listas de (sha, caminho). Origem = linhas de sha ANTES de 'sha256 EMBUTIDO'."""
    if "sha256 EMBUTIDO" not in texto:
        return SHA_LINHA.findall(texto), []
    antes, depois = texto.split("sha256 EMBUTIDO", 1)
    return SHA_LINHA.findall(antes), SHA_LINHA.findall(depois)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="oraculo-win-motor-copia-"))
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(self.home)
        tmpfilhos = os.path.join(self.tmp, "tmp")  # temporários dos subprocessos (harness-dev) apagados junto
        os.makedirs(tmpfilhos)
        self.iso = {"HOME": self.home, "USERPROFILE": self.home,
                    "AC_FRASE_FILE": os.path.join(self.tmp, "frase.json"),
                    "AC_AUDIT_LOG": os.path.join(self.tmp, "audit.jsonl")}
        self.iso_filhos = dict(self.iso, TMP=tmpfilhos, TEMP=tmpfilhos, TMPDIR=tmpfilhos)
        p = mock.patch.dict(os.environ, self.iso)
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(apagar, self.tmp)

    # ---- fonte: só `git show <commit>:<caminho>`
    def fonte(self, caminho):
        if not os.path.isdir(FONTE):
            self.fail("fonte do motor ausente: %s não existe (defina ORACULO_FONTE_AC = raiz do clone do "
                      "auto-correcao com o commit %s)" % (FONTE, COMMIT_FONTE))
        r = subprocess.run(["git", "-C", FONTE, "show", "%s:%s" % (COMMIT_FONTE, caminho)], stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        if r.returncode != 0:
            self.fail("fonte do motor inacessível: `git -C %s show %s:%s` saiu %d: %s (defina ORACULO_FONTE_AC)"
                      % (FONTE, COMMIT_FONTE, caminho, r.returncode, r.stderr.decode("utf-8", "replace").strip()))
        return r.stdout

    # ---- ac.py em subprocesso, isolado
    def ac(self, work, *args, encoding="utf-8"):
        return subprocess.run([sys.executable, AC, "--work", work] + list(args), stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=self.tmp,
                              env=env_isolado(self.iso, encoding), timeout=120)

    def nova_campanha(self, nome="camp"):
        work = os.path.join(self.tmp, nome)
        alvo = os.path.join(self.tmp, "alvo-" + nome)
        os.makedirs(alvo)
        r = self.ac(work, "init", "--target", alvo, "--scope", "x/**", "--problem", "p", "--stop", "q >= 1")
        self.assertEqual(r.returncode, 0, "init falhou (pré-condição do teste): %r" % (r.stderr,))
        return work

    def fechar_intake(self, work):
        """Fixture: marca intake.1-3 como concluídas direto no state.json (sem gate; o teste não aprova nada)."""
        p = os.path.join(work, ".auto-correcao", "state.json")
        with open(p, encoding="utf-8") as fh:
            st = json.load(fh)
        for sid in ("intake.1", "intake.2", "intake.3"):
            st["done"][sid] = "2026-10-08T00:00:00Z"
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(st, fh, ensure_ascii=False, indent=1, sort_keys=True)


# =============================================================================== CA-01 — cópia fiel e rastreável

class CA01CopiaFielRastreavelTest(Base):
    def test_frase_hook_e_references_iguais_a_fonte_apos_lf(self):
        for emb, src in MAPA[1:]:
            with self.subTest(arquivo=emb):
                self.assertEqual(sha(lf(ler_bytes(os.path.join(MOTOR, emb)))), sha(lf(self.fonte(src))),
                                 "%s embutido difere de %s:%s (após CRLF->LF)" % (emb, COMMIT_FONTE, src))

    def test_ac_py_difere_so_pelas_2_linhas_do_layout_depois_de_CICLO(self):
        fonte = lf(self.fonte("scripts/ac.py")).decode("utf-8").splitlines(True)
        emb = lf(ler_bytes(AC)).decode("utf-8").splitlines(True)
        idx = [i for i, l in enumerate(fonte) if l.startswith("CICLO = ")]
        self.assertEqual(len(idx), 1, "a fonte deveria ter exatamente 1 linha `CICLO = ` (achadas: %r)" % idx)
        k = idx[0] + 1
        ops = [op for op in difflib.SequenceMatcher(None, fonte, emb, autojunk=False).get_opcodes() if op[0] != "equal"]
        desc = ["%s fonte[%d:%d] emb[%d:%d]" % op for op in ops]
        self.assertEqual(len(ops), 1, "ac.py embutido deveria diferir da fonte por UM bloco; difere por %d: %r"
                         % (len(ops), desc[:12]))
        tag, i1, i2, j1, j2 = ops[0]
        self.assertEqual((tag, i1, i2, j2 - j1), ("insert", k, k, 2),
                         "esperado: inserção de 2 linhas logo depois de `CICLO = ` (fonte linha %d); achado: %r"
                         % (k, desc))
        bloco = "".join(emb[j1:j2])
        self.assertIn("references", bloco, "as 2 linhas inseridas não tratam do layout references/: %r" % bloco)

    def test_origem_cita_commit_e_confere_sha256_dos_7_arquivos(self):
        texto = ler_bytes(ORIGEM).decode("utf-8")
        self.assertTrue(COMMIT_FONTE in texto, "ORIGEM.txt não cita o commit da fonte %s" % COMMIT_FONTE)
        origem, embutido = secoes_origem(texto)
        self.assertEqual(sorted(c for _, c in origem), sorted(s for _, s in MAPA),
                         "ORIGEM.txt deveria listar os 7 sha256 de origem com o caminho na fonte")
        self.assertEqual(sorted(c for _, c in embutido), sorted(e for e, _ in MAPA),
                         "ORIGEM.txt deveria listar os 7 sha256 EMBUTIDO com o caminho relativo ao motor")
        for h, src in origem:
            with self.subTest(origem=src):
                self.assertEqual(h, sha(self.fonte(src)), "sha256 de origem de %s não confere com `git show %s:%s`"
                                 % (src, COMMIT_FONTE, src))
        for h, rel in embutido:
            with self.subTest(embutido=rel):
                self.assertEqual(h, sha(lf(ler_bytes(os.path.join(MOTOR, rel)))),
                                 "sha256 EMBUTIDO de %s não confere com o arquivo (bytes normalizados para LF)" % rel)


# =============================================================================== CA-02 — frase e saída no Windows

class FakeStdin:
    """stdin simulado: só isatty/fileno; qualquer leitura é registrada e reprovada."""

    def __init__(self, tty):
        self._tty = tty
        self.leituras = []

    def isatty(self):
        return self._tty

    def fileno(self):
        return 0

    def _leu(self, *a, **k):
        self.leituras.append("read")
        raise AssertionError("o ramo Windows leu sys.stdin (proibido)")

    read = readline = readlines = _leu

    @property
    def buffer(self):
        self.leituras.append("buffer")
        raise AssertionError("o ramo Windows leu sys.stdin.buffer (proibido)")


class FakeMsvcrt:
    """`msvcrt` falso: getwch devolve as teclas da fila (sem eco); putwch grava a saída do console."""

    def __init__(self, teclas):
        self.fila = list(teclas)
        self.saida = []
        self.proibidos = []

    def getwch(self):
        if not self.fila:
            raise AssertionError("getwch chamado depois do fim da entrada simulada (Enter não encerrou?)")
        return self.fila.pop(0)

    def putwch(self, ch):
        self.saida.append(ch)

    def __getattr__(self, nome):
        if nome in ("getch", "putch", "getche", "getwche", "ungetch", "ungetwch"):
            def f(*a, **k):
                self.proibidos.append(nome)
                raise AssertionError("msvcrt.%s usado; o contrato é getwch/putwch (sem eco)" % nome)
            return f
        raise AttributeError(nome)

    def texto(self):
        return "".join(self.saida)


class _Console:
    def close(self):
        pass


def spy_os_open(registro):
    real = os.open

    def f(path, flags, *a, **k):
        registro.append(path)
        if path == "/dev/tty":
            raise OSError("sem /dev/tty (simulado)")
        return real(path, flags, *a, **k)
    return f


class CA02FraseESaidaWindowsTest(Base):
    def frase(self):
        return carregar(FRASE_PY, "oraculo_win_motor_copia_frase")

    def exige_ramo_windows(self, m, *nomes):
        faltam = [n for n in nomes if not callable(getattr(m, n, None))]
        if faltam:
            self.fail("frase.%s ausente no motor embutido — sem ramo Windows, a frase só entra por /dev/tty+termios"
                      % ", frase.".join(faltam))

    def _ambiente(self, m, s, stdin_tty=True, teclas=(), abrir_console=True):
        s.enter_context(mock.patch.object(m, "_windows", return_value=True))
        if abrir_console:
            s.enter_context(mock.patch.object(m, "_abrir_console", return_value=None))
        fake = FakeMsvcrt(teclas)
        s.enter_context(mock.patch.dict(sys.modules, {"msvcrt": fake}))
        stdin = FakeStdin(stdin_tty)
        s.enter_context(mock.patch.object(sys, "stdin", stdin))
        abertos = []
        s.enter_context(mock.patch.object(os, "open", side_effect=spy_os_open(abertos)))
        out, err = io.StringIO(), io.StringIO()
        s.enter_context(mock.patch.object(sys, "stdout", out))
        s.enter_context(mock.patch.object(sys, "stderr", err))
        return fake, stdin, abertos, out, err

    def test_ramo_windows_existe_e_consulta_os_name(self):
        m = self.frase()
        self.exige_ramo_windows(m, "_windows", "_abrir_console")
        with mock.patch.object(os, "name", "nt"):
            nt = m._windows()
        with mock.patch.object(os, "name", "posix"):
            px = m._windows()
        self.assertEqual((nt, px), (True, False))

    def test_ler_windows_so_pelo_console_sem_eco(self):
        m = self.frase()
        self.exige_ramo_windows(m, "_windows", "_abrir_console")
        senha = "Zebra#7 voo"
        with contextlib.ExitStack() as s:
            fake, stdin, abertos, out, err = self._ambiente(m, s, teclas=list(senha) + ["\r"])
            r = m.ler("FRASE do founder: ", "Contexto da aprovacao")
        self.assertEqual(r, senha)
        self.assertEqual(stdin.leituras, [], "ler() leu sys.stdin")
        self.assertNotIn("/dev/tty", abertos, "o ramo Windows abriu /dev/tty")
        self.assertEqual(fake.proibidos, [])
        self.assertEqual(out.getvalue() + err.getvalue(), "", "ler() escreveu fora do console (msvcrt.putwch)")
        saida = fake.texto()
        i = saida.find("FRASE do founder: ")
        self.assertGreaterEqual(i, 0, "prompt não passou por msvcrt.putwch: %r" % saida)
        self.assertIn("Contexto da aprovacao", saida[:i])
        self.assertTrue(set(saida[i + len("FRASE do founder: "):]) <= set("\r\n"), "ecoou a frase: %r" % saida)
        self.assertNotIn(senha, saida)

    def test_windows_stdin_pipe_semtty_sem_ler_tecla(self):
        m = self.frase()
        self.exige_ramo_windows(m, "_windows", "_abrir_console")
        with contextlib.ExitStack() as s:
            fake, stdin, abertos, _, _ = self._ambiente(m, s, stdin_tty=False, teclas=list("abc") + ["\r"])
            with self.assertRaises(m.SemTTY):
                m.exigir_tty()
            with self.assertRaises(m.SemTTY):
                m.ler("FRASE: ")
        self.assertEqual(len(fake.fila), 4, "stdin em pipe: nenhuma tecla deveria ser lida")
        self.assertEqual(stdin.leituras, [])
        self.assertNotIn("/dev/tty", abertos, "o ramo Windows abriu /dev/tty")

    def test_windows_stdin_nul_nao_console_semtty(self):
        """NUL é tty para isatty() no Windows: só a prova de console (`_stdin_e_console`) recusa."""
        m = self.frase()
        self.exige_ramo_windows(m, "_windows", "_abrir_console", "_stdin_e_console")
        abriu = []

        def open_falso(caminho, *a, **k):
            if caminho == "CONIN$":
                abriu.append(caminho)
                return _Console()
            return open(caminho, *a, **k)

        with contextlib.ExitStack() as s:
            fake, stdin, abertos, _, _ = self._ambiente(m, s, stdin_tty=True, teclas=list("abc") + ["\r"],
                                                        abrir_console=False)
            s.enter_context(mock.patch.object(m, "open", side_effect=open_falso, create=True))
            prova = s.enter_context(mock.patch.object(m, "_stdin_e_console",
                                                      side_effect=OSError("a stdin não é o console (simulado)")))
            with self.assertRaises(m.SemTTY):
                m.exigir_tty()
            with self.assertRaises(m.SemTTY):
                m.ler("FRASE: ")
            chamou = prova.called
        self.assertTrue(chamou, "exigir_tty() no Windows não provou que a stdin é o console (_stdin_e_console)")
        self.assertEqual(len(fake.fila), 4, "stdin NUL: nenhuma tecla deveria ser lida")
        self.assertEqual(stdin.leituras, [])
        self.assertNotIn("/dev/tty", abertos)

    def _sem_traceback(self, r):
        err = r.stderr.decode("cp1252", "replace")
        self.assertNotIn("Traceback", err, err[-2000:])
        self.assertNotIn("UnicodeEncodeError", err, err[-2000:])
        self.assertEqual(r.returncode, 0, err[-2000:])

    def test_load_oraculo_stdout_cp1252_sem_pythonutf8(self):
        work = self.nova_campanha()
        self.fechar_intake(work)
        r = self.ac(work, "load", "oraculo", encoding="cp1252")
        self._sem_traceback(r)
        self.assertIn("oraculo", r.stdout.decode("cp1252", "replace"))

    def test_status_stdout_cp1252_sem_pythonutf8(self):
        work = self.nova_campanha()
        self.fechar_intake(work)  # etapa completa: imprime a marca de concluída
        r = self.ac(work, "status", encoding="cp1252")
        self._sem_traceback(r)
        self.assertIn("intake", r.stdout.decode("cp1252", "replace"))

    def test_guarda_stdin_nul_e_pipe_reais_nunca_leem_a_frase(self):
        """Guarda (passa hoje e depois): processo real com stdin NUL/pipe -> exigir_tty() levanta SemTTY."""
        code = ("import importlib.util,sys\n"
                "s=importlib.util.spec_from_file_location('f',sys.argv[1]);m=importlib.util.module_from_spec(s)\n"
                "s.loader.exec_module(m)\n"
                "try:\n m.exigir_tty()\nexcept m.SemTTY:\n print('SEMTTY');sys.exit(0)\n"
                "print('LEU-TTY');sys.exit(3)\n")
        for nome, stdin in (("NUL", subprocess.DEVNULL), ("pipe", subprocess.PIPE)):
            with self.subTest(stdin=nome):
                r = subprocess.run([sys.executable, "-c", code, FRASE_PY], stdin=stdin, input=None,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=self.tmp,
                                   env=env_isolado(self.iso), timeout=60)
                self.assertEqual(r.returncode, 0, (r.stdout + r.stderr).decode("utf-8", "replace"))
                self.assertIn(b"SEMTTY", r.stdout)


# =============================================================================== CA-03 — hook vê o PowerShell

def b64_ps(cmd):
    """Base64 do -EncodedCommand do PowerShell: UTF-16LE do texto."""
    return base64.b64encode(cmd.encode("utf-16-le")).decode("ascii")


PS_NEGA = [
    r"python scripts\ac.py --work c gate stop --by f --decision approve",
    r'iex "python scripts\ac.py --work c preauth commit --by f --requires a"',
    r'cmd /c "python scripts\ac.py --work c frase conferir"',
    "powershell -EncodedCommand " + b64_ps(r"python scripts\ac.py --work c gate stop"),
]


class CA03HookPowerShellTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hook = carregar(HOOK, "oraculo_win_motor_copia_hook")

    def nega(self, tool, cmd):
        return bool(self.hook.decide({"tool_name": tool, "tool_input": {"command": cmd}}))

    def test_settings_matcher_do_hook_aprovacao_cobre_bash_e_powershell(self):
        with open(SETTINGS, encoding="utf-8") as fh:
            cfg = json.load(fh)
        regs = [r for r in cfg.get("hooks", {}).get("PreToolUse", [])
                if any("hook_aprovacao.py" in (h.get("command") or "") for h in r.get("hooks", []))]
        self.assertTrue(regs, "nenhum registro PreToolUse cita hook_aprovacao.py em %s" % SETTINGS)
        for r in regs:
            with self.subTest(matcher=r.get("matcher")):
                partes = {p.strip() for p in (r.get("matcher") or "").split("|")}
                self.assertTrue({"Bash", "PowerShell"} <= partes,
                                "matcher %r do hook_aprovacao.py não cobre Bash e PowerShell" % r.get("matcher"))

    def test_decide_nega_aprovacao_pela_ferramenta_powershell(self):
        for cmd in PS_NEGA:
            with self.subTest(cmd=cmd[:80]):
                self.assertTrue(self.nega("PowerShell", cmd), "PowerShell %r foi PERMITIDO (esperado NEGADO)" % cmd)

    def test_selftest_mais_de_83_casos_todos_ok(self):
        tmp = tempfile.mkdtemp(prefix="oraculo-win-motor-copia-hook-")
        try:
            r = subprocess.run([sys.executable, HOOK, "--selftest"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, cwd=tmp, env=env_isolado({}), timeout=120)
        finally:
            apagar(tmp)
        out = r.stdout.decode("utf-8", "replace")
        self.assertEqual(r.returncode, 0, out + r.stderr.decode("utf-8", "replace"))
        m = SELFTEST_RE.search(out)
        self.assertIsNotNone(m, "saída do --selftest sem 'selftest: N/M ok': %r" % out)
        ok, total = int(m.group(1)), int(m.group(2))
        self.assertEqual(ok, total, out)
        self.assertGreater(total, 83, "o --selftest do hook embutido tem só %d casos (esperado > 83)" % total)

    def test_guarda_powershell_git_status_permitido(self):
        self.assertFalse(self.nega("PowerShell", "git status"))

    def test_guarda_bash_gate_continua_negado(self):
        self.assertTrue(self.nega("Bash", "python3 .claude/tools/ac/ac.py --work c gate stop --by f --decision approve"))


# =============================================================================== CA-04 — ORIGEM confere com autocrlf

class CA04OrigemConfereCheckoutWindowsTest(Base):
    def extrair(self):
        """Repo temporário com o .gitattributes do projeto (se houver) + o motor; commit; clone com autocrlf=true.
        Devolve a raiz do clone."""
        src = os.path.join(self.tmp, "src")
        os.makedirs(src)
        git(src, "init", "-q")
        git(src, "config", "core.autocrlf", "true")
        if os.path.isfile(GITATTRIBUTES):
            shutil.copyfile(GITATTRIBUTES, os.path.join(src, ".gitattributes"))
        shutil.copytree(MOTOR, os.path.join(src, ".claude", "tools", "ac"),
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        os.makedirs(os.path.join(src, ".claude", "tools", "tests"))
        shutil.copyfile(os.path.join(TESTS_HARNESS, "test_harness_dev.py"),
                        os.path.join(src, ".claude", "tools", "tests", "test_harness_dev.py"))
        git(src, "add", ".")
        git(src, "commit", "-q", "-m", "motor")
        dst = os.path.join(self.tmp, "clone")
        r = subprocess.run(["git", "-c", "core.autocrlf=true", "clone", "-q", "-c", "core.autocrlf=true", src, dst],
                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace"))
        return dst

    def arquivos_motor(self, raiz):
        ac = os.path.join(raiz, ".claude", "tools", "ac")
        out = []
        for d, _, fs in os.walk(ac):
            for f in fs:
                out.append(os.path.relpath(os.path.join(d, f), ac).replace(os.sep, "/"))
        return ac, sorted(out)

    def test_motor_extraido_com_autocrlf_fica_em_lf(self):
        ac, rels = self.arquivos_motor(self.extrair())
        self.assertGreaterEqual(len(rels), 8)
        com_crlf = [r for r in rels if b"\r\n" in ler_bytes(os.path.join(ac, r))]
        self.assertEqual(com_crlf, [], "clone com core.autocrlf=true extraiu o motor com CRLF (falta eol=lf no "
                                       ".gitattributes para .claude/tools/ac/**)")

    def test_sha256_dos_bytes_extraidos_bate_com_origem_embutido(self):
        ac, _ = self.arquivos_motor(self.extrair())
        _, embutido = secoes_origem(ler_bytes(os.path.join(ac, "ORIGEM.txt")).decode("utf-8"))
        self.assertEqual(len(embutido), 7, "ORIGEM.txt sem os 7 sha256 EMBUTIDO")
        for h, rel in embutido:
            with self.subTest(arquivo=rel):
                self.assertEqual(sha(ler_bytes(os.path.join(ac, rel))), h,
                                 "%s extraído (autocrlf=true) não bate com o sha256 EMBUTIDO do ORIGEM" % rel)

    def test_harness_origem_confere_sha256_passa_no_clone(self):
        raiz = self.extrair()
        r = subprocess.run([sys.executable, "-m", "unittest",
                            "test_harness_dev.MotorEmbutido.test_origem_confere_sha256"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           cwd=os.path.join(raiz, ".claude", "tools", "tests"), env=env_isolado(self.iso_filhos, "utf-8"),
                           timeout=300)
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace")[-2000:])

    def test_guarda_checkout_sem_autocrlf_preserva_lf_do_indice(self):
        """Guarda (passa hoje): o índice guarda LF — o defeito é só a conversão na extração com autocrlf=true."""
        src = os.path.join(self.tmp, "idx")
        os.makedirs(src)
        git(src, "init", "-q")
        git(src, "config", "core.autocrlf", "true")
        shutil.copytree(MOTOR, os.path.join(src, "ac"), ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        git(src, "add", ".")
        blob = git(src, "show", ":ac/ac.py").stdout
        self.assertNotIn(b"\r\n", blob)


# =============================================================================== CA-05 — sem regressão no harness

class CA05SemRegressaoHarnessTest(Base):
    def test_motor_embutido_da_suite_harness_passa_inteira(self):
        # PYTHONUTF8 removido; PYTHONIOENCODING=utf-8 porque o `run()` da suíte harness-dev decodifica a saída dos
        # filhos como UTF-8 (convenção do harness; o Windows nativo do harness é a B-15). A saída cp1252 do motor é
        # provada à parte, no CA02. Ver ESPEC.md, "Calibração do CA05".
        r = subprocess.run([sys.executable, "-m", "unittest", "test_harness_dev.MotorEmbutido"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           cwd=TESTS_HARNESS, env=env_isolado(self.iso_filhos, "utf-8"), timeout=600)
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace")[-3000:])

    def test_guarda_selftest_do_hook_embutido_sai_0(self):
        """Guarda (passa hoje e depois): o selftest do hook embutido continua verde."""
        r = subprocess.run([sys.executable, HOOK, "--selftest"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, cwd=self.tmp, env=env_isolado(self.iso), timeout=120)
        self.assertEqual(r.returncode, 0, (r.stdout + r.stderr).decode("utf-8", "replace")[-2000:])


if __name__ == "__main__":
    unittest.main()
