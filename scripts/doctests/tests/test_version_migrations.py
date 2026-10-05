"""Regra de manutenção do upgrade: VERSION (raiz da skill) tem SEMPRE uma migração correspondente em
references/migrations.json5 — mudar VERSION sem cadastrar a entrada (`to` = VERSION) reprova aqui.

Também confere o catálogo inteiro contra o schema (kinds válidos, `to` estritamente crescente, scan com layers,
schema com script) e que o tipo `rename-dir` está previsto no schema.
"""
import os
import sys
import unittest

SCRIPTS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKILL = os.path.dirname(SCRIPTS)
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from cslib import json5io  # noqa: E402
from upgrade import version as V  # noqa: E402


class VersionHasMigration(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(SKILL, "VERSION"), encoding="utf-8") as fh:
            self.version = fh.read().strip()
        self.cat = json5io.read(os.path.join(SKILL, "references", "migrations.json5"))

    def test_version_is_semver(self):
        V.parse(self.version)

    def test_catalog_version_matches_VERSION(self):
        self.assertEqual(self.cat.get("version"), self.version,
                         "VERSION mudou sem atualizar references/migrations.json5 (version + entrada nova)")

    def test_last_migration_targets_VERSION(self):
        tos = [m.get("to") for m in self.cat.get("migrations") or []]
        self.assertIn(self.version, tos, "VERSION=%s sem migração correspondente (to=%s)" % (self.version,
                                                                                            self.version))
        self.assertEqual(tos[-1], self.version)

    def test_catalog_schema(self):
        self.assertEqual(V.validate_catalog(self.cat, self.version), [])

    def test_rename_dir_kind_foreseen(self):
        self.assertIn("rename-dir", V.KINDS)   # previsto no schema (a migração entra com a frente do rename)

    def test_validator_catches_version_without_migration(self):
        bad = dict(self.cat, version="99.0.0")
        errs = V.validate_catalog(bad, "99.0.0")
        self.assertTrue(any("sem migração correspondente" in e for e in errs), errs)


if __name__ == "__main__":
    unittest.main()
