"""Testes do emissor: idempotência, preservação de conteúdo humano, validação por formato (G7),
gate sem escrita, orçamento por camada, conflito, poda, JSON5.

Rodar: python3 -m unittest discover -s scripts/emit/tests -t scripts
"""
import contextlib
import hashlib
import io
import os
import shutil
import sys
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(os.path.dirname(HERE))
for p in (SCRIPTS, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import fixture  # noqa: E402
from emit import cli, j5  # noqa: E402
from emit.common import BEGIN, END, expand_braces, merge_block, parse_frontmatter  # noqa: E402

ALL = "claude-code,cursor,copilot,codex"


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


def snapshot(root):
    snap = {}
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != "backups"]
        for f in files:
            p = os.path.join(base, f)
            snap[os.path.relpath(p, root)] = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    return snap


class Base(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def emit(self, *extra):
        return run("--target", self.root, "--platforms", ALL, "--allow-outside", *extra)

    def validate(self):
        return run("validate", "--target", self.root, "--platforms", ALL)

    def p(self, rel):
        return Path(self.root) / rel

    def edit(self, rel, old, new):
        path = self.p(rel)
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text, "fixture mudou: %r não está em %s" % (old, rel))
        path.write_text(text.replace(old, new, 1), encoding="utf-8")


class TestIdempotence(Base):
    def test_two_runs_same_bytes(self):
        code, out, err = self.emit()
        self.assertEqual(code, 0, err)
        first = snapshot(self.root)
        code, out, err = self.emit()
        self.assertEqual(code, 0, err)
        self.assertEqual(first, snapshot(self.root))
        self.assertIn("resumo: unchanged=", out)
        self.assertNotIn("update", out.split("resumo:")[1])

    def test_dry_run_writes_nothing(self):
        before = snapshot(self.root)
        code, out, _ = self.emit("--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("create", out)
        self.assertEqual(before, snapshot(self.root))


class TestHumanContent(Base):
    HUMAN_TOP = "# Projeto\n\nRegra humana: nunca rode migrações em produção sem ticket.\n"
    HUMAN_BOTTOM = "\n## Rodapé humano\n\nContato: time-pagamentos.\n"

    def test_block_appended_and_human_preserved(self):
        self.p("CLAUDE.md").write_text(self.HUMAN_TOP, encoding="utf-8")
        code, out, err = self.emit()
        self.assertEqual(code, 0, err)
        text = self.p("CLAUDE.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith(self.HUMAN_TOP))
        self.assertEqual(text.count(BEGIN), 1)
        self.assertIn("append-block", out)
        backups = list((self.p(".swarm/emit/backups")).rglob("CLAUDE.md.*.bak"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), self.HUMAN_TOP)
        self.assertTrue(Path(str(backups[0])[:-4] + ".diff").is_file())

    def test_only_block_changes_on_reemit(self):
        self.emit()
        path = self.p("AGENTS.md")
        path.write_text("Humano antes\n" + path.read_text(encoding="utf-8") + self.HUMAN_BOTTOM, encoding="utf-8")
        team = fixture.team()
        team["core"]["lines"].append({"text": "Build: `make build` (exit 0)", "facts": ["ops.build"]})
        fixture.write_team(self.root, team)
        code, out, err = self.emit()
        self.assertEqual(code, 0, err)
        text = path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("Humano antes\n"))
        self.assertTrue(text.endswith(self.HUMAN_BOTTOM))
        self.assertIn("make build", text[text.index(BEGIN):text.index(END)])

    def test_owned_path_with_human_file_is_conflict(self):
        human = "meu agente escrito à mão\n"
        self.p(".claude/agents").mkdir(parents=True)
        self.p(".claude/agents/dev-billing.md").write_text(human, encoding="utf-8")
        code, out, err = self.emit()
        self.assertEqual(code, 3)
        self.assertEqual(self.p(".claude/agents/dev-billing.md").read_text(encoding="utf-8"), human)
        self.assertFalse(self.p("CLAUDE.md").exists(), "conflito deve impedir toda escrita")
        self.assertTrue(self.p(".swarm/emit/conflicts/.claude/agents/dev-billing.md.proposed").is_file())
        code, out, err = self.emit("--force")
        self.assertEqual(code, 0, err)
        self.assertIn("codebase-specialists:generated", self.p(".claude/agents/dev-billing.md").read_text())
        self.assertTrue(list(self.p(".swarm/emit/backups").rglob("dev-billing.md.*.bak")))

    def test_malformed_markers_conflict(self):
        self.p("CLAUDE.md").write_text("x\n%s\nmeio\n" % BEGIN, encoding="utf-8")
        code, _, _ = self.emit()
        self.assertEqual(code, 3)

    def test_merge_block_unit(self):
        a = merge_block("topo\n", "um")
        b = merge_block(a + "fim\n", "dois")
        self.assertEqual(b, "topo\n\n%s\ndois\n%s\nfim\n" % (BEGIN, END))


class TestValidator(Base):
    def setUp(self):
        super(TestValidator, self).setUp()
        code, _, err = self.emit()
        self.assertEqual(code, 0, err)

    def assertFails(self, needle):
        code, out, err = self.validate()
        self.assertEqual(code, 1, "validador deveria falhar")
        self.assertIn(needle, err)

    def test_clean_passes(self):
        code, out, err = self.validate()
        self.assertEqual(code, 0, err)
        self.assertIn("G7 ok", out)

    def test_claude_agent_missing_description(self):
        self.edit(".claude/agents/dev-web.md", 'description: "Use para mudar rotas HTTP e templates em src/web."\n', "")
        self.assertFails("description obrigatória ausente")

    def test_claude_agent_unknown_field(self):
        self.edit(".claude/agents/dev-web.md", "memory: project\n", "memory: project\npersona: guru\n")
        self.assertFails("campos de frontmatter desconhecidos")

    def test_claude_rule_without_paths(self):
        self.edit(".claude/rules/cs-dev-web.md", 'paths:\n  - "src/web/**"\n', 'paths: []\n')
        self.assertFails("paths ausente ou vazio")

    def test_cursor_rule_always_apply(self):
        self.edit(".cursor/rules/cs-dev-web.mdc", "alwaysApply: false", "alwaysApply: talvez")
        self.assertFails("alwaysApply deve ser booleano")

    def test_cursor_core_must_always_apply(self):
        self.edit(".cursor/rules/cs-core.mdc", "alwaysApply: true", "alwaysApply: false")
        self.assertFails("alwaysApply: true")

    def test_copilot_instructions_apply_to(self):
        self.edit(".github/instructions/cs-dev-web.instructions.md", 'applyTo: "src/web/**"\n', "")
        self.assertFails("applyTo ausente")

    def test_codex_toml_required(self):
        self.edit(".codex/agents/dev-web.toml", "description = ", "descricao = ")
        self.assertFails("campo obrigatório ausente: description")

    def test_block_markers(self):
        self.edit(".github/copilot-instructions.md", END, "")
        self.assertFails("marcadores malformados")

    def test_hand_edit_is_stale(self):
        self.edit(".claude/agents/qa.md", "Mantém tests/", "Cuida de tests/")
        self.assertFails("desatualizado ou editado à mão")

    def test_missing_artifact(self):
        os.unlink(str(self.p(".cursor/agents/qa.md")))
        self.assertFails("ausente")

    def test_orphan_generated_file(self):
        src = self.p(".claude/agents/qa.md")
        shutil.copy(str(src), str(self.p(".claude/agents/fantasma.md")))
        self.assertFails("órfão")

    def test_map_json5_broken(self):
        self.p(".swarm/knowledge/deps.json5").write_text("{nodes: [", encoding="utf-8")
        self.assertFails("deps.json5: JSON5 inválido")

    def test_tree_must_cover_product_dirs(self):
        fixture_files = fixture.scan_facts()["inventory.json5"]["files"]
        fixture_files.append({"path": "src/novo/mod.py", "category": "product", "lang": "python", "loc": 3})
        data = fixture.scan_facts()
        data["inventory.json5"]["files"] = fixture_files
        self.p(".swarm/facts/inventory.json5").write_text(j5.dumps(data["inventory.json5"], "fixture"))
        self.assertFails("tree.json5")


class TestGate(Base):
    def test_emitted_gate_has_no_write_anywhere(self):
        code, _, err = self.emit()
        self.assertEqual(code, 0, err)
        fm, _ = parse_frontmatter(self.p(".claude/agents/reviewer.md").read_text())
        tools = [t.strip() for t in fm["tools"].split(",")]
        self.assertFalse({"Edit", "Write", "MultiEdit", "NotebookEdit"} & set(tools))
        self.assertTrue({"Edit", "Write"} <= {t.strip() for t in fm["disallowedTools"].split(",")})
        fm, _ = parse_frontmatter(self.p(".cursor/agents/reviewer.md").read_text())
        self.assertIs(fm["readonly"], True)
        fm, _ = parse_frontmatter(self.p(".github/agents/reviewer.agent.md").read_text())
        self.assertNotIn("edit", fm["tools"])
        self.assertIn('sandbox_mode = "read-only"', self.p(".codex/agents/reviewer.toml").read_text())
        self.assertFalse(self.p(".claude/rules/cs-reviewer.md").exists(), "gate não tem território (S2)")

    def test_gate_with_write_tool_rejected(self):
        team = fixture.team()
        team["agents"][2]["tools"].append("Edit")
        fixture.write_team(self.root, team)
        code, _, err = self.emit()
        self.assertEqual(code, 2)
        self.assertIn("gate com ferramentas de escrita", err)

    def test_gate_tampered_to_write_fails_validation(self):
        self.emit()
        self.edit(".claude/agents/reviewer.md", "tools: Read, Grep, Glob, Bash", "tools: Read, Grep, Glob, Bash, Edit")
        self.edit(".github/agents/reviewer.agent.md", '"execute"]', '"execute", "edit"]')
        self.edit(".codex/agents/reviewer.toml", '"read-only"', '"workspace-write"')
        self.edit(".cursor/agents/reviewer.md", "readonly: true", "readonly: false")
        code, _, err = self.validate()
        self.assertEqual(code, 1)
        for needle in ("gate com ferramenta de escrita", "gate com ferramenta edit",
                       'gate precisa de sandbox_mode = "read-only"', "gate precisa de readonly: true"):
            self.assertIn(needle, err)

    def test_verdict_outside_enum_rejected(self):
        team = fixture.team()
        team["agents"][2]["card"]["done_when"] = "veredito APPROVED gravado"
        fixture.write_team(self.root, team)
        code, _, err = self.emit()
        self.assertEqual(code, 2)
        self.assertIn("APPROVED", err)


class TestBudgetsAndPrune(Base):
    def test_s1_budget(self):
        team = fixture.team()
        team["agents"][1]["card"]["knows"] = [{"text": "fato %d" % i} for i in range(90)]
        fixture.write_team(self.root, team)
        code, _, err = self.emit()
        self.assertEqual(code, 2)
        self.assertIn("S1", err)

    def test_s0_budget(self):
        team = fixture.team()
        team["core"]["lines"] = [{"text": "linha %d" % i} for i in range(38)]
        fixture.write_team(self.root, team)
        code, _, err = self.emit()
        self.assertEqual(code, 2)
        self.assertIn("S0", err)

    def test_prune_removed_agent(self):
        self.emit()
        self.assertTrue(self.p(".claude/agents/qa.md").exists())
        team = fixture.team()
        team["agents"] = [a for a in team["agents"] if a["name"] != "qa"]
        fixture.write_team(self.root, team)
        code, out, err = self.emit()
        self.assertEqual(code, 0, err)
        self.assertFalse(self.p(".claude/agents/qa.md").exists())
        self.assertFalse(self.p(".codex/agents/qa.toml").exists())
        self.assertFalse(self.p("tests/AGENTS.md").exists())


class TestUnits(unittest.TestCase):
    def test_json5_roundtrip(self):
        obj = {"b": [1, {"x": "a//b", "y": None, "z": True, "w": 2}], "a-b": "ç"}
        text = j5.dumps(obj, "teste")
        self.assertTrue(text.startswith("// teste\n"))
        self.assertEqual(j5.loads(text), obj)
        self.assertEqual(j5.loads('{a: 1, /* c */ b: [1, 2,], // x\n}'), {"a": 1, "b": [1, 2]})

    def test_expand_braces(self):
        self.assertEqual(expand_braces(["src/*.{ts,tsx}"]), ["src/*.ts", "src/*.tsx"])


if __name__ == "__main__":
    unittest.main()
