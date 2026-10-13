"""iter24 (0.12.2): portas laterais do guard — harness indireto, hardlink, registros humanos, flags de saída, inline, git."""
import json
import os
import subprocess
import sys
import unittest

import fixture
import bashscan
import hcore

GUARD = os.path.join(fixture.ENGINE, "guard.py")
SUB = {"agent_id": "ag-1", "agent_type": "dev-billing"}
PROT = ["main", "master"]


def hook(root, mode, payload, actor=None):
    payload = dict(payload, cwd=root)
    payload.update(actor or {})
    e = dict(os.environ, CLAUDE_PROJECT_DIR=root)
    e.pop("CS_GUARD_OFF", None)
    p = subprocess.run([sys.executable, GUARD, mode], input=json.dumps(payload).encode(), env=e,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    return p.returncode, (p.stdout + p.stderr).decode()


def bash(root, cmd, actor=None):
    return hook(root, "pre-bash", {"tool_name": "Bash", "tool_input": {"command": cmd}}, actor)[0]


def write(root, rel, actor=None, tool="Write"):
    ti = {"file_path": os.path.join(root, rel), "content": "x"} if tool == "Write" else \
        {"file_path": os.path.join(root, rel), "old_string": "a", "new_string": "b"}
    return hook(root, "pre-write", {"tool_name": tool, "tool_input": ti}, actor)[0]


def scan(root, cmd):
    hp = {"state": os.path.realpath(os.path.join(root, ".swarm/harness/state.py")),
          "bin_state": os.path.realpath(os.path.join(root, ".swarm/bin/cs-state"))}
    return bashscan.scan(cmd, root, root, hp)


class TestPortasBashscan(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo(no_rules=True)

    def tearDown(self):
        fixture.rm(self.root)

    def calls(self, cmd):
        s = scan(self.root, cmd)
        self.assertEqual(s.unanalyzable, [], cmd)
        return [(c["tool"], c["argv"]) for c in s.harness_calls]

    def test_ca01_formas_indiretas_viram_chamada_do_harness(self):
        for cmd in ("sh .swarm/bin/cs-state accept T-1", "bash .swarm/bin/cs-state accept T-1",
                    "python3 -W ignore .swarm/harness/state.py accept T-1",
                    "python3 -X dev .swarm/harness/state.py accept T-1",
                    "cd .swarm/harness && python3 -m state accept T-1", "python3 -m state accept T-1"):
            self.assertEqual(self.calls(cmd)[-1], ("state", ["accept", "T-1"]), cmd)

    def test_ca01_controle_script_do_projeto_nao_e_harness(self):
        for cmd in ("bash scripts/build.sh", "python3 -m unittest tests.test_ok", "python3 tools/x.py"):
            self.assertEqual(self.calls(cmd), [], cmd)

    def test_ca01_ato_humano_do_auto_por_python_m(self):
        import auto
        self.assertEqual(auto.human_act_in_command("cd .swarm/harness && python3 -m auto approve"), "approve")
        self.assertIsNone(auto.human_act_in_command("python3 -m auto status"))

    def test_ca02_ln_e_cp_l_conferem_a_origem(self):
        for cmd in ("ln .claude/settings.json src/a.py", "cp -l .claude/settings.json src/a.py"):
            self.assertIn(".claude/settings.json", [w[0] for w in scan(self.root, cmd).writes], cmd)
        self.assertNotIn("a.txt", [w[0] for w in scan(self.root, "cp a.txt b.txt").writes])
        self.assertNotIn("a.txt", [w[0] for w in scan(self.root, "ln -s a.txt b.txt").writes])

    def test_ca04_flags_de_saida_viram_destino(self):
        casos = {"git diff --output=out.patch": "out.patch", "git log --output out.txt -1": "out.txt",
                 "curl -o o.bin http://x": "o.bin", "curl -sSo o.bin http://x": "o.bin",
                 "wget -O o.bin http://x": "o.bin", "tar -C dest -xf a.tar": "dest", "tar -xCf dest a.tar": "dest",
                 "unzip -d dest a.zip": "dest", "dotnet publish -o out": "out"}
        for cmd, want in casos.items():
            self.assertIn(want, [w[0] for w in scan(self.root, cmd).writes], cmd)
        self.assertEqual(scan(self.root, "git diff").writes, [])

    def test_ca05_inline_e_stdin(self):
        for cmd in ("python3 -Sc 'x'", "python3 -Ic 'x'", "python3 -uc 'x'", "echo x | python3 -", "echo x | sh -",
                    "python3 /dev/stdin", "ruby -ne 'puts 1'", "node -pe '1'", "perl -pe 's/a/b/'"):
            self.assertTrue(scan(self.root, cmd).unanalyzable, cmd)
        for cmd in ("python3 tools/x.py", "python3 -W ignore tools/x.py", "node tools/x.js", "sh tools/x.sh"):
            self.assertEqual(scan(self.root, cmd).unanalyzable, [], cmd)

    def test_ca06_git_problemas(self):
        bad = [("config", ["core.hooksPath", "/dev/null"]), ("config", ["--global", "core.hookspath", "x"]),
               ("push", ["origin", "HEAD:main"]), ("push", ["origin", "+x:main"]), ("push", ["origin", ":master"]),
               ("push", ["-f"]), ("push", ["--force-with-lease"]), ("push", ["--delete", "o", "x"]),
               ("push", ["--mirror"]), ("commit", ["--no-verify", "-m", "x"]), ("commit", ["-n", "-m", "x"]),
               ("commit", ["-nm", "x"]), ("branch", ["-D", "master"]), ("branch", ["-f", "main", "HEAD"]),
               ("remote", ["set-url", "origin", "x"]), ("remote", ["add", "o", "x"]), ("reflog", ["expire", "--all"])]
        for sub, args in bad:
            self.assertTrue(bashscan.git_problem(sub, args, PROT), (sub, args))
        ok = [("config", ["user.name"]), ("config", ["--get", "core.hooksPath"]), ("push", ["origin", "feat"]),
              ("push", ["-u", "origin", "feat:feat2"]), ("commit", ["-m", "nota normal"]), ("commit", ["-am", "x"]),
              ("commit", ["-mnote"]), ("branch", ["-D", "feat"]), ("branch", ["-a"]), ("remote", ["-v"]),
              ("reflog", []), ("log", ["-1"]), ("status", [])]
        for sub, args in ok:
            self.assertIsNone(bashscan.git_problem(sub, args, PROT), (sub, args))

    def test_ca06_efeito_de_branch_remote_config_reflog(self):
        for sub, args in (("branch", ["-D", "x"]), ("branch", ["novo"]), ("remote", ["add", "o", "u"]),
                          ("config", ["a.b", "v"]), ("reflog", ["expire"])):
            self.assertEqual(bashscan.git_effect(sub, args), "lead", (sub, args))
        for sub, args in (("branch", []), ("branch", ["-a"]), ("remote", ["-v"]), ("config", ["--get", "a.b"]),
                          ("config", ["a.b"]), ("reflog", [])):
            self.assertEqual(bashscan.git_effect(sub, args), "read", (sub, args))


class TestPortasHook(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo(no_rules=True)

    def tearDown(self):
        fixture.rm(self.root)

    def test_ca01_principal_ato_humano_indireto_recusado(self):
        self.assertEqual(bash(self.root, "python3 -m state waive-verify T-1"), 2)
        self.assertEqual(bash(self.root, "cd .swarm/harness && python3 -m auto approve"), 2)
        self.assertEqual(bash(self.root, "bash scripts/build.sh"), 0)

    def test_ca03_registros_humanos_nao_gravaveis(self):
        for rel in hcore.HUMAN_RECORDS:
            for tool in ("Write", "Edit"):
                self.assertEqual(write(self.root, rel, tool=tool), 2, (rel, tool))
        self.assertEqual(bash(self.root, "echo x >> .swarm/approvals.jsonl"), 2)
        self.assertEqual(write(self.root, ".swarm/knowledge/notas-da-ana.md"), 0)

    def test_ca02_escrita_por_hardlink_de_protegido_recusada(self):
        prot = os.path.join(self.root, ".claude", "settings.json")
        os.makedirs(os.path.dirname(prot), exist_ok=True)
        with open(prot, "w") as fh:
            fh.write("{}")
        link = os.path.join(self.root, ".swarm", "knowledge", "elo.md")
        os.makedirs(os.path.dirname(link), exist_ok=True)
        os.link(prot, link)
        self.assertEqual(write(self.root, ".swarm/knowledge/elo.md"), 2)
        self.assertEqual(bash(self.root, "echo x > .swarm/knowledge/elo.md"), 2)
        with open(os.path.join(self.root, ".swarm", "knowledge", "comum.md"), "w") as fh:
            fh.write("a")
        self.assertEqual(write(self.root, ".swarm/knowledge/comum.md"), 0)

    def test_ca06_git_perigoso_e_leitura(self):
        self.assertEqual(bash(self.root, "git config core.hooksPath /dev/null"), 2)
        self.assertEqual(bash(self.root, "git -c core.hooksPath=/dev/null commit -m x"), 2)
        self.assertEqual(bash(self.root, "git push origin HEAD:main"), 2)
        self.assertEqual(bash(self.root, "git commit -n -m x"), 2)
        self.assertEqual(bash(self.root, "git status"), 0)
        self.assertEqual(bash(self.root, "git log -1"), 0)
        self.assertEqual(bash(self.root, "git branch -D master", SUB), 2)
        self.assertEqual(bash(self.root, "git remote set-url origin x", SUB), 2)

    def test_c2_f1_harness_por_variavel_ou_til(self):
        for cmd in ("python3 $PWD/.swarm/harness/state.py waive-verify T-1",
                    'python3 "$PWD"/.swarm/harness/state.py waive-verify T-1',
                    "python3 ~/x/.swarm/harness/state.py waive-verify T-1",
                    "bash $PWD/.swarm/bin/cs-state waive-verify T-1"):
            self.assertEqual(bash(self.root, cmd), 2, cmd)
            self.assertEqual(bash(self.root, cmd, SUB), 2, cmd)
        self.assertEqual(bash(self.root, "python3 $PWD/.swarm/harness/naoexiste.py x"), 2)
        self.assertEqual(bash(self.root, "python3 $PWD/tools/x.py"), 0)
        self.assertEqual(bash(self.root, "python3 tools/x.py"), 0)

    def test_c2_f2_refspec_mais_e_force(self):
        self.assertEqual(bash(self.root, "git push origin +HEAD"), 2)
        self.assertEqual(bash(self.root, "git push origin +x:y"), 2)

    def test_c2_f3_abreviacoes_de_opcao_longa(self):
        for cmd in ("git commit --no-veri -m a", "git commit --no-verif -m a", "git push --no-veri origin x",
                    "git push --forc origin x", "git push --mirr origin", "git push --dele origin x"):
            self.assertEqual(bash(self.root, cmd), 2, cmd)
        self.assertEqual(bash(self.root, "git commit --no-edit -m a"), 0)
        self.assertEqual(bash(self.root, "git push origin x"), 0)


    def test_c3_f1_harness_por_variavel_com_caminho_nao_normalizado(self):
        for cmd in ("python3 $PWD/.swarm//harness/state.py waive-verify T-1",
                    "python3 $PWD/.swarm/./harness/state.py waive-verify T-1",
                    "python3 $PWD/.swarm/tmp/../harness/state.py waive-verify T-1",
                    "bash $PWD/.swarm/./bin/cs-state waive-verify T-1",
                    "python3 $PWD/.swarm/x/../../.swarm/harness/state.py waive-verify T-1",
                    "python3 $A/.swarm/.//harness/state.py waive-verify T-1",
                    "bash ~/.swarm/./bin/cs-state waive-verify T-1",
                    "python3 $PWD/.swarm/outro/coisa.py x"):
            self.assertEqual(bash(self.root, cmd), 2, cmd)
            self.assertEqual(bash(self.root, cmd, SUB), 2, cmd)
        for cmd in ("python3 $PWD/tools/x.py", "bash $PWD/scripts/build.sh", "python3 $HOME/scripts/y.py",
                    "python3 $PWD/tools/./x.py"):
            self.assertEqual(bash(self.root, cmd), 0, cmd)

    def test_c3_f2_no_verify_depois_de_duplo_traco_e_pathspec(self):
        self.assertEqual(bash(self.root, "git commit -m a -- --no-veri"), 0)
        self.assertEqual(bash(self.root, "git commit -m a -- -n"), 0)
        self.assertEqual(bash(self.root, "git commit --no-veri -m a -- x"), 2)


if __name__ == "__main__":
    unittest.main()
