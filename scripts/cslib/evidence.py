"""Construção e validação de fatos no formato do ARCHITECTURE.md §4.

Fato:
  {id, layer, claim, evidence[], confidence, origin, scope[], fingerprint, supports?[], data?{}}
  `data` (opcional) = payload estruturado para consumidores (evita parsear `claim`).

- evidence nunca vazia; itens possíveis:
    {"file": rel, "line": n?}            arquivo do alvo (entra no fingerprint)
    {"cmd": str, "exit": int, "out_sha256": hex, "blob": rel?}   comando e hash da SAÍDA (bytes)
    {"commit": sha, "files": [rel]?}     commit do git
- origin: "mechanical" (derivado por script) | "llm_interpretation" (exige supports: [ids]).
- fingerprint = sha256 de "path\\0sha256(bytes)\\n" dos arquivos-evidência, ordenados; para fatos sem
  arquivo, sha256 do JSON canônico da evidência. Hash sempre de BYTES, nunca de texto normalizado.
"""

import hashlib
import os
import re

from .errors import CsError
from . import jsonio
from . import paths

CONFIDENCE = ("high", "medium", "low")
ORIGINS = ("mechanical", "llm_interpretation")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:@/+-]{0,199}$")
FACT_KEYS = frozenset(["id", "layer", "claim", "evidence", "confidence", "origin", "scope",
                       "fingerprint", "supports", "data"])


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


_SLUG_RE = re.compile(r"[^a-z0-9._-]+")


def slug(text, maxlen=80):
    """Fragmento de id estável: minúsculo, [a-z0-9._-], sem bordas '-'."""
    s = _SLUG_RE.sub("-", text.lower()).strip("-.")
    if len(s) > maxlen:
        s = s[:maxlen - 9].rstrip("-.") + "-" + sha256_bytes(text.encode("utf-8"))[:8]
    return s or "x"


def ev_file(rel, line=None):
    e = {"file": rel}
    if line is not None:
        e["line"] = int(line)
    return e


def ev_cmd(cmd, exit_code, out_bytes, blob=None):
    e = {"cmd": cmd, "exit": int(exit_code), "out_sha256": sha256_bytes(out_bytes)}
    if blob:
        e["blob"] = blob
    return e


def ev_commit(sha, files=None):
    e = {"commit": sha}
    if files:
        e["files"] = sorted(files)
    return e


def store_blob(target, data):
    """Copia bytes de evidência para <alvo>/.swarm/evidence/<sha256>.txt (atômico, idempotente).

    Retorna o path relativo ao alvo.
    """
    digest = sha256_bytes(data)
    rel = "%s/evidence/%s.txt" % (paths.SPECIALISTS_DIRNAME, digest)
    full = os.path.join(target, rel)
    if not os.path.exists(full):
        jsonio.write_bytes_atomic(full, data, target=target)
    return rel


def validate_fact(fact):
    """Erros de schema (lista de str). Vazia = válido."""
    errs = []
    fid = fact.get("id")
    if not isinstance(fid, str) or not ID_RE.match(fid):
        errs.append("id inválido: %r" % (fid,))
    extra = set(fact) - FACT_KEYS
    if extra:
        errs.append("%s: chaves desconhecidas %s" % (fid, sorted(extra)))
    for k in ("layer", "claim", "fingerprint"):
        if not isinstance(fact.get(k), str) or not fact.get(k):
            errs.append("%s: '%s' ausente/vazio" % (fid, k))
    ev = fact.get("evidence")
    if not isinstance(ev, list) or not ev:
        errs.append("%s: evidence vazia" % fid)
    else:
        for item in ev:
            if not isinstance(item, dict) or not ({"file", "cmd", "commit"} & set(item)):
                errs.append("%s: item de evidência sem file/cmd/commit: %r" % (fid, item))
    if fact.get("confidence") not in CONFIDENCE:
        errs.append("%s: confidence fora de %s" % (fid, CONFIDENCE))
    if fact.get("origin") not in ORIGINS:
        errs.append("%s: origin fora de %s" % (fid, ORIGINS))
    if fact.get("origin") == "llm_interpretation" and not fact.get("supports"):
        errs.append("%s: llm_interpretation exige supports=[ids mecânicos]" % fid)
    if not isinstance(fact.get("scope"), list):
        errs.append("%s: scope deve ser lista" % fid)
    if "data" in fact and not isinstance(fact["data"], dict):
        errs.append("%s: data deve ser objeto" % fid)
    return errs


class FactBuilder(object):
    """Constrói fatos de um alvo com cache de sha256 por arquivo e ids únicos por camada.

    fb = FactBuilder(target)
    fb.fact("conv.naming.py", "conventions", "claim...", [ev_file("a.py", 1)], scope=["src/**"])
    """

    def __init__(self, target):
        self.target = target
        self._sha = {}
        self._ids = set()

    def file_sha(self, rel):
        if rel not in self._sha:
            full = os.path.join(self.target, rel)
            if paths.is_within(self.target, full) and os.path.isfile(full):
                self._sha[rel] = sha256_file(full)
            else:
                self._sha[rel] = None
        return self._sha[rel]

    def fingerprint(self, evidence):
        files = sorted(set(e["file"] for e in evidence if "file" in e))
        if files:
            h = hashlib.sha256()
            for f in files:
                h.update(("%s\0%s\n" % (f, self.file_sha(f) or "missing")).encode("utf-8"))
            return h.hexdigest()
        return sha256_bytes(jsonio.dumps(evidence).encode("utf-8"))

    def unique_id(self, fid):
        base, n = fid, 2
        while fid in self._ids:
            fid = "%s-%d" % (base, n)
            n += 1
        self._ids.add(fid)
        return fid

    def fact(self, fid, layer, claim, evidence, confidence="high", origin="mechanical",
             scope=None, supports=None, data=None):
        if not evidence:
            raise CsError("fato %s sem evidência" % fid, "bug do produtor: evidence nunca vazia")
        f = {
            "id": self.unique_id(fid),
            "layer": layer,
            "claim": claim,
            "evidence": evidence,
            "confidence": confidence,
            "origin": origin,
            "scope": sorted(set(scope or [])),
            "fingerprint": self.fingerprint(evidence),
        }
        if supports:
            f["supports"] = sorted(set(supports))
        if data is not None:
            f["data"] = data
        errs = validate_fact(f)
        if errs:
            raise CsError("fato inválido: " + "; ".join(errs), "bug do produtor da camada %s" % layer)
        return f
