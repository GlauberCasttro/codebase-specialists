"""iter19 (B-14, task 02) — estado em JSON padrão, ordem de leitura e chaves em inglês.

Cobre o que o oráculo da campanha deixa para o motor: o mapa pt→en é POR CAMINHO (`para` da story = so_that;
`para` do history = to), a leitura aceita os dois idiomas e os dois formatos, a gravação é determinística e o
validate acusa o `.json5` de estado que sobra ao lado do `.json`. Pessoa = "Ana"."""
import json
import os
import subprocess
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import fixture  # noqa: E402
import hcore  # noqa: E402
import j5  # noqa: E402

STATE = os.path.join(fixture.ENGINE, "state.py")


def st(root, *args):
    e = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    e.pop("CLAUDE_PROJECT_DIR", None)
    p = subprocess.run([sys.executable, STATE, "--root", root] + list(args), cwd=root, env=e,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    return p.returncode, p.stdout.decode() + p.stderr.decode()


def st_ok(root, *args):
    code, out = st(root, *args)
    assert code == 0, "cs-state %s → %d\n%s" % (" ".join(args), code, out)
    return out


STORY_PT = {
    "id": "STO-001", "kind": "story", "tipo": "US", "title": "Cupom", "path": "state/x/story.json5",
    "como": "Ana", "quero": "cupom", "para": "pagar menos",
    "criterios": [{"id": "AC-1", "gherkin": "Dado Quando Então", "teste": "tests.t"}],
    "teste": "tests.proof", "reproducao": "accept.t", "motivo": "m", "aceite": "cmd", "epico": "EPC-001",
    "objetivo": "o", "metrica": "m", "meta": "g", "reaberta": 1,
    "reaberturas": [{"at": "t", "closed": {"entregue": ["a"], "metricas": {"tentativas": 2, "status_m2": "ACCEPTED"}}}],
    "closed": {"entregue": ["a"], "devolvido": [], "metricas": {"tentativas": 1, "tasks": 3}, "origem": "state"},
    "historico": [{"at": "t", "acao": "move", "by": "Ana", "de": "A", "para": "SPR-001"}],
}


class TestMapaPorCaminho(unittest.TestCase):
    def test_para_da_story_e_so_that_e_do_historico_e_to(self):
        en = hcore.item_to_en(STORY_PT)
        self.assertEqual(en["so_that"], "pagar menos")
        self.assertNotIn("to", en)
        self.assertEqual(en["history"][0]["to"], "SPR-001")
        self.assertEqual(en["history"][0]["from"], "A")
        self.assertEqual(en["history"][0]["action"], "move")
        self.assertNotIn("so_that", en["history"][0])

    def test_mapa_completo(self):
        en = hcore.item_to_en(STORY_PT)
        for k in ("type", "as_a", "i_want", "acceptance_criteria", "proving_test", "failing_test", "reason",
                  "acceptance_cmd", "epic", "objective", "metric", "goal", "reopened", "reopenings", "history"):
            self.assertIn(k, en)
        self.assertEqual(en["acceptance_criteria"][0], {"id": "AC-1", "gherkin": "Dado Quando Então", "test": "tests.t"})
        self.assertEqual(sorted(en["closed"]), ["delivered", "metrics", "origin", "returned"])
        self.assertEqual(en["closed"]["metrics"], {"attempts": 1, "tasks": 3})
        self.assertEqual(en["reopenings"][0]["closed"]["metrics"], {"attempts": 2, "m2_status": "ACCEPTED"})
        self.assertEqual(en["kind"], "story")
        pt_keys = set(hcore.item_to_pt(en)) & {"type", "as_a", "history"}
        self.assertEqual(pt_keys, set())

    def test_ida_e_volta_e_idempotente(self):
        pt = hcore.item_to_pt(STORY_PT)
        self.assertEqual(pt["path"], "state/x/story.json")
        pt2 = dict(STORY_PT, path="state/x/story.json")
        self.assertEqual(hcore.item_to_pt(hcore.item_to_en(STORY_PT)), pt)
        self.assertEqual(hcore.item_to_pt(pt), pt)
        self.assertEqual(hcore.canonical(hcore.item_to_pt(hcore.item_to_en(pt2))), hcore.canonical(pt2))

    def test_sessao(self):
        rec = {"saved_at": "t", "blocos": [{"titulo": "T", "linhas": ["a"]}]}
        en = hcore.session_to_en(rec)
        self.assertEqual(en["blocks"], [{"title": "T", "lines": ["a"]}])
        self.assertEqual(hcore.session_to_pt(en), rec)


class TestOrdemEBytes(unittest.TestCase):
    def test_ordem_de_leitura_history_por_ultimo(self):
        en = hcore.order_item(hcore.item_to_en(STORY_PT))
        keys = list(en)
        self.assertEqual(keys[:6], ["id", "kind", "type", "title", "as_a", "i_want"])
        self.assertLess(keys.index("so_that"), keys.index("acceptance_criteria"))
        self.assertEqual(keys[-1], "history")
        rest = keys[keys.index("path") + 1:-1]
        self.assertEqual(rest, sorted(rest))

    def test_texto_deterministico_e_json_indentado(self):
        en = hcore.with_generated_by(hcore.order_item(hcore.item_to_en(STORY_PT)), "gerado  por   Ana")
        a, b = hcore.json_text(en), hcore.json_text(json.loads(hcore.json_text(en)))
        self.assertEqual(a, b)
        self.assertEqual(a, json.dumps(json.loads(a), indent=2, ensure_ascii=False) + "\n")
        self.assertEqual(json.loads(a)["_generated_by"], "gerado por Ana")
        self.assertIn('\n      "id": "AC-1"', a)  # um item de lista por linha, indent 2


class TestArvore(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo(with_state=False)
        self.addCleanup(fixture.rm, self.root)
        st_ok(self.root, "init")
        st_ok(self.root, "new", "epico", "--title", "Cobranca", "--objetivo", "cobrar certo", "--metrica", "0 erros")
        self.epic = os.path.join(self.root, ".swarm", "backlog", "epicos", "EPC-001-cobranca", "epico.json")

    def test_epico_e_projecao_sao_json_em_ingles(self):
        with open(self.epic, encoding="utf-8") as f:
            d = json.loads(f.read())
        self.assertEqual((d["objective"], d["metric"]), ("cobrar certo", "0 erros"))
        self.assertEqual(list(d)[:2], ["_generated_by", "id"])
        self.assertEqual(list(d)[-1], "history")
        self.assertEqual(d["history"][0]["action"], "criado")
        proj = os.path.join(self.root, ".swarm", ".engine", "projection.json")
        self.assertTrue(os.path.isfile(proj))
        self.assertFalse(os.path.exists(proj + "5"))
        self.assertEqual(st(self.root, "validate")[0], 0)

    def test_formato_anterior_e_lido_e_depois_regravado(self):
        with open(self.epic, encoding="utf-8") as f:
            d = json.loads(f.read())
        old = hcore.item_to_pt(d)
        old["path"] = old["path"] + "5"
        os.remove(self.epic)
        with open(self.epic + "5", "w", encoding="utf-8") as f:
            f.write(j5.dumps(old, header="gerado por cs-state"))
        code, out = st(self.root, "validate")
        self.assertEqual(code, 0, out)
        st_ok(self.root, "start", "EPC-001")
        new = os.path.join(self.root, ".swarm", "state", "epicos", "EPC-001-cobranca", "epico.json")
        self.assertTrue(os.path.isfile(new))
        self.assertFalse(os.path.exists(self.epic + "5"))
        self.assertEqual(st(self.root, "validate")[0], 0)

    def test_json5_ao_lado_do_json_e_orfao(self):
        with open(self.epic, encoding="utf-8") as f:
            d = json.loads(f.read())
        stale = self.epic + "5"
        with open(stale, "w", encoding="utf-8") as f:
            f.write(j5.dumps(hcore.item_to_pt(d), header="x"))
        code, out = st(self.root, "validate")
        self.assertNotEqual(code, 0)
        self.assertIn("epico.json5", out)
        self.assertIn("órfão", out)

    def test_json_adulterado_com_chave_pt_e_acusado(self):
        with open(self.epic, encoding="utf-8") as f:
            txt = f.read()
        renomeada = txt.replace('"objective"', '"objetivo"')
        self.assertNotEqual(renomeada, txt)
        with open(self.epic, "w", encoding="utf-8") as f:
            f.write(renomeada)
        code, out = st(self.root, "validate")
        self.assertNotEqual(code, 0, out)
        self.assertIn("edição à mão", out)
        d = json.loads(txt)
        ins = dict([("_generated_by", d.pop("_generated_by")), ("tipo", "EVIL")] + list(d.items()))
        with open(self.epic, "w", encoding="utf-8") as f:
            f.write(json.dumps(ins, indent=2, ensure_ascii=False) + "\n")
        code, out = st(self.root, "validate")
        self.assertNotEqual(code, 0, out)
        self.assertIn("edição à mão", out)


class TestAmendShow(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo(with_state=False)
        self.addCleanup(fixture.rm, self.root)
        st_ok(self.root, "init")
        st_ok(self.root, "new", "task", "--tipo", "chore", "--agent", "dev-a", "--title", "Limpa", "--avulsa", "--allowed-path",
              "src/a.py", "--verify-cmd", "true", "--criterio", "AC-1|Dado a Quando b Então c|", "--motivo", "m")

    def test_show_inexistente_e_so_leitura(self):
        code, out = st(self.root, "show", "TSK-999/09")
        self.assertNotEqual(code, 0)
        self.assertIn("TSK-999/09", out)

    def test_amend_nao_iniciada_reflete_e_show_imprime(self):
        tid = st_ok(self.root, "find", "Limpa").split()[0]
        after = json.dumps([{"id": "AC-1", "criterion": "Dado x Quando y Então z", "verified_by": "reviewer"},
                            {"id": "AC-2", "criterion": "Dado k Quando l Então m", "verified_by": "test:tests.t"}])
        st_ok(self.root, "amend", tid, "--field", "acceptance_criteria", "--after", after, "--reason", "mais um")
        out = st_ok(self.root, "show", tid)
        self.assertRegex(out, r"(?m)^# .*Limpa")
        self.assertIn("AC-2", out)
        self.assertIn("mais um", out)
        self.assertEqual(st(self.root, "validate")[0], 0)

    def test_find_termina_no_caminho(self):
        out = st_ok(self.root, "find", "Limpa").strip().splitlines()[0]
        self.assertTrue(out.endswith(".json"), out)



# ================================================================ task 04 — cs-state migrate state-format
import io  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import tarfile  # noqa: E402
import tempfile  # noqa: E402

OLD_COMMIT = "97a1718"  # 0.10.1
_GIT_ENV = {"GIT_AUTHOR_NAME": "Ana", "GIT_AUTHOR_EMAIL": "ana@x", "GIT_COMMITTER_NAME": "Ana",
            "GIT_COMMITTER_EMAIL": "ana@x"}
_OLD = {}
VERIFY = "python3 -m unittest tests.test_ok"
ACEITE = "python3 -m unittest accept.test_accept"
G1 = "Dado pedido Quando aplico Então desconta"


def _sh(argv, cwd, timeout=600):
    e = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", **_GIT_ENV)
    for k in ("CLAUDE_PROJECT_DIR", "CS_ACTOR", "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        e.pop(k, None)
    p = subprocess.run(argv, cwd=cwd, env=e, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def _git(root, *args):
    c, o, e = _sh(["git", "-C", root] + list(args), root)
    assert c == 0, "git %s: %s%s" % (" ".join(args), o, e)
    return o


def _old_skill():
    """Skill 0.10.1 real ($CS_OLD_SKILL_DIR ou git archive do commit). None = indisponível (o teste se pula)."""
    if "skill" in _OLD:
        return _OLD["skill"]
    d = os.environ.get("CS_OLD_SKILL_DIR")
    if not d:
        top = subprocess.run(["git", "-C", _HERE, "rev-parse", "--show-toplevel"], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE).stdout.decode().strip()
        p = subprocess.run(["git", "-C", top or _HERE, "archive", "--format=tar", OLD_COMMIT],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if p.returncode != 0:
            _OLD["skill"] = None
            return None
        d = os.path.join(_old_base(), "skill-0.10.1")
        os.makedirs(d)
        with tarfile.open(fileobj=io.BytesIO(p.stdout)) as tf:
            tf.extractall(d, filter="data") if hasattr(tarfile, "data_filter") else tf.extractall(d)
    _OLD["skill"] = os.path.realpath(d)
    return _OLD["skill"]


def _old_base():
    if "base" not in _OLD:
        _OLD["base"] = os.path.realpath(tempfile.mkdtemp(prefix="cs-iter19-t04-"))
    return _OLD["base"]


def tearDownModule():
    if "base" in _OLD:
        shutil.rmtree(_OLD["base"], ignore_errors=True)


def _w(root, rel, txt):
    full = os.path.join(root, rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(txt)


def _old_tool(root, name, *args):
    return _sh([sys.executable, os.path.join(root, ".swarm", "harness", name + ".py"), "--root", root] + list(args), root)


def _old_ok(root, name, *args):
    c, o, e = _old_tool(root, name, *args)
    assert c == 0, "%s %s → %d\n%s%s" % (name, " ".join(args), c, o[-2000:], e[-2000:])
    return o


def _commit(root, msg):
    _git(root, "add", "-A")
    if not _git(root, "diff", "--cached", "--name-only").strip():
        return
    c, o, e = _sh(["git", "-C", root, "-c", "core.hooksPath=" + os.path.join(root, ".git", "hooks"), "commit", "-q", "-m", msg], root)
    assert c == 0, "pre-commit barrou %r:\n%s%s" % (msg, o[-2000:], e[-2000:])


def build_old_target():
    """Alvo 0.10.1 REAL (estado em .json5, chaves pt): épico/sprint/feature/tasks em backlog, state e archive + sessão."""
    skill = _old_skill()
    if skill is None:
        return None
    if "target" in _OLD:
        return _OLD["target"]
    code = ("import sys; sys.dont_write_bytecode=True; sys.path.insert(0, %r); sys.path.insert(0, %r);"
            "import fixture; print(fixture.make_repo())" % (os.path.join(skill, "scripts"), os.path.join(skill, "scripts", "emit", "tests")))
    rc, out, err = _sh([sys.executable, "-c", code], _old_base())
    assert rc == 0, out + err
    dest = os.path.join(_old_base(), "alvo")
    shutil.move(out.strip().splitlines()[-1], dest)
    _w(dest, "tests/__init__.py", "")
    _w(dest, "tests/test_ok.py", "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n")
    _w(dest, "accept/__init__.py", "")
    _w(dest, "accept/test_accept.py", "import os\nimport unittest\n\n\nclass A(unittest.TestCase):\n    def test_feature(self):\n"
                                      "        self.assertTrue(os.path.exists('src/billing/cupom.py'))\n")
    _git(dest, "init", "-q")
    _git(dest, "add", "-A")
    _git(dest, "commit", "-q", "-m", "init")
    for args in (("init", "--platforms", "claude-code"), ("harness", "install", "--allow-outside"), ("emit", "--allow-outside")):
        c, o, e = _sh([sys.executable, os.path.join(skill, "scripts", "cs.py"), "--target", dest] + list(args), dest)
        assert c == 0, "cs.py %s: %s%s" % (args, o[-2000:], e[-2000:])
    _git(dest, "add", "-A")
    _git(dest, "commit", "-q", "-m", "gerado")
    c, o, e = _sh([sys.executable, os.path.join(skill, "scripts", "cs.py"), "--target", dest, "harness", "install", "--allow-outside", "--git-hook"], dest)
    assert c == 0, o + e
    S = lambda *a: _old_ok(dest, "state", *a)  # noqa: E731
    S("init")
    S("new", "epico", "--title", "Cobrança", "--objetivo", "cobrar certo", "--metrica", "0 erros")
    S("new", "sprint", "--meta", "entregar cupom", "--epico", "EPC-001")
    S("start", "EPC-001")
    S("start", "SPR-001")
    S("new", "feature", "--title", "Cupom", "--sprint", "SPR-001", "--aceite", ACEITE)
    S("start", "FEA-001")
    crit = "AC-1|%s|tests.test_ok" % G1
    us = lambda title, path, parent: re.search(r"criad[oa] (\S+)", S(  # noqa: E731
        "new", "task", "--tipo", "US", "--agent", "dev-billing", "--title", title, *parent, "--allowed-path", path,
        "--verify-cmd", VERIFY, "--como", "cliente", "--quero", "cupom", "--para", "pagar menos", "--criterio", crit)).group(1)
    t1 = us("Total com cupom", "src/billing/total.py", ["--feature", "FEA-001"])
    S("start", t1)
    S("dispatch", t1, "--manual", "--model", "sonnet")
    with open(os.path.join(dest, "src/billing/total.py"), "a", encoding="utf-8") as fh:
        fh.write("# %s\n" % t1)
    S("submit", t1, "--files-changed", "src/billing/total.py", "--check", "unittest: OK", "--risk", "nenhum", "--handoff-notes", "ok")
    S("verify", t1)
    S("review", t1, "--by", "reviewer", "--verdict", "PASS", "--findings", "conferido")
    S("accept", t1)
    _commit(dest, "entrega")
    S("close", t1, "--summary", "entregue")
    t2 = us("Aplicar cupom", "src/billing/coupons.py", ["--feature", "FEA-001"])
    S("start", t2)
    S("new", "task", "--tipo", "BUG", "--agent", "dev-web", "--title", "Rota quebra", "--backlog", "--allowed-path",
      "src/web/app.py", "--verify-cmd", VERIFY, "--reproducao", "accept.test_accept")
    S("new", "feature", "--title", "Boleto", "--backlog", "--aceite", ACEITE)
    _old_ok(dest, "session", "save")
    _commit(dest, "estado")
    _OLD["target"] = dest
    return dest


def _state_files(root):
    sd = os.path.join(root, ".swarm")
    out = []
    for z in ("backlog", "state", "archive", ".engine"):
        for dp, dns, fns in os.walk(os.path.join(sd, z)):
            rel = os.path.relpath(dp, sd).replace(os.sep, "/")
            if "memory" in rel.split("/") or "mandatos" in rel.split("/") or "evidence" in rel.split("/"):
                dns[:] = []
                continue
            for f in fns:
                if f.endswith(".json") or f.endswith(".json5"):
                    out.append(rel + "/" + f)
    return sorted(out)


def _snap(root):
    snap = {}
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d != ".git"]
        for f in fns:
            full = os.path.join(dp, f)
            if not os.path.islink(full):
                with open(full, "rb") as fh:
                    snap[os.path.relpath(full, root)] = fh.read()
    return snap


def _copy_old(name):
    tpl = build_old_target()
    if tpl is None:
        raise unittest.SkipTest("skill 0.10.1 indisponível (git archive %s / $CS_OLD_SKILL_DIR)" % OLD_COMMIT)
    d = os.path.join(_old_base(), name)
    shutil.copytree(tpl, d, symlinks=True)
    return d


class TestMigrarFormato(unittest.TestCase):
    """cs-state migrate state-format num alvo 0.10.1 real: UM evento encadeado, mapa de caminhos, idempotente."""

    def setUp(self):
        self.root = _copy_old(self.id().split(".")[-1])
        self.before_files = _state_files(self.root)
        with open(os.path.join(self.root, ".swarm", "events.jsonl"), "rb") as fh:
            self.events_before = fh.read()

    def test_alvo_de_partida_e_0101_em_json5(self):
        olds = [p for p in self.before_files if p.endswith(".json5")]
        self.assertGreaterEqual(len(olds), 8, self.before_files)
        self.assertIn(".engine/projection.json5", self.before_files)
        self.assertEqual(st(self.root, "validate")[0], 0, st(self.root, "validate")[1])

    def test_dry_run_lista_e_nao_escreve_nada(self):
        snap = _snap(self.root)
        code, out = st(self.root, "migrate", "state-format", "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertEqual(_snap(self.root), snap, "dry-run escreveu")
        self.assertIn("epico.json5", out)
        self.assertIn("projection.json5", out)
        self.assertIn("dry-run", out)
        for p in self.before_files:
            if p.endswith(".json5"):
                self.assertIn(p, out)

    def test_migra_com_um_evento_encadeado_e_mapa_de_caminhos(self):
        olds = [p for p in self.before_files if p.endswith(".json5")]
        code, out = st(self.root, "migrate", "state-format")
        self.assertEqual(code, 0, out)
        after = _state_files(self.root)
        self.assertEqual([p for p in after if p.endswith(".json5")], [], after)
        self.assertEqual(sorted(p[:-1] for p in olds), after)
        with open(os.path.join(self.root, ".swarm", "events.jsonl"), "rb") as fh:
            now = fh.read()
        self.assertTrue(now.startswith(self.events_before), "eventos antigos reescritos")
        new = [ln for ln in now[len(self.events_before):].split(b"\n") if ln.strip()]
        self.assertEqual(len(new), 1, "UM evento")
        rec = json.loads(new[0].decode("utf-8"))
        self.assertEqual(rec["type"], "arvore.format")
        self.assertEqual(sorted(rec["data"]["paths"]), sorted(olds))
        for old, nw in rec["data"]["paths"].items():
            self.assertEqual(nw, old[:-1])
        puts = [op for op in rec["ops"] if op[0] == "tput"]
        board = hcore.load_board(self.root)
        self.assertEqual(sorted(op[1] for op in puts), sorted(board["tree"]), "tput de CADA item")
        self.assertTrue(all("tipo" in op[3] or "kind" in op[3] for op in puts))
        self.assertEqual(st(self.root, "validate")[0], 0, st(self.root, "validate")[1])
        self.assertEqual(hcore.read_chain(os.path.join(self.root, ".swarm", "events.jsonl"))[1], [])
        for rel in after:
            if rel.startswith(".engine/"):
                continue
            with open(os.path.join(self.root, ".swarm", rel), encoding="utf-8") as fh:
                d = json.loads(fh.read())
            self.assertIn("_generated_by", d, rel)
            self.assertNotIn("historico", d, rel)

    def test_idempotente_nada_a_migrar_e_nenhum_evento(self):
        st_ok(self.root, "migrate", "state-format")
        snap = _snap(self.root)
        code, out = st(self.root, "migrate", "state-format")
        self.assertEqual(code, 0, out)
        self.assertIn("nada a migrar", out)
        self.assertEqual(_snap(self.root), snap)
        code, out = st(self.root, "migrate", "state-format", "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertIn("nada a migrar", out)
        self.assertEqual(_snap(self.root), snap)

    def test_find_e_show_resolvem_caminho_antigo_json5(self):
        st_ok(self.root, "migrate", "state-format")
        with open(os.path.join(self.root, ".swarm", "events.jsonl"), encoding="utf-8") as fh:
            recs = [json.loads(ln) for ln in fh if ln.strip()]
        old = next(p for p in recs[-1]["data"]["paths"] if p.endswith("/epico.json5"))
        out = st_ok(self.root, "find", old)
        self.assertIn("EPC-001", out)
        out = st_ok(self.root, "find", ".swarm/" + old)
        self.assertIn("EPC-001", out)
        task_old = next(p for p in recs[-1]["data"]["paths"] if "/tasks/" in p)
        self.assertIn("# ", st_ok(self.root, "show", task_old))

    def test_motor_opera_depois_da_migracao(self):
        st_ok(self.root, "migrate", "state-format")
        st_ok(self.root, "new", "task", "--tipo", "CHORE", "--agent", "dev-billing", "--title", "Limpa", "--backlog",
              "--allowed-path", "src/billing/money.py", "--verify-cmd", VERIFY, "--motivo", "manutencao")
        self.assertEqual([p for p in _state_files(self.root) if p.endswith(".json5")], [])
        self.assertEqual(st(self.root, "validate")[0], 0, st(self.root, "validate")[1])

    def test_visoes_do_motor_selftest_tambem_viram_json(self):
        _w(self.root, ".swarm/.engine/selftest.json5", j5.dumps({"ok": True, "n": 1}, header="selftest"))
        code, out = st(self.root, "migrate", "state-format", "--dry-run")
        self.assertIn(".engine/selftest.json5 → .engine/selftest.json", out)
        st_ok(self.root, "migrate", "state-format")
        rt = os.path.join(self.root, ".swarm", ".engine")
        self.assertFalse(os.path.exists(os.path.join(rt, "selftest.json5")))
        with open(os.path.join(rt, "selftest.json"), encoding="utf-8") as fh:
            self.assertEqual(json.loads(fh.read())["ok"], True)
        self.assertEqual(st(self.root, "validate")[0], 0, st(self.root, "validate")[1])

    def test_nao_toca_memoria_nem_config(self):
        snap = _snap(self.root)
        st_ok(self.root, "migrate", "state-format")
        after = _snap(self.root)
        for k, v in snap.items():
            if "/memory/" in k or k.endswith("config.json5") or k.endswith("team.json5") or "/mandatos/" in k:
                self.assertEqual(after.get(k), v, k)


class TestMigrarFormatoSemAlvoAntigo(unittest.TestCase):
    def test_estado_novo_nada_a_migrar(self):
        root = fixture.make_repo(with_state=False)
        self.addCleanup(fixture.rm, root)
        st_ok(root, "init")
        st_ok(root, "new", "epico", "--title", "A", "--objetivo", "o")
        snap = _snap(root)
        code, out = st(root, "migrate", "state-format")
        self.assertEqual(code, 0, out)
        self.assertIn("nada a migrar", out)
        self.assertEqual(_snap(root), snap)

    def test_sem_arvore_recusa(self):
        root = fixture.make_repo(with_state=False)
        self.addCleanup(fixture.rm, root)
        code, out = st(root, "migrate", "state-format")
        self.assertNotEqual(code, 0)


class TestMigrarPlanoArvoreLevaMandatoJson(unittest.TestCase):
    """Item extra (a): o plano → árvore move também autonomy/selftest/autonomy-report já em `.json`."""

    def test_json_e_json5_sao_movidos(self):
        import autonomy
        root = fixture.make_repo(with_state=True, no_rules=True)
        self.addCleanup(fixture.rm, root)
        fixture.process(root, "pequena")
        autonomy.start(root, "lead", "FEAT-1", {"tasks": 5, "attempts": 2, "minutes": 60}, klass="pequena")
        sd = os.path.join(root, ".swarm", "state")
        self.assertTrue(os.path.isfile(os.path.join(sd, "autonomy.json")), os.listdir(sd))
        for name in ("selftest", "autonomy-report"):
            hcore.write_json(os.path.join(sd, name + ".json"), {"x": name}, "teste")
        code, out = st(root, "migrate", "state-tree")
        self.assertEqual(code, 0, out)
        rt = os.path.join(root, ".swarm", ".engine")
        for name in ("autonomy", "selftest", "autonomy-report"):
            self.assertTrue(os.path.isfile(os.path.join(rt, name + ".json")), name)
            self.assertFalse(os.path.exists(os.path.join(sd, name + ".json")), name)


class TestAmendHistoricoNormalizado(unittest.TestCase):
    """Item extra (b): o `after` do history é o que ficou gravado (normalizado) e amend sem mudança não registra."""

    def setUp(self):
        self.root = fixture.make_repo(with_state=False)
        self.addCleanup(fixture.rm, self.root)
        st_ok(self.root, "init")
        st_ok(self.root, "new", "task", "--tipo", "chore", "--agent", "dev-a", "--title", "Limpa", "--avulsa",
              "--allowed-path", "src/a.py", "--verify-cmd", "true", "--criterio", "AC-1|Dado a Quando b Então c|tests.t",
              "--motivo", "m")
        self.tid = st_ok(self.root, "find", "Limpa").split()[0]

    def item(self):
        rel = st_ok(self.root, "find", self.tid).strip().splitlines()[0].rsplit(" — ", 1)[1].strip()
        with open(os.path.join(self.root, rel), encoding="utf-8") as fh:
            return json.loads(fh.read())

    def amend(self, crit):
        st_ok(self.root, "amend", self.tid, "--field", "acceptance_criteria", "--after", json.dumps(crit), "--reason", "r")
        return self.item()

    def test_after_e_o_que_ficou_gravado_e_vira_o_before_do_proximo(self):
        d = self.amend([{"id": "AC-1", "criterion": "Dado x Quando y Então z", "verified_by": "reviewer"}])
        h = d["history"][-1]
        self.assertEqual(h["action"], "amend")
        self.assertEqual(h["after"], [{"id": "AC-1", "criterion": "Dado x Quando y Então z",
                                       "verified_by": "verification_command"}])
        self.assertEqual(d["acceptance_criteria"][0].get("test"), None)
        d2 = self.amend([{"id": "AC-1", "criterion": "Dado k Quando l Então m", "verified_by": "test:tests.t"}])
        self.assertEqual(d2["history"][-1]["before"], h["after"])

    def test_amend_que_nao_muda_nada_nao_registra(self):
        d = self.amend([{"id": "AC-1", "criterion": "Dado x Quando y Então z", "verified_by": "test:tests.t"}])
        n = len(d["history"])
        with open(os.path.join(self.root, ".swarm", "events.jsonl"), "rb") as fh:
            ev = fh.read()
        d2 = self.amend([{"id": "AC-1", "criterion": "Dado x Quando y Então z", "verified_by": "test:tests.t"}])
        self.assertEqual(len(d2["history"]), n)
        with open(os.path.join(self.root, ".swarm", "events.jsonl"), "rb") as fh:
            self.assertEqual(fh.read(), ev)
        st_ok(self.root, "amend", self.tid, "--field", "allowed_paths", "--after", '["src/b.py"]', "--reason", "r")
        with open(os.path.join(self.root, ".swarm", "events.jsonl"), "rb") as fh:
            ev = fh.read()
        st_ok(self.root, "amend", self.tid, "--field", "allowed_paths", "--after", '["src/b.py"]', "--reason", "r")
        with open(os.path.join(self.root, ".swarm", "events.jsonl"), "rb") as fh:
            self.assertEqual(fh.read(), ev)


if __name__ == "__main__":
    unittest.main()
