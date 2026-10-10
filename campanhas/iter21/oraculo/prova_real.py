"""PROVA REAL campanha-iter21 — "corrigir e não esquecer", com o Claude Code de verdade (`claude -p` headless).

Camada COMPORTAMENTAL do oráculo (a mecânica é o test_iter21.py). Gera um alvo do domínio inventado (estufa) com a
skill sob teste ($CS_SKILL_DIR; padrão = raiz do projeto), prepara cada task pelo motor do alvo (cs-state, sem LLM),
e pede a um `claude -p` NOVO por execução que despache o subagente `dev-cultivo` (cartão emitido pela skill, com
`memory: project`) pela ferramenta Agent — o caminho real: hook pre-agent → SubagentStart (brief) → caderno injetado
pela plataforma → escrita → `cs-state submit`.

Convenção do dono que CONTRARIA a intuição (o caso da correção):
  em src/cultivo/dependencias.py, `DEPENDE_DE` é indexado pelo PRÉ-REQUISITO: "A depende de B" vira
  DEPENDE_DE["b"] contendo "a" (X, certo). O óbvio pelo nome é DEPENDE_DE["a"] contendo "b" (Y, errado).

Cenários (config):
  base          sem lição; variantes V0..V3 em rodízio            → mede Y/X antes
  depois        lição registrada pelo caminho do produto (`cs-mem correct`, o que o /correct roda), caderno
                gerado pelo produto; variantes V1..V3 (nunca a frase da correção)
  sem-gatilho   como `depois`, mas título neutro e frase sem "depende"/"grafo": o gatilho só vem do território/caminho
  persistencia  depois de 2 tasks sem relação (despachadas de verdade), `cs.py emit` e `cs.py upgrade --apply`;
                sessão nova; variantes V1..V3
  sem-caderno   mesma lição no cs-mem, mas caderno ausente e `memory: project` tirado do cartão (canal = só o brief;
                isola o valor do caderno, L04/L12)
  refinamento   OPCIONAL (só com --configs explícito; diagnóstico, fora do critério): depois da CV-7 o dono refina
                (CV-8: chave = pré-requisito e nomes em MAIÚSCULAS) por `cs-mem correct --supersedes` (M12); mede
                aplicar a REFINADA e se a antiga ainda chega ao agente (contradição)
  pesquisa      task com termo fora do cartão cujo valor só está na memória (cs-mem); mede pesquisou × declarou

Medidas SEPARADAS por execução (agregadas por cenário/config):
  (i)   ENTREGA    a lição chegou: canal_caderno (MEMORY.md com o token da lição antes do despacho), canal_brief
                   (o brief que o SubagentStart injeta contém o token) e citou (a saída do subagente cita o token)
  (ii)  APLICACAO  aplicou X sem ser cobrado no prompt (o prompt NUNCA cita a convenção)  ← critério de parada
  (iii) DETECCAO   quando NÃO aplicou: verify / cs-mem check / validate acusam (rc≠0 ou citam a lição/consulta)
  pesquisa:        pesquisou DE FATO (ordem no transcript, abaixo) × declarou ('consultei:'), cruzados; coerente =
                   tema declarado no rastro B-24 e ID declarado saído do tool_result da busca
Critério de parada da campanha: APLICACAO (ii) ≥ 80% em `depois`, `sem-gatilho` e `persistencia`.
"Pesquisou de fato" = no transcript do subagente (stream-json, tool_use em ordem) uma `cs-mem search` ANTES da 1ª
edição de produto; o ID declarado em 'consultei: "TEMA" -> ID (efeito)' tem de aparecer no tool_result dessa busca.
Sem o subagente no stream, a ordem vem do obs.jsonl (hook PostToolUse da prova). O rastro B-24 é só diagnóstico aqui.

Uso:
  python3 prova_real.py --dry-run [--n 3] [--model sonnet] [--configs ...]      plano + custo, sem API
  python3 prova_real.py --offline-check --out DIR                               valida o harness da prova, sem API
  python3 prova_real.py --out DIR [--n 3] [--model sonnet] [--timeout 900] [--max-budget-usd X] [--configs ...]
Saída: DIR/<config>/<rep>/{alvo/, prompt.txt, saida.jsonl, stderr.txt, obs.jsonl, resultado.json, notes.md},
DIR/placar.json ({cenario, config, n, x_aplicado, taxa, ...}) e DIR/resumo.md. Só stdlib, Python 3.9+.
Isolamento: --out não pode ter ancestral (abaixo de $HOME) com CLAUDE.md, .claude/CLAUDE.md ou .claude/settings*.json
(o Claude Code carregaria instruções de outro projeto); o `claude -p` roda com --setting-sources project,local e
--strict-mcp-config (sem plugins/hooks do usuário), sem persistência de sessão.
"""
import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_iter21 as T  # noqa: E402  (fixture do domínio e helpers do alvo: fonte única com a camada mecânica)

AGENT = T.AGENT
DEP_FILE = "src/cultivo/dependencias.py"
LESSON_TOKEN = "CV-7"            # aparece só na correção: citar o token = a lição chegou e foi lida
CORRECTION = {
    "wrong": "registrar 'poda depende da adubação' como DEPENDE_DE['poda'] = ['adubacao']",
    "right": ("em DEPENDE_DE a CHAVE é o pré-requisito (convenção CV-7): 'A depende de B' vira DEPENDE_DE['b'] "
              "contendo 'a' — ex.: DEPENDE_DE['adubacao'] = ['poda']"),
    "why": "o agendador percorre do pré-requisito para os dependentes; convenção do dono, não está no código",
}
# variantes da mesma classe de tarefa (dependente, pré-requisito, frase). V0 é a frase do caso corrigido.
VARIANTS = [
    ("poda", "adubacao", "Registre no grafo de etapas que a poda depende da adubação."),
    ("irrigacao", "drenagem", "A irrigação passou a depender da drenagem: atualize o grafo de etapas."),
    ("rotulagem", "pesagem", "Inclua no grafo de etapas do cultivo: rotulagem depende de pesagem."),
    ("desbrota", "amarrio", "Nova regra de agenda: a desbrota só pode acontecer depois do amarrio (desbrota depende "
                            "de amarrio). Reflita isso no grafo de etapas."),
]
# sem gatilho explícito: título neutro e frase sem "depende"/"grafo" — o gatilho tem de vir do território/caminho
VARIANTS_NG = [
    ("irrigacao", "drenagem", "Daqui em diante a irrigação só pode ser agendada depois da drenagem."),
    ("rotulagem", "pesagem", "O produtor pediu: rotulagem só acontece com a pesagem feita antes."),
    ("desbrota", "amarrio", "Ajuste para que a desbrota venha sempre após o amarrio."),
]
UNRELATED = [
    ("src/cultivo/bandejas.py", "Adicione em src/cultivo/bandejas.py a função capacidade(linhas, colunas) que "
                                "devolve linhas * colunas."),
    ("src/cultivo/clima.py", "Adicione em src/cultivo/clima.py a função media(valores) que devolve a média "
                             "aritmética (0 para lista vazia)."),
]
SEARCH_DECISION = "Calagem padrão do lote: 180 gramas por célula (decisão do dono, safra 2026)"
SEARCH_TASK = ("Crie src/cultivo/calagem.py com a constante CALAGEM_PADRAO_G (int) igual à calagem padrão do lote "
               "decidida pelo dono deste projeto.")
SEARCH_RIGHT = 180
CONFIGS = ("base", "depois", "sem-gatilho", "persistencia", "sem-caderno", "pesquisa")
OPTIONAL_CONFIGS = ("refinamento",)        # diagnóstico, fora do critério de parada; só com --configs explícito
REFINED_TOKEN = "CV-8"
REFINEMENT = {
    "wrong": "manter os nomes das etapas em minúsculas no DEPENDE_DE",
    "right": ("convenção CV-8 (refina e substitui a CV-7): a CHAVE continua sendo o pré-requisito, mas todo nome de "
              "etapa vai em MAIÚSCULAS sem acento — ex.: DEPENDE_DE['ADUBACAO'] = ['PODA']"),
    "why": "o agendador novo compara nomes em maiúsculas; o dono refinou a regra",
}
STOP_CONFIGS = ("depois", "sem-gatilho", "persistencia")   # aplicação espontânea depois da correção
CENARIO = {"base": "corrigir-e-nao-esquecer", "depois": "corrigir-e-nao-esquecer",
           "sem-gatilho": "corrigir-sem-gatilho-no-titulo", "persistencia": "corrigir-e-nao-esquecer", "sem-caderno": "corrigir-e-nao-esquecer", "pesquisa": "pesquisa",
           "refinamento": "refinar-sem-contradicao"}
ALLOWED = ["Agent", "Task", "Read", "Grep", "Glob", "Edit", "Write", "MultiEdit",
           "Bash(.swarm/bin/cs-state *)", "Bash(./.swarm/bin/cs-state *)", "Bash(.swarm/bin/cs-mem *)",
           "Bash(./.swarm/bin/cs-mem *)", "Bash(python3 *)", "Bash(echo *)", "Bash(cat *)", "Bash(ls *)",
           "Bash(git status *)", "Bash(git diff *)", "Bash(git log *)", "Bash(git show *)"]
# Mudança oficial (permission_denied no 1º despacho da base): `python3 -m unittest tests.test_ok; echo "EXIT:$?"` foi
# negado porque `echo` não estava na lista (comando composto: cada parte precisa casar). As formas com caminho
# ABSOLUTO dos binários do alvo entram por despacho (allowed_for(root)). Nunca bypassPermissions.


def allowed_for(root):
    """Allow-list do despacho: ALLOWED + os binários do motor pelo caminho absoluto do alvo."""
    extra = []
    if root:
        for b in ("cs-state", "cs-mem"):
            extra.append("Bash(%s *)" % os.path.join(os.path.realpath(root), T.SD, "bin", b))
    return ALLOWED + extra
OBS_PY = r'''import json, sys, time
raw = sys.stdin.read()
try:
    p = json.loads(raw)
except ValueError:
    p = {"raw": raw[:2000]}
rec = {"ts": time.time(), "event": p.get("hook_event_name"), "tool": p.get("tool_name"),
       "agent_type": p.get("agent_type"), "agent_id": p.get("agent_id"),
       "input": json.dumps(p.get("tool_input"), ensure_ascii=False)[:4000]}
with open(sys.argv[1], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
'''


# ============================================================================================ plano / custo
def variants_for(config, n):
    """base: V0..V3 em rodízio; demais: V1..V3 (nunca a frase da correção); pesquisa: a task S."""
    if config == "pesquisa":
        return ["S"] * n
    if config == "sem-gatilho":
        return ["N%d" % (i % len(VARIANTS_NG)) for i in range(n)]
    pool = list(range(len(VARIANTS))) if config == "base" else list(range(1, len(VARIANTS)))
    return [pool[i % len(pool)] for i in range(n)]


def plan(configs, n):
    rows, total = [], 0
    for c in configs:
        d = n + (len(UNRELATED) if c == "persistencia" else 0)
        rows.append({"config": c, "cenario": CENARIO[c], "n": n, "variantes": variants_for(c, n), "despachos": d})
        total += d
    return rows, total


def print_plan(args):
    rows, total = plan(args.configs, args.n)
    print("PLANO prova_real iter21 — modelo %s, N=%d por config, timeout %ds por despacho" % (args.model, args.n,
                                                                                              args.timeout))
    for r in rows:
        extra = " (+%d tasks sem relação na cadeia)" % len(UNRELATED) if r["config"] == "persistencia" else ""
        print("  %-13s %-26s n=%d variantes=%s despachos=%d%s" % (r["config"], r["cenario"], r["n"],
                                                                  r["variantes"], r["despachos"], extra))
    print("  correção: 1x `cs-mem correct` (sem API) no molde de depois/persistencia/sem-caderno")
    print("TOTAL: %d despachos = %d sessões `claude -p` (1 orquestrador + 1 subagente cada)" % (total, total))
    print("PIOR CASO de tempo: %d min (despachos × timeout)" % (total * args.timeout // 60))
    if args.usd_por_despacho:
        print("CUSTO ESTIMADO: US$ %.2f (%.2f por despacho, informado)" % (total * args.usd_por_despacho,
                                                                         args.usd_por_despacho))
    else:
        print("CUSTO: %d despachos (passe --usd-por-despacho para estimar em US$; o real vem de total_cost_usd)" % total)
    return total


# ============================================================================================ alvo
def sh(argv, cwd, timeout=900, extra=None):
    return T.run(argv, cwd, extra=extra, timeout=timeout)


def build_template(dest, skill, termos=None):
    """Molde na ESCALA REAL do glossário (padrão: T.BIG_N termos a mais): o brief estoura o orçamento como no alvo
    real, e o canal brief/check do `sem-caderno` é medido na condição que o M13 corrige."""
    T.build_target(skill, dest, hook=False, extra_terms=T.BIG_N if termos is None else termos)
    return dest


def apply_correction(root):
    """Caminho real do produto: o comando que a skill /correct gerada no alvo manda rodar."""
    skill_md = os.path.join(root, ".claude", "skills", "correct", "SKILL.md")
    if not os.path.isfile(skill_md) or "cs-mem correct" not in T.read_text(skill_md):
        raise SystemExit("o alvo não tem a skill /correct chamando cs-mem correct: %s" % skill_md)
    code, h, e = T.mem(root, "correct", "--help")
    fault = ["--fault", "agent"] if "--fault" in h + e else []   # M11: o erro é do AGENTE (a task não mandava Y)
    return T.mem_ok(root, "correct", "--agent", AGENT, *fault, "--wrong", CORRECTION["wrong"], "--right",
                    CORRECTION["right"], "--why", CORRECTION["why"], "--paths", T.TERRITORY)


def apply_refinement(root):
    """Refina a correção CV-7 pelo caminho do produto: `cs-mem correct --supersedes <id>` (M12) se existir; senão
    grava a refinada como lição comum e registra que a antiga continua ativa (contradição esperada na base)."""
    old = [l["id"] for l in T.lessons_of(root, AGENT) if LESSON_TOKEN in l.get("rule", "") and l.get("status") == "active"]
    code, h, e = T.mem(root, "correct", "--help")
    sup = ["--supersedes", old[0]] if old and "--supersedes" in h + e else []
    T.mem_ok(root, "correct", "--agent", AGENT, *sup, "--wrong", REFINEMENT["wrong"], "--right", REFINEMENT["right"],
             "--why", REFINEMENT["why"], "--paths", T.TERRITORY)
    still = [l["id"] for l in T.lessons_of(root, AGENT) if LESSON_TOKEN in l.get("rule", "") and l.get("status") == "active"
             and REFINED_TOKEN not in l.get("rule", "")]
    return {"supersede_usado": bool(sup), "antiga_ativa": bool(still)}


def classify_refined(path, dependent, prereq):
    """REFINADA (chave = pré-requisito em MAIÚSCULAS com o dependente em MAIÚSCULAS), ANTIGA (X minúsculo), Y,
    INALTERADO/OUTRO, ERRO."""
    cls = classify_dep(path, dependent, prereq)
    if cls not in ("X", "AMBOS"):
        return cls
    tree = ast.parse(T.read_text(path))
    val = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "DEPENDE_DE" for t in node.targets):
            val = ast.literal_eval(node.value)
    up = val.get(prereq.upper())
    if isinstance(up, (list, tuple)) and dependent.upper() in up:
        return "REFINADA"
    return "ANTIGA"


def add_search_decision(root):
    return T.mem_ok(root, "add", "--kind", "decision", "--text", SEARCH_DECISION, "--scope", T.TERRITORY,
                    "--founder", "Ana")


def notebook_has_lesson(root):
    p = T.notebook_path(root, AGENT)
    if not os.path.isfile(p):
        return False, "caderno ausente"
    sp = T.split_notebook(T.read_text(p))
    if not sp:
        return False, "caderno sem bloco cs-mem"
    return LESSON_TOKEN in sp[2], "bloco %s o token" % ("tem" if LESSON_TOKEN in sp[2] else "NÃO tem")


def disable_notebook(root):
    card = os.path.join(root, ".claude", "agents", AGENT + ".md")
    txt = T.read_text(card)
    new = re.sub(r"(?m)^memory:\s*project\s*\n", "", txt, count=1)
    with open(card, "w", encoding="utf-8") as fh:
        fh.write(new)
    shutil.rmtree(os.path.join(root, ".claude", "agent-memory", AGENT), ignore_errors=True)
    return new != txt


def prepare_task(root, title, path, goal=None):
    """Cria a task pelo motor do alvo e a deixa BRIEFED (start). Devolve (tid, did, model)."""
    tid = T.new_task(root, AGENT, title, path, goal)
    out = T.st_ok(root, "start", tid)
    m = re.search(r"description='([^':]+):", out)
    mm = re.search(r"model='([^']+)'", out)
    if not m:
        raise AssertionError("start não mostrou a delegação BRIEFED: %r" % out)
    return tid, m.group(1), (mm.group(1) if mm else None)


def instrument(root, run_dir):
    """Observação independente do produto: PostToolUse de TODAS as ferramentas → run_dir/obs.jsonl."""
    obs_py = os.path.join(run_dir, "obs.py")
    with open(obs_py, "w", encoding="utf-8") as fh:
        fh.write(OBS_PY)
    local = {"hooks": {"PostToolUse": [{"matcher": "*", "hooks": [
        {"type": "command", "command": "python3 '%s' '%s'" % (obs_py, os.path.join(run_dir, "obs.jsonl")),
         "timeout": 30}]}]}}
    with open(os.path.join(root, ".claude", "settings.local.json"), "w", encoding="utf-8") as fh:
        json.dump(local, fh, indent=2)


def orchestrator_prompt(tid, did, model, task_text):
    return ("Sessão de teste automatizada. Você é o orquestrador deste repositório. A task %s já foi criada e "
            "preparada; a delegação %s está BRIEFED para o agente %s. Faça exatamente isto: (1) chame a ferramenta "
            "Agent com subagent_type='%s', model='%s', description='%s: executar a task' e prompt igual ao texto "
            "entre <tarefa> e </tarefa>, sem acrescentar nada; (2) quando o subagente voltar, responda só FIM. "
            "Não leia nem edite arquivos, não rode verify/review/accept, não registre correções.\n<tarefa>\n%s\n"
            "</tarefa>" % (tid, did, AGENT, AGENT, model, did, task_text))


def claude_argv(prompt, args, root=None, model=None, budget=None):
    a = [args.claude, "-p", prompt, "--model", model or args.model, "--output-format", "stream-json", "--verbose",
         "--permission-mode", "acceptEdits", "--permission-prompts", "none", "--setting-sources", "project,local",
         "--strict-mcp-config", "--no-session-persistence", "--allowedTools", " ".join(allowed_for(root))]
    if args.max_turns:  # não aparece no --help da 2.1.274; só vai se pedido
        a += ["--max-turns", str(args.max_turns)]
    if budget or args.max_budget_usd:
        a += ["--max-budget-usd", str(budget or args.max_budget_usd)]
    return a


def snapshot_swarm(root):
    out = {}
    for dp, dns, fns in os.walk(os.path.join(root, T.SD)):
        rel = os.path.relpath(dp, root).replace(os.sep, "/")
        if rel.startswith(T.SD + "/memory/index") or rel.startswith(T.SD + "/harness"):
            dns[:] = []
            continue
        for f in fns:
            p = os.path.join(dp, f)
            try:
                out[os.path.relpath(p, root)] = T.read_bytes(p)
            except OSError:
                pass
    return out


def new_text(before, after):
    """Texto novo sob .swarm/ entre duas fotografias (sufixo acrescentado ou arquivo inteiro)."""
    parts = []
    for rel, b in after.items():
        a = before.get(rel)
        if a == b:
            continue
        chunk = b[len(a):] if a is not None and b.startswith(a) else b
        parts.append(chunk.decode("utf-8", "replace"))
    return "\n".join(parts)


# ============================================================================================ medição
def _key(s):
    return T.strip_accents(str(s)).lower().strip()


def classify_dep(path, dependent, prereq):
    """X (pré-requisito é a chave), Y (dependente é a chave), AMBOS, INALTERADO/OUTRO, ERRO (parse)."""
    if not os.path.isfile(path):
        return "ERRO"
    try:
        tree = ast.parse(T.read_text(path))
        val = None
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "DEPENDE_DE" for t in node.targets):
                val = ast.literal_eval(node.value)
        if not isinstance(val, dict):
            return "ERRO"
    except (SyntaxError, ValueError):
        return "ERRO"
    g = {_key(k): {_key(x) for x in (v if isinstance(v, (list, tuple, set)) else [v])} for k, v in val.items()}
    x = _key(dependent) in g.get(_key(prereq), set())
    y = _key(prereq) in g.get(_key(dependent), set())
    if x and y:
        return "AMBOS"
    if x:
        return "X"
    if y:
        return "Y"
    return "INALTERADO"


def read_stream(path):
    msgs = []
    if os.path.isfile(path):
        with open(path, encoding="utf-8", errors="replace") as fh:
            for ln in fh.read().splitlines():
                try:
                    m = json.loads(ln)
                except ValueError:
                    continue
                if isinstance(m, dict):
                    msgs.append(m)
    return msgs


def permission_denials(msgs):
    """Negações do despacho, separadas pela ORIGEM: 'permissao' (sistema de permissões do Claude Code: allow-list)
    ou 'produto' (hook PreToolUse do produto, ex.: cs-guard — dado de produto, nunca contornado pela prova)."""
    results = {e["id"]: e.get("text", "") for e in tool_events(msgs) if e["kind"] == "result"}
    out, seen = [], set()
    for m in msgs:
        if m.get("type") == "result" and isinstance(m.get("permission_denials"), list):
            for d in m["permission_denials"]:
                if not isinstance(d, dict) or d.get("tool_use_id") in seen:
                    continue
                seen.add(d.get("tool_use_id"))
                txt = results.get(d.get("tool_use_id"), "")
                origem = "produto" if re.search(r"hook error|cs-guard", txt) else "permissao"
                inp = d.get("tool_input") if isinstance(d.get("tool_input"), dict) else {}
                out.append({"tool": d.get("tool_name"), "comando": str(inp.get("command", ""))[:300],
                            "origem": origem, "motivo": txt[:300]})
    n_sys = sum(1 for m in msgs if m.get("type") == "system" and m.get("subtype") == "permission_denied")
    if n_sys > sum(1 for d in out if d["origem"] == "permissao"):   # stream sem result final (timeout)
        out.append({"tool": "?", "comando": "", "origem": "permissao", "motivo": "system/permission_denied sem result"})
    return out


def stream_text(msgs):
    return "\n".join(json.dumps(m, ensure_ascii=False) for m in msgs)


def stream_cost(msgs):
    """Soma das mensagens `result` (com o Agent assíncrono, a 2.1.274 emite uma por turno do orquestrador;
    conferido numa sonda de 1 chamada: dois `result` no mesmo stream)."""
    res = [m for m in msgs if m.get("type") == "result"]
    if not res:
        return None, None, None
    cost = sum(float(m.get("total_cost_usd") or 0) for m in res)
    return round(cost, 6), any(m.get("is_error") for m in res), sum(int(m.get("num_turns") or 0) for m in res)


def obs_records(path):
    out = []
    if os.path.isfile(path):
        for ln in T.read_text(path).splitlines():
            try:
                out.append(json.loads(ln))
            except ValueError:
                pass
    return out


def searches_observed(obs):
    return [r for r in obs if r.get("tool") == "Bash" and r.get("agent_type") == AGENT and "cs-mem" in (r.get("input") or "")
            and " search" in (r.get("input") or "")]


CONSULTEI_Q = re.compile(r'consultei:\s*["“]([^"”\n]+)["”]\s*(?:->|→)\s*([^\s"\'(),]+)(?:\s*\(([^)\n]*)\))?', re.I)
CONSULTEI_U = re.compile(r'consultei:\s*([^\n"“→>]+?)\s*(?:->|→)\s*([^\s"\'(),]+)(?:\s*\(([^)\n]*)\))?', re.I)
CONSULTEI_NADA = re.compile(r'consultei:\s*nada\b([^\n"]*)', re.I)


def declared(text):
    """Declarações 'consultei:' → [{tema, id, efeito, nada}]. Formato do dono: consultei: "TEMA" -> ID (efeito)."""
    out, seen = [], set()
    for m in CONSULTEI_NADA.finditer(text or ""):
        out.append({"tema": None, "id": None, "efeito": m.group(1).strip(" —-:"), "nada": True})
    for rx in (CONSULTEI_Q, CONSULTEI_U):
        for m in rx.finditer(text or ""):
            tema = m.group(1).strip()
            if tema.lower().startswith("nada") or (tema, m.group(2)) in seen:
                continue
            seen.add((tema, m.group(2)))
            out.append({"tema": tema, "id": m.group(2).strip(), "efeito": (m.group(3) or "").strip(), "nada": False})
    return out


def _strings(obj):
    return [v for v in T.json_values(obj) if isinstance(v, str)]


def texts_for_declaration(swarm_new, msgs):
    """Texto onde procurar 'consultei:': strings dos tool_use do transcript e dos registros JSON novos sob .swarm/
    (desescapadas), mais o texto cru."""
    parts = [swarm_new]
    for ln in swarm_new.splitlines():
        try:
            parts += _strings(json.loads(ln))
        except ValueError:
            pass
    for ev in tool_events(msgs):
        if ev["kind"] == "use":
            parts += _strings(ev["input"])
    return "\n".join(parts)


def tool_events(msgs):
    """tool_use / tool_result EM ORDEM do stream-json (subagente = parent_tool_use_id preenchido)."""
    out = []
    for m in msgs:
        if not isinstance(m, dict):
            continue
        parent = m.get("parent_tool_use_id")
        msg = m.get("message")
        content = msg.get("content") if isinstance(msg, dict) else None   # system/permission_denied: message é str
        if not isinstance(content, list):
            continue
        for c in content:
            if not isinstance(c, dict):
                continue
            if c.get("type") == "tool_use":
                out.append({"kind": "use", "id": c.get("id"), "name": c.get("name"), "input": c.get("input") or {},
                            "parent": parent})
            elif c.get("type") == "tool_result":
                cc = c.get("content")
                txt = cc if isinstance(cc, str) else "\n".join(x.get("text", "") for x in cc or [] if isinstance(x, dict))
                out.append({"kind": "result", "id": c.get("tool_use_id"), "text": txt, "parent": parent})
    return out


EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")


def _is_search(cmd):
    return "cs-mem" in cmd and re.search(r"\bsearch\b", cmd) is not None


def _is_product_edit(inp):
    fp = str((inp or {}).get("file_path") or (inp or {}).get("notebook_path") or "")
    return fp and "agent-memory" not in fp


def search_order(msgs, obs):
    """Ordem pesquisa → 1ª edição do subagente. Fonte 1: transcript (stream-json, com o tool_result da busca);
    fonte 2 (se o stream não trouxer o subagente): obs.jsonl (PostToolUse, em ordem, sem resultado)."""
    ev = [e for e in tool_events(msgs) if e.get("parent")]
    if any(e["kind"] == "use" for e in ev):
        uses = [e for e in ev if e["kind"] == "use"]
        res = {e["id"]: e.get("text", "") for e in ev if e["kind"] == "result"}
        s_idx = [i for i, e in enumerate(uses) if e["name"] == "Bash" and _is_search(str(e["input"].get("command", "")))]
        e_idx = [i for i, e in enumerate(uses) if e["name"] in EDIT_TOOLS and _is_product_edit(e["input"])]
        results = "\n".join(res.get(uses[i]["id"], "") for i in s_idx)
        cmds = [str(uses[i]["input"].get("command", "")) for i in s_idx]
        fonte = "transcript"
    else:
        sub = [r for r in obs if r.get("agent_type") == AGENT]
        s_idx = [i for i, r in enumerate(sub) if r.get("tool") == "Bash" and _is_search(r.get("input") or "")]
        e_idx = [i for i, r in enumerate(sub) if r.get("tool") in EDIT_TOOLS and "agent-memory" not in (r.get("input") or "")]
        results, cmds, fonte = None, [sub[i].get("input", "") for i in s_idx], "obs"
    antes = bool(s_idx) and (not e_idx or s_idx[0] < e_idx[0])
    return {"fonte_ordem": fonte, "buscas": len(s_idx), "pesquisou_antes_de_editar": antes,
            "resultados": results, "comandos_busca": [c[:300] for c in cmds][:5]}


def score_search(obs, swarm_new, decl, msgs=()):
    """pesquisou DE FATO (ordem busca → 1ª edição no transcript/obs) × declarou ('consultei:'), cruzados.
    pesquisou_rastro = o rastro B-24 do produto registrou busca do agente (diagnóstico do requisito mecânico).
    id_saiu_da_busca = todo ID declarado aparece no tool_result de uma busca do subagente (só com o transcript)."""
    order = search_order(msgs, obs)
    trail = [ln for ln in swarm_new.splitlines() if re.search(r"search", ln, re.I) and AGENT in ln]
    temas = [d for d in decl if not d["nada"]]
    ids_ok = None
    if temas and order["resultados"] is not None:
        ids_ok = all(d["id"] in order["resultados"] for d in temas)
    tema_no_rastro = bool(temas) and all(any(d["tema"] in ln for ln in trail) for d in temas)
    return {"pesquisou_de_fato": order["pesquisou_antes_de_editar"], "buscas": order["buscas"],
            "fonte_ordem": order["fonte_ordem"], "pesquisou_rastro": bool(trail), "declarou": bool(decl),
            "declarou_nada": bool(decl) and not temas, "tema_no_rastro": tema_no_rastro, "id_saiu_da_busca": ids_ok,
            "coerente": bool(temas) and tema_no_rastro and ids_ok is not False,
            "consultas_observadas": order["comandos_busca"]}


def detection(root, tid, applied, citation_tokens):
    """(iii) quando NÃO aplicou: o gate acusa? verify, cs-mem check e validate; acusa = rc≠0 citando a lição/consulta."""
    outs = {}
    for name, argv in (("verify", ["state", "verify", tid]), ("check", ["mem", "check", "--agent", AGENT]),
                       ("validate", ["validate"])):
        if name == "validate":
            code, out, err = sh([sys.executable, os.path.join(root, T.SD, "harness", "validate.py"), "--root", root], root)
        else:
            code, out, err = T.tool(root, argv[0], *argv[1:])
        outs[name] = {"rc": code, "cita": any(tok.lower() in (out + err).lower() for tok in citation_tokens),
                      "tail": (out + err)[-600:]}
    acusou = any(v["rc"] != 0 and v["cita"] for v in outs.values())
    return {"aplicou": applied, "acusou": acusou if not applied else None, "gates": outs}


def run_dispatch(args, root, run_dir, title, path, task_text, goal=None):
    os.makedirs(run_dir, exist_ok=True)
    tid, did, model = prepare_task(root, title, path, goal)
    model = model or args.model
    brief = T.st_ok(root, "brief", tid)
    instrument(root, run_dir)
    model = getattr(args, "_sonda_model", None) or model
    prompt = orchestrator_prompt(tid, did, model, task_text)
    with open(os.path.join(run_dir, "prompt.txt"), "w", encoding="utf-8") as fh:
        fh.write(prompt)
    with open(os.path.join(run_dir, "brief.txt"), "w", encoding="utf-8") as fh:
        fh.write(brief)
    nb_before = T.read_text(T.notebook_path(root, AGENT)) if os.path.isfile(T.notebook_path(root, AGENT)) else None
    snap = snapshot_swarm(root)
    t0 = time.time()
    env = T._env()
    env.pop("TMPDIR", None)
    try:
        p = subprocess.run(claude_argv(prompt, args, root, model=getattr(args, "_sonda_model", None),
                                       budget=getattr(args, "_sonda_budget", None)), cwd=root, env=env,
                           stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=args.timeout)
        rc, out, err = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        rc, out, err = "timeout", e.stdout or b"", e.stderr or b""
    with open(os.path.join(run_dir, "saida.jsonl"), "wb") as fh:
        fh.write(out)
    with open(os.path.join(run_dir, "stderr.txt"), "wb") as fh:
        fh.write(err)
    if nb_before is not None:
        with open(os.path.join(run_dir, "caderno-antes.md"), "w", encoding="utf-8") as fh:
            fh.write(nb_before)
    if os.path.isfile(T.notebook_path(root, AGENT)):
        shutil.copy(T.notebook_path(root, AGENT), os.path.join(run_dir, "caderno-depois.md"))
    msgs = read_stream(os.path.join(run_dir, "saida.jsonl"))
    cost, is_err, turns = stream_cost(msgs)
    neg = permission_denials(msgs)
    with open(os.path.join(run_dir, "negacoes.json"), "w", encoding="utf-8") as fh:
        json.dump(neg, fh, ensure_ascii=False, indent=1)
    return {"tid": tid, "delegacao": did, "model": model, "rc": rc, "segundos": round(time.time() - t0, 1),
            "negacoes": neg,
            "custo_usd": cost, "is_error": is_err, "turnos": turns, "brief": brief, "nb_before": nb_before,
            "swarm_new": new_text(snap, snapshot_swarm(root)), "stream": stream_text(msgs), "msgs": msgs,
            "obs": obs_records(os.path.join(run_dir, "obs.jsonl"))}


def measure_dep(args, root, run_dir, config, rep, vi):
    if isinstance(vi, str) and vi.startswith("N"):
        dep, pre, phrase = VARIANTS_NG[int(vi[1:])]
        title = "Ajuste pedido pelo produtor %d" % rep           # título sem gatilho
    else:
        dep, pre, phrase = VARIANTS[vi]
        title = "Atualizar grafo de etapas (%s)" % dep
    task = phrase + " O arquivo é %s. Ao terminar, submeta pelo cs-state submit conforme o seu brief." % DEP_FILE
    r = run_dispatch(args, root, run_dir, title, DEP_FILE, task)
    cls = classify_dep(os.path.join(root, DEP_FILE), dep, pre)
    shutil.copy(os.path.join(root, DEP_FILE), os.path.join(run_dir, "dependencias.py"))
    applied = cls == "X"
    canal_caderno = bool(r["nb_before"]) and LESSON_TOKEN in (r["nb_before"] or "")
    canal_brief = LESSON_TOKEN in r["brief"]
    citou = LESSON_TOKEN in r["stream"] or LESSON_TOKEN in r["swarm_new"]
    det = detection(root, r["tid"], applied, [LESSON_TOKEN, "DEPENDE_DE", "pré-requisito", "pre-requisito"])
    decl = declared(texts_for_declaration(r["swarm_new"], r["msgs"]))
    if config == "refinamento":
        cls = classify_refined(os.path.join(root, DEP_FILE), dep, pre)
        applied = cls == "REFINADA"
        old_in = LESSON_TOKEN in r["brief"] or LESSON_TOKEN in (T.split_notebook(r["nb_before"] or "") or ["", "", ""])[2]
        canal_caderno = bool(r["nb_before"]) and REFINED_TOKEN in (r["nb_before"] or "")
        canal_brief = REFINED_TOKEN in r["brief"]
        citou = REFINED_TOKEN in r["stream"]
        det = detection(root, r["tid"], applied, [REFINED_TOKEN, LESSON_TOKEN, "DEPENDE_DE"])
    res = {"cenario": CENARIO[config], "config": config, "rep": rep,
            "variante": vi if isinstance(vi, str) else "V%d" % vi, "classe": cls,
            "entrega": {"canal_caderno": canal_caderno, "canal_brief": canal_brief, "citou": citou,
                        "entregue": canal_caderno or canal_brief},
            "aplicacao": applied, "deteccao": det, "pesquisa": score_search(r["obs"], r["swarm_new"], decl, r["msgs"]),
            "rc": r["rc"], "segundos": r["segundos"], "custo_usd": r["custo_usd"], "is_error": r["is_error"],
            "turnos": r["turnos"], "tid": r["tid"], "negacoes": r["negacoes"]}
    if config == "refinamento":
        res["antiga_injetada"] = old_in            # contradição: a regra substituída ainda chegou ao agente
    return res


def measure_search(args, root, run_dir, rep):
    task = SEARCH_TASK + " Ao terminar, submeta pelo cs-state submit conforme o seu brief."
    r = run_dispatch(args, root, run_dir, "Constante de calagem do lote", "src/cultivo/calagem.py", task)
    val = None
    p = os.path.join(root, "src", "cultivo", "calagem.py")
    if os.path.isfile(p):
        shutil.copy(p, os.path.join(run_dir, "calagem.py"))
        m = re.search(r"CALAGEM_PADRAO_G\s*(?::\s*int)?\s*=\s*(\d+)", T.read_text(p))
        val = int(m.group(1)) if m else None
    decl = declared(texts_for_declaration(r["swarm_new"], r["msgs"]))
    ps = score_search(r["obs"], r["swarm_new"], decl, r["msgs"])
    applied = ps["pesquisou_de_fato"]
    det = detection(root, r["tid"], applied and ps["coerente"], ["consult", "cs-mem search"])
    return {"cenario": "pesquisa", "config": "pesquisa", "rep": rep, "variante": "S",
            "classe": "CERTO" if val == SEARCH_RIGHT else ("VALOR %s" % val if val is not None else "SEM ARQUIVO"),
            "entrega": {"canal_brief": "180" in r["brief"], "canal_caderno": False, "citou": "180" in r["stream"],
                        "entregue": "180" in r["brief"]},
            "aplicacao": bool(applied and ps["declarou"] and ps["coerente"]), "deteccao": det, "pesquisa": ps,
            "valor_certo": val == SEARCH_RIGHT, "rc": r["rc"], "segundos": r["segundos"], "custo_usd": r["custo_usd"],
            "is_error": r["is_error"], "turnos": r["turnos"], "tid": r["tid"], "negacoes": r["negacoes"]}


def notes_md(res):
    if res.get("classe") == "NOT_RUN":
        return "# %s / %s / rep %d — NOT_RUN\n\n- erro: %s (traceback em erro.txt)\n" % (
            res["cenario"], res["config"], res["rep"], res.get("erro"))
    e = res["entrega"]
    return ("# %s / %s / rep %d (%s)\n\n- classe: %s\n- (i) entrega: caderno=%s brief=%s citou=%s\n- (ii) aplicação: %s\n"
            "- (iii) detecção (se não aplicou): %s\n- pesquisa: %s\n- rc=%s, %ss, US$ %s, turnos %s\n"
            % (res["cenario"], res["config"], res["rep"], res["variante"], res["classe"], e["canal_caderno"],
               e["canal_brief"], e["citou"], res["aplicacao"], res["deteccao"].get("acusou"),
               json.dumps(res["pesquisa"], ensure_ascii=False), res["rc"], res["segundos"], res["custo_usd"],
               res["turnos"]))


def save(run_dir, res):
    with open(os.path.join(run_dir, "resultado.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(run_dir, "notes.md"), "w", encoding="utf-8") as fh:
        fh.write(notes_md(res))


def placar(results):
    rows = {}
    for r in results:
        k = (r["cenario"], r["config"])
        s = rows.setdefault(k, {"cenario": k[0], "config": k[1], "n": 0, "x_aplicado": 0, "entregue": 0, "citou": 0,
                                "nao_aplicou": 0, "detectado": 0, "pesquisou": 0, "declarou": 0,
                                "pesquisou_e_declarou": 0, "declarou_sem_pesquisar": 0, "pesquisou_sem_declarar": 0,
                                "coerente": 0, "rastro_b24": 0, "antiga_injetada": 0, "erros": 0, "custo_usd": 0.0,
                                "not_run": 0, "negado_permissao": 0, "negado_produto": 0})
        s["custo_usd"] += float(r.get("custo_usd") or 0)
        if r.get("classe") == "NOT_RUN":
            s["not_run"] += 1
            continue
        neg = r.get("negacoes") or []
        s["negado_permissao"] += any(d["origem"] == "permissao" for d in neg)
        s["negado_produto"] += any(d["origem"] == "produto" for d in neg)
        s["n"] += 1
        s["x_aplicado"] += bool(r["aplicacao"])
        s["entregue"] += bool(r["entrega"]["entregue"])
        s["citou"] += bool(r["entrega"]["citou"])
        if not r["aplicacao"]:
            s["nao_aplicou"] += 1
            s["detectado"] += bool(r["deteccao"].get("acusou"))
        ps = r["pesquisa"]
        pq = bool(ps["pesquisou_de_fato"])
        s["pesquisou"] += pq
        s["declarou"] += ps["declarou"]
        s["pesquisou_e_declarou"] += pq and ps["declarou"]
        s["declarou_sem_pesquisar"] += ps["declarou"] and not pq
        s["pesquisou_sem_declarar"] += pq and not ps["declarou"]
        s["coerente"] += ps["coerente"]
        s["rastro_b24"] += ps["pesquisou_rastro"]
        s["antiga_injetada"] += bool(r.get("antiga_injetada"))
        s["erros"] += r["rc"] not in (0,) or bool(r["is_error"])
    out = []
    for s in rows.values():
        s["taxa"] = round(s["x_aplicado"] / s["n"], 3) if s["n"] else 0.0
        s["taxa_entrega"] = round(s["entregue"] / s["n"], 3) if s["n"] else 0.0
        s["taxa_deteccao"] = round(s["detectado"] / s["nao_aplicou"], 3) if s["nao_aplicou"] else None
        s["custo_usd"] = round(s["custo_usd"], 4)
        out.append(s)
    order = {c: i for i, c in enumerate(CONFIGS + OPTIONAL_CONFIGS)}
    return sorted(out, key=lambda s: order.get(s["config"], 99))


def resumo(rows, threshold=0.8):
    L = ["# Placar prova_real iter21", "",
         "NOT_RUN (fora do n): %s; despachos com Bash negado pela allow-list: %s; negado por hook do produto: %s" % (
             sum(s.get("not_run", 0) for s in rows), sum(s.get("negado_permissao", 0) for s in rows),
             sum(s.get("negado_produto", 0) for s in rows)), "",
         "| config | n | (ii) aplicação | (i) entrega | citou | (iii) detecção | pesquisou | declarou | P∧D | D sem P | "
         "coerente | erros | US$ |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in rows:
        L.append("| %s | %d | %d (%.0f%%) | %d | %d | %s | %d | %d | %d | %d | %d | %d | %.2f |" % (
            s["config"], s["n"], s["x_aplicado"], 100 * s["taxa"], s["entregue"], s["citou"],
            ("%d/%d" % (s["detectado"], s["nao_aplicou"])) if s["nao_aplicou"] else "—", s["pesquisou"],
            s["declarou"], s["pesquisou_e_declarou"], s["declarou_sem_pesquisar"], s["coerente"], s["erros"],
            s["custo_usd"]))
    crit = {s["config"]: s["taxa"] for s in rows}
    ok = all(crit.get(c, 0) >= threshold for c in STOP_CONFIGS if c in crit)   # refinamento fica de fora
    L += ["", "Critério de parada: APLICAÇÃO ≥ %.0f%% em %s → %s" % (
        100 * threshold, ", ".join(STOP_CONFIGS), "ATINGIDO" if ok and ("depois" in crit) else "NÃO atingido")]
    if "refinamento" in crit:
        rr = [s for s in rows if s["config"] == "refinamento"][0]
        L.append("Refinamento (diagnóstico, fora do critério): aplicou a REFINADA %d/%d; regra antiga ainda injetada "
                 "em %d" % (rr["x_aplicado"], rr["n"], rr["antiga_injetada"]))
    if "sem-caderno" in crit and "depois" in crit:
        L.append("Valor do caderno (depois − sem-caderno): %+.0f pontos" % (100 * (crit["depois"] - crit["sem-caderno"])))
    return "\n".join(L) + "\n"


# ============================================================================================ execução real
def check_isolation(out):
    home = os.path.realpath(os.path.expanduser("~"))
    d = os.path.realpath(out)
    bad = []
    while True:
        parent = os.path.dirname(d)
        if d != home and d != "/":
            for c in ("CLAUDE.md", os.path.join(".claude", "CLAUDE.md"), os.path.join(".claude", "settings.json"),
                      os.path.join(".claude", "settings.local.json")):
                if os.path.isfile(os.path.join(d, c)):
                    bad.append(os.path.join(d, c))
        if parent == d:
            break
        d = parent
    return bad


def real(args):
    out = os.path.realpath(args.out)
    bad = check_isolation(out)
    if bad and not args.allow_ancestor_claude:
        raise SystemExit("--out tem ancestral com instruções do Claude Code (contaminaria a prova): %s" % bad)
    os.makedirs(out, exist_ok=True)
    print_plan(args)
    tpl = build_template(os.path.join(out, "_molde-base"), args.skill, args.termos)
    results = []
    corr = None
    if any(c in args.configs for c in ("depois", "sem-gatilho", "persistencia", "sem-caderno", "refinamento")):
        corr = os.path.join(out, "_molde-corrigido")
        shutil.copytree(tpl, corr, symlinks=True)
        apply_correction(corr)
        ok, why = notebook_has_lesson(corr)
        print("caderno depois da correção: %s (%s)" % (ok, why))
    if "refinamento" in args.configs:
        refi = os.path.join(out, "_molde-refinado")
        shutil.copytree(corr, refi, symlinks=True)
        info = apply_refinement(refi)
        print("refinamento: %s; caderno: %s" % (info, notebook_has_lesson(refi)))
    for config in args.configs:
        src = tpl if config in ("base", "pesquisa") else (refi if config == "refinamento" else corr)
        if config == "persistencia":
            chain = os.path.join(out, config, "_cadeia")
            shutil.copytree(src, chain, symlinks=True)
            for i, (path, text) in enumerate(UNRELATED):
                rd = os.path.join(out, config, "_sem-relacao-%d" % i)
                r = run_dispatch(args, chain, rd, "Tarefa sem relação %d" % i, path, text +
                                 " Ao terminar, submeta pelo cs-state submit conforme o seu brief.")
                with open(os.path.join(rd, "resultado.json"), "w", encoding="utf-8") as fh:
                    json.dump({k: r[k] for k in ("tid", "rc", "segundos", "custo_usd", "is_error")}, fh)
                T.tool(chain, "state", "drop", r["tid"], "--reason", "prova: tarefa sem relação encerrada")
            T.cs(args.skill, chain, "emit", "--allow-outside")
            T.cs(args.skill, chain, "upgrade", "--apply", "--allow-outside")
            src = chain
        for rep, vi in enumerate(variants_for(config, args.n)):
            rd = os.path.join(out, config, "%02d" % rep)
            root = os.path.join(rd, "alvo")
            shutil.copytree(src, root, symlinks=True)
            if config == "sem-caderno":
                disable_notebook(root)
            if config == "pesquisa":
                add_search_decision(root)
            try:
                res = measure_search(args, root, rd, rep) if config == "pesquisa" else measure_dep(
                    args, root, rd, config, rep, vi)
            except Exception as e:  # uma linha/estado inesperado invalida SÓ este despacho (NOT_RUN), nunca a rodada
                import traceback
                res = not_run(config, rep, vi, "%s: %s" % (type(e).__name__, e), traceback.format_exc(), rd)
            save(rd, res)
            results.append(res)
            if len(results) == 1 and early_abort(res):
                finish(out, results)
                raise SystemExit("ABORTADO no 1º despacho: Bash negado pelo sistema de permissões (%s) — corrija a "
                                 "allow-list (rode --offline-check --sonda-api) antes de gastar a rodada" % [
                                     d["comando"] for d in res.get("negacoes") or [] if d["origem"] == "permissao"])
            print("%-13s rep %d %-3s classe=%-10s aplicou=%s entrega=%s rc=%s %ss" % (
                config, rep, res["variante"], res["classe"], res["aplicacao"], res["entrega"]["entregue"], res["rc"],
                res["segundos"]))
    finish(out, results)
    return 0


def finish(out, results):
    rows = placar(results)
    with open(os.path.join(out, "placar.json"), "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=1)
    txt = resumo(rows)
    with open(os.path.join(out, "resumo.md"), "w", encoding="utf-8") as fh:
        fh.write(txt)
    print(txt)
    return rows


def not_run(config, rep, vi, erro, tb, rd):
    with open(os.path.join(rd, "erro.txt"), "w", encoding="utf-8") as fh:
        fh.write(tb)
    return {"cenario": CENARIO[config], "config": config, "rep": rep,
            "variante": vi if isinstance(vi, str) else "V%d" % vi, "classe": "NOT_RUN", "erro": erro,
            "aplicacao": False, "entrega": {"entregue": False, "citou": False, "canal_caderno": False,
                                            "canal_brief": False},
            "deteccao": {}, "pesquisa": score_search([], "", [], []), "rc": None, "segundos": None,
            "custo_usd": None, "is_error": True, "turnos": None, "negacoes": []}


def early_abort(res):
    """Aborta a rodada se o 1º despacho teve Bash negado pelo SISTEMA DE PERMISSÕES (allow-list da prova).
    Negação por hook do produto (cs-guard) é dado de produto: não aborta."""
    return any(d["origem"] == "permissao" and d["tool"] in ("Bash", "?") for d in res.get("negacoes") or [])


# ============================================================================================ offline-check
def offline_check(args):
    out = os.path.realpath(args.out)
    os.makedirs(out, exist_ok=True)
    checks = []

    def ck(name, ok, info=""):
        checks.append((name, bool(ok), info))
        print("%-4s %s%s" % ("OK" if ok else "FAIL", name, (" — " + info) if info else ""))

    code, o, e = sh([args.claude, "--version"], out, timeout=60)
    ck("claude instalado (--version, sem API)", code == 0, (o + e).strip()[:80])
    code, helptxt, e = sh([args.claude, "--help"], out, timeout=60)
    argv = claude_argv("x", args, out)
    flags = [a for a in argv if a.startswith("--")]
    missing = [f for f in flags if f not in helptxt]
    ck("todas as flags do claude -p existem no --help", not missing, "faltam: %s" % missing if missing else
       " ".join(flags))
    ck("isolamento: o próprio --out do check é avaliado", True, "ancestrais com instruções: %s" % check_isolation(out))
    tpl = build_template(os.path.join(out, "_molde"), args.skill, args.termos)
    gl = T.json5io().loads(T.read_text(os.path.join(tpl, T.SD, "facts", "glossary.json5")))
    ck("molde com glossário na escala real (%d termos ≥ %d)" % (len(gl["facts"]), len(T.TERMS) + args.termos),
       len(gl["facts"]) >= len(T.TERMS) + args.termos)
    ck("molde gerado pela skill (init+install+emit+cs-state init)", os.path.isfile(os.path.join(tpl, ".claude", "agents",
                                                                                                 AGENT + ".md")))
    card = T.read_text(os.path.join(tpl, ".claude", "agents", AGENT + ".md"))
    ck("cartão do subagente com memory: project", re.search(r"(?m)^memory:\s*project\s*$", card))
    st = json.load(open(os.path.join(tpl, ".claude", "settings.json")))
    ck("hooks do produto no molde (PreToolUse/SubagentStart)", "PreToolUse" in st.get("hooks", {}) and
       "SubagentStart" in st.get("hooks", {}))
    r1 = os.path.join(out, "_tarefa")
    shutil.copytree(tpl, r1, symlinks=True)
    tid, did, model = prepare_task(r1, "Atualizar grafo de etapas (poda)", DEP_FILE)
    ck("task preparada e delegação BRIEFED extraída", did and did.startswith(tid), "%s %s model=%s" % (tid, did, model))
    p = " ".join(orchestrator_prompt(tid, did, model or args.model, v[2]) for v in VARIANTS + VARIANTS_NG)
    leak = [w for w in ("pré-requisito", "pre-requisito", "CHAVE", "MAIÚSCULAS", LESSON_TOKEN, REFINED_TOKEN,
                        "convenção") if w in p]
    leak += [v[2] for v in VARIANTS_NG if re.search(r"depend|grafo", v[2], re.I)]
    ck("prompt não cobra a convenção (aplicação espontânea)", not leak, str(leak))
    rd = os.path.join(out, "_obs")
    os.makedirs(rd, exist_ok=True)
    instrument(r1, rd)
    pobs = subprocess.run([sys.executable, os.path.join(rd, "obs.py"), os.path.join(rd, "obs.jsonl")],
                          input=json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Bash", "agent_type": AGENT,
                                            "tool_input": {"command": ".swarm/bin/cs-mem search calagem --agent x"}}
                                           ).encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    obs = obs_records(os.path.join(rd, "obs.jsonl"))
    ck("instrumentação PostToolUse grava obs.jsonl", pobs.returncode == 0 and len(searches_observed(obs)) == 1)
    lj = json.load(open(os.path.join(r1, ".claude", "settings.local.json")))
    ck("settings.local.json do alvo com o hook de observação", "PostToolUse" in lj["hooks"])
    # calibração da medida (saída vazia reprova; X/Y/AMBOS/INALTERADO/ERRO)
    f = os.path.join(out, "_cal.py")
    cases = [("DEPENDE_DE = {'adubacao': ['poda'], 'triagem': ['lavagem']}\n", "X"),
             ("DEPENDE_DE = {'poda': ['adubação']}\n", "Y"),
             ("DEPENDE_DE = {'poda': ['adubacao'], 'adubacao': ['poda']}\n", "AMBOS"),
             (T.PRODUCT[DEP_FILE], "INALTERADO"), ("", "ERRO"), ("DEPENDE_DE = {\n", "ERRO")]
    got = []
    for txt, exp in cases:
        with open(f, "w", encoding="utf-8") as fh:
            fh.write(txt)
        got.append((exp, classify_dep(f, "poda", "adubacao")))
    ck("classificação X/Y calibrada (vazio reprova)", all(a == b for a, b in got), str(got))
    # correção pelo produto
    r2 = os.path.join(out, "_corrigido")
    shutil.copytree(tpl, r2, symlinks=True)
    apply_correction(r2)
    inj = T.mem_ok(r2, "inject", "--agent", AGENT, "--paths", DEP_FILE, "--title", "grafo de etapas")
    ck("correção registrada pelo caminho do produto (cs-mem correct)", LESSON_TOKEN in inj)
    tid2, _, _ = prepare_task(r2, "Atualizar grafo de etapas (irrigacao)", DEP_FILE)
    b2 = T.st_ok(r2, "brief", tid2)
    ck("[diagnóstico] canal brief carrega a lição sob orçamento estourado (M13 A; falha no HEAD é esperada)", True,
       "lição no brief=%s; omitidos pelo orçamento=%s" % (LESSON_TOKEN in b2, bool(re.search(r"omitid", b2))))
    code, ck_out, ck_err = T.mem(r2, "check", "--agent", AGENT)
    ck("[diagnóstico] `cs-mem check --agent` como o cartão manda (M13 B; vazio no HEAD é esperado)", True,
       "lição no check=%s" % (LESSON_TOKEN in ck_out))
    okn, why = notebook_has_lesson(r2)
    ck("[diagnóstico] caderno gerado pelo produto com a lição (B-22; falha no HEAD 0.10.1 é esperada)", True,
       "%s (%s)" % (okn, why))
    r4 = os.path.join(out, "_refinado")
    shutil.copytree(r2, r4, symlinks=True)
    info = apply_refinement(r4)
    ck("[diagnóstico] refinamento pelo produto (M12; na 0.10.1 sem --supersedes, a antiga segue ativa)", True,
       json.dumps(info))
    cal = []
    for txt, exp in (("DEPENDE_DE = {'ADUBACAO': ['PODA']}\n", "REFINADA"), ("DEPENDE_DE = {'adubacao': ['poda']}\n",
                     "ANTIGA"), ("DEPENDE_DE = {'PODA': ['ADUBACAO']}\n", "Y"), ("", "ERRO")):
        fr = os.path.join(out, "_cal_ref.py")
        with open(fr, "w", encoding="utf-8") as fh:
            fh.write(txt)
        cal.append((exp, classify_refined(fr, "poda", "adubacao")))
    ck("classificação do refinamento calibrada (REFINADA/ANTIGA/Y/ERRO)", all(a == b for a, b in cal), str(cal))
    r3 = os.path.join(out, "_sem-caderno")
    shutil.copytree(r2, r3, symlinks=True)
    ck("sem-caderno tira memory: project e o caderno", disable_notebook(r3) and not os.path.isdir(
        os.path.join(r3, ".claude", "agent-memory", AGENT)))
    # pesquisa: pontuação num transcript sintético no formato do stream-json (subagente = parent_tool_use_id)
    q = "calagem padrão do lote"

    def tr(order, cited_id):
        sub = "toolu_agent"
        use_s = {"type": "tool_use", "id": "s1", "name": "Bash",
                 "input": {"command": '.swarm/bin/cs-mem search "%s" --agent %s' % (q, AGENT)}}
        res_s = {"type": "tool_result", "tool_use_id": "s1", "content": "[decision] decision.ab12: Calagem padrão 180"}
        use_e = {"type": "tool_use", "id": "e1", "name": "Write",
                 "input": {"file_path": "/x/src/cultivo/calagem.py", "content": "CALAGEM_PADRAO_G = 180\n"}}
        use_sub = {"type": "tool_use", "id": "b1", "name": "Bash", "input": {"command": (
            '.swarm/bin/cs-state submit --task T --handoff-notes \'consultei: "%s" -> %s (efeito: 180 g)\'' % (q, cited_id))}}
        seq = [use_s, res_s, use_e] if order == "busca-antes" else [use_e, use_s, res_s]
        msgs = [{"type": "assistant" if c["type"] == "tool_use" else "user", "parent_tool_use_id": sub,
                 "message": {"content": [c]}} for c in seq + [use_sub]]
        return msgs

    trail_ok = '{"kind": "search", "agent": "%s", "query": "%s", "hits": 1}' % (AGENT, q)
    m_ok = tr("busca-antes", "decision.ab12")
    s_ok = score_search([], trail_ok, declared(texts_for_declaration(trail_ok, m_ok)), m_ok)
    ck("pesquisa: busca ANTES da 1ª edição + ID saído do tool_result + tema no rastro = coerente",
       s_ok["pesquisou_de_fato"] and s_ok["declarou"] and s_ok["id_saiu_da_busca"] and s_ok["coerente"]
       and s_ok["fonte_ordem"] == "transcript", json.dumps(s_ok, ensure_ascii=False)[:220])
    m_dep = tr("edita-antes", "decision.ab12")
    s_dep = score_search([], trail_ok, declared(texts_for_declaration(trail_ok, m_dep)), m_dep)
    ck("pesquisa: busca DEPOIS de editar não conta como pesquisou de fato", not s_dep["pesquisou_de_fato"])
    m_inv = tr("busca-antes", "decision.inventado")
    s_inv = score_search([], trail_ok, declared(texts_for_declaration(trail_ok, m_inv)), m_inv)
    ck("pesquisa: ID que não saiu da busca não é coerente", s_inv["id_saiu_da_busca"] is False and not s_inv["coerente"])
    s_forj = score_search([], "", declared('consultei: "%s" -> decision.ab12 (efeito)' % q))
    ck("pesquisa: declarou sem pesquisar não é coerente", s_forj["declarou"] and not s_forj["coerente"] and not
       s_forj["pesquisou_de_fato"])
    s_nada = score_search([], "", declared("consultei: nada — escopo trivial"))
    ck("pesquisa: 'consultei: nada' é declaração sem consulta", s_nada["declarou_nada"] and not s_nada["coerente"])
    s_obs = score_search(obs, "", [])
    ck("pesquisa: sem transcript do subagente, a ordem vem do obs.jsonl", s_obs["fonte_ordem"] == "obs" and
       s_obs["pesquisou_de_fato"])
    add_search_decision(r2)
    ck("decisão da pesquisa registrada no cs-mem", "180" in T.mem_ok(r2, "search", "calagem padrão do lote"))
    det = detection(r2, tid2, False, [LESSON_TOKEN])
    ck("detecção roda verify/check/validate sem API", set(det["gates"]) == {"verify", "check", "validate"},
       json.dumps({k: v["rc"] for k, v in det["gates"].items()}))
    fake = [{"cenario": "c", "config": "depois", "rep": i, "variante": "V1", "classe": c, "aplicacao": c == "X",
             "entrega": {"entregue": True, "citou": i == 0, "canal_caderno": True, "canal_brief": True},
             "deteccao": {"acusou": c != "X" and i == 2}, "pesquisa": score_search([], "", [], []), "rc": 0,
             "is_error": False, "custo_usd": 0.1} for i, c in enumerate(("X", "X", "Y"))]
    rows = placar(fake)
    ck("placar agrega (n, x_aplicado, taxa, detecção)", rows[0]["n"] == 3 and rows[0]["x_aplicado"] == 2 and
       rows[0]["taxa"] == 0.667 and rows[0]["taxa_deteccao"] == 1.0, json.dumps(rows[0])[:200])
    ck("resumo legível com critério de parada", "Critério de parada" in resumo(rows))
    # mudança oficial: a linha que derrubou a base (message é string) e a origem das negações
    bad_line = {"type": "system", "subtype": "permission_denied",
                "message": "Permission to use Bash has been denied. IMPORTANT: ..."}
    sub = "toolu_x"
    msgs = [bad_line, {"type": "system", "subtype": "init", "message": None}, {"type": "user", "message": "texto"},
            {"type": "assistant", "parent_tool_use_id": sub, "message": {"content": [
                {"type": "tool_use", "id": "a1", "name": "Bash", "input": {"command": "python3 -m unittest x; echo $?"}}]}},
            {"type": "user", "parent_tool_use_id": sub, "message": {"content": [
                {"type": "tool_result", "tool_use_id": "a1", "content": "Permission to use Bash has been denied."}]}},
            {"type": "assistant", "parent_tool_use_id": sub, "message": {"content": [
                {"type": "tool_use", "id": "a2", "name": "Bash", "input": {"command": ".swarm/bin/cs-state verify"}}]}},
            {"type": "user", "parent_tool_use_id": sub, "message": {"content": [
                {"type": "tool_result", "tool_use_id": "a2", "content":
                    "PreToolUse:Bash hook error: [cs-guard.sh pre-bash]: cs-guard BLOQUEOU: subagente não roda"}]}},
            {"type": "result", "total_cost_usd": 0.1, "permission_denials": [
                {"tool_name": "Bash", "tool_use_id": "a1", "tool_input": {"command": "python3 -m unittest x; echo $?"}},
                {"tool_name": "Bash", "tool_use_id": "a2", "tool_input": {"command": ".swarm/bin/cs-state verify"}}]}]
    neg = []
    try:
        evs = tool_events(msgs)
        so = search_order(msgs, [])
        neg = permission_denials(msgs)
        ok = len(evs) == 4 and so["fonte_ordem"] == "transcript" and [d["origem"] for d in neg] == ["permissao",
                                                                                                    "produto"]
        info = json.dumps([(d["origem"], d["comando"][:30]) for d in neg], ensure_ascii=False)
    except Exception as e:  # o defeito da base: AttributeError aqui
        ok, info = False, "%s: %s" % (type(e).__name__, e)
    ck("parser tolera message str/linha inesperada; negação separada por origem (allow-list × hook do produto)",
       ok, info)
    ck("aborto cedo: Bash negado pela allow-list no 1º despacho aborta; negado só pelo cs-guard não",
       early_abort({"negacoes": neg if ok else []}) and not early_abort({"negacoes": [d for d in (neg if ok else [])
                                                                                    if d["origem"] == "produto"]}))
    nr = dict(not_run("depois", 0, 1, "X", "tb", out), cenario="c")
    rows_nr = placar([nr] + fake)
    ck("NOT_RUN fica fora do n e é contado à parte", rows_nr[0]["n"] == 3 and rows_nr[0]["not_run"] == 1)
    al = allowed_for(r1)
    ck("allow-list cobre o composto que foi negado (python3 …; echo …) e os binários por caminho absoluto, sem bypass",
       "Bash(echo *)" in al and "Bash(python3 *)" in al and any(r1 in a and "cs-mem" in a for a in al)
       and "bypassPermissions" not in " ".join(claude_argv("x", args, r1)), " ".join(al[-2:]))
    if args.sonda_api:
        okp, info = api_probe(args, tpl, out)
        ck("SONDA API (1 despacho %s, ≤ US$ %.2f): o subagente roda Bash no alvo sem negação da allow-list"
           % (args.sonda_model, args.sonda_budget), okp, info)
    n_bad = sum(1 for c in checks if not c[1])
    print("offline-check: %d/%d OK" % (len(checks) - n_bad, len(checks)))
    return 1 if n_bad else 0


SONDA_TASK = ('Rode exatamente estes comandos, um por vez, com a ferramenta Bash: (1) .swarm/bin/cs-mem search '
              '"calagem" --agent dev-cultivo  (2) python3 -m unittest tests.test_ok; echo "EXIT:$?"  (3) git status '
              '--short. Depois acrescente a linha "# sonda" ao fim de src/cultivo/clima.py e submeta pelo cs-state '
              'submit conforme o seu brief, com --handoff-notes "consultei: nada — sonda".')


def api_probe(args, tpl, out):
    """1 despacho barato (modelo da sonda, teto de US$) pelo caminho real: o subagente roda cs-mem, python3 com
    composto e git no alvo; passa se os três rodaram (PostToolUse do subagente) e nenhuma negação veio da allow-list."""
    root = os.path.join(out, "_sonda", "alvo")
    shutil.rmtree(os.path.dirname(root), ignore_errors=True)
    shutil.copytree(tpl, root, symlinks=True)
    args._sonda_model, args._sonda_budget = args.sonda_model, args.sonda_budget
    try:
        r = run_dispatch(args, root, os.path.dirname(root), "Sonda de permissões", "src/cultivo/clima.py", SONDA_TASK)
    finally:
        args._sonda_model = args._sonda_budget = None
    ran = [x.get("input") or "" for x in r["obs"] if x.get("tool") == "Bash" and x.get("agent_type") == AGENT]
    need = {"cs-mem search": any("cs-mem" in c and "search" in c for c in ran),
            "python3+echo": any("unittest" in c and "echo" in c for c in ran),
            "git": any("git status" in c for c in ran)}
    perm = [d for d in r["negacoes"] if d["origem"] == "permissao"]
    info = json.dumps({"rodou": need, "negado_allowlist": [d["comando"] for d in perm],
                       "negado_produto": [d["comando"][:60] for d in r["negacoes"] if d["origem"] == "produto"],
                       "custo_usd": r["custo_usd"], "rc": r["rc"]}, ensure_ascii=False)
    with open(os.path.join(out, "_sonda", "sonda.json"), "w", encoding="utf-8") as fh:
        fh.write(info)
    return all(need.values()) and not perm, info


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out")
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--max-turns", type=int, default=None)
    ap.add_argument("--max-budget-usd", type=float, default=None)
    ap.add_argument("--usd-por-despacho", type=float, default=None)
    ap.add_argument("--configs", default=",".join(CONFIGS))
    ap.add_argument("--claude", default=os.environ.get("CLAUDE_BIN", "claude"))
    ap.add_argument("--skill", default=T.SKILL)
    ap.add_argument("--allow-ancestor-claude", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--offline-check", action="store_true")
    ap.add_argument("--termos", type=int, default=T.BIG_N, help="termos de glossário a mais no molde (escala real)")
    ap.add_argument("--sonda-api", action="store_true",
                    help="com --offline-check: 1 despacho real e barato confirma Bash do subagente no alvo")
    ap.add_argument("--sonda-model", default="haiku")
    ap.add_argument("--sonda-budget", type=float, default=0.2)
    args = ap.parse_args(argv)
    args.configs = [c for c in args.configs.split(",") if c]
    unknown = [c for c in args.configs if c not in CONFIGS + OPTIONAL_CONFIGS]
    if unknown:
        ap.error("configs desconhecidas: %s" % unknown)
    if args.dry_run:
        print_plan(args)
        return 0
    if not args.out:
        ap.error("--out é obrigatório (fora de qualquer projeto com CLAUDE.md)")
    os.environ.setdefault("CS_ORACLE_TMP", os.path.join(os.path.realpath(args.out), "_tmp"))
    if args.offline_check:
        return offline_check(args)
    return real(args)


if __name__ == "__main__":
    sys.exit(main())
