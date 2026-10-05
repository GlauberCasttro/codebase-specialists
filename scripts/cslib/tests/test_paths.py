"""cslib.paths.classify — examples/ fora de pasta de teste é `example` (pode ter dono), não fixture."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cslib import paths  # noqa: E402


class Classify(unittest.TestCase):
    def test_example_dirs(self):
        for rel in ("examples/python-client/client.py", "example/main.go", "samples/demo/app.ts",
                    "sdk/examples/basic.py"):
            self.assertEqual(paths.classify(rel), paths.CAT_EXAMPLE, rel)

    def test_examples_under_tests_are_fixtures(self):
        for rel in ("tests/examples/case.json", "src/__tests__/samples/a.ts", "pkg/testdata/examples/x.txt"):
            self.assertEqual(paths.classify(rel), paths.CAT_FIXTURE, rel)

    def test_priority(self):
        self.assertEqual(paths.classify("examples/node_modules/x/index.js"), paths.CAT_VENDOR)
        self.assertEqual(paths.classify("examples/fixtures/a.json"), paths.CAT_FIXTURE)
        self.assertEqual(paths.classify("src/app.py"), paths.CAT_PRODUCT)

    def test_category_sets(self):
        self.assertIn(paths.CAT_EXAMPLE, paths.CATEGORIES)
        self.assertNotIn(paths.CAT_EXAMPLE, paths.IGNORED_CATEGORIES)
        self.assertEqual(paths.NOT_ANALYZED_CATEGORIES, paths.IGNORED_CATEGORIES | {paths.CAT_EXAMPLE})


if __name__ == "__main__":
    unittest.main()
