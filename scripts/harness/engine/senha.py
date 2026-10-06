#!/usr/bin/env python3
"""senha.py — a SENHA do humano no modo autônomo (mandato M5). Stdlib, Python 3.9+. Sem dependência externa.

Só um segredo que apenas o humano conhece separa humano de agente: `--by <humano>` e o guard pre-bash não bastam
(um agente que chame o motor por outro caminho — pty, import, edição do estado — aprovaria sozinho).

- Registro (`$CS_SENHA_FILE` — só CAMINHO —, senão `$XDG_CONFIG_HOME/codebase-specialists/senha.json`, senão
  `~/.config/codebase-specialists/senha.json`; modo 0600, diretório 0700; SEMPRE fora do repositório-alvo) guarda
  só os sais e o verificador PBKDF2-HMAC-SHA256 (≥ 600000 iterações). A senha nunca é gravada.
- Cada aprovação de mandato leva um SELO: `tag = HMAC-SHA256(K, canonical(mandato, plano_sha256, orcamento, seq,
  ts))`, `K = PBKDF2(senha, salt_chave)`. Quem não sabe a senha não calcula a tag; `cs-auto conferir` recalcula todas.
- A senha só entra por `/dev/tty` com eco desligado, e só se a stdin também for tty. Nenhum argumento, nenhuma
  variável de ambiente e nenhuma stdin em pipe a fornecem.

Limite honesto: o registro é legível/gravável pelo agente. Ele pode apagá-lo, definir a senha dele e re-selar; o
`cs-auto tick` (que roda sem a senha) só confere o FORMATO do selo e se ele cobre o plano atual — não a HMAC. Só o
`cs-auto conferir` digitado pelo humano com a senha real denuncia a troca.
"""
import hashlib
import hmac
import json
import os
import re
import sys
import unicodedata

KDF = "pbkdf2-sha256"
ITER = 600000
SALT_BYTES = 16
VERSAO = 1
ALG = "hmac-sha256"
MIN_CHARS = 12
MIN_DISTINTOS = 6
MIN_CLASSES = 3
ENV_FILE = "CS_SENHA_FILE"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
DEFINIR = "cs-auto senha definir"


class SemTTY(Exception):
    """Não há humano num terminal (stdin não-tty ou sem /dev/tty)."""


class RegistroInvalido(Exception):
    """Registro ausente, ilegível, fora do lugar ou com kdf/iter/sais inválidos."""


# ------------------------------------------------------------------ funções puras
def normalizar(s):
    return unicodedata.normalize("NFC", s.strip())


def classes(n):
    """Quantas classes entre minúscula, maiúscula, dígito e símbolo."""
    return sum((any(c.islower() for c in n), any(c.isupper() for c in n), any(c.isdigit() for c in n),
                any(not c.isalnum() and not c.isspace() for c in n)))


def problemas_forca(s):
    """Lista de problemas (vazia se serve): após NFC+strip, ≥ 12 caracteres, ≥ 6 distintos, ≥ 3 classes."""
    n = normalizar(s)
    probs = []
    if len(n) < MIN_CHARS:
        probs.append("menos de %d caracteres" % MIN_CHARS)
    if len(set(n)) < MIN_DISTINTOS:
        probs.append("menos de %d caracteres distintos" % MIN_DISTINTOS)
    if classes(n) < MIN_CLASSES:
        probs.append("menos de %d classes entre minúscula, maiúscula, dígito e símbolo" % MIN_CLASSES)
    return probs


def derivar(s, salt_hex, it):
    return hashlib.pbkdf2_hmac("sha256", normalizar(s).encode("utf-8"), bytes.fromhex(salt_hex), it, dklen=32)


def canonical_selo(selo):
    body = dict((k, selo.get(k)) for k in ("mandato", "plano_sha256", "orcamento", "seq", "ts"))
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def tag_selo(chave_, selo):
    return hmac.new(chave_, canonical_selo(selo), hashlib.sha256).hexdigest()


def novo_selo(chave_, mandato, plano_sha256, orcamento, seq, ts):
    s = {"versao": VERSAO, "alg": ALG, "mandato": mandato, "plano_sha256": plano_sha256, "orcamento": orcamento,
         "seq": seq, "ts": ts}
    s["tag"] = tag_selo(chave_, s)
    return s


def problemas_formato_selo(selo, mandato=None):
    """Formato do selo (sem a senha): o que o `tick` consegue conferir. Lista vazia = formato válido."""
    if selo is None:
        return ["aprovação sem selo (o approve legítimo grava data.selo com a senha do humano)"]
    if not isinstance(selo, dict):
        return ["selo não é objeto"]
    p = []
    if selo.get("versao") != VERSAO:
        p.append("selo com versao desconhecida (%r)" % (selo.get("versao"),))
    if selo.get("alg") != ALG:
        p.append("selo com alg desconhecido (%r); só %s" % (selo.get("alg"), ALG))
    for k in ("tag", "plano_sha256"):
        if not isinstance(selo.get(k), str) or not HEX64.match(selo[k]):
            p.append("selo com %s ausente ou fora do formato (hex de 64)" % k)
    if type(selo.get("seq")) is not int:
        p.append("selo com seq ausente ou não inteiro")
    if not isinstance(selo.get("ts"), str) or not selo.get("ts"):
        p.append("selo com ts ausente")
    if not isinstance(selo.get("orcamento"), dict):
        p.append("selo sem orcamento (objeto)")
    if not isinstance(selo.get("mandato"), str):
        p.append("selo sem mandato")
    elif mandato is not None and selo["mandato"] != mandato:
        p.append("selo de outro mandato (%s ≠ %s)" % (selo["mandato"], mandato))
    return p


# ------------------------------------------------------------------ registro
def caminho():
    """`$CS_SENHA_FILE` é só CAMINHO; padrão `$XDG_CONFIG_HOME|~/.config` + `/codebase-specialists/senha.json`."""
    p = os.environ.get(ENV_FILE)
    if not p:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
        p = os.path.join(base, "codebase-specialists", "senha.json")
    return os.path.realpath(os.path.abspath(os.path.expanduser(p)))


def dentro_do_alvo(path, root):
    if not root:
        return False
    r = os.path.realpath(root)
    p = os.path.realpath(path)
    return p == r or p.startswith(r.rstrip(os.sep) + os.sep)


def caminho_fora_do_alvo(root):
    p = caminho()
    if dentro_do_alvo(p, root):
        raise RegistroInvalido("o registro da senha (%s) cai DENTRO do repositório-alvo (%s): ele tem de ficar fora "
                               "do alcance do repositório (padrão ~/.config/codebase-specialists/senha.json)" % (p, root))
    return p


def _hex(v, minimo):
    if not isinstance(v, str) or len(v) < 2 * minimo or len(v) % 2:
        return False
    try:
        bytes.fromhex(v)
    except ValueError:
        return False
    return v == v.lower()


def validar(reg):
    if not isinstance(reg, dict):
        raise RegistroInvalido("registro da senha não é um objeto")
    if reg.get("versao") != VERSAO:
        raise RegistroInvalido("registro da senha com versao desconhecida (%r)" % (reg.get("versao"),))
    if reg.get("kdf") != KDF:
        raise RegistroInvalido("registro da senha com kdf desconhecido (%r); só %s" % (reg.get("kdf"), KDF))
    it = reg.get("iter")
    if type(it) is not int or it < ITER:
        raise RegistroInvalido("registro da senha com iter inválido (%r); mínimo %d" % (it, ITER))
    for k in ("salt_verificador", "salt_chave"):
        if not _hex(reg.get(k), SALT_BYTES):
            raise RegistroInvalido("registro da senha com %s inválido (hex de ≥%d bytes)" % (k, SALT_BYTES))
    if reg["salt_verificador"] == reg["salt_chave"]:
        raise RegistroInvalido("registro da senha com salt_verificador igual a salt_chave")
    if not _hex(reg.get("verificador"), 32) or len(reg["verificador"]) != 64:
        raise RegistroInvalido("registro da senha com verificador inválido")
    if "criada_em" in reg and not isinstance(reg["criada_em"], str):
        raise RegistroInvalido("registro da senha com criada_em inválido")
    return reg


def carregar(root=None):
    path = caminho_fora_do_alvo(root)
    if not os.path.isfile(path):
        raise RegistroInvalido("nenhuma senha definida (%s) — o humano roda, no terminal DELE, `%s` "
                               "(uma vez) e depois repete o comando" % (path, DEFINIR))
    try:
        with open(path, encoding="utf-8") as fh:
            reg = json.load(fh)
    except (OSError, ValueError) as e:
        raise RegistroInvalido("registro da senha ilegível em %s (%s)" % (path, type(e).__name__))
    return validar(reg)


def agora_utc():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def novo_registro(s):
    sv, sk = os.urandom(SALT_BYTES).hex(), os.urandom(SALT_BYTES).hex()
    while sk == sv:
        sk = os.urandom(SALT_BYTES).hex()
    return {"versao": VERSAO, "kdf": KDF, "iter": ITER, "salt_verificador": sv, "salt_chave": sk,
            "verificador": derivar(s, sv, ITER).hex(), "criada_em": agora_utc()}


def confere(reg, s):
    return hmac.compare_digest(derivar(s, reg["salt_verificador"], reg["iter"]).hex(), reg["verificador"])


def chave(reg, s):
    return derivar(s, reg["salt_chave"], reg["iter"])


def gravar(reg, path):
    """Grava atômico com modo 0600 (diretório 0700 se criado)."""
    d = os.path.dirname(path)
    if not os.path.isdir(d):
        os.makedirs(d, mode=0o700, exist_ok=True)
    tmp = path + ".tmp-%d" % os.getpid()
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(reg, fh, sort_keys=True, indent=1)
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
def exigir_tty():
    """stdin tty E /dev/tty abrível; senão SemTTY."""
    try:
        ok = sys.stdin is not None and sys.stdin.isatty()
    except (ValueError, OSError):
        ok = False
    if not ok:
        raise SemTTY("a senha só é lida num terminal interativo (stdin tty); nada gravado. Um agente não faz este "
                     "ato — peça ao humano que rode o comando no terminal dele.")
    try:
        fd = os.open("/dev/tty", os.O_RDWR | getattr(os, "O_NOCTTY", 0))
    except OSError:
        raise SemTTY("a senha exige /dev/tty (terminal controlador); nada gravado.")
    os.close(fd)


def ler(prompt, contexto=None):
    """Uma leitura, uma tentativa: abre /dev/tty, DESLIGA o eco e só então escreve o prompt (`SENHA...:`).
    Sem fallback para stdin, argumento ou ambiente. Sem termios utilizável → SemTTY."""
    exigir_tty()
    import termios
    try:
        fd = os.open("/dev/tty", os.O_RDWR | getattr(os, "O_NOCTTY", 0))
    except OSError:
        raise SemTTY("a senha exige /dev/tty (terminal controlador); nada gravado.")
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
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
            os.write(fd, b"\n")
    finally:
        os.close(fd)
    return buf.decode("utf-8", "replace").rstrip("\r\n")


def pedir_chave(root, contexto=None):
    """Ato humano: registro válido (fora do alvo) + senha digitada no terminal e conferida. Devolve (reg, K).
    Levanta RegistroInvalido, SemTTY ou ValueError (senha errada). Uma tentativa só."""
    reg = carregar(root)
    exigir_tty()
    s = ler("SENHA do humano (o eco fica desligado): ", contexto)
    if not s or not confere(reg, s):
        raise ValueError("senha errada (uma tentativa por comando); nada gravado")
    return reg, chave(reg, s)


def definir(root):
    """`cs-auto senha definir`: (senha atual, se houver) + nova + repetição. Devolve o caminho gravado.
    Levanta RegistroInvalido, SemTTY ou ValueError."""
    path = caminho_fora_do_alvo(root)
    exigir_tty()
    atual = None
    if os.path.lexists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                atual = validar(json.load(fh))
        except (OSError, ValueError, RegistroInvalido) as e:
            raise RegistroInvalido("já existe um registro em %s, mas ele é inválido (%s): confira-o e, se for seu, "
                                   "apague-o à mão antes de redefinir" % (path, str(e)[:160]))
        s0 = ler("SENHA atual: ", "trocar a senha do modo autônomo (registro %s)" % path)
        if not s0 or not confere(atual, s0):
            raise ValueError("senha atual errada; registro intocado")
    s1 = ler("SENHA nova: ", None if atual else "definir a senha do modo autônomo (registro %s)" % path)
    probs = problemas_forca(s1)
    if probs:
        raise ValueError("senha fraca: %s; nada gravado" % "; ".join(probs))
    s2 = ler("SENHA nova, de novo: ")
    if normalizar(s1) != normalizar(s2):
        raise ValueError("a repetição não confere; nada gravado")
    gravar(novo_registro(s1), path)
    return path
