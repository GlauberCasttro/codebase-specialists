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
