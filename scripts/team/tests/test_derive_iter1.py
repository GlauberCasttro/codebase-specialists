"""Regressões da iteração 1 em `team derive`: núcleo de domínio ≠ utils; teste co-localizado tem dono por glob."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import synth  # noqa: E402

from team.derive import derive  # noqa: E402
from team.validate import validate  # noqa: E402
from team._shared_tmp.common import expand  # noqa: E402


def by_name(team):
    return {a["name"]: a for a in team["agents"]}


class DomainCoreTest(unittest.TestCase):
    def test_domain_core_by_fan_in_stays_with_a_dev(self):
        edges = [["src/billing/invoice.py", "src/orders/order.py"], ["src/catalog/price.py", "src/orders/order.py"],
                 ["src/tiny/x.py", "src/orders/order.py"]]
        root = synth.make_repo(extra_edges=edges)
        try:
            team, deriv = derive(root)
            a = by_name(team)
            self.assertIn("dev-orders", a)
            self.assertEqual(a["dev-orders"]["territory"], ["src/orders/**"])
            self.assertEqual(a["architect"]["territory"], ["docs/**"])
            self.assertIn("src/orders/**", a["dev-billing"]["reads"])
            self.assertTrue(any("núcleo de domínio" in d["decision"] for d in deriv["decisions"]))
            self.assertTrue(validate(root)["pass"])
        finally:
            synth.cleanup(root)


class ColocatedTestsTest(unittest.TestCase):
    def test_colocated_test_owned_by_directory_owner_glob(self):
        extra = {"src/catalog/search_test.py": "import unittest\n", "src/billing/tests/test_tax.py": "x = 1\n"}
        root = synth.make_repo(extra_files=extra)
        try:
            team, _ = derive(root)
            a = by_name(team)
            self.assertEqual(a["qa"]["territory"], ["tests/**"])
            self.assertIn("src/catalog/**", a["dev-catalog"]["territory"])
            self.assertEqual(a["dev-billing"]["territory"], ["src/billing/**"])
            self.assertEqual(team["test_ownership"]["colocated"], "owner")
            # arquivo de teste NOVO já nasce com dono (glob de diretório, não lista de arquivos)
            for new in ("src/catalog/price_test.py", "src/billing/tests/test_new.py"):
                owners = [n for n, x in a.items() if expand(x["territory"], [new])]
                self.assertEqual(len(owners), 1, (new, owners))
            self.assertTrue(validate(root)["pass"])
        finally:
            synth.cleanup(root)

    def test_direct_files_of_mixed_dir_use_dir_star(self):
        extra = {"src/catalog/sub/a.py": "x = 1\n", "src/catalog/sub/b.py": "x = 1\n", "src/catalog/sub/c.py": "x = 1\n"}
        root = synth.make_repo(extra_files=extra)
        try:
            team, _ = derive(root)
            for ag in team["agents"]:
                for g in ag["territory"]:
                    self.assertFalse(g.endswith(".py") and g.count("/") >= 2 and "*" not in g,
                                     "território por arquivo: %s (%s)" % (g, ag["name"]))
        finally:
            synth.cleanup(root)


if __name__ == "__main__":
    unittest.main()
