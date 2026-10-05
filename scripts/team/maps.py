"""cs.py team maps — mapas de dependência e colisão entre territórios (ARCHITECTURE §8-nonies).

  .swarm/knowledge/deps.json5       matriz território×território (nº de arestas do graph L1,
                                          exemplos arquivo:linha do import), ciclos (SCC) entre
                                          territórios e entre arquivos
  .swarm/knowledge/collision.json5  risco por par = dependência estática + co-change histórico
                                          (L5: suporte/confiança) + arquivos de fronteira;
                                          `do_not_parallelize` acima do limiar, com o porquê

Risco (0..1) = 0,4·min(1, arestas/5) + 0,4·max(confiança de co-change) + 0,2·min(1, fronteira/4).
Limiar padrão 0,30 (calibrar). Território = expansão real dos globs do team.json5 (escritores).
Co-change: TODO(integrador) trocar Facts.cochange() pelo helper de cslib quando exposto.
"""
import os
import re

from team._shared_tmp.common import CsError, expand, read_json, read_lines, sp_path, write_json
from team._shared_tmp.factsio import Facts

THRESHOLD = 0.30
W_STATIC, W_CO, W_BOUND = 0.4, 0.4, 0.2
MAX_EXAMPLES = 5
IMPORT_HINT = re.compile(r"\b(import|from|require|include|use|using)\b|#include")


def _owners(team, product):
    owner = {}
    names = []
    for a in team.get("agents") or []:
        if a.get("kind") == "gate" or not a.get("territory"):
            continue
        names.append(a["name"])
        for p in expand(a["territory"], product):
            owner.setdefault(p, a["name"])
    return owner, sorted(names)


def _import_line(target, src, dst):
    """Linha do import de dst em src (heurística: linha com palavra de import e o stem/módulo de dst)."""
    stem = os.path.splitext(dst.rsplit("/", 1)[-1])[0]
    mod = os.path.splitext(dst)[0].replace("/", ".")
    keys = [k for k in (mod, os.path.splitext(dst)[0], stem) if k and k not in ("__init__", "index")]
    if stem in ("__init__", "index"):
        keys.append(dst.rsplit("/", 2)[-2] if "/" in dst else stem)
    for i, ln in enumerate(read_lines(target, src) or []):
        if IMPORT_HINT.search(ln) and any(k in ln for k in keys):
            return i + 1
    return None


def _scc(nodes, adj):
    """Tarjan iterativo; devolve componentes com >1 nó (ou laço próprio), ordenados."""
    index, low, on, stack, out = {}, {}, set(), [], []
    counter = [0]
    for root in sorted(nodes):
        if root in index:
            continue
        work = [(root, iter(sorted(adj.get(root, ()))))]
        index[root] = low[root] = counter[0]
        counter[0] += 1
        stack.append(root)
        on.add(root)
        while work:
            v, it = work[-1]
            pushed = False
            for w in it:
                if w not in index:
                    index[w] = low[w] = counter[0]
                    counter[0] += 1
                    stack.append(w)
                    on.add(w)
                    work.append((w, iter(sorted(adj.get(w, ())))))
                    pushed = True
                    break
                elif w in on:
                    low[v] = min(low[v], index[w])
            if pushed:
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[v])
            if low[v] == index[v]:
                comp = []
                while True:
                    w = stack.pop()
                    on.discard(w)
                    comp.append(w)
                    if w == v:
                        break
                if len(comp) > 1:
                    out.append(sorted(comp))
    return sorted(out)


def _cycle_path(comp, adj):
    """Um ciclo concreto dentro da SCC (para o porquê), começando pelo menor nó."""
    s = comp[0]
    cs = set(comp)
    prev, frontier, seen = {}, [s], {s}
    while frontier:
        nxt = []
        for v in frontier:
            for w in sorted(adj.get(v, ())):
                if w == s:
                    path = [v]
                    while path[-1] != s:
                        path.append(prev[path[-1]])
                    return list(reversed(path)) + [s]
                if w in cs and w not in seen:
                    seen.add(w)
                    prev[w] = v
                    nxt.append(w)
        frontier = nxt
    return comp + [s]


def build_maps(target, threshold=THRESHOLD):
    facts = Facts(target)
    if not facts.has_graph():
        raise CsError("graph.json5 ausente: mapas de dependência exigem o grafo L1", "rode `cs.py scan` (L1)")
    team = read_json(sp_path(target, "team.json5"), "team.json5")
    product = facts.product_files()
    owner, names = _owners(team, product)
    if not names:
        raise CsError("team.json5 sem territórios de escrita", "rode `cs.py team derive` antes")
    edges = facts.edges()
    matrix = {a: {b: 0 for b in names} for a in names}
    examples = {}
    unowned = 0
    tadj = {}
    fadj = {}
    bound_by = {}
    for s, t in edges:
        fadj.setdefault(s, set()).add(t)
        a, b = owner.get(s), owner.get(t)
        if not a or not b:
            unowned += 1
            continue
        if a == b:
            continue
        matrix[a][b] += 1
        bound_by.setdefault(tuple(sorted((a, b))), set()).update((s, t))
        tadj.setdefault(a, set()).add(b)
        ex = examples.setdefault((a, b), [])
        if len(ex) < MAX_EXAMPLES:
            ex.append({"file": s, "line": _import_line(target, s, t), "imports": t})
    pairs = [{"from": a, "to": b, "edges": matrix[a][b], "examples": examples.get((a, b), [])}
             for a in names for b in names if a != b and matrix[a][b]]
    tcycles = [{"territories": c, "path": _cycle_path(c, tadj)} for c in _scc(names, tadj)]
    fnodes = sorted(set(x for e in edges for x in e))
    fcycles = []
    for c in _scc(fnodes, fadj):
        terrs = sorted(set(owner.get(p, "?") for p in c))
        fcycles.append({"files": c, "path": _cycle_path(c, fadj), "territories": terrs,
                        "cross_territory": len(terrs) > 1})
    deps = {"schema_version": 1, "territories": names, "matrix": matrix, "pairs": pairs,
            "edges_total": len(edges), "edges_cross_territory": sum(p["edges"] for p in pairs),
            "edges_unowned": unowned, "cycles": {"territory": tcycles, "file": fcycles[:100]},
            # forma de grafo exigida por emit validate (check_graph) e lida por panel plan
            "nodes": [{"id": n} for n in names],
            "edges": [{"from": p["from"], "to": p["to"], "count": p["edges"]} for p in pairs]}

    # colisão
    co = {}
    for c in facts.cochange():
        a, b = owner.get(c["a"]), owner.get(c["b"])
        if not a or not b or a == b:
            continue
        k = tuple(sorted((a, b)))
        co.setdefault(k, []).append(c)
    rows, dnp = [], []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            static = matrix[a][b] + matrix[b][a]
            cc = sorted(co.get((a, b), []), key=lambda x: (-max(x["conf_a_b"], x["conf_b_a"]), -x["support"], x["a"]))
            conf = max([max(x["conf_a_b"], x["conf_b_a"]) for x in cc] or [0.0])
            support = sum(x["support"] for x in cc)
            bound = set(bound_by.get((a, b), ()))
            for x in cc:
                bound.update((x["a"], x["b"]))
            if not static and not cc:
                continue
            risk = round(W_STATIC * min(1.0, static / 5.0) + W_CO * min(1.0, conf)
                         + W_BOUND * min(1.0, len(bound) / 4.0), 4)
            why = []
            if static:
                ex = (examples.get((a, b)) or examples.get((b, a)) or [{}])[0]
                why.append("%d aresta(s) de import (ex.: %s%s → %s)" % (
                    static, ex.get("file"), (":%s" % ex["line"]) if ex.get("line") else "", ex.get("imports")))
            if cc:
                why.append("co-change: suporte %d, confiança máx %.2f (%s ↔ %s)" % (support, conf, cc[0]["a"], cc[0]["b"]))
            why.append("%d arquivo(s) de fronteira" % len(bound))
            row = {"pair": [a, b], "risk": risk, "static_edges": static, "cochange_support": support,
                   "cochange_confidence": round(conf, 4), "cochange_facts": sorted(x["fact"] for x in cc if x.get("fact")),
                   "boundary_files": sorted(bound)[:30], "boundary_count": len(bound), "why": "; ".join(why)}
            rows.append(row)
            if risk >= threshold:
                dnp.append({"pair": [a, b], "risk": risk, "why": row["why"]})
    rows.sort(key=lambda r: (-r["risk"], r["pair"]))
    dnp.sort(key=lambda r: (-r["risk"], r["pair"]))
    collision = {"schema_version": 1, "threshold": threshold,
                 "weights": {"static": W_STATIC, "cochange": W_CO, "boundary": W_BOUND},
                 "formula": "0.4*min(1,edges/5) + 0.4*max_conf_cochange + 0.2*min(1,boundary/4)",
                 "pairs": rows, "do_not_parallelize": dnp,
                 "nodes": [{"id": n} for n in names],
                 "edges": [{"from": r["pair"][0], "to": r["pair"][1], "risk": r["risk"]} for r in rows],
                 "cochange_source": "facts/history (L5)" if facts.cochange() else "ausente (sem histórico)"}
    write_json(target, sp_path(target, "knowledge", "deps.json5"), deps,
               "deps.json5 — matriz de dependência território×território; gerado por cs.py team maps")
    write_json(target, sp_path(target, "knowledge", "collision.json5"), collision,
               "collision.json5 — risco de colisão por par de territórios; gerado por cs.py team maps")
    return deps, collision
