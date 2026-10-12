"""iter21 (frente memoria, ciclo 2): achados do revisor isolado F1..F8.

F1 reincidência (lição promovida com proposta pendente continua no caderno, no inject e no check, com a contagem)
F2 retract/supersede descartam a proposta de promoção pendente
F3 check_notebook distingue desatualizado (selo íntegro) de adulterado; CLI `cs-mem notebook [--check]`
F4 CRLF no caderno não é adulteração
F5 BOM e marcador de fim apagado não duplicam o bloco; marcador cs-mem na área livre é acusado
F6 correct com --right diferente (mesmo wrong) substitui a lição antiga (supersede automático), não funde
F7 decaimento por nº de tasks lê a projeção do motor (árvore) e o board plano
F8 search imprime mesmo se o rastro falhar; correct --dry-run não move arquivos
Fixture: repo sintético do harness (fixture.make_repo), pessoa = "Ana".
"""
import json
import os
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "harness", "tests"))
import fixture  # noqa: E402
import mem  # noqa: E402
import j5  # noqa: E402

MEM = os.path.join(os.path.dirname(HERE), "mem.py")
AG = "dev-billing"
WRONG = "somar float no total da Ana"
WHY = "arredondamento quebra o fechamento"
RIGHT = "somar centavos inteiros no total"


def enable_claude(root):
    with open(os.path.join(root, ".swarm", "run.json5"), "w") as f:
        f.write(j5.dumps({"platforms": ["claude-code"]}))


def nb_path(root, agent=AG):
    return os.path.join(root, ".claude", "agent-memory", agent, "MEMORY.md")


def readb(p):
    with open(p, "rb") as f:
        return f.read()


def read(p):
    return readb(p).decode("utf-8")


def writeb(p, b):
    with open(p, "wb") as f:
        f.write(b)


def cli(root, *args):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=root, PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, MEM] + list(args), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.returncode, p.stdout.decode("utf-8"), p.stderr.decode("utf-8")


def promotions(root):
    p = mem.mem_paths(root)["promotions"]
    return (j5.load(p) or {}).get("promotions") or [] if os.path.isfile(p) else []


def kinds(problems):
    return sorted(set(p["kind"] for p in problems))


class Base(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo()
        enable_claude(self.root)

    def tearDown(self):
        fixture.rm(self.root)

    def corr(self, right=RIGHT, wrong=WRONG, why=WHY, ev=None):
        return mem.correct(self.root, AG, wrong, right, why, paths=["src/billing/**"], evidence=ev)

    def block(self):
        blk, _ = mem.split_notebook(read(nb_path(self.root)))
        return blk or ""


# ------------------------------------------------------------------------------------------- F1
class TestF1Reincidencia(Base):
    def test_corrigir_duas_vezes_mantem_licao_no_caderno_inject_e_check(self):
        l1, c1 = self.corr()
        self.assertTrue(c1)
        l2, c2 = self.corr()   # o agente repetiu o erro; o founder corrige DE NOVO, igual
        self.assertFalse(c2, "mesma correção = reincidência (soma), não lição nova")
        self.assertEqual(l2["id"], l1["id"])
        self.assertEqual(l2["count"], 2)
        self.assertEqual(l2["status"], "promoted")
        blk = self.block()
        self.assertIn(l1["id"], blk, "a lição reincidente continua no caderno")
        self.assertIn("reincidente ×2", blk)
        inj = mem.inject_lessons(self.root, AG, ["src/billing/total.py"], "total")
        self.assertIn(l1["id"], [l["id"] for l in inj], "continua no inject")
        self.assertEqual([l["count"] for l in inj if l["id"] == l1["id"]], [2])
        chk = mem.check(self.root, AG, ["src/billing/total.py"], run=False)
        self.assertIn(l1["id"], [c["id"] for c in chk["checklist"]], "continua no check")
        self.assertEqual([c.get("count") for c in chk["checklist"] if c["id"] == l1["id"]], [2])
        code, out, err = cli(self.root, "inject", "--agent", AG, "--paths", "src/billing/total.py")
        self.assertIn(l1["id"], out)
        self.assertIn("reincidente", out.lower())
        code, out, err = cli(self.root, "check", "--agent", AG, "--files", "src/billing/total.py", "--no-run")
        self.assertIn("reincidente ×2", out)

    def test_terceira_vez_conta_3_e_proposta_acompanha(self):
        l1, _ = self.corr()
        self.corr()
        l3, _ = self.corr()
        self.assertEqual(l3["count"], 3)
        self.assertIn("reincidente ×3", self.block())
        pr = [p for p in promotions(self.root) if p["lesson"] == l1["id"]]
        self.assertEqual(len(pr), 1)
        self.assertEqual(pr[0]["count"], 3)

    def test_aplicada_no_cartao_sai_do_caderno_controle(self):
        l1, _ = self.corr()
        self.corr()
        p = mem.mem_paths(self.root)["promotions"]
        data = j5.load(p)
        for it in data["promotions"]:
            it["applied"] = True
        writeb(p, j5.dumps(data).encode("utf-8"))
        mem.write_notebook(self.root, AG)
        self.assertNotIn(l1["id"], self.block(), "aplicada (virou regra do cartão): sai do caderno")
        self.assertEqual(mem.inject_lessons(self.root, AG, ["src/billing/total.py"], "total"), [])


# ------------------------------------------------------------------------------------------- F2
class TestF2PropostaDescartada(Base):
    def pending(self, lid):
        return [p for p in promotions(self.root) if p["lesson"] == lid and not p.get("applied")
                and not p.get("discarded")]

    def test_retract_de_promovida_descarta_a_proposta(self):
        l1, _ = self.corr()
        self.corr()
        self.assertTrue(self.pending(l1["id"]))
        mem.retract(self.root, l1["id"], "regra errada da Ana")
        self.assertEqual(self.pending(l1["id"]), [], "proposta de lição retratada não pode ficar aplicável")
        it = [p for p in promotions(self.root) if p["lesson"] == l1["id"]][0]
        self.assertTrue(it["discarded"])
        self.assertIn("regra errada", it["discarded_reason"])

    def test_supersede_de_promovida_descarta_a_proposta(self):
        l1, _ = self.corr()
        self.corr()
        l2, _ = mem.correct(self.root, AG, WRONG, "somar centavos inteiros e arredondar no fim", WHY,
                            paths=["src/billing/**"], supersedes=l1["id"])
        self.assertEqual(self.pending(l1["id"]), [])
        st = {l["id"]: l["status"] for l in mem.load_lessons(self.root, AG)}
        self.assertEqual(st[l1["id"]], "superseded")


# ------------------------------------------------------------------------------------------- F3
class TestF3DesatualizadoXAdulterado(Base):
    def test_team_mudou_e_desatualizado_nao_adulterado(self):
        self.corr()
        self.assertEqual(mem.check_notebook(self.root, AG), [])
        tp = os.path.join(self.root, ".swarm", "team.json5")
        team = j5.load(tp)
        team["agents"][0]["card"]["footguns"].append({"text": "nova armadilha do cartão"})
        writeb(tp, j5.dumps(team).encode("utf-8"))
        det = mem.check_notebook_detail(self.root, AG)
        self.assertEqual(kinds(det), ["stale"], det)
        msgs = mem.check_notebook(self.root, AG)
        self.assertEqual(len(msgs), 1)
        self.assertIsInstance(msgs[0], str)
        self.assertNotIn("adulterado", msgs[0])
        self.assertIn("cs-mem notebook", msgs[0])
        code, out, err = cli(self.root, "notebook", "--agent", AG, "--check")
        self.assertEqual(code, 0, "desatualizado é aviso:\n" + out + err)
        self.assertIn("desatualizado", out + err)
        code, out, err = cli(self.root, "notebook", "--agent", AG)
        self.assertEqual(code, 0, err)
        self.assertEqual(mem.check_notebook_detail(self.root, AG), [])
        self.assertIn("nova armadilha do cartão", self.block())

    def test_glossario_mudou_e_desatualizado(self):
        self.corr()
        gp = os.path.join(self.root, ".swarm", "facts", "glossary.json5")
        g = j5.load(gp)
        g.append({"id": "term.desconto", "term": "discountRate", "canonical": "taxa de desconto",
                  "scope": ["src/billing/**"], "evidence": [{"file": "src/billing/total.py", "line": 1}]})
        writeb(gp, j5.dumps(g).encode("utf-8"))
        self.assertEqual(kinds(mem.check_notebook_detail(self.root, AG)), ["stale"])

    def test_editar_bloco_a_mao_e_adulterado(self):
        l1, _ = self.corr()
        p = nb_path(self.root)
        writeb(p, read(p).replace("somar centavos inteiros", "somar float mesmo", 1).encode("utf-8"))
        det = mem.check_notebook_detail(self.root, AG)
        self.assertEqual(kinds(det), ["tampered"], det)
        code, out, err = cli(self.root, "notebook", "--agent", AG, "--check")
        self.assertEqual(code, 1, out + err)
        self.assertIn("adulterado", out + err)
        mem.write_notebook(self.root, AG)
        self.assertEqual(mem.check_notebook(self.root, AG), [], "regenerar ⇒ []")

    def test_cli_notebook_sem_agent_regenera_todos(self):
        self.corr()
        os.remove(nb_path(self.root))
        code, out, err = cli(self.root, "notebook")
        self.assertEqual(code, 0, err)
        self.assertTrue(os.path.isfile(nb_path(self.root)))
        code, out, err = cli(self.root, "notebook", "--check", "--json")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(json.loads(out)[AG], [])


# ------------------------------------------------------------------------------------------- F4
class TestF4CRLF(Base):
    def test_caderno_crlf_nao_e_adulterado_e_regenerar_preserva_crlf(self):
        self.corr()
        p = nb_path(self.root)
        writeb(p, read(p).encode("utf-8") + b"\n## Notas\n- nota da Ana\n")
        crlf = readb(p).replace(b"\n", b"\r\n")
        writeb(p, crlf)
        self.assertEqual(mem.check_notebook(self.root, AG), [], "CRLF (autocrlf/Windows) não é adulteração")
        self.assertFalse(mem.write_notebook(self.root, AG), "nada mudou: mesmos bytes")
        self.assertEqual(readb(p), crlf)
        self.corr(right="validar desconto negativo marcador-crlf pedido cliente", wrong="aceitar negativo", why="x")
        b = readb(p)
        self.assertIn(b"marcador-crlf", b)
        self.assertNotIn(b"\n", b.replace(b"\r\n", b""), "estilo CRLF preservado em todo o arquivo")
        self.assertIn(b"- nota da Ana\r\n", b)
        self.assertEqual(mem.check_notebook(self.root, AG), [])


# ------------------------------------------------------------------------------------------- F5
class TestF5BomEMarcadorOrfao(Base):
    def count_start(self):
        return read(nb_path(self.root)).count("cs-mem:inicio")

    def test_bom_nao_duplica_o_bloco(self):
        l1, _ = self.corr()
        p = nb_path(self.root)
        writeb(p, b"\xef\xbb\xbf" + readb(p) + b"\n- nota bom\n")
        self.assertEqual(mem.check_notebook(self.root, AG), [], "BOM não é adulteração")
        mem.retract(self.root, l1["id"], "errada")
        self.assertEqual(self.count_start(), 1, read(p))
        self.assertNotIn(l1["id"], read(p), "a retratada some (não fica num bloco velho na área livre)")
        self.assertIn("- nota bom", read(p))
        self.assertFalse(readb(p).startswith(b"\xef\xbb\xbf"))

    def test_marcador_de_fim_apagado_nao_duplica(self):
        l1, _ = self.corr()
        p = nb_path(self.root)
        txt = read(p).replace(mem.NOTEBOOK_END + "\n", "", 1) + "\n- nota orfa\n"
        writeb(p, txt.encode("utf-8"))
        self.assertNotEqual(mem.check_notebook(self.root, AG), [])
        mem.retract(self.root, l1["id"], "errada")
        t = read(p)
        self.assertEqual(t.count("cs-mem:inicio"), 1, t)
        self.assertNotIn(l1["id"], t, "bloco velho (órfão) não sobra na área livre")
        self.assertIn("- nota orfa", t)

    def test_marcador_na_area_livre_e_duplicate(self):
        self.corr()
        p = nb_path(self.root)
        writeb(p, readb(p) + b"\n" + mem.render_notebook(self.root, AG).encode("utf-8"))
        det = mem.check_notebook_detail(self.root, AG)
        self.assertIn("duplicate", kinds(det), det)
        mem.write_notebook(self.root, AG)
        self.assertEqual(self.count_start(), 1)
        self.assertEqual(mem.check_notebook(self.root, AG), [])


# ------------------------------------------------------------------------------------------- F6
class TestF6RightDiferente(Base):
    def events(self):
        p = mem.lesson_events_path(self.root)
        return [json.loads(x) for x in read(p).splitlines()] if os.path.isfile(p) else []

    def test_right_diferente_substitui_e_guarda_historico(self):
        l1, _ = self.corr(right="somar centavos inteiros no total da fatura")
        l2, created = self.corr(right="somar centavos inteiros no total com Decimal")
        self.assertTrue(created, "o texto novo do founder vira lição (não é fundido)")
        self.assertNotEqual(l2["id"], l1["id"])
        self.assertIn("Decimal", l2["rule"])
        self.assertEqual(l2.get("supersedes"), l1["id"])
        st = {l["id"]: l for l in mem.load_lessons(self.root, AG)}
        self.assertEqual(st[l1["id"]]["status"], "superseded")
        # ciclo 3 (M14.5): a reincidência é do ERRO; a nova herda count da substituída + 1 (antes: "não somou", count 1)
        self.assertEqual(st[l1["id"]]["count"], 1)
        self.assertEqual(st[l2["id"]]["count"], 2, "herdou a contagem do mesmo erro")
        ev = self.events()[-1]
        self.assertEqual((ev["type"], ev["id"], ev["superseded_by"], ev.get("auto")), ("supersede", l1["id"], l2["id"], True))
        blk = self.block()
        self.assertIn("Decimal", blk)
        self.assertNotIn(l1["id"] + "]", blk)

    def test_m14_5_reincidencia_sobrevive_ao_right_reescrito(self):
        wrong = "somar o imposto por item"
        for r in ("somar o imposto no total r1x", "somar o imposto no total da fatura r2x",
                  "somar o imposto no total da fatura sempre r3x"):
            l, _ = self.corr(right=r, wrong=wrong)
        self.assertEqual((l["count"], l["recurrences"]), (3, 2))
        blk = self.block()
        self.assertIn("r3x", blk)
        self.assertNotIn("r1x", blk)
        self.assertNotIn("r2x", blk)
        self.assertTrue(any("r3x" in ln and "reincidente ×3" in ln for ln in blk.split("\n")), blk)

    def test_mesmo_right_soma_controle(self):
        l1, _ = self.corr()
        l2, created = self.corr()
        self.assertFalse(created)
        self.assertEqual(l2["count"], 2)


# ------------------------------------------------------------------------------------------- F7
class TestF7Decaimento(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(fixture.tempfile.mkdtemp(prefix="cs-mem-f7-"))
        os.makedirs(os.path.join(self.root, ".swarm", "state"))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def board(self):
        return {"tasks": [{"id": "T-%d" % i, "agent": AG, "delegations": [
            {"id": "T-%d.d1" % i, "agent": AG, "state": "ACCEPTED", "dispatched_at": "2026-05-01T00:%02d:00Z" % i}]}
            for i in range(mem.DECAY_TASKS)]}

    def lesson(self):
        mem.add_lesson(self.root, AG, "regra que não disparou", "x", ["src/billing/**"], source="human")
        ls = mem.load_lessons(self.root, AG)
        for l in ls:
            l["first_seen"] = l["last_hit"] = "2026-04-30T00:00:00Z"
        mem.save_lessons(self.root, AG, ls)
        return ls

    def run_decay(self):
        ls = mem.load_lessons(self.root, AG)
        mem.decay_and_cap(self.root, AG, ls, now="2026-05-02T00:00:00Z")
        return ls[0]["status"]

    def test_modo_arvore(self):
        self.lesson()
        with open(os.path.join(self.root, ".swarm", "events.jsonl"), "w") as f:
            f.write("")
        os.makedirs(os.path.join(self.root, ".swarm", ".engine"))
        with open(os.path.join(self.root, ".swarm", ".engine", "projection.json5"), "w") as f:
            f.write(j5.dumps(self.board()))
        self.assertEqual(mem._tasks_since(self.root, AG, "2026-04-30T00:00:00Z"), mem.DECAY_TASKS)
        self.assertEqual(self.run_decay(), "archived")

    def test_modo_plano_continua(self):
        self.lesson()
        with open(os.path.join(self.root, ".swarm", "state", "board.json5"), "w") as f:
            f.write(j5.dumps(self.board()))
        self.assertEqual(self.run_decay(), "archived")


# ------------------------------------------------------------------------------------------- F8
class TestF8SemEfeitoColateral(Base):
    def test_search_imprime_mesmo_com_rastro_quebrado(self):
        self.corr(right="somar centavos inteiros marcador-f8")
        os.makedirs(mem.search_trail_path(self.root))  # rastro vira diretório: OSError ao gravar
        code, out, err = cli(self.root, "search", "centavos marcador-f8", "--agent", AG)
        self.assertEqual(code, 0, out + err)
        self.assertIn("marcador-f8", out)
        self.assertIn("rastro", err)
        code, out, err = cli(self.root, "search", "centavos marcador-f8", "--json")
        self.assertEqual(code, 0, out + err)
        self.assertTrue(json.loads(out)["results"])

    def test_dry_run_nao_move_agentes_antigos(self):
        old = os.path.join(self.root, ".swarm", "memory", "agents")
        os.makedirs(old)
        with open(os.path.join(old, AG + ".json5"), "w") as f:
            f.write(j5.dumps({"agent": AG, "lessons": []}))
        code, out, err = cli(self.root, "correct", "--agent", AG, "--wrong", "x", "--right", "y-f8", "--why", "z",
                             "--dry-run", "--supersedes", "L-dev-billing-00000000")
        self.assertEqual(code, 0, err)
        self.assertTrue(os.path.isfile(os.path.join(old, AG + ".json5")), "dry-run não pode mover arquivos")
        self.assertFalse(os.path.exists(mem.lessons_path(self.root, AG)))

    def test_dry_run_avisa_reincidencia_e_substituicao(self):
        l1, _ = self.corr()
        pv = mem.correct_preview(self.root, AG, WRONG, RIGHT, WHY, paths=["src/billing/**"])
        self.assertEqual(pv.get("would"), "recurrence")
        self.assertEqual(pv.get("existing"), l1["id"])
        pv = mem.correct_preview(self.root, AG, WRONG, "somar centavos inteiros no total com Decimal", WHY,
                                 paths=["src/billing/**"])
        self.assertEqual(pv.get("would"), "supersede")
        self.assertEqual(pv.get("existing"), l1["id"])


if __name__ == "__main__":
    unittest.main()
