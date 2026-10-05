"""Helpers comuns dos pacotes facts/interview/panel/verify (só stdlib + cslib).

- leitura de todos os fatos de .swarm/facts/*.json5 (qualquer camada, inclusive interview e
  interpretation), sem depender da forma interna das camadas;
- sincronização do index.json5 (aceita as duas formas existentes: {id: camada} e {facts: [ids]});
- JSONL append-only (leitura estrita: linha corrompida = erro acionável);
- sha256 de bytes e de JSON canônico.
"""

import hashlib
import json
import os

from cslib import CsError, json5io, jsonio, log, paths

INDEX = "index.json5"


def sp(target, *parts):
    return os.path.join(paths.specialists_dir(target), *parts)


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as fh:
        return sha256_bytes(fh.read())


def sha256_obj(obj):
    return sha256_bytes(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                                   separators=(",", ":")).encode("utf-8"))


def now():
    return log.now_iso()


# ------------------------------------------------------------------ JSON5 / JSONL

def read5(path, required=True, default=None):
    """JSON5 (com fallback de leitura .json)."""
    if not os.path.exists(path) and path.endswith(".json5") and os.path.exists(path[:-1]):
        path = path[:-1]
    return json5io.read(path, required=required, default=default)


def write5(target, path, obj, header):
    json5io.dump(obj, path, header, target=target)


def read_jsonl(path):
    """[(nº da linha, registro)] — linha vazia ignorada; linha ilegível = CsError(2)."""
    out = []
    if not os.path.isfile(path):
        return out
    with open(path, "rb") as fh:
        for i, raw in enumerate(fh, start=1):
            s = raw.strip()
            if not s:
                continue
            try:
                rec = json.loads(s.decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as exc:
                raise CsError("%s:%d ilegível (%s)" % (path, i, exc),
                              "arquivo append-only corrompido: restaure do git; nunca edite à mão")
            if isinstance(rec, dict):
                out.append((i, rec))
    return out


def append_jsonl(target, path, rec):
    """Acrescenta e devolve o nº da linha gravada."""
    n = 0
    if os.path.isfile(path):
        with open(path, "rb") as fh:
            n = sum(1 for _ in fh)
    jsonio.append_jsonl(path, rec, target=target)
    return n + 1


# ------------------------------------------------------------------ fatos

def facts_dir(target):
    return paths.facts_dir(target)


def load_all_facts(target):
    """{id: fato} de todos os facts/*.json5|*.json (exceto index). Diretório ausente = CsError."""
    d = facts_dir(target)
    if not os.path.isdir(d):
        raise CsError("diretório de fatos ausente: %s" % d, "rode `cs.py scan` antes")
    out = {}
    names = sorted(os.listdir(d))
    seen_stems = set()
    for fn in names:
        stem, ext = os.path.splitext(fn)
        if ext not in (".json5", ".json") or stem == "index":
            continue
        if ext == ".json" and stem + ".json5" in names:
            continue
        if stem in seen_stems:
            continue
        seen_stems.add(stem)
        data = json5io.read(os.path.join(d, fn))
        facts = data if isinstance(data, list) else (data.get("facts") or [] if isinstance(data, dict) else [])
        for f in facts:
            if isinstance(f, dict) and f.get("id"):
                g = dict(f)
                g.setdefault("layer", stem)
                out.setdefault(g["id"], g)
    return out


def index_ids(target):
    raw = read5(os.path.join(facts_dir(target), INDEX), required=False, default=None)
    if raw is None:
        return set()
    if isinstance(raw, dict) and isinstance(raw.get("facts"), list):
        return set(x["id"] if isinstance(x, dict) else x for x in raw["facts"])
    if isinstance(raw, dict):
        return set(k for k in raw if k not in ("schema_version", "layers"))
    if isinstance(raw, list):
        return set(x["id"] if isinstance(x, dict) else x for x in raw)
    return set()


def index_sync(target, layer, ids, prefix):
    """Troca no index.json5 os ids da camada `layer` (forma {id: camada}) ou com `prefix`
    (forma {facts: [ids]}) pelo conjunto `ids`. Preserva a forma existente."""
    p = os.path.join(facts_dir(target), INDEX)
    raw = read5(p, required=False, default=None)
    header = paths.FACTS_INDEX_HEADER  # o MESMO do scan: conteúdo igual ⇒ hash igual
    if isinstance(raw, dict) and isinstance(raw.get("facts"), list):
        keep = [x for x in raw["facts"] if not str(x if not isinstance(x, dict) else x.get("id")).startswith(prefix)]
        raw["facts"] = sorted(set(str(x if not isinstance(x, dict) else x.get("id")) for x in keep) | set(ids))
        write5(target, p, raw, header)
        return
    idx = dict(raw) if isinstance(raw, dict) else {}
    for k in [k for k, v in idx.items() if v == layer or str(k).startswith(prefix)]:
        del idx[k]
    for i in ids:
        if i in idx and idx[i] != layer:
            raise CsError("id de fato duplicado entre camadas: %s (%s e %s)" % (i, idx[i], layer),
                          "escolha outro id")
        idx[i] = layer
    write5(target, p, idx, header)
