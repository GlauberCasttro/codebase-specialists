"""L9 domínio (ARCHITECTURE.md §8-bis) → facts/glossary.json + facts/business_rules.json.

Glossário (mecânico):
- termos vêm de DEFINIÇÕES: tipos (class/interface/type/enum/struct/record/trait), tabelas SQL e de
  ORM (__tablename__, @Table, [Table]), segmentos de rotas HTTP, definições em docs (`- **Termo**: def`,
  linhas de tabela de glossário) e títulos de ADR;
- forma canônica = partes do identificador em minúsculas sem acento ("OrderItem" → "order item");
- contagem = ocorrências da sequência de partes em todo código/doc analisado (OrderItem, order_item,
  order-item e "order item" contam igual), mais menções em nomes de teste;
- variantes = mesmas partes coladas ("orderitem") ou singular/plural; variante RARA (≤20% da canônica,
  canônica ≥80% do total) vira `never_use`;
- sinônimos = alias explícito no código (`Client = Customer`, `type Client = Customer`) ou em docs
  ("X (aka Y)", "X, também chamado de Y", "X ou Y" em linha de glossário);
- classe: `technical` se alguma parte é palavra técnica; senão `business` se definido/mencionado em
  domínio/models/entities/migrations/schema, tabela SQL, glossário de doc ou ADR; senão `technical`.

Regras de negócio (mecânico, scan/rules_extract.py): validações (raise/throw/errors.New/die com guarda
`if`; mensagem com palavra de regra ou exceção definida no repo), limites nomeados com o VALOR da
definição (expressão aritmética avaliada), formatos (padrões regex nomeados), estados de enum (inclusive
Go e `CREATE TYPE ... AS ENUM`), tabelas de transição, CHECK de SQL e nomes de teste que expressam regra.
Cada regra traz arquivo:linha e a cobertura por teste (scan/coverage.py: import + símbolo + mensagem,
com nível message|exception|reference|asserted|exercised|undetermined|none — nunca "sem teste" nem
"não prova" por palpite: `exercised` diz "não determinado", não "não prova").
"""

import re

from cslib import paths
from cslib.evidence import ev_cmd, ev_file, slug
from cslib.jsonio import dumps
from cslib.tokenize import split_identifier
from . import coverage, l6_rationale, rules_extract

GLOSSARY = "glossary"
RULES = "business_rules"

TECH_WORDS = frozenset("""
abstract adapter api app args async base bash bin bool buf buffer builder bytes cache callback cfg
char class cli client cmd codec config conf conn connection const context controller ctx cursor
dao data db debug decoder decorator default dict dir driver dto encoder engine enum env err error
event exception exec executor factory fake file fixture flag fmt formatter func function gateway
handler hash helper hook html http https id impl index info init input int interface io item
iterator json key lib list listener loader lock log logger loop manager map mapper meta middleware
mixin mock model module msg mutex node num obj object opt option options output param parser path
payload plugin pool port provider proxy queue reader record ref registry render renderer repo
repository request resolver resource response result router runner runtime schema script sdk
serializer server service session setting settings setup shell sql stack state store str stream
string struct stub sync task temp template test tests thread timer tmp token tool type types url
util utils uuid validator value var view visitor worker wrapper writer xml yaml
""".split())
BUSINESS_DIRS = frozenset(["domain", "domains", "model", "models", "entities", "entity", "migrations",
                           "migration", "schema", "schemas", "aggregates", "valueobjects",
                           "value_objects", "dominio", "modelos", "entidades"])
TEST_RULE_WORDS = frozenset("""
cannot cant must should rejects reject rejected forbid forbids forbidden only requires require
limit limits exceed exceeds invalid never always deny denies denied block blocks blocked refuse
refuses nao deve nunca sempre bloqueia recusa rejeita exige proibe falha fails fail_closed
""".split())
TYPE_DEF = {
    "python": re.compile(r"^[ \t]*class\s+([A-Za-z_]\w*)\s*(?:\(([^)]*)\))?\s*:", re.M),
    "javascript": re.compile(r"\b(class)\s+([A-Z]\w*)"),
    "typescript": re.compile(r"\b(class|interface|type|enum)\s+([A-Z]\w*)"),
    "go": re.compile(r"^type\s+([A-Z]\w*)\s+(struct|interface|\w+)", re.M),
    "java": re.compile(r"\b(class|interface|enum|record)\s+([A-Z]\w*)"),
    "kotlin": re.compile(r"\b(class|interface|object|enum class)\s+([A-Z]\w*)"),
    "csharp": re.compile(r"\b(class|interface|enum|record|struct)\s+([A-Z]\w*)"),
    "ruby": re.compile(r"^[ \t]*(class|module)\s+([A-Z]\w*)", re.M),
    "rust": re.compile(r"\b(struct|enum|trait|type)\s+([A-Z]\w*)"),
    "php": re.compile(r"\b(class|interface|trait|enum)\s+([A-Z]\w*)"),
    "swift": re.compile(r"\b(class|struct|enum|protocol)\s+([A-Z]\w*)"),
    "scala": re.compile(r"\b(class|trait|object)\s+([A-Z]\w*)"),
}
SQL_TABLE = re.compile(r"\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"`\[]?(?:\w+[\"`\]]?\.[\"`\[]?)?(\w+)",
                       re.I)
ORM_TABLE = re.compile(r"__tablename__\s*=\s*['\"](\w+)['\"]|@Table\(\s*name\s*=\s*\"(\w+)\"|"
                       r"\[Table\(\s*\"(\w+)\"|db_table\s*=\s*['\"](\w+)['\"]|"
                       r"create_table\s*\(?\s*[:'\"](\w+)")
ROUTE = re.compile(r"(?:@\w+\.(?:get|post|put|patch|delete|route|api_route)|"
                   r"\b(?:app|router|api|r|server)\.(?:get|post|put|patch|delete|route|all)|"
                   r"@(?:Get|Post|Put|Patch|Delete|Request)Mapping|"
                   r"\[(?:Http(?:Get|Post|Put|Patch|Delete)|Route)|\bpath)\s*\(\s*(?:path\s*=\s*|value\s*=\s*)?"
                   r"[\"'`](/[^\"'`]*)[\"'`]")
DOC_DEF = re.compile(r"^\s*[-*]\s+\*\*([^*\n]{2,60})\*\*\s*(?:\(([^)\n]{2,60})\))?\s*[:—–-]\s*(.{3,})$", re.M)
DOC_TABLE = re.compile(r"^\|\s*\**([A-Za-zÀ-ÿ][^|*\n]{1,50}?)\**\s*\|\s*([^|\n]{3,})\|", re.M)
DOC_SYN = re.compile(r"\b(?:aka|a\.k\.a\.|also known as|também chamad[oa] de|tambem chamad[oa] de|"
                     r"sinônimo(?: de)?|sinonimo(?: de)?|alias(?: de)?)\s*:?\s*\**([A-Za-zÀ-ÿ][\w\- ]{1,40})", re.I)
PY_ALIAS = re.compile(r"^([A-Z][A-Za-z0-9]+)\s*=\s*([A-Z][A-Za-z0-9]+)\s*$", re.M)
TS_ALIAS = re.compile(r"\btype\s+([A-Z]\w*)\s*=\s*([A-Z]\w*)\s*;")

ENUM_BASES = re.compile(r"\b(Enum|IntEnum|StrEnum|Flag|IntFlag)\b")


def _line(text, pos):
    return text.count("\n", 0, pos) + 1


def _parts(name):
    return tuple(p for p in split_identifier(name) if p)


def _lemma(parts):
    j = "".join(parts)
    for suf in ("ies", "es", "s"):
        if len(j) > 4 and j.endswith(suf):
            return j[:-len(suf)] + ("y" if suf == "ies" else "")
    return j


def _scope(files):
    return sorted(set(paths.component_of(f) + "/**" if "/" in f else f for f in files))


def _is_doc(rel):
    return paths.lang_of(rel) in ("markdown", "rst") or rel.lower().endswith(".txt")


def collect_terms(ctx, adrs):
    """Definições → {parts: {"names": {surface: n}, "defs": [(file, line, kind, def_text)]}}"""
    terms = {}

    def add(name, rel, line, kind, text=None):
        parts = _parts(name)
        if not parts or len("".join(parts)) < 3 or all(len(p) < 2 for p in parts):
            return
        t = terms.setdefault(parts, {"names": {}, "defs": []})
        t["names"][name] = t["names"].get(name, 0) + 1
        t["defs"].append((rel, line, kind, text))

    enums = []
    aliases = []
    for rel in ctx.files:
        lang = paths.lang_of(rel)
        is_test = paths.is_test_file(rel)
        text = None
        rx = TYPE_DEF.get(lang)
        if rx and not is_test:
            text = ctx.text(rel)
            for m in rx.finditer(text):
                if lang == "python":
                    name, kind, bases = m.group(1), "class", m.group(2) or ""
                    if ENUM_BASES.search(bases):
                        kind = "enum"
                elif lang == "go":
                    name, kind = m.group(1), m.group(2)
                else:
                    kind, name = m.group(1), m.group(2)
                if re.search(r"(Test|Tests|TestCase|Spec|Mock|Fake|Stub)$", name) or name.startswith("_"):
                    continue
                ln = _line(text, m.start())
                add(name, rel, ln, kind)
                if kind == "enum" or (kind in ("enum class",) or (lang != "python" and kind == "enum")):
                    enums.append((name, rel, ln, lang))
            for arx in (PY_ALIAS, TS_ALIAS):
                for m in arx.finditer(text):
                    if m.group(1) != m.group(2):
                        aliases.append((m.group(1), m.group(2), rel, _line(text, m.start())))
        if lang == "sql" or "migration" in rel.lower():
            text = text if text is not None else ctx.text(rel)
            for m in SQL_TABLE.finditer(text):
                add(m.group(1), rel, _line(text, m.start()), "table")
        if paths.is_code(rel) and not is_test:
            text = text if text is not None else ctx.text(rel)
            for m in ORM_TABLE.finditer(text):
                name = next(g for g in m.groups() if g)
                add(name, rel, _line(text, m.start()), "table")
            for m in ROUTE.finditer(text):
                for seg in m.group(1).split("/"):
                    if seg and not re.match(r"^[:{<\[*]|^v\d+$|^api$", seg) and re.match(r"^[\w-]+$", seg):
                        add(seg, rel, _line(text, m.start()), "route")
        if _is_doc(rel):
            text = text if text is not None else ctx.text(rel)
            for m in DOC_DEF.finditer(text):
                add(m.group(1).strip(), rel, _line(text, m.start()), "doc", m.group(3).strip()[:240])
                if m.group(2) and "," not in m.group(2) and len(m.group(2).split()) <= 3:
                    aliases.append((m.group(2).strip(), m.group(1).strip(), rel, _line(text, m.start())))
                sm = DOC_SYN.search(m.group(3))
                if sm:
                    aliases.append((sm.group(1).strip(), m.group(1).strip(), rel, _line(text, m.start())))
            if re.search(r"(?im)^#+\s*(gloss|glossário|glossario|termos|terminologia|vocabul)", text):
                for m in DOC_TABLE.finditer(text):
                    head = m.group(1).strip()
                    if head.lower() in ("termo", "term", "nome", "name") or set(head) <= set("-: "):
                        continue
                    add(head, rel, _line(text, m.start()), "doc", m.group(2).strip()[:240])
    for a in adrs:
        add(a["title"], a["file"], 1, "adr") if len(_parts(a["title"])) <= 4 else None
    return terms, enums, aliases


def count_ngrams(ctx, keys):
    """Ocorrências de cada tupla de partes em código+docs analisados (stream de partes por arquivo).

    Retorna ({key: total}, {key: {file: n}}, {key: n_em_nomes_de_teste}).
    """
    by_first = {}
    for k in keys:
        by_first.setdefault(k[0], set()).add(len(k))
    total = dict.fromkeys(keys, 0)
    per_file = {k: {} for k in keys}
    for rel in ctx.files:
        if not (paths.is_code(rel) or _is_doc(rel) or paths.lang_of(rel) == "sql"):
            continue
        text = ctx.text(rel)
        if not text:
            continue
        toks = []
        for w in re.findall(r"[A-Za-zÀ-ÿ0-9]+(?:[_-][A-Za-zÀ-ÿ0-9]+)*", text):
            toks.extend(split_identifier(w))
        n = len(toks)
        for i, tok in enumerate(toks):
            lens = by_first.get(tok)
            if not lens:
                continue
            for L in lens:
                k = tuple(toks[i:i + L])
                if k in total:
                    total[k] += 1
                    pf = per_file[k]
                    pf[rel] = pf.get(rel, 0) + 1
    return total, per_file


def variants_for(parts):
    out = set()
    if len(parts) > 1:
        out.add(("".join(parts),))
    last = parts[-1]
    if last.endswith("ies") and len(last) > 4:
        out.add(parts[:-1] + (last[:-3] + "y",))
    elif last.endswith("s") and len(last) > 3:
        out.add(parts[:-1] + (last[:-1],))
    else:
        out.add(parts[:-1] + (last + "s",))
    out.discard(parts)
    return out


def build_glossary(ctx, adrs, test_units):
    fb = ctx.fb
    terms, enums, aliases = collect_terms(ctx, adrs)
    keys = set(terms)
    var_map = {}
    for k in terms:
        for v in variants_for(k):
            var_map.setdefault(k, set()).add(v)
            keys.add(v)
    total, per_file = count_ngrams(ctx, keys)
    # menções em nomes de teste
    test_mentions = {}
    for u in test_units:
        for name in u.get("test_names", []):
            ps = tuple(split_identifier(name))
            for k in terms:
                L = len(k)
                if any(ps[i:i + L] == k for i in range(len(ps) - L + 1)):
                    test_mentions.setdefault(k, set()).add(u["file"])
    adr_files = set(a["file"] for a in adrs)
    alias_by_parts = {}
    for a, b, rel, ln in aliases:
        pa, pb = _parts(a), _parts(b)
        if pa and pb and pa != pb:
            alias_by_parts.setdefault(pb, set()).add((pa, rel, ln))
            alias_by_parts.setdefault(pa, set()).add((pb, rel, ln))
    # agrupa por lema: termos distintos que são variantes uns dos outros se fundem no mais frequente
    groups = {}
    for k in terms:
        groups.setdefault(_lemma(k), []).append(k)
    out = []
    for lemma in sorted(groups):
        members = sorted(groups[lemma], key=lambda k: (-total.get(k, 0), k))
        canon = members[0]
        info = {"names": {}, "defs": []}
        for k in members:
            for n, c in terms[k]["names"].items():
                info["names"][n] = info["names"].get(n, 0) + c
            # o 1º elemento marca se a definição é da forma canônica (Delivery) ou de uma variante
            # fundida pelo lema (Deliveries): nome e localização citados vêm da MESMA definição
            info["defs"].extend((k != canon,) + d for d in terms[k]["defs"])
        forms = {}
        for k in set(members) | set(v for k in members for v in var_map.get(k, ())):
            if total.get(k, 0) > 0:
                forms[k] = total[k]
        canon_count = total.get(canon, 0)
        all_count = sum(forms.values()) or canon_count
        never = []
        variants = []
        for k, n in sorted(forms.items(), key=lambda kv: (-kv[1], kv[0])):
            if k == canon:
                continue
            variants.append({"form": " ".join(k), "count": n})
            if canon_count >= 3 and n <= 0.2 * canon_count and canon_count >= 0.8 * all_count \
                    and _lemma(k) == _lemma(canon) and len(k) != len(canon):
                never.append(" ".join(k))
        defs = [d[1:] for d in sorted(set(info["defs"]), key=lambda d: (d[0], d[3] in ("doc", "adr"), d[1], d[2]))]
        def_files = sorted(set(d[0] for d in defs))
        files = per_file.get(canon, {})
        biz = []
        if any(set(f.split("/")[:-1]) & BUSINESS_DIRS for f in def_files):
            biz.append("definido em diretório de domínio")
        if any(d[2] == "table" for d in defs):
            biz.append("tabela")
        if any(d[2] == "doc" for d in defs):
            biz.append("glossário/doc")
        if adr_files & set(files) or any(d[2] == "adr" for d in defs):
            biz.append("ADR")
        if any(set(f.split("/")[:-1]) & BUSINESS_DIRS for f in files):
            biz.append("usado em domínio")
        tech = [p for p in canon if p in TECH_WORDS]
        klass = "technical" if tech or not biz else "business"
        syns = sorted(set(" ".join(p) for k in members for (p, _, _) in alias_by_parts.get(k, ())))
        syn_ev = sorted(set((rel, ln) for k in members for (_, rel, ln) in alias_by_parts.get(k, ())))
        canon_names = terms[canon]["names"]
        surface = sorted(canon_names.items(), key=lambda kv: (-kv[1], kv[0])) or \
            sorted(info["names"].items(), key=lambda kv: (-kv[1], kv[0]))
        other_surfaces = sorted(n for k in members if k != canon for n in terms[k]["names"])
        definition = next((d[3] for d in defs if d[3]), None)
        out.append({
            "term": " ".join(canon),
            "canonical": surface[0][0] if surface else " ".join(canon),
            "merged_forms": other_surfaces,
            "count": canon_count,
            "count_all_forms": all_count,
            "files": len(files),
            "defined_at": [{"file": d[0], "line": d[1], "kind": d[2]} for d in defs[:8]],
            "definition": definition,
            "synonyms": syns,
            "synonym_evidence": [{"file": r, "line": ln} for r, ln in syn_ev[:5]],
            "variants": variants[:10],
            "never_use": sorted(never),
            "class": klass,
            "class_signals": biz if klass == "business" else (["palavra técnica: " + ", ".join(tech)]
                                                              if tech else ["sem sinal de domínio"]),
            "tested_in": sorted(test_mentions.get(canon, ()))[:10],
            "top_files": [f for f, _ in sorted(files.items(), key=lambda kv: (-kv[1], kv[0]))[:5]],
            "_scope_files": sorted(files),
        })
    out.sort(key=lambda t: (-t["count"], t["term"]))
    facts = []
    for t in out:
        if len(facts) >= 200:
            break
        if t["count"] < 2 and not any(d["kind"] in ("doc", "table") for d in t["defined_at"]):
            continue
        d0 = t["defined_at"][0]
        claim = "Termo '%s' (%s): canônico %s, %d ocorrências em %d arquivos; definido em %s:%d (%s)" % (
            t["term"], t["class"], t["canonical"], t["count"], t["files"], d0["file"], d0["line"], d0["kind"])
        others = [d for d in t["defined_at"][1:] if (d["file"], d["line"]) != (d0["file"], d0["line"])]
        if t["merged_forms"] and others:
            claim += "; forma(s) relacionada(s) %s também definida(s) em %s" % (
                ", ".join(t["merged_forms"][:3]),
                ", ".join("%s:%d (%s)" % (d["file"], d["line"], d["kind"]) for d in others[:2]))
        if t["definition"]:
            claim += "; definição: %s" % t["definition"][:160]
        if t["synonyms"]:
            claim += "; sinônimos: %s" % ", ".join(t["synonyms"])
        if t["never_use"]:
            claim += "; nunca usar: %s" % ", ".join(t["never_use"])
        ev = [ev_file(d["file"], d["line"]) for d in t["defined_at"][:3]]
        ev += [ev_file(s["file"], s["line"]) for s in t["synonym_evidence"][:2]]
        ev.append(ev_cmd("scan:L9 contagem de '%s' (partes do identificador) em código+docs" % t["term"], 0,
                         dumps({"count": t["count"], "variants": t["variants"]}).encode("utf-8")))
        facts.append(fb.fact("gloss.%s" % slug(t["term"]), GLOSSARY, claim, ev,
                             confidence="high" if t["count"] >= 5 else "medium",
                             scope=_scope(t["_scope_files"][:200]) or ["**"],
                             data={"term": t["term"], "canonical": t["canonical"], "category": t["class"],
                                   "synonyms": t["synonyms"], "never_use": t["never_use"],
                                   "definition": t["definition"] or "", "count": t["count"],
                                   "variants": [v["form"] for v in t["variants"]]}))
    for t in out:
        t.pop("_scope_files", None)
    if not facts:
        facts.append(fb.fact("gloss.none", GLOSSARY, "Nenhum termo de domínio definido (tipos, tabelas, "
                             "rotas, glossário em docs) com ≥2 ocorrências",
                             [ev_cmd("scan:L9 extração de termos", 1, b"")], scope=["**"]))
    return {"layer": GLOSSARY, "terms": out, "enums": [{"name": n, "file": f, "line": ln, "lang": lg}
                                                       for n, f, ln, lg in sorted(enums, key=lambda e: (e[1], e[2]))],
            "facts": facts}, enums


COV_LEVEL_CONF = {"message": None, "exception": None, "reference": None, "asserted": "medium",
                  "exercised": "medium",
                  "undetermined": "medium", "none": "medium"}


def _cov_text(r):
    cov = r.get("covered_by") or {}
    lv = cov.get("level")
    if lv == "self":
        return ""
    if lv == "message":
        return "; coberto por %s:%d (o teste confere a mensagem)" % (cov["file"], cov["line"])
    if lv == "exception":
        if not cov.get("via"):
            return "; coberto por %s:%d (o teste espera %s, levantada só neste ponto do repo)" % (
                cov["file"], cov["line"], cov["match"])
        return "; coberto por %s:%d (o teste chama `%s` e espera %s)" % (cov["file"], cov["line"],
                                                                         cov["via"], cov["match"])
    if lv == "reference":
        return "; citado em teste %s:%d (`%s`)" % (cov["file"], cov["line"], cov["match"])
    if lv == "asserted":
        return "; coberto por %s:%d (o teste chama `%s` e confere o resultado — valor ou exceção " \
               "esperados, derivados da regra)" % (cov["file"], cov["line"], cov["via"] or cov["match"])
    if lv == "exercised":
        if cov.get("ambiguous"):
            return "; alcançável por teste: %s:%d chama `%s` — ambíguo: espera a exceção que %d regras " \
                   "levantam (qual delas o teste prova não é determinável mecanicamente)" % (
                       cov["file"], cov["line"], cov["via"], cov["ambiguous"])
        return "; alcançável por teste: %s:%d chama `%s` (se o teste isola esta regra não é determinável " \
               "mecanicamente — confira antes de afirmar)" % (cov["file"], cov["line"], cov["via"])
    if lv == "undetermined":
        return "; cobertura por teste não determinável mecanicamente (alcançada por operador/dunder)"
    if r["lang"] == "sql":
        return "; nenhum teste cita `%s` (SQL não é importável; cobertura indireta não verificada)" % (
            r.get("name") or "a regra")
    if cov.get("module_imported_by"):
        # só o CORPO dos casos de teste é rastreado: setUp/helpers podem chamar o símbolo sem disparar a regra
        return "; nenhum caso de teste alcança esta regra mecanicamente (o módulo é importado por %s, mas " \
               "nenhum caso confere a mensagem nem chama o símbolo no corpo do teste; chamadas via " \
               "setUp/helpers não são rastreadas)" % ", ".join(cov["module_imported_by"])
    return "; nenhum teste importa este módulo nem cita a mensagem (cobertura indireta — CLI/HTTP/" \
           "subprocess — não verificada)"


def build_rules(ctx, enums, test_units):
    fb = ctx.fb
    code = [f for f in ctx.files if (paths.is_code(f) or paths.lang_of(f) == "sql")
            and not paths.is_test_file(f)]
    errors = rules_extract.custom_errors(ctx, code)
    rules = []
    for rel in code:
        rules.extend(rules_extract.extract(ctx, rel, errors))
    have_state = set((r["file"], r["name"]) for r in rules if r["kind"] == "state")
    rules.extend(r for r in rules_extract.enum_states(ctx, enums) if (r["file"], r["name"]) not in have_state)
    for r in rules:
        if r["kind"] == "state" and r["lang"] != "sql":
            r["members"] = list(r["states"])
    names = set(r["name"] for r in rules if r.get("name"))
    names.update(m for r in rules for m in r.get("members", []))
    idx = coverage.CoverageIndex(ctx, [u["file"] for u in test_units], names)
    idx.set_validations(rules)
    for r in rules:
        if r.get("exc"):
            idx.exc_sites[r["exc"]] = idx.exc_sites.get(r["exc"], 0) + 1
    for r in rules:
        r["covered_by"] = idx.cover(r)
    coverage.disambiguate(rules)
    for r in rules:
        r["covered_by"].pop("block", None)
        r["covered_by"].pop("ref_line", None)
    tests = {u["file"]: ctx.text(u["file"]) for u in test_units}
    for u in test_units:
        text = tests.get(u["file"], "")
        for name in u.get("test_names", []):
            ps = split_identifier(name)
            if not set(ps) & TEST_RULE_WORDS:
                continue
            i = text.find(name)
            ln = _line(text, i) if i >= 0 else 1
            sentence = " ".join(p for p in ps if p != "test")
            rules.append({"kind": "test", "file": u["file"], "line": ln, "lang": u["lang"],
                          "name": name, "rule": sentence,
                          "covered_by": {"file": u["file"], "line": ln, "match": name, "level": "self"}})
    rules.sort(key=lambda r: (r["kind"], r["file"], r["line"], r.get("name") or r.get("message", "")))

    facts = []
    per_kind_cap = {"validation": 150, "limit": 80, "format": 40, "transition": 40, "state": 40,
                    "constraint": 60, "test": 120}
    used = {}
    for r in rules:
        used[r["kind"]] = used.get(r["kind"], 0) + 1
        if used[r["kind"]] > per_kind_cap[r["kind"]]:
            continue
        cov = r.get("covered_by") or {}
        lv = cov.get("level")
        cov_txt = _cov_text(r)
        conf = "high"
        if r["kind"] == "validation":
            gl = r.get("guard_line")
            if r["guard"] and gl and gl != r["line"]:
                # guarda e raise em linhas diferentes: cita cada um na SUA linha
                where = "%s:%d-%d" % (r["file"], gl, r["line"])
                cond = "quando `%s` (linha %d) " % (r["guard"], gl)
                tail = " (linha %d)" % r["line"]
            else:
                where = "%s:%d" % (r["file"], r["line"])
                cond = ("quando `%s` " % r["guard"]) if r["guard"] else ""
                tail = ""
            claim = "Regra (validação) em %s: %s→ %s%s%s%s" % (
                where, cond, r["raises"], ("(\"%s\")" % r["message"][:160]) if r["message"] else "", tail,
                cov_txt)
            fid = "brule.validation.%s.%d" % (slug(r["file"], 60), r["line"])
        elif r["kind"] == "limit":
            if r["value"] is None:
                shown = "`%s` (valor não literal; não avaliado)" % r["expr"]
                conf = "low"
            elif r["expr"].replace("_", "") != r["value"]:
                shown = "%s (`%s`)" % (r["value"], r["expr"])
            else:
                shown = r["value"]
            claim = "Limite %s = %s (%s) em %s:%d%s" % (r["name"], shown, r["class"], r["file"],
                                                        r["line"], cov_txt)
            fid = "brule.limit.%s" % slug(r["name"])
        elif r["kind"] == "format":
            claim = "Formato %s = %s em %s:%d%s" % (r["name"], r["value"][:120], r["file"], r["line"], cov_txt)
            fid = "brule.format.%s" % slug(r["name"])
        elif r["kind"] == "transition":
            claim = "Transições permitidas %s em %s:%d: %s%s" % (
                r["name"], r["file"], r["line"],
                ", ".join("%s→%s" % tuple(p) for p in r["transitions"][:20]), cov_txt)
            fid = "brule.transitions.%s" % slug(r["name"])
        elif r["kind"] == "state":
            claim = "Estados de %s (%s:%d): %s%s" % (r["name"], r["file"], r["line"],
                                                     ", ".join(r["states"][:30]), cov_txt)
            fid = "brule.states.%s" % slug(r["name"])
        elif r["kind"] == "constraint":
            claim = "Restrição CHECK %s em %s:%d: %s%s" % (r["name"], r["file"], r["line"], r["expr"], cov_txt)
            fid = "brule.constraint.%s" % slug(r["name"])
        else:
            claim = "Regra expressa em teste %s (%s:%d): %s" % (r["name"], r["file"], r["line"], r["rule"])
            fid = "brule.test.%s" % slug(r["name"], 70)
        if lv in COV_LEVEL_CONF and COV_LEVEL_CONF[lv] and conf == "high":
            conf = COV_LEVEL_CONF[lv]
        if lv == "none" and not cov.get("module_imported_by"):
            conf = "low"
        if r["kind"] == "format" and conf == "high":
            conf = "medium"  # padrão nomeado: regra de negócio provável, não certa
        ev = [ev_file(r["file"], r["line"])]
        if r["kind"] == "validation" and r.get("guard") and r.get("guard_line") not in (None, r["line"]):
            ev.append(ev_file(r["file"], r["guard_line"]))
        if cov.get("file") and cov["file"] != r["file"]:
            ev.append(ev_file(cov["file"], cov["line"]))
        subject = r.get("name") or r.get("message") or r.get("rule") or r.get("raises")
        value = {"limit": r.get("value"), "state": r.get("states"), "transition": r.get("transitions"),
                 "validation": r.get("guard"), "test": r.get("rule"), "format": r.get("value"),
                 "constraint": r.get("expr")}.get(r["kind"])
        strong = lv in coverage.STRONG or lv == "self"
        r.pop("members", None)
        data = {"subject": subject, "kind": r["kind"], "value": value,
                "test": ("%s:%d" % (cov["file"], cov["line"])) if strong else None,
                "coverage": lv if lv != "self" else "self",
                "source": "code", "class": r.get("class", "business")}
        if lv == "exercised":
            data["exercised_by"] = "%s:%d" % (cov["file"], cov["line"])
        if r["kind"] == "limit":
            data["expr"] = r["expr"]
        if r["kind"] == "validation":
            data["exception"] = r.get("exc")
        facts.append(fb.fact(fid, RULES, claim, ev, confidence=conf,
                             scope=sorted(set([r["file"]] + ([cov["file"]] if cov.get("file") else []))),
                             data=data))
    if not facts:
        facts.append(fb.fact("brule.none", RULES, "Nenhuma regra de negócio mecânica detectada "
                             "(validações, limites nomeados, formatos, estados/transições, CHECK de SQL, "
                             "testes com nome de regra) — regras precisam vir da entrevista",
                             [ev_cmd("scan:L9 extração de regras", 1, b"")], scope=["**"]))
    summary = {}
    for r in rules:
        summary[r["kind"]] = summary.get(r["kind"], 0) + 1
    coverage_summary = {}
    for r in rules:
        lv = (r.get("covered_by") or {}).get("level")
        if r["kind"] != "test":
            coverage_summary[lv] = coverage_summary.get(lv, 0) + 1
    return {"layer": RULES, "rules": rules, "summary": summary, "coverage": coverage_summary,
            "facts": facts}


def run(ctx):
    adrs = [l6_rationale.parse_adr(ctx, f) for f in ctx.files if l6_rationale.is_adr(f)]
    units = ctx.layer("L4")["test_units"]
    glossary, enums = build_glossary(ctx, adrs, units)
    rules = build_rules(ctx, enums, units)
    return {"_outputs": {GLOSSARY: glossary, RULES: rules}}
