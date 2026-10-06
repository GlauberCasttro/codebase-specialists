"""Aprovação do roster (specialize.2) e ciclo de vida dos cartões (specialize.3, rt.4).

Aprovações (append-only): .swarm/team-approvals.jsonl
  {ts, by, note, roster_sha256, agents[]}; roster = [{name, kind, territory, reads}] ordenado por nome
  (cartões fora do hash: redigir cartão não invalida a aprovação; mudar roster invalida).
Status dos cartões: .swarm/cards/status.json5
  {<agente>: {drafted: {at, sha256, by}, revised?: {at, sha256, panel_sha256, note, changed}}}
  sha256 = JSON canônico do cartão. Cartão alterado fora de `team card set|revise` = não conta.
"""
import hashlib
import json
import os

from cslib import jsonio
from cslib import log as cslog
from team._shared_tmp.common import CsError, read_json, sp_path, write_json
from team._shared_tmp.factsio import Facts

CARD_KEYS = {"description", "mission", "knows", "refuses", "done_when", "playbooks", "rules", "footguns",
             "anchors"}
ITEM_LISTS = ("knows", "refuses", "rules", "footguns")
FACTS_REQUIRED = ("knows", "footguns")
MAX_DESC = 300


def _sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _file_sha(path):
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def load_team(target):
    return read_json(sp_path(target, "team.json5"), "team.json5")


def save_team(target, team):
    write_json(target, sp_path(target, "team.json5"), team,
               "team.json5 — roster e cartões; gerado por cs.py team (derive/card)")


def agent_of(team, name):
    for a in team.get("agents") or []:
        if a.get("name") == name:
            return a
    raise CsError("agente inexistente no team.json5: %s" % name,
                  "agentes: %s" % ", ".join(a.get("name", "?") for a in team.get("agents") or []))


# ------------------------------------------------------------------ roster

def roster(team):
    return sorted(({"name": a.get("name"), "kind": a.get("kind"), "territory": sorted(a.get("territory") or []),
                    "reads": sorted(a.get("reads") or [])} for a in team.get("agents") or []),
                  key=lambda r: str(r["name"]))


def approvals_path(target):
    return sp_path(target, "team-approvals.jsonl")


def _jsonl(path):
    out = []
    if not os.path.isfile(path):
        return out
    with open(path, "rb") as fh:
        for i, raw in enumerate(fh, 1):
            if raw.strip():
                try:
                    out.append(json.loads(raw.decode("utf-8")))
                except ValueError as exc:
                    raise CsError("%s:%d ilegível (%s)" % (path, i, exc), "restaure do git; nunca edite à mão")
    return out


def approve(target, by, note, simulated=False):
    """`--simulated`: sem humano (eval/CI) — o registro ganha `approval: simulated` (como `cs.py approve`)."""
    if not (by or "").strip():
        raise CsError("--by vazio", "informe quem aprovou (nome do usuário)")
    team = load_team(target)
    if not team.get("agents"):
        raise CsError("team.json5 sem agentes", "rode `cs.py team derive`")
    errs = roster_errors(target, team)
    if errs:
        raise CsError("roster inválido não pode ser aprovado:\n  - " + "\n  - ".join(errs[:10]),
                      "corrija com `cs.py team roster ...` e aprove de novo")
    rec = {"ts": cslog.now_iso(), "by": by.strip(), "note": (note or "").strip(),
           "roster_sha256": _sha(roster(team)), "agents": [r["name"] for r in roster(team)],
           "approval": "simulated" if simulated else "human"}
    jsonio.append_jsonl(approvals_path(target), rec, target=target)
    return rec


def roster_errors(target, team):
    """Regras 1–4 e 8 (as do roster) sobre o team atual — aprovação só vale para roster válido."""
    from team.validate import validate
    out = validate(target, stage="derive", team=team, write=False)
    return ["regra %s: %s" % (k, e) for k in ("1", "2", "3", "4", "8") for e in out["rules"][k]["errors"]]


def invalidate(target, by, what):
    """Ajuste de roster por comando invalida a aprovação explicitamente (mesmo se o sha voltar a bater)."""
    recs = _jsonl(approvals_path(target))
    prev = next((r for r in reversed(recs) if not r.get("invalidated")), None)
    rec = {"ts": cslog.now_iso(), "by": by, "invalidated": True, "what": what,
           "previous_by": (prev or {}).get("by")}
    jsonio.append_jsonl(approvals_path(target), rec, target=target)
    return rec


def approved(target):
    """→ (ok, mensagem)."""
    team = load_team(target)
    recs = _jsonl(approvals_path(target))
    if not recs:
        return False, "roster sem aprovação registrada (`cs.py team approve --by <nome> --note ...`)"
    last = recs[-1]
    cur = _sha(roster(team))
    if last.get("invalidated"):
        return False, ("roster alterado por `%s` em %s (aprovação anterior de %s invalidada); aprove de novo"
                       % (last.get("by"), last.get("ts"), last.get("previous_by") or "?"))
    if last.get("roster_sha256") != cur:
        now = set(r["name"] for r in roster(team))
        was = set(last.get("agents") or [])
        diff = []
        if now - was:
            diff.append("novos: %s" % ", ".join(sorted(now - was)))
        if was - now:
            diff.append("removidos: %s" % ", ".join(sorted(was - now)))
        return False, ("roster mudou depois da aprovação de %s em %s (%s); aprove de novo"
                       % (last.get("by"), last.get("ts"), "; ".join(diff) or "território/kind/reads alterados"))
    errs = roster_errors(target, team)
    if errs:
        return False, "roster aprovado por %s, mas hoje inválido (%s); corrija e aprove de novo" % (
            last.get("by"), errs[0])
    return True, "roster aprovado por %s em %s (sha %s)%s" % (last.get("by"), last.get("ts"), cur[:12],
                                                             " [simulado]" if last.get("approval") == "simulated"
                                                             else "")


# ------------------------------------------------------------------ cartões

def validate_card(card, fact_ids, kind=None, enum=None):
    """Erros de schema do cartão (team-schema.md). Lista vazia = válido."""
    errs = []
    if not isinstance(card, dict):
        return ["cartão deve ser objeto"]
    extra = sorted(set(card) - CARD_KEYS)
    if extra:
        errs.append("campos desconhecidos: %s" % extra)
    for k in ("description", "mission", "done_when"):
        if not isinstance(card.get(k), str) or not card.get(k).strip():
            errs.append("%s ausente/vazio" % k)
    if isinstance(card.get("description"), str) and len(card["description"]) > MAX_DESC:
        errs.append("description com %d > %d caracteres" % (len(card["description"]), MAX_DESC))
    for k in ITEM_LISTS:
        items = card.get(k, [])
        if not isinstance(items, list):
            errs.append("%s deve ser lista" % k)
            continue
        for i, it in enumerate(items):
            where = "%s[%d]" % (k, i)
            if not isinstance(it, dict) or not isinstance(it.get("text"), str) or not it["text"].strip():
                errs.append("%s sem text" % where)
                continue
            if k == "refuses" and not str(it.get("why", "")).strip():
                errs.append("%s: recusa sem porquê" % where)
            if "check" in it and not isinstance(it["check"], str):
                errs.append("%s: check deve ser string" % where)
            fl = it.get("facts", [])
            if not isinstance(fl, list) or not all(isinstance(x, str) for x in fl):
                errs.append("%s: facts deve ser lista de ids" % where)
                continue
            if k in FACTS_REQUIRED and not fl:
                errs.append("%s: sem facts[] (nada entra no cartão sem fato)" % where)
            if k == "knows" and fl and all(str(x).startswith("gap.") for x in fl):
                errs.append("%s: só cita lacuna (gap.*) — lacuna não é conhecimento; cite-a em refuses/footguns" % where)
            for fid in fl:
                if fid not in fact_ids:
                    errs.append("%s: fato inexistente %s" % (where, fid))
    for i, pb in enumerate(card.get("playbooks", []) if isinstance(card.get("playbooks", []), list) else [None]):
        if not isinstance(pb, dict) or not str(pb.get("title", "")).strip() or not isinstance(pb.get("steps"), list) \
                or not pb["steps"] or not all(isinstance(s, str) and s.strip() for s in pb["steps"]):
            errs.append("playbooks[%d]: precisa de title e steps (lista de strings)" % i)
    an = card.get("anchors", [])
    if not isinstance(an, list) or not all(isinstance(x, str) and x.strip() for x in an):
        errs.append("anchors deve ser lista de paths")
    if kind == "gate" and enum:
        from team.validate import _foreign_verdicts
        from team._shared_tmp.cardtext import walk_strings
        fv = _foreign_verdicts("\n".join(s for _, s in walk_strings(card)), enum)
        if fv:
            errs.append("gate cita veredito fora do veredito_enum: %s" % fv)
    return errs


def status_path(target):
    return sp_path(target, "cards", "status.json5")


def load_status(target):
    p = status_path(target)
    return read_json(p, "cards/status.json5") if os.path.isfile(p) else {}


def save_status(target, st):
    write_json(target, status_path(target), st,
               "cards/status.json5 — estado dos cartões (redigido/revisado); gerado por cs.py team card")


def resolve_input(target, path):
    """Arquivo de entrada da CLI: relativo ao ALVO (como todo outro caminho da CLI); cwd só como fallback."""
    if not path:
        raise CsError("caminho de arquivo vazio")
    p = os.path.expanduser(path)
    if os.path.isabs(p):
        return p
    at_target = os.path.join(target, p)
    if os.path.isfile(at_target) or not os.path.isfile(os.path.abspath(p)):
        return at_target
    return os.path.abspath(p)


LAYER_SCHEMA = {  # camadas que specialize.3/rt.4 mandam produzir (prompts.json5 → saida.camadas)
    "s0_core": ({"text", "facts"}, set()),
    "s2_por_caminho": ({"paths", "text", "facts"}, set()),
    "s5_memoria": ({"kind", "text", "facts"}, set()),
}
S5_KINDS = ("term", "rule", "fact")


def validate_camadas(camadas, fact_ids):
    errs = []
    if not isinstance(camadas, dict):
        return ["camadas deve ser objeto {%s}" % ", ".join(sorted(LAYER_SCHEMA))]
    extra = sorted(set(camadas) - set(LAYER_SCHEMA))
    if extra:
        errs.append("camadas: chaves desconhecidas %s" % extra)
    for k, (req, opt) in sorted(LAYER_SCHEMA.items()):
        items = camadas.get(k, [])
        if not isinstance(items, list):
            errs.append("camadas.%s deve ser lista" % k)
            continue
        for i, it in enumerate(items):
            where = "camadas.%s[%d]" % (k, i)
            if not isinstance(it, dict):
                errs.append("%s deve ser objeto com %s" % (where, sorted(req)))
                continue
            miss = sorted(req - set(it))
            if miss:
                errs.append("%s sem %s" % (where, miss))
            if not isinstance(it.get("text"), str) or not it.get("text", "").strip():
                errs.append("%s sem text" % where)
            fl = it.get("facts")
            if not isinstance(fl, list) or not fl or not all(isinstance(x, str) for x in fl):
                errs.append("%s: facts deve ser lista de ≥1 id (nada entra numa camada sem fato)" % where)
            else:
                for fid in fl:
                    if fid not in fact_ids:
                        errs.append("%s: fato inexistente %s" % (where, fid))
            if k == "s2_por_caminho" and (not isinstance(it.get("paths"), list) or not it.get("paths")
                                          or not all(isinstance(x, str) and x.strip() for x in it["paths"])):
                errs.append("%s: paths deve ser lista de globs" % where)
            if k == "s5_memoria" and it.get("kind") not in S5_KINDS:
                errs.append("%s: kind deve ser %s" % (where, "|".join(S5_KINDS)))
    return errs


def _read_card_file(path, meta=None):
    """→ (card, camadas|None). Aceita a saída inteira do subagente ({agent, card, camadas, ...}) ou só o card.
    `meta` (dict) recebe a identidade do rascunho: {draft_id, draft_at, file_sha256}."""
    if not os.path.isfile(path):
        raise CsError("arquivo do cartão ausente: %s" % path,
                      "caminho relativo é resolvido a partir do alvo (--target), não do cwd")
    raw = read_json(path, "cartão")
    camadas = None
    if meta is not None:
        d = raw.get("draft") if isinstance(raw, dict) and isinstance(raw.get("draft"), dict) else {}
        meta["draft_id"] = str(d.get("id") or (raw.get("delegation") if isinstance(raw, dict) else "") or "") or None
        meta["draft_at"] = str(d.get("at") or "") or None
        meta["mtime"] = os.path.getmtime(path)
        meta["file_sha256"] = _file_sha(path)
        meta["path"] = path
    if isinstance(raw, dict) and isinstance(raw.get("card"), dict) and "mission" not in raw:
        camadas = raw.get("camadas")
        raw = raw["card"]
    return raw, camadas


def _fact_ids(target):
    f = Facts(target, require_inventory=False)
    try:
        ids = f.index_ids()
    except CsError:
        ids = set(f.by_id)
    f.interview_invariants()
    return ids | set(f.by_id)


def _install_card(target, name, path, meta=None, guard=None, post_guard=None):
    team = load_team(target)
    ag = agent_of(team, name)
    card, camadas = _read_card_file(resolve_input(target, path), meta)
    if guard is not None:
        guard(card)
    ids = _fact_ids(target)
    errs = validate_card(card, ids, ag.get("kind"), team.get("veredito_enum"))
    if camadas is not None:
        errs += validate_camadas(camadas, ids)
    if errs:
        raise CsError("cartão de %s inválido:\n  - %s" % (name, "\n  - ".join(errs)),
                      "corrija o JSON5 devolvido pelo subagente (schema em references/team-schema.md)")
    if post_guard is not None:
        post_guard(card)
    ag["card"] = card
    if camadas is not None:  # camadas S0/S2/S5 persistem (o emissor usa S2 e S5; `team core from-panel` usa S0)
        ag["camadas"] = {k: camadas.get(k) or [] for k in sorted(LAYER_SCHEMA)}
    lay = ag.get("camadas") or {}
    used = sorted(set(ag.get("facts_used") or []) | set(
        x for k in ITEM_LISTS for it in card.get(k) or [] for x in it.get("facts") or []) | set(
        x for k in LAYER_SCHEMA for it in lay.get(k) or [] for x in it.get("facts") or []))
    ag["facts_used"] = used
    save_team(target, team)
    return card


def _older(meta, prev):
    """Rascunho novo é MAIS VELHO que o registrado? (iteração 2: redator atrasado sobrescreveu o rascunho
    depois do `card set`). Compara `draft.at` (ISO, do próprio rascunho) quando os dois têm; senão o mtime."""
    if not prev:
        return False
    if meta.get("draft_at") and prev.get("draft_at"):
        return meta["draft_at"] < prev["draft_at"]
    if meta.get("mtime") is not None and prev.get("draft_mtime") is not None:
        return meta["mtime"] + 1e-6 < float(prev["draft_mtime"])
    return False


def card_set(target, name, path, by="subagente", force=False):
    """Grava o cartão (specialize.3). Registra a identidade do rascunho (hash do arquivo, `draft.id` = id da
    delegação, `draft.at`) e RECUSA rascunho mais velho que o já registrado — salvo `--force` (revisão humana
    consciente). Mesmo arquivo de novo = idempotente."""
    st = load_status(target)
    prev = (st.get(name) or {}).get("drafted")
    meta = {}

    def guard(card):
        if prev and prev.get("file_sha256") and prev["file_sha256"] == meta.get("file_sha256"):
            return
        if not force and _older(meta, prev):
            raise CsError("rascunho de %s é MAIS VELHO que o registrado (%s, delegação %s): nada foi gravado"
                          % (name, prev.get("draft_at") or prev.get("at"), prev.get("draft_id") or "?"),
                          "redator atrasado/duplicado? confira `team card-status`; para gravar mesmo assim, --force")
    card = _install_card(target, name, path, meta, guard)
    st = load_status(target)
    st.setdefault(name, {})["drafted"] = {"at": cslog.now_iso(), "sha256": _sha(card), "by": by,
                                          "file_sha256": meta.get("file_sha256"), "draft_id": meta.get("draft_id"),
                                          "draft_at": meta.get("draft_at"), "draft_mtime": meta.get("mtime"),
                                          "file": os.path.relpath(meta["path"], target) if meta.get("path") else None}
    for k in ("revised", "refines", "existence_fixes"):
        st[name].pop(k, None)
    save_status(target, st)
    return st[name]


def panel_file(target, name):
    return sp_path(target, "panel", "%s.json5" % name)


def _existence_missing(target, team, name):
    """Faltas de existência (G2) do cartão de `name` no `team` dado — mesmo classificador do `probes existence`:
    caminho/símbolo/glob inexistente ou comando fora de operations.json5 (verified) sem `[unverified]`."""
    from probes.existence import existence_report
    return (existence_report(target, team)["agents"].get(name) or {}).get("missing") or []


def _fmt_missing(miss, limit=6):
    return "\n  - ".join("%s %s `%s` (%s)" % (m.get("where", "?"), m.get("type"), m.get("value"), m.get("why"))
                         for m in miss[:limit]) + ("\n  - … +%d" % (len(miss) - limit) if len(miss) > limit else "")


def latest_revision(status):
    """Registro de revisão MAIS RECENTE entre `revised` (mesa redonda), `refines[]` (validate.4) e
    `existence_fixes[]` — iteração 3: card-status comparava com refines[-1] e acusava "mudou depois da revisão"
    depois de uma revisão de mesa redonda posterior ao refino. Ordem: `seq` (gravado desde a iteração 4), depois `at`."""
    recs = []
    if status.get("revised"):
        recs.append(status["revised"])
    recs += list(status.get("refines") or []) + list(status.get("existence_fixes") or [])
    if not recs:
        return None
    return max(enumerate(recs), key=lambda ir: (ir[1].get("seq", -1), str(ir[1].get("at") or ""), ir[0]))[1]


def card_revise(target, name, path=None, note=""):
    """Revisão do autor (rt.4) ou do refino (validate.4). Iteração 4: a revisão roda o `probes existence` no
    cartão NOVO e recusa referência inexistente / comando sem `[unverified]` (nada é gravado). Quando a revisão
    está travada (já revisou para este painel e nenhum exame reprovado libera outra — ex.: reexame APROVADO), ela
    ainda é aceita como CONSERTO DE EXISTÊNCIA: o cartão atual tem falta de existência e o novo (`--file`) zera."""
    team = load_team(target)
    ag = agent_of(team, name)
    st = load_status(target)
    if not (st.get(name) or {}).get("drafted"):
        raise CsError("%s sem cartão redigido" % name, "rode `cs.py team card set %s --file card.json5`" % name)
    psha = _file_sha(panel_file(target, name))
    rev = st[name].get("revised")
    refine = None
    fix = False
    if psha is None:
        # iteração 5 (ts-shop --fast): sem mesa redonda não há painel, e o conserto de existência que o check de
        # existência (todos os modos) devolve ao autor era recusado aqui. Conserto de existência (`--file` que
        # zera as faltas do cartão ATUAL) não depende de painel; a revisão do autor (rt.4) continua exigindo um.
        # cobaia .NET (--fast com refino liberado): exame reprovado libera a revisão do refino mesmo sem painel
        refine = refine_slot(target, name, st[name])
        cur_miss = _existence_missing(target, team, name) if (path and ag.get("card")) else []
        if refine is None and not cur_miss:
            raise CsError("painel de %s não consolidado (.swarm/panel/%s.json5)" % (name, name),
                          "rode `cs.py panel consolidate` antes da revisão do autor; sem painel só vale o conserto "
                          "de existência (`--file` com o cartão que zera as citações inexistentes do cartão atual)")
        fix = refine is None
    elif rev and rev.get("panel_sha256") == psha:
        refine = refine_slot(target, name, st[name])
        if refine is None:
            cur_miss = _existence_missing(target, team, name) if ag.get("card") else []
            if not (path and cur_miss):
                raise CsError("%s já revisou uma vez para este painel" % name,
                              "a revisão é única por consolidação (mesa redonda); no refino (validate.4) ela é "
                              "liberada depois de cada exame reprovado; conserto de existência (`--file` com o "
                              "cartão que zera as citações inexistentes) é aceito a qualquer momento"
                              + ("" if not cur_miss else " — passe --file"))
            fix = True
    if path:
        def check_existence(card):
            t2 = json.loads(json.dumps(team))
            agent_of(t2, name)["card"] = card
            miss = _existence_missing(target, t2, name)
            if miss:
                raise CsError("revisão de %s recusada: %d citação(ões) inexistente(s) ou comando sem [unverified] "
                              "(nada foi gravado):\n  - %s" % (name, len(miss), _fmt_missing(miss)),
                              "corrija o cartão (caminho real; comando verified em operations.json5 ou marque "
                              "`[unverified]`) e rode `team card revise` de novo — a revisão continua disponível")
        card = _install_card(target, name, path, post_guard=check_existence)
    else:
        if not (note or "").strip():
            raise CsError("revisão sem mudança exige --note com o porquê")
        card = ag.get("card")
        if not card:
            raise CsError("%s sem cartão no team.json5" % name)
        miss = _existence_missing(target, team, name)
        if miss:
            raise CsError("revisão sem mudança de %s recusada: o cartão cita %d referência(s) inexistente(s) ou "
                          "comando sem [unverified]:\n  - %s" % (name, len(miss), _fmt_missing(miss)),
                          "revise com --file e o cartão corrigido")
    seq = 1 + max([r.get("seq", 0) for r in ([st[name].get("revised") or {}] + list(st[name].get("refines") or [])
                                             + list(st[name].get("existence_fixes") or []))] or [0])
    rec = {"at": cslog.now_iso(), "sha256": _sha(card), "panel_sha256": psha, "note": (note or "").strip(),
           "changed": bool(path), "seq": seq}
    if fix:  # conserto de existência fora do ciclo: não consome nem libera revisão
        rec["existence_fix"] = True
        st[name].setdefault("existence_fixes", []).append(rec)
    elif refine is not None:  # revisão do refino: não apaga a da mesa redonda; o cartão atual é o do refino
        rec["cycle"] = refine
        st[name].setdefault("refines", []).append(rec)
    else:
        st[name]["revised"] = rec
    save_status(target, st)
    st[name]["last"] = rec
    return st[name]


def refine_slot(target, name, status):
    """Refino (validate.4): cada exame REPROVADO registrado em probes/cycles.json5 libera UMA revisão.
    → nº do ciclo reprovado ainda sem revisão, ou None."""
    p = sp_path(target, "probes", "cycles.json5")
    if not os.path.isfile(p):
        return None
    cyc = read_json(p, "probes/cycles.json5").get(name) or []
    failed = [i + 1 for i, c in enumerate(cyc) if c.get("decision") != "PASS"]
    done = set(r.get("cycle") for r in status.get("refines") or [])
    pend = [n for n in failed if n not in done]
    return pend[-1] if pend else None


def cited_facts(ag, card_only=False):
    card = ag.get("card") or {}
    lay = {} if card_only else (ag.get("camadas") or {})
    return sorted(set(x for k in ITEM_LISTS for it in card.get(k) or [] if isinstance(it, dict)
                      for x in it.get("facts") or []) |
                  set(x for k in LAYER_SCHEMA for it in lay.get(k) or [] if isinstance(it, dict)
                      for x in it.get("facts") or []))


def card_status(target):
    """→ [{agent, drafted, revised, problems_drafted[], problems_revised[]}]."""
    team = load_team(target)
    st = load_status(target)
    ids = _fact_ids(target)
    rows = []
    try:  # rt.4 (efeito): a revisão do autor tem de zerar as faltas de existência do cartão
        from probes.existence import existence_report
        exist = existence_report(target, team)["agents"]
    except Exception:  # sem fatos/inventário: o check de existência (rt.2) acusa
        exist = {}
    for ag in team.get("agents") or []:
        n = ag.get("name")
        s = st.get(n) or {}
        card = ag.get("card")
        pd, pr = [], []
        cur = _sha(card) if card else None
        if not card:
            pd.append("sem cartão")
        else:
            errs = validate_card(card, ids, ag.get("kind"), team.get("veredito_enum"))
            if errs:
                pd.append("cartão inválido: %s" % errs[0])
        if not s.get("drafted"):
            pd.append("não registrado por `team card set`")
        elif card and cur not in (s["drafted"].get("sha256"), (latest_revision(s) or {}).get("sha256")):
            pd.append("cartão alterado fora de `team card set|revise`")
        if card and not cited_facts(ag, card_only=True):
            pd.append("cartão não cita nenhum fato (specialize.3 escreve SÓ a partir de fatos)")
        rev = s.get("revised")
        if not rev:
            pr.append("sem revisão do autor (`team card revise`)")
        else:
            last = latest_revision(s) or rev
            psha = _file_sha(panel_file(target, n))
            if psha is None:
                pr.append("painel consolidado ausente")
            elif psha != last.get("panel_sha256"):
                pr.append("painel re-consolidado depois da revisão")
            if card and cur != last.get("sha256"):
                pr.append("cartão mudou depois da revisão")
            miss = (exist.get(n) or {}).get("missing") or []
            if miss:
                pr.append("revisado mas com %d citação(ões) inexistente(s) (ex.: %s `%s`)" % (
                    len(miss), miss[0]["type"], miss[0]["value"]))
        rows.append({"agent": n, "drafted": not pd, "revised": not pd and not pr,
                     "problems_drafted": pd, "problems_revised": pd + pr})
    return rows
