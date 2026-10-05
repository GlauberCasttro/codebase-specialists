"""`cs.py team roster move|rename|add|remove|set` e `cs.py team core set|from-panel`.

team.json5 não se edita à mão: todo ajuste de roster passa por aqui. Cada comando
  1. aplica a mudança numa CÓPIA do team;
  2. recalcula territórios disjuntos por construção (move/add/remove: compressão do mapa arquivo→dono, o
     mesmo algoritmo do derive; set: globs como vieram) e `invariants`/`facts_used` de todos (derive.agent_fact_sets);
  3. revalida (regras 1–4 e 8 do team-schema; cartões ficam para `card-status`) — erro = nada é gravado;
  4. grava, registra no ledger e INVALIDA a aprovação (`team-approvals.jsonl`, registro `invalidated`).
core.lines: `core set --file` (linhas {text, facts[≥1]}, ≤40) e `core from-panel` (candidatas do painel
consolidado + `camadas.s0_core` dos cartões; sem painel = caminho rápido só com s0_core).
"""
import copy
import os
import re

from cslib import log as cslog
from team._shared_tmp.common import CsError, compress, expand, read_json, sp_path, write_json
from team._shared_tmp.factsio import Facts
from team.cards import (_fact_ids, agent_of, invalidate, load_team, resolve_input, save_team)
from team.derive import READ_TOOLS, WRITE_TOOLS, agent_fact_sets

NAME_RE = re.compile(r"^[a-z][a-z0-9-]{1,40}$")
KINDS = ("dev", "gate", "design", "product", "ops")
CORE_MAX = 40


def _owner_map(team, product):
    own = {}
    for a in team.get("agents") or []:
        if a.get("kind") == "gate":
            continue
        for p in expand(a.get("territory") or [], product):
            own.setdefault(p, a["name"])
    return own


def _recompress(team, facts, own):
    boundary = list(facts.ownable_files()) + facts.reserved_files()
    o = dict(own)
    for r in facts.reserved_files():
        o[r] = "__reserved__"
    terr = compress(o, sorted(set(boundary)))
    for a in team["agents"]:
        if a.get("kind") != "gate":
            a["territory"] = terr.get(a["name"], [])


def reads_facts(facts, a, product):
    """Fatos de regra/negócio/glossário/decisão que tocam o que o agente LÊ (reads) — contexto, não invariante.
    Iteração 2: `roster add/set` mudando só `reads` deixava facts_used velho (dev-storage com migrations/**)."""
    if a.get("kind") == "gate":
        return []
    terr = set(expand(a.get("territory") or [], product))
    rf = [p for p in expand(a.get("reads") or [], product) if p not in terr]
    if not rf:
        return []
    from team.derive import _touching
    pool = facts.rules() + facts.interview_invariants() + list(facts.facts.get("business_rules", [])) + \
        list(facts.facts.get("glossary", [])) + list(facts.facts.get("rationale", []))
    return _touching(pool, rf)


def _refresh_facts(team, facts):
    product = facts.product_files()
    for a in team["agents"]:
        files = expand(a.get("territory") or [], product) if a.get("kind") != "gate" else []
        inv, used = agent_fact_sets(facts, a["name"], a.get("kind"), files)
        card = a.get("card") or {}
        cited = set(x for k in ("knows", "refuses", "rules", "footguns") for it in card.get(k) or []
                    if isinstance(it, dict) for x in it.get("facts") or [])
        a["invariants"] = inv
        a["facts_used"] = sorted(set(used) | cited | set(reads_facts(facts, a, product)))


UNIVERSAL_LAYERS = ("project_docs", "rules", "rationale", "operations")
BROAD_KINDS = ("gate", "design", "product", "ops")


def _is_instruction(f):
    return str(f.get("id", "")).startswith("docs.instr.") or \
        str((f.get("data") or {}).get("kind") or "").lower() == "agent_instruction"


def pack_extras(allf, ag, scope_files):
    """Fatos que o pacote do redator leva ALÉM do território (iteração 3: `team facts` não entregava a instrução
    do time de escopo `**` a nenhum agente e o `security` recebia só gap.* nos 3 alvos):
      - todo agente: instrução do time (docs.instr.*, L10) que toca o escopo, decisões de ADR (rat.adr.*) e os
        fatos de escopo `**`/sem escopo das camadas rules/rationale/operations/project_docs;
      - gate/design/product/ops e qa (papéis sem território de código ou transversais): todos os comandos
        (ops.*, com o status verified/declared do scan) e todo o rationale;
      - gate: todos os invariantes negativos (rules.never.*) — reviewer e security julgam o diff inteiro.
    Nunca toca `facts_used`/`invariants` gravados (o pacote é calculado na leitura)."""
    kind, name = ag.get("kind"), ag.get("name")
    files = sorted(scope_files)
    broad = kind in BROAD_KINDS or name == "qa" or not files
    from team.derive import is_negative_invariant
    out = set()
    for fid, f in allf.items():
        if fid.startswith("gap."):
            continue
        sc = f.get("scope") or []
        layer = f.get("layer")
        star = not sc or "**" in sc
        if _is_instruction(f):
            if star or broad or expand(sc, files):
                out.add(fid)
        elif fid.startswith("rat.adr.") or (layer == "rationale" and
                                             str((f.get("data") or {}).get("kind") or "").lower() == "adr"):
            out.add(fid)
        elif layer in UNIVERSAL_LAYERS and star:
            out.add(fid)
        elif broad and layer in ("operations", "rationale"):
            out.add(fid)
        elif kind == "gate" and is_negative_invariant(f):
            out.add(fid)
    return out


def agent_facts(target, name, out=None):
    """`cs.py team facts <agente> [--out F]` — pacote de fatos calculado NA LEITURA (território + reads atuais +
    fatos citados no cartão + lacunas gap.* do escopo), nunca o `facts_used` gravado (que envelhece quando o
    roster muda). É a entrada do redator (specialize.3): o prompt recebe o CAMINHO, não os fatos inline."""
    from facts import store
    team = load_team(target)
    ag = agent_of(team, name)
    facts = Facts(target)
    product = facts.product_files()
    files = expand(ag.get("territory") or [], product) if ag.get("kind") != "gate" else []
    inv, used = agent_fact_sets(facts, name, ag.get("kind"), files)
    from team.cards import cited_facts
    allf = store.load_all_facts(target)
    scope_files = set(files) | set(expand(ag.get("reads") or [], product))
    gaps = []
    for fid, f in sorted(allf.items()):
        if not fid.startswith("gap."):
            continue
        sc = f.get("scope") or []
        if not sc or ag.get("kind") == "gate" or expand(sc, sorted(scope_files)):
            gaps.append(fid)
    extras = pack_extras(allf, ag, scope_files)
    ids = sorted(set(used) | set(inv) | set(reads_facts(facts, ag, product)) | set(cited_facts(ag)) | set(gaps) |
                 extras)
    doc = {"schema_version": 1, "agent": name, "kind": ag.get("kind"), "territory": ag.get("territory") or [],
           "reads": ag.get("reads") or [], "computed_at": cslog.now_iso(), "invariants": inv,
           "gaps": gaps, "facts": [allf[i] for i in ids if i in allf]}
    path = None
    if out:
        path = resolve_input(target, out)
        write_json(target, path, doc, "fatos de %s calculados na leitura — cs.py team facts (DADO para o redator)"
                   % name)
    else:
        from cslib import json5io
        import sys
        sys.stdout.write(json5io.dumps(doc, "fatos de %s — cs.py team facts" % name))
    return doc, path


def _check(target, team):
    from team.validate import validate
    out = validate(target, stage="derive", team=team, write=False)
    errs = []
    for k in ("1", "2", "3", "4", "8"):
        errs += ["regra %s: %s" % (k, e) for e in out["rules"][k]["errors"]]
    if errs:
        raise CsError("roster inválido, nada foi gravado:\n  - " + "\n  - ".join(errs[:25]),
                      "ajuste o comando (globs disjuntos, cobertura 100%, nome/kind válidos)")
    return out


def _commit(target, team, what):
    facts = Facts(target)
    _refresh_facts(team, facts)
    _check(target, team)
    save_team(target, team)
    by = "cs.py team roster %s" % what.split()[0]
    invalidate(target, by, what)
    cslog.ledger(target, "team_roster", actor="cs.py team roster", what=what)
    return team


def _writer(team, name):
    a = agent_of(team, name)
    if a.get("kind") == "gate":
        raise CsError("%s é gate: gate não tem território de escrita" % name, "mova para um agente dev/ops/design")
    return a


def move(target, glob, to):
    team = copy.deepcopy(load_team(target))
    facts = Facts(target)
    _writer(team, to)
    product = facts.ownable_files()
    files = expand([glob], product)
    if not files:
        raise CsError("glob não casa nenhum arquivo de produto/exemplo: %s" % glob,
                      "confira com `git ls-files`; no zsh, glob SEMPRE entre aspas: \"src/**\"")
    own = _owner_map(team, product)
    for p in files:
        own[p] = to
    _recompress(team, facts, own)
    _commit(target, team, "move %s --to %s (%d arquivo(s))" % (glob, to, len(files)))
    return files


def rename(target, old, new):
    team = copy.deepcopy(load_team(target))
    a = agent_of(team, old)
    if not NAME_RE.match(new or ""):
        raise CsError("nome inválido: %r" % new, "use ^[a-z][a-z0-9-]{1,40}$")
    if any(x["name"] == new for x in team["agents"]):
        raise CsError("já existe agente %s" % new)
    a["name"] = new
    _commit(target, team, "rename %s %s" % (old, new))
    st_path = sp_path(target, "cards", "status.json5")
    if os.path.isfile(st_path):
        from team.cards import load_status, save_status
        st = load_status(target)
        if old in st:
            st[new] = st.pop(old)
            save_status(target, st)
    return a


def add(target, name, kind, territory, reads=None, tools=None):
    team = copy.deepcopy(load_team(target))
    if not NAME_RE.match(name or ""):
        raise CsError("nome inválido: %r" % name, "use ^[a-z][a-z0-9-]{1,40}$")
    if any(x["name"] == name for x in team["agents"]):
        raise CsError("já existe agente %s" % name, "use `team roster move` para dar território a ele")
    if kind not in KINDS:
        raise CsError("kind fora do enum: %s" % kind, "kinds: %s" % ", ".join(KINDS))
    territory = [g for g in territory or [] if g]
    if kind == "gate" and territory:
        raise CsError("gate não tem território de escrita")
    facts = Facts(target)
    product = facts.ownable_files()
    own = _owner_map(team, product)
    moved = []
    for g in territory:
        fs = expand([g], product)
        if not fs:
            raise CsError("glob não casa nenhum arquivo de produto/exemplo: %s" % g,
                          "no zsh, glob SEMPRE entre aspas: --territory \"examples/**\"")
        for p in fs:
            own[p] = name
            moved.append(p)
    ag = {"name": name, "kind": kind, "territory": [], "reads": sorted(set(reads or (["**"] if kind != "dev" else []))),
          "tools": tools or (READ_TOOLS if (kind == "gate" or not territory) else WRITE_TOOLS),
          "model": "inherit", "card": None, "invariants": [], "facts_used": []}
    if kind == "gate":
        ag["gate_scope"] = "all"
    team["agents"].append(ag)
    _recompress(team, facts, own)
    _commit(target, team, "add %s --kind %s (%d arquivo(s))" % (name, kind, len(set(moved))))
    return ag


def remove(target, name, to=None):
    team = copy.deepcopy(load_team(target))
    a = agent_of(team, name)
    facts = Facts(target)
    product = facts.ownable_files()
    own = _owner_map(team, product)
    mine = [p for p, o in own.items() if o == name]
    if mine and not to:
        raise CsError("%s tem %d arquivo(s) de escrita" % (name, len(mine)),
                      "passe --to <agente> para quem herda o território")
    if to:
        if to == name:
            raise CsError("--to não pode ser o próprio agente")
        _writer(team, to)
        for p in mine:
            own[p] = to
    team["agents"] = [x for x in team["agents"] if x is not a]
    _recompress(team, facts, own)
    _commit(target, team, "remove %s%s" % (name, (" --to %s" % to) if to else ""))
    return mine


def set_roster(target, path):
    team = copy.deepcopy(load_team(target))
    raw = read_json(resolve_input(target, path), "roster")
    items = raw.get("agents") if isinstance(raw, dict) else raw
    if not isinstance(items, list) or not items:
        raise CsError("roster deve ser {agents: [{name, kind, territory, reads, tools?, model?}]}")
    old = {a["name"]: a for a in team["agents"]}
    new = []
    for i, r in enumerate(items):
        if not isinstance(r, dict) or not r.get("name") or not r.get("kind"):
            raise CsError("agents[%d] sem name/kind" % i)
        base = copy.deepcopy(old.get(r.get("renamed_from") or r["name"]) or {"card": None})
        base.update({"name": r["name"], "kind": r["kind"], "territory": list(r.get("territory") or []),
                     "reads": list(r.get("reads") or [])})
        base["tools"] = r.get("tools") or base.get("tools") or (
            READ_TOOLS if (r["kind"] == "gate" or not base["territory"]) else WRITE_TOOLS)
        base["model"] = r.get("model") or base.get("model") or "inherit"
        if r["kind"] == "gate":
            base["gate_scope"] = r.get("gate_scope") or base.get("gate_scope") or (
                "security" if r["name"] == "security" else "all")
        else:
            base.pop("gate_scope", None)
        for k in ("invariants", "facts_used"):
            base.setdefault(k, [])
        new.append(base)
    team["agents"] = new
    _commit(target, team, "set --file %s (%d agentes)" % (path, len(new)))
    return team


# ------------------------------------------------------------------ core.lines

def _norm(t):
    """Texto normalizado: minúsculo, sem acento e sem pontuação ("Não edite migração." == "Nao edite migracao")."""
    from cslib.tokenize import strip_accents
    return " ".join(re.findall(r"\w+", strip_accents((t or "").lower())))


def validate_core(lines, fact_ids):
    errs = []
    if not isinstance(lines, list) or not lines:
        return ["core.lines deve ser lista não vazia"]
    if len(lines) > CORE_MAX:
        errs.append("core.lines = %d > %d (mova o que vale para um território só para o cartão/S2)"
                    % (len(lines), CORE_MAX))
    for i, ln in enumerate(lines):
        where = "lines[%d]" % i
        if not isinstance(ln, dict) or not isinstance(ln.get("text"), str) or not ln["text"].strip():
            errs.append("%s sem text" % where)
            continue
        if "\n" in ln["text"]:
            errs.append("%s: uma linha só" % where)
        fl = ln.get("facts")
        if not isinstance(fl, list) or not fl:
            errs.append("%s: sem facts[] (nada entra no core sem fato)" % where)
            continue
        for f in fl:
            if f not in fact_ids:
                errs.append("%s: fato inexistente %s" % (where, f))
    return errs


def _existence_errors(target, team):
    from probes.existence import existence_report
    rep = existence_report(target, team)
    return ["%s %s (%s)" % (m["type"], m["value"], m["why"]) for m in rep["core"]["missing"]]


def _save_core(target, team, lines, what):
    errs = validate_core(lines, _fact_ids(target))
    t2 = copy.deepcopy(team)
    t2.setdefault("core", {})["lines"] = [{"text": " ".join(l["text"].split()), "facts": sorted(set(l["facts"]))}
                                          for l in lines]
    if not errs:
        errs = ["existência: " + e for e in _existence_errors(target, t2)]
    if errs:
        raise CsError("core inválido, nada foi gravado:\n  - " + "\n  - ".join(errs[:25]),
                      "cada linha: {text, facts:[ids]}; caminho/comando citado tem de existir/estar verified")
    save_team(target, t2)
    cslog.ledger(target, "team_core", actor="cs.py team core", what=what, lines=len(lines))
    return t2["core"]["lines"]


def core_set(target, path):
    raw = read_json(resolve_input(target, path), "core")
    lines = raw.get("lines") if isinstance(raw, dict) else raw
    if isinstance(raw, dict) and isinstance(raw.get("core"), dict):
        lines = raw["core"].get("lines")
    saved = _save_core(target, load_team(target), lines or [], "set --file %s" % path)
    write_json(target, promotion_path(target),
               {"schema_version": 1, "at": cslog.now_iso(), "source": "set", "file": path,
                "candidates_sha256": _file_sha(sp_path(target, "panel", "core-candidates.json5")),
                "promoted": [{"text": l["text"], "facts": l["facts"], "origin": "set"} for l in saved], "refused": []},
               "core-promotion.json5 — core gravado por `team core set`")
    return saved


_LINE_NO = re.compile(r"((?:[\w.@-]+/)*[\w@-][\w.@-]*\.[A-Za-z0-9]{1,8}|Makefile|Dockerfile|Jenkinsfile)"
                      r"(?::\d+(?:-\d+)?|#L\d+(?:-L?\d+)?)")
DUP_JACCARD = 0.6


DUP_JACCARD_SAME_FACT = 0.3  # mesma regra em outra redação: compartilha fato E ≥30% das palavras


def _words(t):
    return set(w for w in re.findall(r"\w{3,}", _norm(t)))


def _jaccard(a, b):
    wa, wb = _words(a), _words(b)
    return len(wa & wb) / float(len(wa | wb)) if wa and wb else 0.0


def _near_dup(a, b):
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return False
    return len(wa & wb) / float(len(wa | wb)) >= DUP_JACCARD


def core_room(team):
    """Linhas de core que cabem no S0 (≤40 linhas com o mapa de agentes e as linhas operacionais), medido com o
    MESMO renderizador do emit (iteração 2: 26 linhas de core + mapa de 11 agentes estouraram o S0 só no emit)."""
    try:
        from emit import render
        from emit.platforms import ORCH_CLAUDE
    except ImportError:  # pragma: no cover
        return CORE_MAX
    if not all((a.get("card") or {}).get("description") for a in team.get("agents") or []):
        return CORE_MAX
    t = copy.deepcopy(team)
    t.setdefault("core", {})["lines"] = []
    worst = 0
    for args in ((".claude/agents/{n}.md", "native", render.orch_pointer(ORCH_CLAUDE)), (None, "terminal")):
        try:
            worst = max(worst, render.count_lines(render.s0_block(t, *args)))
        except Exception:  # cartão incompleto: sem medida, vale o teto do schema
            return CORE_MAX
    return max(0, min(CORE_MAX, render.BUDGET["S0"] - worst))


def promotion_path(target):
    return sp_path(target, "panel", "core-promotion.json5")


def _file_sha(path):
    import hashlib
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def core_from_panel(target):
    """Core = linhas atuais + candidatas do painel (≥2 revisores) + s0_core dos cartões.

    Iteração 3: cada candidata é limpa (sem `arquivo:linha` — vira só o arquivo), deduplicada (texto igual,
    mesmo conjunto de fatos ou quase igual por Jaccard ≥0,6) e conferida por referência com o classificador
    único (`cslib/refs.py`): candidata com caminho/símbolo/comando inexistente é RECUSADA com o motivo — não
    derruba as outras. O total respeita o espaço que sobra no S0 (mapa de agentes + linhas operacionais).
    Grava `.swarm/panel/core-promotion.json5` {promoted[], refused[{text, why}], room} — o check de rt.3
    exige esse registro fresco (linhas promovidas OU recusa explícita)."""
    from probes.existence import RepoIndex
    from team._shared_tmp.cardtext import extract_refs
    team = load_team(target)
    idx = RepoIndex(target)
    out, refused = [], []
    seen_f = set()

    def bad_refs(text):
        miss = []
        for kind, val, extra in extract_refs(text):
            ok, why = idx.check(kind, val, extra)
            if not ok:
                miss.append("%s `%s` (%s)" % (kind, val, why))
        return miss

    def push(text, fl, origin):
        text = " ".join(_LINE_NO.sub(r"\1", text or "").split())
        k_f = tuple(sorted(set(fl or [])))
        if not text or not k_f:
            if text:
                refused.append({"text": text, "origin": origin, "why": "sem fato"})
            return
        for o in out:
            if _norm(text) == _norm(o["text"]) or _near_dup(text, o["text"]):
                o["facts"] = sorted(set(o["facts"]) | set(k_f))  # quase-duplicata: soma a evidência, não a linha
                return
            if set(k_f) <= set(o["facts"]):
                return  # mesma evidência já está no core em outra redação
            if set(k_f) & set(o["facts"]) and _jaccard(text, o["text"]) >= DUP_JACCARD_SAME_FACT:
                # iteração 3 (go-polyglot): a mesma regra em 3 redações com fatos superconjunto/sobrepostos
                o["facts"] = sorted(set(o["facts"]) | set(k_f))
                return
        if k_f in seen_f:
            return
        miss = bad_refs(text)
        if miss:
            refused.append({"text": text, "origin": origin, "why": "referência inexistente: " + "; ".join(miss[:3])})
            return
        seen_f.add(k_f)
        out.append({"text": text, "facts": list(k_f), "origin": origin})

    for ln in (team.get("core") or {}).get("lines") or []:
        if isinstance(ln, dict):
            push(ln.get("text", ""), ln.get("facts") or [], "atual")
    cp = sp_path(target, "panel", "core-candidates.json5")
    used_panel = os.path.isfile(cp)
    if used_panel:
        cands = read_json(cp, "panel/core-candidates.json5").get("candidates") or []
        for c in sorted(cands, key=lambda c: (-len(c.get("reviewers") or []), c.get("facts") or [])):
            regras = c.get("regras") or []
            push(regras[0] if regras else "", c.get("facts") or [], "painel")
    votes = {}
    for a in team.get("agents") or []:
        for it in (a.get("camadas") or {}).get("s0_core") or []:
            k = _norm(it.get("text"))
            v = votes.setdefault(k, {"text": it.get("text", ""), "facts": set(), "agents": set()})
            v["facts"] |= set(it.get("facts") or [])
            v["agents"].add(a["name"])
    for v in sorted(votes.values(), key=lambda v: (-len(v["agents"]), _norm(v["text"]))):
        push(v["text"], sorted(v["facts"]), "s0_core")
    room = core_room(team)
    lines, dropped = out[:room], out[room:]
    for d in dropped:
        refused.append({"text": d["text"], "origin": d["origin"],
                        "why": "sem espaço no S0 (cabem %d linhas de core com o mapa de agentes)" % room})
    if not lines and not refused:
        raise CsError("nada para o core: sem linhas atuais, sem panel/core-candidates.json5 e sem camadas.s0_core",
                      "grave os cartões com camadas (`team card set`) ou use `team core set --file`")
    if lines:
        saved = _save_core(target, team, [{"text": l["text"], "facts": l["facts"]} for l in lines],
                           "from-panel%s" % ("" if used_panel else " (sem painel: s0_core)"))
    else:
        saved = []
    rec = {"schema_version": 1, "at": cslog.now_iso(), "source": "from-panel", "used_panel": used_panel,
           "candidates_sha256": _file_sha(cp), "room": room,
           "promoted": [{"text": l["text"], "facts": l["facts"], "origin": l["origin"]} for l in lines],
           "refused": refused}
    write_json(target, promotion_path(target), rec,
               "core-promotion.json5 — o que `team core from-panel` promoveu e recusou (com motivo)")
    return saved, dropped, used_panel, refused


def core_check(target):
    """Check de rt.3 (efeito): promoção registrada sobre as candidatas ATUAIS e core não vazio — ou recusa
    explícita de tudo, com motivo. `panel consolidate` sem `team core from-panel` não fecha rt.3."""
    probs = []
    rp = promotion_path(target)
    if not os.path.isfile(rp):
        return ["core não promovido: rode `cs.py team core from-panel` (ou `team core set --file`) depois do "
                "`panel consolidate`"]
    rec = read_json(rp, "panel/core-promotion.json5")
    cp = sp_path(target, "panel", "core-candidates.json5")
    if rec.get("source") == "from-panel" and rec.get("candidates_sha256") != _file_sha(cp):
        probs.append("candidatas do painel mudaram depois da promoção: rode `cs.py team core from-panel` de novo")
    lines = ((load_team(target).get("core") or {}).get("lines")) or []
    if not lines and not rec.get("refused"):
        probs.append("core vazio e nenhuma recusa registrada")
    return probs
