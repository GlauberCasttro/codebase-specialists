"""Iteração 21 (memória dos agentes) — o que o produto EMITE ensina o ciclo: quem errou (--fault), prévia e
confirmação antes de gravar, supersede/retract, caderno MEMORY.md e a linha `consultei:`."""
import os
import re
import shutil
import sys
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import fixture  # noqa: E402
from test_emit import run  # noqa: E402

SKILL = Path(HERE).parents[2]


class Emitido(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo()
        self.addCleanup(shutil.rmtree, self.root, True)
        code, out, err = run("--target", self.root, "--platforms", "claude-code", "--allow-outside")
        self.assertEqual(code, 0, out + err)

    def correct_skill(self):
        return (Path(self.root) / ".claude" / "skills" / "correct" / "SKILL.md").read_text(encoding="utf-8")

    def card(self):
        d = Path(self.root) / ".claude" / "agents"
        return "\n".join(p.read_text(encoding="utf-8") for p in sorted(d.glob("*.md")))


class CorrectSkill(Emitido):
    def test_pergunta_quem_errou(self):
        txt = self.correct_skill()
        self.assertIn("--fault", txt)
        self.assertIn("brief", txt)
        self.assertIn("agent", txt)

    @staticmethod
    def comandos(body):
        cmds = re.findall(r"`(\.swarm/bin/cs-mem correct[^`]*)`", body)
        return [c for c in cmds if "--dry-run" in c], [c for c in cmds if "--dry-run" not in c]

    def test_mostra_e_confirma_antes_de_gravar(self):
        body = self.correct_skill().split("---", 2)[-1].lower()
        i_cmd = body.find("cs-mem correct")
        self.assertGreaterEqual(body.find("confirm"), 0)
        for w in ("errado", "certo", "porquê"):
            self.assertIn(w, body[:i_cmd])
        # ordem real: prévia --dry-run -> pedido de confirmação/PARE -> comando de gravação
        preview, write = self.comandos(body)
        self.assertTrue(preview and write)
        i_prev = body.find(preview[0])
        i_conf = body.find("confirmação explícita", i_prev)
        i_pare = body.find("pare", i_prev)
        i_write = body.rfind(write[-1])  # rfind: o comando gravado é prefixo da prévia
        self.assertLess(i_prev, i_conf)
        self.assertLess(i_conf, i_write)
        self.assertLess(i_pare, i_write)
        self.assertLess(i_prev, body.find("só depois de confirmado"))

    def test_previa_inclui_supersedes(self):
        body = self.correct_skill().split("---", 2)[-1].lower()
        preview, write = self.comandos(body)
        self.assertTrue(preview and write)
        for l in preview + write:
            self.assertIn("--supersedes", l, "a flag aparece na prévia e no comando gravado")
        self.assertLess(body.find("--supersedes"), body.find("--dry-run"),
                        "supersedes é decidido antes da prévia")

    def test_retract_exige_confirmacao_propria(self):
        body = self.correct_skill().split("---", 2)[-1].lower()
        i_ret = body.find("cs-mem retract <id>")
        self.assertGreaterEqual(i_ret, 0)
        before = body[max(0, i_ret - 500):i_ret]
        self.assertIn("confirmação explícita", before)
        self.assertIn("pare", before)
        self.assertIn("id e texto", before)

    def test_supersede_e_retract_documentados(self):
        txt = self.correct_skill()
        self.assertIn("--supersedes", txt)
        self.assertIn("cs-mem retract", txt)
        self.assertIn("--reason", txt)
        front = txt.split("---", 2)[1]
        self.assertIn("cs-mem retract", front, "allowed-tools libera o retract")


class CartaoEnsinaConsultei(Emitido):
    def test_cartao_ensina_formato_consultei(self):
        card = self.card()
        self.assertIn('consultei: "<consulta>" -> <ID> (<efeito>)', card)
        self.assertIn("consultei: nada", card)


class DocsCaderno(unittest.TestCase):
    def test_marcador_do_caderno_documentado(self):
        txt = (SKILL / "docs" / "03-memoria-e-licoes.md").read_text(encoding="utf-8")
        self.assertIn("<!-- cs-mem:inicio", txt)
        self.assertIn("<!-- cs-mem:fim -->", txt)
        self.assertIn("MEMORY.md", txt)
        for s in ("Correções recebidas", "Armadilhas do território", "Quando pesquisar no cs-mem"):
            self.assertIn(s, txt)

    def test_versao_e_catalogo(self):
        v = (SKILL / "VERSION").read_text(encoding="utf-8").strip()
        # B-32: teste nunca fixa versao; exige que a 0.12.0 exista (>=) e que a migracao dela esteja no catalogo.
        self.assertGreaterEqual(tuple(int(x) for x in v.split(".")), (0, 12, 0))
        cat = (SKILL / "references" / "migrations.json5").read_text(encoding="utf-8")
        self.assertRegex(cat, r'to:\s*"0\.12\.0"')
        self.assertIn('version: "%s"' % v, cat)


if __name__ == "__main__":
    unittest.main()
