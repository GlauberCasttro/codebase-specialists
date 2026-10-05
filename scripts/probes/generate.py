"""cs.py probes generate — banco de sondas a partir dos FATOS (nunca de LLM), com semente determinística.

Por agente: ~20 sondas, ~60% do território (12) e ~40% cross-território (8), ≥2 negativas.
Tipos: location, existence, command, prohibition, dependency, history, why, term, business_rule.
Gabarito vem do grafo/scan/operations/rules/history/rationale/glossary/business_rules; negativas são
verificadas contra o repo (grep de palavra inteira) antes de entrar no banco.
"""
import random
import re

from team._shared_tmp.common import (CsError, expand, norm_cmd, read_json, read_lines, sp_path,
                                     write_json)
from team._shared_tmp.factsio import Facts, fact_files

TOTAL, HOME, MIN_NEG = 20, 12, 2
TYPE_ORDER = ["location", "dependency", "command", "prohibition", "history", "why", "term",
              "business_rule", "existence"]
FAB_SUFFIX = ["Reconciler", "Registry", "Dispatcher", "Ledger", "Throttle", "Snapshot", "Gateway",
              "Escalator"]
FAB_SNAKE = ["reconcile", "rebalance", "escalate", "quarantine", "throttle", "snapshot"]
# decisoes.nao_medido: ≥HARD_MIN sondas POSITIVAS de território que o baseline sem cartão e sem repo não acerta
# por chute (negativa "NENHUM", comando `make test` e termo canônico se chutam). Território sem fatos positivos
# suficientes (ops com 12/12 "não existe" na iteração 3) completa com fatos dos arquivos que o agente LÊ e, por
# fim, do produto — a sonda leva `source: reads|product`.
HARD_MIN = 6
HARD_TYPES = ("location", "dependency", "prohibition", "history", "why", "business_rule", "existence")


def is_hard(p):
    """Sonda positiva que exige o repositório (arquivo:linha, sha, conjunto de arquivos) — não se acerta por chute."""
    a = p.get("answer") or {}
    if not a.get("exists", True):
        return False
    return p.get("type") in HARD_TYPES or (p.get("type") == "term" and a.get("variant") == "where")


KIND_PT = {"limit": "limite", "state": "estado permitido", "validation": "validação",
           "transition": "transição permitida", "constant": "valor"}


def split_ident(name):
    parts = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name).replace("_", " ").replace("-", " ").split()
    return [p.lower() for p in parts if p]


def mask(text, name):
    out = text or ""
    for tok in sorted(set([name] + [t for t in split_ident(name) if len(t) >= 3]), key=len, reverse=True):
        out = re.sub(re.escape(tok), "___", out, flags=re.I)
    return out


CODE_EXT = (".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".go", ".java", ".kt", ".cs", ".rb", ".rs",
            ".php", ".swift", ".scala", ".dart", ".vue", ".svelte", ".ex", ".exs", ".c", ".h", ".cc", ".cpp",
            ".hpp", ".sh", ".lua")
_TEST_PATH = re.compile(r"(^|/)(tests?|spec|__tests__|e2e)/|(_test|\.test|\.spec|Test|Tests)\.\w+$|(^|/)test_[^/]+$")


def is_code_file(p):
    return p.lower().endswith(CODE_EXT)


def is_test_summary(r):
    """Fato de rules que resume testes (contagem de casos/asserts), não uma regra imposta por config."""
    d = r.get("data") or {}
    kind = str(d.get("kind") or "").lower()
    if ".tests." in r["id"] or r["id"].startswith(("rules.tests", "rules.test.")) or \
            kind in ("test", "tests", "test_asserts", "asserts", "test_summary", "assert"):
        return True
    ev = [e for e in r.get("evidence") or [] if isinstance(e, dict) and e.get("file")]
    return bool(ev) and all(_TEST_PATH.search(e["file"]) and int(e.get("line") or 1) == 1 for e in ev)


class Builder(object):
    def __init__(self, target, seed, team):
        self.target = target
        self.seed = str(seed)
        self.f = Facts(target)
        self.team = team
        self.product = self.f.product_files()
        self.agents = [a for a in team.get("agents") or [] if a.get("name")]
        if not self.agents:
            raise CsError("team.json5 sem agentes", "rode `cs.py team derive` antes")
        self.owner = {}
        self.terr_files = {}
        for a in self.agents:
            fs = expand(a.get("territory") or [], self.product) if a.get("kind") != "gate" else []
            self.terr_files[a["name"]] = fs
            for p in fs:
                self.owner.setdefault(p, a["name"])
        self.globs = {a["name"]: a.get("territory") or [] for a in self.agents}
        self.edges = self.f.edges()
        self.symbols = self.f.symbols()
        self._words = None
        self.card_text = self._card_text()

    def _card_text(self):
        from team._shared_tmp.cardtext import walk_strings
        return "\n".join(s for a in self.agents for _, s in walk_strings(a.get("card") or {}))

    def words(self):
        if self._words is None:
            w = set()
            for p in self.f.all_files():
                for ln in read_lines(self.target, p) or []:
                    w.update(x.lower() for x in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", ln))
            self._words = w
        return self._words

    def label(self, files):
        owners = sorted(set(self.owner.get(p) for p in files if self.owner.get(p)))
        if len(owners) == 1 and self.globs.get(owners[0]):
            return ", ".join("`%s`" % g for g in self.globs[owners[0]])
        return "o repositório"

    # ----------------------------------------------------------- pools por conjunto de arquivos
    def pool(self, F, rng, tag):
        F = set(F)
        P = {t: [] for t in TYPE_ORDER}
        N = []  # negativas
        importers = {}
        for a, b in self.edges:
            importers.setdefault(b, set()).add(a)
        for s in self.symbols:
            if s["path"] not in F:
                continue
            desc = []
            if s["signature"]:
                desc.append("assinatura `%s`" % mask(s["signature"], s["name"]))
            if s["doc"]:
                desc.append("documentação \"%s\"" % mask(s["doc"], s["name"])[:120])
            imp = sorted(importers.get(s["path"], ()))
            if desc:
                desc = "com " + " e ".join(desc)
            elif imp:
                desc = "definido no arquivo que `%s` importa" % imp[0]
            else:
                continue
            P["location"].append(dict(
                type="location",
                question="Onde está definido o símbolo (%s) %s, em %s? Responda arquivo:linha." % (
                    s["kind"], desc, self.label([s["path"]])),
                answer={"exists": True, "path": s["path"], "line": s["line"], "symbol": s["name"]},
                atomic_facts=["symbol %s defined at %s:%d" % (s["name"], s["path"], s["line"])]
                + ([s["fact"]] if s.get("fact") else [])))
        seen_q = {}
        for it in P["location"]:
            seen_q[it["question"]] = seen_q.get(it["question"], 0) + 1
        P["location"] = [it for it in P["location"] if seen_q[it["question"]] == 1]  # pergunta ambígua não entra
        for x in sorted(F):
            if x not in self.owner or not is_code_file(x):
                continue  # "quem importa o Makefile/go.mod" não é pergunta de import
            outside = sorted(i for i in importers.get(x, ()) if self.owner.get(i) != self.owner[x])
            q = "Quais arquivos fora de %s importam `%s`? Liste todos (ou NENHUM)." % (self.label([x]), x)
            item = dict(type="dependency", question=q, answer={"exists": bool(outside), "files": outside, "subject": x},
                        atomic_facts=["%s imports %s" % (i, x) for i in outside] or ["no external importer of %s" % x])
            if outside:
                P["dependency"].append(item)
            elif importers.get(x) is not None or self.f.has_graph():
                N.append(item)
        verified = [o for o in self.f.operations() if o["status"] == "verified"]
        for o in verified:
            if norm_cmd(o["command"]) in norm_cmd(self.card_text):
                continue
            sc = o.get("scope") or []
            if sc and not expand(sc, F):
                continue
            purpose = o["purpose"] or o["kind"]
            alts = sorted(set(x["command"] for x in verified if x is not o and (x["purpose"] or x["kind"]) == purpose
                              and norm_cmd(x["command"]) != norm_cmd(o["command"])))
            ans = {"exists": True, "command": o["command"]}
            if alts:
                ans["alternatives"] = alts  # mesmo propósito, dois comandos corretos: os dois valem
            P["command"].append(dict(
                type="command",
                question="Qual comando exato (verificado, exit 0) roda %s?" % purpose,
                answer=ans, atomic_facts=[o["fact"]] if o["fact"] else []))
        for r in self.f.rules():
            files = set(fact_files(r))
            sc = r.get("scope") or []
            if not (expand(sc, F) if sc else files & F):
                continue
            d = r.get("data") or {}
            if is_test_summary(r):
                continue  # "1 arquivo de teste, 5 casos" não é regra mecânica imposta num arquivo:linha
            scope_lbl = (", ".join("`%s`" % s for s in sc[:3]) + (" (e mais %d)" % (len(sc) - 3) if len(sc) > 3 else "")) \
                or self.label(files)
            if Facts.is_negative(r) and d.get("pattern"):
                pat = d["pattern"]
                hits = [p for p in expand(sc, self.product) if any(pat in ln for ln in read_lines(self.target, p) or [])]
                if hits:
                    continue  # fato em drift: a "negativa" não é mais verdade
                N.append(dict(type="existence",
                              question="Existe alguma ocorrência de `%s` em %s? Se sim, cite; senão responda NENHUM." % (pat, scope_lbl),
                              answer={"exists": False}, atomic_facts=[r["id"]]))
                continue
            ev = [{"file": e["file"], "line": int(e.get("line") or 1)} for e in r.get("evidence") or []
                  if isinstance(e, dict) and e.get("file")]
            if not ev:
                continue
            ev = [self.rule_line(e, d) for e in ev]
            P["prohibition"].append(dict(
                type="prohibition",
                question="Que regra mecânica%s vale para %s e em que arquivo:linha ela é imposta?" % (
                    (" (ferramenta: %s)" % d["tool"]) if d.get("tool") else "", scope_lbl),
                answer={"exists": True, "enforced_at": ev, "fact": r["id"],
                        "file_level": all(e.get("file_level") for e in ev)}, atomic_facts=[r["id"]]))
        for c in self.f.fix_commits():
            if not set(c["files"]) & F:
                continue
            P["history"].append(dict(
                type="history",
                question="Qual commit (sha) corrigiu \"%s\" (tocou %d arquivo(s))?" % (c["subject"], len(c["files"])),
                answer={"exists": True, "sha": c["sha"]}, atomic_facts=[c["fact"] or c["sha"]]))
        seen_adr = set()
        for r in sorted(self.f.rationale(), key=lambda r: r["fact"]):
            # ADR com fatos por decisão (rat.adr.<adr>.dN): UMA sonda POR-QUÊ por documento (sem redundância)
            adr_key = tuple(sorted(set(s["file"] for s in r["sources"]))) or (r["fact"],)
            if adr_key in seen_adr:
                continue
            fx = self.f.by_id.get(r["fact"]) or {}
            sc = fx.get("scope") or []
            if not (set(s["file"] for s in r["sources"]) & F or (sc and expand(sc, F))):
                continue
            seen_adr.add(adr_key)
            P["why"].append(dict(
                type="why", question="Por que %s? Cite a fonte (arquivo:linha)." % r["topic"],
                answer={"exists": True, "key_terms": r["key_terms"], "sources": r["sources"]},
                atomic_facts=[r["fact"]], panel=True))
        for g in self.f.glossary():
            g = dict(g, defined_at=self.term_definition(g))
            gf = set([g["defined_at"]["file"]]) if g["defined_at"] else set()
            if not (gf & F or (g["scope"] and expand(g["scope"], F))):
                continue
            variants = []
            if g["defined_at"]:
                variants.append(dict(
                    type="term", question="Onde é definido o termo %s %s? Responda arquivo:linha." % (
                        "de negócio" if g["category"] == "business" else "técnico",
                        ("que significa \"%s\"" % mask(g["definition"], g["term"])) if g["definition"]
                        else "`%s`" % g["term"]),
                    answer={"exists": True, "variant": "where", "path": g["defined_at"]["file"],
                            "line": g["defined_at"]["line"], "term": g["term"]}, atomic_facts=[g["fact"]]))
            for syn in g["synonyms"]:
                variants.append(dict(
                    type="term", question="Neste repo, qual é o termo canônico para \"%s\"?" % syn,
                    answer={"exists": True, "variant": "canonical", "canonical": g["term"]}, atomic_facts=[g["fact"]]))
            if g["never_use"]:
                variants.append(dict(
                    type="term", question="Qual variante do termo `%s` nunca deve ser usada?" % g["term"],
                    answer={"exists": True, "variant": "never_use", "never_use": g["never_use"]},
                    atomic_facts=[g["fact"]]))
            P["term"] += variants
        for b in self.f.business_rules():
            bf = set(s["file"] for s in b["sources"])
            if not (bf & F or (b["scope"] and expand(b["scope"], F))):
                continue
            P["business_rule"].append(dict(
                type="business_rule",
                question="Qual o %s de \"%s\" e onde é imposto (arquivo:linha)?" % (
                    KIND_PT.get(b["kind"], b["kind"]), b["subject"]),
                answer={"exists": True, "value": b["value"], "sources": b["sources"]}, atomic_facts=[b["fact"]]))
        # existência positiva / negativa entre territórios (grafo)
        if self.f.has_graph():
            src_owners = sorted(set(self.owner[p] for p in F if p in self.owner))
            for oa in src_owners:
                for ob in sorted(self.terr_files):
                    if ob == oa or not self.terr_files[ob] or not self.globs.get(oa):
                        continue
                    hits = sorted(set(a for a, b in self.edges if self.owner.get(a) == oa and self.owner.get(b) == ob))
                    q = "Algum arquivo em %s importa diretamente de %s? Se sim, cite os arquivos; senão NENHUM." % (
                        ", ".join("`%s`" % g for g in self.globs[oa]), ", ".join("`%s`" % g for g in self.globs[ob]))
                    item = dict(type="existence", question=q, answer={"exists": bool(hits), "files": hits},
                                atomic_facts=["edge %s->%s" % (oa, ob)])
                    (P["existence"] if hits else N).append(item)
        # negativas fabricadas (sempre possíveis): símbolo, termo, regra de negócio
        toks = sorted(set(t for s in self.symbols if s["path"] in F for t in split_ident(s["name"]) if len(t) >= 3))
        if not toks:
            toks = sorted(set(t for p in F for t in split_ident(re.sub(r"\.\w+$", "", p.rsplit("/", 1)[-1])) if len(t) >= 3))
        toks = toks or ["core"]
        for i in range(6):
            name = self._fabricate(rng, toks, camel=(i % 2 == 0))
            if not name:
                continue
            lbl = self.label(F)
            kind = i % 3
            if kind == 0:
                N.append(dict(type="location",
                              question="Onde está definido o símbolo `%s` em %s? Responda arquivo:linha ou NENHUM." % (name, lbl),
                              answer={"exists": False}, atomic_facts=["absent symbol %s" % name]))
            elif kind == 1:
                N.append(dict(type="term",
                              question="Neste repo, qual é o termo canônico para \"%s\"? Se não existir, NENHUM." % " ".join(split_ident(name)),
                              answer={"exists": False}, atomic_facts=["absent term %s" % name]))
            else:
                N.append(dict(type="business_rule",
                              question="Qual o limite de \"%s\" e onde é imposto (arquivo:linha)? Se não houver, NENHUM." % " ".join(split_ident(name)),
                              answer={"exists": False}, atomic_facts=["absent rule %s" % name]))
        return P, N

    def rule_line(self, e, d):
        """Gabarito de regra de config aponta a LINHA da regra, não o cabeçalho: evidência na linha 1 é procurada
        no arquivo pelo nome da regra/padrão; não achou → imposição no nível do arquivo (`file_level`)."""
        if int(e.get("line") or 1) > 1:
            return e
        ls = read_lines(self.target, e["file"]) or []
        if len(ls) <= 1:
            return e
        keys = [str(d.get(k)) for k in ("rule", "name", "pattern", "key", "setting") if d.get(k)]
        for k in keys:
            hits = [i + 1 for i, ln in enumerate(ls) if k in ln]
            if hits:
                return {"file": e["file"], "line": hits[0]}
        return {"file": e["file"], "line": 1, "file_level": True}

    def term_definition(self, g):
        """Local de definição do termo conferido contra o código: a linha citada pelo glossário tem de conter o
        termo; senão vale a definição de símbolo com o MESMO nome (iteração 1: `Deliveries` apontava para
        `type Delivery struct`); sem confirmação, não há sonda de localização para o termo."""
        term = g["term"]
        at = g["defined_at"]
        if at:
            ls = read_lines(self.target, at["file"]) or []
            ln = at["line"]
            win = ls[max(0, ln - 1):ln]
            if any(re.search(r"(?<![\w])%s(?![\w])" % re.escape(term), x) for x in win):
                return at
        defs = sorted(set((s["path"], s["line"]) for s in self.symbols if s["name"] == term))
        if at:
            same = [d for d in defs if d[0] == at["file"]]
            defs = same or defs
        if len(set(p for p, _ in defs)) == 1:
            return {"file": defs[0][0], "line": defs[0][1]}
        return None

    def _fabricate(self, rng, toks, camel=True):
        w = self.words()
        for _ in range(50):
            a = rng.choice(toks)
            if camel:
                name = a.capitalize() + rng.choice(FAB_SUFFIX)
            else:
                name = rng.choice(FAB_SNAKE) + "_" + a + "_" + rng.choice(["window", "quota", "ledger", "batch"])
            parts = split_ident(name)
            if name.lower() not in w and "".join(parts) not in w and "_".join(parts) not in w:
                return name
        return None

    # ----------------------------------------------------------- seleção
    def pick(self, P, N, n, nneg, rng, used, min_hard=0):
        out = []
        negs = [x for x in N if x["question"] not in used]
        rng.shuffle(negs)
        for x in negs[:nneg]:
            out.append(x)
            used.add(x["question"])
        pools = {t: [x for x in P[t] if x["question"] not in used] for t in TYPE_ORDER}
        for t in TYPE_ORDER:
            rng.shuffle(pools[t])
        hard = 0
        while hard < min_hard and len(out) < n:  # primeiro as positivas difíceis (round-robin por tipo)
            took = False
            for t in TYPE_ORDER:
                if hard >= min_hard or len(out) >= n:
                    break
                cand = [x for x in pools[t] if is_hard(x) and x["question"] not in used]
                if cand:
                    x = cand[-1]
                    pools[t].remove(x)
                    out.append(x)
                    used.add(x["question"])
                    hard += 1
                    took = True
            if not took:
                break
        while len(out) < n and any(pools.values()):
            for t in TYPE_ORDER:
                if len(out) >= n:
                    break
                if pools[t]:
                    x = pools[t].pop()
                    if x["question"] in used:
                        continue
                    out.append(x)
                    used.add(x["question"])
        rest = [x for x in negs[nneg:] if x["question"] not in used]
        while len(out) < n and rest:
            x = rest.pop(0)
            out.append(x)
            used.add(x["question"])
        return out

    def build_agent(self, a, rng, used=None, id_prefix=None):
        """Sondas de UM agente. `used` = perguntas já usadas (rotação: sondas NOVAS); ids P-<agente>[-rN]-NN."""
        name = a["name"]
        home = self.terr_files[name] or list(self.product)
        others = sorted(p for p in self.product if self.owner.get(p) not in (None, name)) or list(self.product)
        Ph, Nh = self.pool(home, rng, "home")
        Pc, Nc = self.pool(others, rng, "cross")
        used = set(used or ())
        self._complete_hard(a, Ph, home, rng, used)
        hs = self.pick(Ph, Nh, HOME, MIN_NEG, rng, used, min_hard=HARD_MIN)
        cs = self.pick(Pc, Nc, TOTAL - HOME, 1, rng, used)
        negs = sum(1 for x in hs + cs if not x["answer"].get("exists", True))
        items = [(x, "territory") for x in hs] + [(x, "cross") for x in cs]
        probes = []
        for i, (x, scope) in enumerate(items):
            p = {"id": "%s-%02d" % (id_prefix or ("P-%s" % name), i + 1), "agent": name, "type": x["type"],
                 "scope": scope, "question": x["question"], "answer": x["answer"],
                 "atomic_facts": x["atomic_facts"], "negative": not x["answer"].get("exists", True),
                 "must_cite_evidence": True, "discriminative": None}
            if x.get("panel"):
                p["panel"] = True
            if x.get("source"):
                p["source"] = x["source"]
            if x["type"] == "why" and x["answer"].get("sources"):
                src = x["answer"]["sources"][0]
                p["answer"]["source"] = "%s:%s" % (src["file"], src.get("line") or 1)
                p["gabarito_fonte"] = "%s — %s" % (p["answer"]["source"], x["answer"].get("claim") or
                                                   (self.f.by_id.get((x["atomic_facts"] or [""])[0]) or {}).get("claim", ""))
            probes.append(p)
        meta = {"territory": len(hs), "cross": len(cs), "negatives": negs,
                "warnings": ([] if negs >= MIN_NEG else ["menos de %d negativas" % MIN_NEG])
                + ([] if len(hs) + len(cs) >= TOTAL else ["banco curto: %d sondas" % (len(hs) + len(cs))])}
        return probes, meta

    def _complete_hard(self, a, Ph, home, rng, used):
        """Território com < HARD_MIN positivas difíceis ainda não usadas: completa com as dos arquivos que o agente
        lê (`reads`) e, se faltar, do produto inteiro (sonda marcada `source`)."""
        def count():
            return sum(1 for t in TYPE_ORDER for x in Ph[t] if is_hard(x) and x["question"] not in used)
        if count() >= HARD_MIN:
            return
        seen = set(x["question"] for t in TYPE_ORDER for x in Ph[t])
        reads = expand(a.get("reads") or [], self.product)
        for label, files in (("reads", reads), ("product", list(self.product))):
            extra = sorted(set(files) - set(home))
            if not extra:
                continue
            P2, _ = self.pool(extra, random.Random("%s:%s:%s" % (self.seed, a["name"], label)), label)
            for t in TYPE_ORDER:
                for x in P2[t]:
                    if is_hard(x) and x["question"] not in seen:
                        seen.add(x["question"])
                        Ph[t].append(dict(x, source=label))
            if count() >= HARD_MIN:
                return

    def build(self):
        probes = []
        meta = {}
        for a in sorted(self.agents, key=lambda x: x["name"]):
            rng = random.Random("%s:%s" % (self.seed, a["name"]))
            ps, m = self.build_agent(a, rng)
            probes += ps
            meta[a["name"]] = m
        return {"schema_version": 1, "seed": self.seed, "generator": "facts-only", "agents": meta,
                "probes": probes, "baseline": {}}


def probe_sha(p):
    """Identidade de uma sonda (pergunta + gabarito): veredito de juiz e ciclo valem só para ESTA sonda."""
    import hashlib
    import json
    return hashlib.sha256(json.dumps({"q": p.get("question"), "a": p.get("answer")}, sort_keys=True,
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def rotate(target, agent, seed=None):
    """`probes generate --rotate --agent <a>`: troca SÓ as sondas de <a> por sondas NOVAS (nunca perguntas de
    bancos anteriores dele), com ids `P-<a>-r<N>-NN`; os outros agentes ficam intactos (sondas, baseline,
    respostas e ciclos). O baseline de <a> é descartado (sondas novas → baseline novo) e os vereditos de juiz
    das sondas antigas dele saem do painel (id repetido nunca herda veredito)."""
    import os
    from cslib import log as cslog
    bank = load_bank(target)
    team = read_json(sp_path(target, "team.json5"), "team.json5")
    ag = [a for a in team.get("agents") or [] if a.get("name") == agent]
    if not ag:
        raise CsError("agente inexistente no team.json5: %s" % agent)
    old = [p for p in bank["probes"] if p["agent"] == agent]
    if not old:
        raise CsError("%s sem sondas no banco atual" % agent, "rode `cs.py probes generate` (banco completo) antes")
    rot = bank.setdefault("rotations", {}).setdefault(agent, [])
    n = len(rot) + 1
    seed = seed or "%s-r%d" % (bank.get("seed") or "cs-probes-v1", n)
    retired = bank.setdefault("retired_questions", {}).setdefault(agent, [])
    used = set(retired) | set(p["question"] for p in old)
    b = Builder(target, seed, team)
    probes, meta = b.build_agent(ag[0], random.Random("%s:%s" % (seed, agent)), used=used,
                                 id_prefix="P-%s-r%d" % (agent, n))
    if not probes:
        # sem ciclo de refino possível: registrado para `probes check --allow-non-specialist` aceitar o agente
        bank.setdefault("rotation_exhausted", {})[agent] = "rotação %d: todas as perguntas já usadas" % n
        write_json(target, sp_path(target, "probes", "bank.json5"), bank)
        raise CsError("%s: nenhuma sonda nova possível (todas as perguntas já usadas)" % agent,
                      "registre o agente como nao-especialista ou amplie os fatos do território")
    retired[:] = sorted(used)
    keep = [p for p in bank["probes"] if p["agent"] != agent]
    bank["probes"] = sorted(keep + probes, key=lambda p: (p["agent"], p["id"]))
    bank.setdefault("agents", {})[agent] = meta
    (bank.get("baseline") or {}).pop(agent, None)
    rot.append({"n": n, "seed": seed, "at": cslog.now_iso(), "retired": len(old), "new": len(probes)})
    mark_issued(target, [agent])
    write_json(target, sp_path(target, "probes", "bank.json5"), bank)
    pp = sp_path(target, "probes", "panel", "%s.json5" % agent)
    if os.path.isfile(pp):
        panel = read_json(pp, "painel")
        old_ids = set(p["id"] for p in old)
        write_json(target, pp, {k: v for k, v in panel.items() if k not in old_ids})
    return bank, probes, meta


def issued_path(target):
    return sp_path(target, "probes", "issued.json5")


def mark_issued(target, agents):
    """Quando as sondas de cada agente foram (re)emitidas — fora do bank.json5 (que é determinístico em bytes);
    resposta gravada ANTES disso é de outro banco."""
    import os
    import time
    p = issued_path(target)
    cur = read_json(p, "issued.json5") if os.path.isfile(p) else {}
    now = round(time.time(), 3)
    for a in agents:
        cur[a] = now
    write_json(target, p, cur, "issued.json5 — quando as sondas de cada agente foram emitidas (cs.py probes generate)")


def load_issued(target):
    import os
    p = issued_path(target)
    return read_json(p, "issued.json5") if os.path.isfile(p) else {}


def generate(target, seed="cs-probes-v1"):
    team = read_json(sp_path(target, "team.json5"), "team.json5")
    bank = Builder(target, seed, team).build()
    write_json(target, sp_path(target, "probes", "bank.json5"), bank)
    mark_issued(target, sorted(bank["agents"]))
    return bank


def load_bank(target):
    return read_json(sp_path(target, "probes", "bank.json5"), "probes/bank.json5")
