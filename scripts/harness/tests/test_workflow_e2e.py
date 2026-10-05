"""ORÁCULO — WORKFLOW-E2E: o workflow inteiro do harness, de ponta a ponta (plano da rodada,
"OBRIGATÓRIO em toda rodada — workflow inteiro do harness testado de ponta a ponta"; máquinas em docs/02-harness.md).

Tudo pelo comportamento OBSERVÁVEL: CLI real (engine/state.py = cs-state, engine/session.py = cs-session e
engine/validate.py, em subprocesso) e guard real (engine/guard.py com payloads de hook), num repo git temporário
(fixture.make_repo). Nada de mock do motor. Este arquivo é contrato: quem implementa não o edita.

Cada teste percorre um caminho e TERMINA num estado coerente (`assert_coerente`):
  * `validate --strict` OK (replay da cadeia);
  * nada trancado: nenhuma sessão M1 aberta (todas IDLE), toda task ACCEPTED ou DROPPED, nenhuma delegação fora de
    estado terminal, mandato autônomo (se houver) fora de ESCALATED/ACTIVE, e `cs-state next` responde (exit 0).

Escolhas onde o contrato não fixa detalhe:
  * Hierarquia: o modelo ATUAL do motor (épico → feature → story → task; sprint agrupa stories). A árvore
    épico → sprint → feature(s) → tasks é rodada futura e NÃO é testada aqui.
  * "verify falho → reject": no motor a falha do verify já leva a delegação a REJECTED (on_guard_fail); o `reject`
    explícito (`cs-state reject`) é exercitado no caminho review FAIL (VERIFIED/REVIEWED → REJECTED).
  * Despacho em ondas: classe `feature` (2 territórios) exige task do po ACCEPTED antes do dev. "Arquivo comum": o
    time do repo temporário ganha `src/shared/**` no território dos dois devs, para que dois agentes DIFERENTES
    disputem o mesmo arquivo (com o mesmo agente, `one_in_flight_per_agent` mascararia a colisão).
  * Falha de AMBIENTE: o verification_command é `sh tools/verify_env.sh`, que sai 127 ("command not found")
    enquanto um marcador FORA do repo não existe; "consertar o ambiente" = criar o marcador (nenhum arquivo do repo
    muda, então o diff × allowed_paths continua limpo).
  * `failure_kind`: procurado em QUALQUER dict da task (delegação, gate_report, build...) — o contrato fixa o campo
    e o valor `environment`, não onde ele mora. Para falha de asserção, exige-se apenas que NÃO seja `environment`.
  * `waive-verify --task T --by <humano> --reason ... --evidence ...`: "humano" = não é agente de team.json5 nem o
    orquestrador (`lead`: "lead não pode auto-aprovar", decisão de produto A2); usa-se `founder`. O `--evidence` cita a
    saída real do verify (o motor exige que a evidência nomeie a ferramenta ausente, aqui `fake-dep`). Depois do waive a
    revisão continua obrigatória: o aceite sem review de gate é recusado (testado em classe `pequena`, onde a review
    já é exigida, e em `trivial`, onde só o waive a tornaria obrigatória — este último isolado num teste próprio).
  * `reverify --task T`: roda o verify de novo sobre a MESMA submissão (sem novo despacho: `attempts` não muda).
  * Recusa = exit 1 (hcore.Refused). Exit 2 do argparse (subcomando inexistente) NÃO conta como recusa.

DEPENDEM DA FRENTE EM ANDAMENTO (decisões de produto A1/A2) — podem falhar hoje:
  [A2] `reverify`, `waive-verify`, `failure_kind: environment` → classe TestFalhaDeAmbiente inteira.
  [A1] `retry --decision`, `reroute --decision`, `drop --reason` de ESCALATED/ABSTAINED → classe TestEscaladaSaidas
       e o meio do TestAutonomoE2E (retomada da delegação abstida).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import fixture  # noqa: E402
import hcore  # noqa: E402
import j5  # noqa: E402
from test_faixas_aceite import (agent_payload, bash_payload, board, consults, cs, hook, latest_deleg,  # noqa: E402
                                write_payload)

SESSION = os.path.join(fixture.ENGINE, "session.py")
VALIDATE = os.path.join(fixture.ENGINE, "validate.py")
VERIFY = "python3 -m unittest discover -s tests -t ."
VERIFY_ASSERT = "python3 -m unittest tests.test_discount"
VERIFY_ENV = "sh tools/verify_env.sh"
AC = "AC-1|desconto aplicado ao total do pedido|test:tests.test_billing"
HUMAN = "founder"

TEST_DISCOUNT = """import os
import unittest


class D(unittest.TestCase):
    def test_rate(self):
        p = os.path.join('src', 'billing', 'discount.py')
        self.assertTrue(os.path.exists(p), 'discount.py ausente')
        with open(p) as f:
            self.assertIn('RATE = 30', f.read())
"""

VERIFY_ENV_SH = """#!/bin/sh
# simula dependência de AMBIENTE ausente (ex.: httpx/ferramenta fora do PATH): sai 127 até o marcador existir
if [ ! -f "%s" ]; then
  echo "fake-dep: command not found" >&2
  exit 127
fi
exec python3 -m unittest discover -s tests -t .
"""


# ------------------------------------------------------------------ helpers de processo (subprocesso real)
def run_py(script, root, *args, env_extra=None):
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CS_ACTOR", None)
    env.update(env_extra or {})
    p = subprocess.run([sys.executable, script, "--root", root] + list(args), cwd=root, env=env, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=180)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


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


def task(root, tid):
    return hcore.find(board(root), "task", tid)


def deleg(root, tid):
    return latest_deleg(task(root, tid))


def failure_kinds(root, tid):
    return [d["failure_kind"] for d in walk(task(root, tid)) if "failure_kind" in d]


def commit_all(root, msg="setup e2e"):
    fixture.git(root, "add", "-A")
    fixture.git(root, "commit", "-qm", msg)


class E2E(unittest.TestCase):
    """Base: repo temporário + atalhos para CLI/hook reais com asserção de exit."""

    def setUp(self):
        self._tmp = []

    def tearDown(self):
        for r in self._tmp:
            shutil.rmtree(r, ignore_errors=True)

    def repo(self, **kw):
        r = fixture.make_repo(**kw)
        self._tmp.append(r)
        return r

    def outside_dir(self):
        d = os.path.realpath(tempfile.mkdtemp(prefix="cs-e2e-env-"))
        self._tmp.append(d)
        return d

    # --- cs-state
    def ok(self, root, *args, actor=None):
        code, out, err = cs(root, *args, actor=actor)
        self.assertEqual(code, 0, "cs-state %s → exit %d\n%s%s" % (" ".join(args), code, out, err))
        return out

    def refused(self, root, *args, actor=None):
        code, out, err = cs(root, *args, actor=actor)
        self.assertEqual(code, 1, "cs-state %s deveria ser RECUSADO (exit 1), deu %d\n%s%s" % (" ".join(args), code, out, err))
        return out + err

    # --- processo épico → feature → story (CLI)
    def process(self, root, klass="pequena", sprint=False):
        self.ok(root, "add", "epic", "--title", "Billing", "--objective", "cobrar certo", "--metric", "receita")
        self.ok(root, "epic", "activate", "--id", "EPIC-1")
        self.ok(root, "add", "feature", "--epic", "EPIC-1", "--title", "Desconto", "--spec", "spec/feat.md",
                "--accept-cmd", "python3 -m unittest accept.test_accept", "--accept-file", "accept/test_accept.py")
        self.ok(root, "feature", "ready", "--id", "FEAT-1")
        self.ok(root, "add", "story", "--type", "us", "--feature", "FEAT-1", "--title", "Como cliente quero desconto",
                "--as-a", "cliente", "--i-want", "desconto", "--so-that", "pagar menos",
                "--criterion", "AC-1|Dado pedido Quando aplico Então desconta|tests.test_billing")
        self.ok(root, "story", "ready", "--id", "US-1")
        if sprint:
            self.ok(root, "sprint", "plan", "--goal", "entregar o desconto", "--budget", "tasks=8,attempts=2,minutes=120",
                    "--add", "US-1")
            self.ok(root, "sprint", "start")
            self.assertEqual(board(root)["sprints"][-1]["state"], "ACTIVE")
        self.ok(root, "session", "start", "--request", "implementar o desconto do pedido")
        self.ok(root, "session", "triage", "--class", klass, "--why", "teste e2e")
        self.ok(root, "session", "plan")

    def add_task(self, root, agent, path, title, wave=1, verify=VERIFY, ref="src/billing/total.py:1"):
        before = {t["id"] for t in board(root)["tasks"]}
        self.ok(root, "add", "task", "--story", "US-1", "--agent", agent, "--title", title,
                "--goal", "%s porque FEAT-1 exige" % title, "--allowed-path", path, "--verify-cmd", verify,
                "--ac", AC, "--ref", ref, "--in", title, "--out", "tax: outra task", "--wave", str(wave), "--ready")
        new = [t["id"] for t in board(root)["tasks"] if t["id"] not in before]
        self.assertEqual(len(new), 1, new)
        self.assertEqual(deleg(root, new[0])["state"], "BRIEFED")
        return new[0]

    # --- delegação via guard real
    def dispatch(self, root, tid, agent, tuid):
        d = deleg(root, tid)
        self.assertEqual(d["state"], "BRIEFED", d)
        code, _, err = hook(root, "pre-agent", agent_payload("%s: implementar" % d["id"], agent, model=d["route"]["model"],
                                                             tuid=tuid))
        self.assertEqual(code, 0, "despacho de %s deveria passar no guard: %s" % (d["id"], err))
        self.assertEqual(deleg(root, tid)["state"], "DISPATCHED")

    def dispatch_blocked(self, root, tid, agent, tuid):
        d = deleg(root, tid)
        code, _, err = hook(root, "pre-agent", agent_payload("%s: implementar" % d["id"], agent, model=d["route"]["model"],
                                                             tuid=tuid))
        self.assertEqual(code, 2, "despacho de %s deveria ser BLOQUEADO pelo guard" % d["id"])
        self.assertEqual(deleg(root, tid)["state"], "BRIEFED", "despacho bloqueado não muda o estado")
        return err

    def implement(self, root, tid, agent, rel, txt):
        sub = {"agent_id": "ag-%s" % tid, "agent_type": agent}
        code, _, err = hook(root, "pre-write", write_payload(root, rel, sub))
        self.assertEqual(code, 0, "subagente %s escrevendo %s no próprio território: %s" % (agent, rel, err))
        fixture.write(root, rel, txt)
        self.ok(root, "submit", "--task", tid, "--files-changed", rel, "--check", "unittest: OK", "--risk", "nenhum",
                "--handoff-notes", "ok", actor=agent)
        self.assertEqual(deleg(root, tid)["state"], "RETURNED")

    def verify_pass(self, root, tid):
        out = self.ok(root, "verify", "--task", tid)
        self.assertIn("verify PASS", out, out)
        self.assertEqual(deleg(root, tid)["state"], "VERIFIED")

    def verify_fail(self, root, tid):
        out = self.ok(root, "verify", "--task", tid)
        self.assertIn("REPROVOU", out, out)
        self.assertEqual(deleg(root, tid)["state"], "REJECTED")
        return out

    def review(self, root, tid, verdict="PASS", by="reviewer"):
        self.ok(root, "review", "--task", tid, "--by", by, "--verdict", verdict, "--findings", "%s: ok file:1" % verdict,
                actor=by)

    def accept(self, root, tid):
        self.ok(root, "accept", "--task", tid)
        self.assertEqual((deleg(root, tid)["state"], task(root, tid)["status"]), ("ACCEPTED", "ACCEPTED"))

    def full_task(self, root, tid, agent, rel, txt, tuid, review=True):
        self.dispatch(root, tid, agent, tuid)
        self.implement(root, tid, agent, rel, txt)
        self.verify_pass(root, tid)
        if review:
            self.review(root, tid)
        self.accept(root, tid)

    def close_session(self, root, final_review=False):
        self.ok(root, "session", "verify")
        if final_review:
            self.ok(root, "session", "review", "--by", "reviewer", "--verdict", "PASS", "--findings", "entrega ok")
        self.ok(root, "session", "report")
        self.ok(root, "session", "close")

    # --- estado coerente, nada trancado
    def assert_coerente(self, root):
        code, out, err = run_py(VALIDATE, root, "--strict")
        self.assertEqual(code, 0, "validate --strict: %s%s" % (out, err))
        b = board(root)
        aberto = [(s["id"], s["state"]) for s in b["sessions"] if s["state"] != "IDLE"]
        self.assertEqual(aberto, [], "sessão M1 ficou aberta")
        for t in b["tasks"]:
            self.assertIn(t["status"], ("ACCEPTED", "DROPPED"), "task %s ficou em %s" % (t["id"], t["status"]))
            for d in t.get("delegations") or []:
                self.assertIn(d["state"], ("ACCEPTED", "REROUTED", "DROPPED"), "delegação %s ficou em %s" % (d["id"], d["state"]))
        for c in b.get("consults") or []:
            self.assertIn(c["state"], ("ANSWERED", "CANCELLED"), "consulta %s ficou em %s" % (c["id"], c["state"]))
        import autonomy
        m = autonomy.load(root)
        if m:
            self.assertIn(m["state"], ("DONE", "STOPPED"), "mandato autônomo ficou em %s" % m["state"])
        self.ok(root, "next")


# ------------------------------------------------------------------ 1. fluxo completo + ondas + fechamento de níveis
class TestFluxoCompleto(E2E):
    def _team_with_shared(self, root):
        with open(os.path.join(root, hcore.STATE_DIR, "team.json5"), encoding="utf-8") as f:
            team = j5.loads(f.read())
        for a in team["agents"]:
            if a["name"] in ("dev-billing", "dev-members"):
                a["territory"] = list(a["territory"]) + ["src/shared/**"]
        with open(os.path.join(root, hcore.STATE_DIR, "team.json5"), "w", encoding="utf-8") as f:
            f.write(j5.dumps(team))
        fixture.write(root, "src/shared/util.py", "SHARED = 0\n")
        commit_all(root, "time com src/shared/** compartilhado")

    def test_epico_feature_story_tasks_ondas_sem_colisao_e_fechamento_de_todos_os_niveis(self):
        root = self.repo()
        self._team_with_shared(root)
        self.process(root, "feature", sprint=True)
        po = self.add_task(root, "po", "docs/stories/US-1.md", "detalhar a story", wave=1, ref="docs/stories/README.md:1")
        t_bil = self.add_task(root, "dev-billing", "src/billing/discount.py", "criar desconto", wave=2)
        t_usr = self.add_task(root, "dev-members", "src/members/discount.py", "elegibilidade do desconto", wave=2,
                              ref="src/members/model.py:1")
        t_sh1 = self.add_task(root, "dev-members", "src/shared/util.py", "util compartilhado (users)", wave=3)
        t_sh2 = self.add_task(root, "dev-billing", "src/shared/util.py", "util compartilhado (billing)", wave=4)
        self.ok(root, "session", "execute")

        # classe feature: dev só depois da task do po ACCEPTED
        self.dispatch_blocked(root, t_bil, "dev-billing", "tu-early")
        self.full_task(root, po, "po", "docs/stories/US-1.md", "# US-1 detalhada\n", "tu-po")

        # onda 2: dois agentes, arquivos disjuntos → em voo AO MESMO TEMPO
        self.dispatch(root, t_bil, "dev-billing", "tu-bil")
        self.dispatch(root, t_usr, "dev-members", "tu-usr")
        self.assertEqual((deleg(root, t_bil)["state"], deleg(root, t_usr)["state"]), ("DISPATCHED", "DISPATCHED"))
        self.implement(root, t_bil, "dev-billing", "src/billing/discount.py", "RATE = 30\n")
        self.implement(root, t_usr, "dev-members", "src/members/discount.py", "ELIGIBLE = True\n")
        self.verify_pass(root, t_bil)
        self.verify_pass(root, t_usr)  # o arquivo da onda-irmã (já VERIFIED) não pode contar como "fora de allowed_paths"
        for t in (t_bil, t_usr):
            self.review(root, t)
            self.accept(root, t)

        # arquivo comum: a 2ª espera a 1ª
        self.dispatch(root, t_sh1, "dev-members", "tu-sh1")
        err = self.dispatch_blocked(root, t_sh2, "dev-billing", "tu-sh2-cedo")
        self.assertIn("colide", err, err)
        self.implement(root, t_sh1, "dev-members", "src/shared/util.py", "SHARED = 1\n")
        self.verify_pass(root, t_sh1)
        self.review(root, t_sh1)
        self.accept(root, t_sh1)
        self.full_task(root, t_sh2, "dev-billing", "src/shared/util.py", "SHARED = 2\n", "tu-sh2")

        # fechamento: sessão (review final da classe feature) → story → feature → épico → sprint
        self.close_session(root, final_review=True)
        b = board(root)
        self.assertEqual(hcore.find(b, "story", "US-1")["state"], "IN_REVIEW")
        self.ok(root, "story", "done", "--id", "US-1")
        self.ok(root, "feature", "done", "--id", "FEAT-1")
        self.ok(root, "epic", "done", "--id", "EPIC-1")
        self.ok(root, "sprint", "review")
        self.ok(root, "sprint", "close")
        b = board(root)
        self.assertEqual((hcore.find(b, "story", "US-1")["state"], hcore.find(b, "feature", "FEAT-1")["state"],
                          hcore.find(b, "epic", "EPIC-1")["state"], b["sprints"][-1]["state"]),
                         ("DONE", "DONE", "DONE", "CLOSED"))
        self.assertEqual(b["sprints"][-1]["review"]["delivered"], ["US-1"])
        self.assert_coerente(root)

    def test_mesmo_arquivo_na_mesma_onda_recusa_execute_e_ondas_separadas_destravam(self):
        root = self.repo()
        self._team_with_shared(root)
        self.process(root, "feature")
        po = self.add_task(root, "po", "docs/stories/US-1.md", "detalhar a story", wave=1, ref="docs/stories/README.md:1")
        a = self.add_task(root, "dev-members", "src/shared/util.py", "util (users)", wave=2)
        b_ = self.add_task(root, "dev-billing", "src/shared/util.py", "util (billing)", wave=2)
        out = self.refused(root, "session", "execute")
        self.assertIn("wave", out)
        self.ok(root, "amend", "--task", b_, "--field", "wave", "--after", "3", "--reason", "mesmo arquivo: onda seguinte")
        if deleg(root, b_)["state"] == "PLANNED":
            self.ok(root, "ready", "--task", b_)
        self.ok(root, "session", "execute")
        self.full_task(root, po, "po", "docs/stories/US-1.md", "# US-1\n", "tu-po")
        self.full_task(root, a, "dev-members", "src/shared/util.py", "SHARED = 1\n", "tu-a")
        self.full_task(root, b_, "dev-billing", "src/shared/util.py", "SHARED = 2\n", "tu-b")
        self.close_session(root, final_review=True)
        self.assert_coerente(root)


# ------------------------------------------------------------------ 2. verify / reject / retry / review
class TestVerifyReview(E2E):
    def _repo_assert(self):
        root = self.repo()
        fixture.write(root, "tests/test_discount.py", TEST_DISCOUNT)
        commit_all(root)
        return root

    def test_submit_verify_falho_reject_retry_verify_ok_review_pass_accept(self):
        root = self._repo_assert()
        self.process(root, "pequena")
        t = self.add_task(root, "dev-billing", "src/billing/discount.py", "criar desconto", verify=VERIFY_ASSERT)
        self.ok(root, "session", "execute")
        self.dispatch(root, t, "dev-billing", "tu-1")
        self.implement(root, t, "dev-billing", "src/billing/discount.py", "RATE = 10\n")
        self.verify_fail(root, t)  # falha de ASSERÇÃO → REJECTED (o reject do gate)
        self.assertEqual(task(root, t)["status"], "REJECTED")
        self.assertTrue(task(root, t).get("reject_reason"))
        self.assertNotIn("environment", failure_kinds(root, t), "falha de asserção não é ambiente")
        self.refused(root, "accept", "--task", t)
        self.assertIn("cs-state retry --task %s" % t, self.ok(root, "next"))
        self.ok(root, "retry", "--task", t, "--findings", "RATE deve ser 30 (tests/test_discount.py)")
        self.assertEqual((deleg(root, t)["state"], int(deleg(root, t)["retries"])), ("BRIEFED", 1))
        self.dispatch(root, t, "dev-billing", "tu-2")
        self.implement(root, t, "dev-billing", "src/billing/discount.py", "RATE = 30\n")
        self.verify_pass(root, t)
        self.review(root, t, "PASS")
        self.accept(root, t)
        self.assertEqual(task(root, t)["attempts"], 2)
        self.close_session(root)
        self.assert_coerente(root)

    def test_review_fail_reject_retry_e_aceite(self):
        root = self.repo()
        self.process(root, "pequena")
        t = self.add_task(root, "dev-billing", "src/billing/discount.py", "criar desconto")
        self.ok(root, "session", "execute")
        self.dispatch(root, t, "dev-billing", "tu-1")
        self.implement(root, t, "dev-billing", "src/billing/discount.py", "RATE = 10\n")
        self.verify_pass(root, t)
        self.review(root, t, "FAIL")
        self.refused(root, "accept", "--task", t)  # FAIL vence
        self.assertIn("cs-state reject --task %s" % t, self.ok(root, "next"))
        self.ok(root, "reject", "--task", t, "--reason", "review FAIL: arredondamento errado")
        self.assertEqual(deleg(root, t)["state"], "REJECTED")
        self.ok(root, "retry", "--task", t, "--findings", "corrigir arredondamento")
        self.dispatch(root, t, "dev-billing", "tu-2")
        self.implement(root, t, "dev-billing", "src/billing/discount.py", "RATE = 30\n")
        self.verify_pass(root, t)
        self.review(root, t, "PASS")
        self.accept(root, t)
        self.close_session(root)
        self.assert_coerente(root)

    def test_review_needs_specialist_roteia_para_outro_gate(self):
        root = self.repo()
        self.process(root, "pequena")
        t = self.add_task(root, "dev-billing", "src/billing/discount.py", "criar desconto")
        self.ok(root, "session", "execute")
        self.dispatch(root, t, "dev-billing", "tu-1")
        self.implement(root, t, "dev-billing", "src/billing/discount.py", "RATE = 30\n")
        self.verify_pass(root, t)
        self.review(root, t, "NEEDS_SPECIALIST", by="reviewer")
        err = self.refused(root, "accept", "--task", t)
        self.assertIn("NEEDS_SPECIALIST", err)
        nxt = self.ok(root, "next")
        self.assertIn("NEEDS_SPECIALIST", nxt)
        self.assertIn("security", nxt, "deve rotear para o OUTRO gate (security): " + nxt)
        self.review(root, t, "PASS", by="security")
        self.accept(root, t)
        self.close_session(root)
        self.assert_coerente(root)


# ------------------------------------------------------------------ 3. escalate/abstain → retomar | trocar | descartar
# [A1] depende da frente em andamento (saídas de ESCALATED/ABSTAINED).
class TestEscaladaSaidas(E2E):
    def _ate_despachada(self):
        root = self.repo()
        self.process(root, "pequena")
        t = self.add_task(root, "dev-billing", "src/billing/discount.py", "criar desconto")
        self.ok(root, "session", "execute")
        self.dispatch(root, t, "dev-billing", "tu-1")
        return root, t

    def _entra(self, root, t, como):
        if como == "escalate":
            out = self.ok(root, "escalate", "--task", t, "--reason", "AC-1 contradiz o épico")
            self.assertEqual((deleg(root, t)["state"], task(root, t)["status"]), ("ESCALATED", "BLOCKED"))
        else:
            out = self.ok(root, "abstain", "--task", t, "--kind", "spec_ambiguous", "--reason", "AC-1 ambíguo",
                          actor="dev-billing")
            self.assertEqual(deleg(root, t)["state"], "ABSTAINED")
        for saida in ("retry --task %s" % t, "reroute --task %s" % t, "drop --task %s" % t):
            self.assertIn(saida, out + self.ok(root, "next"), "as três saídas devem aparecer com comando pronto")
        # nenhuma outra transição destrava: só as três saídas humanas
        self.refused(root, "accept", "--task", t)
        self.refused(root, "retry", "--task", t)  # sem --decision
        return out

    def _retomar(self, root, t):
        self.ok(root, "retry", "--task", t, "--decision", "AC-1 vale como escrito")
        self.assertEqual((deleg(root, t)["state"], task(root, t)["status"]), ("BRIEFED", "READY"))
        self.assertEqual(int(deleg(root, t).get("retries") or 0), 0, "decisão humana não consome tentativa")
        self.full_task(root, t, "dev-billing", "src/billing/discount.py", "RATE = 30\n", "tu-2")
        self.close_session(root)
        self.assert_coerente(root)

    def _trocar(self, root, t):
        self.ok(root, "reroute", "--task", t, "--agent", "dev-members", "--allowed-path", "src/members/discount.py",
                "--decision", "é território de members")
        ds = task(root, t)["delegations"]
        self.assertEqual((ds[-2]["state"], ds[-1]["state"], ds[-1]["agent"]), ("REROUTED", "PLANNED", "dev-members"))
        self.ok(root, "ready", "--task", t)
        self.full_task(root, t, "dev-members", "src/members/discount.py", "ELIGIBLE = True\n", "tu-2")
        self.close_session(root)
        self.assert_coerente(root)

    def _descartar(self, root, t):
        self.refused(root, "drop", "--task", t)  # sem --reason
        self.ok(root, "drop", "--task", t, "--reason", "o humano decidiu não fazer agora")
        self.assertEqual((deleg(root, t)["state"], task(root, t)["status"]), ("DROPPED", "DROPPED"))
        self.close_session(root)
        # a story que ficou só com task descartada também tem saída (volta ao backlog)
        self.ok(root, "story", "requeue", "--id", "US-1", "--reason", "task descartada pelo humano")
        self.assert_coerente(root)

    def test_escalate_retomar(self):
        root, t = self._ate_despachada()
        self._entra(root, t, "escalate")
        self._retomar(root, t)

    def test_escalate_trocar_de_agente(self):
        root, t = self._ate_despachada()
        self._entra(root, t, "escalate")
        self._trocar(root, t)

    def test_escalate_descartar(self):
        root, t = self._ate_despachada()
        self._entra(root, t, "escalate")
        self._descartar(root, t)

    def test_abstain_retomar(self):
        root, t = self._ate_despachada()
        self._entra(root, t, "abstain")
        self._retomar(root, t)

    def test_abstain_trocar_de_agente(self):
        root, t = self._ate_despachada()
        self._entra(root, t, "abstain")
        self._trocar(root, t)

    def test_abstain_descartar(self):
        root, t = self._ate_despachada()
        self._entra(root, t, "abstain")
        self._descartar(root, t)


# ------------------------------------------------------------------ 4. falha de AMBIENTE no verify
# [A2] depende da frente em andamento: `failure_kind: environment`, `reverify`, `waive-verify`.
class TestFalhaDeAmbiente(E2E):
    def _repo_env(self, **kw):
        root = self.repo(**kw)
        self.marker = os.path.join(self.outside_dir(), "env-ok")
        fixture.write(root, "tools/verify_env.sh", VERIFY_ENV_SH % self.marker)
        fixture.write(root, "tests/test_discount.py", TEST_DISCOUNT)
        commit_all(root)
        return root

    def _falha_ambiente(self, klass="pequena"):
        root = self._repo_env()
        self.process(root, klass)
        t = self.add_task(root, "dev-billing", "src/billing/discount.py", "criar desconto", verify=VERIFY_ENV)
        self.ok(root, "session", "execute")
        self.dispatch(root, t, "dev-billing", "tu-1")
        self.implement(root, t, "dev-billing", "src/billing/discount.py", "RATE = 30\n")
        self.verify_fail(root, t)
        self.assertEqual(task(root, t)["gate_report"]["build"]["exit_code"], 127)
        self.assertIn("environment", failure_kinds(root, t), "verify com exit 127 deve gravar failure_kind: environment")
        return root, t

    def _falha_assercao(self):
        root = self._repo_env()
        self.process(root, "pequena")
        t = self.add_task(root, "dev-billing", "src/billing/discount.py", "criar desconto", verify=VERIFY_ASSERT)
        self.ok(root, "session", "execute")
        self.dispatch(root, t, "dev-billing", "tu-1")
        self.implement(root, t, "dev-billing", "src/billing/discount.py", "RATE = 10\n")
        self.verify_fail(root, t)
        self.assertNotIn("environment", failure_kinds(root, t))
        return root, t

    def _waive(self, root, t, by, actor=None):
        return cs(root, "waive-verify", "--task", t, "--by", by, "--reason", "httpx ausente na máquina de CI",
                  "--evidence", "saída do verify: 'fake-dep: command not found' (exit 127); 3/3 ACs verdes localmente",
                  actor=actor)

    def test_ambiente_reverify_apos_consertar_segue_para_review(self):
        root, t = self._falha_ambiente()
        attempts = task(root, t)["attempts"]
        open(self.marker, "w").close()  # "consertar o ambiente" (nada no repo muda)
        out = self.ok(root, "reverify", "--task", t)
        self.assertIn("PASS", out, out)
        self.assertEqual(deleg(root, t)["state"], "VERIFIED")
        self.assertEqual(task(root, t)["attempts"], attempts, "reverify não é novo despacho")
        self.assertIn("review", self.ok(root, "next"), "depois do reverify o próximo passo é a review")
        self.refused(root, "accept", "--task", t)  # pequena: review continua obrigatória
        self.review(root, t, "PASS")
        self.accept(root, t)
        self.close_session(root)
        self.assert_coerente(root)

    def test_waive_verify_por_humano_aceito_so_para_ambiente_e_review_continua(self):
        root, t = self._falha_ambiente()
        code, out, err = self._waive(root, t, HUMAN)
        self.assertEqual(code, 0, "waive-verify por humano em falha de ambiente: exit %d %s%s" % (code, out, err))
        self.assertIn(deleg(root, t)["state"], ("VERIFIED", "REVIEWED"))
        self.refused(root, "accept", "--task", t)  # o waive não substitui a review de gate
        self.review(root, t, "PASS")
        self.accept(root, t)
        self.close_session(root)
        self.assert_coerente(root)
        code, out, err = run_py(VALIDATE, root, "--strict")
        self.assertEqual(code, 0, out + err)
        self.assertTrue(any(HUMAN in json.dumps(d, ensure_ascii=False) for d in walk(task(root, t)) if "waive" in json.dumps(d)),
                        "o waive (quem, motivo, evidência) fica registrado na task")

    def test_waive_verify_trivial_review_passa_a_ser_obrigatoria(self):
        # trivial normalmente aceita sem review; depois de um waive de verify, a review de gate é exigida
        root = self._repo_env(no_rules=True)  # trivial não toca invariante
        self.ok(root, "session", "start", "--request", "ajuste de 1 arquivo")
        self.ok(root, "session", "triage", "--class", "trivial", "--why", "1 arquivo")
        before = {x["id"] for x in board(root)["tasks"]}
        code, out, err = cs(root, "add", "task", "--quick", "--agent", "dev-members", "--title", "ajustar idade",
                            "--allowed-path", "src/members/model.py", "--verify-cmd", VERIFY_ENV)
        self.assertEqual(code, 0, out + err)
        t = [x["id"] for x in board(root)["tasks"] if x["id"] not in before][0]
        if board(root)["sessions"][-1]["state"] == "PLANNING":
            self.ok(root, "session", "execute")
        self.dispatch(root, t, "dev-members", "tu-1")
        self.implement(root, t, "dev-members", "src/members/model.py", "AGE = 21\n")
        self.verify_fail(root, t)
        self.assertIn("environment", failure_kinds(root, t))
        code, out, err = self._waive(root, t, HUMAN)
        self.assertEqual(code, 0, out + err)
        self.refused(root, "accept", "--task", t)
        self.review(root, t, "PASS")
        self.accept(root, t)
        self.close_session(root)
        self.assert_coerente(root)

    def test_waive_verify_recusado_para_ator_nao_humano(self):
        root, t = self._falha_ambiente()
        for by in ("dev-billing", "reviewer", "lead"):
            code, out, err = self._waive(root, t, by)
            self.assertEqual(code, 1, "waive-verify --by %s (não humano) deve ser RECUSADO: exit %d %s%s" % (by, code, out, err))
            self.assertEqual(deleg(root, t)["state"], "REJECTED")
        # subagente não pode nem rodar o comando
        sub = {"agent_id": "ag-x", "agent_type": "dev-billing"}
        code, _, _ = hook(root, "pre-bash", bash_payload(
            root, ".swarm/bin/cs-state waive-verify --task %s --by founder --reason x --evidence y" % t, sub))
        self.assertEqual(code, 2, "subagente rodando waive-verify deve ser bloqueado pelo guard")
        # saída legítima continua existindo: humano decide
        code, out, err = self._waive(root, t, HUMAN)
        self.assertEqual(code, 0, out + err)
        self.review(root, t, "PASS")
        self.accept(root, t)
        self.close_session(root)
        self.assert_coerente(root)

    def test_waive_verify_recusado_para_falha_de_assercao(self):
        root, t = self._falha_assercao()
        code, out, err = self._waive(root, t, HUMAN)
        self.assertEqual(code, 1, "waive-verify em falha de ASSERÇÃO deve ser recusado: exit %d %s%s" % (code, out, err))
        self.assertEqual(deleg(root, t)["state"], "REJECTED")
        # o caminho certo continua aberto: retry com correção
        self.ok(root, "retry", "--task", t, "--findings", "RATE deve ser 30")
        self.full_task(root, t, "dev-billing", "src/billing/discount.py", "RATE = 30\n", "tu-2")
        self.close_session(root)
        self.assert_coerente(root)


# ------------------------------------------------------------------ 5. faixas
class TestFaixasE2E(E2E):
    def test_consulta_so_leitura_do_inicio_ao_fim(self):
        root = self.repo()
        self.ok(root, "session", "start", "--request", "como o total é calculado?")
        self.ok(root, "session", "triage", "--class", "pergunta", "--why", "só leitura")
        out = self.ok(root, "ask", "dev-billing", "como o total do pedido é calculado?", "--paths", "src/billing/**")
        c = [x for x in consults(root) if x.get("state") == "BRIEFED"][0]
        self.assertIn(c["id"], out)
        model = (c.get("route") or {}).get("model") or "sonnet"
        code, _, err = hook(root, "pre-agent", agent_payload(out.strip(), "dev-billing", model=model))
        self.assertEqual(code, 0, err)
        sub = {"agent_id": "ag-c", "agent_type": "dev-billing"}
        self.assertEqual(hook(root, "pre-write", write_payload(root, "src/billing/discount.py", sub))[0], 2)
        self.assertEqual(hook(root, "pre-bash", bash_payload(root, "cat src/billing/total.py", sub))[0], 0)
        code, sout, _ = hook(root, "subagent-stop", dict({"hook_event_name": "SubagentStop"}, **sub))
        self.assertEqual(code, 0)
        self.assertNotIn('"block"', sout)
        b = board(root)
        self.assertEqual([x for x in consults(root) if x["id"] == c["id"]][0]["state"], "ANSWERED")
        self.assertEqual((b["tasks"], b["stories"]), ([], []))
        self.ok(root, "session", "answer")
        self.ok(root, "session", "close")
        self.assertFalse(os.path.exists(os.path.join(root, "src/billing/discount.py")))
        self.assert_coerente(root)

    def test_task_avulsa_trivial_do_inicio_ao_fim(self):
        root = self.repo(no_rules=True)
        self.ok(root, "session", "start", "--request", "renomear constante")
        self.ok(root, "session", "triage", "--class", "trivial", "--why", "1 arquivo")
        out = self.ok(root, "add", "task", "--quick", "--agent", "dev-billing", "--title", "criar desconto",
                      "--allowed-path", "src/billing/discount.py", "--verify-cmd", VERIFY, "--ac", AC)
        t = board(root)["tasks"][-1]["id"]
        self.assertIn(t, out)
        self.assertIn("AVULSA", task(root, t)["story"])
        self.assertEqual((board(root)["epics"], board(root)["features"], board(root)["sprints"]), ([], [], []))
        if board(root)["sessions"][-1]["state"] == "PLANNING":
            self.ok(root, "session", "execute")
        self.full_task(root, t, "dev-billing", "src/billing/discount.py", "RATE = 30\n", "tu-1", review=False)
        self.close_session(root)
        self.assert_coerente(root)


# ------------------------------------------------------------------ 6. retomada de sessão (cs-session save/load)
class TestRetomadaDeSessao(E2E):
    def test_save_no_meio_de_delegacao_em_voo_e_load_em_sessao_nova(self):
        root = self.repo()
        self.process(root, "pequena")
        t = self.add_task(root, "dev-billing", "src/billing/discount.py", "criar desconto")
        self.ok(root, "session", "execute")
        self.dispatch(root, t, "dev-billing", "tu-1")
        d_id = deleg(root, t)["id"]
        code, out, err = run_py(SESSION, root, "save", "--did", "despachou %s para dev-billing" % d_id,
                                "--next", "aguardar o retorno de %s e verificar" % d_id)
        self.assertEqual(code, 0, out + err)
        code, out, err = run_py(SESSION, root, "save", "--check")
        self.assertEqual(code, 0, "save --check logo após o save: " + out + err)

        # "sessão nova": processo novo, só o disco — pelo hook SessionStart e pelo cs-session load
        code, sout, err = hook(root, "session-start", {"hook_event_name": "SessionStart", "source": "startup"})
        self.assertEqual(code, 0, err)
        ctx = json.loads(sout)["hookSpecificOutput"]["additionalContext"]
        code, lout, err = run_py(SESSION, root, "load")
        self.assertEqual(code, 0, err)
        for txt in (ctx, lout):
            self.assertIn("próximo passo", txt)
            self.assertIn(d_id, txt, "o load deve dizer qual delegação está em voo")
            self.assertIn("comando:", txt)
        self.assertIn(t, lout)

        # continua de onde parou e fecha
        self.implement(root, t, "dev-billing", "src/billing/discount.py", "RATE = 30\n")
        self.verify_pass(root, t)
        self.review(root, t)
        self.accept(root, t)
        code, lout2, err = run_py(SESSION, root, "load")
        self.assertEqual(code, 0, err)
        self.assertIn("DELTA", lout2, "estado mudou desde o save: load mostra o delta")
        self.close_session(root)
        self.assert_coerente(root)


# ------------------------------------------------------------------ 7. modo autônomo do início ao fim com escalada
# [A1] a retomada da delegação abstida usa `retry --decision` (frente em andamento).
class TestAutonomoE2E(E2E):
    def stop(self, root):
        code, out, err = hook(root, "stop", {"hook_event_name": "Stop"})
        self.assertEqual(code, 0, err)
        return '"block"' in out

    def test_autonomo_inicio_ao_fim_com_escalada_retomada(self):
        import autonomy
        root = self.repo(no_rules=True)
        self.process(root, "pequena")
        self.ok(root, "autonomy", "start", "--feature", "FEAT-1", "--budget", "tasks=5,attempts=2,minutes=60",
                "--class", "pequena")
        t = self.add_task(root, "dev-billing", "src/billing/discount.py", "criar desconto")
        self.ok(root, "session", "execute")
        self.assertTrue(self.stop(root), "com trabalho pendente o Stop bloqueia (loop continua)")
        self.dispatch(root, t, "dev-billing", "tu-1")
        self.assertTrue(self.stop(root))

        # escalada no meio: o especialista se abstém por ambiguidade material
        self.ok(root, "abstain", "--task", t, "--kind", "spec_ambiguous", "--reason", "desconto sobre subtotal ou total?",
                actor="dev-billing")
        self.assertFalse(self.stop(root), "condição de escalada: o loop para")
        m = autonomy.load(root)
        self.assertEqual((m["state"], m["escalation"]["condition"]), ("ESCALATED", "material_ambiguity"))
        nxt = self.ok(root, "next")
        self.assertIn("autonomy resume --decision", nxt)

        # humano decide: retoma o mandato E a delegação
        self.ok(root, "autonomy", "resume", "--decision", "desconto sobre o subtotal")
        self.ok(root, "retry", "--task", t, "--decision", "desconto sobre o subtotal")
        self.assertEqual(autonomy.load(root)["state"], "ACTIVE")
        self.assertTrue(self.stop(root), "mandato retomado volta a conduzir o loop")
        self.assertEqual(autonomy.load(root)["state"], "ACTIVE", "a mesma evidência não reescala")

        self.full_task(root, t, "dev-billing", "src/billing/discount.py", "RATE = 30\n", "tu-2")
        self.assertFalse(self.stop(root), "sem trabalho pendente o Stop libera")
        self.close_session(root)
        rep = json.loads(json.dumps(j5.loads(self.ok(root, "autonomy", "report"))))
        self.assertEqual(rep["state"], "DONE", rep)
        self.assertEqual(autonomy.load(root)["state"], "DONE")
        self.assertTrue(os.path.isfile(os.path.join(root, hcore.STATE_DIR, "session", "resume.json5")),
                        "checkpoint automático (cs-session save) a cada delegação ACCEPTED")
        self.assert_coerente(root)


if __name__ == "__main__":
    unittest.main()
