"""[Q][FIX]: menção que recusa a fixture não conta como contaminação; afirmação de stack conta.

Rodar: python3 -m unittest discover -s evals/tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import check_run as cr  # noqa: E402


def contaminated(line, term):
    neg = cr.neg_filtered(line)
    kept = "\n".join(l for l in neg.splitlines()
                     if not cr.FIXTURE_CTX_RE.search(l) and not cr.FIXTURE_REFUSAL_RE.search(l))
    return cr.word_in(term, kept)


class FixRefusal(unittest.TestCase):
    def test_refusal_is_not_contamination(self):
        # caso real do ts-shop (iteração 2): `why` do never_use gravado como string própria
        why = "README.md e o scan tratam esses arquivos (exports do ERP antigo em Python/Java) só como dado de teste de importação."
        self.assertFalse(contaminated(why, "python"))
        self.assertFalse(contaminated(why, "java"))
        self.assertFalse(contaminated("Os .csproj são test data only, not part of the product.", "java"))
        self.assertFalse(contaminated("Não use Django: o legacy-erp é fixture.", "django"))

    def test_affirmation_is_contamination(self):
        self.assertTrue(contaminated("O backend usa Python 3.12 com Django.", "django"))
        self.assertTrue(contaminated("Stack: TypeScript e Java/Spring para pedidos.", "java"))


if __name__ == "__main__":
    unittest.main()
