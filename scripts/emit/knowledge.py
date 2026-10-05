"""Conhecimento lido de .swarm/facts/ para o emissor (ARCHITECTURE §4 e §8-bis).

- facts: id -> claim (todas as camadas), para resolver invariantes;
- glossary: termos do domínio (facts/glossary.json, camada L9);
- business_rules: regras de negócio (facts/business_rules.json, camada L9).

Leitura defensiva: aceita os nomes de campo prováveis do scan (canonical/term/name,
definition/claim, where/defined_at/evidence[0], never_use/never/forbidden, test/covered_by...).
Seleção por território: só entram itens cuja evidência casa com os globs do agente; top-N por
relevância (contagem/ocorrências no território), desempate pelo nome — determinístico.
"""
import re
from pathlib import Path
from cslib.paths import STATE_DIR

from emit import j5
from emit.common import EmitError, one_line

GLOSSARY_STEM = "glossary"
RULES_STEM = "business_rules"


def glob_to_regex(glob):
    i, out = 0, ["^"]
    while i < len(glob):
        c = glob[i]
        if glob.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
            continue
        if glob.startswith("**", i):
            out.append(".*")
            i += 2
            continue
        if c == "*":
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        elif c == "{":
            j = glob.find("}", i)
            if j < 0:
                out.append(re.escape(c))
            else:
                alts = glob[i + 1:j].split(",")
                out.append("(?:%s)" % "|".join(re.escape(a) for a in alts))
                i = j + 1
                continue
        else:
            out.append(re.escape(c))
        i += 1
    out.append("$")
    return re.compile("".join(out))


def path_in(path, globs):
    if not path:
        return False
    while path.startswith("./"):
        path = path[2:]
    return any(glob_to_regex(g).match(path) for g in globs)


class Knowledge(object):
    def __init__(self, facts=None, glossary=None, business_rules=None):
        self.facts = facts or {}
        self.glossary = glossary or []
        self.business_rules = business_rules or []

    # -------------------------------------------------------------- seleção
    def terms_for(self, globs, limit):
        scored = []
        for t in self.glossary:
            if globs:
                hits = [loc for loc in t["locations"] if path_in(loc.split(":")[0], globs)]
                if not hits:
                    continue
                score = len(hits) * 1000 + t["count"]
            else:
                score = t["count"]
            scored.append((-score, t["kind"] != "business", t["canonical"].lower(), t))
        scored.sort(key=lambda x: x[:3])
        return [x[3] for x in scored[:limit]], len(scored)

    def rules_for(self, globs, limit):
        scored = []
        for r in self.business_rules:
            if globs and not any(path_in(loc.split(":")[0], globs) for loc in r["locations"]):
                continue
            score = (1 if r["source"] == "founder" else 0) * 10 + (1 if r["test"] else 0)
            scored.append((-score, r["text"].lower(), r))
        scored.sort(key=lambda x: x[:2])
        return [x[2] for x in scored[:limit]], len(scored)


def load(root):
    fdir = Path(root) / STATE_DIR / "facts"
    facts = {}
    glossary, rules = [], []
    if fdir.is_dir():
        for path in fact_files(fdir):
            data = _read(path)
            _collect_facts(data, facts)
            stem = path.name.split(".")[0]
            if stem == GLOSSARY_STEM:
                glossary = [t for t in (_norm_term(x) for x in _items(data, ("terms", "glossary", "facts")))
                            if t]
            elif stem == RULES_STEM:
                rules = [r for r in (_norm_rule(x) for x in _items(data, ("rules", "business_rules", "facts")))
                         if r]
    return Knowledge(facts, glossary, rules)


def fact_files(fdir):
    """facts/*.json5 (formato) e *.json (transição); se ambos existem para o mesmo nome, vale o .json5."""
    by_stem = {}
    for p in sorted(fdir.glob("*.json")) + sorted(fdir.glob("*.json5")):
        by_stem[p.name.split(".")[0]] = p
    return [by_stem[k] for k in sorted(by_stem)]


def _read(path):
    try:
        return j5.load(path)
    except ValueError as exc:
        raise EmitError("fato ilegível %s: %s" % (path, exc))


def _collect_facts(node, out):
    if isinstance(node, dict):
        if isinstance(node.get("id"), str) and isinstance(node.get("claim"), str):
            out.setdefault(node["id"], node["claim"])
        for v in node.values():
            _collect_facts(v, out)
    elif isinstance(node, list):
        for v in node:
            _collect_facts(v, out)


def _items(data, keys):
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for k in keys:
            if isinstance(data.get(k), list):
                return [x for x in data[k] if isinstance(x, dict)]
    return []


def _first(d, keys, default=None):
    for k in keys:
        v = d.get(k)
        if v not in (None, "", []):
            return v
    return default


def _loc(v):
    """'a.py:12' | {'file','line'} | [..] -> lista de 'arquivo:linha'."""
    out = []
    if isinstance(v, str):
        out.append(v)
    elif isinstance(v, dict):
        f = v.get("file") or v.get("path")
        if f:
            out.append("%s:%s" % (f, v["line"]) if v.get("line") else f)
    elif isinstance(v, list):
        for x in v:
            out.extend(_loc(x))
    return out


def _norm_term(x):
    canon = _first(x, ("canonical", "term", "name"))
    if not isinstance(canon, str):
        return None
    locs = _loc(_first(x, ("where", "defined_at", "definition_at", "locations", "evidence"), []))
    never = _first(x, ("never_use", "never", "forbidden_variants", "avoid"), []) or []
    if isinstance(never, str):
        never = [never]
    return {
        "canonical": canon,
        "definition": one_line(_first(x, ("definition", "claim", "description", "text"), "") or ""),
        "locations": locs,
        "never": [str(n) for n in never],
        "count": int(_first(x, ("count", "occurrences"), 0) or 0),
        "kind": str(_first(x, ("kind", "category", "type"), "business")),
        "id": x.get("id"),
    }


def _norm_rule(x):
    text = _first(x, ("rule", "text", "claim", "description"))
    if not isinstance(text, str):
        return None
    data = x.get("data") if isinstance(x.get("data"), dict) else {}
    test = _first(x, ("test", "covered_by", "tests")) or _first(data, ("test",))
    if isinstance(test, list):
        test = ", ".join(_loc(test) or [str(t) for t in test])
    elif isinstance(test, dict):
        test = ", ".join(_loc(test))
    src = x.get("source")
    if isinstance(src, dict):
        src = "founder" if "founder" in src else "code"
    return {
        "text": one_line(text),
        "locations": _loc(_first(x, ("where", "enforced_at", "locations", "evidence"), [])),
        "test": test or None,
        # contrato do scan: data.test só com cobertura forte; o resto em data.coverage + data.exercised_by
        "coverage": _first(x, ("coverage",)) or _first(data, ("coverage",)) or ("test" if test else None),
        "exercised_by": _first(x, ("exercised_by",)) or _first(data, ("exercised_by",)),
        "source": src or data.get("source") or "code",
        "id": x.get("id"),
    }
