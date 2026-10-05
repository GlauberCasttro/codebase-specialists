"""cslib.workspaces — nome de pacote do monorepo → diretório/entrada; nunca é caminho."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cslib import workspaces  # noqa: E402

FILES = {
    "package.json": '{"name": "shop", "workspaces": ["packages/*", "apps/*"]}',
    "packages/shared/package.json": '{"name": "@shop/shared", "exports": {".": "./src/index.ts"}}',
    "packages/shared/src/index.ts": "",
    "packages/shared/src/sku.ts": "",
    "packages/api/package.json": '{"name": "@shop/api", "main": "dist/server.js", "scripts": {"test": "x"}}',
    "packages/api/src/server.ts": "",
    "packages/api/src/inventory/index.ts": "",
    "apps/web/package.json": '{"name": "@shop/web"}',
    "apps/web/src/main.tsx": "",
    "node_modules/x/package.json": '{"name": "x"}',
    "broken/package.json": "{not json",
}


def read(rel):
    return FILES[rel]


class Workspaces(unittest.TestCase):
    def setUp(self):
        self.ws = workspaces.discover(sorted(FILES), read)

    def test_discover(self):
        self.assertEqual(sorted(self.ws), ["@shop/api", "@shop/shared", "@shop/web", "shop"])
        self.assertEqual(self.ws["@shop/shared"]["dir"], "packages/shared")
        self.assertEqual(self.ws["@shop/shared"]["entries"], ["packages/shared/src/index.ts"])
        self.assertEqual(self.ws["@shop/api"]["scripts"], {"test": "x"})
        self.assertNotIn("x", self.ws)  # node_modules nunca é workspace

    def test_resolve(self):
        files = set(FILES)
        self.assertEqual(workspaces.resolve(self.ws, "@shop/shared", files), "packages/shared/src/index.ts")
        self.assertEqual(workspaces.resolve(self.ws, "@shop/api/inventory", files),
                         "packages/api/src/inventory/index.ts")
        self.assertIsNone(workspaces.resolve(self.ws, "@shop/api/nope", files))
        self.assertIsNone(workspaces.resolve(self.ws, "react", files))

    def test_entry_fallback_when_main_points_to_build_output(self):
        self.assertEqual(self.ws["@shop/api"]["entries"], [])
        self.assertEqual(self.ws["@shop/web"]["entries"], ["apps/web/src/main.tsx"])

    def test_package_ref_shape(self):
        self.assertTrue(workspaces.looks_like_package_ref("@shop/api/inventory"))
        self.assertTrue(workspaces.looks_like_package_ref("@types/node"))
        self.assertFalse(workspaces.looks_like_package_ref("packages/shared"))
        self.assertFalse(workspaces.looks_like_package_ref("@decorator"))
        self.assertEqual(workspaces.split_spec("@a/b/c/d"), ("@a/b", "c/d"))
        self.assertEqual(workspaces.split_spec("lodash/fp"), ("lodash", "fp"))


if __name__ == "__main__":
    unittest.main()
