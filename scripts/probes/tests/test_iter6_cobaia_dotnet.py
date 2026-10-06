"""Iteração 6 (cobaia .NET, 2026-10-05) — reprovações vinham da PROVA, não do agente: `using` em string literal C#
contado como import; pergunta de dependência sem critério; POR-QUÊ exigia a linha do título; POR-QUÊ gerada de
cabeçalho genérico de log."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "team", "tests"))
import synth  # noqa: E402

from team._shared_tmp.common import read_json, sp_path  # noqa: E402
from team.derive import derive  # noqa: E402
from probes.exam import Checker  # noqa: E402
from probes.generate import GENERIC_TOPICS, IMPORT_CRITERION, _topic_key, generate  # noqa: E402
from scan.l1_graph import CS_FIRST_TYPE, CS_USING  # noqa: E402

CS_TEST = '''using System;
using Xunit;

namespace App.Tests;

[Trait("k", "v")]
public sealed class GeneratorTests
{
    const string Src = """
        using App.Configuration;
        namespace User { }
        """;
}
'''


def cs_usings(text):
    first = CS_FIRST_TYPE.search(text)
    return [m.group(1) for m in CS_USING.finditer(text[:first.start()] if first else text)]


class CSharpUsingScope(unittest.TestCase):
    def test_using_inside_string_literal_is_not_import(self):
        self.assertEqual(cs_usings(CS_TEST), ["System", "Xunit"])

    def test_usings_inside_namespace_block_before_type_count(self):
        text = "namespace A\n{\n    using B.C;\n    internal static partial class X { }\n}\n"
        self.assertEqual(cs_usings(text), ["B.C"])

    def test_file_without_type_keeps_all_usings(self):
        self.assertEqual(cs_usings("using Foo.Bar;\nusing Baz;\n"), ["Foo.Bar", "Baz"])


class ProbeWording(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()
        derive(self.root)

    def tearDown(self):
        synth.cleanup(self.root)

    def test_dependency_question_states_criterion(self):
        generate(self.root)
        bank = read_json(sp_path(self.root, "probes", "bank.json5"), "bank")
        deps = [p for p in bank["probes"] if p["type"] == "dependency"]
        self.assertTrue(deps, "synth deveria gerar sonda de dependência")
        for p in deps:
            self.assertIn("critério:", p["question"])
        self.assertIn("using", IMPORT_CRITERION[".cs"])

    def test_generic_topics_are_detected(self):
        for t in ("O que foi feito", "Sumário", "  Próximos passos ", "Context"):
            self.assertIn(_topic_key(t), GENERIC_TOPICS, t)
        self.assertNotIn(_topic_key("ADR-006: IncludePrivateMembers via UnsafeAccessor"), GENERIC_TOPICS)

    def test_why_accepts_any_line_of_source_document(self):
        ch = Checker(self.root)
        probe = {"type": "why", "answer": {"exists": True, "key_terms": [],
                                            "sources": [{"file": "src/billing/invoice.py", "line": 1}]}}
        ok, _, why, pend = ch.score_one(probe, {"answer": "porque X", "evidence": ["src/billing/invoice.py:3"]})
        self.assertTrue(ok and pend, why)
        other = [f for f in ch.files if f.endswith(".py") and f != "src/billing/invoice.py"][0]
        ok, _, why, _ = ch.score_one(probe, {"answer": "porque X", "evidence": ["%s:1" % other]})
        self.assertFalse(ok, why)


if __name__ == "__main__":
    unittest.main()
