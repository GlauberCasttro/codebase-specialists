"""`cs.py emit budget` — confere os orçamentos de camada (S0 ≤40, S1 ≤80, S2 ≤60, kernel ≤80, sessão ≤15,
comandos ≤25) a partir do team.json5, renderizando em memória com o mesmo emissor. Não escreve nada.

Limites: render.BUDGET (fonte única). Medida: render.count_lines sobre o corpo de cada artefato (sem
frontmatter/marcador), exatamente como `emit validate` mede no disco.
"""
from emit import knowledge, platforms as P, render, validate as V
from emit.team import load_team, resolve_invariants


def check_budget(root, plats):
    """→ {ok, errors[], layers: {camada: {limit, max, worst}}}. EmitError (entrada inválida) propaga."""
    team = load_team(root)
    kn = knowledge.load(root)
    resolve_invariants(team, kn.facts)
    rep = V.Report()
    layers = {}
    pre = _all_overflows(team, kn)  # iteração 1: um estouro por vez custava uma volta por agente
    if pre:
        return {"ok": False, "errors": pre, "layers": layers}
    try:
        arts = P.build(team, kn, root, plats)
    except render.BudgetError as exc:
        return {"ok": False, "errors": [str(exc)], "layers": layers}
    agents = {a["name"]: a for a in team["agents"]}
    for art in arts:
        if art.mode == P.BLOCK:
            chunks = V._layer_text(art, art.content.strip("\n"))
        else:
            checker = V.CHECKERS.get(art.kind)
            body = checker(V.Report(), art, art.content, team, agents.get(art.agent)) if checker else None
            if body is None:
                continue
            chunks = [(art.layer, body)]
        for layer, text in chunks:
            limit = render.BUDGET.get(layer)
            if limit is None:
                continue
            n = render.count_lines(text)
            cur = layers.setdefault(layer, {"limit": limit, "max": 0, "worst": None})
            if n > cur["max"]:
                cur["max"], cur["worst"] = n, art.path
            V._budget(rep, art.path, layer, text)
    return {"ok": rep.ok, "errors": rep.errors, "layers": layers}


def _all_overflows(team, kn):
    """Mede S0, S1 e S2 de TODOS os agentes de uma vez (mesmo renderizador) e devolve todos os estouros."""
    errs = []
    try:
        render.s0_fit(team, ".claude/agents/{n}.md", "native", render.orch_pointer(P.ORCH_CLAUDE))
    except render.BudgetError as exc:
        errs.append(str(exc))
    for ag in team["agents"]:
        pointers = {"s2": "s2" if ag.get("territory") else None, "s4": "s4" if render.has_playbooks(ag) else None}
        try:
            _, st, sr = render.s1_fit(team, ag, kn, pointers)
        except render.BudgetError as exc:
            errs.append(str(exc))
            continue
        if ag.get("territory"):
            try:
                render.s2_body(team, ag, kn, st, sr)
            except render.BudgetError as exc:
                errs.append(str(exc))
    return errs
