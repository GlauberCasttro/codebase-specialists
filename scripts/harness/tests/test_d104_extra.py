"""D-1-04 extra: 2º legacy-ack só com algo NOVO a reconhecer; caducidade quando o item muda; cs-state validate."""
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import fixture  # noqa: E402,F401
import engine  # noqa: E402
from engine import Event, ref  # noqa: E402
from fixture import A  # noqa: E402
from test_legacy_hierarquia import Base, old_motor_start  # noqa: E402


class TestSegundoAck(Base):
    def test_segundo_ack_so_com_novidade(self):
        self.ack()
        self.refused("legacy-ack", "--reason", "nada novo")
        old_motor_start(self.root, "story", "US-2")
        self.assert_invalid("story US-2 IN_PROGRESS com feature FEAT-2 em BACKLOG")
        out = self.ok("legacy-ack", "--reason", "segundo legado")
        self.assertIn("US-2", out)
        acks = self.ack_events()
        self.assertEqual(len(acks), 2)
        hier = acks[1]["data"]["args"]["hierarchy"]
        self.assertEqual([(h["id"], h["parent"]) for h in hier], [("US-2", "FEAT-2")])  # US-3 já reconhecida
        self.assert_valid()
        self.refused("legacy-ack", "--reason", "de novo")

    def test_reconhecimento_caduca_quando_o_pai_muda(self):
        self.ack()
        self.assert_valid()
        # o pai sai de BACKLOG (por op direta, como faria um hotfix): a incoerência agora é OUTRA (FEAT-2 READY)
        engine.commit(self.root, A, lambda ctx: [Event("feature.ready", "FEAT-2",
                                                       [["set", ref("feature", "FEAT-2"), "state", "READY"]])])
        self.assert_invalid("story US-3 IN_PROGRESS com feature FEAT-2 em READY")


if __name__ == "__main__":
    unittest.main()
