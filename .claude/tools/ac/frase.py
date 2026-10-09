#!/usr/bin/env python3
"""frase.py — aprovação humana por FRASE-SENHA do founder (auto-correcao v0.4). Stdlib, Python 3.9+.

Módulo compartilhado: o ac.py importa daqui; o co_estado da construcao-orquestrada deve importá-lo por importlib
(sem copiar). Só um segredo que apenas o founder conhece separa humano de agente: tty + desafio era forjável por
qualquer agente com `pty.fork`.

- `frase.json` (`$AC_FRASE_FILE`, padrão `~/.claude/auto-correcao/frase.json`, modo 0600) guarda SÓ salts e o
  verificador PBKDF2-HMAC-SHA256 (600000 iterações). A frase nunca é gravada.
- Cada aprovação leva `tag = HMAC-SHA256(K, canonical(work, nome, decisao, seq, estado_hash))`, com
  `K = PBKDF2(frase, salt_chave)`. Quem não sabe a frase não calcula a tag; `ac.py frase conferir` recalcula todas.
- A frase só entra por `/dev/tty` com eco desligado, e só se a stdin também for tty. Nenhum argumento, nenhuma
  variável de ambiente e nenhuma stdin em pipe a fornecem.
- No Windows (`os.name == "nt"`) não há `/dev/tty` nem termios: a frase só entra pelo CONSOLE, tecla a tecla por
  `msvcrt.getwch` (que não ecoa), e o prompt sai por `msvcrt.putwch`. Exige a stdin tty, o console `CONIN$`
  abrível E a stdin ser um handle de console (GetConsoleMode; `isatty()` sozinho aceita `NUL`); sem isso,
  SemTTY. Nunca lê `sys.stdin`, argumento ou variável de ambiente. No Git Bash (mintty) a stdin é um pipe: rode
  `winpty python ...` ou use o PowerShell.

Limite honesto: o frase.json é legível pelo agente. Ele pode apagá-lo e definir outra frase; daí em diante aprova
e "confere" com a frase dele. Só o `frase conferir` digitado pelo founder com a frase real denuncia a troca.
"""
import hashlib
import hmac
import json
import os
import sys
import unicodedata

KDF = "pbkdf2-sha256"
ITER = 600000          # OWASP 2023; mínimo aceito, sem atalho por variável de ambiente
SALT_BYTES = 16
VERSAO = 1
MIN_CHARS = 12
MIN_PALAVRAS = 3
MIN_DISTINTOS = 6
MIN_CLASSES = 3
DEFAULT_PATH = os.path.join("~", ".claude", "auto-correcao", "frase.json")


class SemTTY(Exception):
    """Não há humano num terminal (stdin não-tty, sem /dev/tty ou, no Windows, sem console CONIN$)."""


class ArquivoInvalido(Exception):
    """frase.json ausente, ilegível ou com kdf/iter/salts inválidos."""


# ------------------------------------------------------------------ funções puras

def normalizar(f):
    return unicodedata.normalize("NFC", f.strip())


def classes(n):
    """Quantas classes entre minúscula, maiúscula, dígito e símbolo (não alfanumérico e não espaço)."""
    return sum((any(c.islower() for c in n), any(c.isupper() for c in n), any(c.isdigit() for c in n),
                any(not c.isalnum() and not c.isspace() for c in n)))


def problemas_forca(f):
    """Lista de problemas (vazia se serve). Senha ou frase, após normalizar: ≥12 caracteres, ≥6 caracteres
    distintos (espaço conta), e (≥3 palavras — frase — OU ≥3 classes entre minúscula, maiúscula, dígito e
    símbolo — senha)."""
    n = normalizar(f)
    probs = []
    if len(n) < MIN_CHARS:
        probs.append("menos de %d caracteres" % MIN_CHARS)
    if len(set(n)) < MIN_DISTINTOS:
        probs.append("menos de %d caracteres distintos" % MIN_DISTINTOS)
    if len(n.split()) < MIN_PALAVRAS and classes(n) < MIN_CLASSES:
        probs.append("nem frase (≥%d palavras) nem senha (≥%d classes entre minúscula, maiúscula, dígito e "
                     "símbolo)" % (MIN_PALAVRAS, MIN_CLASSES))
    return probs


def canonical(work, nome, decisao, seq, estado_hash):
    return json.dumps({"work": work, "nome": nome, "decisao": decisao, "seq": seq, "estado_hash": estado_hash},
                      sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def tag(chave, work, nome, decisao, seq, estado_hash):
    return hmac.new(chave, canonical(work, nome, decisao, seq, estado_hash), hashlib.sha256).hexdigest()


def derivar(f, salt_hex, it):
    return hashlib.pbkdf2_hmac("sha256", normalizar(f).encode("utf-8"), bytes.fromhex(salt_hex), it, dklen=32)


# ------------------------------------------------------------------ frase.json

def caminho():
    """`$AC_FRASE_FILE` é só CAMINHO; padrão `$HOME/.claude/auto-correcao/frase.json`."""
    return os.path.realpath(os.path.expanduser(os.environ.get("AC_FRASE_FILE") or DEFAULT_PATH))


def _hex(v, minimo):
    if not isinstance(v, str) or len(v) < 2 * minimo or len(v) % 2:
        return False
    try:
        bytes.fromhex(v)
    except ValueError:
        return False
    return True


def validar(fj):
    """Levanta ArquivoInvalido se o conteúdo não segue o formato v1 (kdf pbkdf2-sha256, iter int ≥ 600000)."""
    if not isinstance(fj, dict):
        raise ArquivoInvalido("frase.json não é um objeto")
    if fj.get("versao") != VERSAO:
        raise ArquivoInvalido("frase.json com versao desconhecida (%r)" % (fj.get("versao"),))
    if fj.get("kdf") != KDF:
        raise ArquivoInvalido("frase.json com kdf desconhecido (%r); só %s é aceito" % (fj.get("kdf"), KDF))
    it = fj.get("iter")
    if type(it) is not int or it < ITER:
        raise ArquivoInvalido("frase.json com iter inválido (%r); mínimo %d" % (it, ITER))
    for k in ("salt_verificador", "salt_chave"):
        if not _hex(fj.get(k), SALT_BYTES):
            raise ArquivoInvalido("frase.json com %s inválido (hex de ≥%d bytes)" % (k, SALT_BYTES))
    if fj["salt_verificador"] == fj["salt_chave"]:
        raise ArquivoInvalido("frase.json com salt_verificador igual a salt_chave")
    if not _hex(fj.get("verificador"), 32):
        raise ArquivoInvalido("frase.json com verificador inválido")
    if "criada_em" in fj and not isinstance(fj["criada_em"], str):
        raise ArquivoInvalido("frase.json com criada_em inválido")
    return fj


def existe(path=None):
    return os.path.isfile(path or caminho())


def carregar(path=None):
    path = path or caminho()
    if not os.path.isfile(path):
        raise ArquivoInvalido("nenhuma senha ou frase definida em %s — o founder roda, no terminal dele, "
                              "`ac.py frase definir`" % path)
    try:
        with open(path, encoding="utf-8") as fh:
            fj = json.load(fh)
    except (OSError, ValueError) as e:
        raise ArquivoInvalido("frase.json ilegível em %s (%s)" % (path, type(e).__name__))
    return validar(fj)


def novo_registro(f):
    sv, sk = os.urandom(SALT_BYTES).hex(), os.urandom(SALT_BYTES).hex()
    while sk == sv:
        sk = os.urandom(SALT_BYTES).hex()
    return {"versao": VERSAO, "kdf": KDF, "iter": ITER, "salt_verificador": sv, "salt_chave": sk,
            "verificador": derivar(f, sv, ITER).hex(), "criada_em": agora_utc()}


def agora_utc():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def confere(fj, f):
    return hmac.compare_digest(derivar(f, fj["salt_verificador"], fj["iter"]).hex(), fj["verificador"])


def chave(fj, f):
    return derivar(f, fj["salt_chave"], fj["iter"])


def gravar(fj, path=None):
    """Grava atômico com modo 0600 (diretório 0700 se criado)."""
    path = path or caminho()
    d = os.path.dirname(path)
    os.makedirs(d, mode=0o700, exist_ok=True)
    tmp = path + ".tmp-%d" % os.getpid()
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(fj, fh, sort_keys=True, indent=1)
            fh.write("\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    os.chmod(path, 0o600)


# ------------------------------------------------------------------ leitura humana (tty, sem eco)

def _windows():
    """True no Windows nativo. Consultado a cada chamada (não no import)."""
    return os.name == "nt"


def _stdin_e_console():
    """OSError se a stdin NÃO é um handle de console (GetConsoleMode falha). Necessário porque no Windows
    `isatty()` é True para qualquer dispositivo de caractere — inclusive `NUL` (subprocess.DEVNULL)."""
    try:
        import ctypes
        import msvcrt
        from ctypes import wintypes
        h = msvcrt.get_osfhandle(sys.stdin.fileno())
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.GetConsoleMode.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        k32.GetConsoleMode.restype = wintypes.BOOL
        modo = wintypes.DWORD()
        ok = bool(k32.GetConsoleMode(h, ctypes.byref(modo)))
    except (ImportError, AttributeError, ValueError, OSError) as e:  # falha fechada: sem prova de console, não lê
        raise OSError("não foi possível provar que a stdin é o console (%s)" % type(e).__name__)
    if not ok:
        raise OSError("a stdin não é o console (GetConsoleMode falhou)")


def _abrir_console():
    """Abre e fecha o console de entrada (`CONIN$`) e exige que a stdin SEJA esse console (`_stdin_e_console`).
    OSError se o processo não tem console ou se a stdin não é um handle de console."""
    fh = open("CONIN$", "rb", buffering=0)
    fh.close()
    _stdin_e_console()


SEM_CONSOLE = ("a senha ou frase só é lida no console interativo do Windows (stdin no console); nada gravado. "
               "No Git Bash (mintty) a stdin não é console: rode `winpty python ...` ou use o PowerShell. "
               "Um agente não aprova — peça ao founder que rode este comando no terminal dele.")


def exigir_tty():
    """stdin tty E /dev/tty abrível (no Windows: stdin tty, console `CONIN$` abrível E a stdin é um handle de
    console). Senão SemTTY (o chamador sai com exit 2). Devolve o ttyname (no Windows, "CONIN$")."""
    try:
        ok = sys.stdin is not None and sys.stdin.isatty()
    except (ValueError, OSError):
        ok = False
    if _windows():
        if not ok:
            raise SemTTY(SEM_CONSOLE)
        try:
            _abrir_console()
        except OSError:
            raise SemTTY(SEM_CONSOLE)
        return "CONIN$"
    if not ok:
        raise SemTTY("a senha ou frase só é lida num terminal interativo (stdin tty); nada gravado. Um agente não aprova — "
                     "peça ao founder que rode este comando no terminal dele.")
    try:
        fd = os.open("/dev/tty", os.O_RDWR | getattr(os, "O_NOCTTY", 0))
    except OSError:
        raise SemTTY("a frase exige /dev/tty (terminal controlador); nada gravado.")
    os.close(fd)
    try:
        return os.ttyname(sys.stdin.fileno())
    except (OSError, AttributeError):  # AttributeError: plataforma sem os.ttyname
        return "/dev/tty"


def ler(prompt, contexto=None):
    """Uma leitura, uma tentativa: abre /dev/tty, DESLIGA o eco e só então escreve o prompt (`FRASE...:`).
    Sem fallback para stdin (ao contrário do getpass). Sem termios utilizável → SemTTY.
    No Windows: só o console — prompt por msvcrt.putwch, teclas por msvcrt.getwch (sem eco); Enter encerra,
    Backspace apaga, Ctrl+C → KeyboardInterrupt, teclas especiais (prefixo \\x00/\\xe0) descartadas, até 4096."""
    exigir_tty()
    if _windows():
        import msvcrt
        if contexto:
            for c in contexto.rstrip("\n") + "\r\n":
                msvcrt.putwch(c)
        for c in prompt:
            msvcrt.putwch(c)
        buf = []
        try:
            while True:
                ch = msvcrt.getwch()
                if ch in ("\r", "\n"):
                    break
                if ch == "\x03":
                    raise KeyboardInterrupt
                if ch in ("\x00", "\xe0"):  # tecla especial: o código seguinte não é caractere
                    msvcrt.getwch()
                    continue
                if ch == "\b":
                    if buf:
                        buf.pop()
                    continue
                if len(buf) < 4096:  # o excedente é consumido e descartado (não vaza para o shell)
                    buf.append(ch)
        finally:
            for c in "\r\n":
                msvcrt.putwch(c)
        return "".join(buf)
    import termios
    try:
        fd = os.open("/dev/tty", os.O_RDWR | getattr(os, "O_NOCTTY", 0))
    except OSError:
        raise SemTTY("a frase exige /dev/tty (terminal controlador); nada gravado.")
    try:
        try:
            old = termios.tcgetattr(fd)
        except termios.error:
            raise SemTTY("/dev/tty sem controle de eco; nada gravado.")
        new = list(old)
        new[3] = new[3] & ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSAFLUSH, new)
        buf = b""
        try:
            if contexto:
                os.write(fd, (contexto.rstrip("\n") + "\n").encode("utf-8"))
            os.write(fd, prompt.encode("utf-8"))
            while not buf.endswith(b"\n") and len(buf) < 4096:
                ch = os.read(fd, 1)
                if not ch:
                    break
                buf += ch
        finally:
            termios.tcsetattr(fd, termios.TCSAFLUSH, old)
            os.write(fd, b"\n")
    finally:
        os.close(fd)
    return buf.decode("utf-8", "replace").rstrip("\r\n")
