"""engine — motor ÚNICO das máquinas (machines.json5): guardas mecânicas, efeitos, commit encadeado.

Toda mudança de estado passa por `commit()` (lock → board fresco → checagem board×cadeia → guardas →
ops → events.jsonl encadeado → board.json5 atômico). As guardas citadas em machines.json5 são
implementadas em GUARDS; uma guarda que falta é erro (fail-closed).
"""
import os
import re
import shlex
import shutil
import subprocess
import time

import hcore
from hcore import Refused, StateError

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
DELEG_RE = re.compile(r"(?<![\w.-])([A-Za-z0-9][A-Za-z0-9_-]*(?:-[A-Za-z0-9_]+)*\.d\d+)(?![\w-])")
# delegação de task da ÁRVORE: <EPC|SPR|FEA|US|BUG|FIX-nnn>/<nn>[-rN].dK (o id da árvore tem "/")
TREE_DELEG_RE = re.compile(r"(?<![\w./-])((?:[A-Z]{2,5}-\d{3}|\d{4}-\d{2}-\d{2}-\d{2})/\d{2}(?:-r\d+)?\.d\d+)(?![\w-])")
SHELL_CHARS = re.compile(r"[|&;<>()$`*?~{}\n\\\"']")
VAGUE = re.compile(r"^\s*(ok|funciona|works|done|feito|tudo certo|deve funcionar|it works)\s*\.?\s*$", re.I)
GHERKIN = re.compile(r"\b(dado|given)\b.*\b(quando|when)\b.*\b(ent[aã]o|then)\b", re.I | re.S)
TASK_TYPES = ("BE", "FE", "QA", "ARCH", "PO", "SEC", "OPS", "DOC", "HARNESS")


# ================================================================ contexto
class Ctx(object):
    def __init__(self, root, board, actor="lead"):
        self.root = root
        self.paths = hcore.state_paths(root)
        self.board = board
        self.actor = actor
        self.cfg = hcore.load_config(root)
        self.team = hcore.load_team(root)
        self.M = hcore.machines()
        self._facts = None
        self._collision = None
        self.warnings = []

    @property
    def facts(self):
        if self._facts is None:
            self._facts = hcore.load_facts(self.root)
        return self._facts

    def cls(self, name):
        return self.M["classes"].get(name or "pequena") or self.M["classes"]["pequena"]

    def find(self, kind, eid):
        return hcore.find(self.board, kind, eid)

    def session_of(self, task):
        return self.find("session", task.get("session")) if task.get("session") else None

    def task_class(self, task):
        s = self.session_of(task)
        return task.get("class") or (s or {}).get("class") or "pequena"

    def agent_kind(self, name):
        a = hcore.team_agent(self.team, name)
        return (a or {}).get("kind")

    def territory(self, name):
        a = hcore.team_agent(self.team, name)
        return list((a or {}).get("territory") or [])

    def collision(self):
        if self._collision is None:
            kd = self.paths["knowledge_dir"]
            p = hcore.first_existing(os.path.join(kd, "collision.json5"), os.path.join(kd, "collision.json"))
            self._collision = hcore.read_any(p) if p else False
        return self._collision or None


def latest_deleg(task):
    ds = task.get("delegations") or []
    return ds[-1] if ds else None


def active_deleg(task, states=None):
    d = latest_deleg(task)
    if d and (states is None or d["state"] in states):
        return d
    return None


def all_delegs(board):
    for t in board["tasks"]:
        for d in t.get("delegations") or []:
            yield t, d


def ref(kind, eid):
    return "%s:%s" % (kind, eid)


# ================================================================ execução de comandos (verify/DoR/DoD)
def needs_shell(cmd):
    return bool(SHELL_CHARS.search(cmd))


def run_cmd(root, cmd, timeout, shell=None):
    """Executa SEMPRE via shell (/bin/sh -c) no cwd do alvo (H-1): atribuição de variável (`PYTHONPATH=src python3 …`),
    `&&`, aspas e pipes funcionam e o exit code REAL é propagado (127 só quando o programa de fato não existe).
    `shell` fica na assinatura por compatibilidade; o comando nunca é quebrado por shlex/execve.
    Registra exit, duração, sha da saída (bytes) e do comando."""
    shell = True
    argv = ["/bin/sh", "-c", cmd]
    t0 = time.time()
    timed_out = False
    try:
        p = subprocess.run(argv, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout,
                           env=dict(os.environ, CS_HARNESS_VERIFY="1", PYTHONDONTWRITEBYTECODE="1"))
        code, out = p.returncode, p.stdout or b""
    except subprocess.TimeoutExpired as e:
        code, out, timed_out = 124, (e.output or b"") + b"\n[timeout]", True
    except OSError as e:
        code, out = 127, ("[não executável: %s]" % e).encode("utf-8")
    return {"cmd": cmd, "shell": shell, "exit_code": code, "duration_s": round(time.time() - t0, 3),
            "output_sha256": hcore.sha256_bytes(out), "command_sha256": hcore.sha256_bytes(cmd.encode("utf-8")),
            "timed_out": timed_out, "tail": out[-1500:].decode("utf-8", "replace"), "at": hcore.now_iso()}


def executable_problem(root, cmd):
    """None se o comando é executável (não prosa); senão o motivo."""
    if not isinstance(cmd, str) or not cmd.strip():
        return "verification_command vazio"
    try:
        toks = shlex.split(cmd)
    except ValueError as e:
        return "verification_command não tokeniza (%s)" % e
    first = None
    for t in toks:
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t):
            continue
        first = t
        break
    if not first:
        return "verification_command sem programa"
    if first in ("test", "[", "true", "false", "cd", "!", "set"):
        return None
    if "/" in first:
        p = first if os.path.isabs(first) else os.path.join(root, first)
        if os.path.isfile(p):
            return None
        return "programa %r não existe" % first
    if shutil.which(first):
        return None
    words = len(cmd.split())
    return "programa %r não encontrado no PATH%s" % (first, " (parece prosa)" if words > 6 else "")


def resolve_test(cfg, test_id):
    """Comando de um teste por id (verified_by test:<id>). None se nenhum runner casa."""
    for r in cfg.get("test_runners") or []:
        m = re.match(r["match"], test_id)
        if not m:
            continue
        if r.get("shell"):
            return m.groupdict().get("cmd") or test_id
        return " ".join(shlex.quote(a.replace("{test}", test_id)) for a in r["argv"])
    return None


# D-1-03: protected_paths são provados PELO MOTOR no verify (cmds.diff_check), contra o que ESTA delegação mudou
# (fora do território: fotografia do despacho; dentro: base da task, D-0-13) — nunca por checagem crua da árvore no
# verification_command (`git status --porcelain`/`git diff --quiet` sobre os protected), que reprova a task pela sujeira
# legítima de uma task-irmã em voo. O sufixo antigo (motor ≤ D-1-02) é removido na geração/amend e na execução.
PROTECT_MARK = ' && test -z "$(git status --porcelain -- '
RAW_TREE_CHECK = re.compile(r"git\s+(status\s+--porcelain|diff\s+(--\S+\s+)*--quiet)")


def strip_protection(cmd):
    """verification_command sem o sufixo legado de checagem crua da árvore."""
    return cmd.split(PROTECT_MARK)[0] if cmd else cmd


def with_protection(cmd, protected):
    """Comando gerado: o do brief, SEM checagem de árvore (protected_paths: o motor prova no verify)."""
    return strip_protection(cmd)


def raw_tree_check_problem(vc, protected):
    """Checagem crua escrita no brief (o sufixo legado o motor já remove na execução e no brief do subagente)."""
    vc = strip_protection(vc)
    if protected and vc and RAW_TREE_CHECK.search(vc):
        return ("verification_command com checagem crua da árvore inteira (git status --porcelain / git diff --quiet): "
                "reprova a task pela sujeira legítima de task-irmã em voo — protected_paths são provados pelo motor "
                "contra o que ESTA delegação mudou; tire a checagem (cs-state amend --field verification_command)")
    return None


# ================================================================ git
def git(root, args, timeout=60):
    try:
        p = subprocess.run(["git"] + args, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        return p.returncode, p.stdout.decode("utf-8", "replace")
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, str(e)


def git_dirty(root):
    """{path: sha256|None} dos arquivos sujos/não rastreados (z-terminated, robusto a espaços)."""
    code, _ = git(root, ["rev-parse", "--is-inside-work-tree"])
    if code != 0:
        return None
    try:
        p = subprocess.run(["git", "status", "--porcelain", "-z", "--untracked-files=all"], cwd=root,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if p.returncode != 0:
        return None
    out, items = p.stdout.decode("utf-8", "replace").split("\0"), {}
    i = 0
    while i < len(out):
        e = out[i]
        if len(e) < 4:
            i += 1
            continue
        st, path = e[:2], e[3:]
        if "R" in st or "C" in st:
            i += 1  # próximo item é a origem
        full = os.path.join(root, path)
        items[path] = hcore.sha256_file(full) if os.path.isfile(full) else None
        i += 1
    return items


def tree_sha(root, paths):
    h = __import__("hashlib").sha256()
    for rel in sorted(set(paths)):
        full = os.path.join(root, rel)
        h.update(("%s\0%s\n" % (rel, hcore.sha256_file(full) if os.path.isfile(full) else "missing")).encode("utf-8"))
    return h.hexdigest()


def files_in_scope(root, patterns):
    """Arquivos existentes que casam com allowed_paths (walk limitado aos prefixos literais)."""
    out = set()
    for p in patterns or []:
        lp = hcore.literal_prefix(p).rstrip("/")
        base = os.path.join(root, lp) if lp else root
        if os.path.isfile(base):
            out.add(lp)
            continue
        if not os.path.isdir(base):
            continue
        for dp, dns, fns in os.walk(base):
            dns[:] = [d for d in dns if d not in (".git", "node_modules", hcore.STATE_DIR)]
            for fn in fns:
                rel = os.path.relpath(os.path.join(dp, fn), root).replace(os.sep, "/")
                if hcore.path_matches(rel, p):
                    out.add(rel)
            if len(out) > 5000:
                break
    return sorted(out)


# ================================================================ base da TASK (D-0-13)
# "Mudança da TASK" = arquivo de allowed_paths cujo conteúdo difere do que tinha no 1º dispatch da task: se o arquivo
# já estava sujo naquele dispatch, vale o sha256 fotografado então; senão, o conteúdo no commit HEAD daquele dispatch
# (ausente no HEAD e presente agora = mudou; presente no HEAD e apagado = mudou). A base fica na TASK (change_base) e é
# fixa entre retry / retomada / reroute — a delegação continua com o seu baseline só para julgar o que está FORA do
# território. Boards antigos (sem change_base) usam task_change_base() com fallback derivado do 1º evento
# delegation.dispatch da task (baseline daquele evento + HEAD vigente no instante dele); sem esse evento → None
# (o verify cai no comportamento antigo: só a fotografia da delegação).
CHANGE_BASE_FIRST = "first-dispatch"
CHANGE_BASE_FALLBACK = "fallback:first-dispatch-event"


def git_head(root):
    code, out = git(root, ["rev-parse", "--verify", "-q", "HEAD"])
    return out.strip() if code == 0 and out.strip() else None


def new_change_base(root, dirty):
    """Base fixada no 1º dispatch da task (dirty = fotografia git_dirty desse dispatch)."""
    if dirty is None:
        return None
    return {"head": git_head(root), "dirty": dict(dirty), "source": CHANGE_BASE_FIRST, "at": hcore.now_iso()}


def _head_at(root, at):
    """Commit HEAD vigente no instante `at` (ISO UTC do motor) — aproximação pelo committer date."""
    if not isinstance(at, str) or len(at) < 19:
        return None
    when = at[:19].replace("T", " ") + " +0000"
    code, out = git(root, ["rev-list", "-1", "--before=%s" % when, "HEAD"])
    return out.strip() if code == 0 and out.strip() else None


def fallback_change_base(root, task):
    """Board antigo: base derivada do 1º evento delegation.dispatch da task (events.jsonl). None se impossível."""
    ids = {d["id"] for d in task.get("delegations") or []}
    if not ids:
        return None
    try:
        recs, _, _ = hcore.read_chain(hcore.state_paths(root)["events"])
    except (OSError, ValueError):
        return None
    for r in recs:
        if r.get("type") != "delegation.dispatch" or r.get("entity") not in ids:
            continue
        snap = None
        for op in r.get("ops") or []:
            if isinstance(op, list) and len(op) >= 4 and op[0] == "set" and op[2] == "baseline":
                snap = op[3]
        if not isinstance(snap, dict) or snap.get("__nogit__"):
            return None
        head = _head_at(root, r.get("at"))
        if head is None:
            return None
        return {"head": head, "dirty": snap, "source": CHANGE_BASE_FALLBACK, "at": r.get("at")}
    return None


def task_change_base(root, task):
    return task.get("change_base") or fallback_change_base(root, task)


def _git_oid(root, args):
    code, out = git(root, args)
    return out.strip() if code == 0 and out.strip() else None


def task_changed_files(root, cb, candidates):
    """Subconjunto de `candidates` cujo conteúdo atual difere da base da task `cb`."""
    snap, head = cb.get("dirty") or {}, cb.get("head")
    out = set()
    for f in sorted(set(candidates)):
        full = os.path.join(root, f)
        exists = os.path.isfile(full)
        if f in snap:
            if (hcore.sha256_file(full) if exists else None) != snap[f]:
                out.add(f)
            continue
        base_oid = _git_oid(root, ["rev-parse", "--verify", "-q", "%s:%s" % (head, f)]) if head else None
        if base_oid is None or not exists:
            if (base_oid is None) != (not exists):
                out.add(f)
            continue
        if _git_oid(root, ["hash-object", "--", f]) != base_oid:
            out.add(f)
    return out


def task_base_candidates(root, cb):
    """Arquivos que podem diferir da base: sujos na base + os que mudaram entre o HEAD da base e o HEAD atual."""
    out = {k for k in (cb.get("dirty") or {}) if k != "__nogit__"}
    head = cb.get("head")
    if head:
        code, txt = git(root, ["diff", "--name-only", "-z", "--no-renames", head, "HEAD", "--"])
        if code == 0:
            out |= {p for p in txt.split("\0") if p}
    return out


# ================================================================ guardas
GUARDS = {}


def guard(name):
    def deco(fn):
        GUARDS[name] = fn
        return fn
    return deco


def _nonempty(v):
    return isinstance(v, str) and v.strip()


@guard("reason_present")
def g_reason(ctx, kind, ent, a):
    if _nonempty(a.get("reason")):
        return []
    if kind == "mandato":  # M5: recusa nomeia a guarda (stderr `guarda <nome>: <problema>`)
        return ["guarda reason_present: --reason é obrigatório (motivo gravado no evento do mandato)"]
    return ["--reason é obrigatório (motivo gravado no evento)"]


@guard("note_present")
def g_note(ctx, kind, ent, a):
    return [] if _nonempty(a.get("note")) else ["--note obrigatório (confirmação literal do usuário)"]


@guard("why_present")
def g_why(ctx, kind, ent, a):
    return [] if _nonempty(a.get("why")) else ["--why obrigatório: grave o critério da classe"]


@guard("class_valid")
def g_class_valid(ctx, kind, ent, a):
    c = a.get("class")
    return [] if c in ctx.M["classes"] else ["--class deve ser uma de %s" % ", ".join(ctx.M["classes"])]


@guard("class_set")
def g_class_set(ctx, kind, ent, a):
    return [] if ent.get("class") else ["sessão sem classe: rode cs-state session triage --class <c> --why <...>"]


@guard("class_is_question")
def g_q(ctx, kind, ent, a):
    return [] if ent.get("class") == "pergunta" else ["answer só para classe pergunta (atual: %s)" % ent.get("class")]


@guard("class_not_question")
def g_nq(ctx, kind, ent, a):
    return ["classe pergunta não planeja: use cs-state session answer"] if ent.get("class") == "pergunta" else []


def session_tasks(ctx, sid):
    return [t for t in ctx.board["tasks"] if t.get("session") == sid]


@guard("plan_recorded")
def g_plan(ctx, kind, ent, a):
    ts = session_tasks(ctx, ent["id"])
    if not ts:
        return ["plano vazio: adicione tasks com cs-state add task --session %s ..." % ent["id"]]
    bad = [t["id"] for t in ts if (latest_deleg(t) or {}).get("state") == "PLANNED"]
    return ["tasks sem brief válido (rode cs-state ready --task <id>): %s" % ", ".join(bad)] if bad else []


def scoped_invariants(task):
    return [i for i in (task.get("briefing") or {}).get("invariants") or [] if isinstance(i, dict) and not i.get("global")]


@guard("plan_fits_class")
def g_plan_fits(ctx, kind, ent, a):
    c = ctx.cls(ent.get("class"))
    ts = session_tasks(ctx, ent["id"])
    probs = []
    if "max_tasks" in c and len(ts) > c["max_tasks"]:
        probs.append("classe %s admite ≤%d task(s); plano tem %d — reclassifique (session triage)" % (ent["class"], c["max_tasks"], len(ts)))
    for t in ts:
        if c.get("single_literal_file") and (len(t["allowed_paths"]) != 1 or hcore.has_wild(t["allowed_paths"][0])):
            probs.append("trivial exige 1 arquivo explícito em allowed_paths (%s tem %s)" % (t["id"], t["allowed_paths"]))
        if c.get("no_invariants") and scoped_invariants(t):
            probs.append("trivial não pode tocar invariante (%s toca %s) — classe risco" % (
                t["id"], ", ".join(i["id"] for i in scoped_invariants(t))))
    if c.get("max_dev_agents"):
        devs = {t["agent"] for t in ts if ctx.agent_kind(t["agent"]) in (None, "dev")}
        if len(devs) > c["max_dev_agents"]:
            probs.append("classe pequena admite 1 território; plano usa %s — classe feature" % sorted(devs))
    for k in c.get("require_kinds_before_dev") or []:
        if not any(ctx.agent_kind(t["agent"]) == k for t in ts):
            probs.append("classe %s exige task de agente kind=%s (ex.: po) no plano" % (ent["class"], k))
    frozen = ctx.cfg.get("frozen_paths") or []
    for t in ts:
        if frozen and hcore.scopes_overlap(t["allowed_paths"], frozen) and ent.get("class") != "risco":
            probs.append("%s toca área congelada %s — classe risco + confirmação" % (t["id"], frozen))
    return probs


def collision_pairs(ctx):
    col = ctx.collision()
    if not col:
        return None
    pairs = col.get("do_not_parallelize") or []
    out = []
    for p in pairs:
        if isinstance(p, dict):
            a, b = p.get("a") or (p.get("pair") or [None, None])[0], p.get("b") or (p.get("pair") or [None, None])[1]
            out.append((a, b, p))
        elif isinstance(p, (list, tuple)) and len(p) >= 2:
            out.append((p[0], p[1], {}))
    return out


def collision_reason(ctx, agent_a, agent_b):
    """Motivo (str) se o par de territórios está em do_not_parallelize; None se não; '' se arquivo ausente."""
    pairs = collision_pairs(ctx)
    if pairs is None:
        return ""
    for a, b, meta in pairs:
        if {a, b} == {agent_a, agent_b} or {a, b} & {agent_a} and {a, b} & {agent_b} and agent_a != agent_b:
            nums = []
            for k in ("deps", "dependency", "edges", "co_change", "support", "confidence", "boundary_files", "score"):
                if k in meta:
                    nums.append("%s=%s" % (k, meta[k]))
            return "colisão %s×%s (%s)" % (agent_a, agent_b, ", ".join(nums) or "do_not_parallelize")
    return None


def warn_no_collision(ctx):
    msg = "collision.json5 ausente: paralelismo decidido só por disjunção de allowed_paths"
    if msg not in ctx.warnings:
        ctx.warnings.append(msg)
        try:
            hcore.ledger_append(ctx.root, {"kind": "warning", "reason": msg})
        except Exception:
            pass


@guard("waves_disjoint")
def g_waves(ctx, kind, ent, a):
    ts = session_tasks(ctx, ent["id"])
    probs = []
    for i in range(len(ts)):
        for j in range(i + 1, len(ts)):
            x, y = ts[i], ts[j]
            if x.get("wave", 1) != y.get("wave", 1) or x.get("readonly") or y.get("readonly"):
                continue
            if hcore.scopes_overlap(x["allowed_paths"], y["allowed_paths"]):
                probs.append("wave %s: %s e %s têm allowed_paths sobrepostos — separe em waves" % (x.get("wave", 1), x["id"], y["id"]))
            elif x["agent"] != y["agent"]:
                r = collision_reason(ctx, x["agent"], y["agent"])
                if r == "":
                    warn_no_collision(ctx)
                elif r:
                    probs.append("wave %s: %s e %s não paralelizam: %s" % (x.get("wave", 1), x["id"], y["id"], r))
    return probs


@guard("risk_confirmed")
def g_risk(ctx, kind, ent, a):
    if ctx.cls(ent.get("class")).get("user_confirmation") and not ent.get("confirmation"):
        return ["classe risco exige confirmação do usuário: cs-state session confirm --note '<frase do usuário>'"]
    return []


@guard("no_delegation_in_flight")
def g_no_flight(ctx, kind, ent, a):
    if kind == "mandato":
        import auto
        return auto.g_no_flight(ctx, kind, ent, a)
    fl = [d["id"] for t in session_tasks(ctx, ent["id"]) for d in t.get("delegations") or []
          if d["state"] in ("DISPATCHED", "RETURNED", "VERIFIED", "REVIEWED", "BRIEFED")]
    return ["delegações ainda abertas: %s" % ", ".join(fl)] if fl else []


@guard("all_tasks_closed")
def g_closed(ctx, kind, ent, a):
    op = [t["id"] for t in session_tasks(ctx, ent["id"]) if t["status"] not in ("ACCEPTED", "BLOCKED", "DROPPED")]
    return ["tasks não fechadas: %s" % ", ".join(op)] if op else []


@guard("reviewer_is_gate")
def g_gate(ctx, kind, ent, a):
    by = a.get("by")
    if ctx.team is None:
        return ["team.json5 ausente: impossível provar que o revisor é gate (fail-closed)"]
    if by not in hcore.gate_agents(ctx.team):
        return ["%r não é agente gate em team.json5 (gates: %s)" % (by, ", ".join(sorted(hcore.gate_agents(ctx.team))) or "nenhum")]
    return []


@guard("reviewer_not_author")
def g_not_author(ctx, kind, ent, a):
    return ["revisor não pode ser o autor (%s)" % ent["agent"]] if a.get("by") == ent["agent"] else []


@guard("verdict_valid")
def g_verdict(ctx, kind, ent, a):
    return [] if a.get("verdict") in hcore.verdicts() else ["veredito deve ser um de %s" % "|".join(hcore.verdicts())]


@guard("findings_present")
def g_findings(ctx, kind, ent, a):
    return [] if _nonempty(a.get("findings")) else ["--findings obrigatório (achados gravados, mesmo em PASS)"]


@guard("pipeline_satisfied")
def g_pipeline(ctx, kind, ent, a):
    c = ctx.cls(ent.get("class"))
    probs = []
    ts = session_tasks(ctx, ent["id"])
    for t in ts:
        d = latest_deleg(t)
        if t["status"] not in ("ACCEPTED", "DROPPED") and (d or {}).get("state") != "ESCALATED":
            probs.append("%s não ACCEPTED, DROPPED nem ESCALATED" % t["id"])
    if c.get("final_review"):
        ok = [r for r in ent.get("reviews") or [] if r["verdict"] == "PASS"]
        if not ok:
            probs.append("classe %s exige review final PASS de gate: cs-state session review --by <gate> --verdict PASS --findings ..." % ent["class"])
    return probs


# ---- delegação
def brief_problems(ctx, task, agent=None):
    """Brief válido (§8-quinquies + brief-schema.json5). Lista de problemas acionáveis."""
    agent = agent or task["agent"]
    P = []
    if not _nonempty(task.get("title")):
        P.append("title vazio")
    quick = is_quick(task) or is_tree_task(task)
    if not _nonempty(task.get("goal")):
        P.append("goal vazio: diga o resultado e o PORQUÊ (decisão/fato que sustenta)")
    if is_tree_task(task):
        pass  # task da árvore: o pai é a pasta (feature/sprint/story/avulsa); DoR por tipo já conferido no `start`
    elif quick:
        if not str(task.get("story") or "").startswith(AVULSA_PREFIX):
            P.append("task avulsa sem story implícita %s<sessão>" % AVULSA_PREFIX)
    elif not task.get("story") or not ctx.find("story", task["story"]):
        P.append("task sem story válida (toda task pertence a US/BUG/FIX)")
    if ctx.team is None:
        P.append("team.json5 ausente: não dá para checar território (fail-closed)")
    elif not hcore.team_agent(ctx.team, agent):
        P.append("agente %r não existe em team.json5" % agent)
    elif ctx.agent_kind(agent) == "gate":
        P.append("agente gate não recebe task de escrita")
    terr = ctx.territory(agent)
    ap = task.get("allowed_paths") or []
    if not ap:
        P.append("allowed_paths vazio (sempre arquivos explícitos ou diretório estreito)")
    for p in ap:
        try:
            hcore.norm_rel(p)
        except StateError as e:
            P.append(str(e))
            continue
        if hcore.literal_prefix(p) == "" or p.strip("/") in ("**", "*", "**/*", "src/**", "lib/**", "app/**"):
            P.append("allowed_path amplo demais: %r (use arquivos explícitos)" % p)
        elif hcore.is_reserved(p):
            P.append("allowed_path em área reservada do harness: %r" % p)
        elif terr and not hcore.pattern_within(p, terr):
            P.append("allowed_path %r fora do território de %s (%s)" % (p, agent, ", ".join(terr)))
        elif not terr and ctx.team is not None:
            P.append("%s sem território em team.json5" % agent)
    for p in task.get("protected_paths") or []:
        if hcore.scopes_overlap([p], ap) and any(hcore.path_matches(hcore.norm_rel(x).rstrip("/"), p) for x in ap if not hcore.has_wild(x)):
            P.append("protected_path %r contém allowed_path" % p)
    vc = task.get("verification_command") or ""
    ep = executable_problem(ctx.root, vc)
    if ep:
        P.append(ep)
    rt = raw_tree_check_problem(vc, task.get("protected_paths"))
    if rt:
        P.append(rt)
    acs = task.get("acceptance_criteria") or []
    if not acs:
        P.append("acceptance_criteria vazio")
    ids = set()
    for ac in acs:
        if not isinstance(ac, dict) or not _nonempty(ac.get("id")) or not _nonempty(ac.get("criterion")):
            P.append("AC sem id/criterion: %r" % (ac,))
            continue
        if ac["id"] in ids:
            P.append("AC id duplicado %s" % ac["id"])
        ids.add(ac["id"])
        if len(ac["criterion"].strip()) < 12 or VAGUE.match(ac["criterion"]):
            P.append("%s não é testável (critério vago)" % ac["id"])
        vb = ac.get("verified_by") or ""
        if vb == "verification_command" or vb == "reviewer":
            pass
        elif vb.startswith("test:"):
            if not resolve_test(ctx.cfg, vb[5:]):
                P.append("%s: nenhum test_runner resolve %r (config.json5 test_runners)" % (ac["id"], vb))
        else:
            P.append("%s: verified_by deve ser verification_command | test:<id> | reviewer" % ac["id"])
    br = task.get("briefing") or {}
    refs = br.get("references") or []
    if not refs and not quick:
        P.append("briefing.references vazio (âncoras arquivo:linha de padrão a seguir)")
    for r in refs:
        f = r.split(":")[0]
        if not os.path.exists(os.path.join(ctx.root, f)):
            P.append("referência inexistente: %s" % r)
    if not ((br.get("scope") or {}).get("out")) and not quick:
        P.append("briefing.scope.out vazio (fora de escopo e por quê)")
    need = {i["id"] for i in required_invariants(ctx, ap)}
    have = {i.get("id") for i in br.get("invariants") or [] if isinstance(i, dict)}
    if need - have:
        P.append("invariantes do escopo não anexados: %s (rode cs-state amend ou re-add)" % ", ".join(sorted(need - have)))
    return P


def required_invariants(ctx, allowed_paths):
    """Invariantes/regras (rules, business_rules) cujo scope toca allowed_paths, + invariants do agente em team."""
    out = []
    for f in ctx.facts.values():
        if hcore.fact_category(f) not in ("rule", "business_rule"):
            continue
        sc = hcore.fact_scope(f)
        if hcore.scopes_overlap(sc or ["**"], allowed_paths):
            out.append({"id": f["id"], "text": hcore.fact_text(f)[:300], "global": hcore.is_global_scope(sc),
                        "category": hcore.fact_category(f)})
    return sorted(out, key=lambda x: x["id"])


@guard("brief_valid")
def g_brief(ctx, kind, ent, a):
    task = hcore.task_of_deleg(ctx.board, ent["id"])
    return brief_problems(ctx, task, ent["agent"])


@guard("session_executing")
def g_sess_exec(ctx, kind, ent, a):
    task = hcore.task_of_deleg(ctx.board, ent["id"])
    if is_tree_task(task):
        return []  # árvore: "qualquer alteração exige pelo menos uma task — e nada além disso" (sem sessão M1)
    s = ctx.session_of(task)
    if not s:
        return ["task %s sem sessão M1 (cs-state session start)" % task["id"]]
    if s["state"] != "EXECUTING":
        return ["sessão %s em %s; despacho só em EXECUTING (cs-state session execute)" % (s["id"], s["state"])]
    if s.get("class") == "pergunta":
        return ["classe pergunta não delega"]
    return []


@guard("deps_accepted")
def g_deps(ctx, kind, ent, a):
    task = hcore.task_of_deleg(ctx.board, ent["id"])
    bad = [d for d in task.get("depends_on") or [] if (ctx.find("task", d) or {}).get("status") != "ACCEPTED"]
    return ["dependências não ACCEPTED: %s" % ", ".join(bad)] if bad else []


@guard("one_in_flight_per_agent")
def g_one(ctx, kind, ent, a):
    other = [d["id"] for t, d in all_delegs(ctx.board) if d["agent"] == ent["agent"] and d["state"] == "DISPATCHED" and d["id"] != ent["id"]]
    other += [c["id"] for c in consults_in_flight(ctx.board, ent["agent"])]
    return ["%s já tem delegação em voo (%s): o guard identifica o ator pelo agent_type — espere o retorno" % (ent["agent"], ", ".join(other))] if other else []


@guard("no_parallel_collision")
def g_collision(ctx, kind, ent, a):
    task = hcore.task_of_deleg(ctx.board, ent["id"])
    if task.get("readonly"):
        return []
    probs = []
    for t, d in all_delegs(ctx.board):
        if d["state"] != "DISPATCHED" or d["id"] == ent["id"] or t.get("readonly"):
            continue
        if hcore.scopes_overlap(t["allowed_paths"], task["allowed_paths"]):
            probs.append("colide com %s em voo (allowed_paths sobrepostos)" % d["id"])
        elif d["agent"] != ent["agent"]:
            r = collision_reason(ctx, d["agent"], ent["agent"])
            if r == "":
                warn_no_collision(ctx)
            elif r:
                probs.append("não paralelizar com %s: %s" % (d["id"], r))
    return probs


@guard("class_dispatch_order")
def g_order(ctx, kind, ent, a):
    task = hcore.task_of_deleg(ctx.board, ent["id"])
    c = ctx.cls(ctx.task_class(task))
    req = c.get("require_kinds_before_dev") or []
    if not req or ctx.agent_kind(ent["agent"]) not in (None, "dev"):
        return []
    sid = task.get("session")
    probs = []
    for k in req:
        if not any(ctx.agent_kind(t["agent"]) == k and t["status"] == "ACCEPTED" for t in session_tasks(ctx, sid)):
            probs.append("classe %s: task de kind=%s (po) precisa estar ACCEPTED antes do dev" % (ctx.task_class(task), k))
    return probs


@guard("budget_available")
def g_budget(ctx, kind, ent, a):
    import autonomy
    P = autonomy.budget_problems(ctx)
    if ctx.board.get("mandatos"):
        import auto  # M5: nó do mandato só despacha em RUNNING, fora de ramo congelado e abaixo do corte de 80%
        P += auto.dispatch_problems(ctx, ent)
    return P


@guard("model_declared")
def g_model(ctx, kind, ent, a):
    import router
    return router.dispatch_model_problems(ctx, ent, a)


# ---- consulta (M4) e task avulsa: as três faixas de interação
AVULSA_PREFIX = "STORY-AVULSA-"
CONSULT_RE = re.compile(r"(?<![\w-])(ASK-\d+)(?![\w-])")


def is_quick(task):
    return bool((task or {}).get("quick"))


def is_tree_task(task):
    """Task M2 nascida de `cs-state start` de uma task da árvore (id da árvore, sem sessão M1 nem story do board)."""
    return bool((task or {}).get("tree"))


def lane_of(ctx, klass):
    """Faixa pela classe da triagem (machines.json5 classes.<c>.lane)."""
    return (ctx.M["classes"].get(klass or "") or {}).get("lane") or ("completo" if klass else None)


def consults_in_flight(board, agent):
    return [c for c in board.get("consults") or [] if c.get("agent") == agent and c.get("state") == "DISPATCHED"]


@guard("consult_agent_free")
def g_consult_free(ctx, kind, ent, a):
    busy = [d["id"] for t, d in all_delegs(ctx.board) if d["agent"] == ent["agent"] and d["state"] == "DISPATCHED"]
    busy += [c["id"] for c in consults_in_flight(ctx.board, ent["agent"]) if c["id"] != ent["id"]]
    return ["%s já tem trabalho em voo (%s): o guard identifica o ator pelo agent_type — espere o retorno" % (
        ent["agent"], ", ".join(busy))] if busy else []


@guard("consult_model_declared")
def g_consult_model(ctx, kind, ent, a):
    if (ent.get("route") or {}).get("model") == "inherit":
        return []
    return [] if _nonempty(a.get("model")) else [
        "despacho de consulta sem model: passe model=%r" % ((ent.get("route") or {}).get("model") or "sonnet")]


def quick_problems(ctx, session, agent, allowed_paths):
    """Promoção obrigatória da faixa avulsa: >1 território/agente, invariante ou área congelada → suba a classe."""
    up = "suba a classe: `cs-state session triage --class feature|risco --why '...'` e siga o fluxo completo"
    P = []
    ap = [hcore.norm_rel(p) for p in allowed_paths or []]
    owners = set()
    for p in ap:
        for ag in (ctx.team or {}).get("agents") or []:
            if not isinstance(ag, dict) or ag.get("kind") == "gate":
                continue
            terr = list(ag.get("territory") or [])
            if terr and (hcore.pattern_within(p, terr) or hcore.scopes_overlap([p], terr)):
                owners.add(ag.get("name"))
    if len(owners) > 1:
        P.append("task avulsa toca %d territórios (%s) — %s" % (len(owners), ", ".join(sorted(owners)), up))
    elif owners and agent not in owners:
        P.append("allowed_paths é território de %s, não de %s (exige >1 agente) — %s" % (", ".join(sorted(owners)), agent, up))
    others = {t["agent"] for t in session_tasks(ctx, session["id"])} - {agent}
    if others:
        P.append("sessão já tem task avulsa de %s; um 2º agente (%s) — %s" % (", ".join(sorted(others)), agent, up))
    inv = [i["id"] for i in required_invariants(ctx, ap) if not i.get("global")]
    if inv:
        P.append("task avulsa toca invariante %s — %s" % (", ".join(inv), up))
    frozen = ctx.cfg.get("frozen_paths") or []
    if frozen and hcore.scopes_overlap(ap, frozen):
        P.append("task avulsa toca área congelada %s — %s" % (", ".join(frozen), up))
    c = ctx.cls(session.get("class"))
    if not P and c.get("single_literal_file") and (len(ap) != 1 or hcore.has_wild(ap[0])):
        P.append("classe %s aceita 1 arquivo explícito (%s) — suba a classe: `cs-state session triage --class pequena`"
                 % (session.get("class"), ap))
    if not P and "max_tasks" in c and len(session_tasks(ctx, session["id"])) >= c["max_tasks"]:
        P.append("classe %s admite ≤%d task(s) — suba a classe: `cs-state session triage --class pequena`"
                 % (session.get("class"), c["max_tasks"]))
    return P


SUBMISSION_KEYS = ("files_changed", "checks_run", "risks", "handoff_notes")


@guard("submission_complete")
def g_sub(ctx, kind, ent, a):
    s = a.get("submission")
    if not isinstance(s, dict):
        return ["submission ausente"]
    P = []
    for k in SUBMISSION_KEYS:
        if k not in s:
            P.append("submission.%s ausente" % k)
    if not s.get("files_changed"):
        P.append("submission.files_changed vazio (abstenção? use cs-state abstain)")
    if not s.get("checks_run"):
        P.append("submission.checks_run vazio (rode o verification_command antes de submeter)")
    return P


@guard("files_in_allowed_paths")
def g_files(ctx, kind, ent, a):
    task = hcore.task_of_deleg(ctx.board, ent["id"])
    P = []
    for f in (a.get("submission") or {}).get("files_changed") or []:
        try:
            rel = hcore.norm_rel(f)
        except StateError as e:
            P.append(str(e))
            continue
        if not hcore.matches_any(rel, task["allowed_paths"]):
            P.append("%s fora de allowed_paths" % rel)
        if hcore.matches_any(rel, task.get("protected_paths") or []):
            P.append("%s está em protected_paths" % rel)
    return P


@guard("command_exit_zero")
def g_exit(ctx, kind, ent, a):
    g = a.get("_gate") or {}
    b = g.get("build")
    if not b:
        return ["verify sem execução registrada"]
    return [] if b["exit_code"] == 0 else ["verification_command exit=%s (sha saída %s): %s" % (
        b["exit_code"], b["output_sha256"][:12], b.get("tail", "")[-300:])]


@guard("ac_tests_green")
def g_ac(ctx, kind, ent, a):
    return ["AC %s: teste %s exit=%s" % (r["ac"], r["test"], r["exit_code"]) for r in (a.get("_gate") or {}).get("ac_tests") or []
            if r["exit_code"] != 0]


@guard("diff_within_allowed_paths")
def g_diff(ctx, kind, ent, a):
    return list((a.get("_gate") or {}).get("diff_problems") or [])


@guard("lessons_check_pass")
def g_lessons(ctx, kind, ent, a):
    return list((a.get("_gate") or {}).get("lesson_failures") or [])


def current_waiver(task):
    """verify_waiver válido para a tentativa atual (exceção de AMBIENTE com portão humano) ou None."""
    w = task.get("verify_waiver") or None
    b = ((task.get("gate_report") or {}).get("build") or {})
    if w and w.get("attempt") == task["attempts"] and b.get("attempt") == task["attempts"] and \
            w.get("output_sha256") == b.get("output_sha256") and w.get("failure_kind") == "environment":
        return w
    return None


def verify_failure(ctx, task):
    """(failure_kind, ferramentas) do último verify da tentativa atual. Board antigo sem `failure_kind`: reclassifica
    pela saída gravada no evento delegation.verify (mesma heurística)."""
    gr = task.get("gate_report") or {}
    b = gr.get("build") or {}
    if b.get("attempt") != task["attempts"]:
        return None, []
    if "failure_kind" in gr:
        return gr.get("failure_kind"), list(gr.get("missing_tools") or [])
    if b.get("exit_code") == 0 and not any(r.get("exit_code") for r in gr.get("ac_tests") or []):
        return None, []
    import envfail
    ids = {d["id"] for d in task.get("delegations") or []}
    recs, _, _ = hcore.read_chain(ctx.paths["events"])
    for r in reversed(recs):
        if r.get("type") == "delegation.verify" and r.get("entity") in ids:
            g = (r.get("data") or {}).get("gate") or {}
            if g.get("output_sha256") != b.get("output_sha256"):
                return envfail.CODE, []
            runs = [{"exit_code": g.get("exit_code"), "tail": g.get("tail")}] + list(g.get("ac_tests") or [])
            if any(x.get("exit_code") and "tail" not in x for x in runs[1:]):
                return envfail.CODE, []  # AC sem saída gravada: sem prova de ambiente
            return envfail.classify(ctx.root, runs, list(g.get("diff_problems") or []) + list(g.get("lesson_failures") or []))
    return envfail.CODE, []


@guard("verify_pass")
def g_vpass(ctx, kind, ent, a):
    task = hcore.task_of_deleg(ctx.board, ent["id"])
    b = ((task.get("gate_report") or {}).get("build") or {})
    if b.get("attempt") == task["attempts"] and b.get("exit_code") != 0 and current_waiver(task):
        return []  # exceção de ambiente registrada por humano (review por gate continua obrigatória)
    if b.get("attempt") != task["attempts"] or b.get("exit_code") != 0:
        return ["sem verify PASS (exit 0) na tentativa %d: cs-state verify --task %s" % (task["attempts"], task["id"])]
    return []


@guard("reverify_allowed")
def g_reverify(ctx, kind, ent, a):
    task = hcore.task_of_deleg(ctx.board, ent["id"])
    sub = task.get("submission") or {}
    if sub.get("attempt") != task["attempts"] or sub.get("abstain"):
        return ["sem submission da tentativa %d para verificar de novo (use retry/reroute/drop)" % task["attempts"]]
    if ent.get("state") == "REJECTED" and verify_failure(ctx, task)[0] != "environment":
        return ["reverify de REJECTED só quando o verify falhou por AMBIENTE; falha de código → cs-state retry"]
    return []


@guard("verify_failed_by_environment")
def g_vfail_env(ctx, kind, ent, a):
    task = hcore.task_of_deleg(ctx.board, ent["id"])
    b = ((task.get("gate_report") or {}).get("build") or {})
    if b.get("attempt") != task["attempts"]:
        return ["nenhum verify na tentativa %d: rode cs-state verify/reverify antes de pedir exceção" % task["attempts"]]
    fk, tools = verify_failure(ctx, task)
    if fk != "environment":
        return ["exceção de verify só para falha de AMBIENTE (ferramenta/módulo ausente); esta falha é %s "
                "(teste/asserção/escopo nunca recebe exceção)" % (fk or "inexistente")]
    ev = a.get("evidence") or ""
    names = [x for x in (t.split(":", 1)[-1] for t in tools) if x and x != "?"]
    if names and not any(n in ev for n in names):
        return ["--evidence deve conter a saída do verify que mostra a ferramenta ausente (%s)" % ", ".join(names)]
    return []


NOT_HUMAN = {"lead", "tech-lead", "orchestrator", "orquestrador", "main", "principal", "claude", "assistant", "agent",
             "agente", "ai", "llm", "bot"}


@guard("waiver_by_human")
def g_waiver_human(ctx, kind, ent, a):
    by = (a.get("by") or "").strip()
    if not by:
        return ["--by obrigatório: o HUMANO que assume a exceção"]
    if by.lower() in NOT_HUMAN or by == ctx.actor or (ctx.team and hcore.team_agent(ctx.team, by)):
        return ["--by %r não é humano: o orquestrador/agentes não se auto-dispensam do verify (peça ao humano)" % by]
    return []


@guard("evidence_present")
def g_evidence(ctx, kind, ent, a):
    return [] if _nonempty(a.get("evidence")) else ["--evidence obrigatório (saída do verify mostrando a falha de ambiente)"]


@guard("tree_unchanged")
def g_tree(ctx, kind, ent, a):
    task = hcore.task_of_deleg(ctx.board, ent["id"])
    b = ((task.get("gate_report") or {}).get("build") or {})
    files = b.get("tree_files") or []
    if b.get("tree_sha256") and tree_sha(ctx.root, files) != b["tree_sha256"]:
        return ["árvore mudou desde o verify (tree_sha256 diverge): rode verify de novo"]
    return []


def current_reviews(task):
    latest = {}
    for r in task.get("reviews") or []:
        if r.get("attempt") == task["attempts"]:
            latest[r["by"]] = r
    return latest


def _attempt_reviews(task):
    return [r for r in task.get("reviews") or [] if r.get("attempt") == task["attempts"]]


def open_specialist_requests(task):
    """NEEDS_SPECIALIST ainda sem veredito posterior de OUTRO gate (na mesma tentativa) → [(by, review)]."""
    revs = _attempt_reviews(task)
    out = []
    for i, r in enumerate(revs):
        if r["verdict"] != "NEEDS_SPECIALIST":
            continue
        later = [x for x in revs[i + 1:] if x["by"] != r["by"] and x["verdict"] in ("PASS", "FAIL")]
        if not later:
            out.append((r["by"], r))
    return out


def review_outcome(task):
    """Precedência entre gates sobre os mesmos caminhos (fonte única):
    qualquer FAIL (último veredito de cada gate) vence; NEEDS_SPECIALIST em aberto roteia para outro gate e
    trava o aceite até o especialista dar PASS/FAIL; senão PASS. None = nenhuma review nesta tentativa."""
    latest = current_reviews(task)
    if not latest:
        return None
    if any(r["verdict"] == "FAIL" for r in latest.values()):
        return "FAIL"
    if open_specialist_requests(task):
        return "NEEDS_SPECIALIST"
    return "PASS"


@guard("reviews_satisfy_class")
def g_reviews(ctx, kind, ent, a):
    task = hcore.task_of_deleg(ctx.board, ent["id"])
    c = ctx.cls(ctx.task_class(task))
    need = int(c.get("min_gate_reviews", 1) if c.get("review_required", True) else 0)
    if current_waiver(task):
        need = max(need, 1)  # verify dispensado por ambiente: review por gate sempre obrigatória
    latest = current_reviews(task)
    gates = hcore.gate_agents(ctx.team) if ctx.team else set()
    ok = {b for b, r in latest.items() if r["verdict"] == "PASS" and b != ent["agent"] and b in gates}
    P = []
    if len(ok) < need:
        P.append("classe %s exige %d review(s) PASS de gate(s) distinto(s) ≠ autor; tem %d" % (ctx.task_class(task), need, len(ok)))
    for b, r in sorted(latest.items()):
        if r["verdict"] == "FAIL":
            P.append("review FAIL de %s pendente (FAIL vence): rejeite com os achados" % b)
    for b, _ in open_specialist_requests(task):
        P.append("review NEEDS_SPECIALIST de %s pendente: rotear para o especialista (outro gate) antes do aceite" % b)
    return P


def awaiting_human(ctx):
    """Estados da delegação que esperam a decisão humana (machines.json5 delegation.awaiting_human)."""
    return tuple(ctx.M["machines"]["delegation"].get("awaiting_human") or ())


@guard("retries_left")
def g_retries(ctx, kind, ent, a):
    if ent.get("state") in awaiting_human(ctx):
        return []  # retomada por decisão humana: não consome tentativa
    mx = int(ctx.M["limits"]["max_retries"])
    import autonomy
    mx = autonomy.retry_cap(ctx, mx)
    return [] if int(ent.get("retries") or 0) < mx else ["retries esgotados (%d): escale (cs-state escalate) ou reroute" % mx]


@guard("findings_attached")
def g_findings_att(ctx, kind, ent, a):
    task = hcore.task_of_deleg(ctx.board, ent["id"])
    if ent.get("state") in awaiting_human(ctx):
        if _nonempty(a.get("findings")):
            return []
        return ["retomar de %s exige a decisão do humano (--decision '<decisão>' ou --findings)" % ent.get("state")]
    if _nonempty(a.get("findings")) or _nonempty(task.get("reject_reason")):
        return []
    return ["retry exige os achados (--findings) ou reject_reason registrado"]


@guard("new_agent_valid")
def g_new_agent(ctx, kind, ent, a):
    if kind == "mandato":
        import auto
        return auto.g_new_agent(ctx, kind, ent, a)
    na = a.get("agent")
    task = hcore.task_of_deleg(ctx.board, ent["id"])
    if not na or not hcore.team_agent(ctx.team, na):
        return ["--agent deve existir em team.json5"]
    if na == ent["agent"]:
        return ["reroute para o mesmo agente; use retry"]
    terr = ctx.territory(na)
    ap = a.get("allowed_paths") or task["allowed_paths"]
    bad = [p for p in ap if not hcore.pattern_within(p, terr)]
    return ["allowed_paths fora do território de %s: %s (passe --allowed-path)" % (na, bad)] if bad else []


@guard("abstain_kind_valid")
def g_abs(ctx, kind, ent, a):
    return [] if a.get("abstain_kind") in ctx.M["abstain_kinds"] else ["--kind deve ser um de %s" % ", ".join(ctx.M["abstain_kinds"])]


# ---- processo (§8-septies)
@guard("epic_dor")
def g_epic_dor(ctx, kind, ent, a):
    P = []
    if not _nonempty(ent.get("objective")):
        P.append("épico sem objective")
    if not _nonempty(ent.get("metric")):
        P.append("épico sem métrica de sucesso (--metric)")
    return P


@guard("epic_dod")
def g_epic_dod(ctx, kind, ent, a):
    fs = [f for f in ctx.board["features"] if f.get("epic") == ent["id"]]
    if not fs:
        return ["épico sem features"]
    bad = [f["id"] for f in fs if f["state"] not in ("DONE", "DROPPED")]
    return ["features abertas: %s" % ", ".join(bad)] if bad else []


def run_acceptance(ctx, cmds):
    return [run_cmd(ctx.root, c, int(ctx.cfg.get("verify_timeout_s", 900))) for c in cmds]


@guard("feature_dor")
def g_feat_dor(ctx, kind, ent, a):
    P = []
    if not ent.get("epic") or not ctx.find("epic", ent["epic"]):
        P.append("feature sem épico válido")
    spec = ent.get("spec")
    if not spec or not os.path.isfile(os.path.join(ctx.root, spec)):
        P.append("spec inexistente: %r" % spec)
    for f in ent.get("acceptance_files") or []:
        if not os.path.isfile(os.path.join(ctx.root, f)):
            P.append("teste de aceite inexistente: %s" % f)
    cmds = ent.get("acceptance") or []
    if not cmds:
        P.append("feature sem critérios de aceite executáveis (--accept-cmd)")
    for c in cmds:
        ep = executable_problem(ctx.root, c)
        if ep:
            P.append("aceite %r: %s" % (c, ep))
    if P:
        return P
    runs = run_acceptance(ctx, cmds)
    a["_runs"] = runs
    for r in runs:
        if r["exit_code"] == 0:
            P.append("teste de aceite já PASSA hoje (%s): DoR exige teste vermelho" % r["cmd"])
    return P


@guard("parent_epic_active")
def g_parent_epic(ctx, kind, ent, a):
    e = ctx.find("epic", ent.get("epic"))
    return [] if e and e["state"] == "ACTIVE" else ["épico %s não está ACTIVE" % ent.get("epic")]


@guard("feature_dod")
def g_feat_dod(ctx, kind, ent, a):
    st = [s for s in ctx.board["stories"] if s.get("feature") == ent["id"]]
    if not st:
        return ["feature sem stories"]
    bad = [s["id"] for s in st if s["state"] != "DONE"]
    if bad:
        return ["stories não DONE: %s" % ", ".join(bad)]
    runs = run_acceptance(ctx, ent.get("acceptance") or [])
    a["_runs"] = runs
    return ["aceite vermelho: %s exit=%s" % (r["cmd"], r["exit_code"]) for r in runs if r["exit_code"] != 0]


@guard("stories_have_dor")
def g_sprint_plan(ctx, kind, ent, a):
    P = []
    for sid in a.get("add") or []:
        s = ctx.find("story", sid)
        if not s:
            P.append("story %s inexistente" % sid)
        elif s["state"] != "READY":
            P.append("story %s sem DoR (estado %s): cs-state story ready --id %s" % (sid, s["state"], sid))
    return P


@guard("sprint_dor")
def g_sprint_dor(ctx, kind, ent, a):
    P = []
    if not _nonempty(ent.get("goal")):
        P.append("sprint sem meta (--goal)")
    if not ent.get("budget"):
        P.append("sprint sem orçamento (--budget tasks=N,attempts=2,minutes=M)")
    if not ent.get("stories"):
        P.append("sprint sem stories comprometidas (cs-state sprint plan --id %s --add US-n)" % ent["id"])
    for sid in ent.get("stories") or []:
        s = ctx.find("story", sid)
        if not s or s["state"] not in ("READY", "IN_PROGRESS"):
            P.append("story %s sem DoR" % sid)
    return P


@guard("sprint_review_recorded")
def g_sprint_rev(ctx, kind, ent, a):
    return [] if ent.get("review") else ["review não gravada: cs-state sprint review --id %s" % ent["id"]]


def story_tests(s):
    t = s.get("type")
    if t == "us":
        return [c.get("test") for c in s.get("criteria") or [] if c.get("test")]
    if t == "bug":
        return [s["failing_test"]] if s.get("failing_test") else []
    return [s["proving_test"]] if s.get("proving_test") else []


@guard("story_dor")
def g_story_dor(ctx, kind, ent, a):
    P = []
    if not ent.get("feature") or not ctx.find("feature", ent["feature"]):
        P.append("story sem feature válida")
    t = ent.get("type")
    if t == "us":
        for k in ("as_a", "i_want", "so_that"):
            if not _nonempty(ent.get(k)):
                P.append("US sem %s (Como/Quero/Para)" % k)
        crit = ent.get("criteria") or []
        if not crit:
            P.append("US sem critérios Gherkin")
        for c in crit:
            if not GHERKIN.search(c.get("gherkin") or ""):
                P.append("critério %s não é Gherkin (Dado/Quando/Então)" % c.get("id"))
            if not c.get("test") or not resolve_test(ctx.cfg, c["test"]):
                P.append("critério %s sem teste ligado resolvível" % c.get("id"))
    elif t == "bug":
        if not ent.get("repro"):
            P.append("BUG sem passos de reprodução")
        if ent.get("severity") not in ctx.M["severities"]:
            P.append("BUG sem severidade (%s)" % "|".join(ctx.M["severities"]))
        if not _nonempty(ent.get("environment")):
            P.append("BUG sem ambiente")
        cmd = resolve_test(ctx.cfg, ent.get("failing_test") or "")
        if not cmd:
            P.append("BUG sem teste que reproduz (--failing-test) resolvível")
        elif not P:
            r = run_cmd(ctx.root, cmd, int(ctx.cfg.get("verify_timeout_s", 900)))
            a["_runs"] = [r]
            if r["exit_code"] == 0:
                P.append("teste do BUG passa hoje: não reproduz (TDD de correção exige vermelho)")
    elif t == "fix":
        fx = ent.get("fixes") or ""
        okf = False
        if fx.startswith("BUG-"):
            okf = bool(ctx.find("story", fx))
        elif fx.startswith("review:"):
            tk = ctx.find("task", fx.split(":", 1)[1])
            okf = bool(tk and any(r["verdict"] != "PASS" for r in tk.get("reviews") or []))
        elif fx.startswith("forensic:"):
            okf = os.path.isfile(os.path.join(ctx.root, fx.split(":", 1)[1]))
        if not okf:
            P.append("FIX sem fixes: válido (BUG-n | review:<task> com achado | forensic:<arquivo>)")
        if not resolve_test(ctx.cfg, ent.get("proving_test") or ""):
            P.append("FIX sem teste que prova (--proving-test) resolvível")
    else:
        P.append("tipo de story inválido: %r" % t)
    return P


@guard("story_tasks_accepted")
def g_story_tasks(ctx, kind, ent, a):
    ts = [t for t in ctx.board["tasks"] if t.get("story") == ent["id"]]
    if not ts:
        return ["story sem tasks"]
    live = [t for t in ts if t["status"] != "DROPPED"]
    if not live:
        return ["story só tem tasks descartadas (DROPPED)"]
    bad = [t["id"] for t in live if t["status"] != "ACCEPTED"]
    return ["tasks não ACCEPTED: %s" % ", ".join(bad)] if bad else []


@guard("story_dod")
def g_story_dod(ctx, kind, ent, a):
    P = g_story_tasks(ctx, kind, ent, a)
    if P:
        return P
    cmds = [resolve_test(ctx.cfg, t) for t in story_tests(ent)]
    if ent.get("type") in ("bug", "fix"):
        reg = ent.get("regression") or ctx.cfg.get("regression_command")
        if not reg:
            return ["%s exige suíte de regressão (--regression ou config regression_command)" % ent["type"].upper()]
        cmds.append(reg)
    runs = run_acceptance(ctx, [c for c in cmds if c])
    a["_runs"] = runs
    return ["vermelho: %s exit=%s" % (r["cmd"], r["exit_code"]) for r in runs if r["exit_code"] != 0]


# ---- M5 mandato (modo autônomo): guardas registradas AQUI (engine.GUARDS, decorador @guard) — a implementação mora
# em auto.py (carregado sob demanda, sem import circular). Guardas compartilhadas com outras máquinas
# (reason_present, new_agent_valid, no_delegation_in_flight) despacham por `kind == "mandato"` na própria função.
M5_GUARDS = ("target_exists", "class_allowed", "spec_present", "acceptance_executable", "acceptance_red", "no_open_mandate",
             "not_trivial", "by_human", "dag_acyclic", "dag_covers_acceptance", "nodes_in_territory", "nodes_fit_horizon",
             "plan_within_budget", "waves_computed", "lessons_consulted", "regression_green", "pending_nodes",
             "replan_trigger", "replans_left", "acceptance_all_green", "final_review_pass", "next_feature_queued",
             "replan_cites_evidence", "accepted_nodes_untouched", "plan_diff_recorded", "escalation_condition",
             "package_recorded", "choice_in_package", "decision_present", "in_flight_marked", "stamp_matches",
             "wrap_trigger", "report_generated", "open_items_returned")


def _m5_guard(name):
    def fn(ctx, kind, ent, a):
        import auto
        return auto.M5_GUARD_IMPL[name](ctx, kind, ent, a)
    fn.__name__ = "g_m5_" + name
    return fn


for _g in M5_GUARDS:
    guard(_g)(_m5_guard(_g))


# ================================================================ transição + commit
class Event(object):
    def __init__(self, typ, entity, ops, data=None):
        self.type, self.entity, self.ops, self.data = typ, entity, ops, data or {}


def check_guards_defined():
    missing = set()
    for m in hcore.machines()["machines"].values():
        for t in (m.get("transitions") or {}).values():
            for g in t.get("guards") or []:
                if g not in GUARDS:
                    missing.add(g)
    return sorted(missing)


def evaluate(ctx, kind, ent, tname, a):
    """(to, problems) sem efeitos. Usado por transition() e por why/next."""
    mname = hcore.KIND_MACHINE[kind]
    m = ctx.M["machines"][mname]
    t = (m.get("transitions") or {}).get(tname)
    if t is None:
        raise Refused("transição %r não existe em %s (válidas: %s)" % (tname, mname, ", ".join(m.get("transitions") or {})))
    cur = ent.get(m.get("field", "state"))
    if cur not in t["from"]:
        raise Refused("%s %s: transição %r inválida no estado %s (permitida de: %s)" % (
            mname, ent["id"], tname, cur, ", ".join(t["from"])), hint=hint_for(ctx, kind, ent))
    probs = []
    for g in t.get("guards") or []:
        fn = GUARDS.get(g)
        if fn is None:
            probs.append("guarda %s não implementada (fail-closed)" % g)
            continue
        probs.extend(fn(ctx, kind, ent, a))
    to = t["to"] if t["to"] != "=" else cur
    if to == "^":  # volta ao estado de onde veio (gravado em `anterior` ao entrar na espera/pausa)
        to = ent.get("anterior")
        if not to:
            raise Refused("%s %s: transição %r volta à origem, mas a origem não foi gravada (anterior ausente)" % (
                mname, ent["id"], tname))
    if probs:
        if t.get("on_guard_fail"):
            return t["on_guard_fail"], probs
        return None, probs
    return to, []


def transition(ctx, kind, eid, tname, a=None, extra=None):
    a = a if a is not None else {}
    ent = ctx.find(kind, eid)
    if ent is None:
        raise Refused("%s %s inexistente" % (kind, eid))
    to, probs = evaluate(ctx, kind, ent, tname, a)
    if to is None:
        raise Refused(probs, hint=hint_for(ctx, kind, ent))
    field = hcore.state_field(kind)
    ops = [["set", ref(kind, eid), field, to], ["set", ref(kind, eid), "updated_at", hcore.now_iso()]]
    if kind == "deleg":
        task = hcore.task_of_deleg(ctx.board, eid)
        ts = ctx.M["machines"]["delegation"]["drives_task"][to]
        if ts != task["status"] or ts == "VERIFYING":
            ops.append(["set", ref("task", task["id"]), "status", ts])
    if extra:
        ops.extend(extra(to, probs) or [])
    return Event("%s.%s" % (hcore.KIND_MACHINE[kind], tname), eid, ops, {"args": public_args(a), "problems": probs})


def promote(ctx, prior, kind, eid, tname, a=None, extra=None):
    """Promoção IMPLÍCITA de pai (story start/dispatch → feature IN_PROGRESS; accept → story IN_REVIEW; ...).

    Passa pela MESMA transição nomeada da máquina do pai (machines.json5 é a fonte única): as guardas são avaliadas
    num board de ensaio com os eventos filhos `prior` já aplicados. Se a máquina do pai recusar, a operação filha
    inteira é recusada com a mensagem da guarda do pai (nada é gravado — commit é tudo-ou-nada)."""
    import copy
    trial = Ctx(ctx.root, copy.deepcopy(ctx.board), ctx.actor)
    for ev in prior or []:
        hcore.apply_ops(trial.board, ev.ops)
    m = hcore.KIND_MACHINE[kind]
    try:
        return transition(trial, kind, eid, tname, a, extra)
    except Refused as e:
        raise Refused(["promoção implícita %s %s (%s.%s) recusada pela máquina do pai:" % (m, eid, m, tname)] + e.problems,
                      hint=e.hint)


def hierarchy_items(board):
    """Incoerências pai×filho (o que um atalho de guarda deixaria para trás), uma por item, estruturadas:
    {kind, id, state, parent_kind, parent, parent_state, problem}. `problem` é a mensagem do validador."""
    P = []
    for f in board.get("features") or []:
        if f.get("state") == "IN_PROGRESS":
            e = hcore.find(board, "epic", f.get("epic"))
            if not e or e.get("state") != "ACTIVE":
                est = (e or {}).get("state", "inexistente")
                P.append({"kind": "feature", "id": f["id"], "state": f["state"], "parent_kind": "epic",
                          "parent": f.get("epic"), "parent_state": est,
                          "problem": "feature %s IN_PROGRESS com épico %s em %s (parent_epic_active contornada)" % (
                              f["id"], f.get("epic"), est)})
    for s in board.get("stories") or []:
        if s.get("state") == "IN_PROGRESS" and s.get("feature"):
            f = hcore.find(board, "feature", s["feature"])
            if f and f.get("state") != "IN_PROGRESS":
                P.append({"kind": "story", "id": s["id"], "state": s["state"], "parent_kind": "feature",
                          "parent": f["id"], "parent_state": f.get("state"),
                          "problem": "story %s IN_PROGRESS com feature %s em %s (feature.start contornada)" % (
                              s["id"], f["id"], f.get("state"))})
    return P


def hierarchy_key(item):
    return tuple((item or {}).get(k) for k in ("kind", "id", "state", "parent_kind", "parent", "parent_state"))


def acked_hierarchy(events):
    """Chaves de incoerência de hierarquia reconhecidas por harness.legacy_ack (D-1-04) e AINDA VIGENTES: o
    reconhecimento vale só enquanto o item continuar o mesmo — qualquer mudança de estado do filho ou do pai depois
    do ack o caduca (uma incoerência que reapareça depois é nova e volta a ser acusada)."""
    live = {}
    for ev in events or []:
        if ev.get("type") == "harness.legacy_ack":
            for it in ((ev.get("data") or {}).get("args") or {}).get("hierarchy") or []:
                if isinstance(it, dict) and it.get("kind") in ("story", "feature"):
                    live[hierarchy_key(it)] = (ref(it["kind"], it.get("id")), ref(it.get("parent_kind"), it.get("parent")))
            continue
        if not live:
            continue
        touched = {op[1] for op in ev.get("ops") or []
                   if isinstance(op, list) and len(op) == 4 and op[0] == "set" and isinstance(op[1], str)
                   and op[1].split(":", 1)[0] in hcore.KIND_MACHINE
                   and op[2] == hcore.state_field(op[1].split(":", 1)[0])}
        if touched:
            live = {k: v for k, v in live.items() if not (set(v) & touched)}
    return set(live)


def hierarchy_problems(board, acked=None):
    """Pai em estado incompatível com o filho, menos as incoerências reconhecidas (acked: chaves de acked_hierarchy)."""
    return [it["problem"] for it in hierarchy_items(board) if hierarchy_key(it) not in (acked or ())]


def public_args(a):
    return {k: v for k, v in (a or {}).items() if not k.startswith("_")}


def hint_for(ctx, kind, ent):
    try:
        import views
        return views.next_for(ctx, kind, ent)
    except Exception:
        return None


def commit(root, actor, build, post=True):
    """build(ctx) -> [Event]. Tudo sob lock; nada é escrito se uma op for ilegal."""
    p = hcore.state_paths(root)
    if not os.path.isdir(p["state_dir"]):
        raise StateError("estado ausente (%s): rode cs-state init" % p["state_dir"])
    with hcore.file_lock(p["lock"]):
        board = hcore.load_board(root)
        tree_before = copy_tree(board) if p.get("tree") else None
        lh = hcore.last_hash(p["events"])
        if lh != board["last_event_hash"]:
            raise StateError("board×events divergentes (último hash %s ≠ board %s): rode validate --strict" % (lh[:12], board["last_event_hash"][:12]))
        ctx = Ctx(root, board, actor)
        events = build(ctx) or []
        import copy
        trial = copy.deepcopy(board)
        for ev in events:
            hcore.apply_ops(trial, ev.ops)
        written = []
        for ev in events:
            rec = {"at": hcore.now_iso(), "actor": actor, "type": ev.type, "entity": ev.entity, "ops": ev.ops, "data": ev.data}
            h, seq = hcore.append_chained(p["events"], rec)
            hcore.apply_ops(board, ev.ops)
            board["event_count"] = seq + 1
            board["last_event_hash"] = h
            rec["seq"] = seq
            written.append(rec)
        if written:
            hcore.save_board(root, board)
            if p.get("tree"):
                import tree  # materializa as pastas (backlog/state/archive) e o INDEX.md a partir da projeção
                tree.materialize(root, tree_before or {}, board)
            if any(str(r["type"]).startswith("mandato.") for r in written):
                import auto  # visão do mandato (M5): mandato.json5, plano.vN.json5, pacotes de escalada, relatório
                auto.materialize(root, board)
    if post and written:
        after_commit(root, board, written)
    return ctx, written


def copy_tree(board):
    import copy
    return copy.deepcopy(board.get("tree") or {})


def after_commit(root, board, written):
    """Memória episódica, lições automáticas, checkpoint autônomo, roteador. Falha aqui não desfaz estado."""
    try:
        import mem
    except ImportError:
        mem = None
    for rec in written:
        task = None
        if rec["entity"]:
            task = hcore.find(board, "task", rec["entity"]) or hcore.task_of_deleg(board, rec["entity"])
        try:
            if mem:
                mem.record_episode(root, _episode_view(rec, task), task)
                mem.capture_from_event(root, rec, task)
        except Exception as e:  # registrado; consolidate faz backfill
            try:
                hcore.ledger_append(root, {"kind": "warning", "reason": "memória: %s" % e})
            except Exception:
                pass
        try:
            if rec["type"] in ("delegation.accept", "delegation.reject", "delegation.return") or (
                    rec["type"] == "delegation.verify" and rec["data"].get("problems")):
                import router
                router.outcome_from_event(root, board, rec)
        except Exception as e:
            try:
                hcore.ledger_append(root, {"kind": "warning", "reason": "router: %s" % e})
            except Exception:
                pass
        if rec["type"] == "delegation.accept":
            try:
                import autonomy
                autonomy.checkpoint(root, rec)
            except Exception as e:
                try:
                    hcore.ledger_append(root, {"kind": "warning", "reason": "checkpoint: %s" % e})
                except Exception:
                    pass


def _episode_view(rec, task=None):
    """Adapta o evento genérico ao formato de episódio da memória."""
    typ = rec["type"].split(".")[-1]
    args = (rec.get("data") or {}).get("args") or {}
    data = {"reason": args.get("reason"), "verdict": args.get("verdict"), "by": args.get("by"),
            "findings": args.get("findings"), "kind": args.get("abstain_kind"), "submission": args.get("submission")}
    for op in rec["ops"]:
        if op[0] == "create" and op[1] == "task":
            typ, data["task"] = "add", op[3]
        if op[0] == "set" and op[2] == "gate_report":
            data["verification"] = {"exit": op[3]["build"]["exit_code"], "duration_s": op[3]["build"]["duration_s"],
                                    "cmd": op[3]["build"]["cmd"]}
        if op[0] == "set" and op[2] in ("state", "status"):
            data["to"] = op[3]
    if task and typ == "dispatch":
        data["attempt"] = task.get("attempts")
    return {"seq": rec["seq"], "at": rec["at"], "type": typ, "task": (task or {}).get("id") or rec["entity"],
            "actor": rec["actor"], "data": data}


def init_state(root):
    p = hcore.state_paths(root)
    os.makedirs(p["state_dir"], exist_ok=True)
    with hcore.file_lock(p["lock"]):
        if os.path.isfile(p["board"]) and os.path.isfile(p["events"]):
            return False
        if os.path.isfile(p["events"]) and not os.path.isfile(p["board"]):
            raise StateError("events.jsonl existe sem board: estado corrompido — não recrio por cima (rode validate)")
        board = hcore.new_board()
        h, seq = hcore.append_chained(p["events"], {"at": hcore.now_iso(), "actor": "install", "type": "init",
                                                     "entity": None, "ops": [], "data": {"schema_version": hcore.SCHEMA_VERSION}})
        board["event_count"], board["last_event_hash"] = seq + 1, h
        hcore.save_board(root, board)
    return True


# ================================================================ ids
def next_id(board, kind, prefix, width=0):
    lst = board[hcore.BOARD_LISTS[kind]]
    n = 0
    for e in lst:
        m = re.match(r"^%s-(\d+)" % re.escape(prefix), e["id"])
        if m:
            n = max(n, int(m.group(1)))
    return "%s-%s" % (prefix, str(n + 1).zfill(width) if width else n + 1)
