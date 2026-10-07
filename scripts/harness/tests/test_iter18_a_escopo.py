"""iter18 (corretor A): R1 escopo do tree_sha256 sem ignorados; R7 allowed_paths = território inteiro recusado.
O oráculo da campanha (campanhas/iter18/oraculo) cobre o fluxo pela CLI; aqui ficam as unidades do motor."""
import os
import tempfile
import unittest

import fixture  # noqa: F401  (sys.path do engine)
import cmds
import engine
import hcore


class TestWholeTerritory(unittest.TestCase):
    TERR = ["src/billing/**"]

    def test_contem_o_territorio(self):
        for p in ("src/billing/**", "src/billing/**/*", "src/billing/", "src/billing", "src/**"):
            self.assertTrue(engine.whole_territory(p, self.TERR), p)

    def test_estreito_passa(self):
        for p in ("src/billing/total.py", "src/billing/discount/**", "src/billing/*.py", "src/billing/*"):
            self.assertFalse(engine.whole_territory(p, self.TERR), p)

    def test_territorio_de_arquivo_explicito(self):
        self.assertFalse(engine.whole_territory("config/app.json", ["config/app.json"]))
        self.assertTrue(engine.whole_territory("config/**", ["config/app.json"]))

    def test_dica_de_amend(self):
        msg = engine.whole_territory_problem("T-9", "src/billing/**", "dev-billing", self.TERR)
        self.assertIn("cs-state amend T-9 --field allowed_paths", msg)


class TestFilesInScopeSemIgnorados(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo(with_state=False)
        fixture.write(self.root, ".gitignore", "bin/\nobj/\n")
        fixture.write(self.root, "src/billing/obj/x.dll", "build\n")
        fixture.write(self.root, "src/billing/novo.py", "N = 1\n")

    def tearDown(self):
        fixture.rm(self.root)

    def test_git_tira_ignorado_e_mantem_nao_rastreado(self):
        got = engine.files_in_scope(self.root, ["src/billing/**"])
        self.assertIn("src/billing/total.py", got)
        self.assertIn("src/billing/novo.py", got)
        self.assertNotIn("src/billing/obj/x.dll", got)
        self.assertEqual(engine.git_ignored(self.root, ["src/billing/obj/x.dll", "src/billing/total.py"]),
                         {"src/billing/obj/x.dll"})

    def test_sem_git_cai_no_walk(self):
        d = os.path.realpath(tempfile.mkdtemp(prefix="cs-nogit-"))
        try:
            fixture.write(d, "src/billing/obj/x.dll", "build\n")
            self.assertEqual(engine.files_in_scope(d, ["src/billing/**"]), ["src/billing/obj/x.dll"])
        finally:
            fixture.rm(d)


class TestDespachoRecusaTerritorioInteiro(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo()
        fixture.process(self.root, "pequena")

    def tearDown(self):
        fixture.rm(self.root)

    def test_ready_recusa_com_dica(self):
        with self.assertRaises(hcore.Refused) as cm:
            cmds.add_task(self.root, fixture.A, fixture.task_spec(paths=("src/billing/**",)), ready=True)
        self.assertIn("amend", " ".join(cm.exception.problems))
        cmds.add_task(self.root, fixture.A, fixture.task_spec(paths=("src/billing/discount.py",), title="ok"), ready=True)


if __name__ == "__main__":
    unittest.main()
