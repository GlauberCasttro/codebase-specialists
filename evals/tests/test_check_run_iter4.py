"""Corretor (check_run.py) — regressões da iteração 4 (PLANO-ITER4.json5, frente_docs_scan_eval).

Falsos negativos medidos na iteração 3 (go-polyglot/with_skill/grading.json):
- [Q][TERM] "dev-dispatch usa 'driver'/'driver_id'" — as linhas eram o id de lacuna `gap.driver-id-compat` e
  "O backend usa courier_id; pings antigos do app do entregador ainda mandam driver_id." (variante citada
  como legado, ao lado do canônico): explicação, não uso;
- [Q][FIX] "python no texto" — a linha era o id de lacuna `gap.python-client-owner`; caminho
  `examples/python-client` numa recusa também não afirma stack;
- [Q][STACK] `@types/express` (pacote de tipos) nunca é lido como a versão de `express`.

Rodar: python3 -m unittest discover -s evals/tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import check_run as cr  # noqa: E402


class TermNegation(unittest.TestCase):
    def misuse(self, text, variant="driver_id", canonical="Courier"):
        return cr.term_misuse_lines(variant, canonical, text)

    def test_gap_id_is_not_usage(self):
        self.assertFalse(self.misuse("gap.driver-id-compat", variant="driver"))
        self.assertFalse(self.misuse("- lacuna: gap.driver-id-compat (ninguém sabe)", variant="driver"))

    def test_legacy_variant_next_to_canonical_is_not_usage(self):
        self.assertFalse(self.misuse("O backend usa courier_id; pings antigos do app do entregador ainda "
                                     "mandam driver_id."))
        self.assertFalse(self.misuse("'driver' não se usa: o termo é Courier.", variant="driver"))
        self.assertFalse(self.misuse("Apps velhos mandam driver_id (compatibilidade).", canonical="Entregador"))

    def test_variant_used_as_term_is_usage(self):
        self.assertTrue(self.misuse("Atribua a entrega ao driver com menos entregas ativas.", variant="driver"))
        self.assertTrue(self.misuse("O handler grava driver_id na tabela de entregas."))


class FixtureRefusal(unittest.TestCase):
    def claims(self, text, term, fx=("internal/dispatch/testdata/", "examples/")):
        return cr.word_in(term, cr.fixture_claim_corpus(text, list(fx)))

    def test_fact_id_and_path_are_not_stack(self):
        self.assertFalse(self.claims("gap.python-client-owner", "python"))
        self.assertFalse(self.claims("Pergunte antes (lacuna python-client-owner).", "python"))
        self.assertFalse(self.claims("Não decidir mudança que obrigue alterar `examples/python-client/client.py`.",
                                     "python"))
        self.assertFalse(self.claims("Recuse PR que mexa em `examples/python-client/**` sem o dono.", "python"))

    def test_stack_affirmation_still_counts(self):
        self.assertTrue(self.claims("O serviço usa Python 3.12 com requests.", "python"))
        self.assertTrue(self.claims("Stack: Go 1.22 e Python para a API.", "python"))


class StackScopedPackage(unittest.TestCase):
    def test_types_package_is_not_the_library(self):
        objs = [{"libs": [{"name": "@types/express", "version": "4.17.21"},
                          {"name": "lib:node:express", "version": "4.19.2"}]}]
        self.assertEqual(cr.find_version(objs, "express"), {"4.19.2"})
        self.assertEqual(cr.find_version(objs, "@types/express"), {"4.17.21"})

    def test_go_module_path_still_matches(self):
        self.assertTrue(cr.same_package("github.com/go-chi/chi/v5", "github.com/go-chi/chi/v5"))
        self.assertTrue(cr.same_package("lib:go:github.com/jackc/pgx/v5", "github.com/jackc/pgx/v5"))


if __name__ == "__main__":
    unittest.main()
