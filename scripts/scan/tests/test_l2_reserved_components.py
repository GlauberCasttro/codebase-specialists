"""L2: prefixos reservados ao harness/plataformas (cslib/paths.RESERVED_PREFIXES: `.claude/`, `.cursor/`, `.codex/`,
`.github/agents/`, `scripts/harness/`...) não contam como componente de topo do produto.

Defeito medido (iteração 4, ts-shop-setup-vague/with_skill): depois do harness instalado, o rescan dizia
"5 componentes de topo" — `.claude` (por `.claude/hooks/cs-guard.sh`) entrava ao lado de `.`, apps/web,
packages/api e packages/shared."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_precision import build, load, scan  # noqa: E402
import synth  # noqa: E402

# Alvo real (ts-shop com harness instalado por uma execução anterior); opcional — sem ele o teste é PULADO.
TS_SHOP = os.environ.get("CS_TS_SHOP_TARGET") or ""

SYN = {
    "package.json": "{\"name\": \"shop\", \"private\": true}\n",
    "eslint.config.mjs": "export default [];\n",
    "packages/shared/src/sku.ts": "export const sku = (s: string) => s.trim();\n",
    "packages/api/src/server.ts": "import { sku } from '../../shared/src/sku';\nexport const run = () => sku(' a ');\n",
    "apps/web/src/main.ts": "import { sku } from '../../../packages/shared/src/sku';\nexport const m = sku('x');\n",
    ".claude/hooks/cs-guard.sh": "#!/bin/sh\nexec python3 \"$CLAUDE_PROJECT_DIR/.swarm/harness/guard.py\"\n",
    ".claude/hooks/helper.py": "import os\n\n\ndef f():\n    return os.getcwd()\n",
    ".cursor/hooks/cs-guard.sh": "#!/bin/sh\necho ok\n",
    ".codex/hooks/x.py": "def g():\n    return 1\n",
    "scripts/harness/engine.py": "def h():\n    return 2\n",
}


def components(root):
    return load(root, "architecture")["components"]


def claim(root):
    return [f for f in load(root, "architecture")["facts"] if f["id"] == "arch.components"][0]["claim"]


class ReservedNotComponent(unittest.TestCase):
    root = None

    def tearDown(self):
        if self.root:
            shutil.rmtree(os.path.dirname(self.root) if self.root.endswith("/target") else self.root,
                          ignore_errors=True)

    def test_synthetic_reserved_prefixes_are_not_components(self):
        self.root = build(SYN)
        scan(self.root, "--no-exec", "--layers", "L0,L1,L2")
        comps = components(self.root)
        for c in comps:
            self.assertFalse(c.startswith((".claude", ".cursor", ".codex", "scripts")), comps)
        self.assertNotIn("arch.deps.claude", [f["id"] for f in load(self.root, "architecture")["facts"]])

    @unittest.skipUnless(bool(TS_SHOP) and os.path.isdir(TS_SHOP), "alvo ts-shop ausente (defina $CS_TS_SHOP_TARGET)")
    def test_ts_shop_has_4_components_not_5(self):
        # só LÊ o alvo: cópia para tmp (sem .git e sem .swarm), git novo, scan na cópia
        self.root = os.path.join(tempfile.mkdtemp(prefix="cs-l2-"), "target")
        shutil.copytree(TS_SHOP, self.root, symlinks=True,
                        ignore=lambda d, names: [n for n in names if n in (".git", ".swarm")]
                        if os.path.realpath(d) == os.path.realpath(TS_SHOP) else [])
        self.assertTrue(os.path.isfile(os.path.join(self.root, ".claude", "hooks", "cs-guard.sh")))
        synth.git(self.root, "init", "-q")
        synth.commit(self.root, "init")
        scan(self.root, "--no-exec", "--layers", "L0,L1,L2")
        self.assertEqual(components(self.root), [".", "apps/web", "packages/api", "packages/shared"])
        self.assertTrue(claim(self.root).startswith("4 componentes de topo"), claim(self.root))


if __name__ == "__main__":
    unittest.main()
