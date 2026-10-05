"""Cenários de aceite do `cs.py upgrade` (UPGRADE-1..6) contra um alvo REAL gerado pela skill na iteração 4.

O alvo de origem ($CS_UPGRADE_LEGACY_TARGET: alvo gerado por versão anterior da skill; sem ele, PULA) é só COPIADO para um mktemp — nunca escrito.
Ele é legado (run.json5 sem skill_version). A base "versão anterior" é essa cópia depois de um upgrade real
para a VERSION atual; os cenários 1/2/4/5 sobem dela para uma versão sintética (VERSION e migrations.json5
temporários via $CS_SKILL_VERSION_FILE / $CS_MIGRATIONS_FILE), cuja última migração é a ação sob teste.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKILL = os.path.dirname(SCRIPTS)
CS = os.path.join(SCRIPTS, "cs.py")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from cslib import json5io  # noqa: E402
from cslib.paths import LEGACY_STATE_DIR, STATE_DIR  # noqa: E402

LEGACY_SRC = os.environ.get("CS_UPGRADE_LEGACY_TARGET") or ""
NEXT = "9.9.0"
PRESERVED_FILES = ("interview.jsonl", "team-approvals.jsonl", "approvals.jsonl", "cards/status.json5",
                   "team-derivation.json5")


def tree_hash(root, skip=(".git",), skip_backups=False):
    """{relpath: sha256|link:<alvo>} de toda a árvore (exceto .git e, opcionalmente, <STATE_DIR>/backups)."""
    out = {}
    for d, dirs, files in os.walk(root):
        rel_d = os.path.relpath(d, root)
        keep = []
        for x in dirs:
            rel = os.path.normpath(os.path.join(rel_d, x))
            if rel in skip or (skip_backups and rel == os.path.join(STATE_DIR, "backups")):
                continue
            if os.path.islink(os.path.join(d, x)):
                out[rel] = "link:" + os.readlink(os.path.join(d, x))
                continue
            keep.append(x)
        dirs[:] = keep
        for f in files:
            p = os.path.join(d, f)
            rel = os.path.normpath(os.path.join(rel_d, f))
            if os.path.islink(p):
                out[rel] = "link:" + os.readlink(p)
            else:
                with open(p, "rb") as fh:
                    out[rel] = hashlib.sha256(fh.read()).hexdigest()
    return out


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def cs(target, *args, env=None):
    e = dict(env or os.environ)
    e.pop("CLAUDE_PROJECT_DIR", None)
    p = subprocess.run([sys.executable, CS, "--target", target] + list(args), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, env=e, timeout=1800)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def clean_env():
    e = dict(os.environ)
    for k in ("CS_SKILL_VERSION_FILE", "CS_MIGRATIONS_FILE", "CLAUDE_PROJECT_DIR"):
        e.pop(k, None)
    return e


@unittest.skipUnless(bool(LEGACY_SRC) and os.path.isdir(os.path.join(LEGACY_SRC, LEGACY_STATE_DIR)),
                     "alvo legado ausente (defina $CS_UPGRADE_LEGACY_TARGET): %s" % (LEGACY_SRC or "não definido"))
class Upgrade(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="cs-upgrade-")
        cls.legacy = os.path.join(cls.tmp, "legacy")
        shutil.copytree(LEGACY_SRC, cls.legacy, symlinks=True)
        run = json5io.read(os.path.join(cls.legacy, LEGACY_STATE_DIR, "run.json5"))
        assert "skill_version" not in run, "o alvo de origem deveria ser legado"
        cls.base = os.path.join(cls.tmp, "base")             # "gerado na versão anterior" (= VERSION atual)
        shutil.copytree(cls.legacy, cls.base, symlinks=True)
        rc, out, err = cs(cls.base, "upgrade", "--apply", "--allow-outside", env=clean_env())
        assert rc == 0, out + err
        with open(os.path.join(SKILL, "VERSION")) as fh:
            cls.current = fh.read().strip()
        cls.n = 0

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # ---------------------------------------------------------------- helpers

    def copy(self, src):
        Upgrade.n += 1
        dst = os.path.join(self.tmp, "t%d" % Upgrade.n)
        shutil.copytree(src, dst, symlinks=True)
        self.addCleanup(shutil.rmtree, dst, True)
        return dst

    def next_env(self, actions):
        """VERSION=NEXT e catálogo = real + {to: NEXT, actions}."""
        d = tempfile.mkdtemp(prefix="cat-", dir=self.tmp)
        cat = json5io.read(os.path.join(SKILL, "references", "migrations.json5"))
        cat["version"] = NEXT
        cat["migrations"].append({"to": NEXT, "why": "teste", "actions": actions})
        json5io.dump(cat, os.path.join(d, "migrations.json5"), "catálogo de teste")
        with open(os.path.join(d, "VERSION"), "w") as fh:
            fh.write(NEXT + "\n")
        env = clean_env()
        env["CS_MIGRATIONS_FILE"] = os.path.join(d, "migrations.json5")
        env["CS_SKILL_VERSION_FILE"] = os.path.join(d, "VERSION")
        return env, d

    def run_json(self, t, state_dir=STATE_DIR):
        return json5io.read(os.path.join(t, state_dir, "run.json5"))

    def knowledge_snapshot(self, t, state_dir=STATE_DIR):
        """state_dir: STATE_DIR depois do upgrade; LEGACY_STATE_DIR só na foto inicial do alvo legado."""
        sp = os.path.join(t, state_dir)
        team = json5io.read(os.path.join(sp, "team.json5"))
        run = self.run_json(t, state_dir)
        return {
            "files": {f: sha(os.path.join(sp, f)) for f in PRESERVED_FILES if os.path.exists(os.path.join(sp, f))},
            "cards": {a["name"]: json.dumps(a.get("card"), sort_keys=True) for a in team["agents"]},
            "roster": sorted((a["name"], json.dumps(a.get("territory"), sort_keys=True)) for a in team["agents"]),
            "stages": json.dumps(run.get("stages"), sort_keys=True),
            "current_stage": run.get("current_stage"),
        }

    def assert_knowledge_intact(self, before, t, env):
        self.assertEqual(self.knowledge_snapshot(t), before)
        rc, out, err = cs(t, "team", "approved", env=env)
        self.assertEqual(rc, 0, out + err)           # roster continua aprovado (sem reabrir aprovação)

    # ---------------------------------------------------------------- cenários

    def test_upgrade_1_previous_version_keeps_interview_roster_cards(self):
        t = self.copy(self.base)
        env, _ = self.next_env([{"kind": "harness"}, {"kind": "emit"}])
        before = self.knowledge_snapshot(t)
        self.assertEqual(self.run_json(t)["skill_version"], self.current)
        rc, out, err = cs(t, "upgrade", "--apply", "--allow-outside", env=env)
        self.assertEqual(rc, 0, out + err)
        self.assertNotIn("legado", out.split("migrações")[0])
        self.assert_knowledge_intact(before, t, env)
        run = self.run_json(t)
        self.assertEqual(run["skill_version"], NEXT)
        self.assertEqual([h["to"] for h in run["upgrade_history"]], [self.current, NEXT])
        self.assertEqual(run["upgrade_history"][-1]["migrations"], [NEXT])   # só o intervalo (atual, NEXT]
        self.assertTrue(os.path.isdir(os.path.join(t, STATE_DIR, "backups",
                                                   "upgrade-%s-%s" % (self.current, NEXT))))

    def test_upgrade_2_board_events_memory_survive(self):
        """iter10: a base já está em árvore (MIGRATE-1). Eventos onde o motor os fixa (hcore.state_paths), itens
        da árvore (state/ backlog/ archive/) e memória byte a byte depois de um upgrade que não mexe no estado."""
        t = self.copy(self.base)
        env, _ = self.next_env([{"kind": "harness"}, {"kind": "emit"}])
        sp = os.path.join(t, STATE_DIR)
        sys.path.insert(0, os.path.join(SCRIPTS, "harness", "engine"))
        import hcore
        ev_rel = os.path.relpath(hcore.state_paths(t)["events"], sp)
        tree = tuple(d + os.sep for d in ("state", "backlog", "archive"))
        keep = {k: v for k, v in tree_hash(sp).items()
                if k.startswith("memory" + os.sep) or k == ev_rel
                or (k.startswith(tree) and os.path.basename(k) not in (".lock", "ledger.jsonl"))}
        self.assertIn(ev_rel, keep)
        self.assertTrue(any(k.startswith("memory") for k in keep))
        rc, out, err = cs(t, "upgrade", "--apply", "--allow-outside", env=env)
        self.assertEqual(rc, 0, out + err)
        after = tree_hash(sp)
        self.assertEqual({k: after.get(k) for k in keep}, keep)
        rc, out, err = cs(t, "harness", "validate", "--strict", "--allow-empty", env=env)   # cadeia de hash
        self.assertEqual(rc, 0, out + err)
        events, cerr, _ = hcore.read_chain(hcore.state_paths(t)["events"])
        self.assertEqual(cerr, [])
        self.assertTrue(events)

    def test_upgrade_3_plan_writes_nothing(self):
        t = self.copy(self.legacy)
        before = tree_hash(t, skip=())
        rc, out, err = cs(t, "upgrade", env=clean_env())
        self.assertEqual(rc, 0, out + err)
        self.assertIn("partindo de repositório legado", out)
        self.assertIn("fora de .specialists/", out)
        self.assertIn("preservado", out)
        self.assertEqual(tree_hash(t, skip=()), before)
        # --apply sem --allow-outside, com escrita fora pendente: recusa sem escrever nada
        rc, out, err = cs(t, "upgrade", "--apply", env=clean_env())
        self.assertEqual(rc, 3, out + err)
        self.assertEqual(tree_hash(t, skip=()), before)

    def test_upgrade_4_failed_verification_restores_backup(self):
        t = self.copy(self.base)
        env, d = self.next_env([{"kind": "schema", "script": "break.py"}, {"kind": "harness"}])
        with open(os.path.join(d, "break.py"), "w") as fh:
            fh.write("import os, sys\nt = sys.argv[sys.argv.index('--target') + 1]\n"
                     "open(os.path.join(t, 'CLAUDE.md'), 'a').write('\\nquebrado pelo teste\\n')\n"
                     "a = sorted(os.listdir(os.path.join(t, '.claude', 'agents')))[0]\n"
                     "open(os.path.join(t, '.claude', 'agents', a), 'a').write('\\neditado\\n')\n"
                     "open(os.path.join(t, '.claude', 'novo-lixo.md'), 'w').write('x')\n"
                     "open(os.path.join(t, %r, 'memory', 'lixo.txt'), 'w').write('x')\n"
                     "os.remove(os.path.join(t, %r, 'interview.jsonl'))\n" % (STATE_DIR, STATE_DIR))
        before = tree_hash(t, skip_backups=True)
        rc, out, err = cs(t, "upgrade", "--apply", "--allow-outside", env=env)
        self.assertEqual(rc, 1, out + err)
        self.assertIn("backup restaurado", err)
        self.assertEqual(tree_hash(t, skip_backups=True), before)
        self.assertEqual(self.run_json(t)["skill_version"], self.current)

    def test_upgrade_5_scan_layer_redoes_only_that_layer(self):
        t = self.copy(self.base)
        env, _ = self.next_env([{"kind": "scan", "layers": ["L2"]}])
        fdir = os.path.join(t, STATE_DIR, "facts")
        before = {f: sha(os.path.join(fdir, f)) for f in os.listdir(fdir) if f.endswith(".json5")}
        index_before = json5io.read(os.path.join(fdir, "index.json5"))
        arch = os.path.join(fdir, "architecture.json5")
        ino = os.stat(arch).st_ino
        rc, out, err = cs(t, "upgrade", "--apply", "--allow-outside", env=env)
        self.assertEqual(rc, 0, out + err)
        self.assertIn("scan --layers L2", out)
        after = {f: sha(os.path.join(fdir, f)) for f in os.listdir(fdir) if f.endswith(".json5")}
        self.assertEqual(set(after), set(before))
        redo = ("architecture.json5", "index.json5")
        self.assertEqual({f: h for f, h in after.items() if f not in redo},
                         {f: h for f, h in before.items() if f not in redo})
        # index.json5 é reconstruído por todo scan: mesmo conteúdo (id → camada); só o cabeçalho pode variar
        self.assertEqual(json5io.read(os.path.join(fdir, "index.json5")), index_before)
        self.assertNotEqual(os.stat(arch).st_ino, ino)             # L2 foi regravada (escrita atômica)
        with open(os.path.join(t, STATE_DIR, "state", "ledger.jsonl")) as fh:
            scans = [r for r in (json.loads(l) for l in fh if l.strip()) if r.get("event") == "scan"]
        self.assertEqual(scans[-1]["layers"], ["L2"])

    def test_upgrade_6_legacy_target(self):
        t = self.copy(self.legacy)
        before = self.knowledge_snapshot(t, LEGACY_STATE_DIR)       # foto inicial: alvo ainda legado
        rc, out, err = cs(t, "upgrade", "--apply", "--allow-outside", env=clean_env())
        self.assertEqual(rc, 0, out + err)
        self.assertIn("partindo de repositório legado", out)
        self.assert_knowledge_intact(before, t, clean_env())
        run = self.run_json(t)
        self.assertEqual(run["skill_version"], self.current)
        h = run["upgrade_history"]
        self.assertEqual(len(h), 1)
        self.assertEqual(h[0]["from"], "0.0.0-legado")
        self.assertTrue(h[0]["legacy"])
        rc, out, err = cs(t, "upgrade", env=clean_env())
        self.assertIn("nada a fazer", out)

    def test_rename_dir_only_moves_this_skill_legacy_dir(self):
        """rename-dir (SWARM-DIR-3, DEC-SWARM-DIR) só renomeia o legado DESTA skill (.specialists → .swarm).
        Qualquer parâmetro que aponte outra pasta continua recusado (exit 2) sem escrever nada."""
        t = self.copy(self.base)
        for bad in ({"kind": "rename-dir", "from": "src", "to": "lib"},
                    {"kind": "rename-dir", "to": ".outra-pasta"},
                    {"kind": "rename-dir", "from": ".claude"}):
            env, _ = self.next_env([bad])
            before = tree_hash(t)
            rc, out, err = cs(t, "upgrade", "--apply", "--allow-outside", env=env)
            self.assertEqual(rc, 2, "rename-dir com %r deveria ser recusado: %s" % (bad, out + err))
            self.assertEqual(tree_hash(t), before)
        t = self.copy(self.legacy)
        env, _ = self.next_env([{"kind": "rename-dir"}])
        rc, out, err = cs(t, "upgrade", "--apply", "--allow-outside", env=env)
        self.assertEqual(rc, 0, out + err)
        self.assertFalse(os.path.lexists(os.path.join(t, ".specialists")), "legado sobrou após rename-dir")
        run = json5io.read(os.path.join(t, ".swarm", "run.json5"))
        self.assertEqual(run["skill_version"], NEXT)
        self.assertIn("rename-dir", run["upgrade_history"][-1]["actions"])


class PreservedGuard(unittest.TestCase):
    """Sem ação explícita (schema|cards|probes), mexer em entrevista/aprovações/board/memória reprova o upgrade."""

    def test_violation_detected(self):
        from upgrade import core
        d = tempfile.mkdtemp(prefix="cs-pres-")
        self.addCleanup(shutil.rmtree, d, True)
        sp = os.path.join(d, ".specialists")
        os.makedirs(os.path.join(sp, "memory", "agents"))
        os.makedirs(os.path.join(sp, "state"))
        for rel in ("interview.jsonl", os.path.join("memory", "agents", "a.jsonl"),
                    os.path.join("state", "events.jsonl")):
            with open(os.path.join(sp, rel), "w") as fh:
                fh.write("{}\n")
        before = core.preserved_snapshot(d)
        self.assertEqual(len(before), 3)
        self.assertEqual(core.preserved_violations(before, core.preserved_snapshot(d)), [])
        with open(os.path.join(sp, "memory", "agents", "a.jsonl"), "a") as fh:
            fh.write("{}\n")
        os.remove(os.path.join(sp, "interview.jsonl"))
        self.assertEqual(core.preserved_violations(before, core.preserved_snapshot(d)),
                         ["interview.jsonl", os.path.join("memory", "agents", "a.jsonl")])


if __name__ == "__main__":
    unittest.main()
