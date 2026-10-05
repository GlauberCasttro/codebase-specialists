"""JSON determinístico e escrita atômica.

- dumps(): sort_keys, indent=2, ensure_ascii=False, allow_nan=False, '\\n' final → mesmos bytes
  para o mesmo objeto.
- write_*_atomic(): grava em arquivo temporário no MESMO diretório, fsync, os.replace.
- Quando `target` é passado, o destino precisa estar dentro de <target>/.swarm/ (realpath).
"""

import json
import os
import tempfile

from .errors import CsError


def dumps(obj):
    """Serialização canônica (str). Falha em NaN/Infinity e em tipos não-JSON."""
    try:
        return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    except (TypeError, ValueError) as exc:
        raise CsError("objeto não serializável em JSON canônico: %s" % exc,
                      "bug interno: um valor não-JSON (NaN, set, bytes) chegou ao writer")


def dumps_line(obj):
    """Uma linha JSON canônica compacta (para jsonl)."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":"))


def _guard(path, target):
    if target is None:
        return
    from .paths import ensure_inside_specialists
    ensure_inside_specialists(target, path)


def write_bytes_atomic(path, data, target=None):
    """Grava bytes atomicamente. Cria diretórios pais."""
    _guard(path, target)
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=d)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_text_atomic(path, text, target=None):
    write_bytes_atomic(path, text.encode("utf-8"), target=target)


def write_json_atomic(path, obj, target=None):
    write_bytes_atomic(path, dumps(obj).encode("utf-8"), target=target)


def read_json(path, required=True, default=None):
    """Lê JSON. Ausência com required=True é ERRO explícito (nunca permissão silenciosa)."""
    if not os.path.exists(path):
        if required:
            raise CsError("arquivo obrigatório ausente: %s" % path,
                          "rode a fase que o produz (ex.: `cs.py scan`) antes desta")
        return default
    try:
        with open(path, "rb") as fh:
            return json.loads(fh.read().decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise CsError("JSON ilegível em %s: %s" % (path, exc),
                      "o arquivo está corrompido; apague-o e regenere com a fase correspondente")


def append_jsonl(path, obj, target=None):
    """Acrescenta uma linha (O_APPEND + fsync). Linha < PIPE_BUF é atômica na prática."""
    _guard(path, target)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    line = (dumps_line(obj) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, line)
        os.fsync(fd)
    finally:
        os.close(fd)
