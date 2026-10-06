"""Renderização por camada de steering (ARCHITECTURE §8-ter), neutra de plataforma.

S0 núcleo (≤40) · S1 cartão (≤80) · S2 por território (≤60) · S4 playbooks (sem limite).
Fonte única: cada item aparece numa só camada; as outras apontam.
Conteúdo: sem persona; só o que está em team.json/facts (com evidência); regra com o comando que a
prova; recusa com porquê; veredito só do veredito_enum.
"""
import re

from emit.common import EmitError, one_line, template
from emit.team import veredito_enum

BUDGET = {"S0": 40, "S1": 80, "S2": 60, "ORCH": 80, "SESSION": 15, "CMD": 25, "STATE": 40}
TOP_N = (5, 4, 3, 2, 1)  # termos/regras de negócio no S1: maior N que cabe no orçamento


def count_lines(text):
    """Linhas que custam contexto: não vazias e que não são comentário HTML de linha inteira."""
    n = 0
    for line in text.split("\n"):
        s = line.strip()
        if not s or (s.startswith("<!--") and s.endswith("-->")):
            continue
        n += 1
    return n


class BudgetError(EmitError):
    pass


def _fact_ref(item):
    """Ids de fato NÃO vão para o Markdown emitido: `hist.fix.<sha>` entrega o gabarito da sonda de história e
    o anti-cola da própria skill reprovava o cartão (iteração 1: 205 violações). O id fica em team.json5."""
    return ""


_LINE_REF = re.compile(r"((?:[\w.@-]+/)*[\w@-][\w.@-]*\.[A-Za-z0-9]{1,8}|Makefile|Dockerfile|Jenkinsfile)"
                       r"(?::\d+(?:-\d+)?|#L\d+(?:-L?\d+)?)")
_SHA = re.compile(r"\b(?=[0-9a-f]*[0-9])(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}\b")


def no_answer_keys(text):
    """Tira do texto emitido o que é resposta de sonda: `arquivo:linha` (fica só o arquivo) e sha de commit."""
    t = _LINE_REF.sub(r"\1", str(text))
    return _SHA.sub("(commit)", t)


def _clean(text):
    return no_answer_keys(one_line(text))


def _code(glob):
    return "`%s`" % glob


def section(title, lines):
    if not lines:
        return ""
    return "## %s\n\n%s" % (title, "\n".join(lines))


def join_sections(parts):
    return "\n\n".join(p for p in parts if p)


# ------------------------------------------------------------------ peças

def territory_lines(agent):
    out = []
    terr = agent.get("territory") or []
    if terr:
        out.append("- Escreve somente em: %s" % ", ".join(_code(g) for g in terr))
    else:
        out.append("- Sem território de escrita (não edita arquivos do produto).")
    if agent.get("reads"):
        out.append("- Lê também: %s" % ", ".join(_code(g) for g in agent["reads"]))
    return out


def knows_lines(card):
    return ["- %s%s" % (_clean(k["text"]), _fact_ref(k)) for k in card.get("knows") or []]


def _strip_neg(text):
    low = text.lower()
    for prefix in ("nunca ", "não ", "nao "):
        if low.startswith(prefix):
            return text[len(prefix):]
    return text[0].lower() + text[1:] if text else text


def refuses_lines(card):
    return ["- Não %s — porque %s%s" % (_strip_neg(_clean(r["text"])), _clean(r["why"]), _fact_ref(r))
            for r in card.get("refuses") or []]


def rules_lines(card):
    out = []
    for r in card.get("rules") or []:
        line = "- %s" % _clean(r["text"])
        if r.get("check"):
            line += " — prova: `%s`" % one_line(r["check"])
        out.append(line + _fact_ref(r))
    return out


def footgun_lines(card):
    return ["- %s%s" % (_clean(f["text"]), _fact_ref(f)) for f in card.get("footguns") or []]


# Prioridade de invariante no cartão de quem não tem território (gates, qa, po): decisão registrada
# (ADR, entrevista) > proibição > regra de negócio > configuração. O resto fica no team.json5 e na memória.
INV_PRIORITY = ("rat.", "interview.", "interp.", "rules.never", "brule.", "rules.")
INV_TOP = (None, 12, 8, 5, 3)  # None = todas; o S1 tenta do maior para o menor


def _inv_rank(fid):
    for i, p in enumerate(INV_PRIORITY):
        if fid.startswith(p):
            return i
    return len(INV_PRIORITY)


def invariant_lines(agent, facts, limit=None):
    ids = [f for f in agent.get("invariants") or [] if facts.get(f)]
    if limit is not None:
        ids = sorted(ids, key=_inv_rank)[:limit]  # sort estável: mantém a ordem original dentro da classe
    return ["- %s" % _clean(facts[f]) for f in ids]


INV_CLASS = ("decisão (ADR)", "entrevista", "interpretação conferida", "proibição", "regra de negócio", "regra")


def invariants_path(name):
    return ".swarm/knowledge/invariants/%s.json5" % name


def invariants_data(agent, facts):
    """Lista COMPLETA e priorizada dos invariantes do agente (contrato `invariantes_gate`): o gate não cabe no
    S1 com todos; o cartão mostra o topo e aponta este arquivo. Sem `arquivo:linha`/sha (anti-cola)."""
    ids = sorted((f for f in agent.get("invariants") or [] if facts.get(f)), key=_inv_rank)
    return {"schema_version": 1, "agent": agent["name"], "total": len(ids),
            "order": "decisão registrada > entrevista > proibição > regra de negócio > configuração",
            "invariants": [{"rank": i + 1, "class": INV_CLASS[min(_inv_rank(f), len(INV_CLASS) - 1)],
                            "text": no_answer_keys(one_line(facts[f]))} for i, f in enumerate(ids)]}


def invariant_count(agent, facts):
    return sum(1 for f in agent.get("invariants") or [] if facts.get(f))


def _path_only(loc):
    return no_answer_keys(str(loc).split(":")[0])


def term_line(t):
    line = "- `%s`" % t["canonical"]
    if t["definition"]:
        line += " — %s" % _clean(t["definition"])
    if t["locations"]:
        line += " (em `%s`)" % _path_only(t["locations"][0])
    if t["never"]:
        line += "; nunca: %s" % ", ".join("`%s`" % v for v in t["never"])
    return line


def brule_line(r):
    line = "- %s" % _clean(r["text"])
    if r["locations"]:
        line += " — imposta em `%s`" % _path_only(r["locations"][0])
    ex = r.get("exercised_by")
    if isinstance(ex, list):
        ex = ex[0] if ex else None
    cov = r.get("coverage")
    if r["test"]:
        line += " — teste: `%s`" % _path_only(r["test"])
    elif ex and cov in ("exercised", "message", "exception", "reference", None):
        line += " — exercitada por `%s` (sem assert direto)" % _path_only(ex)
    elif cov == "undetermined":
        line += " — cobertura indeterminada"
    else:
        line += " — sem teste"
    if r["source"] == "founder":
        line += " (dono)"
    return line


def playbook_lines(card):
    out = []
    for pb in card.get("playbooks") or []:
        if out:
            out.append("")
        out.append("## %s" % one_line(pb["title"]))
        out.append("")
        for i, step in enumerate(pb.get("steps") or [], start=1):
            out.append("%d. %s" % (i, one_line(step)))
    return out


def verdict_lines(team, agent):
    if agent["kind"] != "gate":
        return []
    out = ["Emita exatamente um veredito: %s. Qualquer outro valor é inválido."
           % " | ".join("`%s`" % v for v in veredito_enum(team)),
           "",
           "Precedência entre gates sobre os mesmos caminhos: qualquer `FAIL` vence (a entrega volta com os "
           "achados); `NEEDS_SPECIALIST` roteia para o gate especialista citado nos achados e trava o aceite até o "
           "veredito dele; só sem FAIL e sem NEEDS_SPECIALIST em aberto vale `PASS`."]
    if agent.get("gate_scope") == "security" or agent["name"] == "security":
        out.append("Escopo: julgue só regras de segurança (segredos, autenticação, injeção, permissões, "
                   "dependências vulneráveis); o resto é do outro gate.")
    return out


def search_globs(agent):
    return ",".join(agent.get("territory") or agent.get("reads") or ["**"])


# ------------------------------------------------------------------ S0

def agent_map_lines(team, s1_pointer):
    out = []
    for ag in team["agents"]:
        terr = ", ".join(_code(g) for g in ag.get("territory") or []) or "sem escrita"
        out.append("- `%s` (%s; %s): %s%s" % (ag["name"], ag["kind"], terr,
                                             one_line(ag["card"]["description"]),
                                             (" → `%s`" % s1_pointer.format(n=ag["name"])) if s1_pointer else ""))
    out.append("- Vereditos de gate: %s." % " | ".join("`%s`" % v for v in veredito_enum(team)))
    return out


# Linhas operacionais do S0: versão "native" (Claude Code, com comandos /x) e "terminal" (demais plataformas).
S0_LINES = {
    "session": {
        "native": "Sessão: `/save-session` ao parar e `/load-session` ao retomar (chamam `.swarm/bin/cs-session`; "
                  "não leia arquivos de estado).",
        "terminal": "Sessão: ao parar, `.swarm/bin/cs-session save --did \"<feito>\" --next \"<próximo>\" "
                    "[--blocked \"<bloqueio>\"]`; ao retomar, `.swarm/bin/cs-session load`. Não leia arquivos de estado."},
    "autonomy": {
        "native": "Modo autônomo: `/feature-autonoma <id> <spec>` conduz a aprovação única e inicia o mandato.",
        "terminal": "Modo autônomo: após UMA aprovação do usuário (spec, testes de aceite vermelhos, classe, "
                    "orçamento), `.swarm/bin/cs-state autonomy start --feature <id> --spec <arquivo> --budget "
                    "tasks=N,attempts=2,minutes=M`; depois `.swarm/bin/cs-state next` até REPORTING."},
    "process": {
        "native": "Processo: Épico → Feature → Sprint → Story (US|Bug|Fix) via `.swarm/bin/cs-state add ...`; "
                  "`.swarm/bin/cs-state board` mostra a árvore; `/plan-sprint` planeja a sprint.",
        "terminal": "Processo: Épico → Feature → Sprint → Story (US|Bug|Fix) via `.swarm/bin/cs-state add ...`; "
                    "`.swarm/bin/cs-state board` mostra a árvore; `.swarm/bin/cs-state sprint plan --goal \"<meta>\" --budget <n> "
                    "--stories <ids>` planeja a sprint."},
    "routing": {
        "native": "Modelo por despacho: passe o `model` de `.swarm/bin/cs-route recommend <id>` (o hook bloqueia despacho "
                  "sem model); discordou, `.swarm/bin/cs-route override <id> --model X --reason \"...\"`.",
        "terminal": "Modelo: antes de delegar, `.swarm/bin/cs-route recommend <id>` diz o tier mais barato que resolve; use-o "
                    "no agente/modo escolhido ou registre `.swarm/bin/cs-route override <id> --model X --reason \"...\"`."},
    "correction": {
        "native": "Usuário corrigiu um agente: `/correct` antes de seguir.",
        "terminal": "Usuário corrigiu um agente: `.swarm/bin/cs-mem correct --agent X --wrong \"...\" --right \"...\" "
                    "--why \"...\"` antes de seguir."},
}
ORCH_INLINE = "Agente principal: o kernel do orquestrador vem logo abaixo deste núcleo; subagente: ignore-o."


def orch_pointer(path):
    return ("Agente principal: siga o kernel do orquestrador em `%s` (entra no início da sessão; se não "
            "estiver no seu contexto, leia-o agora). Subagente: ignore-o." % path)


def s0_block(team, s1_pointer=None, flavor="terminal", orchestrator_line=ORCH_INLINE):
    core = "\n".join("- %s" % _clean(l["text"]) for l in team["core"]["lines"])
    lines = {"%s_line" % k: v[flavor] for k, v in S0_LINES.items()}
    return template("core-block.md", core=core, agent_map="\n".join(agent_map_lines(team, s1_pointer)),
                    orchestrator_line=orchestrator_line, **lines)


def s0_fit(team, s1_pointer=None, flavor="terminal", orchestrator_line=ORCH_INLINE):
    body = s0_block(team, s1_pointer, flavor, orchestrator_line)
    n = count_lines(body)
    if n > BUDGET["S0"]:
        raise BudgetError(
            "S0 núcleo: %d linhas > %d (core.lines=%d + mapa de %d agentes + linhas operacionais). Mova linhas "
            "de core que valem para um território só para S2 (rules/footguns do agente dono)."
            % (n, BUDGET["S0"], len(team["core"]["lines"]), len(team["agents"])))
    return body


# ------------------------------------------------------------------ S1

def s1_card(team, agent, kn, pointers, n, n_inv=None):
    """pointers: {'s2': str|None, 's4': str|None}. n: top-N de termos e de regras de negócio.
    n_inv: máximo de invariantes no cartão de agente sem território (None = todas)."""
    card = agent["card"]
    globs = agent.get("territory") or []
    terms, n_terms = kn.terms_for(globs, n)
    brules, n_brules = kn.rules_for(globs, n)
    no_terr = not globs
    rest = []
    if pointers.get("s2"):
        rest.append("- Invariantes, convenções, armadilhas e o restante dos termos/regras do território: "
                    "`%s` (carrega ao tocar arquivos do território)." % pointers["s2"])
    if pointers.get("s4"):
        titles = "; ".join(one_line(p["title"]) for p in card.get("playbooks") or [])
        rest.append("- Playbooks (%s): leia `%s` antes de executar." % (titles, pointers["s4"]))
    if card.get("anchors"):
        rest.append("- Âncoras: %s" % ", ".join("`%s`" % a for a in card["anchors"]))
    fatia = (" (sua fatia: nós com `owner: \"%s\"`)" % agent["name"]) if globs else ""
    rest.append("- Mapas (JSON5, sob demanda) em `.swarm/knowledge/`: `tree.json5`%s, `deps.json5`, "
                "`collision.json5`, `stack.json5`." % fatia)
    total_inv = invariant_count(agent, kn.facts) if no_terr else 0
    if no_terr and n_inv is not None and total_inv > n_inv:
        rest.append("- Mais %d invariante(s): lista completa e priorizada em `%s` — leia antes do veredito."
                    % (total_inv - n_inv, invariants_path(agent["name"])))
    if n_terms > len(terms) or n_brules > len(brules):
        rest.append("- Mais %d termo(s) e %d regra(s) de negócio: `.swarm/bin/cs-mem search \"<termo>\" --kind term|rule "
                    "--paths \"%s\"`." % (n_terms - len(terms), n_brules - len(brules), search_globs(agent)))
    sections = join_sections([
        section("Território", territory_lines(agent)),
        section("Fatos deste repositório", knows_lines(card)),
        section("Termos do domínio", [term_line(t) for t in terms]),
        section("Regras de negócio do território", [brule_line(r) for r in brules]),
        section("Invariantes", invariant_lines(agent, kn.facts, n_inv)) if no_terr else "",
        section("Regras", rules_lines(card)) if no_terr else "",
        section("Armadilhas registradas", footgun_lines(card)) if no_terr else "",
        section("Recusas", refuses_lines(card)),
        section("Feito quando", ["- %s" % one_line(card["done_when"])]),
        section("Veredito", verdict_lines(team, agent)),
        section("Como escrever cada tipo de story", [template("product-process.md").strip("\n")])
        if agent["kind"] == "product" else "",
        section("Onde está o resto", rest),
        section("Memória e autocorreção", [template("memory.md", paths=search_globs(agent),
                                                    agent=agent["name"]).strip("\n")]),
    ])
    body = template("card.md", name=agent["name"], mission=one_line(card["mission"]), sections=sections)
    return body.rstrip("\n") + "\n", {t["canonical"] for t in terms}, {r["text"] for r in brules}


def s1_fit(team, agent, kn, pointers):
    """Maior top-N que cabe em S1; senão BudgetError com sugestão."""
    last = None
    inv_steps = INV_TOP if not (agent.get("territory") or []) else (None,)
    for n_inv in inv_steps:  # primeiro corta invariantes do gate (ficam na memória), depois termos/regras
        for n in TOP_N:
            body, shown_t, shown_r = s1_card(team, agent, kn, pointers, n, n_inv)
            last = count_lines(body)
            if last <= BUDGET["S1"]:
                return body, shown_t, shown_r
    raise BudgetError(
        "S1 cartão de %r: %d linhas > %d mesmo com top-1 termo/regra e top-3 invariantes. Mova `knows` longos para S2 "
        "(rules/footguns do território), playbooks para S4, ou encurte recusas." % (agent["name"], last, BUDGET["S1"]))


# ------------------------------------------------------------------ S2

def s2_sections(agent, kn, shown_t, shown_r, room, n_inv=None):
    """Seções do território. A parte escrita à mão precisa caber; termos/regras restantes preenchem `room`.
    `n_inv` corta os invariantes no top-N por rank; o resto fica no arquivo de invariantes (S5)."""
    card = agent["card"]
    inv = invariant_lines(agent, kn.facts, n_inv)
    total_inv = invariant_count(agent, kn.facts)
    if n_inv is not None and total_inv > n_inv:
        inv.append("- Mais %d invariante(s): lista completa e priorizada em `%s`."
                   % (total_inv - n_inv, invariants_path(agent["name"])))
    hand = [section("Invariantes", inv),
            section("Convenções e regras técnicas", rules_lines(card)),
            section("Armadilhas registradas", footgun_lines(card)),
            section("Notas por caminho", path_note_lines(agent))]
    globs = agent.get("territory") or []
    terms, _ = kn.terms_for(globs, 10 ** 6)
    brules, _ = kn.rules_for(globs, 10 ** 6)
    terms = [t for t in terms if t["canonical"] not in shown_t]
    brules = [r for r in brules if r["text"] not in shown_r]
    used = count_lines(join_sections(hand))
    t_lines, r_lines, left = [], [], room - used - 3  # 2 títulos + 1 ponteiro
    for t in terms:
        if left <= 0:
            break
        t_lines.append(term_line(t))
        left -= 1
    for r in brules:
        if left <= 0:
            break
        r_lines.append(brule_line(r))
        left -= 1
    omitted = len(terms) - len(t_lines) + len(brules) - len(r_lines)
    extra = [section("Termos do domínio (além do cartão do dono)", t_lines),
             section("Regras de negócio (além do cartão do dono)", r_lines)]
    if omitted:
        extra.append("- Mais %d termo(s)/regra(s): `.swarm/bin/cs-mem search \"<consulta>\" --kind term|rule --paths \"%s\"`."
                     % (omitted, search_globs(agent)))
    return join_sections(hand + extra), used


def s2_fit(agent, kn, shown_t, shown_r, room):
    """Maior top-N de invariantes que cabe em `room` (como o S1 do gate); devolve a última tentativa se nada cabe."""
    for n_inv in INV_TOP:
        secs, used = s2_sections(agent, kn, shown_t, shown_r, room, n_inv)
        if used <= room:
            break
    return secs, used


def path_note_lines(agent):
    """camadas.s2_por_caminho do cartão (specialize.3): o que vale para quem toca um diretório."""
    out = []
    for it in (agent.get("camadas") or {}).get("s2_por_caminho") or []:
        paths = ", ".join("`%s`" % p for p in it.get("paths") or [])
        out.append("- %s%s" % (("%s: " % paths) if paths else "", _clean(it.get("text", ""))))
    return out


def s5_items(team):
    """camadas.s5_memoria de todos os cartões → dado para `cs-mem search` (S5)."""
    items = []
    for ag in team.get("agents") or []:
        globs = ag.get("territory") or []
        for i, it in enumerate((ag.get("camadas") or {}).get("s5_memoria") or []):
            items.append({"id": "s5.%s.%d" % (ag["name"], i + 1), "agent": ag["name"],
                          "kind": it.get("kind") or "fact", "text": one_line(it.get("text", "")),
                          "scope": list(globs), "facts": list(it.get("facts") or [])})
    return items


def s2_body(team, agent, kn, shown_t, shown_r):
    head = template("territory-rule.md", name=agent["name"], kind=agent["kind"],
                    delegate="Mudança aqui respeita o que segue; o cartão do dono tem missão e recusas.",
                    sections="")
    room = BUDGET["S2"] - count_lines(head)
    secs, used = s2_fit(agent, kn, shown_t, shown_r, room)
    if used > room:
        raise BudgetError(
            "S2 território de %r: invariantes+regras+armadilhas somam %d linhas > %d. Mova armadilhas antigas "
            "para a memória (S5, `.swarm/bin/cs-mem add --kind lesson`) ou procedimentos para playbooks (S4)."
            % (agent["name"], used, room))
    body = (head.rstrip("\n") + "\n\n" + secs).rstrip("\n") + "\n"
    return body


def nested_block(team, agents, kn, shown):
    head = template("nested-agents-md-block.md", sections="")
    parts = []
    room = BUDGET["S2"] - count_lines(head)
    per = max(1, room // len(agents))
    for ag in agents:
        st, sr = shown[ag["name"]]
        title = "### Dono: `%s` (%s)" % (ag["name"], ag["kind"])
        secs, used = s2_fit(ag, kn, st, sr, per - 1)
        if used > per - 1:
            raise BudgetError("S2 AGENTS.md aninhado de %r: %d linhas > %d" % (ag["name"], used, per - 1))
        parts.append(title + "\n\n" + re.sub(r"(?m)^## ", "#### ", secs))
    return template("nested-agents-md-block.md", sections="\n\n".join(parts))


# ------------------------------------------------------------------ S4

def s2_data(agent, kn, shown_t, shown_r):
    """S2 como dado (JSON5) para plataformas sem regra por caminho nativa que caiba no glob."""
    card = agent["card"]
    globs = agent.get("territory") or []
    terms, _ = kn.terms_for(globs, 10 ** 6)
    brules, _ = kn.rules_for(globs, 10 ** 6)
    return {
        "agent": agent["name"], "territory": list(globs),
        "invariants": [{"text": no_answer_keys(kn.facts.get(f, ""))} for f in agent.get("invariants") or []
                       if kn.facts.get(f)],
        "rules": [{k: (no_answer_keys(r[k]) if k == "text" else r[k]) for k in ("text", "check") if r.get(k)}
                  for r in card.get("rules") or []],
        "footguns": [{"text": no_answer_keys(f["text"])} for f in card.get("footguns") or []],
        "path_notes": [{"paths": list(it.get("paths") or []), "text": no_answer_keys(it.get("text", ""))}
                       for it in (agent.get("camadas") or {}).get("s2_por_caminho") or []],
        "terms": [{"canonical": t["canonical"], "definition": no_answer_keys(t["definition"]),
                   "where": [_path_only(x) for x in t["locations"][:1]],
                   "never": t["never"]} for t in terms if t["canonical"] not in shown_t],
        "business_rules": [{"text": no_answer_keys(r["text"]), "where": [_path_only(x) for x in r["locations"][:1]],
                            "test": _path_only(r["test"]) if r["test"] else None}
                           for r in brules if r["text"] not in shown_r],
    }


def s4_playbooks(agent):
    return template("playbooks-skill.md", name=agent["name"],
                    sections="\n".join(playbook_lines(agent["card"]))).rstrip("\n") + "\n"


def has_playbooks(agent):
    return bool(agent["card"].get("playbooks"))


# ------------------------------------------------------------------ kernel do orquestrador

def orchestrator_kernel(team):
    ags = [a for a in team["agents"] if a.get("territory")]
    devs = [a for a in ags if a["kind"] == "dev"] or ags or team["agents"]
    ex = devs[0]
    path = (ex.get("territory") or ex.get("reads") or ["<caminho>"])[0]
    body = template("orchestrator.md", veredito=" | ".join("`%s`" % v for v in veredito_enum(team)),
                    example_agent=ex["name"], example_path=path).rstrip("\n") + "\n"
    n = count_lines(body)
    if n > BUDGET["ORCH"]:
        raise BudgetError("kernel do orquestrador: %d linhas > %d; detalhe de gate vai para "
                          "references/harness.md, não para o kernel." % (n, BUDGET["ORCH"]))
    return body
