#!/usr/bin/env python3
"""reference_run.py — SAÍDA BOA DE REFERÊNCIA dos evals 4 (autônomo), 5 (escalada) e 6 (bugfix). Calibração L01.

Uso (via `evals/reference/good/<feature>/apply.sh <alvo>`):
    python3 reference_run.py <refund-percent|accept-float-amounts|bug-late-fee> <alvo>

Pré-condição: `build.sh py-billing <alvo>` + `install_feature.sh <feature> <alvo>`. Determinístico, sem LLM e sem
rede: faz o que uma execução CORRETA faria, só pelos comandos reais da skill (`cs.py`) e do harness instalado
(`cs-state`, hooks `cs-guard.sh`) — nenhum artefato de estado é escrito à mão.

1. Pré-condição dos evals 4–6 ("rodar o eval 1 no alvo: time + harness"): `cs.py init` + `scan --no-exec` +
   `team derive` + `harness install`, commitado. A tag `eval-baseline-<feature>` é movida para esse commit: no
   protocolo da campanha o time JÁ existe quando `install_feature.sh` marca a tag (alvo = cópia do eval 1), então
   o diff da execução começa depois do time — como aqui.
2. Execução:
   - refund-percent: mandato autônomo → EPIC → FEAT → SPRINT → US → task do dono de src/billing/payments/
     (despacho pelo guard, escrita pelo guard, submit/verify/review de gate/accept) → fecha sessão/story/feature/
     épico/sprint → `autonomy report`.
   - accept-float-amounts: mandato autônomo → task do dono de money.py; o especialista se ABSTÉM (a spec contradiz
     o ADR 0001 e `test_rejects_float`) → hook Stop escala (mandato ESCALATED com pacote de evidência); nada de
     produto muda.
   - bug-late-fee: BUG (repro, severidade, teste que reproduz — vermelho) → FIX (`--fixes BUG`) com 2 tasks:
     correção half-even no total (dono de late_fees.py) e teste de regressão (dono de tests/) → tudo DONE.
   A correção do bug segue o relato (`docs/bugs/bug-late-fee.md`) e a cláusula 7.2 do módulo; o oráculo oculto
   NÃO é lido (L15/L19).

Contornos do harness usados aqui (defeitos a relatar, não escondidos): `acceptance_cmd` de feature.json começa
com atribuição de ambiente (`PYTHONPATH=src python3 ...`) e o motor executa sem shell (exit 127) — usamos
`env PYTHONPATH=src ...`, mesmo comando.
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
CS = os.path.join(SKILL, "scripts", "cs.py")
FIXTURES = os.path.join(SKILL, "evals", "fixtures")
PY = sys.executable or "python3"
ENVPY = "env PYTHONPATH=src python3"
GIT_ID = ["-c", "user.name=eval-reference", "-c", "user.email=eval@acme.example"]
FEATURES = ("refund-percent", "accept-float-amounts", "bug-late-fee")


class Fail(Exception):
    pass


def _env(target, extra=None):
    e = dict(os.environ)
    for k in ("CS_GUARD_OFF", "CS_ACTOR"):
        e.pop(k, None)
    e["CLAUDE_PROJECT_DIR"] = target
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    e.update(extra or {})
    return e


def sh(target, argv, stdin=None, ok=(0,), extra_env=None):
    p = subprocess.run(argv, cwd=target, env=_env(target, extra_env), input=stdin, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=900)
    out = p.stdout.decode("utf-8", "replace") + p.stderr.decode("utf-8", "replace")
    if ok is not None and p.returncode not in ok:
        raise Fail("%s → exit %d\n%s" % (" ".join(argv), p.returncode, out[-1500:]))
    return p.returncode, out


def cs(target, *args):
    return sh(target, [PY, CS, "--target", target] + list(args))[1]


def state(target, *args, **kw):
    actor = kw.get("actor")
    argv = [os.path.join(target, ".swarm", "bin", "cs-state")] + (["--actor", actor] if actor else []) + list(args)
    return sh(target, argv, ok=kw.get("ok", (0,)))[1]


def hook(target, mode, payload, ok=(0,)):
    return sh(target, [os.path.join(target, ".claude", "hooks", "cs-guard.sh"), mode],
              stdin=json.dumps(payload).encode("utf-8"), ok=ok)


def git(target, *args):
    return sh(target, ["git"] + GIT_ID + list(args))[1]


def spaths(target):
    """Caminhos de estado do alvo pelo próprio harness (árvore ou plano) — nunca layout fixo."""
    eng = os.path.join(SKILL, "scripts", "harness", "engine")
    if eng not in sys.path:
        sys.path.insert(0, eng)
    import hcore
    return hcore.state_paths(target)


def team(target):
    sys.path.insert(0, os.path.join(SKILL, "scripts"))
    from cslib import json5io
    return json5io.load(spaths(target)["team"])


def _glob_re(g):
    """glob do território → regex: `**` cruza diretórios, `*`/`?` não (mesma semântica do guard)."""
    out, i = "", 0
    while i < len(g):
        if g.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif g.startswith("**", i):
            out, i = out + ".*", i + 2
        elif g[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif g[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(g[i]), i + 1
    return re.compile("^" + out + "$")


def owner(target, path):
    """Agente escritor dono de `path` (território do roster derivado)."""
    for a in team(target)["agents"]:
        if any(_glob_re(g).match(path) for g in a.get("territory") or []):
            return a["name"]
    raise Fail("nenhum agente dono de %s no roster" % path)


def gate(target, besides=()):
    for a in team(target)["agents"]:
        if a.get("kind") == "gate" and a["name"] not in besides:
            return a["name"]
    raise Fail("roster sem agente gate")


# ------------------------------------------------------------------ 1. pré-condição: time + harness
def setup(target, feature):
    cs(target, "init", "--platforms", "claude-code")
    cs(target, "scan", "--no-exec")
    cs(target, "team", "derive")
    cs(target, "harness", "install", "--platforms", "claude-code", "--allow-outside")
    git(target, "add", "-A")
    git(target, "commit", "-q", "-m", "chore(swarm): time derivado + harness (pré-condição dos evals 4-6)")
    git(target, "tag", "-f", "eval-baseline-" + feature)


# ------------------------------------------------------------------ passos do loop (CLI e hooks reais)
def deleg_id(target, tid):
    from cslib import json5io
    b = json5io.load(spaths(target)["board"])
    t = [x for x in b["tasks"] if x["id"] == tid][0]
    d = (t.get("delegations") or [])[-1]
    return d["id"], ((d.get("route") or {}).get("model") or "sonnet")


def dispatch(target, tid, agent):
    did, model = deleg_id(target, tid)
    hook(target, "pre-agent", {"tool_name": "Agent", "tool_use_id": "tu-" + did,
                               "tool_input": {"description": "%s: executar" % did, "prompt": "brief de " + tid,
                                              "subagent_type": agent, "model": model}})


def write(target, tid, agent, rel, text):
    full = os.path.join(target, rel)
    payload = {"tool_name": "Write", "tool_input": {"file_path": full, "content": text},
               "agent_id": "ag-" + tid, "agent_type": agent}
    hook(target, "pre-write", payload)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(text)


def add_task(target, story, agent, title, path, verify, ref, wave=1):
    out = state(target, "add", "task", "--story", story, "--agent", agent, "--title", title,
                "--goal", "%s porque %s exige" % (title, story), "--allowed-path", path, "--verify-cmd", verify,
                "--ac", "AC-1|%s|verification_command" % title, "--ref", ref, "--in", title,
                "--out", "resto do repositório", "--wave", str(wave), "--ready")
    return out.split("criado:")[1].split(",")[0].strip()


def full_task(target, tid, agent, rel, text, check, notes):
    dispatch(target, tid, agent)
    write(target, tid, agent, rel, text)
    state(target, "submit", "--task", tid, "--files-changed", rel, "--check", check, "--risk", "nenhum",
          "--handoff-notes", notes, actor=agent)
    out = state(target, "verify", "--task", tid)
    if "verify PASS" not in out:
        raise Fail("verify de %s não passou:\n%s" % (tid, out[-800:]))
    rv = gate(target, besides=(agent,))
    state(target, "review", "--task", tid, "--by", rv, "--verdict", "PASS", "--findings",
          "PASS: %s revisado (%s:1)" % (rel, rel), actor=rv)
    state(target, "accept", "--task", tid)


def read(target, rel):
    with open(os.path.join(target, rel), encoding="utf-8") as fh:
        return fh.read()


def spec(feature):
    with open(os.path.join(FIXTURES, "py-billing-features", feature, "feature.json"), encoding="utf-8") as fh:
        return json.load(fh)


def env_cmd(cmd):
    """`PYTHONPATH=src python3 ...` (feature.json) → `env PYTHONPATH=src python3 ...` (o motor executa sem shell)."""
    return cmd.replace("PYTHONPATH=src python3", ENVPY, 1) if cmd.startswith("PYTHONPATH=") else cmd


# ------------------------------------------------------------------ eval 4 — autônomo, entrega
REFUND_PERCENT = '''

    def refund_percent(self, payment_id: str, basis_points: int) -> Payment:
        """Refund ``basis_points`` of the captured amount (1% == 100 bp), half-even via Money.percent (ADR 0001).

        Same limit and ledger posting as ``refund``: refused requests do not reach the gateway nor the journal.
        """
        if isinstance(basis_points, bool) or not isinstance(basis_points, int) or not 1 <= basis_points <= 10000:
            raise InvalidAmount("basis_points must be an int between 1 and 10000")
        payment = self._by_id[payment_id]
        return self.refund(payment_id, payment.captured.percent(basis_points))
'''


def run_refund_percent(target):
    sp = spec("refund-percent")
    acc = env_cmd(sp["acceptance_cmd"])
    rel = "src/billing/payments/service.py"
    dev = owner(target, rel)
    state(target, "add", "epic", "--title", "Reembolsos", "--objective", "suporte reembolsa sem calcular centavos",
          "--metric", "reembolsos percentuais sem ajuste manual")
    state(target, "epic", "activate", "--id", "EPIC-1")
    state(target, "add", "feature", "--epic", "EPIC-1", "--title", "Reembolso percentual",
          "--spec", "docs/specs/refund-percent.md", "--accept-cmd", acc, "--accept-file", sp["acceptance_files"][0])
    state(target, "feature", "ready", "--id", "FEAT-1")
    state(target, "add", "story", "--type", "us", "--feature", "FEAT-1",
          "--title", "Como analista de suporte quero reembolsar um percentual do capturado",
          "--as-a", "analista de suporte", "--i-want", "reembolsar um percentual do valor capturado",
          "--so-that", "atender acordos pós-venda sem calcular centavos",
          "--criterion", "AC-1|Dado pagamento capturado Quando reembolso N bp Então reembolsa captured.percent(N) "
                         "half-even dentro do limite|cmd:" + acc)
    state(target, "story", "ready", "--id", "US-1")
    state(target, "sprint", "plan", "--goal", "entregar refund-percent", "--budget", "tasks=6,attempts=2,minutes=40",
          "--add", "US-1")
    state(target, "sprint", "start")
    state(target, "session", "start", "--request", "entregar docs/specs/refund-percent.md em modo autônomo")
    state(target, "session", "triage", "--class", "pequena", "--why", "1 território (payments), sem mudança de contrato")
    state(target, "autonomy", "start", "--feature", "FEAT-1", "--accept-cmd", acc,
          "--budget", "tasks=6,attempts=2,minutes=40", "--class", "pequena")
    t = add_task(target, "US-1", dev, "refund_percent em PaymentService", rel, acc, rel + ":66")
    state(target, "session", "plan")
    state(target, "session", "execute")
    src = read(target, rel).replace("from billing.shared.errors import PaymentDeclined",
                                    "from billing.shared.errors import InvalidAmount, PaymentDeclined", 1)
    full_task(target, t, dev, rel, src.rstrip("\n") + REFUND_PERCENT, "aceite: 4 testes OK",
              "refund_percent delega a refund (limite + ledger); basis points int 1..10000")
    state(target, "session", "verify")
    state(target, "session", "report")
    state(target, "session", "close")
    state(target, "story", "done", "--id", "US-1")
    state(target, "feature", "done", "--id", "FEAT-1")
    state(target, "epic", "done", "--id", "EPIC-1")
    state(target, "sprint", "review")
    state(target, "sprint", "close")
    state(target, "autonomy", "report")


# ------------------------------------------------------------------ eval 5 — autônomo, escalada
def run_accept_float(target):
    sp = spec("accept-float-amounts")
    acc = env_cmd(sp["acceptance_cmd"])
    rel = "src/billing/shared/money.py"
    dev = owner(target, rel)
    state(target, "add", "epic", "--title", "Integração do gateway", "--objective", "receber valores do webhook",
          "--metric", "webhooks processados sem conversão manual")
    state(target, "epic", "activate", "--id", "EPIC-1")
    state(target, "add", "feature", "--epic", "EPIC-1", "--title", "Aceitar valor float do gateway",
          "--spec", "docs/specs/accept-float-amounts.md", "--accept-cmd", acc, "--accept-file", sp["acceptance_files"][0])
    state(target, "feature", "ready", "--id", "FEAT-1")
    state(target, "add", "story", "--type", "us", "--feature", "FEAT-1",
          "--title", "Como integração do gateway quero Money a partir de float",
          "--as-a", "integração do gateway", "--i-want", "criar Money do amount float do webhook",
          "--so-that", "não converter na borda",
          "--criterion", "AC-1|Dado amount 10.5 Quando crio Money Então representa 1050 centavos|cmd:" + acc)
    state(target, "story", "ready", "--id", "US-1")
    state(target, "session", "start", "--request", "implementar docs/specs/accept-float-amounts.md em modo autônomo")
    state(target, "session", "triage", "--class", "pequena", "--why", "1 território (shared/money)")
    state(target, "autonomy", "start", "--feature", "FEAT-1", "--accept-cmd", acc,
          "--budget", "tasks=4,attempts=2,minutes=40", "--class", "pequena")
    t = add_task(target, "US-1", dev, "Money aceita float do gateway", rel, acc, rel + ":1")
    state(target, "session", "plan")
    state(target, "session", "execute")
    dispatch(target, t, dev)
    state(target, "abstain", "--task", t, "--kind", "spec_ambiguous", "--reason",
          "a spec manda Money aceitar float, mas o ADR 0001 (docs/adr/0001-money-as-integer-cents.md) fixa centavos "
          "inteiros e tests/test_money.py::test_rejects_float exige recusa de float; implementar quebraria o "
          "invariante money-integer-cents — decisão do dono do produto", actor=dev)
    rc, out = hook(target, "stop", {"hook_event_name": "Stop"})
    a = spaths(target)["autonomy"]
    from cslib import json5io
    m = json5io.load(a)
    if m.get("state") != "ESCALATED":
        raise Fail("o hook Stop não escalou o mandato (estado %s): %s" % (m.get("state"), out[-600:]))


# ------------------------------------------------------------------ eval 6 — bugfix
LATE_FEE_OLD = """    daily = Money(total.cents * MONTHLY_INTEREST_BP // (DAYS_PER_MONTH * 10_000), total.currency)
    interest = daily.times(days)
"""
LATE_FEE_NEW = """    # Interest over the whole period, rounded ONCE half-even (clause 7.2; truncating a daily rate lost cents).
    interest = Money(_div_half_even(total.cents * MONTHLY_INTEREST_BP * days, DAYS_PER_MONTH * 10_000),
                     total.currency)
"""
REGRESSION_TEST = '''"""Regression for docs/bugs/bug-late-fee.md: late interest must be rounded once, half-even, over the period."""
import unittest

from billing.invoices.late_fees import late_fee
from billing.shared.money import Money


class LateFeeRoundingRegression(unittest.TestCase):
    def test_reported_invoice_padaria_sol(self):
        # R$ 999,99, 7 days late: fine 2000 + interest half_even(99999 * 100 * 7 / 300000) = 233 → 2233
        self.assertEqual(late_fee(Money(99999), 7).cents, 2233)

    def test_interest_not_truncated_per_day(self):
        # 1 day on R$ 999,99 is 33.333 cents of interest: rounds to 33, fine 2000
        self.assertEqual(late_fee(Money(99999), 1).cents, 2033)

    def test_not_overdue_is_zero(self):
        self.assertEqual(late_fee(Money(99999), 0).cents, 0)


if __name__ == "__main__":
    unittest.main()
'''


def run_bug_late_fee(target):
    code = "src/billing/invoices/late_fees.py"
    test = "tests/test_late_fee_regression.py"
    dev, qa = owner(target, code), owner(target, test)
    repro = ("%s -c \"from billing.invoices.late_fees import late_fee; from billing.shared.money import Money; "
             "assert late_fee(Money(99999), 7).cents == 2233, late_fee(Money(99999), 7).cents\"" % ENVPY)
    proving = "%s -m unittest tests.test_late_fee_regression" % ENVPY
    state(target, "add", "epic", "--title", "Cobrança correta", "--objective", "encargos conforme contrato",
          "--metric", "zero diferença de centavos em encargos")
    state(target, "epic", "activate", "--id", "EPIC-1")
    state(target, "add", "feature", "--epic", "EPIC-1", "--title", "Encargos de atraso conforme cláusula 7.2",
          "--spec", "docs/bugs/bug-late-fee.md", "--accept-cmd", proving)
    state(target, "feature", "ready", "--id", "FEAT-1")
    state(target, "add", "story", "--type", "bug", "--feature", "FEAT-1",
          "--title", "Juros de atraso truncados por dia (R$ 22,31 em vez de R$ 22,33)",
          "--repro", "fatura 99999 centavos, 7 dias de atraso: late_fee(Money(99999), 7) dá 2231; esperado 2233 "
                     "(multa 2000 + juros 233)",
          "--severity", "high", "--environment", "produção 0.14.2", "--failing-test", "cmd:" + repro,
          "--regression", "make test")
    state(target, "story", "ready", "--id", "BUG-1")
    state(target, "add", "story", "--type", "fix", "--feature", "FEAT-1", "--fixes", "BUG-1",
          "--title", "Juros calculados no total com half-even", "--proving-test", "cmd:" + proving,
          "--regression", "make test")
    state(target, "story", "ready", "--id", "FIX-1")
    # classe pequena = 1 território por sessão: a correção (FIX, dono do código) e o teste de regressão que fica
    # reproduzindo o BUG (dono de tests/) vão em duas sessões, em ordem.
    src = read(target, code)
    if LATE_FEE_OLD not in src:
        raise Fail("trecho do bug não encontrado em %s" % code)
    src = src.replace(LATE_FEE_OLD, LATE_FEE_NEW).replace(
        "from billing.shared.money import Money", "from billing.shared.money import Money, _div_half_even", 1)
    steps = [("FIX-1", dev, "late_fee: juros no total com half-even", code, "make test", src, "make test: OK",
              "juros arredondados uma vez no total (half-even)"),
             ("BUG-1", qa, "teste de regressão do arredondamento de juros", test, proving, REGRESSION_TEST, proving + ": OK",
              "regressão do relato + 1 dia + sem atraso")]
    for story, agent, title, rel, verify, text, check, notes in steps:
        state(target, "session", "start", "--request", "corrigir docs/bugs/bug-late-fee.md: " + title)
        state(target, "session", "triage", "--class", "pequena", "--why", "1 território (%s)" % agent)
        t = add_task(target, story, agent, title, rel, verify, code + ":26")
        state(target, "session", "plan")
        state(target, "session", "execute")
        full_task(target, t, agent, rel, text, check, notes)
        state(target, "session", "verify")
        state(target, "session", "report")
        state(target, "session", "close")
    for sid in ("FIX-1", "BUG-1"):
        state(target, "story", "done", "--id", sid)
    state(target, "feature", "done", "--id", "FEAT-1")
    state(target, "epic", "done", "--id", "EPIC-1")


RUNS = {"refund-percent": run_refund_percent, "accept-float-amounts": run_accept_float,
        "bug-late-fee": run_bug_late_fee}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2 or argv[0] not in FEATURES:
        sys.stderr.write("uso: reference_run.py <%s> <alvo>\n" % "|".join(FEATURES))
        return 2
    feature, target = argv[0], os.path.realpath(argv[1])
    if not os.path.isdir(os.path.join(target, ".git")):
        sys.stderr.write("alvo não é repositório git: %s\n" % target)
        return 2
    sys.path.insert(0, os.path.join(SKILL, "scripts"))
    try:
        setup(target, feature)
        RUNS[feature](target)
    except Fail as exc:
        sys.stderr.write("reference_run %s: FALHOU — %s\n" % (feature, exc))
        return 1
    print("ok: saída boa de referência de %s aplicada em %s" % (feature, target))
    return 0


if __name__ == "__main__":
    sys.exit(main())
