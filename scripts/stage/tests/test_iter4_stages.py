"""Iteração 4 — stages.json5 coerente com a CLI (rodada 3: validate.3 mandava `--out <dir fora do alvo>` enquanto o
SKILL mandava `.swarm/tmp/exam`; nenhum texto dizia a regra de GO nem a saída `--allow-non-specialist` do
--fast) e o pacote de `stage load validate` continua ≤ handoff_max_tokens com os textos novos."""
import os
import sys
import unittest

SCRIPTS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, SCRIPTS)

from stage import engine  # noqa: E402


class StagesText(unittest.TestCase):
    def setUp(self):
        self.cfg = engine.load_stages()
        self.subs = {s["id"]: s for n in self.cfg["order"] for s in self.cfg["stages"][n]["substages"]}

    def test_exam_pack_inside_specialists_tmp_with_history(self):
        do = self.subs["validate.3"]["do"]
        self.assertIn(".swarm/tmp/exam/<agente>", do)
        self.assertNotIn("fora do alvo>", do)
        self.assertIn("git -C <out>/repo log", do)

    def test_go_rule_and_fast_exit(self):
        self.assertIn("--allow-non-specialist", self.subs["validate.4"]["do"])
        self.assertIn("nao-especialista", self.subs["validate.6"]["do"])
        self.assertIn("NO-GO", self.subs["validate.6"]["do"])

    def test_harness_install_shows_outside_first(self):
        do = self.subs["validate.5"]["do"]
        self.assertIn("--dry-run", do)
        self.assertIn("--allow-outside", do)

    def test_validate_package_fits_handoff(self):
        run = {"schema_version": 1, "stages": {n: {"status": "done", "substages": {}} for n in self.cfg["order"]}}
        run["stages"]["validate"] = {"status": "pending", "substages": {}}
        import tempfile
        import shutil
        root = tempfile.mkdtemp(prefix="cs-it4-")
        try:
            from cslib import json5io
            os.makedirs(os.path.join(root, ".swarm", "stages"))
            json5io.dump({"produced": ["x"], "numbers": {"agents": 11}, "pending": []},
                         engine.handoff_path(root, "round-table-deep-specialize"), "teste", target=root)
            pkg, text = engine.load_package(root, self.cfg, run, "validate")
            self.assertLessEqual(engine.est_tokens(text), self.cfg["limits"]["handoff_max_tokens"])
            got = {c["id"]: c["do"] for c in pkg["checklist"]}
            for sid in ("validate.3", "validate.4", "validate.5", "validate.6"):  # o texto novo chega inteiro (sem encolher)
                self.assertEqual(got[sid], self.subs[sid]["do"])
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
