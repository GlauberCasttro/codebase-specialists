"""iter21 (frente memoria): caderno MEMORY.md gerado pelo cs-mem, check sem --files, ordem no empate, rastro da busca,
/correct --fault, supersede/retract, prévia (--dry-run).

Defeitos: D-0-02 (caderno), D-0-04 (check sem --files), D-0-05 (empate), D-0-07 (rastro), D-0-09 (--fault),
D-0-10 (supersede/retract). Fixture: repo sintético do harness (fixture.make_repo), pessoa = "Ana".
"""
import json
import os
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "harness", "tests"))
import fixture  # noqa: E402
import mem  # noqa: E402
import j5  # noqa: E402

MEM = os.path.join(os.path.dirname(HERE), "mem.py")
AG = "dev-billing"
OTHER = "dev-users"
START = "<!-- cs-mem:inicio (gerado pelo cs-mem; não edite este bloco) -->"
END = "<!-- cs-mem:fim -->"


def enable_claude(root):
    with open(os.path.join(root, ".swarm", "run.json5"), "w") as f:
        f.write(j5.dumps({"platforms": ["claude-code"]}))


def nb_path(root, agent=AG):
    return os.path.join(root, ".claude", "agent-memory", agent, "MEMORY.md")


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def readb(p):
    with open(p, "rb") as f:
        return f.read()


def block(root, agent=AG):
    txt = read(nb_path(root, agent))
    lines = txt.split("\n")
    s = next(i for i, l in enumerate(lines) if l.startswith("<!-- cs-mem:inicio"))
    e = next(i for i, l in enumerate(lines) if l.startswith("<!-- cs-mem:fim"))
    return s, e, "\n".join(lines[s:e + 1]), "\n".join(lines[e + 1:])


def cli(root, *args):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=root, PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, MEM] + list(args), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.returncode, p.stdout.decode("utf-8"), p.stderr.decode("utf-8")


def correct(root, right, agent=AG, wrong="somar float", why="arredondamento", paths=("src/billing/**",)):
    return mem.correct(root, agent, wrong, right, why, paths=list(paths))


class Base(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo()
        enable_claude(self.root)

    def tearDown(self):
        fixture.rm(self.root)


# ------------------------------------------------------------------------------------------- D-0-02 caderno
class TestCaderno(Base):
    def test_correct_gera_caderno_com_bloco_no_topo_e_secoes(self):
        l, _ = correct(self.root, "somar centavos inteiros marcador-c1")
        s, e, blk, after = block(self.root)
        self.assertEqual(read(nb_path(self.root)).split("\n")[0], START)
        self.assertLessEqual(s, 2)
        self.assertIn(END, blk)
        i1, i2, i3 = (blk.find("## Correções recebidas"), blk.find("## Armadilhas do território"),
                      blk.find("## Quando pesquisar no cs-mem"))
        self.assertTrue(0 < i1 < i2 < i3, blk)
        self.assertIn("marcador-c1", blk[i1:i2])
        self.assertIn(l["id"], blk[i1:i2], "correção com id")
        self.assertIn("arredondar centavos antes de somar quebra totais", blk[i2:i3], "armadilha do cartão")
        q = blk[i3:]
        self.assertIn("cs-mem search", q)
        self.assertIn("src/billing/**", q)
        self.assertIn("invoice total", q, "termo do glossário do território")
        self.assertIn('consultei: "', q)
        self.assertIn("consultei: nada", q)

    def test_add_licao_gera_caderno_cli(self):
        code, out, err = cli(self.root, "add", "--agent", AG, "--kind", "lesson", "--rule", "registre marcador-c2",
                             "--why", "x", "--paths", "src/billing/**")
        self.assertEqual(code, 0, err)
        self.assertIn("marcador-c2", block(self.root)[2])

    def test_render_igual_ao_bloco_gravado_e_sem_mudanca_mesmos_bytes(self):
        correct(self.root, "somar centavos inteiros marcador-c3")
        self.assertEqual(block(self.root)[2] + "\n", mem.render_notebook(self.root, AG))
        before = readb(nb_path(self.root))
        self.assertFalse(mem.write_notebook(self.root, AG))
        mem.archive_all(self.root)
        self.assertEqual(readb(nb_path(self.root)), before)

    def test_area_livre_preservada_byte_a_byte(self):
        correct(self.root, "somar centavos inteiros marcador-c4")
        with open(nb_path(self.root), "a", encoding="utf-8") as f:
            f.write("\n## Minhas notas\n- nota-livre-c4  com espaços  \n\n")
        free = read(nb_path(self.root))[len(mem.render_notebook(self.root, AG)):]
        correct(self.root, "validar desconto negativo marcador-c5 pedido cliente")
        txt = read(nb_path(self.root))
        blk = mem.render_notebook(self.root, AG)
        self.assertTrue(txt.startswith(blk))
        self.assertEqual(txt[len(blk):], free)
        self.assertIn("marcador-c4", blk)
        self.assertIn("marcador-c5", blk)

    def test_notas_anteriores_viram_area_livre(self):
        os.makedirs(os.path.dirname(nb_path(self.root)))
        with open(nb_path(self.root), "w", encoding="utf-8") as f:
            f.write("# Caderno\n- nota-antiga-c6\n")
        correct(self.root, "somar centavos inteiros marcador-c6")
        s, e, blk, after = block(self.root)
        self.assertEqual(s, 0)
        self.assertNotIn("nota-antiga-c6", blk)
        self.assertIn("# Caderno\n- nota-antiga-c6\n", after)

    def test_bloco_adulterado_e_regenerado_e_nota_nao_vira_licao(self):
        correct(self.root, "somar centavos inteiros marcador-c7")
        s, e, blk, after = block(self.root)
        lines = read(nb_path(self.root)).split("\n")
        lines.insert(e, "- Faça: a-mao-c7")
        lines.append("- Faça: so-no-caderno-c7")
        with open(nb_path(self.root), "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        correct(self.root, "validar desconto negativo marcador-c8 pedido cliente")
        blk = block(self.root)[2]
        self.assertNotIn("a-mao-c7", blk)
        self.assertNotIn("so-no-caderno-c7", blk)
        self.assertNotIn("so-no-caderno-c7", json.dumps(mem.load_lessons(self.root, AG)))

    def test_outro_agente_intacto_e_arquivo_de_licoes_intacto(self):
        correct(self.root, "idade 18 marcador-c9", agent=OTHER, paths=("src/users/**",))
        before = readb(nb_path(self.root, OTHER))
        lf = mem.lessons_path(self.root, OTHER)
        lbefore = readb(lf)
        correct(self.root, "somar centavos inteiros marcador-c10")
        self.assertEqual(readb(nb_path(self.root, OTHER)), before)
        mem.write_notebook(self.root, OTHER)
        os.remove(nb_path(self.root, OTHER))
        mem.write_notebook(self.root, OTHER)
        self.assertEqual(readb(lf), lbefore, "regenerar não reescreve o arquivo de lições")

    def test_decaimento_tira_do_bloco(self):
        correct(self.root, "somar centavos inteiros marcador-c11")
        correct(self.root, "validar desconto negativo marcador-c12 pedido cliente")
        ls = mem.load_lessons(self.root, AG)
        for l in ls:
            if "marcador-c11" in l["rule"]:
                l["first_seen"] = l["last_hit"] = "2020-01-01T00:00:00Z"
        mem.save_lessons(self.root, AG, ls)
        code, out, err = cli(self.root, "archive")
        self.assertEqual(code, 0, err)
        blk = block(self.root)[2]
        self.assertNotIn("marcador-c11", blk)
        self.assertIn("marcador-c12", blk)

    def test_sem_claude_code_nao_cria_caderno(self):
        os.remove(os.path.join(self.root, ".swarm", "run.json5"))
        with open(os.path.join(self.root, ".swarm", "run.json5"), "w") as f:
            f.write(j5.dumps({"platforms": ["cursor", "copilot", "codex"]}))
        correct(self.root, "somar centavos inteiros marcador-c13")
        self.assertFalse(os.path.exists(os.path.join(self.root, ".claude", "agent-memory")))

    def test_cartao_sem_memory_project_nao_cria_e_com_cria(self):
        os.remove(os.path.join(self.root, ".swarm", "run.json5"))
        os.makedirs(os.path.join(self.root, ".claude", "agents"))
        with open(os.path.join(self.root, ".claude", "agents", OTHER + ".md"), "w") as f:
            f.write("---\nname: dev-users\nmodel: inherit\n---\n# x\n")
        with open(os.path.join(self.root, ".claude", "agents", AG + ".md"), "w") as f:
            f.write("---\nname: dev-billing\nmemory: project\n---\n# x\n")
        correct(self.root, "idade 18 marcador-c14", agent=OTHER, paths=("src/users/**",))
        correct(self.root, "somar centavos inteiros marcador-c15")
        self.assertFalse(os.path.exists(nb_path(self.root, OTHER)))
        self.assertIn("marcador-c15", block(self.root)[2])

    def test_orcamento_200_linhas_25kb_mais_recente_presente(self):
        ls = []
        for i in range(60):
            ls.append({"id": "L-%s-%08d" % (AG, i), "rule": "regra %02d %s" % (i, "palavra " * 150), "why": "w " * 400,
                       "trigger": {"paths": ["src/billing/**"], "kinds": []}, "source": "human", "evidence": [],
                       "count": 1, "recurrences": 0, "first_seen": "2026-01-01T00:%02d:00Z" % i,
                       "last_hit": "2026-01-01T00:%02d:00Z" % i, "status": "active", "occurrences": []})
        mem.save_lessons(self.root, AG, ls)
        mem.write_notebook(self.root, AG)
        s, e, blk, after = block(self.root)
        self.assertLess(e, 200)
        self.assertLessEqual(len(blk.encode("utf-8")), 25 * 1024)
        self.assertIn("L-%s-%08d" % (AG, 59), blk, "a mais recente fica")
        self.assertNotIn("L-%s-%08d" % (AG, 0), blk, "a mais antiga sai primeiro")
        self.assertRegex(blk, r"\+\d+ .*fora")


# ------------------------------------------------------------------------------------------- D-0-04 / D-0-05 check
class TestCheck(Base):
    def test_check_sem_files_deriva_da_delegacao_ativa(self):
        correct(self.root, "somar centavos inteiros marcador-k1")
        fixture.dispatched(self.root)
        fixture.write(self.root, "src/billing/discount.py", "X = 2\n")
        code, out, err = cli(self.root, "check", "--agent", AG, "--no-run")
        self.assertIn("marcador-k1", out, out + err)
        files, why = mem.delegation_files(self.root, AG)
        self.assertEqual(files, ["src/billing/discount.py"])

    def test_check_sem_files_usa_submissao(self):
        correct(self.root, "somar centavos inteiros marcador-k2")
        fixture.dispatched(self.root)
        fixture.submit_ok(self.root)
        files, why = mem.delegation_files(self.root, AG)
        self.assertEqual(files, ["src/billing/discount.py"])
        self.assertIn("submiss", why)

    def test_check_sem_files_sem_delegacao_avisa(self):
        correct(self.root, "somar centavos inteiros marcador-k3")
        code, out, err = cli(self.root, "check", "--agent", AG, "--no-run")
        self.assertEqual(code, 0, err)
        self.assertIn("sem delegação ativa; passe --files", out + err)
        self.assertNotIn("marcador-k3", out)

    def test_board_projecao_json_chaves_pt(self):
        correct(self.root, "somar centavos inteiros marcador-k4")
        rt = os.path.join(self.root, ".swarm", ".engine")
        os.makedirs(rt)
        with open(os.path.join(self.root, ".swarm", "events.jsonl"), "w") as f:
            f.write("")
        with open(os.path.join(rt, "projection.json"), "w") as f:
            json.dump({"tarefas": [{"id": "T-9", "agente": AG, "caminhos_permitidos": ["src/billing/x.py"],
                                    "delegacoes": [{"id": "T-9.d1", "agente": AG, "estado": "DISPATCHED",
                                                    "despachada_em": "2026-01-01T00:00:00Z"}]}]}, f)
        files, why = mem.delegation_files(self.root, AG)
        self.assertEqual(files, ["src/billing/x.py"], why)

    def test_empate_de_count_mais_recente_primeiro(self):
        correct(self.root, "monte fixture compartilhada bandeja marcador-k5", wrong="errado-a", why="antiga")
        correct(self.root, "parametrize casos limite tabela marcador-k6", wrong="errado-b", why="nova")
        ls = mem.load_lessons(self.root, AG)
        self.assertEqual([l["count"] for l in ls], [1, 1])
        old, new = sorted(ls, key=lambda l: l["id"])   # a ANTIGA tem o menor id (o desempate por id a punha antes)
        old["first_seen"], new["first_seen"] = "2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z"
        mem.save_lessons(self.root, AG, ls)
        res = mem.check(self.root, AG, ["src/billing/total.py"], run=False)
        ids = [c["id"] for c in res["checklist"]]
        self.assertEqual(ids[:2], [new["id"], old["id"]], "no empate de count, a mais recente primeiro")


# ------------------------------------------------------------------------------------------- D-0-07 rastro
class TestRastro(Base):
    def trail(self):
        p = os.path.join(self.root, ".swarm", "state", "memory", "search.jsonl")
        return p, [json.loads(l) for l in read(p).splitlines()] if os.path.isfile(p) else []

    def test_search_registra_json_texto_zero_hits_append_only(self):
        correct(self.root, "somar centavos inteiros marcador-r1")
        code, out, err = cli(self.root, "search", "centavos marcador-r1", "--agent", AG, "--json", "--paths",
                             "src/billing/**", "--kind", "lesson")
        self.assertEqual(code, 0, err)
        res = json.loads(out)["results"]
        p, rows = self.trail()
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual((r["agent"], r["query"], r["hits"]), (AG, "centavos marcador-r1", len(res)))
        self.assertEqual(r["ids"], [x["id"] for x in res])
        self.assertEqual(r["kinds"], ["lesson"])
        self.assertEqual(r["paths"], ["src/billing/**"])
        self.assertIn("at", r)
        first = readb(p)
        code, out, err = cli(self.root, "search", "qzxwvk-r2")
        self.assertEqual(code, 0, err)
        self.assertTrue(readb(p).startswith(first))
        rows = self.trail()[1]
        self.assertEqual((rows[1]["agent"], rows[1]["hits"], rows[1]["ids"]), (None, 0, []))

    def test_busca_interna_do_motor_nao_polui_o_rastro(self):
        mem.search(self.root, "centavos")
        self.assertEqual(self.trail()[1], [])


# ------------------------------------------------------------------------------------------- D-0-09 --fault
class TestFault(Base):
    def test_fault_brief_vai_para_o_lead_sem_caderno(self):
        code, out, err = cli(self.root, "correct", "--agent", AG, "--fault", "brief", "--wrong", "x", "--right",
                             "pedir a chave marcador-f1", "--why", "y", "--paths", "src/billing/**")
        self.assertEqual(code, 0, err)
        lead = [l for l in mem.load_lessons(self.root, "lead") if "marcador-f1" in l["rule"]]
        self.assertEqual(lead[0]["source"], "brief")
        self.assertFalse([l for l in mem.load_lessons(self.root, AG) if "marcador-f1" in l["rule"]])
        self.assertFalse(os.path.exists(nb_path(self.root)))
        self.assertEqual(json.loads(out.strip().splitlines()[-1])["agent"], "lead")

    def test_fault_agent_e_padrao_vao_para_o_caderno(self):
        code, out, err = cli(self.root, "correct", "--agent", AG, "--fault", "agent", "--wrong", "x", "--right",
                             "pedir a chave marcador-f2", "--why", "y", "--paths", "src/billing/**")
        self.assertEqual(code, 0, err)
        self.assertIn("marcador-f2", block(self.root)[2])
        code, out, err = cli(self.root, "correct", "--agent", AG, "--wrong", "x", "--right",
                             "validar desconto negativo marcador-f3", "--why", "y", "--paths", "src/billing/**")
        self.assertEqual(code, 0, err)
        self.assertIn("marcador-f3", block(self.root)[2])


# ------------------------------------------------------------------------------------------- D-0-10 supersede/retract
class TestSupersede(Base):
    OLD = "use a chave do pré-requisito antiga-s1"
    NEW = "use a chave do pré-requisito e nomes em maiúsculas refinada-s1"

    def corr(self, right, *extra):
        code, out, err = cli(self.root, *(["correct", "--agent", AG, "--wrong", "fazer do jeito óbvio", "--right",
                                           right, "--why", "dono", "--paths", "src/billing/**"] + list(extra)))
        self.assertEqual(code, 0, out + err)
        return json.loads(out.strip().splitlines()[-1])["id"]

    def events(self):
        p = os.path.join(self.root, ".swarm", "state", "memory", "lesson-events.jsonl")
        return [json.loads(l) for l in read(p).splitlines()] if os.path.isfile(p) else []

    def assert_not_injected(self, oid, mark):
        self.assertNotIn(mark, json.dumps(mem.inject_lessons(self.root, AG, ["src/billing/total.py"], "chave")))
        self.assertNotIn(oid, [c["id"] for c in mem.check(self.root, AG, ["src/billing/total.py"], run=False)["checklist"]])
        self.assertNotIn(mark, block(self.root)[2])
        self.assertNotIn(oid, [r["id"] for r in mem.search(self.root, "chave pré-requisito %s" % mark, agent=AG)])

    def test_supersede(self):
        oid = self.corr(self.OLD)
        self.assertIn("antiga-s1", block(self.root)[2])
        nid = self.corr(self.NEW, "--supersedes", oid)
        self.assertNotEqual(nid, oid)
        st = {l["id"]: l for l in mem.load_lessons(self.root, AG)}
        self.assertEqual(st[oid]["status"], "superseded")
        self.assertEqual(st[oid]["superseded_by"], nid)
        self.assertEqual(st[nid]["status"], "active")
        self.assertEqual(st[nid]["count"], 1, "a refinada não é fundida na antiga pelo dedup")
        ev = self.events()
        self.assertEqual((ev[-1]["type"], ev[-1]["id"], ev[-1]["superseded_by"]), ("supersede", oid, nid))
        self.assert_not_injected(oid, "antiga-s1")
        self.assertIn("refinada-s1", block(self.root)[2])

    def test_supersede_id_inexistente_recusa_sem_gravar(self):
        code, out, err = cli(self.root, "correct", "--agent", AG, "--wrong", "x", "--right", "nova-s2", "--why", "y",
                             "--supersedes", "L-dev-billing-00000000")
        self.assertNotEqual(code, 0)
        self.assertFalse([l for l in mem.load_lessons(self.root, AG) if "nova-s2" in l["rule"]])

    def test_retract_com_e_sem_motivo(self):
        oid = self.corr(self.OLD)
        code, out, err = cli(self.root, "retract", oid)
        self.assertNotEqual(code, 0)
        self.assertIn("--reason", out + err)
        self.assertIn("motivo", out + err)
        self.assertEqual({l["id"]: l["status"] for l in mem.load_lessons(self.root, AG)}[oid], "active")
        code, out, err = cli(self.root, "retract", oid, "--reason", "regra errada motivo-s3")
        self.assertEqual(code, 0, err)
        st = {l["id"]: l for l in mem.load_lessons(self.root, AG)}[oid]
        self.assertEqual(st["status"], "retracted")
        self.assertEqual(st["retracted_reason"], "regra errada motivo-s3")
        ev = self.events()[-1]
        self.assertEqual((ev["type"], ev["id"], ev["reason"]), ("retract", oid, "regra errada motivo-s3"))
        self.assert_not_injected(oid, "antiga-s1")
        code, out, err = cli(self.root, "retract", oid, "--reason", "de novo")
        self.assertNotEqual(code, 0, "já retratada")

    def test_dry_run_mostra_e_nao_grava(self):
        code, out, err = cli(self.root, "correct", "--agent", AG, "--wrong", "errado-p", "--right", "previa-p",
                             "--why", "porque-p", "--dry-run")
        self.assertEqual(code, 0, err)
        for w in ("errado-p", "previa-p", "porque-p", AG, "fault"):
            self.assertIn(w, out)
        self.assertFalse(os.path.exists(mem.lessons_path(self.root, AG)))
        self.assertFalse(os.path.exists(nb_path(self.root)))


if __name__ == "__main__":
    unittest.main()
