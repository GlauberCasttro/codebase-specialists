"""Conferência de fatos contra o código (scan.5) e correções `llm_interpretation`.

Registros (append-only): <alvo>/.swarm/spotcheck.jsonl
  {ts, fact, verdict: ok|wrong, note, by, correction?}
Correções: <alvo>/.swarm/facts/interpretation.json5 (camada `interpretation`, ids `interp.*`),
  fatos origin=llm_interpretation com supports=[ids mecânicos] e data.corrects=<id do fato errado>.
Check (`facts spotcheck --min N`): ≥N fatos distintos conferidos (vale o último veredito de cada um) e
  todo `wrong` com um fato llm_interpretation que o corrige.
"""

import os

from cslib import CsError, evidence, paths
from facts import store

LAYER = "interpretation"
PREFIX = "interp."
VERDICTS = ("ok", "wrong")


def records_path(target):
    return store.sp(target, "spotcheck.jsonl")


def interp_path(target):
    return os.path.join(store.facts_dir(target), "interpretation.json5")


def corrections(facts):
    """{id corrigido: [ids das correções]} entre fatos llm_interpretation."""
    out = {}
    for f in facts.values():
        if f.get("origin") != "llm_interpretation":
            continue
        corr = (f.get("data") or {}).get("corrects")
        for c in ([corr] if isinstance(corr, str) else (corr or [])):
            out.setdefault(c, []).append(f["id"])
    return out


def _fp(f):
    """Identidade do fato conferido: fingerprint do scan + texto + evidência (re-scan que muda o fato invalida)."""
    return store.sha256_obj({"fp": f.get("fingerprint"), "claim": f.get("claim"), "ev": f.get("evidence")})


def record(target, fact_id, verdict, note, by="orquestrador"):
    if verdict not in VERDICTS:
        raise CsError("--verdict deve ser ok|wrong (veio %r)" % verdict)
    if not (note or "").strip():
        raise CsError("--note vazio", "diga o que foi conferido (ex.: \"src/x.py:10 confirma\")")
    facts = store.load_all_facts(target)
    if fact_id not in facts:
        raise CsError("fato inexistente: %s" % fact_id, "use um id de .swarm/facts/index.json5")
    rec = {"ts": store.now(), "fact": fact_id, "verdict": verdict, "note": note.strip(), "by": by,
           "fingerprint": _fp(facts[fact_id])}
    if verdict == "wrong":
        corr = corrections(facts).get(fact_id)
        if not corr:
            raise CsError("veredito wrong sem correção para %s" % fact_id,
                          "registre antes a correção: `cs.py facts interpret --corrects %s --claim \"...\" "
                          "--supports <ids mecânicos> --evidence <arquivo:linha>`" % fact_id)
        rec["correction"] = sorted(corr)
    store.append_jsonl(target, records_path(target), rec)
    return rec


def status(target, min_n):
    """→ (ok, linhas de relatório, faltas)."""
    facts = store.load_all_facts(target)
    corr = corrections(facts)
    latest = {}
    for _, r in store.read_jsonl(records_path(target)):
        if r.get("fact") and r.get("verdict") in VERDICTS:
            latest[r["fact"]] = r
    lines, problems = [], []
    counted = 0
    for fid in sorted(latest):
        r = latest[fid]
        if fid not in facts:
            problems.append("fato %s conferido não existe mais (re-scan?) — confira de novo" % fid)
            continue
        if facts[fid].get("origin") == "llm_interpretation" or fid.startswith(PREFIX):
            lines.append("(não conta) %s é correção llm_interpretation — conferir a própria correção não é conferência" % fid)
            continue
        if r.get("fingerprint") and r["fingerprint"] != _fp(facts[fid]):
            lines.append("(não conta) fato %s mudou depois da conferência (re-scan) — confira de novo" % fid)
            continue
        counted += 1
        if r["verdict"] == "wrong" and not corr.get(fid):
            problems.append("%s marcado wrong sem fato llm_interpretation que o corrija" % fid)
        lines.append("%-5s %s — %s%s" % (r["verdict"], fid, r.get("note", ""),
                                         (" → " + ", ".join(sorted(corr.get(fid, [])))) if r["verdict"] == "wrong" else ""))
    if counted < min_n:
        problems.append("%d fato(s) conferido(s) < mínimo %d" % (counted, min_n))
    return not problems, lines, problems, counted


def _parse_ev(target, spec):
    rel, _, line = spec.partition(":")
    rel = rel[2:] if rel.startswith("./") else rel
    full = os.path.join(target, rel)
    if not rel or not paths.is_within(target, full) or not os.path.isfile(full):
        raise CsError("evidência inexistente: %s" % spec, "use arquivo:linha de um arquivo do repositório")
    if line:
        if not line.isdigit():
            raise CsError("linha inválida em %s" % spec)
        with open(full, "rb") as fh:
            n = sum(1 for _ in fh)
        if not 1 <= int(line) <= max(n, 1):
            raise CsError("linha %s fora de %s (%d linhas)" % (line, rel, n))
        return evidence.ev_file(rel, int(line))
    return evidence.ev_file(rel)


def interpret(target, fid, claim, supports, evid, corrects=None, scope=None, confidence="medium"):
    if not fid.startswith(PREFIX):
        fid = PREFIX + fid
    if not evidence.ID_RE.match(fid):
        raise CsError("id inválido: %s" % fid, "use [a-z0-9._-]")
    if not (claim or "").strip():
        raise CsError("--claim vazio")
    facts = store.load_all_facts(target)
    sup = sorted(set(s for s in supports if s))
    missing = [s for s in sup if s not in facts]
    if missing:
        raise CsError("supports inexistentes: %s" % missing, "cite ids de .swarm/facts/")
    if not any(facts[s].get("origin", "mechanical") == "mechanical" for s in sup):
        raise CsError("llm_interpretation precisa citar ≥1 fato mecânico em --supports")
    if corrects and corrects not in facts:
        raise CsError("--corrects aponta fato inexistente: %s" % corrects)
    if not evid:
        raise CsError("--evidence obrigatório (arquivo:linha conferido no código)")
    fb = evidence.FactBuilder(target)
    data = {"source": "spotcheck"}
    if corrects:
        data["corrects"] = corrects
    layer_fact = fb.fact(fid, LAYER, claim.strip(), [_parse_ev(target, e) for e in evid],
                         confidence=confidence, origin="llm_interpretation", scope=scope or [],
                         supports=sup, data=data)
    p = interp_path(target)
    doc = store.read5(p, required=False, default=None) or {"schema_version": 1, "layer": LAYER, "facts": []}
    others = [f for f in doc.get("facts") or [] if f.get("id") != fid]
    if fid in facts and fid not in set(f.get("id") for f in doc.get("facts") or []):
        raise CsError("id %s já existe em outra camada" % fid, "escolha outro id")
    doc["facts"] = sorted(others + [layer_fact], key=lambda f: f["id"])
    doc.update({"schema_version": 1, "layer": LAYER, "generator": "cs.py facts interpret"})
    store.write5(target, p, doc, "interpretation — correções llm_interpretation (conferidas no código); "
                                 "gerado por cs.py facts interpret")
    store.index_sync(target, LAYER, [f["id"] for f in doc["facts"]], PREFIX)
    return layer_fact


# ------------------------------------------------------------------ pacote de entrada (scan.5)
# Iteração 4 (ts-shop): o orquestrador escreveu script para montar `{tmp}/in/spotcheck.<lote>.json5` — agora é comando.
PACK_LAYERS = ("rules", "business_rules", "operations", "glossary", "history", "conventions", "rationale",
               "architecture", "stack", "project_docs", "inventory", "graph", "stack_graph")
PACK_DEFAULT_N = 10
PACK_MECANICOS = 30


def _out_ok(target, out):
    """--out fora do alvo ou em <alvo>/.swarm/tmp/ (rascunho; nunca polui o produto)."""
    root = os.path.realpath(target)
    out = os.path.realpath(out)
    if out != root and not out.startswith(root + os.sep):
        return True
    return out.startswith(os.path.join(root, paths.STATE_DIR, "tmp") + os.sep)


def _file_evidence(target, f, cache):
    """'arq:linha' das evidências de arquivo com linha que existem no alvo (linha dentro do arquivo)."""
    out = []
    for e in f.get("evidence") or []:
        if not isinstance(e, dict) or not e.get("file") or not e.get("line"):
            continue
        rel = e["file"]
        full = os.path.join(target, rel)
        if not paths.is_within(target, full) or not os.path.isfile(full):
            continue
        if rel not in cache:
            with open(full, "rb") as fh:
                cache[rel] = sum(1 for _ in fh)
        if 1 <= int(e["line"]) <= max(cache[rel], 1):
            out.append("%s:%d" % (rel, int(e["line"])))
    return out


def _parse_batch(batch):
    if not batch:
        return None
    k, _, m = str(batch).partition("/")
    if not (k.isdigit() and m.isdigit()) or not 1 <= int(k) <= int(m):
        raise CsError("--batch deve ser K/M com 1 ≤ K ≤ M (veio %r)" % batch, "ex.: --batch 1/2")
    return int(k), int(m)


def pack(target, n=PACK_DEFAULT_N, batch=None):
    """Pacote de entrada da conferência (scan.5): `n` fatos mecânicos com evidência `arquivo:linha` existente,
    ainda não conferidos (ou conferidos antes de um re-scan), em rodízio pelas camadas de PACK_LAYERS (ordem
    determinística por sha256 do id). `batch` K/M: fatia disjunta do MESMO pacote (posições i ≡ K-1 mod M); a
    união dos M lotes é o pacote inteiro. → dict {kind: "spotcheck-pack", facts, mecanicos, record_cmd, ...}."""
    if n < 1:
        raise CsError("--n deve ser ≥ 1")
    km = _parse_batch(batch)
    facts = store.load_all_facts(target)
    done = {}
    for _, r in store.read_jsonl(records_path(target)):
        if r.get("fact") in facts and r.get("verdict") in VERDICTS:
            done[r["fact"]] = r
    cache = {}
    by_layer = {}
    for fid, f in facts.items():
        if f.get("origin", "mechanical") != "mechanical" or fid.startswith(PREFIX):
            continue
        r = done.get(fid)
        if r and (not r.get("fingerprint") or r["fingerprint"] == _fp(f)):
            continue  # já conferido sobre o fato atual
        ev = _file_evidence(target, f, cache)
        if not ev or not (f.get("claim") or "").strip():
            continue
        by_layer.setdefault(f.get("layer"), []).append((store.sha256_bytes(fid.encode("utf-8")), fid, ev))
    order = [l for l in PACK_LAYERS if l in by_layer] + sorted(l for l in by_layer if l not in PACK_LAYERS)
    queues = [sorted(by_layer[l]) for l in order]
    picked = []
    while len(picked) < n and any(queues):
        for q in queues:
            if q and len(picked) < n:
                picked.append(q.pop(0))
    if km:
        k, m = km
        if m > len(picked):
            raise CsError("--batch %d/%d: só %d fato(s) no pacote" % (k, m, len(picked)), "use menos lotes")
        picked = [p for i, p in enumerate(picked) if i % m == k - 1]
    out_facts = []
    files = set()
    for _, fid, ev in picked:
        f = facts[fid]
        out_facts.append({"id": fid, "layer": f.get("layer"), "text": f.get("claim"), "claim": f.get("claim"),
                          "evidence": ev, "confidence": f.get("confidence"), "origin": f.get("origin", "mechanical"),
                          "scope": f.get("scope") or []})
        files |= set(e.rsplit(":", 1)[0] for e in ev)
    chosen = set(f["id"] for f in out_facts)
    mec = sorted(fid for fid, f in facts.items() if fid not in chosen and f.get("origin", "mechanical") == "mechanical"
                 and any(isinstance(e, dict) and e.get("file") in files for e in f.get("evidence") or []))
    return {"schema_version": 1, "kind": "spotcheck-pack", "generator": "cs.py facts spotcheck pack",
            "batch": "%d/%d" % km if km else None, "n": len(out_facts), "facts": out_facts,
            "fatos": out_facts, "mecanicos": mec[:PACK_MECANICOS],
            "record_cmd": "cs.py facts spotcheck record --fact <id> --verdict ok|wrong --note \"<o que foi conferido>\"",
            "interpret_cmd": "cs.py facts interpret --id <id> --claim \"...\" --supports <ids mecânicos> "
                             "--evidence <arquivo:linha> --corrects <id do fato errado>",
            "check_cmd": "cs.py facts spotcheck --min 5"}


def write_pack(target, out, n=PACK_DEFAULT_N, batch=None):
    if not _out_ok(target, out):
        raise CsError("--out dentro do alvo só em %s/tmp/ (senão o pacote polui o produto): %s" % (paths.STATE_DIR, out),
                      "use %s/<nome>.json5 ou um caminho fora do alvo"
                      % os.path.join(os.path.realpath(target), paths.STATE_DIR, "tmp", "in"))
    doc = pack(target, n=n, batch=batch)
    if not doc["facts"]:
        raise CsError("nenhum fato a conferir: todos os fatos com evidência arquivo:linha já foram conferidos",
                      "rode o check: cs.py facts spotcheck --min 5")
    out = os.path.realpath(out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    from cslib import json5io
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(json5io.dumps(doc, "pacote de entrada do spot-check (scan.5) — cs.py facts spotcheck pack"))
    return out, doc
