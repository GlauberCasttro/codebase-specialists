"""ORÁCULO iter9 (acréscimo do founder) — o guia de uso (MODO-DE-USO.md) e o SKILL.md entram no checador de doctests
e falam da pasta `.swarm/`, do harness único (`--replace-harness`) e do `upgrade` do legado.

(1) Cobertura: `test_commands_parse.doc_files()` inclui MODO-DE-USO.md e SKILL.md, e todo comando/subcomando/flag de
    `cs.py` e `cs-*` citado neles parseia contra o argparse real (mesmo pipeline: doc_texts → occurrences →
    check_occurrence). Prova de efeito (L03): numa CÓPIA temporária da skill, planta-se uma flag inexistente no
    MODO-DE-USO.md e roda-se o checador de verdade (subprocesso); ele tem de reprovar citando a flag. Controle: a
    mesma cópia sem a planta não cita a flag.
(2) Conteúdo: o nome legado só aparece dentro de uma seção (título markdown) de migração/legado; os dois arquivos
    citam `.swarm/`, `--replace-harness` e o `upgrade` do legado (dentro dessa seção).

Contrato: quem implementa não edita este arquivo. O nome legado é montado em tempo de execução (o teste de
constante única do oráculo iter9 reprova o literal fora da allowlist).
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(os.path.dirname(HERE))
SKILL = os.path.dirname(SCRIPTS)
for _p in (SCRIPTS, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import test_commands_parse as TCP  # noqa: E402

GUIDES = ("MODO-DE-USO.md", "SKILL.md")
LEGACY_RE = re.compile(r"(?<![A-Za-z0-9_])\." + "specialists" + r"(?![A-Za-z0-9_])")
SECTION_OK_RE = re.compile(r"migra|legad", re.I)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
PLANTED_FLAG = "--flag-inexistente-l03"
PLANTED_LINE = "\n\nExemplo: `cs.py harness install %s`\n" % PLANTED_FLAG


def read(name):
    with open(os.path.join(SKILL, name), encoding="utf-8") as fh:
        return fh.read()


def sections(text):
    """[(nº da linha, linha, [títulos ancestrais])] — fora de blocos ``` os títulos abrem/fecham seções."""
    out, stack, fence = [], [], False
    for n, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            fence = not fence
        m = None if fence else HEADING_RE.match(line)
        if m:
            lvl = len(m.group(1))
            stack = [(l, t) for l, t in stack if l < lvl] + [(lvl, m.group(2))]
        out.append((n, line, [t for _, t in stack]))
    return out


def legacy_section_text(text):
    return "\n".join(line for _, line, heads in sections(text) if any(SECTION_OK_RE.search(h) for h in heads))


class GuiaNoChecador(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parsers = TCP.load_parsers()

    def test_doc_files_inclui_modo_de_uso_e_skill(self):
        files = set(os.path.realpath(p) for p in TCP.doc_files())
        for g in GUIDES:
            self.assertIn(os.path.realpath(os.path.join(SKILL, g)), files,
                          "%s fora de test_commands_parse.doc_files()" % g)

    def test_comandos_citados_nos_guias_parseiam(self):
        errs, oks = [], 0
        for g in GUIDES:
            for label, text, is_code in TCP.doc_texts(os.path.join(SKILL, g)):
                for lab, prog, toks, in_code, shown in TCP.occurrences(label, text, is_code):
                    st, msg, _ = TCP.check_occurrence(self.parsers, prog, toks, in_code)
                    if st == "erro":
                        errs.append("%s: %s → %s" % (lab, shown.strip()[:120], msg))
                    elif st == "ok":
                        oks += 1
        self.assertGreater(oks, 10, "o extrator deveria achar comandos nos guias; achou %d" % oks)
        self.assertEqual(errs, [], "comandos dos guias que a CLI real não aceita:\n  " + "\n  ".join(errs))

    def test_pipeline_reprova_flag_plantada(self):
        """Sanidade (independe da cobertura): a linha plantada reprova no pipeline do checador."""
        hits = []
        for lab, prog, toks, in_code, shown in TCP.occurrences("planta", PLANTED_LINE.strip(), None):
            hits.append(TCP.check_occurrence(self.parsers, prog, toks, in_code)[0])
        self.assertEqual(hits, ["erro"])


def _copy_skill(dst):
    shutil.copytree(SKILL, dst, symlinks=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "fixtures", "iteration-*"))


def _run_checker(skill_copy):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("CLAUDE_PROJECT_DIR", None)
    p = subprocess.run([sys.executable, "-m", "unittest", "-v",
                        "scripts.doctests.tests.test_commands_parse.CommandsParseTest.test_every_cited_command_parses"],
                       cwd=skill_copy, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
    return p.returncode, p.stdout.decode("utf-8", "replace") + p.stderr.decode("utf-8", "replace")


class ProvaDeEfeitoL03(unittest.TestCase):
    def test_checador_reprova_flag_inexistente_plantada_no_modo_de_uso(self):
        tmp = tempfile.mkdtemp(prefix="cs-guia-")
        self.addCleanup(shutil.rmtree, tmp, True)
        copy = os.path.join(tmp, "codebase-specialists")
        _copy_skill(copy)
        rc0, out0 = _run_checker(copy)
        self.assertNotIn(PLANTED_FLAG, out0, "controle: a cópia sem planta não pode citar a flag")
        with open(os.path.join(copy, "MODO-DE-USO.md"), "a", encoding="utf-8") as fh:
            fh.write(PLANTED_LINE)
        rc, out = _run_checker(copy)
        self.assertNotEqual(rc, 0, "o checador NÃO reprovou a flag plantada no MODO-DE-USO.md:\n" + out[-1500:])
        self.assertIn(PLANTED_FLAG, out, "reprovou, mas não pela flag plantada:\n" + out[-1500:])
        self.assertIn("MODO-DE-USO.md", out)


class GuiaConteudoSwarm(unittest.TestCase):
    def test_nome_legado_so_em_secao_de_migracao(self):
        for g in GUIDES:
            with self.subTest(arquivo=g):
                fora = ["%s:%d: %s" % (g, n, line.strip()[:120]) for n, line, heads in sections(read(g))
                        if LEGACY_RE.search(line) and not any(SECTION_OK_RE.search(h) for h in heads)]
                self.assertEqual(fora, [], "nome legado fora de seção de migração/legado:\n  " + "\n  ".join(fora))

    def test_citam_swarm_replace_harness_e_upgrade_do_legado(self):
        for g in GUIDES:
            with self.subTest(arquivo=g):
                txt = read(g)
                self.assertTrue(".swarm/" in txt, "%s não cita .swarm/" % g)
                self.assertTrue("--replace-harness" in txt, "%s não explica a substituição de outro harness "
                                "(--replace-harness)" % g)
                sec = legacy_section_text(txt)
                self.assertTrue(sec.strip(), "%s sem seção de migração/legado (título com 'migra' ou 'legado')" % g)
                self.assertRegex(sec, r"upgrade", "%s: a seção de migração/legado não cita o `upgrade`" % g)
                self.assertRegex(sec, LEGACY_RE.pattern, "%s: a seção de migração não nomeia a pasta legada" % g)

    def test_secoes_detectadas(self):
        """Sanidade do detector de seção (passa sempre)."""
        doc = "# A\nx .%s/\n## Migração do legado\ny .%s/\n```\n# não é título\n```\nz\n# B\nw\n" % (
            "specialists", "specialists")
        bad = [n for n, line, heads in sections(doc)
               if LEGACY_RE.search(line) and not any(SECTION_OK_RE.search(h) for h in heads)]
        self.assertEqual(bad, [2])
        self.assertIn("z", legacy_section_text(doc))
        self.assertNotIn("w", legacy_section_text(doc))


if __name__ == "__main__":
    unittest.main()
