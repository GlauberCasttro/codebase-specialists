"""cs.py probes memory-recall — gate G8 (ARCHITECTURE §8-bis).

Para cada sonda positiva do tipo TERMO/REGRA-DE-NEGÓCIO, consulta a busca de memória com o texto da
pergunta e verifica se o fato-gabarito (atomic_facts[0]) está no top-5. Mede latência de cada busca.
  recall@5 ≥ 0,90 e latência p95 < 200 ms.
Latência do gate = `ms` reportado pela própria busca (tempo de busca em processo); a latência de
parede (inclui partida do interpretador) também é registrada. A 1ª chamada aquece/constrói o índice e
fica fora da medida.
Busca: <skill>/scripts/memory/cli.py ou mem.py (ou --mem <arquivo>), `--root <alvo> search Q -k 5 --json`.
"""
import json
import math
import os
import subprocess
import sys
import time

from team._shared_tmp.common import CsError, sp_path, write_json
from probes.generate import load_bank

RECALL_MIN, P95_MAX_MS, K = 0.90, 200.0, 5
TYPES = ("term", "business_rule")


def find_mem(explicit=None):
    if explicit:
        if not os.path.isfile(explicit):
            raise CsError("busca de memória não encontrada: %s" % explicit)
        return explicit
    scripts = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for c in (os.path.join(scripts, "memory", "cli.py"), os.path.join(scripts, "memory", "mem.py")):
        if os.path.isfile(c):
            return c
    raise CsError("busca de memória ausente (scripts/memory/cli.py ou mem.py)",
                  "instale o componente de memória do harness ou passe --mem <caminho do mem.py>")


def _ids(obj):
    out = []
    if isinstance(obj, dict):
        for k in ("id", "fact_id", "fact"):
            if isinstance(obj.get(k), str):
                out.append(obj[k])
        src = obj.get("source")
        if isinstance(src, dict) and isinstance(src.get("fact_id"), str):
            out.append(src["fact_id"])
    return out


def search(mem, target, query, k=K):
    cmd = [sys.executable, mem, "--root", target, "search", query, "-k", str(k), "--json"]
    t0 = time.time()
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        raise CsError("falha ao executar a busca de memória: %s" % exc)
    wall = (time.time() - t0) * 1000.0
    if r.returncode != 0:
        raise CsError("busca de memória saiu com %d: %s" % (r.returncode, r.stderr.decode("utf-8", "replace")[-400:]),
                      "confira `%s search --help`" % os.path.basename(mem))
    try:
        data = json.loads(r.stdout.decode("utf-8"))
    except ValueError:
        raise CsError("busca de memória não devolveu JSON com --json")
    results = data.get("results", data.get("hits")) if isinstance(data, dict) else data
    if not isinstance(results, list):
        raise CsError("saída da busca sem lista de resultados")
    ids = [i for x in results[:k] for i in _ids(x)]
    ms = data.get("ms") if isinstance(data, dict) and isinstance(data.get("ms"), (int, float)) else wall
    return ids, float(ms), wall


def p95(xs):
    if not xs:
        return None
    s = sorted(xs)
    return round(s[max(0, int(math.ceil(0.95 * len(s))) - 1)], 2)


def memory_recall(target, mem=None):
    mem = find_mem(mem)
    bank = load_bank(target)
    probes = [p for p in bank["probes"] if p["type"] in TYPES and not p.get("negative")
              and p.get("atomic_facts")]
    if not probes:
        raise CsError("banco sem sondas TERMO/REGRA positivas",
                      "confira facts/glossary.json5 e facts/business_rules.json5 e rode `probes generate`")
    search(mem, target, probes[0]["question"])  # aquecimento (constrói índice)
    rows, lat, walls, seen = [], [], [], set()
    for p in probes:
        key = (p["question"], p["atomic_facts"][0])
        if key in seen:
            continue
        seen.add(key)
        ids, ms, wall = search(mem, target, p["question"])
        exp = p["atomic_facts"][0]
        hit = exp in ids
        rows.append({"id": p["id"], "type": p["type"], "expected": exp, "hit": hit,
                     "rank": (ids.index(exp) + 1) if hit else None, "ms": round(ms, 2)})
        lat.append(ms)
        walls.append(wall)
    recall = round(sum(1 for r in rows if r["hit"]) / float(len(rows)), 4)
    lp95 = p95(lat)
    rep = {"schema_version": 1, "gate": "G8", "k": K, "queries": len(rows), "recall_at_5": recall,
           "latency_p95_ms": lp95, "wall_p95_ms": p95(walls),
           "thresholds": {"recall_at_5": RECALL_MIN, "latency_p95_ms": P95_MAX_MS},
           "pass": recall >= RECALL_MIN and lp95 < P95_MAX_MS, "mem": os.path.basename(mem),
           "misses": [r for r in rows if not r["hit"]], "rows": rows}
    write_json(target, sp_path(target, "probes", "memory-recall.json5"), rep)
    return rep
