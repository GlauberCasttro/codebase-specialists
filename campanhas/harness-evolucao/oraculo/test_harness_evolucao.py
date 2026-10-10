"""ORÁCULO harness-evolucao — os 19 CAs do FEATURE.md (um TestCA<NN> por CA, selecionável por -k CA<NN>).

Contrato (nomes de comando, flags, campos e eventos): ESPEC.md, nesta pasta. Quem implementa NÃO edita este arquivo.
Tudo pelo comportamento OBSERVÁVEL do harness do PRODUTO num alvo de rascunho (tempfile): `cs.py harness install`,
cs-state/cs-mem/guard instalados no alvo (ver _alvo.py), `cs.py upgrade`. Nada de mock do motor, nada de LLM.
Rodar (da raiz do projeto):
  python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA01
"""
import json
import os
import re
import shutil
import tempfile
import unittest

import _alvo as A
from _alvo import Alvo, norm

SUB = {"agent_id": "ag-1", "agent_type": "dev-billing"}
TEAM = [ag["name"] for ag in A.fixture.TEAM["agents"]]
REDACTED_RE = re.compile(r"\[REDACTED:[A-Za-z0-9_.-]+\]")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


def bash_payload(root, cmd, actor=None):
    p = {"tool_name": "Bash", "tool_use_id": "tu-oraculo", "tool_input": {"command": cmd}, "cwd": root}
    p.update(actor or {})
    return p


def tmpfile(obj):
    fd, path = tempfile.mkstemp(prefix="cs-oraculo-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(obj, f)
    return path


# ====================================================================== base
class Base(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.alvos = []

    def tearDown(self):
        for a in self.alvos:
            a.rm()

    def alvo(self, install=True):
        a = Alvo.novo(install=install)
        self.alvos.append(a)
        return a

    # ---- execução
    def ok(self, a, *args, actor=None, msg=""):
        rc, out, err = a.cs(*args, actor=actor)
        self.assertEqual(rc, 0, "%s`cs-state %s` deveria passar (exit %d): %s%s" % (
            msg and msg + ": ", " ".join(args), rc, out, err))
        return out + err

    def no(self, a, *args, actor=None, msg=""):
        rc, out, err = a.cs(*args, actor=actor)
        self.assertNotEqual(rc, 0, "%s`cs-state %s` deveria ser RECUSADO: %s%s" % (
            msg and msg + ": ", " ".join(args), out, err))
        return out + err

    def mem_ok(self, a, *args):
        rc, out, err = a.mem(*args)
        self.assertEqual(rc, 0, "`cs-mem %s` deveria passar (exit %d): %s%s" % (" ".join(args), rc, out, err))
        return out

    def new(self, a, *args):
        out = self.ok(a, "new", *args)
        m = A.CREATED_RE.findall(out)
        self.assertTrue(m, "`cs-state new` deve imprimir `criado <ID> em <caminho>` (veio %r)" % out)
        return m[0][0]

    # ---- árvore
    def epico(self, a, start=True, extra=()):
        eid = self.new(a, "epico", "--title", "Billing completo", "--objetivo", "cobrar certo", *extra)
        if start:
            self.ok(a, "start", eid)
        return eid

    def sprint(self, a, epico=None, start=True, extra=(), meta="entregar desconto"):
        sid = self.new(a, "sprint", "--meta", meta, *((["--epico", epico] if epico else []) + list(extra)))
        if start:
            self.ok(a, "start", sid)
        return sid

    def feature(self, a, sprint, aceite=A.ACEITE, start=True, title="Desconto", extra=()):
        fid = self.new(a, "feature", "--title", title, "--sprint", sprint, "--aceite", aceite, *extra)
        if start:
            self.ok(a, "start", fid)
        return fid

    def task_args(self, parent, agent="dev-billing", paths=("src/billing/discount.py",), tipo="US",
                  title="criar desconto", verify=A.VERIFY, extra=()):
        args = ["task", "--tipo", tipo, "--agent", agent, "--title", title] + list(parent)
        for p in paths:
            args += ["--allowed-path", p]
        args += ["--verify-cmd", verify, "--criterio", A.CRIT]
        if tipo == "US":
            args += ["--como", "cliente", "--quero", "pagar certo", "--para", "nao perder dinheiro"]
        elif tipo == "CHORE":
            args += ["--motivo", "manutencao tecnica sem valor de usuario"]
        return args + list(extra)

    def task(self, a, parent, **kw):
        return self.new(a, *self.task_args(parent, **kw)[0:])

    def avulsa(self, a, rel="src/users/idade.py", title="ajustar idade minima", tipo="US", **kw):
        return self.task(a, ["--avulsa"], agent="dev-users", paths=(rel,), title=title, tipo=tipo, **kw)

    def dispatch(self, a, tid):
        model = ((a.item(tid).get("route") or {}).get("model")) or "sonnet"
        return self.ok(a, "dispatch", tid, "--manual", "--model", model)

    def submit(self, a, tid, rel, agent):
        return self.ok(a, "submit", tid, "--files-changed", rel, "--check", "unittest: OK", "--risk", "nenhum",
                       "--handoff-notes", "ok", actor=agent)

    def run_task(self, a, tid, rel, agent="dev-billing", close=True, start=True):
        """M2 inteira (sem atalho): start → dispatch --manual → submit → verify → review → accept [→ close]."""
        if start:
            self.ok(a, "start", tid)
        self.dispatch(a, tid)
        a.write(rel)
        self.submit(a, tid, rel, agent)
        out = self.ok(a, "verify", tid, msg="verify da task %s" % tid)
        self.assertNotIn("REPROVOU", out, "verify da task %s reprovou (comando verde): %s" % (tid, out))
        self.ok(a, "review", tid, "--by", "reviewer", "--verdict", "PASS", "--findings", "conferido: teste verde")
        self.ok(a, "accept", tid)
        if close:
            self.close_if_open(a, tid)

    def close_if_open(self, a, ident):
        if a.zona(ident) != "archive":
            self.ok(a, "close", ident, "--summary", "entregue")
        self.assertEqual(a.zona(ident), "archive", "%s deveria estar fechado em archive/" % ident)

    def mem_snapshot(self, a):
        return {k: v for k, v in A.snapshot(a.root).items() if k.startswith("memory/") or k.startswith("state/memory/")}


# ====================================================================== CA-01
GH = "gh" + "p_" + "A1b2C3d4" * 4 + "Zz9Y"
GHO = "gh" + "o_" + "Q" * 36
PAT = "github" + "_pat_" + "11" + "B" * 20 + "_" + "c" * 40
AWS = "AK" + "IA" + "QWERTYUIOPASDFGH"
SLACK = "xo" + "xb-" + "1234567890-abcdefghijkl"
JWT = "ey" + "JhbGciOiJIUzI1NiJ9" + "." + "ey" + "JzdWIiOiJhbmEifQ" + "." + "c2lnbmF0dXJhLWZpY3RpY2lhLWRvLW9yYWN1bG8"
PWD_VAL = "S3nh4" + "Fict1c1aOraculo"
BEARER_VAL = "tok" + "Fict" * 8
PEM_BODY = "MIIEvQIBADANBgkqhkiG9w0BAQEFAAS" + "CBKcwggSjAgEAAoIBAQ"
PEM = "-----BEGIN " + "PRIVATE KEY-----\n" + PEM_BODY + "\n-----END " + "PRIVATE KEY-----"


class TestCA01(Base):
    """CA-01 — segredo nunca é gravado (arquivo do agente, memória do projeto, índice, inject/search)."""

    def assert_redigido(self, text, raws, onde):
        self.assertTrue(text and text.strip(), "%s: vazio — nada para conferir" % onde)
        for r in raws:
            self.assertNotIn(r, text, "%s contém o segredo em claro (%s…)" % (onde, r[:6]))
        self.assertRegex(text, REDACTED_RE, "%s deveria conter [REDACTED:<tipo>] no lugar do segredo" % onde)

    @staticmethod
    def contagem(out):
        try:
            v = json.loads(out.strip().splitlines()[-1]).get("redacted")
        except (ValueError, IndexError, AttributeError):
            return None
        return v if isinstance(v, int) else None

    def test_add_licao_redige_arquivo_inject_search_e_indice(self):
        a = self.alvo()
        rule = "nunca commitar %s nem %s no repo" % (GH, AWS)
        why = "vazou %s e password=%s" % (JWT, PWD_VAL)
        out = self.mem_ok(a, "add", "--agent", "dev-billing", "--rule", rule, "--why", why, "--paths", "src/billing/**")
        raws = [GH, AWS, JWT, PWD_VAL]
        self.assertEqual(self.contagem(out), 4, "a saída deve informar quantos trechos redigiu (redacted: 4): %r" % out)
        f = a.agent_mem_file("dev-billing")
        self.assertTrue(f, "lição do agente não gravada")
        self.assert_redigido(A.read_text(f), raws, "arquivo de memória do dev-billing")
        inj = self.mem_ok(a, "inject", "--agent", "dev-billing", "--paths", "src/billing/total.py")
        self.assert_redigido(inj, raws, "saída do inject")
        srch = self.mem_ok(a, "search", "commitar repo", "--agent", "dev-billing")
        self.assert_redigido(srch, raws, "saída do search")
        idx = A.all_files_text(a.p("memory", "index"))
        for r in raws:
            self.assertNotIn(r, idx, "índice de busca contém segredo em claro")

    def test_add_conhecimento_redige_memoria_do_projeto(self):
        a = self.alvo()
        text = "token do bot %s; header Authorization: Bearer %s; chave %s" % (SLACK, BEARER_VAL, PEM)
        out = self.mem_ok(a, "add", "--kind", "decision", "--text", text, "--founder", "Ana")
        raws = [SLACK, BEARER_VAL, PEM_BODY]
        self.assertEqual(self.contagem(out), 3, "a saída deve informar quantos trechos redigiu (redacted: 3): %r" % out)
        self.assert_redigido(A.read_text(a.p("memory", "knowledge.jsonl")), raws, "knowledge.jsonl")
        srch = self.mem_ok(a, "search", "token bot header chave")
        self.assert_redigido(srch, raws, "saída do search")
        idx = A.all_files_text(a.p("memory", "index"))
        for r in raws:
            self.assertNotIn(r, idx, "índice de busca contém segredo em claro")

    def test_correct_redige(self):
        a = self.alvo()
        out = self.mem_ok(a, "correct", "--scope", "agent", "--agent", "dev-billing", "--wrong", "colou %s no log" % GHO,
                          "--right", "ler o token do cofre", "--why", "o PAT %s vazou" % PAT, "--paths", "src/billing/**")
        self.assertEqual(self.contagem(out), 2, "a saída deve informar quantos trechos redigiu (redacted: 2): %r" % out)
        self.assert_redigido(A.read_text(a.agent_mem_file("dev-billing") or os.devnull), [GHO, PAT],
                             "arquivo de memória do dev-billing")

    def test_calibracao_redacao(self):
        with self.assertRaises(AssertionError):
            self.assert_redigido("", [GH], "vazio")
        with self.assertRaises(AssertionError):
            self.assert_redigido("regra com %s" % GH, [GH], "em claro")
        self.assert_redigido("regra com [REDACTED:github-token] no lugar", [GH], "bom conhecido")
        self.assertIsNone(self.contagem(""))
        self.assertEqual(self.contagem('{"ok": true, "redacted": 4}'), 4)


# ====================================================================== CA-02
class TestCA02(Base):
    """CA-02 — um agente não escreve na memória de outro (guard exit 2; cs-mem exit 1, nada gravado)."""

    def test_guard_recusa_agent_repetido(self):
        a = self.alvo()
        for cmd in ("cs-mem add --agent dev-billing --agent dev-users --rule x --why y",
                    "cs-mem add --agent dev-billing --agent=dev-users --rule x --why y",
                    "cs-mem correct --agent dev-billing --agent dev-users --wrong a --right b --why c"):
            rc, out, err = a.hook("pre-bash", bash_payload(a.root, cmd, SUB))
            self.assertEqual(rc, 2, "guard deveria recusar (exit 2) `%s` do subagente dev-billing: %s%s" % (cmd, out, err))

    def test_guard_mantem_fora_do_time_recusado_e_proprio_aceito(self):
        a = self.alvo()
        rc, out, err = a.hook("pre-bash", bash_payload(a.root, "cs-mem add --agent fantasma --rule x --why y", SUB))
        self.assertEqual(rc, 2, out + err)
        rc, out, err = a.hook("pre-bash", bash_payload(a.root, "cs-mem add --agent dev-billing --rule x --why y", SUB))
        self.assertEqual(rc, 0, "a própria memória continua permitida: %s%s" % (out, err))

    def test_cli_recusa_agent_repetido_sem_gravar(self):
        a = self.alvo()
        for args in (["--agent", "dev-billing", "--agent", "dev-users"], ["--agent", "dev-billing", "--agent=dev-users"]):
            before = self.mem_snapshot(a)
            rc, out, err = a.mem("add", *(args + ["--rule", "regra intrusa", "--why", "teste"]))
            self.assertEqual(rc, 1, "cs-mem deveria recusar --agent repetido com exit 1 (veio %d): %s%s" % (rc, out, err))
            self.assertEqual(self.mem_snapshot(a), before, "nada pode ser gravado na memória")

    def test_cli_recusa_agente_fora_do_team(self):
        a = self.alvo()
        before = self.mem_snapshot(a)
        rc, out, err = a.mem("add", "--agent", "fantasma", "--rule", "regra", "--why", "teste")
        self.assertEqual(rc, 1, "agente fora do team.json5 deve ser recusado (exit 1, veio %d): %s%s" % (rc, out, err))
        rc, out, err = a.mem("correct", "--scope", "agent", "--agent", "fantasma", "--wrong", "a", "--right", "b",
                             "--why", "c")
        self.assertEqual(rc, 1, "correct para agente fora do team.json5: exit 1 (veio %d): %s%s" % (rc, out, err))
        self.assertEqual(self.mem_snapshot(a), before, "nada pode ser gravado na memória")
        self.assertIsNone(a.agent_mem_file("fantasma"))

    def test_cli_aceita_lead(self):
        a = self.alvo()
        rc, out, err = a.mem("add", "--agent", "lead", "--rule", "registrar decisao no ledger", "--why", "rastreio")
        self.assertEqual(rc, 0, "lead é aceito: %s%s" % (out, err))

    def test_calibracao_snapshot_de_memoria(self):
        a = self.alvo()
        s0 = self.mem_snapshot(a)
        self.assertEqual(self.mem_snapshot(a), s0, "sem escrita o snapshot não muda")
        self.mem_ok(a, "add", "--agent", "dev-billing", "--rule", "somar em centavos", "--why", "regra")
        self.assertNotEqual(self.mem_snapshot(a), s0, "uma escrita legítima muda o snapshot")


# ====================================================================== CA-03
class TestCA03(Base):
    """CA-03 — o install cria e repara as memórias (projeto + cada agente), com memory_init no ledger."""

    @staticmethod
    def jsonl_valido_vazio(path):
        if not os.path.isfile(path):
            return False
        try:
            return A.read_jsonl(path) == []
        except ValueError:
            return False

    def agent_files(self, a):
        return {ag: a.agent_mem_file(ag) for ag in TEAM}

    def test_install_cria_memoria_do_projeto_e_dos_agentes(self):
        a = self.alvo()
        for f in ("knowledge.jsonl", "episodes.jsonl"):
            self.assertTrue(self.jsonl_valido_vazio(a.p("memory", f)), "memória do projeto: %s vazio e válido" % f)
        for ag, f in self.agent_files(a).items():
            self.assertTrue(f, "memória do agente %s não foi criada pelo install" % ag)
            d = A.read_doc(f)
            self.assertIsInstance(d, dict, f)
            self.assertEqual(d.get("lessons"), [], "%s: memória nova vazia e válida (lessons: [])" % f)
        evs = a.find_events("memory_init")
        self.assertTrue(evs, "o ledger deve registrar memory_init")
        for k in ("created", "repaired", "kept"):
            self.assertIn(k, evs[-1], "memory_init sem `%s`" % k)
        self.assertTrue(evs[-1]["created"], "primeira execução cria")

    def test_reinstalar_recria_so_o_que_falta(self):
        a = self.alvo()
        files = self.agent_files(a)
        self.assertTrue(all(files.values()), "pré-condição: install cria a memória de cada agente: %s" % files)
        os.remove(files["dev-users"])
        shas = {ag: A.sha_file(f) for ag, f in files.items() if ag != "dev-users"}
        k_sha = A.sha_file(a.p("memory", "knowledge.jsonl"))
        rc, out, err = a.install()
        self.assertEqual(rc, 0, out + err)
        self.assertTrue(a.agent_mem_file("dev-users"), "a segunda execução recria o arquivo apagado")
        for ag, s in shas.items():
            self.assertEqual(A.sha_file(a.agent_mem_file(ag)), s, "%s não pode mudar de sha" % ag)
        self.assertEqual(A.sha_file(a.p("memory", "knowledge.jsonl")), k_sha)
        ev = a.find_events("memory_init")[-1]
        refeito = json.dumps([ev.get("created"), ev.get("repaired")])
        self.assertIn("dev-users", refeito, "memory_init deve listar o recriado: %r" % ev)
        self.assertNotIn("dev-billing", refeito, "memory_init: só o que faltava é recriado: %r" % ev)
        self.assertIn("dev-billing", json.dumps(ev.get("kept")), "memory_init.kept lista o preservado: %r" % ev)

    def test_memoria_ilegivel_recusa_com_backup(self):
        a = self.alvo()
        f = a.agent_mem_file("dev-billing") or a.p("state", "memory", "agents", "dev-billing.json")
        os.makedirs(os.path.dirname(f), exist_ok=True)
        lixo = b"{ isto nao e json nem json5 ::"
        with open(f, "wb") as fh:
            fh.write(lixo)
        rc, out, err = a.install()
        self.assertNotEqual(rc, 0, "memória ilegível: o install recusa (veio exit 0): %s%s" % (out, err))
        with open(f, "rb") as fh:
            self.assertEqual(fh.read(), lixo, "arquivo ilegível nunca é sobrescrito")
        bk = a.p("backups", "memory")
        achou = False
        for dp, _, fs in os.walk(bk):
            for n in fs:
                with open(os.path.join(dp, n), "rb") as fh:
                    achou = achou or fh.read() == lixo
        self.assertTrue(achou, "backup do arquivo ilegível em .swarm/backups/memory/")

    def test_calibracao_jsonl(self):
        d = tempfile.mkdtemp(prefix="cs-oraculo-")
        try:
            self.assertFalse(self.jsonl_valido_vazio(os.path.join(d, "nao-existe.jsonl")))
            p = os.path.join(d, "x.jsonl")
            open(p, "w").close()
            self.assertTrue(self.jsonl_valido_vazio(p))
            with open(p, "w") as fh:
                fh.write("{nao json\n")
            self.assertFalse(self.jsonl_valido_vazio(p))
        finally:
            shutil.rmtree(d, ignore_errors=True)


# ====================================================================== CA-04
CAMPOS_CORRECT = ("id", "scope", "agent", "project", "taskId", "originalRequest", "incorrectBehavior", "correction",
                  "expectedBehavior", "createdAt", "source", "status", "confidence", "applicationCount")


class TestCA04(Base):
    """CA-04 — correct com --scope agent|project|execution --task, registro completo e evento lesson.recorded."""

    def faltando(self, rec, tid, scope, title):
        if not isinstance(rec, dict):
            return list(CAMPOS_CORRECT)
        miss = [k for k in CAMPOS_CORRECT if rec.get(k) in (None, "")]
        if rec.get("scope") != scope:
            miss.append("scope=%s" % scope)
        if rec.get("taskId") != tid:
            miss.append("taskId=%s" % tid)
        if title not in str(rec.get("originalRequest") or ""):
            miss.append("originalRequest copiado da task")
        if rec.get("source") != "correct":
            miss.append("source=correct")
        if rec.get("status") != "active":
            miss.append("status=active")
        if not ISO_RE.match(str(rec.get("createdAt") or "")):
            miss.append("createdAt ISO-8601")
        if not isinstance(rec.get("applicationCount"), int):
            miss.append("applicationCount int")
        return miss

    def registro(self, docs, tid):
        for d in docs:
            for x in A.walk_dicts(d):
                if x.get("taskId") == tid:
                    return x
        return None

    def prep(self):
        a = self.alvo()
        title = "ajustar idade minima"
        return a, self.avulsa(a, title=title), title

    def correct(self, a, scope, tid, marca):
        args = ["correct", "--scope", scope, "--agent", "dev-users", "--wrong", "usou 21 anos %s" % marca,
                "--right", "usar a constante AGE %s" % marca, "--why", "regra de negocio %s" % marca,
                "--paths", "src/users/**"]
        if tid:
            args += ["--task", tid]
        return a.mem(*args)

    def test_scope_agent(self):
        a, tid, title = self.prep()
        rc, out, err = self.correct(a, "agent", tid, "zebraagente")
        self.assertEqual(rc, 0, out + err)
        rec = self.registro([{"l": a.lessons("dev-users")}], tid)
        self.assertEqual(self.faltando(rec, tid, "agent", title), [], "registro na memória do agente: %r" % rec)
        self.assertIn("zebraagente", str(rec.get("incorrectBehavior")))
        self.assertTrue(a.find_events("lesson.recorded"), "o motor grava lesson.recorded no ledger")

    def test_scope_project(self):
        a, tid, title = self.prep()
        rc, out, err = self.correct(a, "project", tid, "zebraprojeto")
        self.assertEqual(rc, 0, out + err)
        rows = [r for r in a.knowledge() if "zebraprojeto" in json.dumps(r, ensure_ascii=False)]
        self.assertTrue(rows, "scope project grava na memória do projeto (knowledge.jsonl)")
        self.assertIn(rows[-1].get("kind"), ("rule", "decision"))
        rec = self.registro(rows, tid)
        self.assertEqual(self.faltando(rec, tid, "project", title), [], "registro na memória do projeto: %r" % rec)
        self.assertNotIn("zebraprojeto", json.dumps(a.lessons("dev-users"), ensure_ascii=False),
                         "scope project não vai para a memória do agente")
        self.assertTrue(a.find_events("lesson.recorded"))

    def test_scope_execution_so_no_historico_da_task(self):
        a, tid, title = self.prep()
        rc, out, err = self.correct(a, "execution", tid, "zebraexecucao")
        self.assertEqual(rc, 0, out + err)
        self.assertIn("zebraexecucao", A.read_text(a.item_path(tid)), "scope execution grava no histórico da task")
        self.mem_ok(a, "search", "zebraexecucao constante idade")
        kn = a.p("memory", "knowledge.jsonl")
        for onde, txt in (("knowledge.jsonl", A.read_text(kn) if os.path.isfile(kn) else ""),
                          ("memória dos agentes",
                           A.all_files_text(a.p("state", "memory")) + A.all_files_text(a.p("memory", "agents"))),
                          ("índice", A.all_files_text(a.p("memory", "index")))):
            self.assertNotIn("zebraexecucao", txt, "scope execution nunca vai para %s" % onde)
        evs = a.find_events("lesson.recorded")
        self.assertTrue(evs, "o motor grava lesson.recorded no ledger")
        rec = self.registro([a.item(tid)] + evs, tid)
        self.assertEqual(self.faltando(rec, tid, "execution", title), [], "registro da execução: %r" % rec)

    def test_execution_sem_task_recusa(self):
        a, tid, title = self.prep()
        before = self.mem_snapshot(a)
        rc, out, err = self.correct(a, "execution", None, "zebrasemtask")
        self.assertNotEqual(rc, 0, "--scope execution sem --task é recusado")
        self.assertIn("--task", out + err, "a recusa explica que --scope execution exige --task: %s%s" % (out, err))
        self.assertEqual(self.mem_snapshot(a), before)
        self.assertNotIn("zebrasemtask", A.read_text(a.item_path(tid)))

    def test_calibracao_registro(self):
        self.assertTrue(self.faltando({}, "T", "agent", "titulo"))
        self.assertTrue(self.faltando(None, "T", "agent", "titulo"))
        bom = {"id": "L-1", "scope": "agent", "agent": "dev-users", "project": "demo", "taskId": "T",
               "originalRequest": "titulo da task", "incorrectBehavior": "w", "correction": "r",
               "expectedBehavior": "e", "createdAt": "2026-10-09T10:00:00Z", "source": "correct", "status": "active",
               "confidence": 0.8, "applicationCount": 0}
        self.assertEqual(self.faltando(bom, "T", "agent", "titulo"), [])


# ====================================================================== CA-05
class TestCA05(Base):
    """CA-05 — correção contraditória substitui (supersedes); lição promovida e não aplicada continua no inject/search."""

    @staticmethod
    def ids(out):
        try:
            d = json.loads(out)
        except ValueError:
            return []
        return [x.get("id") for x in A.walk_dicts(d) if isinstance(x.get("id"), str)]

    def test_contraditoria_substitui_sem_promover(self):
        a = self.alvo()
        base = ["correct", "--scope", "agent", "--agent", "dev-billing", "--paths", "src/billing/**"]
        rc, out, err = a.mem(*(base + ["--wrong", "arredondar antes de somar", "--right",
                                         "somar em centavos e arredondar no fim", "--why", "regra do projeto"]))
        self.assertEqual(rc, 0, out + err)
        rc, out, err = a.mem(*(base + ["--wrong", "somar em centavos e arredondar no fim", "--right",
                                         "arredondar antes de somar", "--why", "a regra mudou"]))
        self.assertEqual(rc, 0, out + err)
        ls = a.lessons("dev-billing")
        self.assertEqual(len(ls), 2, "a contraditória nasce como lição NOVA: %r" % ls)
        old, new = ls[0], ls[1]
        if new.get("supersedes") != old.get("id"):
            old, new = new, old
        self.assertEqual(new.get("supersedes"), old.get("id"), "a nova aponta `supersedes` para a antiga: %r" % ls)
        self.assertEqual(old.get("status"), "superseded", "a antiga vira superseded: %r" % old)
        self.assertTrue(old.get("superseded_by") == new.get("id") or old.get("historico") or old.get("history"),
                        "a antiga guarda histórico da substituição: %r" % old)
        self.assertFalse([l for l in ls if l.get("status") == "promoted"], "nada é promovido: %r" % ls)
        inj = self.mem_ok(a, "inject", "--agent", "dev-billing", "--paths", "src/billing/total.py", "--json")
        got = self.ids(inj)
        self.assertIn(new["id"], got)
        self.assertNotIn(old["id"], got, "superseded fica fora do inject")

    def test_promovida_nao_aplicada_continua_no_inject_e_search(self):
        a = self.alvo()
        t1 = self.avulsa(a, rel="src/users/a.py", title="primeira")
        t2 = self.avulsa(a, rel="src/users/b.py", title="segunda")
        for t in (t1, t2):
            self.mem_ok(a, "add", "--agent", "dev-billing", "--rule", "validar centavos inteiros antes de somar",
                        "--why", "bug recorrente no total", "--paths", "src/billing/**", "--task", t)
        ls = a.lessons("dev-billing")
        self.assertEqual(len(ls), 1, ls)
        self.assertGreaterEqual(int(ls[0].get("count") or 0), 2, ls)
        lid = ls[0]["id"]
        inj = self.mem_ok(a, "inject", "--agent", "dev-billing", "--paths", "src/billing/total.py", "--json")
        self.assertIn(lid, self.ids(inj), "lição com count >= 2 ainda não aplicada ao cartão continua no inject")
        srch = self.mem_ok(a, "search", "centavos inteiros somar", "--agent", "dev-billing", "--json")
        self.assertIn(lid, srch, "e no search")

    def test_calibracao_ids(self):
        self.assertEqual(self.ids(""), [])
        self.assertEqual(self.ids('{"lessons": [{"id": "L-x"}]}'), ["L-x"])


# ====================================================================== CA-06
class TestCA06(Base):
    """CA-06 — memory_injected no ledger, submissão sem lessons_checked recusada, applicationCount incrementa."""

    @staticmethod
    def evento_ok(ev, lid):
        return (isinstance(ev, dict) and all(k in ev for k in ("task", "agent", "lesson_ids", "hit_ids", "omitted"))
                and lid in (ev.get("lesson_ids") or []))

    def prep(self):
        a = self.alvo()
        out = self.mem_ok(a, "add", "--agent", "dev-users", "--rule", "validar idade com a constante AGE",
                          "--why", "regra de negocio", "--paths", "src/users/**")
        lid = json.loads(out.strip().splitlines()[-1])["id"]
        tid = self.avulsa(a, rel="src/users/idade.py")
        self.ok(a, "start", tid)
        self.dispatch(a, tid)
        a.hook("subagent-start", {"agent_type": "dev-users", "agent_id": "ag-users", "hook_event_name": "SubagentStart"})
        a.cs("brief", tid)
        return a, tid, lid

    def test_injecao_registrada(self):
        a, tid, lid = self.prep()
        evs = [e for e in a.find_events("memory_injected") if self.evento_ok(e, lid)]
        self.assertTrue(evs, "ledger deve ter memory_injected {task, agent, lesson_ids, hit_ids, omitted} com %s" % lid)
        self.assertEqual(evs[-1].get("agent"), "dev-users")

    def test_submissao_sem_lessons_checked_recusada_e_contagem(self):
        a, tid, lid = self.prep()
        rel = "src/users/idade.py"
        a.write(rel)
        rc, out, err = a.cs("submit", tid, "--files-changed", rel, "--check", "unittest: OK", "--handoff-notes", "ok",
                            actor="dev-users")
        self.assertNotEqual(rc, 0, "submissão sem lessons_checked (brief injetou lições) deve ser recusada")
        f = tmpfile({"files_changed": [rel], "checks_run": ["unittest: OK"], "risks": [], "handoff_notes": "ok",
                     "lessons_checked": [lid]})
        try:
            self.ok(a, "submit", tid, "--from", f, actor="dev-users")
        finally:
            os.remove(f)
        l = [x for x in a.lessons("dev-users") if x.get("id") == lid]
        self.assertTrue(l)
        self.assertEqual(l[0].get("applicationCount"), 1, "lição checada incrementa applicationCount: %r" % l[0])

    def test_calibracao_evento(self):
        self.assertFalse(self.evento_ok({}, "L-1"))
        self.assertTrue(self.evento_ok({"task": "T", "agent": "a", "lesson_ids": ["L-1"], "hit_ids": [],
                                        "omitted": []}, "L-1"))


# ====================================================================== CA-07
S_EPICO = ["--territorio", "src/billing/**", "--territorio", "src/users/**", "--territorio", "docs/stories/**",
           "--entregas", "5", "--dependencias", "3", "--paralelizavel", "--duracao-estimada", "3",
           "--features-estimadas", "4", "--tasks-estimadas", "14", "--invariante", "rule.billing.cents"]
S_FEATURE = ["--territorio", "src/billing/**", "--entregas", "1", "--dependencias", "1", "--duracao-estimada", "1",
             "--features-estimadas", "1", "--tasks-estimadas", "4"]
S_AVULSA = ["--territorio", "src/users/**", "--entregas", "1", "--dependencias", "0", "--duracao-estimada", "1",
            "--features-estimadas", "0", "--tasks-estimadas", "1"]


class TestCA07(Base):
    """CA-07 — cs-state classify (script) propõe avulsa|feature|epico com justificativa e sinais em evento."""

    @staticmethod
    def classe_ok(d, classe):
        return (isinstance(d, dict) and d.get("classe") == classe and isinstance(d.get("why"), str)
                and d["why"].strip() != "" and isinstance(d.get("sinais"), dict) and bool(d["sinais"]))

    def classify(self, a, sinais):
        out = self.ok(a, "classify", "--json", *sinais)
        try:
            return json.loads(out[out.index("{"):out.rindex("}") + 1])
        except ValueError:
            self.fail("classify --json deve imprimir um objeto JSON: %r" % out)

    def test_classify_propoe_estrutura_e_grava_evento(self):
        a = self.alvo()
        for sinais, classe in ((S_EPICO, "epico"), (S_FEATURE, "feature"), (S_AVULSA, "avulsa")):
            n = len(a.find_events("classify"))
            d = self.classify(a, sinais)
            self.assertTrue(self.classe_ok(d, classe), "esperado %s com why e sinais: %r" % (classe, d))
            evs = a.find_events("classify")
            self.assertEqual(len(evs), n + 1, "classify grava UM evento")
            self.assertTrue(self.classe_ok(evs[-1], classe), "evento com classe, why e sinais: %r" % evs[-1])

    def test_triage_aceita_epico(self):
        a = self.alvo()
        self.ok(a, "session", "start", "--request", "billing completo com tres dominios")
        self.ok(a, "session", "triage", "--class", "epico", "--why", "3 territorios e 5 entregas")

    def test_epico_guarda_classificacao(self):
        a = self.alvo()
        self.classify(a, S_EPICO)
        eid = self.epico(a, start=False)
        c = a.item(eid).get("classificacao")
        self.assertTrue(self.classe_ok(c, "epico"), "épico criado a partir do classify guarda classificacao: %r" % c)

    def test_calibracao_classe(self):
        self.assertFalse(self.classe_ok({}, "epico"))
        self.assertFalse(self.classe_ok({"classe": "epico", "why": "", "sinais": {"x": 1}}, "epico"))
        self.assertTrue(self.classe_ok({"classe": "epico", "why": "3 dominios", "sinais": {"entregas": 5}}, "epico"))


# ====================================================================== CA-08
PROIBIDOS = [re.compile(r"\badd\s+(epic|feature|story)\b"), re.compile(r"\bsprint\s+plan\b"),
             re.compile(r"\badd\s+task\b[^\n]*--quick")]
TEMPLATES = ("assets/templates/orchestrator.md", "assets/templates/product-process.md",
             "assets/templates/plan-sprint.md")


class TestCA08(Base):
    """CA-08 — um caminho só (a árvore): textos emitidos e `next` sem board legado; comandos legados recusam."""

    @staticmethod
    def proibidos(text, permitir_legado=False):
        hits = []
        for ln in text.splitlines():
            if permitir_legado and re.search(r"legad|legacy|board plano", norm(ln)):
                continue
            if any(p.search(ln) for p in PROIBIDOS):
                hits.append(ln.strip())
        return hits

    def ler(self, rel):
        p = os.path.join(A.SKILL, rel)
        self.assertTrue(os.path.isfile(p), "texto emitido ausente: %s" % rel)
        t = A.read_text(p)
        self.assertTrue(t.strip(), "texto emitido vazio: %s" % rel)
        return t

    def test_textos_emitidos_nao_mandam_ao_board_legado(self):
        for rel in TEMPLATES:
            self.assertEqual(self.proibidos(self.ler(rel)), [], "%s manda usar o board legado" % rel)
        self.assertEqual(self.proibidos(self.ler("references/harness.md"), permitir_legado=True), [],
                         "references/harness.md manda usar o board legado (fora de linha marcada como legado)")

    def test_next_nao_manda_ao_board_legado(self):
        a = self.alvo()
        out = self.ok(a, "next")
        self.assertEqual(self.proibidos(out), [], "`next` (árvore vazia) manda usar o board legado: %s" % out)
        self.epico(a)
        out = self.ok(a, "next")
        self.assertEqual(self.proibidos(out), [], "`next` (épico ativo) manda usar o board legado: %s" % out)

    def test_comandos_legados_recusam_em_modo_arvore(self):
        a = self.alvo()
        casos = ((("add", "epic", "--title", "Billing", "--objective", "cobrar"), "new epico"),
                 (("add", "feature", "--epic", "EPIC-1", "--title", "Desconto", "--accept-cmd", A.VERDE), "new feature"),
                 (("add", "story", "--type", "us", "--title", "Como cliente quero desconto"), "new story"),
                 (("sprint", "plan", "--goal", "entregar desconto"), "new sprint"),
                 (("add", "task", "--quick", "--agent", "dev-users", "--title", "ajuste", "--allowed-path",
                   "src/users/x.py", "--verify-cmd", A.VERDE), "new task"))
        for args, dica in casos:
            ev0, snap0 = a.events_bytes(), A.snapshot(a.root)
            rc, out, err = a.cs(*args)
            self.assertNotEqual(rc, 0, "`cs-state %s` em modo árvore deve recusar: %s%s" % (" ".join(args), out, err))
            self.assertIn(dica, out + err, "a recusa ensina o comando da árvore (%s): %s%s" % (dica, out, err))
            self.assertEqual(a.events_bytes(), ev0, "nenhum evento (item invisível) criado por %s" % " ".join(args))
            self.assertEqual(A.snapshot(a.root), snap0)

    def test_calibracao_proibidos(self):
        self.assertTrue(self.proibidos("use `.swarm/bin/cs-state add epic --title x`"))
        self.assertTrue(self.proibidos("cs-state add task --quick --agent a"))
        self.assertEqual(self.proibidos("cs-state new epico --title x; cs-state new task --avulsa"), [])
        self.assertEqual(self.proibidos("(legado) cs-state add epic", permitir_legado=True), [])
        with self.assertRaises(AssertionError):
            self.ler("assets/templates/nao-existe-oraculo.md")


# ====================================================================== CA-09
class TestCA09(Base):
    """CA-09 — task avulsa só pequena e completa; válida fecha e arquiva sozinha sem épico/sprint/feature."""

    @staticmethod
    def pede_estrutura(text):
        return "suba para estruturado" in norm(text)

    def test_avulsa_em_invariante_escopada_recusa(self):
        a = self.alvo()
        out = self.no(a, *self.task_args(["--avulsa"], agent="dev-billing", paths=("src/billing/discount.py",)))
        self.assertTrue(self.pede_estrutura(out), "recusa com 'suba para estruturado': %s" % out)
        self.assertFalse([n for n in a.nodes().values() if n["kind"] == "task"], "nada criado")

    def test_avulsa_em_mais_de_um_territorio_recusa(self):
        a = self.alvo()
        out = self.no(a, *self.task_args(["--avulsa"], agent="dev-users",
                                          paths=("src/users/a.py", "docs/stories/a.md")))
        self.assertTrue(self.pede_estrutura(out), "recusa com 'suba para estruturado': %s" % out)

    def test_avulsa_valida_fecha_e_arquiva_individualmente(self):
        a = self.alvo()
        tid = self.avulsa(a, rel="src/users/limpeza.py", title="limpar constante", tipo="CHORE", verify=A.VERDE)
        it = a.item(tid)
        self.assertTrue(it.get("status"), "a avulsa tem status persistido: %r" % it)
        self.assertGreaterEqual(len(it.get("criterios") or []), 1, "a avulsa (inclusive CHORE) tem >= 1 critério")
        self.run_task(a, tid, "src/users/limpeza.py", agent="dev-users", close=True)
        self.assertEqual(a.zona(tid), "archive", "a avulsa fecha e arquiva individualmente pelo close")
        it = a.item(tid)
        self.assertTrue(it.get("historico"), "histórico da avulsa")
        self.assertIn("tentativas", (it.get("closed") or {}).get("metricas") or {}, "histórico com tentativas")
        self.assertFalse([n for n in a.nodes().values() if n["kind"] in ("epico", "sprint", "feature")],
                         "a avulsa não cria épico, sprint nem feature")

    def test_calibracao_mensagem(self):
        self.assertFalse(self.pede_estrutura(""))
        self.assertTrue(self.pede_estrutura("RECUSADO: toca invariante escopada — suba para estruturado"))


# ====================================================================== CA-10
class TestCA10(Base):
    """CA-10 — cardinalidade: pai sem filho não fecha; no fluxo de épico sprint sem feature não fecha; B/C fora dele ok."""

    @staticmethod
    def recusou(rc, zona):
        return rc != 0 and zona != "archive"

    def test_epico_sprint_feature_sem_filho_recusam(self):
        a = self.alvo()
        eid = self.epico(a)
        rc, out, err = a.cs("close", eid, "--summary", "vazio")
        self.assertTrue(self.recusou(rc, a.zona(eid)), "épico sem sprint não fecha: %s%s" % (out, err))
        sid = self.sprint(a)
        rc, out, err = a.cs("close", sid, "--summary", "vazia")
        self.assertTrue(self.recusou(rc, a.zona(sid)), "sprint sem filho não fecha: %s%s" % (out, err))
        fid = self.feature(a, sid)
        a.write("src/billing/discount.py")  # aceite verde: só a cardinalidade pode recusar
        rc, out, err = a.cs("close", fid, "--summary", "vazia")
        self.assertTrue(self.recusou(rc, a.zona(fid)), "feature sem task não fecha: %s%s" % (out, err))

    def test_fluxo_de_epico_sprint_sem_feature_recusa(self):
        a = self.alvo()
        eid = self.epico(a)
        sid = self.sprint(a, epico=eid)
        tid = self.task(a, ["--sprint", sid])
        self.run_task(a, tid, "src/billing/discount.py")
        if a.zona(sid) != "archive":
            rc, out, err = a.cs("close", sid, "--summary", "so task")
        else:
            rc, out, err = 0, "", "fechou sozinha"
        self.assertTrue(self.recusou(rc, a.zona(sid)), "no fluxo de épico, sprint sem feature não fecha: %s%s" % (out, err))

    def test_casos_b_e_c_fora_do_epico_continuam_validos(self):
        a = self.alvo()
        s1 = self.sprint(a)
        f1 = self.feature(a, s1)
        t1 = self.task(a, ["--feature", f1])
        self.run_task(a, t1, "src/billing/discount.py")
        self.close_if_open(a, f1)
        self.close_if_open(a, s1)
        s2 = self.sprint(a, meta="entregar imposto")
        t2 = self.task(a, ["--sprint", s2], paths=("src/billing/extra.py",), title="criar extra")
        self.run_task(a, t2, "src/billing/extra.py")
        self.close_if_open(a, s2)

    def test_calibracao_recusa(self):
        self.assertFalse(self.recusou(0, "archive"))
        self.assertFalse(self.recusou(1, "archive"))
        self.assertTrue(self.recusou(1, "state"))


# ====================================================================== CA-11
class TestCA11(Base):
    """CA-11 — --depends-on em task/feature/sprint (start recusa com dependência aberta; ciclo recusado);
    --aceite em épico/sprint roda no close; updated_at e status em todo item."""

    @staticmethod
    def tem_campos(d):
        return isinstance(d, dict) and ISO_RE.match(str(d.get("updated_at") or "")) is not None and bool(d.get("status"))

    def test_depends_on_bloqueia_start(self):
        a = self.alvo()
        t1 = self.avulsa(a, rel="src/users/a.py", title="primeira")
        t2 = self.task(a, ["--avulsa"], agent="dev-users", paths=("src/users/b.py",), title="segunda",
                       extra=("--depends-on", t1))
        out = self.no(a, "start", t2, msg="dependência aberta")
        self.assertIn(t1, out, "a recusa cita a dependência aberta")
        s1 = self.sprint(a, start=False)
        s2 = self.sprint(a, start=False, extra=("--depends-on", s1), meta="depois")
        self.no(a, "start", s2, msg="sprint com dependência aberta")
        f1 = self.new(a, "feature", "--title", "Base", "--backlog", "--aceite", A.ACEITE)
        self.new(a, "feature", "--title", "Depois", "--backlog", "--aceite", A.ACEITE, "--depends-on", f1)

    def test_ciclo_recusado(self):
        a = self.alvo()
        rc, out, err = a.cs(*(self.task_args(["--avulsa"], agent="dev-users", paths=("src/users/c.py",),
                                             title="ciclo") + ["--dry-run"]))
        self.assertEqual(rc, 0, out + err)
        prox = json.loads(out[out.index("{"):out.rindex("}") + 1])["ids"][0]
        out = self.no(a, *self.task_args(["--avulsa"], agent="dev-users", paths=("src/users/c.py",), title="ciclo",
                                         extra=("--depends-on", prox)))
        self.assertIn("ciclo", norm(out), "dependência de si mesma é ciclo: %s" % out)
        self.assertFalse([n for n in a.nodes().values() if n["kind"] == "task"], "nada criado")

    def test_aceite_da_sprint_vermelho_recusa_o_close(self):
        a = self.alvo()
        d = tempfile.mkdtemp(prefix="cs-oraculo-marca-")
        try:
            marca = os.path.join(d, "sprint-ok")
            a.extra["CS_ORACULO_MARCA"] = marca
            sid = self.sprint(a, extra=("--aceite", A.ACEITE_MARCA))
            tid = self.task(a, ["--sprint", sid])
            self.run_task(a, tid, "src/billing/discount.py")
            rc, out, err = a.cs("close", sid, "--summary", "tentativa com aceite vermelho")
            self.assertTrue(rc != 0 and a.zona(sid) != "archive", "aceite vermelho recusa o close: %s%s" % (out, err))
            open(marca, "w").close()
            self.close_if_open(a, sid)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_epico_aceita_aceite(self):
        a = self.alvo()
        eid = self.new(a, "epico", "--title", "Com aceite", "--objetivo", "x", "--aceite", A.VERDE)
        self.assertEqual(a.item(eid).get("aceite"), A.VERDE)

    def test_updated_at_e_status_em_todo_item(self):
        a = self.alvo()
        eid = self.epico(a, start=False)
        sid = self.sprint(a, start=False)
        fid = self.new(a, "feature", "--title", "Na fila", "--backlog", "--aceite", A.ACEITE)
        tid = self.avulsa(a)
        for i in (eid, sid, fid, tid):
            self.assertTrue(self.tem_campos(a.item(i)), "%s sem updated_at/status persistidos: %r" % (i, a.item(i)))

    def test_calibracao_campos(self):
        self.assertFalse(self.tem_campos({}))
        self.assertTrue(self.tem_campos({"updated_at": "2026-10-09T10:00:00Z", "status": "backlog"}))


# ====================================================================== CA-12
class TestCA12(Base):
    """CA-12 — fechamento propaga (close {auto: true, gatilho}); aceite vermelho do pai → "pronto para fechar"."""

    @staticmethod
    def auto_close(evs, ident):
        return [e for e in evs if e.get("entity") == ident and e.get("auto") is True and e.get("gatilho")]

    def test_feature_sprint_e_epico_fecham_sozinhos(self):
        a = self.alvo()
        eid = self.epico(a)
        sid = self.sprint(a, epico=eid)
        fid = self.feature(a, sid)
        tid = self.task(a, ["--feature", fid])
        self.run_task(a, tid, "src/billing/discount.py")
        evs = a.find_events("close")
        for ident in (fid, sid, eid):
            self.assertEqual(a.zona(ident), "archive", "%s fecha sozinho quando o último filho fecha" % ident)
            self.assertTrue(self.auto_close(evs, ident), "evento close {auto: true, gatilho} para %s" % ident)

    def test_aceite_vermelho_fica_pronto_para_fechar(self):
        a = self.alvo()
        sid = self.sprint(a)
        fid = self.feature(a, sid, aceite=A.ACEITE_NUNCA)
        tid = self.task(a, ["--feature", fid])
        self.run_task(a, tid, "src/billing/discount.py")
        self.assertEqual(a.zona(fid), "state", "aceite vermelho: a feature não fecha")
        hist = json.dumps(a.item(fid).get("historico") or [], ensure_ascii=False)
        self.assertIn("pronto para fechar", norm(hist), "histórico da feature registra 'pronto para fechar'")
        nxt = self.ok(a, "next")
        self.assertIn(fid, nxt)
        self.assertIn("pronto para fechar", norm(nxt), "`next` mostra o pai pronto para fechar: %s" % nxt)

    def test_calibracao_evento(self):
        self.assertEqual(self.auto_close([], "FEA-001"), [])
        self.assertEqual(self.auto_close([{"entity": "FEA-001", "auto": False}], "FEA-001"), [])
        self.assertTrue(self.auto_close([{"entity": "FEA-001", "auto": True, "gatilho": "FEA-001/01"}], "FEA-001"))


# ====================================================================== CA-13
class TestCA13(Base):
    """CA-13 — reabertura em cascata: task arquivada reabre feature/sprint/épico no mesmo evento, com motivo e
    cascata_de; só os afetados saem do archive; outra feature ativa é estacionada; validate passa."""

    @staticmethod
    def cascata_ok(item, origem, motivo):
        h = (item or {}).get("historico") or []
        return any(x.get("acao") == "reopen" and motivo in str(x.get("reason") or "") and x.get("cascata_de") == origem
                   for x in h if isinstance(x, dict))

    def test_reabre_em_cascata(self):
        a = self.alvo()
        eid = self.epico(a)
        sid = self.sprint(a, epico=eid)
        fid = self.feature(a, sid)
        t1 = self.task(a, ["--feature", fid])
        t2 = self.task(a, ["--feature", fid], paths=("src/billing/tax.py",), title="ajustar imposto")
        self.run_task(a, t1, "src/billing/discount.py")
        self.run_task(a, t2, "src/billing/tax.py")
        for i in (fid, sid, eid):
            self.close_if_open(a, i)
        s2 = self.sprint(a, meta="outra frente")
        f2 = self.feature(a, s2, aceite=A.ACEITE_NUNCA, title="Outra feature")
        n0 = len(A.read_jsonl(a.p("events.jsonl")))
        out = self.ok(a, "reopen", t1, "--reason", "regressao no desconto")
        for i in (t1, fid, sid, eid):
            self.assertEqual(a.zona(i), "state", "%s volta para em andamento: %s" % (i, out))
        for i in (fid, sid, eid):
            self.assertTrue(self.cascata_ok(a.item(i), t1, "regressao no desconto"),
                            "%s reaberto com o motivo e cascata_de=%s: %r" % (i, t1, a.item(i).get("historico")))
        self.assertEqual(a.zona(t2), "archive", "só os afetados saem do archive")
        novos = A.read_jsonl(a.p("events.jsonl"))[n0:]
        reopen = [r for r in novos if str(r.get("type", "")).endswith("reopen")]
        self.assertEqual(len(reopen), 1, "a cascata é UM evento: %r" % [r.get("type") for r in novos])
        ids = {op[1] for op in reopen[0].get("ops") or [] if isinstance(op, list) and len(op) > 1}
        self.assertTrue({t1, fid, sid, eid} <= ids, "o mesmo evento reabre os 4: %r" % ids)
        self.assertEqual(a.zona(f2), "backlog", "a outra feature ativa é estacionada")
        self.assertTrue((a.item(f2).get("park") or {}).get("reason"), "estacionada com motivo")
        self.ok(a, "validate")

    def test_calibracao_cascata(self):
        self.assertFalse(self.cascata_ok({}, "FEA-001/01", "m"))
        self.assertTrue(self.cascata_ok({"historico": [{"acao": "reopen", "reason": "m", "cascata_de": "FEA-001/01"}]},
                                        "FEA-001/01", "m"))


# ====================================================================== CA-14
class TestCA14(Base):
    """CA-14 — nada fecha sem validação (reaberta, --devolver vermelho, backlog nunca iniciado, feature drop)."""

    @staticmethod
    def descartada(status):
        s = norm(status or "")
        return "descart" in s and "fechad" not in s

    def test_reaberta_nao_fecha_sem_novo_aceite_e_aparece_no_board(self):
        a = self.alvo()
        tid = self.avulsa(a, rel="src/users/r.py")
        self.run_task(a, tid, "src/users/r.py", agent="dev-users")
        self.ok(a, "reopen", tid, "--reason", "regressao")
        rc, out, err = a.cs("close", tid, "--summary", "fecha sem refazer")
        self.assertTrue(rc != 0 and a.zona(tid) != "archive", "reaberta sem nova M2 ACCEPTED não fecha: %s%s" % (out, err))
        board = self.ok(a, "board")
        linha = [l for l in board.splitlines() if tid in l]
        self.assertTrue(linha and "reabert" in norm(linha[0]), "board mostra a task como reaberta: %s" % board)

    def test_devolver_com_aceite_vermelho_recusa(self):
        a = self.alvo()
        sid = self.sprint(a)
        fid = self.feature(a, sid)
        self.task(a, ["--feature", fid])
        rc, out, err = a.cs("close", fid, "--summary", "devolve", "--devolver", "--reason", "sem tempo")
        self.assertTrue(rc != 0 and a.zona(fid) == "state", "--devolver com aceite vermelho recusa: %s%s" % (out, err))

    def test_backlog_nunca_iniciado_aponta_drop(self):
        a = self.alvo()
        fid = self.new(a, "feature", "--title", "Na fila", "--backlog", "--aceite", A.ACEITE)
        out = self.no(a, "close", fid, "--summary", "nunca iniciada")
        self.assertIn("drop", out, "a recusa aponta `drop`")
        tid = self.task(a, ["--backlog"], agent="dev-users", paths=("src/users/q.py",), title="na fila")
        out = self.no(a, "close", tid, "--summary", "nunca iniciada")
        self.assertIn("drop", out, "a recusa aponta `drop`")

    def test_feature_drop_descarta_tasks_nao_feitas(self):
        a = self.alvo()
        sid = self.sprint(a)
        fid = self.feature(a, sid)
        t1 = self.task(a, ["--feature", fid])
        t2 = self.task(a, ["--feature", fid], paths=("src/billing/tax.py",), title="ajustar imposto")
        self.ok(a, "feature", "drop", "--id", fid, "--reason", "fora de escopo")
        for t in (t1, t2):
            st = a.nodes().get(t, {}).get("status")
            self.assertTrue(self.descartada(st), "%s fica descartada, não fechada (status %r)" % (t, st))

    def test_calibracao_descartada(self):
        self.assertFalse(self.descartada(""))
        self.assertFalse(self.descartada("fechada"))
        self.assertTrue(self.descartada("descartada"))


# ====================================================================== CA-15
class TestCA15(Base):
    """CA-15 — comandos rodam no Windows nativo (exit real; 127 só programa inexistente); DoR não aceita 127."""

    @staticmethod
    def exit_real(out, esperado):
        return ("exit %d" % esperado) in out and "127" not in out

    def test_verify_roda_com_exit_real(self):
        a = self.alvo()
        tid = self.avulsa(a, rel="src/users/w.py", tipo="CHORE", verify=A.VERDE)
        self.ok(a, "start", tid)
        self.dispatch(a, tid)
        a.write("src/users/w.py")
        self.submit(a, tid, "src/users/w.py", "dev-users")
        out = self.ok(a, "verify", tid)
        self.assertNotIn("REPROVOU", out, "verify de comando verde passa (exit real 0): %s" % out)
        self.assertNotIn("127", out)

    def test_aceite_127_nao_e_vermelho(self):
        a = self.alvo()
        sid = self.sprint(a)
        rc, out, err = a.cs("new", "feature", "--title", "Aceite quebrado", "--sprint", sid, "--aceite", A.INEXISTENTE)
        if rc == 0:
            fid = A.CREATED_RE.findall(out)[0][0]
            rc2, out2, err2 = a.cs("start", fid)
            self.assertNotEqual(rc2, 0, "DoR: aceite com exit 127 (programa inexistente) não é 'aceite vermelho': %s%s"
                                % (out2, err2))
            self.assertNotEqual(a.zona(fid), "state")

    def test_cs_mem_check_exit_real(self):
        a = self.alvo()
        self.mem_ok(a, "add", "--agent", "dev-users", "--rule", "suite de usuarios precisa ficar verde", "--why", "x",
                    "--paths", "src/users/**", "--check", A.VERDE)
        self.mem_ok(a, "add", "--agent", "dev-users", "--rule", "constante AGE nunca muda sem migracao", "--why", "y",
                    "--paths", "src/users/**", "--check", A.VERMELHO_3)
        rc, out, err = a.mem("check", "--agent", "dev-users", "--files", "src/users/model.py")
        self.assertEqual(rc, 1, "uma lição com check vermelho reprova: %s%s" % (out, err))
        self.assertTrue(self.exit_real(out, 3), "cs-mem check propaga o exit real (3), nunca 127: %s%s" % (out, err))

    def test_selftest_roda(self):
        a = self.alvo()
        rc, out, err = a.cspy("harness", "selftest")
        self.assertEqual(rc, 0, "harness selftest roda no SO atual: %s%s" % (out, err))

    def test_calibracao_exit(self):
        self.assertFalse(self.exit_real("", 3))
        self.assertFalse(self.exit_real("FALHOU L-1 (exit 127)", 3))
        self.assertTrue(self.exit_real("FALHOU L-1 (exit 3): regra", 3))


# ====================================================================== CA-16
SECOES = ("cenario", "itens criados", "estrutura", "testes", "falhas", "correc", "retest", "aprendizado", "memoria",
          "nao resolvid", "evidencia")
SHA_RE = re.compile(r'"output_sha256":\s*"([0-9a-f]{64})"')


class TestCA16(Base):
    """CA-16 — cs-state report [--epico ID]: relatório só leitura fora do modo autônomo."""

    @staticmethod
    def secoes_faltando(text):
        t = norm(text)
        return [s for s in SECOES if s not in t]

    def test_report_do_epico(self):
        a = self.alvo()
        eid = self.epico(a)
        sid = self.sprint(a, epico=eid)
        fid = self.feature(a, sid)
        tid = self.task(a, ["--feature", fid])
        self.run_task(a, tid, "src/billing/discount.py")
        shas = set(SHA_RE.findall(a.events_bytes().decode("utf-8", "replace")))
        self.assertTrue(shas, "pré-condição: o verify grava output_sha256 nos eventos")
        ev0, snap0 = a.events_bytes(), A.snapshot(a.root)
        out = self.ok(a, "report", "--epico", eid)
        self.assertEqual(self.secoes_faltando(out), [], "seções do relatório:\n%s" % out)
        for i in (eid, sid, fid, tid):
            self.assertIn(i, out, "relatório lista o item criado %s" % i)
        self.assertTrue(any(s in out for s in shas), "evidência: sha da saída do verify")
        self.assertEqual(a.events_bytes(), ev0, "report é só leitura (eventos)")
        self.assertEqual(A.snapshot(a.root), snap0, "report é só leitura (estado)")

    def test_report_sem_epico_janela_de_eventos(self):
        a = self.alvo()
        self.avulsa(a)
        ev0, snap0 = a.events_bytes(), A.snapshot(a.root)
        out = self.ok(a, "report")
        self.assertEqual(self.secoes_faltando(out), [], out)
        self.assertEqual(a.events_bytes(), ev0)
        self.assertEqual(A.snapshot(a.root), snap0)

    def test_calibracao_secoes(self):
        self.assertEqual(self.secoes_faltando(""), list(SECOES))
        bom = ("Cenários; Itens criados; Estrutura; Testes; Falhas; Correções; Retestes; Aprendizado; "
               "Memória atualizada; Não resolvidos; Evidências")
        self.assertEqual(self.secoes_faltando(bom), [])


# ====================================================================== CA-17
class TestCA17(Base):
    """CA-17 — autocorreção: retry estruturado, lição de falha só no ACCEPTED, 3 tentativas → ESCALATED, limites."""

    RETRY = ("--esperado", "teste de marca verde", "--obtido", "AssertionError marca ausente",
             "--causa", "zebracausa marca nao criada", "--correcao", "zebracorrecao criar a marca")

    def prep(self):
        a = self.alvo()
        d = tempfile.mkdtemp(prefix="cs-oraculo-marca-")
        self.addCleanup(shutil.rmtree, d, True)
        a.extra["CS_ORACULO_MARCA"] = os.path.join(d, "ok")
        tid = self.avulsa(a, rel="src/users/flag.py", title="ligar flag", tipo="CHORE", verify=A.ACEITE_MARCA)
        self.ok(a, "start", tid)
        return a, tid

    def falha(self, a, tid, primeira):
        self.dispatch(a, tid)
        if primeira:
            a.write("src/users/flag.py")
        self.submit(a, tid, "src/users/flag.py", "dev-users")
        a.cs("verify", tid)
        st = json.dumps(a.nodes().get(tid))
        self.assertTrue("REJECTED" in st or "ESCALATED" in st, "verify vermelho deveria reprovar a tentativa: %s" % st)

    @staticmethod
    def escalada(node):
        return "ESCALATED" in json.dumps(node or {})

    def test_retry_exige_campos_estruturados(self):
        a, tid = self.prep()
        self.falha(a, tid, True)
        self.no(a, "retry", tid, "--findings", "texto livre", msg="retry sem esperado/obtido/causa/correcao")
        self.ok(a, "retry", tid, *self.RETRY)

    def test_licao_de_falha_so_no_accepted(self):
        a, tid = self.prep()
        self.falha(a, tid, True)
        self.ok(a, "retry", tid, *self.RETRY)
        self.assertNotIn("zebracausa", json.dumps(a.lessons("dev-users")), "lição de falha só no ACCEPTED")
        open(a.extra["CS_ORACULO_MARCA"], "w").close()
        self.dispatch(a, tid)
        self.submit(a, tid, "src/users/flag.py", "dev-users")
        self.ok(a, "verify", tid)
        self.ok(a, "review", tid, "--by", "reviewer", "--verdict", "PASS", "--findings", "ok")
        self.ok(a, "accept", tid)
        txt = json.dumps(a.lessons("dev-users"), ensure_ascii=False)
        self.assertIn("zebracausa", txt, "a lição guarda a causa")
        self.assertIn("zebracorrecao", txt, "a lição guarda a correção")

    def test_tres_tentativas_escalam_e_entram_no_relatorio(self):
        a, tid = self.prep()
        for n in (1, 2, 3):
            self.falha(a, tid, n == 1)
            if n < 3:
                self.ok(a, "retry", tid, *self.RETRY)
        self.assertTrue(self.escalada(a.nodes().get(tid)), "3 tentativas esgotadas → ESCALATED automático: %r"
                        % a.nodes().get(tid))
        self.no(a, "retry", tid, *self.RETRY, msg="sem 4ª tentativa")
        t = norm(self.ok(a, "report"))
        self.assertIn("nao resolvid", t)
        self.assertIn(tid.lower(), t[t.index("nao resolvid"):], "a task escalada entra no relatório como não resolvida")

    def test_max_attempts_conferido(self):
        a = self.alvo()
        alvo_m = None
        for n in ("machines.json", "machines.json5"):
            if os.path.isfile(a.p("harness", n)):
                alvo_m = a.p("harness", n)
                break
        self.assertTrue(alvo_m, "máquinas instaladas no alvo")
        txt = A.read_text(alvo_m)
        novo = re.sub(r'("?max_attempts"?\s*:\s*)3', r"\g<1>7", txt, count=1)
        self.assertNotEqual(novo, txt, "limits.max_attempts = 3 nas máquinas instaladas")
        with open(alvo_m, "w", encoding="utf-8", newline="\n") as f:
            f.write(novo)
        rc1, o1, e1 = a.cs("validate")
        rc2, o2, e2 = a.cspy("harness", "selftest")
        self.assertTrue((rc1 != 0 and "max_attempts" in o1 + e1) or (rc2 != 0 and "max_attempts" in o2 + e2),
                        "max_attempts != max_retries + 1 deve ser acusado: %s%s | %s%s" % (o1, e1, o2, e2))

    def test_calibracao_escalada(self):
        self.assertFalse(self.escalada({}))
        self.assertFalse(self.escalada({"status": "REJECTED/REJECTED"}))
        self.assertTrue(self.escalada({"status": "ESCALATED/ESCALATED"}))


# ====================================================================== CA-18
class TestCA18(Base):
    """CA-18 — estado, itens, memória, sessão e config do harness em .json válido, indent 2, formatVersion; JSONL
    igual; .json5 legado continua legível."""

    DIRS = ("backlog", "state", "archive", ".engine", "memory")

    def docs(self, a):
        out = []
        for d in self.DIRS:
            base = a.p(d)
            for dp, dns, fs in os.walk(base):
                if os.path.basename(dp) == "index" and os.path.basename(os.path.dirname(dp)) == "memory":
                    dns[:] = []
                    continue
                for f in fs:
                    if f.endswith((".json", ".json5")):
                        out.append(os.path.join(dp, f))
        for n in ("config.json", "config.json5"):
            if os.path.isfile(a.p("harness", n)):
                out.append(a.p("harness", n))
        return out

    def test_estado_gravado_em_json_formatado(self):
        a = self.alvo()
        self.epico(a)
        self.avulsa(a)
        self.mem_ok(a, "add", "--agent", "dev-users", "--rule", "validar idade", "--why", "regra", "--paths",
                    "src/users/**")
        self.mem_ok(a, "add", "--kind", "decision", "--text", "idade minima 18 anos", "--founder", "Ana")
        self.ok(a, "session", "start", "--request", "ajustar idade")
        docs = self.docs(a)
        self.assertGreaterEqual(len(docs), 4, "documentos do harness encontrados: %r" % docs)
        legados = [os.path.relpath(p, a.root) for p in docs if p.endswith(".json5")]
        self.assertEqual(legados, [], "o harness ainda grava JSON5")
        for p in docs:
            t = A.read_text(p)
            self.assertIsNone(A.json_fmt_problem(t), "%s: %s" % (os.path.relpath(p, a.root), A.json_fmt_problem(t)))
            d = json.loads(t)
            if isinstance(d, dict):
                self.assertIn("formatVersion", d, "%s sem formatVersion" % os.path.relpath(p, a.root))

    def test_jsonl_continua_jsonl(self):
        a = self.alvo()
        self.avulsa(a)
        self.mem_ok(a, "add", "--kind", "decision", "--text", "idade minima 18 anos", "--founder", "Ana")
        for rel in ("events.jsonl", "memory/knowledge.jsonl"):
            p = a.p(*rel.split("/"))
            rows = A.read_jsonl(p)
            self.assertTrue(rows and all(isinstance(r, dict) for r in rows), "%s: um objeto JSON por linha" % rel)

    def test_json5_legado_continua_legivel(self):
        a = self.alvo()
        d = a.p("state", "memory", "agents")
        os.makedirs(d, exist_ok=True)
        for ext in (".json", ".json5"):
            if os.path.isfile(os.path.join(d, "dev-users" + ext)):
                os.remove(os.path.join(d, "dev-users" + ext))
        legado = ("// lições do agente dev-users — legado JSON5\n{\n agent: \"dev-users\",\n lessons: [\n  {id: "
                  "\"L-dev-users-legado\", rule: \"validar idade com a constante AGE\", why: \"regra\", trigger: "
                  "{paths: [\"src/users/**\"], kinds: []}, source: \"human\", evidence: [], count: 1, recurrences: 0, "
                  "first_seen: \"2026-10-01T00:00:00Z\", last_hit: \"2026-10-01T00:00:00Z\", status: \"active\", "
                  "occurrences: []},\n ],\n}\n")
        with open(os.path.join(d, "dev-users.json5"), "w", encoding="utf-8", newline="\n") as f:
            f.write(legado)
        out = self.mem_ok(a, "inject", "--agent", "dev-users", "--paths", "src/users/model.py")
        self.assertIn("L-dev-users-legado", out, "lição em .json5 legado continua legível")

    def test_calibracao_formato(self):
        self.assertIsNotNone(A.json_fmt_problem(""))
        self.assertIsNotNone(A.json_fmt_problem('{\n a: 1,\n}\n'))
        self.assertIsNotNone(A.json_fmt_problem('{"a": 1, "b": 2}\n'))
        self.assertIsNone(A.json_fmt_problem('{\n  "formatVersion": 1,\n  "a": [\n    1\n  ]\n}\n'))


# ====================================================================== CA-19
class TestCA19(Base):
    """CA-19 — migração JSON5 → JSON segura de um alvo 0.10.0: detecção no plano do upgrade, conversão pelo motor
    (cs-state migrate json-format) com backup, evento encadeado, registro arquivo a arquivo, validate, idempotência
    e restauração em falha."""

    @classmethod
    def setUpClass(cls):
        cls.tmpl = None
        legado = A.legacy_skill()
        a = Alvo.novo(skill=legado)
        cls.tmpl = a
        t = unittest.TestCase()

        def ok(*args, actor=None):
            rc, out, err = a.cs(*args, actor=actor)
            t.assertEqual(rc, 0, "alvo legado: cs-state %s (exit %d): %s%s" % (" ".join(args), rc, out, err))
            return out
        eid = A.CREATED_RE.findall(ok("new", "epico", "--title", "Billing", "--objetivo", "cobrar"))[0][0]
        ok("start", eid)
        sid = A.CREATED_RE.findall(ok("new", "sprint", "--meta", "desconto", "--epico", eid))[0][0]
        ok("start", sid)
        fid = A.CREATED_RE.findall(ok("new", "feature", "--title", "Desconto", "--sprint", sid, "--aceite",
                                      A.ACEITE))[0][0]
        ok("start", fid)
        ok("new", *Base.task_args(None, ["--feature", fid]))
        ok("new", *Base.task_args(None, ["--avulsa"], agent="dev-users", paths=("src/users/idade.py",), title="idade"))
        rc, out, err = a.mem("add", "--agent", "dev-users", "--rule", "validar idade", "--why", "regra", "--paths",
                             "src/users/**")
        t.assertEqual(rc, 0, out + err)
        with open(a.p("run.json5"), "w", encoding="utf-8") as f:
            f.write('// run.json5 — alvo 0.10.0 (oráculo)\n{\n skill_version: "0.10.0",\n}\n')

    @classmethod
    def tearDownClass(cls):
        if cls.tmpl:
            cls.tmpl.rm()

    def copia(self):
        dst = tempfile.mkdtemp(prefix="cs-legado-")
        shutil.rmtree(dst)
        shutil.copytree(self.tmpl.root, dst, symlinks=True)
        a = Alvo(dst)
        self.alvos.append(a)
        return a

    @staticmethod
    def json5_de_estado(root):
        out = []
        for d in ("backlog", "state", "archive", ".engine", "memory"):
            for dp, _, fs in os.walk(os.path.join(root, A.SD, d)):
                out += [os.path.relpath(os.path.join(dp, f), os.path.join(root, A.SD)).replace(os.sep, "/")
                        for f in fs if f.endswith(".json5")]
        return sorted(out)

    def migrate(self, a):
        return a.cs("migrate", "json-format", engine=os.path.join(A.ENGINE_SRC, "state.py"))

    def test_plano_do_upgrade_detecta(self):
        a = self.copia()
        snap = A.snapshot(a.root)
        rc, out, err = a.cspy("upgrade")
        self.assertEqual(rc, 0, out + err)
        self.assertIn("json-format", out + err, "o plano do upgrade detecta o estado JSON5 (migração json-format)")
        self.assertEqual(A.snapshot(a.root), snap, "plano não escreve")

    def test_migra_com_backup_evento_registro_e_validate(self):
        a = self.copia()
        antes = self.json5_de_estado(a.root)
        self.assertTrue(antes, "pré-condição: alvo legado com estado em JSON5")
        shas = {r: A.sha_file(a.p(*r.split("/"))) for r in antes}
        ev0 = a.events_bytes()
        rc, out, err = self.migrate(a)
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(self.json5_de_estado(a.root), [], "nenhum .json5 de estado sobra")
        for r in antes:
            novo = a.p(*(r[:-1]).split("/"))
            self.assertTrue(os.path.isfile(novo), "%s convertido para .json" % r)
            self.assertIsNone(A.json_fmt_problem(A.read_text(novo)), r)
        bk = {}
        for dp, _, fs in os.walk(a.p("backups")):
            for f in fs:
                bk[A.sha_file(os.path.join(dp, f))] = f
        for r, s in shas.items():
            self.assertIn(s, bk, "backup do original %s" % r)
        ev1 = a.events_bytes()
        self.assertTrue(ev1.startswith(ev0) and len(ev1) > len(ev0), "eventos: append-only com o evento da migração")
        novos = ev1[len(ev0):].decode("utf-8", "replace")
        self.assertIn("migr", novos.lower(), "evento do motor registra a migração")
        registro = novos + out + err
        for r in antes:
            self.assertIn(r.rsplit("/", 1)[-1][:-6], registro, "registro arquivo a arquivo: %s" % r)
        for n in a.nodes().values():
            self.assertTrue(n["path"].endswith(".json"), "caminho do item reescrito: %s" % n["path"])
        rc, out, err = a.cs("validate", engine=os.path.join(A.ENGINE_SRC, "state.py"))
        self.assertEqual(rc, 0, "validate (cadeia de hash íntegra) depois da migração: %s%s" % (out, err))

    def test_segunda_execucao_nao_muda_nada(self):
        a = self.copia()
        rc, out, err = self.migrate(a)
        self.assertEqual(rc, 0, out + err)
        snap, ev = A.snapshot(a.root), a.events_bytes()
        rc, out, err = self.migrate(a)
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(A.snapshot(a.root), snap, "segunda execução não muda nada")
        self.assertEqual(a.events_bytes(), ev)

    def test_falha_no_meio_restaura(self):
        a = self.copia()
        alvo_q = [r for r in self.json5_de_estado(a.root) if "/tasks/" in r][-1]
        with open(a.p(*alvo_q.split("/")), "wb") as f:
            f.write(b"// quebrado\n{ id: \"x\", ")
        snap = A.snapshot(a.root)
        rc, out, err = self.migrate(a)
        self.assertNotEqual(rc, 0, "arquivo ilegível no meio: a migração falha")
        self.assertIn(alvo_q.rsplit("/", 1)[-1], out + err, "a falha aponta o arquivo que não converteu")
        self.assertEqual(A.snapshot(a.root), snap, "falha restaura o estado anterior por inteiro")

    def test_calibracao_json5_restantes(self):
        d = tempfile.mkdtemp(prefix="cs-oraculo-")
        try:
            os.makedirs(os.path.join(d, A.SD, "state", "tasks"))
            self.assertEqual(self.json5_de_estado(d), [])
            open(os.path.join(d, A.SD, "state", "tasks", "x.json5"), "w").close()
            self.assertEqual(self.json5_de_estado(d), ["state/tasks/x.json5"])
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
