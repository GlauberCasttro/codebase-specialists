"""ORÁCULO — COBERTURA DAS MÁQUINAS DE ESTADO do harness (machines.json5), medida, não declarada.

Objetivo (founder): "todo o harness testado E2E e comprovado 100% funcional, principalmente a state machine".
Critério mecânico deste arquivo:
  1. O UNIVERSO é lido de machines.json5 EM TEMPO DE EXECUÇÃO (nada de lista fixa): toda máquina em `machines`
     (sessão, delegação, task, consulta, épico, feature, sprint, story, ... o que existir) + o bloco `autonomy`.
       * aresta    = (máquina, transição, estado de origem) para cada `from` de cada transição;
       * máquina só com `pairs` (task) = cada par legal (de → para) vira uma aresta "DE->PARA";
       * guarda    = (máquina, transição, guarda) para cada guarda listada na transição.
  2. Cada CENÁRIO roda a CLI real (engine/state.py) e o guard real (engine/guard.py, payloads de hook) em SUBPROCESSO,
     num repo git temporário (fixture.make_repo). O prefixo de montagem pode ser in-process (cmds/fixture, mesmo motor);
     SÓ o que passa pela CLI/hook em subprocesso conta para a matriz.
  3. A matriz é montada a partir de evidência:
       * events.jsonl do repo temporário (evento `<máquina>.<transição>` gravado = transição exercitada com sucesso;
         ops `set task:<id> status` = par da task exercitado);
       * autonomy.json5 antes/depois da chamada (máquina `autonomy`, que não grava estado em events.jsonl);
       * um OBSERVADOR no subprocesso: o processo filho roda `runpy` sobre o state.py/guard.py REAIS depois de embrulhar
         engine.transition/engine.evaluate/engine.GUARDS só para REGISTRAR (num .jsonl) qual guarda devolveu qual
         problema — não muda decisão nenhuma. Sem isso não há como atribuir uma recusa a UMA guarda (o motor não grava
         recusa em events.jsonl), e a atribuição exige também que o texto da guarda apareça no stderr real.
     Guarda OK     = a guarda devolveu [] numa transição que foi gravada.
     Guarda RECUSA = a guarda devolveu problemas e (a) a CLI saiu 1 / o hook pre-* saiu 2 com esse texto no stderr, ou
                     (b) a transição tem `on_guard_fail` e o evento gravou o destino de falha com esse problema
                     (delegation.verify → REJECTED: o verify reprovado é a recusa observável, exit 0 "REPROVOU").
  4. `test_cobertura_100` (classe TestZZCobertura, roda por último; se rodar isolado executa os cenários que faltam)
     agrega tudo e FALHA listando aresta/transição nunca exercitada, guarda nunca vista OK e guarda nunca vista
     RECUSANDO. Imprime o resumo (transições x/y, arestas x/y, guardas ok x/y, guardas recusa x/y).

Cenários "por adulteração" (defesa em profundidade): `verify_pass` e `sprint_review_recorded` NÃO recusam por nenhum
caminho legal da CLI (VERIFIED/REVIEWED só nascem com verify exit 0 ou waiver válido; REVIEW do sprint só nasce com
`review` gravado). `reviewer_not_author` só recusa SOZINHA se o autor virar gate depois do despacho (team.json5 editado).
Para provar que a guarda funciona, o cenário adultera o board.json5 (sem tocar events.jsonl) ou o team.json5 e exige a
recusa; depois restaura. Isso está documentado no relatório como achado (guarda inalcançável por caminho legal).

Recusa da CLI = exit 1 (hcore.Refused); recusa do hook pre-* = exit 2 (cs-guard BLOQUEOU). Exit 2 do argparse NÃO conta.
Este arquivo não edita o motor nem os testes existentes; só lê.

EXTENSÃO M5 (campanha-M5, mudança oficial — ver campanha-m5/oraculo/mudanca-oficial/PORQUE.md): a máquina `mandato`
(modo autônomo) mora em `machines.machines` e entra no MESMO universo e nos MESMOS critérios. Acréscimos, sem afrouxar
nada do que já existia:
  * `to: "^"` (volta ao estado de onde veio) — a aresta conta quando o destino gravado é um estado da máquina;
  * recusa INTERNA — o motor tenta uma transição por engine.transition, captura o Refused e segue por outra; conta como
    RECUSA quando o evento vencedor grava `data.guardas_recusadas: [{transicao, guarda, problema}]` com aquela guarda;
  * transição de CRIAÇÃO (`from: []`, ex.: mandato.propose) — não há entidade antes, o observador não vê
    engine.evaluate: aresta = (máquina, transição, None) pelo evento gravado; guarda OK = `data.guardas` do evento;
    guarda RECUSA = exit 1 sem recusa de outra máquina e a linha `guarda <nome>:` no stderr;
  * cenários m5_* (m5_cenarios.py) pela CLI real `cs-auto` (engine/auto.py) e pelos hooks reais;
  * exclusões M5 (só guardas sem caminho legal de recusa) entram apenas quando `mandato` existe em machines.json5.
"""
import collections
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import fixture  # noqa: E402
import hcore  # noqa: E402
import j5  # noqa: E402
from test_faixas_aceite import agent_payload  # noqa: E402

STATE = os.path.join(fixture.ENGINE, "state.py")
AUTO = os.path.join(fixture.ENGINE, "auto.py")
GUARD = os.path.join(fixture.ENGINE, "guard.py")
MACHINES = os.path.join(fixture.HARNESS, "machines.json5")
A = fixture.A
VERIFY = "python3 -m unittest discover -s tests -t ."
VERIFY_ENV = "sh tools/verify_env.sh"
AC = "AC-1|desconto aplicado ao total do pedido|test:tests.test_billing"
HUMAN = "founder"
VERIFY_ENV_SH = """#!/bin/sh
# simula dependência de AMBIENTE ausente: sai 127 até o marcador (fora do repo) existir
if [ ! -f "%s" ]; then
  echo "fake-dep: command not found" >&2
  exit 127
fi
exec python3 -m unittest discover -s tests -t .
"""

# ---------------------------------------------------------------------------------------------------------------
# EXCLUSÕES — chave → motivo. Só o que comprovadamente NÃO tem como ser exercitado nem por CLI, hook, relógio ou
# adulteração. Chaves: ("aresta", máquina, transição, origem) | ("guarda_ok"|"guarda_recusa", máquina, transição, guarda).
# ---------------------------------------------------------------------------------------------------------------
EXCLUSOES = {
    ("aresta", "task", "DRAFT->DRAFT", "DRAFT"):
        "par reflexivo de LEGALIDADE: engine.transition só grava `status` da task quando ele muda (exceto VERIFYING), "
        "e nenhum outro código grava status igual ao atual — o par existe em machines.json5 mas nenhum evento o produz",
    ("aresta", "task", "BLOCKED->BLOCKED", "BLOCKED"):
        "idem: par reflexivo de legalidade; ESCALATED/escalate sobre task já BLOCKED não reescreve o status",
}


# ---------------------------------------------------------------- iter14 (mudança oficial): o approve pede a SENHA
# `cs-auto approve` passou a exigir a senha do humano, digitada num terminal (ver campanha-iter14/oraculo/ESPEC.md).
# O oráculo faz o papel do humano: roda o approve num pseudo-terminal REAL (pty.fork) e digita SENHA_TESTE a cada
# prompt `SENHA...:`. Não há bypass no produto: a senha só vale porque CS_SENHA_FILE aponta para um registro PBKDF2
# gerado com ela (formato da ESPEC iter14 §2.1). Todas as asserções seguem iguais; só muda COMO o approve é digitado.
import atexit as _atexit  # noqa: E402
import hashlib as _hashlib  # noqa: E402
import pty as _pty  # noqa: E402
import re as _re  # noqa: E402
import select as _select  # noqa: E402
import signal as _signal  # noqa: E402
import time as _time  # noqa: E402
import unicodedata as _ud  # noqa: E402

SENHA_TESTE = "Mandato-Seguro-2026"
_SENHA_PROMPT = _re.compile(rb"SENHA[^\r\n:]*:")
_SENHA_FILE = []


def senha_file():
    """Registro de senha de teste (PBKDF2-SHA256, 600000 iterações), num diretório temporário fora do alvo."""
    if not _SENHA_FILE:
        d = tempfile.mkdtemp(prefix="cs-senha-teste-")
        _atexit.register(shutil.rmtree, d, True)
        sv, sk = os.urandom(16).hex(), os.urandom(16).hex()
        nb = _ud.normalize("NFC", SENHA_TESTE.strip()).encode("utf-8")
        reg = {"versao": 1, "kdf": "pbkdf2-sha256", "iter": 600000, "salt_verificador": sv, "salt_chave": sk,
               "verificador": _hashlib.pbkdf2_hmac("sha256", nb, bytes.fromhex(sv), 600000, dklen=32).hex(),
               "criada_em": "2026-10-05T00:00:00Z"}
        p = os.path.join(d, "senha.json")
        with open(p, "w") as f:
            json.dump(reg, f)
        os.chmod(p, 0o600)
        _SENHA_FILE.append(p)
    return _SENHA_FILE[0]


def is_approve(args):
    """O subcomando (depois de --root/--actor) é `approve`?"""
    args, i = list(args), 0
    while i < len(args):
        if args[i] in ("--root", "--actor"):
            i += 2
            continue
        if args[i].startswith(("--root=", "--actor=")):
            i += 1
            continue
        return args[i] == "approve"
    return False


def run_tty(argv, cwd, env, timeout=300):
    """Roda argv num pty real (stdin = tty controlador) digitando SENHA_TESTE a cada prompt. (exit, saída)."""
    pid, fd = _pty.fork()
    if pid == 0:
        try:
            os.chdir(cwd)
            os.execve(argv[0], argv, env)
        finally:
            os._exit(127)
    buf, seen, deadline = b"", 0, _time.time() + timeout
    try:
        while True:
            if _time.time() > deadline:
                os.kill(pid, _signal.SIGKILL)
                raise AssertionError("approve no tty não terminou em %ss: %r" % (timeout, buf[-500:]))
            r, _, _ = _select.select([fd], [], [], 0.1)
            if not r:
                continue
            try:
                data = os.read(fd, 4096)
            except OSError:
                break
            if not data:
                break
            buf += data
            n = len(_SENHA_PROMPT.findall(buf))
            while seen < n:
                os.write(fd, (SENHA_TESTE + "\n").encode("utf-8"))
                seen += 1
    finally:
        _, status = os.waitpid(pid, 0)
        os.close(fd)
    code = os.WEXITSTATUS(status) if os.WIFEXITED(status) else 128 + os.WTERMSIG(status)
    return code, buf.decode("utf-8", "replace").replace("\r\n", "\n")


# ================================================================ observador (roda no subprocesso, antes do script real)
SHIM = r'''
import json, os, runpy, sys
engine_dir, mem_dir, log, script = sys.argv[1:5]
sys.argv = [script] + sys.argv[5:]
for p in (mem_dir, engine_dir):
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)
import engine
import hcore
_tok, _frames = [], []
_orig_eval, _orig_tr = engine.evaluate, engine.transition

def _emit(rec):
    with open(log, "a") as f:
        f.write(json.dumps(rec, default=str) + "\n")

def transition(ctx, kind, eid, tname, a=None, extra=None):
    _tok.append(True)
    try:
        return _orig_tr(ctx, kind, eid, tname, a, extra)
    finally:
        _tok.pop()

def evaluate(ctx, kind, ent, tname, a):
    rec = None
    if _tok and _tok[-1]:
        _tok[-1] = False
        m = hcore.KIND_MACHINE[kind]
        field = ctx.M["machines"][m].get("field", "state")
        rec = {"machine": m, "transition": tname, "entity": ent.get("id"), "from": ent.get(field), "guards": {}}
    _frames.append(rec)
    try:
        to, probs = _orig_eval(ctx, kind, ent, tname, a)
    except Exception as e:
        if rec is not None:
            rec["error"] = str(e)
            _emit(rec)
        raise
    finally:
        _frames.pop()
    if rec is not None:
        rec["to"] = to
        rec["problems"] = list(probs or [])
        _emit(rec)
    return to, probs

def _wrap(name, fn):
    def w(ctx, kind, ent, a):
        out = fn(ctx, kind, ent, a)
        if _frames and _frames[-1] is not None:
            _frames[-1]["guards"][name] = [str(x) for x in (out or [])]
        return out
    return w

for _k in list(engine.GUARDS):
    engine.GUARDS[_k] = _wrap(_k, engine.GUARDS[_k])
engine.evaluate, engine.transition = evaluate, transition
runpy.run_path(script, run_name="__main__")
'''


# ================================================================ universo (lido de machines.json5 em tempo de execução)
def load_machines():
    return j5.load(MACHINES)


def universe(M=None):
    """(transições, arestas, guardas) esperadas. transições = {(m, t)}; arestas = {(m, t, de)}; guardas = {(m, t, g)}."""
    M = M or load_machines()
    trans, edges, guards = set(), set(), set()
    for mname, m in sorted(M["machines"].items()):
        for tname, t in sorted((m.get("transitions") or {}).items()):
            trans.add((mname, tname))
            for f in t.get("from") or [None]:  # from: [] = transição de CRIAÇÃO (aresta de None)
                edges.add((mname, tname, f))
            for g in t.get("guards") or []:
                guards.add((mname, tname, g))
        for pair in m.get("pairs") or []:
            k = "%s->%s" % (pair[0], pair[1])
            trans.add((mname, k))
            edges.add((mname, k, pair[0]))
    au = M.get("autonomy") or {}
    for tname, t in sorted((au.get("transitions") or {}).items()):
        trans.add(("autonomy", tname))
        for f in t.get("from") or []:
            edges.add(("autonomy", tname, f))
        for g in t.get("guards") or []:
            guards.add(("autonomy", tname, g))
    return trans, edges, guards


# ================================================================ matriz global (agregada por todos os cenários)
MATRIX = {"edge": {}, "guard_ok": {}, "guard_no": {}, "atalho": {}}
RESULTS = collections.OrderedDict()  # cenário → None (ok) | traceback
SCENARIOS = collections.OrderedDict()


def _mark(kind, key, who):
    MATRIX[kind].setdefault(key, who)


def _read_lines(path):
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def _autonomy_state(root):
    p = hcore.state_paths(root)["autonomy"]
    if not os.path.isfile(p):
        return None
    try:
        return (j5.load(p) or {}).get("state")
    except Exception:
        return None


def _states(root):
    """{"kind:id": estado} de todas as entidades do board (inclui delegações)."""
    try:
        b = hcore.load_board(root)
    except Exception:
        return {}
    out = {}
    for kind, lst in hcore.BOARD_LISTS.items():
        for e in b.get(lst) or []:
            out["%s:%s" % (kind, e["id"])] = e.get(hcore.state_field(kind))
    for t in b["tasks"]:
        for d in t.get("delegations") or []:
            out["deleg:%s" % d["id"]] = d.get("state")
    return out


class Step(object):
    def __init__(self, code, out, err, recs, events):
        self.code, self.out, self.err, self.recs, self.events = code, out, err, recs, events

    def refused_by(self):
        """{guarda: problemas} das avaliações recusadas nesta chamada."""
        out = {}
        for r in self.recs:
            if r.get("to") is None and not r.get("error"):
                for g, p in r["guards"].items():
                    if p:
                        out.setdefault(g, []).extend(p)
        return out


class H(object):
    """Contexto de um cenário: repos temporários + chamadas observadas (CLI/hook reais em subprocesso)."""

    def __init__(self, name):
        self.name = name
        self.tmp = []
        self.M = load_machines()

    def cleanup(self):
        for r in self.tmp:
            shutil.rmtree(r, ignore_errors=True)

    # ---------------------------------------------------------------- repos
    def repo(self, **kw):
        r = fixture.make_repo(**kw)
        self.tmp.append(r)
        return r

    def outside(self):
        d = os.path.realpath(tempfile.mkdtemp(prefix="cs-cov-env-"))
        self.tmp.append(d)
        return d

    # ---------------------------------------------------------------- execução observada
    def _run(self, root, script, args, stdin=None, env_extra=None):
        logd = tempfile.mkdtemp(prefix="cs-cov-log-")
        log = os.path.join(logd, "evals.jsonl")
        sp = hcore.state_paths(root)
        n_ev = len(_read_lines(sp["events"]))
        au0 = _autonomy_state(root)
        st0 = _states(root)
        env = dict(os.environ)
        for k in ("CLAUDE_PROJECT_DIR", "CS_ACTOR", "CS_GUARD_OFF"):
            env.pop(k, None)
        env["CS_SENHA_FILE"] = senha_file()  # iter14: registro da senha de teste (fora do alvo)
        env.update(env_extra or {})
        argv = [sys.executable, "-c", SHIM, fixture.ENGINE, fixture.MEMORY, log, script] + list(args)
        if script == AUTO and is_approve(args):  # iter14: o approve é digitado num terminal, com a senha
            code, out = run_tty(argv, root, env)
            p, err = subprocess.CompletedProcess(argv, code), out
        else:
            p = subprocess.run(argv, cwd=root, env=env, input=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               timeout=300)
            out, err = p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
        recs = _read_lines(log)
        shutil.rmtree(logd, ignore_errors=True)
        events = _read_lines(sp["events"])[n_ev:]
        self._account(p.returncode, err, recs, events, st0, au0, _autonomy_state(root), script == GUARD)
        return Step(p.returncode, out, err, recs, events)

    def _account(self, code, err, recs, events, st0, au0, au1, is_hook):
        Ms = self.M["machines"]
        written = {(e["type"], e.get("entity")): e for e in events}
        for r in recs:
            if r.get("error"):
                continue
            m, t = r["machine"], r["transition"]
            tdef = Ms[m]["transitions"][t]
            normal_to = r["from"] if tdef["to"] == "=" else tdef["to"]
            ev = written.get(("%s.%s" % (m, t), r["entity"]))
            volta = tdef["to"] == "^" and r.get("to") in (Ms[m].get("states") or [])  # "^": volta à origem
            if r.get("to") is not None and ev is not None:
                if (r["to"] == normal_to or volta) and not r.get("problems"):
                    _mark("edge", (m, t, r["from"]), self.name)
                    for g, p in r["guards"].items():
                        if not p:
                            _mark("guard_ok", (m, t, g), self.name)
                elif tdef.get("on_guard_fail") and r["to"] == tdef["on_guard_fail"]:
                    gravados = " ".join((ev.get("data") or {}).get("problems") or [])
                    for g, p in r["guards"].items():
                        if p and all(x[:80] in gravados for x in p):
                            _mark("guard_no", (m, t, g), self.name)
                        elif not p:
                            _mark("guard_ok", (m, t, g), self.name)
            elif r.get("to") is None and code == (2 if is_hook else 1):
                for g, p in r["guards"].items():
                    if p and any(x[:80] in err for x in p):
                        _mark("guard_no", (m, t, g), self.name)
            if r.get("to") is None:
                # recusa INTERNA (M5): Refused capturado pelo motor e gravado no evento vencedor
                rec = [x for e in events if str(e.get("type") or "").startswith(m + ".")
                       for x in ((e.get("data") or {}).get("guardas_recusadas") or []) if isinstance(x, dict)]
                for g, p in r["guards"].items():
                    if p and any(x.get("transicao") == t and x.get("guarda") == g for x in rec):
                        _mark("guard_no", (m, t, g), self.name)
        # transições de CRIAÇÃO (from: []): evento gravado + data.guardas; recusa pelo stderr `guarda <nome>:`
        refused_rec = any(r.get("to") is None and not r.get("error") for r in recs)
        for mname, mdef in Ms.items():
            for tname, tdef in (mdef.get("transitions") or {}).items():
                if tdef.get("from"):
                    continue
                for e in events:
                    if e.get("type") == "%s.%s" % (mname, tname):
                        _mark("edge", (mname, tname, None), self.name)
                        for g in (e.get("data") or {}).get("guardas") or []:
                            if g in (tdef.get("guards") or []):
                                _mark("guard_ok", (mname, tname, g), self.name)
                if code == 1 and not is_hook and not refused_rec:
                    for g in tdef.get("guards") or []:
                        if ("guarda %s:" % g) in err:
                            _mark("guard_no", (mname, tname, g), self.name)
        # replay das ops de estado: pares da task (máquina por pares) e ATALHOS — mudança de estado de máquina com
        # transições nomeadas gravada sem passar por engine.evaluate (guardas não avaliadas). Informativo.
        st = dict(st0)
        evaluated = {(r["machine"], r["entity"], r.get("to")) for r in recs if not r.get("error")}
        for e in events:
            for op in e.get("ops") or []:
                if op[0] == "create":
                    kind = op[1]
                    st["%s:%s" % (kind, op[3]["id"])] = op[3].get(hcore.state_field(kind))
                    continue
                if op[0] != "set":
                    continue
                kind, eid = op[1].split(":", 1)
                if op[2] != hcore.state_field(kind):
                    continue
                old = st.get(op[1])
                m = hcore.KIND_MACHINE[kind]
                if kind == "task":
                    _mark("edge", ("task", "%s->%s" % (old, op[3]), old), self.name)
                elif (Ms[m].get("transitions") and (m, eid, op[3]) not in evaluated
                      and not (kind == "deleg" and e["type"].startswith("delegation."))):
                    _mark("atalho", (m, "%s->%s" % (old, op[3]), e["type"]), self.name)
                st[op[1]] = op[3]
        # autonomy (estado em autonomy.json5)
        if au0 is not None and au1 is not None and au0 != au1:
            for tname, t in (self.M.get("autonomy") or {}).get("transitions", {}).items():
                if au0 in t["from"] and t["to"] == au1:
                    _mark("edge", ("autonomy", tname, au0), self.name)

    def cs(self, root, *args, **kw):
        actor = kw.get("actor")
        a = ["--root", root] + (["--actor", actor] if actor else []) + list(args)
        return self._run(root, STATE, a)

    def hook(self, root, mode, payload, env_extra=None):
        e = {"CLAUDE_PROJECT_DIR": root}
        e.update(env_extra or {})
        return self._run(root, GUARD, [mode], stdin=json.dumps(payload).encode("utf-8"), env_extra=e)

    def auto(self, root, *args, **kw):
        """`cs-auto` (piloto do mandato M5) pela CLI real, observada como as demais."""
        actor = kw.get("actor")
        a = ["--root", root] + (["--actor", actor] if actor else []) + list(args)
        return self._run(root, AUTO, a, env_extra=kw.get("env_extra"))

    # ---------------------------------------------------------------- asserções
    def ok(self, root, *args, **kw):
        s = self.cs(root, *args, **kw)
        if s.code != 0:
            raise AssertionError("cs-state %s → exit %d (esperado 0)\n%s%s" % (" ".join(args), s.code, s.out, s.err))
        return s

    def no(self, root, *args, **kw):
        guards = kw.pop("guards", ())
        s = self.cs(root, *args, **kw)
        if s.code != 1:
            raise AssertionError("cs-state %s deveria ser RECUSADO (exit 1), deu %d\n%s%s" % (" ".join(args), s.code, s.out, s.err))
        self._expect_guards(s, guards, args)
        return s

    def hook_ok(self, root, mode, payload):
        s = self.hook(root, mode, payload)
        if s.code != 0:
            raise AssertionError("hook %s → exit %d (esperado 0)\n%s%s" % (mode, s.code, s.out, s.err))
        return s

    def hook_no(self, root, mode, payload, guards=()):
        s = self.hook(root, mode, payload)
        if s.code != 2:
            raise AssertionError("hook %s deveria BLOQUEAR (exit 2), deu %d\n%s%s" % (mode, s.code, s.out, s.err))
        self._expect_guards(s, guards, [mode])
        return s

    def _expect_guards(self, s, guards, args):
        rb = s.refused_by()
        for g in guards:
            if g not in rb:
                raise AssertionError("%s: esperava recusa da guarda %s; recusaram %s\n%s" % (" ".join(args), g, sorted(rb), s.err))
            if not any(x[:80] in s.err for x in rb[g]):
                raise AssertionError("%s: mensagem da guarda %s ausente do stderr\n%s" % (" ".join(args), g, s.err))

    def state_of(self, root, tid):
        return deleg(root, tid)["state"]

    def expect(self, root, tid, state):
        got = self.state_of(root, tid)
        if got != state:
            raise AssertionError("delegação de %s em %s, esperado %s" % (tid, got, state))


# ================================================================ helpers in-process (montagem; não contam na matriz)
def board(root):
    return hcore.load_board(root)


def task(root, tid):
    return hcore.find(board(root), "task", tid)


def deleg(root, tid):
    t = task(root, tid)
    return (t.get("delegations") or [None])[-1]


def model_of(root, tid):
    return ((deleg(root, tid) or {}).get("route") or {}).get("model")


def add(root, ready=True, **kw):
    import cmds
    _, ev = cmds.add_task(root, A, fixture.task_spec(**kw), ready=ready)
    return next(e["entity"] for e in ev if e["type"] == "task.add")


def execute(root):
    import cmds
    cmds.session_cmd(root, A, "execute")


def dispatch_ip(root, tid):
    import cmds
    cmds.dispatch(root, A, tid, model=model_of(root, tid), tool_use_id="tu-%s" % tid, procedencia="declarada-no-despacho")


def submit_ip(root, tid, rel="src/billing/discount.py", txt="RATE = 30\n", agent="dev-billing"):
    import cmds
    fixture.write(root, rel, txt)
    cmds.submit(root, agent, tid, {"files_changed": [rel], "checks_run": ["unittest: OK"], "risks": [], "handoff_notes": "ok"})


def verify_ip(root, tid):
    import cmds
    cmds.verify(root, A, tid)


def review_ip(root, tid, by="reviewer", verdict="PASS"):
    import cmds
    cmds.review(root, by, tid, by, verdict, "%s: ok src/billing/discount.py:1" % verdict)


def commit_all(root, msg="setup cobertura"):
    fixture.git(root, "add", "-A")
    fixture.git(root, "commit", "-qm", msg)


def base(h, klass="pequena", **kw):
    root = h.repo(**kw)
    fixture.process(root, klass)
    return root


def drive(h, target, klass="pequena"):
    """Repo com T-1 (dev-billing, src/billing/discount.py) com a delegação no estado `target`."""
    import cmds
    root = base(h, klass)
    tid = "T-1"
    if target == "PLANNED":
        add(root, ready=False)
    else:
        add(root)
        if target == "ABSTAINED":
            cmds.abstain(root, A, tid, "spec_ambiguous", "spec ambígua: desconto sobre bruto ou líquido?")
        elif target != "BRIEFED":
            execute(root)
            dispatch_ip(root, tid)
            if target not in ("DISPATCHED",):
                submit_ip(root, tid)
                if target == "REJECTED":
                    cmds.reject(root, A, tid, "achado: falta teste do desconto")
                elif target == "ESCALATED":
                    cmds.escalate(root, A, tid, "decisão do humano necessária")
                elif target in ("VERIFIED", "REVIEWED"):
                    verify_ip(root, tid)
                    if target == "REVIEWED":
                        review_ip(root, tid)
                elif target != "RETURNED":
                    raise AssertionError("drive(): estado %s sem receita de montagem — acrescente-a" % target)
    got = deleg(root, tid)["state"]
    if got != target:
        raise AssertionError("drive(%s) montou %s" % (target, got))
    return root, tid


def tamper(root, fn):
    """Adultera board.json5 (sem tocar events.jsonl) e devolve o original para restaurar."""
    orig = board(root)
    b = board(root)
    fn(b)
    hcore.save_board(root, b)
    return orig


# ================================================================ registro de cenários
def scenario(fn):
    SCENARIOS[fn.__name__] = fn
    return fn


def run_scenario(name):
    if name in RESULTS:
        return RESULTS[name]
    h = H(name)
    try:
        SCENARIOS[name](h)
        RESULTS[name] = None
    except Exception:
        RESULTS[name] = traceback.format_exc()
    finally:
        h.cleanup()
    return RESULTS[name]


# ---------------------------------------------------------------- M1 sessão
@scenario
def sessao_triagem_pergunta_e_planejamento(h):
    root = h.repo()
    h.ok(root, "session", "start", "--request", "como funciona o desconto?")
    h.no(root, "session", "triage", "--class", "inexistente", "--why", "x", guards=["class_valid"])
    h.no(root, "session", "triage", "--class", "pergunta", guards=["why_present"])
    h.ok(root, "session", "triage", "--class", "pergunta", "--why", "só leitura")
    h.no(root, "session", "confirm", guards=["note_present"])
    h.ok(root, "session", "confirm", "--note", "sim, só responda")
    h.no(root, "session", "plan", guards=["class_not_question"])
    h.ok(root, "session", "answer")
    h.ok(root, "session", "close")
    h.ok(root, "session", "start", "--request", "mudar o desconto")
    h.no(root, "session", "plan", guards=["class_set"])
    h.ok(root, "session", "triage", "--class", "pequena", "--why", "1 território")
    h.no(root, "session", "answer", guards=["class_is_question"])
    h.ok(root, "session", "plan")
    h.ok(root, "session", "triage", "--class", "pequena", "--why", "re-triagem no PLANNING")
    h.ok(root, "session", "confirm", "--note", "confirmado no PLANNING")
    h.no(root, "session", "execute", guards=["plan_recorded"])


@scenario
def sessao_execute_recusas_risco_e_replan(h):
    root = base(h, "trivial", no_rules=True)
    add(root, agent="dev-users", paths=("src/users/a.py",), title="a")
    add(root, agent="dev-users", paths=("src/users/b.py",), title="b", wave=2)
    h.no(root, "session", "execute", guards=["plan_fits_class"])

    root = base(h, "pequena")
    add(root)
    add(root, title="mesmo arquivo")
    h.no(root, "session", "execute", guards=["waves_disjoint"])

    root = base(h, "risco")
    add(root, agent="po", paths=("docs/stories/US-1.md",), title="detalhar story")
    add(root, wave=2)
    h.no(root, "session", "execute", guards=["risk_confirmed"])
    h.ok(root, "session", "confirm", "--note", "pode mexer no desconto")
    h.ok(root, "session", "execute")
    h.ok(root, "session", "triage", "--class", "risco", "--why", "re-triagem em EXECUTING")
    h.ok(root, "session", "replan")


@scenario
def sessao_verify_review_report_close(h):
    import cmds
    root = base(h, "feature")
    add(root, agent="po", paths=("docs/stories/US-1.md",), title="detalhar story")
    add(root, wave=2)
    execute(root)
    h.no(root, "session", "verify", guards=["no_delegation_in_flight", "all_tasks_closed"])
    cmds.escalate(root, A, "T-1", "humano decide")
    cmds.escalate(root, A, "T-2", "humano decide")
    h.ok(root, "session", "verify")
    h.ok(root, "session", "replan")
    execute(root)
    h.ok(root, "session", "verify")
    h.no(root, "session", "review", "--by", "dev-billing", "--verdict", "TALVEZ",
         guards=["reviewer_is_gate", "verdict_valid", "findings_present"])
    h.no(root, "session", "report", guards=["pipeline_satisfied"])
    h.ok(root, "session", "review", "--by", "reviewer", "--verdict", "PASS", "--findings", "entrega ok")
    h.ok(root, "session", "report")
    h.ok(root, "session", "close")


# ---------------------------------------------------------------- M2 delegação: ready / dispatch / submit / return
@scenario
def deleg_ready(h):
    root = base(h)
    add(root, ready=False, briefing={"references": ["src/billing/nao_existe.py:1"], "scope": {"in": ["x"], "out": ["y: z"]}})
    h.no(root, "ready", "--task", "T-1", guards=["brief_valid"])
    add(root, ready=False, paths=("src/billing/outro.py",), title="outro")
    h.ok(root, "ready", "--task", "T-2")


@scenario
def deleg_dispatch_cli_e_recusas(h):
    root = base(h)
    add(root)
    add(root, paths=("src/billing/dep.py",), title="depende", wave=2, depends_on=["T-1"])
    add(root, paths=("src/billing/terceira.py",), title="terceira", wave=3)
    h.no(root, "dispatch", "--task", "T-1", "--model", model_of(root, "T-1"), guards=["session_executing"])
    execute(root)
    h.no(root, "dispatch", "--task", "T-1", guards=["model_declared"])
    h.ok(root, "dispatch", "--task", "T-1", "--model", model_of(root, "T-1"), "--tool-use-id", "tu-cov-1")
    h.no(root, "dispatch", "--task", "T-2", "--model", model_of(root, "T-2"), guards=["deps_accepted"])
    h.no(root, "dispatch", "--task", "T-3", "--model", model_of(root, "T-3"), guards=["one_in_flight_per_agent"])


@scenario
def deleg_dispatch_colisao(h):
    root = base(h, with_collision={"do_not_parallelize": [{"a": "po", "b": "dev-billing", "co_change": 7}]})
    add(root, agent="po", paths=("docs/stories/US-1.md",), title="detalhar story")
    add(root, wave=2)
    execute(root)
    h.ok(root, "dispatch", "--task", "T-1", "--model", model_of(root, "T-1"), "--tool-use-id", "tu-cov-2")
    h.no(root, "dispatch", "--task", "T-2", "--model", model_of(root, "T-2"), guards=["no_parallel_collision"])


@scenario
def deleg_dispatch_ordem_da_classe(h):
    root = base(h, "feature")
    add(root, agent="po", paths=("docs/stories/US-1.md",), title="detalhar story")
    add(root, wave=2)
    execute(root)
    h.no(root, "dispatch", "--task", "T-2", "--model", model_of(root, "T-2"), guards=["class_dispatch_order"])


@scenario
def deleg_dispatch_hook_e_return_hook(h):
    root = base(h)
    add(root)
    execute(root)
    h.hook_no(root, "pre-agent", agent_payload("T-1.d1: implementar", "dev-billing", tuid="tu-x"), guards=["model_declared"])
    h.hook_ok(root, "pre-agent", agent_payload("T-1.d1: implementar", "dev-billing", model=model_of(root, "T-1"), tuid="tu-1"))
    h.expect(root, "T-1", "DISPATCHED")
    h.hook_ok(root, "subagent-stop", {"agent_type": "dev-billing", "agent_id": "ag-1", "stop_hook_active": True})
    h.expect(root, "T-1", "REJECTED")


@scenario
def deleg_dispatch_orcamento_e_autonomia(h):
    root = base(h)
    add(root)
    execute(root)
    budget = "tasks=5,attempts=2,minutes=90,usd=1"
    h.ok(root, "autonomy", "start", "--feature", "FEAT-1", "--budget", budget)
    h.ok(root, "autonomy", "spend", "--usd", "2")
    h.no(root, "dispatch", "--task", "T-1", "--model", model_of(root, "T-1"), guards=["budget_available"])
    h.hook_no(root, "pre-agent", agent_payload("T-1.d1: implementar", "dev-billing", model=model_of(root, "T-1")),
              guards=["budget_available"])
    h.hook_ok(root, "stop", {"session_id": "s1"})                 # autonomy ACTIVE → ESCALATED (hook Stop)
    assert _autonomy_state(root) == "ESCALATED", _autonomy_state(root)
    h.ok(root, "autonomy", "resume", "--decision", "seguir mesmo assim")  # ESCALATED → ACTIVE
    h.ok(root, "autonomy", "stop", "--reason", "parar")             # ACTIVE → STOPPED
    h.ok(root, "autonomy", "start", "--feature", "FEAT-1", "--budget", budget)
    h.ok(root, "autonomy", "spend", "--usd", "2")
    h.hook_ok(root, "stop", {"session_id": "s1"})
    assert _autonomy_state(root) == "ESCALATED", _autonomy_state(root)
    h.ok(root, "autonomy", "stop", "--reason", "humano desistiu")   # ESCALATED → STOPPED


@scenario
def autonomia_done(h):
    root = base(h)
    h.ok(root, "autonomy", "start", "--feature", "FEAT-1", "--budget", "tasks=5,attempts=2,minutes=90")
    add(root)
    execute(root)
    dispatch_ip(root, "T-1")
    submit_ip(root, "T-1")
    verify_ip(root, "T-1")
    review_ip(root, "T-1")
    import cmds
    cmds.accept(root, A, "T-1")
    h.ok(root, "autonomy", "report")                                 # ACTIVE → DONE
    assert _autonomy_state(root) == "DONE", _autonomy_state(root)


@scenario
def deleg_submit_e_return(h):
    root, tid = drive(h, "DISPATCHED")
    fixture.write(root, "src/billing/discount.py", "RATE = 30\n")
    h.no(root, "submit", "--task", tid, "--files-changed", "src/billing/discount.py", actor="dev-billing",
         guards=["submission_complete"])
    h.no(root, "submit", "--task", tid, "--files-changed", "src/billing/tax.py", "--check", "unittest: OK",
         "--risk", "nenhum", "--handoff-notes", "ok", actor="dev-billing", guards=["files_in_allowed_paths"])
    h.ok(root, "submit", "--task", tid, "--files-changed", "src/billing/discount.py", "--check", "unittest: OK",
         "--risk", "nenhum", "--handoff-notes", "ok", actor="dev-billing")
    root, tid = drive(h, "DISPATCHED")
    h.ok(root, "return", "--task", tid)
    h.expect(root, tid, "REJECTED")


# ---------------------------------------------------------------- verify / review / accept
@scenario
def deleg_verify_ok(h):
    root, tid = drive(h, "RETURNED")
    h.ok(root, "verify", "--task", tid)
    h.expect(root, tid, "VERIFIED")


@scenario
def deleg_verify_reprovado_pelas_quatro_guardas(h):
    import mem
    root = base(h)
    add(root, verification_command="false", acceptance_criteria=["AC-1|desconto aplicado ao total do pedido|test:cmd:false"])
    mem.add_lesson(root, "dev-billing", "nunca somar centavos como float no desconto", why="arredondamento",
                   paths=["src/billing/**"], check="false")
    execute(root)
    dispatch_ip(root, "T-1")
    submit_ip(root, "T-1")
    fixture.write(root, "src/billing/tax.py", "RATE = 99\n")  # fora de allowed_paths e não declarado
    s = h.ok(root, "verify", "--task", "T-1")
    assert "REPROVOU" in s.out, s.out
    h.expect(root, "T-1", "REJECTED")
    rb = s.refused_by()
    for g in ("command_exit_zero", "ac_tests_green", "diff_within_allowed_paths", "lessons_check_pass"):
        assert g not in rb  # on_guard_fail: não é "recusa com exit 1"; a matriz lê o evento gravado
    keys = {k for k in MATRIX["guard_no"] if k[:2] == ("delegation", "verify")}
    falt = {"command_exit_zero", "ac_tests_green", "diff_within_allowed_paths", "lessons_check_pass"} - {k[2] for k in keys}
    assert not falt, "verify reprovado sem atribuir às guardas: %s" % sorted(falt)


@scenario
def deleg_review(h):
    root, tid = drive(h, "VERIFIED")
    h.no(root, "review", "--task", tid, "--by", "dev-billing", "--verdict", "PASS", "--findings", "x",
         guards=["reviewer_is_gate", "reviewer_not_author"])
    h.no(root, "review", "--task", tid, "--by", "reviewer", "--verdict", "TALVEZ", "--findings", "x", guards=["verdict_valid"])
    h.no(root, "review", "--task", tid, "--by", "reviewer", "--verdict", "PASS", guards=["findings_present"])
    h.ok(root, "review", "--task", tid, "--by", "reviewer", "--verdict", "PASS", "--findings", "ok discount.py:1", actor="reviewer")
    h.ok(root, "review", "--task", tid, "--by", "security", "--verdict", "PASS", "--findings", "ok discount.py:1", actor="security")
    # reviewer_not_author SOZINHA: só se o autor virar gate depois do despacho (team.json5 editado)
    tp = os.path.join(root, hcore.STATE_DIR, "team.json5")
    with open(tp, encoding="utf-8") as f:
        orig = f.read()
    team = j5.loads(orig)
    for a in team["agents"]:
        if a["name"] == "dev-billing":
            a["kind"] = "gate"
    with open(tp, "w", encoding="utf-8") as f:
        f.write(j5.dumps(team))
    s = h.no(root, "review", "--task", tid, "--by", "dev-billing", "--verdict", "PASS", "--findings", "x",
             guards=["reviewer_not_author"])
    assert "reviewer_is_gate" not in s.refused_by(), s.err
    with open(tp, "w", encoding="utf-8") as f:
        f.write(orig)


@scenario
def deleg_accept(h):
    root, tid = drive(h, "REVIEWED")
    h.ok(root, "accept", "--task", tid)
    # VERIFIED → ACCEPTED: classe trivial (min_gate_reviews 0), sem invariantes de escopo
    root = base(h, "trivial", no_rules=True)
    add(root, agent="dev-users", paths=("src/users/discount.py",), title="elegibilidade")
    execute(root)
    dispatch_ip(root, "T-1")
    submit_ip(root, "T-1", rel="src/users/discount.py", agent="dev-users")
    verify_ip(root, "T-1")
    h.expect(root, "T-1", "VERIFIED")
    h.ok(root, "accept", "--task", "T-1")
    # recusas
    root, tid = drive(h, "VERIFIED")
    h.no(root, "accept", "--task", tid, guards=["reviews_satisfy_class"])
    root, tid = drive(h, "REVIEWED")
    fixture.write(root, "src/billing/discount.py", "RATE = 31\n")
    h.no(root, "accept", "--task", tid, guards=["tree_unchanged"])
    # verify_pass: inalcançável por caminho legal → adulteração do board (gate_report.build.exit_code)
    root, tid = drive(h, "REVIEWED")

    def bad_build(b):
        hcore.find(b, "task", tid)["gate_report"]["build"]["exit_code"] = 1
    orig = tamper(root, bad_build)
    h.no(root, "accept", "--task", tid, guards=["verify_pass"])
    hcore.save_board(root, orig)
    h.ok(root, "accept", "--task", tid)


# ---------------------------------------------------------------- reject / retry (cadeia até esgotar)
@scenario
def deleg_reject_retry_ate_esgotar(h):
    root, tid = drive(h, "RETURNED")
    h.no(root, "reject", "--task", tid, guards=["reason_present"])
    h.ok(root, "reject", "--task", tid, "--reason", "falta teste")           # RETURNED → REJECTED
    h.ok(root, "retry", "--task", tid)                                       # REJECTED → BRIEFED (reject_reason)
    dispatch_ip(root, tid)
    submit_ip(root, tid, txt="RATE = 29\n")
    verify_ip(root, tid)
    h.ok(root, "reject", "--task", tid, "--reason", "valor errado")          # VERIFIED → REJECTED
    h.ok(root, "retry", "--task", tid, "--findings", "use 30")
    dispatch_ip(root, tid)
    submit_ip(root, tid, txt="RATE = 28\n")
    verify_ip(root, tid)
    review_ip(root, tid, verdict="FAIL")
    h.ok(root, "reject", "--task", tid, "--reason", "review FAIL")           # REVIEWED → REJECTED (retries=2 → BLOCKED)
    assert task(root, tid)["status"] == "BLOCKED", task(root, tid)["status"]
    h.no(root, "retry", "--task", tid, "--findings", "de novo", guards=["retries_left"])
    # brief inválido no retry: referência do brief some
    root, tid = drive(h, "REJECTED")
    os.remove(os.path.join(root, "src", "billing", "total.py"))
    h.no(root, "retry", "--task", tid, "--findings", "x", guards=["brief_valid"])
    # retomada de ESCALATED sem a decisão humana
    root, tid = drive(h, "ESCALATED")
    h.no(root, "retry", "--task", tid, guards=["findings_attached"])


# ---------------------------------------------------------------- transições genéricas: TODA origem lida de machines.json5
GENERIC = {
    "escalate": lambda t: ["escalate", "--task", t, "--reason", "decisão humana necessária"],
    "reroute": lambda t: ["reroute", "--task", t, "--agent", "dev-users", "--allowed-path", "src/users/discount.py",
                          "--reason", "território errado"],
    "drop": lambda t: ["drop", "--task", t, "--reason", "humano descartou"],
    "abstain": lambda t: ["abstain", "--task", t, "--kind", "spec_ambiguous", "--reason", "spec ambígua"],
    "reject": lambda t: ["reject", "--task", t, "--reason", "achado de review"],
    "retry": lambda t: ["retry", "--task", t, "--findings", "achados anexados", "--decision", "seguir com o mesmo agente"],
}
GENERIC_REFUSALS = {
    "escalate": [(["escalate"], ["reason_present"])],
    "reroute": [(["reroute", "--agent", "dev-users", "--allowed-path", "src/users/discount.py"], ["reason_present"]),
                (["reroute", "--agent", "dev-billing", "--reason", "x"], ["new_agent_valid"])],
    "drop": [(["drop"], ["reason_present"])],
    "abstain": [(["abstain", "--kind", "spec_ambiguous"], ["reason_present"]),
                (["abstain", "--kind", "inventado", "--reason", "x"], ["abstain_kind_valid"])],
}


def _generic(tname, origin):
    def fn(h):
        root, tid = drive(h, origin)
        for argv, guards in GENERIC_REFUSALS.get(tname, []):
            h.no(root, *(argv[:1] + ["--task", tid] + argv[1:]), guards=guards)
        h.ok(root, *GENERIC[tname](tid))
        to = h.M["machines"]["delegation"]["transitions"][tname]["to"]
        got = [d["state"] for d in task(root, tid)["delegations"]]
        if to not in got:
            raise AssertionError("%s de %s: delegações %s, esperado %s" % (tname, origin, got, to))
    fn.__name__ = "deleg_%s_de_%s" % (tname, origin)
    return fn


for _t in sorted(GENERIC):
    for _f in load_machines()["machines"]["delegation"]["transitions"].get(_t, {}).get("from") or []:
        scenario(_generic(_t, _f))


# ---------------------------------------------------------------- falha de AMBIENTE: reverify / waive_verify
def env_repo(h):
    root = h.repo()
    marker = os.path.join(h.outside(), "env-ok")
    fixture.write(root, "tools/verify_env.sh", VERIFY_ENV_SH % marker)
    commit_all(root)
    fixture.process(root, "pequena")
    add(root, verification_command=VERIFY_ENV)
    execute(root)
    dispatch_ip(root, "T-1")
    submit_ip(root, "T-1")
    verify_ip(root, "T-1")
    if deleg(root, "T-1")["state"] != "REJECTED" or task(root, "T-1")["gate_report"].get("failure_kind") != "environment":
        raise AssertionError("montagem: verify deveria falhar por AMBIENTE (%s)" % task(root, "T-1")["gate_report"])
    return root, "T-1", marker


EVID = "saída do verify: 'fake-dep: command not found' (exit 127)"


@scenario
def deleg_reverify_de_rejected_e_escalated(h):
    import cmds
    root, tid, marker = env_repo(h)
    open(marker, "w").close()
    h.ok(root, "reverify", "--task", tid)                                    # REJECTED → RETURNED → VERIFIED
    h.expect(root, tid, "VERIFIED")
    root, tid, marker = env_repo(h)
    cmds.escalate(root, A, tid, "ambiente quebrado: humano decide")
    open(marker, "w").close()
    h.ok(root, "reverify", "--task", tid)                                    # ESCALATED → RETURNED → VERIFIED
    h.expect(root, tid, "VERIFIED")
    # falha de CÓDIGO (REJECTED sem verify de ambiente) não reverifica
    root, tid = drive(h, "REJECTED")
    h.no(root, "reverify", "--task", tid, guards=["reverify_allowed"])


@scenario
def deleg_reverify_de_verified_e_reviewed(h):
    """iter18 R2: árvore mudou depois do verify → reverify (VERIFIED/REVIEWED → RETURNED → VERIFIED); intacta → recusa."""
    for origin in ("VERIFIED", "REVIEWED"):
        root, tid = drive(h, origin)
        h.no(root, "reverify", "--task", tid, guards=["reverify_allowed"])          # árvore intacta
        fixture.write(root, "src/billing/discount.py", "RATE = 31\n")
        h.no(root, "accept", "--task", tid, guards=["tree_unchanged"])
        h.ok(root, "reverify", "--task", tid)
        h.expect(root, tid, "VERIFIED")


@scenario
def deleg_waive_verify(h):
    import cmds
    root, tid, _ = env_repo(h)
    h.no(root, "waive-verify", "--task", tid, "--by", HUMAN, "--evidence", EVID, guards=["reason_present"])
    h.no(root, "waive-verify", "--task", tid, "--by", HUMAN, "--reason", "CI sem fake-dep", guards=["evidence_present"])
    h.no(root, "waive-verify", "--task", tid, "--by", "lead", "--reason", "CI sem fake-dep", "--evidence", EVID,
         guards=["waiver_by_human"])
    h.no(root, "waive-verify", "--task", tid, "--by", HUMAN, "--reason", "CI sem fake-dep", "--evidence", "falhou",
         guards=["verify_failed_by_environment"])
    fixture.write(root, "src/billing/discount.py", "RATE = 31\n")
    h.no(root, "waive-verify", "--task", tid, "--by", HUMAN, "--reason", "CI sem fake-dep", "--evidence", EVID,
         guards=["tree_unchanged"])
    fixture.write(root, "src/billing/discount.py", "RATE = 30\n")
    h.ok(root, "waive-verify", "--task", tid, "--by", HUMAN, "--reason", "CI sem fake-dep", "--evidence", EVID)  # REJECTED
    h.expect(root, tid, "VERIFIED")
    root, tid, _ = env_repo(h)
    cmds.escalate(root, A, tid, "ambiente quebrado")
    h.ok(root, "waive-verify", "--task", tid, "--by", HUMAN, "--reason", "CI sem fake-dep", "--evidence", EVID)  # ESCALATED
    h.expect(root, tid, "VERIFIED")


# ---------------------------------------------------------------- M4 consulta (só via hook + ask/cancel)
@scenario
def consulta(h):
    root = h.repo()
    h.ok(root, "session", "start", "--request", "como calcula o desconto?")
    h.ok(root, "session", "triage", "--class", "pergunta", "--why", "só leitura")
    h.ok(root, "ask", "dev-billing", "como calcula o desconto?")
    h.hook_no(root, "pre-agent", agent_payload("ASK-1: responda", "dev-billing"), guards=["consult_model_declared"])
    h.hook_ok(root, "pre-agent", agent_payload("ASK-1: responda", "dev-billing", model="sonnet"))
    h.ok(root, "ask", "dev-billing", "e o imposto?")
    h.hook_no(root, "pre-agent", agent_payload("ASK-2: responda", "dev-billing", model="sonnet"), guards=["consult_agent_free"])
    h.hook_ok(root, "subagent-stop", {"agent_type": "dev-billing", "agent_id": "ag-ask"})
    assert hcore.find(board(root), "consult", "ASK-1")["state"] == "ANSWERED"
    h.no(root, "consult", "cancel", "--id", "ASK-2", guards=["reason_present"])
    h.ok(root, "consult", "cancel", "--id", "ASK-2", "--reason", "não precisa mais")
    h.ok(root, "ask", "dev-users", "quem é elegível?")
    h.hook_ok(root, "pre-agent", agent_payload("ASK-3: responda", "dev-users", model="sonnet"))
    h.ok(root, "consult", "cancel", "--id", "ASK-3", "--reason", "humano respondeu antes")


# ---------------------------------------------------------------- processo: épico, feature, sprint, story (+ fluxo feliz)
@scenario
def epico(h):
    root = h.repo()
    h.ok(root, "add", "epic", "--title", "E", "--objective", "o")
    h.no(root, "epic", "activate", "--id", "EPIC-1", guards=["epic_dor"])
    h.no(root, "epic", "drop", "--id", "EPIC-1", guards=["reason_present"])
    h.ok(root, "epic", "drop", "--id", "EPIC-1", "--reason", "fora do roadmap")
    h.ok(root, "add", "epic", "--title", "E2", "--objective", "o", "--metric", "receita")
    h.ok(root, "epic", "activate", "--id", "EPIC-2")
    h.no(root, "epic", "done", "--id", "EPIC-2", guards=["epic_dod"])
    h.ok(root, "epic", "drop", "--id", "EPIC-2", "--reason", "cancelado")


ACC = ["--accept-cmd", "python3 -m unittest accept.test_accept", "--accept-file", "accept/test_accept.py"]


@scenario
def feature(h):
    root = h.repo()
    h.ok(root, "add", "epic", "--title", "E", "--objective", "o", "--metric", "receita")
    h.ok(root, "add", "feature", "--epic", "EPIC-1", "--title", "F", "--spec", "spec/nao_existe.md", *ACC)
    h.no(root, "feature", "ready", "--id", "FEAT-1", guards=["feature_dor"])
    h.no(root, "feature", "drop", "--id", "FEAT-1", guards=["reason_present"])
    h.ok(root, "feature", "drop", "--id", "FEAT-1", "--reason", "spec errada")
    h.ok(root, "add", "feature", "--epic", "EPIC-1", "--title", "F2", "--spec", "spec/feat.md", *ACC)
    h.ok(root, "feature", "ready", "--id", "FEAT-2")
    h.no(root, "feature", "start", "--id", "FEAT-2", guards=["parent_epic_active"])
    h.ok(root, "feature", "drop", "--id", "FEAT-2", "--reason", "repriorizada")
    h.ok(root, "epic", "activate", "--id", "EPIC-1")
    h.ok(root, "add", "feature", "--epic", "EPIC-1", "--title", "F3", "--spec", "spec/feat.md", *ACC)
    h.ok(root, "feature", "ready", "--id", "FEAT-3")
    h.ok(root, "feature", "start", "--id", "FEAT-3")
    h.no(root, "feature", "done", "--id", "FEAT-3", guards=["feature_dod"])
    h.ok(root, "feature", "drop", "--id", "FEAT-3", "--reason", "abandonada")


STORY = ["--as-a", "cliente", "--i-want", "desconto", "--so-that", "pagar menos"]
CRIT = ["--criterion", "AC-1|Dado pedido Quando aplico Então desconta|tests.test_billing"]


@scenario
def fluxo_feliz_sprint_story_feature_epico(h):
    root = h.repo()
    h.ok(root, "add", "epic", "--title", "Billing", "--objective", "cobrar certo", "--metric", "receita")
    h.ok(root, "epic", "activate", "--id", "EPIC-1")
    h.ok(root, "add", "feature", "--epic", "EPIC-1", "--title", "Desconto", "--spec", "spec/feat.md", *ACC)
    h.ok(root, "feature", "ready", "--id", "FEAT-1")
    h.ok(root, "add", "feature", "--epic", "EPIC-1", "--title", "Rascunho", "--spec", "spec/feat.md", *ACC)
    h.ok(root, "add", "story", "--type", "us", "--feature", "FEAT-2", "--title", "sem critério", *STORY)   # US-1
    h.no(root, "story", "ready", "--id", "US-1", guards=["story_dor"])
    h.ok(root, "add", "story", "--type", "us", "--feature", "FEAT-1", "--title", "quero desconto", *(STORY + CRIT))  # US-2
    h.ok(root, "story", "ready", "--id", "US-2")
    # sprint
    h.no(root, "sprint", "plan", "--goal", "entregar desconto", "--budget", "tasks=4,attempts=2,minutes=60", "--add", "US-1",
         guards=["stories_have_dor"])
    sid = board(root)["sprints"][-1]["id"]
    h.ok(root, "sprint", "plan", "--id", sid, "--add", "US-2")
    h.ok(root, "add", "sprint", "--goal", "vazio", "--budget", "tasks=1,attempts=1,minutes=10")
    sid2 = board(root)["sprints"][-1]["id"]
    h.no(root, "sprint", "start", "--id", sid2, guards=["sprint_dor"])
    h.ok(root, "sprint", "start", "--id", sid)
    # story: todas as saídas antes de ter task
    h.ok(root, "story", "start", "--id", "US-2")
    h.no(root, "story", "review", "--id", "US-2", guards=["story_tasks_accepted"])
    h.no(root, "story", "reject", "--id", "US-2", guards=["reason_present"])
    h.ok(root, "story", "reject", "--id", "US-2", "--reason", "critério incompleto")       # IN_PROGRESS → REJECTED
    h.no(root, "story", "requeue", "--id", "US-2", guards=["reason_present"])
    h.ok(root, "story", "requeue", "--id", "US-2", "--reason", "volta ao backlog")          # REJECTED → BACKLOG
    h.ok(root, "story", "ready", "--id", "US-2")
    h.ok(root, "story", "requeue", "--id", "US-2", "--reason", "repriorizada")              # READY → BACKLOG
    h.ok(root, "story", "ready", "--id", "US-2")
    h.ok(root, "story", "start", "--id", "US-2")
    h.ok(root, "story", "requeue", "--id", "US-2", "--reason", "bloqueada")                 # IN_PROGRESS → BACKLOG
    h.ok(root, "story", "ready", "--id", "US-2")
    # sessão + task inteira pela CLI/hook
    h.ok(root, "session", "start", "--request", "implementar desconto")
    h.ok(root, "session", "triage", "--class", "pequena", "--why", "1 território")
    h.ok(root, "session", "plan")
    h.ok(root, "add", "task", "--story", "US-2", "--agent", "dev-billing", "--title", "criar desconto",
         "--goal", "desconto porque FEAT-1 exige", "--allowed-path", "src/billing/discount.py", "--verify-cmd", VERIFY,
         "--ac", AC, "--ref", "src/billing/total.py:1", "--in", "desconto", "--out", "tax: outra task", "--ready")
    h.ok(root, "session", "execute")
    h.hook_ok(root, "pre-agent", agent_payload("T-1.d1: implementar", "dev-billing", model=model_of(root, "T-1"), tuid="tu-1"))
    fixture.write(root, "src/billing/discount.py", "RATE = 30\n")
    h.ok(root, "submit", "--task", "T-1", "--files-changed", "src/billing/discount.py", "--check", "unittest: OK",
         "--risk", "nenhum", "--handoff-notes", "ok", actor="dev-billing")
    h.ok(root, "verify", "--task", "T-1")
    h.ok(root, "review", "--task", "T-1", "--by", "reviewer", "--verdict", "PASS", "--findings", "ok discount.py:1", actor="reviewer")
    h.ok(root, "accept", "--task", "T-1")
    assert hcore.find(board(root), "story", "US-2")["state"] == "IN_REVIEW"
    h.ok(root, "story", "reject", "--id", "US-2", "--reason", "PO pediu ajuste")              # IN_REVIEW → REJECTED
    h.ok(root, "story", "requeue", "--id", "US-2", "--reason", "ajuste feito")
    h.ok(root, "story", "ready", "--id", "US-2")
    h.ok(root, "story", "start", "--id", "US-2")
    h.ok(root, "story", "review", "--id", "US-2")                                           # IN_PROGRESS → IN_REVIEW
    h.ok(root, "story", "requeue", "--id", "US-2", "--reason", "revisão de novo")            # IN_REVIEW → BACKLOG
    h.ok(root, "story", "ready", "--id", "US-2")
    h.ok(root, "story", "start", "--id", "US-2")
    h.ok(root, "story", "review", "--id", "US-2")
    with open(os.path.join(root, "tests", "test_billing.py"), encoding="utf-8") as f:
        tb = f.read()
    fixture.write(root, "tests/test_billing.py", tb.replace("assertTrue(True)", "assertTrue(False)"))
    h.no(root, "story", "done", "--id", "US-2", guards=["story_dod"])
    fixture.write(root, "tests/test_billing.py", tb)
    h.ok(root, "story", "done", "--id", "US-2")
    h.ok(root, "session", "verify")
    h.ok(root, "session", "report")
    h.ok(root, "session", "close")
    h.ok(root, "feature", "drop", "--id", "FEAT-2", "--reason", "rascunho descartado")
    h.ok(root, "feature", "done", "--id", "FEAT-1")
    h.ok(root, "epic", "done", "--id", "EPIC-1")
    h.ok(root, "sprint", "review", "--id", sid)
    # sprint_review_recorded: inalcançável por caminho legal → adulteração (review apagada do board)

    def no_review(b):
        hcore.find(b, "sprint", sid)["review"] = None
    orig = tamper(root, no_review)
    h.no(root, "sprint", "close", "--id", sid, guards=["sprint_review_recorded"])
    hcore.save_board(root, orig)
    h.ok(root, "sprint", "close", "--id", sid)


# ================================================================ testes
class TestCenarios(unittest.TestCase):
    """Um teste por cenário (gerados). Falha de cenário = transição/guarda que o motor não deixou exercitar."""


def _mk(name):
    def t(self):
        err = run_scenario(name)
        if err:
            self.fail("cenário %s falhou:\n%s" % (name, err))
    t.__name__ = "test_%s" % name
    return t


import m5_cenarios  # noqa: E402  (extensão M5: cenários do mandato pela CLI real)

for _fn in m5_cenarios.CENARIOS:
    scenario(_fn)
if "mandato" in (load_machines().get("machines") or {}):
    EXCLUSOES.update(m5_cenarios.EXCLUSOES_M5)

for _n in SCENARIOS:
    setattr(TestCenarios, "test_%s" % _n, _mk(_n))


class TestM5Presente(unittest.TestCase):
    """O modo autônomo novo (M5 `mandato`) mora em machines.machines: entra na vivacidade e nesta cobertura."""

    def test_mandato_declarado_em_machines(self):
        self.assertIn("mandato", load_machines().get("machines") or {},
                      "machines.json5 → machines.mandato ausente (AUTONOMIA-DESENHO §5)")


def _excl(key):
    return key in EXCLUSOES


def coverage_report():
    trans, edges, guards = universe()
    ok_edges = set(MATRIX["edge"])
    edges_hit = {e for e in edges if e in ok_edges}
    trans_hit = {(m, t) for (m, t, f) in edges_hit}
    g_ok = {g for g in guards if g in MATRIX["guard_ok"]}
    g_no = {g for g in guards if g in MATRIX["guard_no"]}
    miss_edges = sorted((e for e in edges - edges_hit if not _excl(("aresta",) + e)), key=str)
    miss_trans = sorted(t for t in trans - trans_hit
                        if not all(_excl(("aresta",) + e) for e in edges if e[:2] == t))
    miss_gok = sorted(g for g in guards - g_ok if not _excl(("guarda_ok",) + g))
    miss_gno = sorted(g for g in guards - g_no if not _excl(("guarda_recusa",) + g))
    stale = sorted(k for k in EXCLUSOES if (k[0] == "aresta" and k[1:] not in edges) or
                   (k[0] != "aresta" and k[1:] not in guards))
    extra = sorted((e for e in ok_edges if e not in edges), key=str)  # observado mas fora de machines.json5 (não deveria existir)
    return {"trans": (len(trans_hit), len(trans)), "edges": (len(edges_hit), len(edges)), "g_ok": (len(g_ok), len(guards)),
            "g_no": (len(g_no), len(guards)), "miss_edges": miss_edges, "miss_trans": miss_trans, "miss_gok": miss_gok,
            "miss_gno": miss_gno, "stale": stale, "extra": extra, "excl": sorted(EXCLUSOES)}


class TestAtalhoDeGuarda(unittest.TestCase):
    """BUG REAL (achado deste oráculo): feature chega a IN_PROGRESS com o épico fora de ACTIVE.

    A transição `feature.start` exige a guarda `parent_epic_active`, mas `cs-state story start` (cmds.level_transition
    emite um Event "feature.start" direto) e `dispatch` (ops diretas em cmds.dispatch) movem a feature READY →
    IN_PROGRESS SEM avaliar guarda nenhuma. `validate --strict` aceita (o par é legal). Marcado expectedFailure: quando o
    motor for corrigido o teste vira "unexpected success" e a suíte falha — aí remova o decorator."""

    def test_feature_so_entra_em_progresso_com_epico_active(self):
        h = H("atalho_feature_start")
        try:
            root = h.repo()
            h.ok(root, "add", "epic", "--title", "E", "--objective", "o", "--metric", "receita")   # fica PROPOSED
            h.ok(root, "add", "feature", "--epic", "EPIC-1", "--title", "F", "--spec", "spec/feat.md", *ACC)
            h.ok(root, "feature", "ready", "--id", "FEAT-1")
            h.no(root, "feature", "start", "--id", "FEAT-1", guards=["parent_epic_active"])     # a guarda funciona...
            h.ok(root, "add", "story", "--type", "us", "--feature", "FEAT-1", "--title", "t", *(STORY + CRIT))
            h.ok(root, "story", "ready", "--id", "US-1")
            h.cs(root, "story", "start", "--id", "US-1")                                        # ...mas o atalho não
            b = board(root)
            self.assertFalse(hcore.find(b, "feature", "FEAT-1")["state"] == "IN_PROGRESS"
                             and hcore.find(b, "epic", "EPIC-1")["state"] != "ACTIVE",
                             "feature IN_PROGRESS com épico %s (parent_epic_active contornada)" % hcore.find(b, "epic", "EPIC-1")["state"])
        finally:
            h.cleanup()


class TestZZCobertura(unittest.TestCase):
    """Roda por último (ordem alfabética do unittest); se rodar isolado, executa os cenários que faltam."""

    def test_cobertura_100(self):
        t0 = time.time()
        for n in SCENARIOS:
            run_scenario(n)
        rep = coverage_report()
        failed = [n for n, e in RESULTS.items() if e]
        lines = ["", "=" * 78, "COBERTURA DAS MÁQUINAS (machines.json5 lido em tempo de execução)",
                 "  transições exercitadas : %d/%d" % rep["trans"],
                 "  arestas (t × origem)   : %d/%d" % rep["edges"],
                 "  guardas vistas OK      : %d/%d" % rep["g_ok"],
                 "  guardas vistas RECUSA  : %d/%d" % rep["g_no"],
                 "  cenários               : %d (%d falharam)  [%.0fs]" % (len(RESULTS), len(failed), time.time() - t0),
                 "  exclusões              : %d" % len(rep["excl"])]
        lines += ["    - %s: %s" % ("/".join(str(y) for y in k), EXCLUSOES[k][:110]) for k in rep["excl"]]
        for title, key in (("transição nunca exercitada", "miss_trans"), ("aresta nunca exercitada", "miss_edges"),
                           ("guarda nunca vista OK", "miss_gok"), ("guarda nunca vista RECUSANDO", "miss_gno"),
                           ("exclusão obsoleta (não existe mais em machines.json5)", "stale"),
                           ("aresta observada FORA de machines.json5", "extra")):
            for x in rep[key]:
                lines.append("  FALTA %s: %s" % (title, "/".join(str(y) for y in x)))
        for k, who in sorted(MATRIX["atalho"].items()):
            lines.append("  ATALHO (estado mudou sem avaliar guardas): %s %s via evento %s [%s]" % (k[0], k[1], k[2], who))
        for n in failed:
            lines.append("  CENÁRIO FALHOU: %s — %s" % (n, RESULTS[n].strip().splitlines()[-1][:200]))
        lines.append("=" * 78)
        sys.stderr.write("\n".join(lines) + "\n")
        problems = rep["miss_trans"] + rep["miss_edges"] + rep["miss_gok"] + rep["miss_gno"] + rep["stale"] + rep["extra"]
        self.assertFalse(problems, "cobertura incompleta (ver resumo acima)")


if __name__ == "__main__":
    unittest.main()
