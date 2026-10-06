"""ORÁCULO — três faixas de interação (ROADMAP-proxima-rodada.md, "PRIORIDADE MÁXIMA (P0 da rodada 1)").

Cenários de aceite CONSULT-1, CONSULT-2, QUICK-1, QUICK-2, QUICK-3, PEQUENA-1 + guarda de regressão do fluxo completo.
Tudo pelo comportamento OBSERVÁVEL: CLI real (engine/state.py = cs-state, em subprocesso) e guard real (engine/guard.py,
com payloads de hook). Nada de mock do motor. Este arquivo é o contrato: quem implementa não o edita.

Escolhas onde o contrato não fixa detalhe (documentadas também em cada teste):
  * Consulta: a sessão é triada como `pergunta` antes do `ask` (a tabela diz "Classe pergunta"). O id da consulta é
    lido do board procurando o objeto com `kind == "consult"` (o contrato fixa `kind: consult`), em qualquer lugar do
    board; o teste exige também que esse id apareça no stdout do `ask` ("imprime o id"). A description do Agent é o
    stdout do `ask` inteiro (contém o id), então o formato exato do id/da linha é livre.
  * Modelo no despacho da consulta: usa `route.model` da delegação de consulta se o motor gravar um; senão "sonnet".
  * "Evento no ledger": aceita registro em events.jsonl (cadeia do motor) OU harness-ledger.jsonl (guard) que cite o id.
  * Task avulsa: passa exatamente as flags do contrato (--quick --agent --title --allowed-path --verify-cmd --ac) mais
    --goal/--ref/--out, que já existem em `add task` e que o brief normal exige — o contrato diz que a faixa dispensa a
    HIERARQUIA (épico/feature/sprint/story), não que afrouxa o brief. Não passa --story/--epic/--feature/--sprint.
  * Story implícita: o teste exige que o id da story da task contenha "AVULSA" (contrato: `STORY-AVULSA` da sessão;
    pode ser sufixado pela sessão) e que nenhum épico/feature/sprint tenha sido criado.
  * Ordem da sessão: `add task --quick` logo após a triagem; depois o helper avança só o que faltar (plan / ready /
    execute), conforme o estado real lido do board — se o motor já avançar sozinho, o teste se adapta.
  * Recusa = exit 1 (hcore.Refused). Exit 2 do argparse ("--quick"/"ask" desconhecidos) NÃO conta como recusa.
  * "Suba a classe": exigido no stderr da recusa de `add task --quick` (o contrato cita a mensagem literal), junto
    com "triage" (o comando de reclassificação que a mensagem indica).
"""
import json
import os
import subprocess
import sys
import unittest

# roda tanto por `python3 -m unittest discover -s tests` quanto por `python3 -m unittest tests.test_faixas_aceite`
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import fixture  # noqa: E402
import hcore  # noqa: E402

STATE = os.path.join(fixture.ENGINE, "state.py")
GUARD = os.path.join(fixture.ENGINE, "guard.py")
VERIFY = "python3 -m unittest discover -s tests -t ."
AC = "AC-1|desconto aplicado ao total do pedido|test:tests.test_billing"


# ------------------------------------------------------------------ helpers (CLI e hooks reais)
def cs(root, *args, actor=None):
    argv = [sys.executable, STATE, "--root", root]
    if actor:
        argv += ["--actor", actor]
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CS_ACTOR", None)
    p = subprocess.run(argv + list(args), cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def hook(root, mode, payload):
    e = dict(os.environ)
    e.pop("CS_GUARD_OFF", None)
    e["CLAUDE_PROJECT_DIR"] = root
    p = subprocess.run([sys.executable, GUARD, mode], input=json.dumps(payload).encode(), env=e, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=120)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def agent_payload(desc, st, model=None, actor=None, tuid="tu-ag"):
    ti = {"description": desc, "prompt": "responda", "subagent_type": st}
    if model:
        ti["model"] = model
    p = {"tool_name": "Agent", "tool_use_id": tuid, "tool_input": ti}
    p.update(actor or {})
    return p


def write_payload(root, rel, actor, tool="Write"):
    p = {"tool_name": tool, "tool_use_id": "tu-w", "tool_input": {"file_path": os.path.join(root, rel)}, "cwd": root}
    p.update(actor)
    return p


def bash_payload(root, cmd, actor=None):
    p = {"tool_name": "Bash", "tool_use_id": "tu-b", "tool_input": {"command": cmd}, "cwd": root}
    p.update(actor or {})
    return p


def board(root):
    return hcore.load_board(root)


def walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            for x in walk(v):
                yield x
    elif isinstance(obj, list):
        for v in obj:
            for x in walk(v):
                yield x


def consults(root):
    return [d for d in walk(board(root)) if d.get("kind") == "consult" and d.get("id")]


def consult_by_id(root, cid):
    for d in consults(root):
        if d["id"] == cid:
            return d
    return None


def chain_mentions(root, needle):
    sp = hcore.state_paths(root)
    for k in ("events", "ledger"):
        path = sp[k]
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            if needle in f.read():
                return True
    return False


def session(root):
    ss = [s for s in board(root)["sessions"] if s["state"] != "IDLE"]
    return ss[-1] if ss else None


def start_session(tc, root, klass):
    code, out, err = cs(root, "session", "start", "--request", "pedido do usuário")
    tc.assertEqual(code, 0, err)
    code, out, err = cs(root, "session", "triage", "--class", klass, "--why", "teste de aceite")
    tc.assertEqual(code, 0, err)


def add_quick(root, paths=("src/billing/discount.py",), agent="dev-billing", title="criar desconto"):
    args = ["add", "task", "--quick", "--agent", agent, "--title", title, "--verify-cmd", VERIFY, "--ac", AC,
            "--goal", "aplicar desconto porque o pedido exige", "--ref", "src/billing/total.py:1", "--out", "tax: outra task"]
    for p in paths:
        args += ["--allowed-path", p]
    return cs(root, *args)


def new_task_ids(root, before):
    return [t["id"] for t in board(root)["tasks"] if t["id"] not in before]


def latest_deleg(task):
    ds = task.get("delegations") or []
    return ds[-1] if ds else None


def advance_to_executing(tc, root, tid):
    """Avança só o que faltar: plan (TRIAGE→PLANNING), ready (PLANNED→BRIEFED), execute (PLANNING→EXECUTING)."""
    if session(root)["state"] == "TRIAGE":
        code, _, err = cs(root, "session", "plan")
        tc.assertEqual(code, 0, err)
    t = hcore.find(board(root), "task", tid)
    if latest_deleg(t)["state"] == "PLANNED":
        code, _, err = cs(root, "ready", "--task", tid)
        tc.assertEqual(code, 0, err)
    if session(root)["state"] == "PLANNING":
        code, _, err = cs(root, "session", "execute")
        tc.assertEqual(code, 0, err)
    tc.assertEqual(session(root)["state"], "EXECUTING")


def dispatch_via_hook(tc, root, tid, agent="dev-billing"):
    d = latest_deleg(hcore.find(board(root), "task", tid))
    tc.assertEqual(d["state"], "BRIEFED")
    code, _, err = hook(root, "pre-agent", agent_payload("%s: implementar" % d["id"], agent, model=d["route"]["model"]))
    tc.assertEqual(code, 0, err)
    tc.assertEqual(latest_deleg(hcore.find(board(root), "task", tid))["state"], "DISPATCHED")


def implement_and_submit(tc, root, tid, rel="src/billing/discount.py", agent="dev-billing"):
    sub = {"agent_id": "ag-1", "agent_type": agent}
    code, _, err = hook(root, "pre-write", write_payload(root, rel, sub))
    tc.assertEqual(code, 0, err)  # território da task: subagente de task escreve
    fixture.write(root, rel)
    code, _, err = cs(root, "submit", "--task", tid, "--files-changed", rel, "--check", "unittest: OK", "--risk", "nenhum",
                      "--handoff-notes", "ok", actor=agent)
    tc.assertEqual(code, 0, err)


def verify_ok(tc, root, tid):
    code, out, err = cs(root, "verify", "--task", tid)
    tc.assertEqual(code, 0, err)
    tc.assertIn("verify PASS", out, out + err)


class Base(unittest.TestCase):
    def setUp(self):
        self.roots = []

    def tearDown(self):
        for r in self.roots:
            fixture.rm(r)

    def repo(self, **kw):
        r = fixture.make_repo(**kw)
        self.roots.append(r)
        return r

    def quick_task(self, root, klass, paths=("src/billing/discount.py",)):
        start_session(self, root, klass)
        before = {t["id"] for t in board(root)["tasks"]}
        code, out, err = add_quick(root, paths)
        self.assertEqual(code, 0, "add task --quick deveria criar a task (exit %d): %s%s" % (code, out, err))
        ids = new_task_ids(root, before)
        self.assertEqual(len(ids), 1, ids)
        return ids[0]

    def ask(self, root, agent="dev-billing", question="como o total do pedido é calculado?"):
        code, out, err = cs(root, "ask", agent, question, "--paths", "src/billing/**")
        self.assertEqual(code, 0, "cs-state ask deveria criar a consulta (exit %d): %s%s" % (code, out, err))
        cs_ = [c for c in consults(root) if c.get("agent") == agent and c.get("state") == "BRIEFED"]
        self.assertEqual(len(cs_), 1, "esperada 1 delegação kind=consult BRIEFED para %s; achei %r" % (agent, consults(root)))
        cid = cs_[0]["id"]
        self.assertIn(cid, out, "ask deve imprimir o id da consulta para a description do Agent")
        return cid, out.strip(), cs_[0]


# ------------------------------------------------------------------ CONSULT
class TestConsulta(Base):
    def test_consult_1_ask_sem_story_despacho_aceito_subagente_so_leitura_e_ledger(self):
        root = self.repo()
        start_session(self, root, "pergunta")
        # o agente principal pode rodar `cs-state ask` pelo Bash (guard não pode tratar `ask` como desconhecido)
        code, _, err = hook(root, "pre-bash", bash_payload(root, ".swarm/bin/cs-state ask dev-billing 'como calcula'"))
        self.assertEqual(code, 0, "principal rodando cs-state ask deveria passar no guard: " + err)

        cid, out, c = self.ask(root)
        b = board(root)
        self.assertEqual(b["tasks"], [], "consulta não cria task")
        self.assertEqual(b["stories"], [], "consulta não cria story")

        model = (c.get("route") or {}).get("model") or "sonnet"
        code, _, err = hook(root, "pre-agent", agent_payload(out, "dev-billing", model=model))
        self.assertEqual(code, 0, "despacho citando a consulta deve ser aceito: " + err)

        sub = {"agent_id": "ag-c", "agent_type": "dev-billing"}
        # só leitura: escrita bloqueada MESMO dentro do território do agente
        for tool in ("Write", "Edit"):
            code, _, err = hook(root, "pre-write", write_payload(root, "src/billing/discount.py", sub, tool))
            self.assertEqual(code, 2, "%s do subagente de consulta deve ser bloqueado" % tool)
        code, _, _ = hook(root, "pre-bash", bash_payload(root, "touch src/billing/discount.py", sub))
        self.assertEqual(code, 2, "Bash que escreve, do subagente de consulta, deve ser bloqueado")
        code, _, err = hook(root, "pre-bash", bash_payload(root, "ls src/billing", sub))
        self.assertEqual(code, 0, "leitura continua permitida na consulta: " + err)
        self.assertFalse(os.path.exists(os.path.join(root, "src/billing/discount.py")))

        # ao terminar, fecha sozinha (ANSWERED), sem pedir submission
        code, sout, _ = hook(root, "subagent-stop", {"hook_event_name": "SubagentStop", **sub})
        self.assertEqual(code, 0)
        self.assertNotIn('"block"', sout, "consulta não exige submit ao encerrar")
        self.assertEqual((consult_by_id(root, cid) or {}).get("state"), "ANSWERED")
        b = board(root)
        self.assertEqual((b["tasks"], b["stories"]), ([], []), "sem task, sem story, sem review")
        self.assertTrue(chain_mentions(root, cid), "ledger/events deve ter o evento da consulta %s" % cid)

    def test_consult_2_despacho_sem_ask_continua_bloqueado(self):
        root = self.repo()
        start_session(self, root, "pergunta")
        # sem ask e sem delegação: bloqueado (com e sem model)
        self.assertEqual(hook(root, "pre-agent", agent_payload("pergunta sobre billing", "dev-billing", model="sonnet"))[0], 2)
        self.assertEqual(hook(root, "pre-agent", agent_payload("pergunta sobre billing", "dev-billing"))[0], 2)

        cid, out, c = self.ask(root)
        model = (c.get("route") or {}).get("model") or "sonnet"
        # a consulta existir não abre brecha: sem citar o id → bloqueado
        self.assertEqual(hook(root, "pre-agent", agent_payload("pergunta sobre billing", "dev-billing", model=model))[0], 2)
        # consulta de dev-billing não autoriza outro agente
        self.assertEqual(hook(root, "pre-agent", agent_payload(out, "dev-users", model=model))[0], 2)
        # subagente não despacha, nem com o id
        self.assertEqual(hook(root, "pre-agent", agent_payload(out, "dev-billing", model=model,
                                                               actor={"agent_id": "x", "agent_type": "dev-users"}))[0], 2)
        # subagente não cria consulta pelo Bash
        self.assertEqual(hook(root, "pre-bash", bash_payload(root, "cs-state ask dev-users 'x'",
                                                             {"agent_id": "x", "agent_type": "dev-billing"}))[0], 2)
        # despacho legítimo passa; a consulta é descartável: depois de ANSWERED o mesmo id não serve de novo
        code, _, err = hook(root, "pre-agent", agent_payload(out, "dev-billing", model=model))
        self.assertEqual(code, 0, err)
        hook(root, "subagent-stop", {"hook_event_name": "SubagentStop", "agent_id": "ag-c", "agent_type": "dev-billing"})
        self.assertEqual((consult_by_id(root, cid) or {}).get("state"), "ANSWERED")
        self.assertEqual(hook(root, "pre-agent", agent_payload(out, "dev-billing", model=model, tuid="tu-2"))[0], 2,
                         "consulta ANSWERED não pode ser reusada para novo despacho")


# ------------------------------------------------------------------ QUICK
class TestTaskAvulsa(Base):
    def test_quick_1_sessao_trivial_cria_task_sem_hierarquia_e_verify_accept_funcionam(self):
        root = self.repo(no_rules=True)  # sem invariante escopado em src/billing (trivial não toca invariante)
        tid = self.quick_task(root, "trivial")
        b = board(root)
        t = hcore.find(b, "task", tid)
        self.assertIn("AVULSA", (t.get("story") or "").upper(), "task avulsa vai para a story implícita STORY-AVULSA")
        self.assertEqual((b["epics"], b["features"], b["sprints"]), ([], [], []), "sem épico/feature/sprint explícitos")
        self.assertEqual(t["allowed_paths"], ["src/billing/discount.py"])
        self.assertIn(VERIFY, t["verification_command"])

        advance_to_executing(self, root, tid)
        dispatch_via_hook(self, root, tid)
        implement_and_submit(self, root, tid)
        verify_ok(self, root, tid)
        code, out, err = cs(root, "accept", "--task", tid)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(hcore.find(board(root), "task", tid)["status"], "ACCEPTED")

    def test_quick_2_sessao_feature_recusa_add_task_quick(self):
        root = self.repo(no_rules=True)
        # sem sessão: recusa (exit 1 = recusa do motor; exit 2 do argparse não conta)
        code, out, err = add_quick(root)
        self.assertEqual(code, 1, "sem sessão triada: recusa (exit 1). exit=%d %s%s" % (code, out, err))
        start_session(self, root, "feature")
        code, out, err = add_quick(root)
        self.assertEqual(code, 1, "sessão feature: --quick recusado (exit 1). exit=%d %s%s" % (code, out, err))
        self.assertEqual(board(root)["tasks"], [], "recusa não cria task")
        for klass in ("risco", "pergunta"):
            cs(root, "session", "triage", "--class", klass, "--why", "reclassificado")
            code, out, err = add_quick(root)
            self.assertEqual(code, 1, "sessão %s: --quick recusado. exit=%d %s%s" % (klass, code, out, err))
        self.assertEqual(board(root)["tasks"], [])

    def _assert_promote(self, root, paths):
        before = len(board(root)["tasks"])
        code, out, err = add_quick(root, paths)
        self.assertEqual(code, 1, "esperada recusa (exit 1) para %s. exit=%d %s%s" % (paths, code, out, err))
        self.assertIn("suba a classe", (out + err).lower())
        self.assertIn("triage", out + err)
        self.assertEqual(len(board(root)["tasks"]), before, "recusa não cria task")

    def test_quick_3_task_avulsa_em_dois_territorios_ou_invariante_pede_subir_classe(self):
        # (a) dois territórios
        root = self.repo(no_rules=True)
        start_session(self, root, "pequena")
        self._assert_promote(root, ("src/billing/discount.py", "src/users/discount.py"))
        # (b) invariante escopado (rule.billing.cents / br.billing.max-discount em src/billing/**)
        root = self.repo()
        start_session(self, root, "pequena")
        self._assert_promote(root, ("src/billing/discount.py",))
        # (c) área congelada
        root = self.repo(no_rules=True)
        hcore.write_json5(hcore.state_paths(root)["config"], {"frozen_paths": ["src/billing/tax.py"]}, "teste")
        start_session(self, root, "pequena")
        self._assert_promote(root, ("src/billing/tax.py",))


# ------------------------------------------------------------------ PEQUENA
class TestPequena(Base):
    def test_pequena_1_avulsa_pequena_exige_1_revisao_de_gate_trivial_nao(self):
        # pequena: accept sem revisão é recusado; com 1 review PASS de gate, aceita
        root = self.repo(no_rules=True)
        tid = self.quick_task(root, "pequena")
        advance_to_executing(self, root, tid)
        dispatch_via_hook(self, root, tid)
        implement_and_submit(self, root, tid)
        verify_ok(self, root, tid)
        code, out, err = cs(root, "accept", "--task", tid)
        self.assertEqual(code, 1, "pequena sem revisão de gate não pode ser ACCEPTED: " + out + err)
        self.assertNotEqual(hcore.find(board(root), "task", tid)["status"], "ACCEPTED")
        code, out, err = cs(root, "review", "--task", tid, "--by", "reviewer", "--verdict", "PASS",
                            "--findings", "ok discount.py:1", actor="reviewer")
        self.assertEqual(code, 0, out + err)
        code, out, err = cs(root, "accept", "--task", tid)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(hcore.find(board(root), "task", tid)["status"], "ACCEPTED")

        # trivial: aceita sem revisão
        root2 = self.repo(no_rules=True)
        tid2 = self.quick_task(root2, "trivial")
        advance_to_executing(self, root2, tid2)
        dispatch_via_hook(self, root2, tid2)
        implement_and_submit(self, root2, tid2)
        verify_ok(self, root2, tid2)
        code, out, err = cs(root2, "accept", "--task", tid2)
        self.assertEqual(code, 0, "trivial avulsa aceita sem revisão: " + out + err)
        t2 = hcore.find(board(root2), "task", tid2)
        self.assertEqual(t2["status"], "ACCEPTED")
        self.assertEqual(t2.get("reviews") or [], [])


# ------------------------------------------------------------------ regressão
class TestRegressaoFluxoCompleto(Base):
    def test_regressao_fluxo_completo_story_task_delegacao(self):
        root = self.repo()
        fixture.process(root, "pequena")  # épico → feature → story READY → sessão PLANNING (classe pequena)
        # task sem --quick continua exigindo story
        code, out, err = cs(root, "add", "task", "--agent", "dev-billing", "--title", "x",
                            "--allowed-path", "src/billing/discount.py", "--verify-cmd", VERIFY)
        self.assertEqual(code, 1, out + err)
        self.assertIn("Story", out + err)
        code, out, err = cs(root, "add", "task", "--story", "US-1", "--agent", "dev-billing", "--title", "criar desconto",
                            "--goal", "aplicar desconto porque FEAT-1 exige", "--allowed-path", "src/billing/discount.py",
                            "--verify-cmd", VERIFY, "--ac", AC, "--ref", "src/billing/total.py:1", "--in", "desconto",
                            "--out", "tax: outra task", "--ready")
        self.assertEqual(code, 0, out + err)
        t = hcore.find(board(root), "task", "T-1")
        self.assertEqual(t["story"], "US-1")
        advance_to_executing(self, root, "T-1")
        # despacho sem id continua bloqueado; com id BRIEFED + model passa
        self.assertEqual(hook(root, "pre-agent", agent_payload("faz o desconto", "dev-billing", model="sonnet"))[0], 2)
        dispatch_via_hook(self, root, "T-1")
        # fora do território continua bloqueado para o subagente da task
        sub = {"agent_id": "ag-1", "agent_type": "dev-billing"}
        self.assertEqual(hook(root, "pre-write", write_payload(root, "src/billing/tax.py", sub))[0], 2)
        implement_and_submit(self, root, "T-1")
        verify_ok(self, root, "T-1")
        self.assertEqual(cs(root, "accept", "--task", "T-1")[0], 1)  # pequena: precisa de review
        code, out, err = cs(root, "review", "--task", "T-1", "--by", "reviewer", "--verdict", "PASS",
                            "--findings", "ok discount.py:1", actor="reviewer")
        self.assertEqual(code, 0, out + err)
        code, out, err = cs(root, "accept", "--task", "T-1")
        self.assertEqual(code, 0, out + err)
        b = board(root)
        self.assertEqual(hcore.find(b, "task", "T-1")["status"], "ACCEPTED")
        self.assertEqual(hcore.find(b, "story", "US-1")["state"], "IN_REVIEW")
        import validate
        ok, errs, _ = validate.run(root, strict=True)
        self.assertTrue(ok, errs)


if __name__ == "__main__":
    unittest.main()
