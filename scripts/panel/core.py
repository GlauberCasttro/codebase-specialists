"""Mesa redonda estruturada (etapa round-table-deep-specialize): crítica independente + checagem mecânica.

Arquivos (todos em <alvo>/.swarm/panel/):
  plan.json5                    {schema_version, roster_sha256, deps_sha256, agents: {<autor>: {reviewers: [
                                  {name, role: adjacent|fallback|skeptic, weight, territory[]}]}}}
  reviews/<autor>/<revisor>.json5   objeções do revisor, schema REVIEW_KEYS
  <autor>.json5                 consolidado: {agent, verdict (veredito_enum), confirmed{3 listas}, rejected[],
                                  core_candidates[], inputs{plan_sha256, reviews_sha256}, at}
  core-candidates.json5         regras cross-cutting apontadas por ≥2 revisores de territórios diferentes
O painel de MÉRITO das sondas POR-QUÊ (lido por `probes check`) é outro arquivo:
  <alvo>/.swarm/probes/panel/<agente>.json5 = {<id da sonda>: "PASS"|"FAIL"} (comando `panel why`).

Revisores: 2 adjacentes pelo knowledge/deps.json5 (maior nº de arestas nos dois sentidos; empate por nome;
sem vizinho suficiente → `fallback` determinístico) + 1 cético externo (`cetico`, de preferência outro modelo).
Confirmação (só objeção confirmada vai para o autor):
  afirmacoes_sem_evidencia   {afirmacao, ref?}: `ref` reprovado por `probes existence` (mesma função), ou
                             afirmação casa um item do cartão sem facts[] / com fato inexistente.
  conflitos_com_meu_territorio {path, descricao}: path casa ≥1 arquivo do território do revisor E o autor
                             escreve/cita esse caminho (território ou texto do cartão).
  regras_cross_cutting_faltando {regra, facts[≥1]}: todos os fatos existem.
"""
import os
import re

from cslib import CsError
from cslib.paths import STATE_DIR
from facts import store

REVIEW_KEYS = ("afirmacoes_sem_evidencia", "conflitos_com_meu_territorio", "regras_cross_cutting_faltando")
ITEM_SCHEMA = {
    "afirmacoes_sem_evidencia": ({"afirmacao"}, {"ref", "campo", "trecho", "motivo", "evidencia"}),
    "conflitos_com_meu_territorio": ({"path", "descricao"}, {"trecho", "minha_regra", "evidencia"}),
    "regras_cross_cutting_faltando": ({"regra", "facts"}, {"escopo"}),
}
LIST_FIELDS = {"evidencia", "escopo", "facts"}
PROMPT_TOP = {"revisor", "revisado", "papel", "modelo", "injection_attempts", "agent", "reviewer", "at"}
ROLE_ALIASES = {"cetico": "skeptic", "cético": "skeptic", "skeptic": "skeptic", "adjacente": "adjacent",
                "adjacent": "adjacent", "fallback": "adjacent"}
SKEPTIC = "cetico"
N_ADJ = 2
CARD_ITEMS = ("knows", "rules", "footguns", "refuses")


def pdir(target, *parts):
    return store.sp(target, "panel", *parts)


def load_team(target):
    team = store.read5(store.sp(target, "team.json5"), required=True)
    if not team.get("agents"):
        raise CsError("team.json5 sem agentes", "rode `cs.py team derive`")
    return team


def roster_sha(team):
    return store.sha256_obj(sorted([a.get("name"), sorted(a.get("territory") or [])] for a in team["agents"]))


def adjacency(deps):
    """{(a, b): peso} simétrico, a partir de deps.json5 (forma matrix de `team maps` ou {edges})."""
    w = {}

    def add(a, b, n):
        if a and b and a != b:
            k = tuple(sorted((a, b)))
            w[k] = w.get(k, 0) + int(n or 0)
    m = deps.get("matrix")
    if isinstance(m, dict):
        for a, row in m.items():
            for b, n in (row or {}).items():
                add(a, b, n)
    for e in ([] if isinstance(m, dict) else deps.get("edges") or []):
        if isinstance(e, dict):
            add(e.get("from") or e.get("src") or e.get("a"), e.get("to") or e.get("dst") or e.get("b"),
                e.get("count", e.get("edges", 1)))
        elif isinstance(e, list) and len(e) >= 2:
            add(e[0], e[1], e[2] if len(e) > 2 else 1)
    for p in deps.get("pairs") or []:
        if isinstance(p, dict) and "matrix" not in deps:
            add(p.get("from"), p.get("to"), p.get("edges", 1))
    return w


def plan(target):
    team = load_team(target)
    dp = store.sp(target, "knowledge", "deps.json5")
    deps = store.read5(dp, required=False, default=None)
    if deps is None:  # iteração 2: nenhum passo dizia para rodar `team maps` antes
        from team.maps import build_maps
        from team._shared_tmp.common import CsError as TeamErr
        try:
            build_maps(target)
        except TeamErr as exc:
            raise CsError("knowledge/deps.json5 ausente e `team maps` falhou: %s" % exc.message,
                          exc.hint or "rode `cs.py team maps` e veja o erro")
        deps = store.read5(dp, required=False, default=None)
        if deps is None:
            raise CsError("knowledge/deps.json5 ausente", "rode `cs.py team maps` antes de planejar o painel")
    w = adjacency(deps)
    by = {a["name"]: a for a in team["agents"]}
    names = sorted(by)
    out = {}
    load = dict((n, 0) for n in names)
    for a in names:
        # adjacentes primeiro (mais arestas); sem aresta: quem tem território e menos revisões atribuídas
        cands = sorted((n for n in names if n != a),
                       key=lambda n: (-w.get(tuple(sorted((a, n))), 0), load[n], not by[n].get("territory"), n))
        revs = []
        for n in cands[:N_ADJ]:
            wt = w.get(tuple(sorted((a, n))), 0)
            load[n] += 1
            revs.append({"name": n, "role": "adjacent" if wt > 0 else "fallback", "weight": wt,
                         "territory": sorted(by[n].get("territory") or [])})
        revs.append({"name": SKEPTIC, "role": "skeptic", "weight": 0, "territory": [],
                     "model_hint": "de preferência outro modelo/provedor"})
        out[a] = {"reviewers": revs}
    doc = {"schema_version": 1, "roster_sha256": roster_sha(team), "deps_sha256": store.sha256_file(dp),
           "agents": out}
    store.write5(target, pdir(target, "plan.json5"), doc,
                 "plan.json5 — revisores por cartão (2 adjacentes + 1 cético); gerado por cs.py panel plan")
    return doc


def load_plan(target, team=None):
    p = pdir(target, "plan.json5")
    doc = store.read5(p, required=False, default=None)
    if doc is None:
        raise CsError("panel/plan.json5 ausente", "rode `cs.py panel plan`")
    if team is not None and doc.get("roster_sha256") != roster_sha(team):
        raise CsError("roster mudou depois do plano do painel", "rode `cs.py panel plan` de novo", code=1)
    return doc


def review_path(target, agent, reviewer):
    return pdir(target, "reviews", agent, "%s.json5" % reviewer)


_EV_PATH = re.compile(r"^`?((?:[\w.@-]+/)*[\w.@-]+?)(?::\d+(?:-\d+)?)?`?$")


def _ev_path(evs):
    """1º item de `evidencia` que é arquivo (arquivo:linha → arquivo); ids de fato e comandos não contam."""
    for e in evs or []:
        e = str(e).strip().split()[0] if str(e).strip() else ""
        m = _EV_PATH.match(e)
        if m and ("/" in m.group(1) or re.search(r"\.[A-Za-z0-9]{1,8}$", m.group(1)) or
                  m.group(1) in ("Makefile", "Dockerfile")) and not re.match(r"^[a-z]+(\.[\w-]+){2,}$", m.group(1)):
            return m.group(1)
    return None


def normalize_review(obj):
    """Aceita o schema que prompts.json5 (rt.1) manda produzir e converte para o interno, preservando os campos
    originais (campo, trecho, motivo, evidencia, minha_regra, escopo, injection_attempts)."""
    if not isinstance(obj, dict):
        return obj
    out = {k: v for k, v in obj.items() if k not in REVIEW_KEYS}
    for k in REVIEW_KEYS:
        items = obj.get(k)
        if not isinstance(items, list):
            out[k] = items
            continue
        conv = []
        for it in items:
            if not isinstance(it, dict):
                conv.append(it)
                continue
            it = dict(it)
            if k == "afirmacoes_sem_evidencia" and "afirmacao" not in it and ("trecho" in it or "motivo" in it):
                it["afirmacao"] = " — ".join(x for x in (str(it.get("trecho") or "").strip(),
                                                        str(it.get("motivo") or "").strip()) if x)
                ref = _ev_path(it.get("evidencia"))
                if ref and "ref" not in it:
                    it["ref"] = ref
            if k == "conflitos_com_meu_territorio" and "descricao" not in it and ("trecho" in it or "minha_regra" in it):
                it["descricao"] = " — ".join(x for x in (str(it.get("trecho") or "").strip(),
                                                        str(it.get("minha_regra") or "").strip()) if x)
                it.setdefault("path", _ev_path(it.get("evidencia")) or str(it.get("trecho") or "").strip())
            conv.append(it)
        out[k] = conv
    return out


def validate_review(obj):
    errs = []
    if not isinstance(obj, dict):
        return ["objeções devem ser objeto {%s}" % ", ".join(REVIEW_KEYS)]
    extra = sorted(set(obj) - set(REVIEW_KEYS) - PROMPT_TOP)
    if extra:
        errs.append("chaves desconhecidas: %s" % extra)
    for k in REVIEW_KEYS:
        if k not in obj:
            errs.append("chave obrigatória ausente: %s (use [] se nada)" % k)
            continue
        if not isinstance(obj[k], list):
            errs.append("%s deve ser lista" % k)
            continue
        req, opt = ITEM_SCHEMA[k]
        for i, it in enumerate(obj[k]):
            where = "%s[%d]" % (k, i)
            if not isinstance(it, dict):
                errs.append("%s deve ser objeto com %s" % (where, sorted(req)))
                continue
            miss = sorted(req - set(it))
            if miss:
                errs.append("%s sem %s" % (where, miss))
            bad = sorted(set(it) - req - opt)
            if bad:
                errs.append("%s com chaves desconhecidas %s" % (where, bad))
            for f in req | opt:
                if f in LIST_FIELDS:
                    if f in it and f != "facts" and not (isinstance(it[f], list) and
                                                         all(isinstance(x, (str, int)) for x in it[f])):
                        errs.append("%s.%s deve ser lista" % (where, f))
                    continue
                if f in it and not (isinstance(it[f], str) and it[f].strip()):
                    errs.append("%s.%s deve ser texto não vazio" % (where, f))
            if "facts" in it and (not isinstance(it["facts"], list) or not it["facts"]
                                  or not all(isinstance(x, str) for x in it["facts"])):
                errs.append("%s.facts deve ser lista de ≥1 id de fato" % where)
    return errs


def _own_file_only(team, pl, agent, reviewer, path):
    """Iteração 3 (go-polyglot): um revisor regravou os arquivos de OUTROS revisores e o `panel record` aceitou.
    Arquivo no padrão `<agente>.<revisor>.json5` (o de `prompts.json5` rt.1) tem de ser deste par."""
    stem = os.path.basename(path)
    for ext in (".json5", ".json"):
        if stem.endswith(ext):
            stem = stem[:-len(ext)]
            break
    parts = stem.split(".")
    if len(parts) != 2:
        return
    known = set(a.get("name") for a in team.get("agents") or []) | set(
        r.get("name") for v in (pl.get("agents") or {}).values() for r in v.get("reviewers") or [])
    if parts[0] in known and parts[1] in known and (parts[0], parts[1]) != (agent, reviewer):
        raise CsError("arquivo %s é das objeções de %s sobre %s, não de %s sobre %s (um revisor não grava nem "
                      "sobrescreve as de outro)" % (os.path.basename(path), parts[1], parts[0], reviewer, agent),
                      "grave as objeções de %s em .swarm/tmp/panel/%s.%s.json5" % (reviewer, agent, reviewer))


def record(target, agent, reviewer, path, role=None):
    from team.cards import resolve_input
    team = load_team(target)
    pl = load_plan(target, team)
    if agent not in pl["agents"]:
        raise CsError("agente fora do plano: %s" % agent, "agentes: %s" % ", ".join(sorted(pl["agents"])))
    plan_revs = (pl["agents"].get(agent) or {}).get("reviewers") or []
    revs = [r["name"] for r in plan_revs]
    if reviewer not in revs:
        raise CsError("%s não é revisor de %s no plano" % (reviewer, agent), "revisores: %s" % ", ".join(revs))
    if role:
        want = ROLE_ALIASES.get(role.lower())
        got = ROLE_ALIASES.get([r["role"] for r in plan_revs if r["name"] == reviewer][0])
        if want != got:
            raise CsError("--role %s não bate com o plano (%s é %s de %s)" % (role, reviewer, got, agent))
    path = resolve_input(target, path)
    if not os.path.isfile(path):
        raise CsError("arquivo de objeções ausente: %s" % path, "caminho relativo é resolvido a partir do alvo")
    _own_file_only(team, pl, agent, reviewer, path)
    obj = normalize_review(store.read5(path))
    if isinstance(obj, dict):
        for k, want in (("revisado", agent), ("agent", agent), ("revisor", reviewer), ("reviewer", reviewer)):
            if obj.get(k) and obj[k] != want:
                raise CsError("objeções dizem %s=%s, mas o registro é de %s (um revisor não grava nem sobrescreve "
                              "as objeções de outro)" % (k, obj[k], want),
                              "confira --card/--reviewer (ou o JSON devolvido pelo subagente); se o arquivo foi "
                              "regravado por outro revisor, peça ao dono que o grave de novo")
    errs = validate_review(obj)
    if errs:
        raise CsError("objeções inválidas:\n  - " + "\n  - ".join(errs),
                      "schema: {afirmacoes_sem_evidencia: [{afirmacao, ref?}], conflitos_com_meu_territorio: "
                      "[{path, descricao}], regras_cross_cutting_faltando: [{regra, facts: [ids]}]}")
    doc = {k: obj[k] for k in REVIEW_KEYS}
    doc.update({"agent": agent, "reviewer": reviewer, "at": store.now(),
                "card_sha256": _drafted_sha(target, agent)})
    for k in ("papel", "modelo", "injection_attempts"):
        if obj.get(k) not in (None, "", []):
            doc[k] = obj[k]
    store.write5(target, review_path(target, agent, reviewer), doc,
                 "objeções de %s ao cartão de %s — gravado por cs.py panel record" % (reviewer, agent))
    return doc


def _drafted_sha(target, agent):
    """sha do rascunho registrado (`team card set`); revisão do autor (rt.4) não muda isto."""
    st = store.read5(store.sp(target, "cards", "status.json5"), required=False, default=None) or {}
    return ((st.get(agent) or {}).get("drafted") or {}).get("sha256")


def review_status(target):
    """→ (faltas[], plano)."""
    team = load_team(target)
    pl = load_plan(target, team)
    missing = []
    for a in sorted(pl["agents"]):
        if a not in set(x["name"] for x in team["agents"]):
            missing.append("%s está no plano mas não no roster" % a)
        for r in pl["agents"][a]["reviewers"]:
            p = review_path(target, a, r["name"])
            if not os.path.isfile(p):
                missing.append("%s ← %s (%s)" % (a, r["name"], r["role"]))
                continue
            doc = store.read5(p)
            errs = validate_review({k: doc[k] for k in REVIEW_KEYS if k in doc})
            if errs:
                missing.append("%s ← %s inválido: %s" % (a, r["name"], errs[0]))
            elif doc.get("card_sha256") and doc["card_sha256"] != _drafted_sha(target, a):
                missing.append("%s ← %s revisou um rascunho ANTERIOR (cartão regravado por `team card set` "
                               "depois da revisão): revise de novo" % (a, r["name"]))
    for a in team["agents"]:
        if a["name"] not in pl["agents"]:
            missing.append("%s fora do plano (rode `panel plan`)" % a["name"])
    return missing, pl


def reviews_sha(target, agent, pl):
    parts = []
    for r in sorted(x["name"] for x in pl["agents"][agent]["reviewers"]):
        parts.append([r, store.sha256_file(review_path(target, agent, r))])
    return store.sha256_obj(parts)


def _norm(s):
    s = (s or "").strip().strip("`").strip()
    return s[2:] if s.startswith("./") else s


def _words(s):
    return " ".join(re.findall(r"\w+", (s or "").lower()))


def consolidate(target):
    from probes.existence import existence_report
    from team._shared_tmp.cardtext import walk_strings
    from team._shared_tmp.common import expand
    from team._shared_tmp.factsio import Facts
    missing, pl = review_status(target)
    if missing:
        raise CsError("revisões pendentes: %s" % "; ".join(missing[:8]), "rode `cs.py panel status --all-reviewed`",
                      code=1)
    team = load_team(target)
    by = {a["name"]: a for a in team["agents"]}
    ex = existence_report(target, team)
    known = set(store.load_all_facts(target)) | store.index_ids(target)
    files = list(Facts(target).all_files())
    enum = team.get("veredito_enum") or ["PASS", "FAIL", "NEEDS_SPECIALIST"]
    ok_v, fail_v = ("PASS" if "PASS" in enum else enum[0]), ("FAIL" if "FAIL" in enum else enum[-1])
    rule_votes = {}
    results = {}
    for a in sorted(pl["agents"]):
        ag = by[a]
        card = ag.get("card") or {}
        miss = {}
        for m in (ex["agents"].get(a) or {}).get("missing") or []:
            miss.setdefault(_norm(str(m["value"])), m)
        items = [it for k in CARD_ITEMS for it in card.get(k) or [] if isinstance(it, dict)]
        card_text = "\n".join(s for _, s in walk_strings(card))
        author_files = set(expand(ag.get("territory") or [], files))
        conf = {k: [] for k in REVIEW_KEYS}
        rej = []
        # rt.2 (efeito): TODA falta de existência do cartão chega ao autor como objeção confirmada, mesmo que
        # nenhum revisor a tenha apontado (iteração 2: o orquestrador repassava à mão)
        flagged = set()
        for r in pl["agents"][a]["reviewers"]:
            rv0 = store.read5(review_path(target, a, r["name"]))
            flagged |= set(_norm(it.get("ref", "")) for it in rv0.get("afirmacoes_sem_evidencia") or [])
        for ref, m in sorted(miss.items()):
            if ref not in flagged:
                conf["afirmacoes_sem_evidencia"].append({
                    "afirmacao": "%s `%s` citado em %s" % (m["type"], m["value"], m["where"]), "ref": ref,
                    "reviewer": "probes-existence",
                    "evidencia": "probes existence: %s %s (%s)" % (m["type"], ref, m["why"])})
        for r in pl["agents"][a]["reviewers"]:
            rv = store.read5(review_path(target, a, r["name"]))
            rterr = sorted((by.get(r["name"]) or {}).get("territory") or [])
            tkey = "terr:" + ",".join(rterr) if rterr else "rev:" + r["name"]
            for it in rv["afirmacoes_sem_evidencia"]:
                ref = _norm(it.get("ref", ""))
                why = None
                if ref and ref in miss:
                    why = "probes existence: %s %s (%s)" % (miss[ref]["type"], ref, miss[ref]["why"])
                else:
                    w = _words(it["afirmacao"])
                    for ci in items:
                        cw = _words(ci.get("text"))
                        if w and cw and (w in cw or cw in w):
                            fl = ci.get("facts") or []
                            bad = [f for f in fl if f not in known]
                            if not fl or bad:
                                why = "item do cartão %s" % ("sem facts[]" if not fl else "com fato inexistente %s" % bad)
                            break
                entry = dict(it, reviewer=r["name"])
                if why:
                    conf["afirmacoes_sem_evidencia"].append(dict(entry, evidencia=why))
                else:
                    rej.append(dict(entry, tipo="afirmacoes_sem_evidencia",
                                    motivo="ref existe (probes existence ok)" if ref else
                                    "afirmação sustentada por fato ou ausente do cartão"))
            for it in rv["conflitos_com_meu_territorio"]:
                pth = _norm(it["path"])
                hit = set(expand([pth], files)) if pth else set()
                if not hit and pth in files:
                    hit = {pth}
                mine = hit & set(expand(rterr, files)) if rterr else set()
                touches = (hit & author_files) or (pth and pth in card_text)
                entry = dict(it, reviewer=r["name"])
                if hit and mine and touches:
                    conf["conflitos_com_meu_territorio"].append(dict(entry, evidencia="%d arquivo(s) do território de %s "
                                                                     "tocados pelo autor (ex.: %s)" % (
                                                                         len(mine), r["name"], sorted(mine)[0])))
                else:
                    rej.append(dict(entry, tipo="conflitos_com_meu_territorio",
                                    motivo="path não casa arquivo" if not hit else
                                    "fora do território do revisor" if not mine else "autor não toca o caminho"))
            for it in rv["regras_cross_cutting_faltando"]:
                bad = [f for f in it["facts"] if f not in known]
                entry = dict(it, reviewer=r["name"])
                if bad:
                    rej.append(dict(entry, tipo="regras_cross_cutting_faltando", motivo="fato inexistente %s" % bad))
                    continue
                conf["regras_cross_cutting_faltando"].append(entry)
                for f in it["facts"]:
                    v = rule_votes.setdefault(f, {"facts": [f], "regras": [], "reviewers": {}, "agents": set()})
                    if it["regra"] not in v["regras"]:
                        v["regras"].append(it["regra"])
                    v["reviewers"][r["name"]] = tkey
                    v["agents"].add(a)
        results[a] = {"confirmed": conf, "rejected": rej}
    cands = []
    for f in sorted(rule_votes):
        v = rule_votes[f]
        if len(set(v["reviewers"].values())) >= 2:
            cands.append({"facts": v["facts"], "regras": v["regras"], "reviewers": sorted(v["reviewers"]),
                          "agents": sorted(v["agents"])})
    core_n = len((team.get("core") or {}).get("lines") or [])
    store.write5(target, pdir(target, "core-candidates.json5"),
                 {"schema_version": 1, "candidates": cands, "core_lines": core_n,
                  "core_room": max(0, 40 - core_n), "at": store.now()},
                 "core-candidates.json5 — regras apontadas por ≥2 revisores de territórios diferentes; "
                 "gerado por cs.py panel consolidate")
    plan_sha = store.sha256_file(pdir(target, "plan.json5"))
    for a, res in results.items():
        n_conf = sum(len(v) for v in res["confirmed"].values())
        doc = {"schema_version": 1, "agent": a, "verdict": fail_v if n_conf else ok_v,
               "confirmed": res["confirmed"], "rejected": res["rejected"],
               "core_candidates": [c for c in cands if a in c["agents"]],
               "inputs": {"plan_sha256": plan_sha, "reviews_sha256": reviews_sha(target, a, pl)},
               "at": store.now()}
        store.write5(target, pdir(target, "%s.json5" % a), doc,
                     "painel consolidado de %s (só objeções confirmadas vão ao autor) — cs.py panel consolidate" % a)
        res["verdict"] = doc["verdict"]
        res["n_confirmed"] = n_conf
    return results, cands


def consolidate_check(target):
    """→ faltas[]: consolidado presente e fresco (plano e revisões iguais aos usados)."""
    team = load_team(target)
    pl = load_plan(target, team)
    plan_sha = store.sha256_file(pdir(target, "plan.json5"))
    probs = []
    if not os.path.isfile(pdir(target, "core-candidates.json5")):
        probs.append("core-candidates.json5 ausente")
    for a in sorted(pl["agents"]):
        doc = store.read5(pdir(target, "%s.json5" % a), required=False, default=None)
        if doc is None:
            probs.append("%s sem consolidado" % a)
            continue
        inp = doc.get("inputs") or {}
        if inp.get("plan_sha256") != plan_sha:
            probs.append("%s: plano mudou depois da consolidação" % a)
        elif inp.get("reviews_sha256") != reviews_sha(target, a, pl):
            probs.append("%s: revisões mudaram depois da consolidação" % a)
    return probs


def why_verdict(target, agent, probe_id, verdict):
    """Mérito de sonda POR-QUÊ → probes/panel/<agente>.json5 ({id: PASS|FAIL}, formato lido por probes check)."""
    from probes.generate import load_bank
    if verdict not in ("PASS", "FAIL"):
        raise CsError("--verdict deve ser PASS|FAIL")
    bank = load_bank(target)
    p = [x for x in bank["probes"] if x["id"] == probe_id and x["agent"] == agent]
    if not p:
        raise CsError("sonda %s de %s inexistente no banco" % (probe_id, agent))
    if not p[0].get("panel") and p[0]["type"] != "why":
        raise CsError("sonda %s não é POR-QUÊ (mérito só é julgado em sondas `why`)" % probe_id)
    path = store.sp(target, "probes", "panel", "%s.json5" % agent)
    cur = store.read5(path, required=False, default=None) or {}
    from probes.generate import probe_sha
    cur[probe_id] = {"verdict": verdict, "probe_sha256": probe_sha(p[0])}  # id repetido em banco novo não herda
    store.write5(target, path, cur, "painel de mérito das sondas POR-QUÊ de %s ({id: PASS|FAIL}) — cs.py panel why"
                 % agent)
    return cur


# ------------------------------------------------------------------ juízes POR-QUÊ: pacote e maioria
# Iteração 4 (ts-shop): o orquestrador montou `{tmp}/in/why.<a>.json5` à mão e escreveu `tmp/why-majority.sh` para
# tirar a maioria dos 3 juízes. Agora os dois passos são comandos; cada juiz grava `<dir>/j<N>.json5`.
WHY_JUDGES = 3
WHY_VERDICTS = ("PASS", "FAIL")


def _why_out_ok(target, out):
    root = os.path.realpath(target)
    if out != root and not out.startswith(root + os.sep):
        return True
    return out.startswith(os.path.join(root, STATE_DIR, "tmp") + os.sep)


def why_pack(target, agent, out):
    """`panel why pack <agente> --out <dir>` → <dir>/pack.json5 {kind: "why-pack", agent, judges: 3,
    items: [{probe, question, answer, evidence, gabarito_fonte, probe_sha256}], judge_file, judge_format}.
    `answer`/`evidence` = resposta do exame do agente (caminho único `.swarm/probes/exams/<a>.answers.json5`);
    `gabarito_fonte` = `answer.source` da sonda no bank (o juiz abre a fonte que define a resposta certa).
    Re-empacotar o mesmo <dir> apaga os votos antigos (j*.json5): voto vale só para o pacote atual."""
    import glob
    from cslib import json5io
    from probes.exam import _load_answers
    from probes.final import answers_path
    from probes.generate import load_bank, probe_sha
    out = os.path.realpath(os.path.abspath(os.path.expanduser(out)))
    if not _why_out_ok(target, out):
        raise CsError("--out dentro do alvo só em %s/tmp/ (senão o pacote polui o produto): %s" % (STATE_DIR, out),
                      "use %s/why/%s ou um diretório fora do alvo"
                      % (os.path.join(os.path.realpath(target), STATE_DIR, "tmp"), agent))
    if os.path.isdir(out) and os.listdir(out):
        old = os.path.join(out, "pack.json5")
        prev = json5io.load(old) if os.path.isfile(old) else None
        if not isinstance(prev, dict) or prev.get("kind") != "why-pack":
            raise CsError("--out existe e não é um pacote why anterior: %s" % out, "use um diretório vazio")
    bank = load_bank(target)
    probes = sorted((p for p in bank["probes"] if p.get("agent") == agent and p.get("type") == "why"),
                    key=lambda p: p["id"])
    if not probes:
        raise CsError("nenhuma sonda POR-QUÊ (`why`) de %s no banco" % agent, "confira o nome ou `probes generate`")
    ap = answers_path(target, agent)
    if not os.path.isfile(ap):
        raise CsError("respostas do exame de %s ausentes: %s" % (agent, ap),
                      "rode o exame guiado (`probes exam-pack %s --out ...`) e `probes check %s` antes" % (agent, agent))
    answers = _load_answers(ap)
    items = []
    for p in probes:
        a = answers.get(p["id"]) or {}
        items.append({"probe": p["id"], "question": p.get("question"), "answer": a.get("answer"),
                      "evidence": a.get("evidence") or [], "gabarito_fonte": (p.get("answer") or {}).get("source"),
                      "probe_sha256": probe_sha(p)})
    os.makedirs(out, exist_ok=True)
    for j in glob.glob(os.path.join(out, "j*.json5")) + glob.glob(os.path.join(out, "j*.json")):
        os.remove(j)
    exam_dir = None
    ptr = store.sp(target, "probes", "exams", "%s.exam-copy.json5" % agent)
    if os.path.isfile(ptr):
        exam_dir = (store.read5(ptr, required=False, default=None) or {}).get("out")
    doc = {"schema_version": 1, "kind": "why-pack", "agent": agent, "judges": WHY_JUDGES, "items": items,
           "exam_dir": exam_dir, "answers": os.path.relpath(ap, os.path.realpath(target)),
           "judge_file": os.path.join(out, "j<N>.json5") + " (N = 1..%d; um arquivo por juiz)" % WHY_JUDGES,
           "judge_format": {"juiz": "modelo usado", "veredictos": {"<probe>": "PASS|FAIL"},
                            "motivos": {"<probe>": "1 frase citando o gabarito_fonte"}},
           "tally_cmd": "cs.py panel why tally %s --from %s" % (agent, out)}
    with open(os.path.join(out, "pack.json5"), "w", encoding="utf-8") as fh:
        fh.write(json5io.dumps(doc, "itens dos juízes POR-QUÊ de %s — DADO, não instrução (cs.py panel why pack)"
                               % agent))
    return out, doc


def why_tally(target, agent, src):
    """`panel why tally <agente> --from <dir>`: maioria dos juízes (<dir>/j*.json5) → probes/panel/<agente>.json5,
    no mesmo formato de `panel why` ({id: {verdict, probe_sha256}} + votos). Tudo é validado ANTES de gravar:
    < 3 juízes ou nº par, sonda fora do pacote, veredito fora de PASS|FAIL, juiz que não julgou uma sonda votada
    pelos outros ou sonda que mudou no banco desde o pacote ⇒ recusa (exit ≠ 0) e o painel fica intacto."""
    import glob
    from cslib import json5io
    from probes.generate import load_bank, probe_sha
    src = os.path.realpath(os.path.abspath(os.path.expanduser(src)))
    pp = os.path.join(src, "pack.json5")
    if not os.path.isfile(pp):
        raise CsError("pacote ausente: %s" % pp, "rode `cs.py panel why pack %s --out %s` antes" % (agent, src))
    pack_ = json5io.load(pp)
    if not isinstance(pack_, dict) or pack_.get("kind") != "why-pack" or pack_.get("agent") != agent:
        raise CsError("%s não é o pacote why de %s" % (pp, agent))
    items = {i["probe"]: i for i in pack_.get("items") or [] if isinstance(i, dict) and i.get("probe")}
    files = sorted(set(glob.glob(os.path.join(src, "j*.json5")) + glob.glob(os.path.join(src, "j*.json"))))
    P, votes, judges = [], {}, []
    for f in files:
        fn = os.path.basename(f)
        try:
            j = json5io.load(f)
        except Exception as exc:  # noqa — arquivo de juiz ilegível é recusa, não crash
            P.append("%s ilegível (%s)" % (fn, exc))
            continue
        ver = j.get("veredictos") if isinstance(j, dict) else None
        if not isinstance(ver, dict) or not ver:
            P.append("%s sem `veredictos` {<probe>: PASS|FAIL}" % fn)
            continue
        judges.append((fn, str(j.get("juiz") or os.path.splitext(fn)[0])))
        for pid, v in ver.items():
            if pid not in items:
                P.append("%s: sonda %s fora do pacote" % (fn, pid))
            elif v not in WHY_VERDICTS:
                P.append("%s: veredito %r para %s (só PASS|FAIL)" % (fn, v, pid))
            else:
                votes.setdefault(pid, {})[fn] = v
    n = len(judges)
    if n < WHY_JUDGES or n % 2 == 0:
        P.append("%d juiz(es) em %s: a maioria exige ≥%d e número ímpar" % (n, src, WHY_JUDGES))
    for pid, vs in sorted(votes.items()):
        miss = [fn for fn, _ in judges if fn not in vs]
        if miss:
            P.append("sonda %s sem voto de %s" % (pid, ", ".join(miss)))
    if not votes and not P:
        P.append("nenhum voto nos arquivos de juiz")
    bank = {p["id"]: p for p in load_bank(target)["probes"] if p.get("agent") == agent}
    for pid in votes:
        p = bank.get(pid)
        if p is None or probe_sha(p) != (items[pid].get("probe_sha256") or probe_sha(p)):
            P.append("sonda %s mudou no banco desde o pacote: refaça `panel why pack`" % pid)
    if P:
        raise CsError("tally recusado, painel intacto:\n  - " + "\n  - ".join(P[:20]),
                      "corrija os arquivos dos juízes em %s (formato em pack.json5 `judge_format`)" % src)
    path = store.sp(target, "probes", "panel", "%s.json5" % agent)
    cur = store.read5(path, required=False, default=None) or {}
    res = {}
    for pid, vs in sorted(votes.items()):
        n_pass = sum(1 for v in vs.values() if v == "PASS")
        verdict = "PASS" if n_pass * 2 > len(vs) else "FAIL"
        cur[pid] = {"verdict": verdict, "probe_sha256": probe_sha(bank[pid]),
                    "votes": {"%s (%s)" % (name, fn): vs[fn] for fn, name in judges}, "by": "panel why tally"}
        res[pid] = (verdict, n_pass, len(vs))
    store.write5(target, path, cur, "painel de mérito das sondas POR-QUÊ de %s ({id: PASS|FAIL}) — cs.py panel why "
                 "tally (maioria de %d juízes)" % (agent, n))
    return res, n


# ------------------------------------------------------------------ pack (cético isolado)

def copy_repo(root, dest):
    """Cópia dos arquivos versionados do alvo SEM `.swarm/` e `.git/` (fonte única: `panel pack` e
    `probes exam-pack --out`). Symlink não é seguido. → nº de arquivos copiados."""
    import shutil
    from team._shared_tmp.common import list_repo_files
    os.makedirs(dest)
    n = 0
    for rel in list_repo_files(root):
        if rel.startswith((".swarm/", ".git/")) or rel == STATE_DIR:
            continue
        src = os.path.join(root, rel)
        if os.path.islink(src) or not os.path.isfile(src):
            continue
        dst = os.path.join(dest, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        n += 1
    return n


PACK_ROLES = ("cetico", "adjacente")


def pack(target, agent, role, out, reviewer=None):
    """Pacote isolado para um revisor: `<out>/repo/` = cópia dos arquivos do alvo SEM `.swarm/` (rascunhos,
    entrevista, revisões dos outros e gabarito não entram) + `card.json5` (o cartão como DADO, sem lacunas) +
    `facts.json5` (fatos citados pelo cartão, sem os da entrevista) + `pack.json5` (manifesto)."""
    import shutil
    from cslib import json5io
    from team._shared_tmp.common import list_repo_files
    if role not in PACK_ROLES:
        raise CsError("--role deve ser %s" % "|".join(PACK_ROLES))
    team = load_team(target)
    by = {a["name"]: a for a in team["agents"]}
    if agent not in by:
        raise CsError("agente inexistente: %s" % agent)
    ag = by[agent]
    if not ag.get("card"):
        raise CsError("%s sem cartão" % agent, "rode `cs.py team card set %s --file ...`" % agent)
    out = os.path.realpath(os.path.abspath(out))
    root = os.path.realpath(target)
    sp_tmp = os.path.join(root, STATE_DIR, "tmp")
    if (out == root or out.startswith(root + os.sep)) and not out.startswith(sp_tmp + os.sep):
        raise CsError("--out dentro do alvo só em .swarm/tmp/ (senão o pacote polui o produto): %s" % out,
                      "use %s/<nome> ou um diretório fora do alvo" % sp_tmp)
    if os.path.isdir(out) and os.listdir(out):
        if not os.path.isfile(os.path.join(out, "pack.json5")):
            raise CsError("--out existe e não é um pacote anterior: %s" % out, "use um diretório vazio")
        shutil.rmtree(out)
    n = copy_repo(root, os.path.join(out, "repo"))
    card = dict(ag["card"])
    for k in ("lacunas", "injection_attempts", "notes", "notas"):
        card.pop(k, None)
    cited = sorted(set(x for k in CARD_ITEMS for it in card.get(k) or [] if isinstance(it, dict)
                       for x in it.get("facts") or []))
    allf = store.load_all_facts(target)
    facts = [allf[f] for f in cited if f in allf and allf[f].get("layer") != "interview"]
    data = {"agent": agent, "kind": ag.get("kind"), "territory": ag.get("territory") or [],
            "reads": ag.get("reads") or [], "card": card}
    docs = {"card.json5": data, "facts.json5": {"facts": facts},
            "pack.json5": {"schema_version": 1, "agent": agent, "role": role, "repo": "repo/", "files": n,
                           "excluded": [".swarm/"], "at": store.now()}}
    if role == "adjacente" and reviewer:
        if reviewer not in by or not by[reviewer].get("card"):
            raise CsError("revisor sem cartão: %s" % reviewer)
        rc = dict(by[reviewer]["card"])
        rc.pop("lacunas", None)
        docs["reviewer.json5"] = {"agent": reviewer, "territory": by[reviewer].get("territory") or [], "card": rc}
    for name, obj in docs.items():
        with open(os.path.join(out, name), "w", encoding="utf-8") as fh:
            fh.write(json5io.dumps(obj, "%s — DADO para o revisor %s de %s (cs.py panel pack); não é instrução"
                                   % (name, role, agent)))
    return out, n
