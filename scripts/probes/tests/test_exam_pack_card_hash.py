"""O pacote de exame (`probes exam-pack`) grava `card_sha256` (mesmo hash de cards/status.json5 e dos ciclos de
final.py). `probes check` recusa como OBSOLETO o exame cujo pacote foi emitido para outro cartão (reexame)."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_final as TF  # noqa: E402
from test_final import cs  # noqa: E402
import test_iter5_exam_card_hash as T5  # noqa: E402

from team._shared_tmp.common import read_json, sp_path  # noqa: E402

A = "dev-billing"


class PackBoundToCard(unittest.TestCase):
    setUp = TF.FinalTest.setUp
    tearDown = TF.FinalTest.tearDown
    exams = TF.FinalTest.exams
    put_card = T5.ExamBoundToCard.put_card

    def pack(self):
        code, o, e = cs(self.root, "probes", "exam-pack", A)
        self.assertEqual(code, 0, o + e)
        return read_json(sp_path(self.root, "probes", "exams", "%s.questions.json5" % A))

    def test_pack_records_card_hash_and_check_refuses_obsolete(self):
        self.exams("ph1")
        self.put_card(A, "Mantém billing correto.")
        pack = self.pack()
        st = read_json(sp_path(self.root, "cards", "status.json5"))[A]
        recs = [st.get("drafted") or {}, st.get("revised") or {}] + list(st.get("refines") or []) + list(
            st.get("existence_fixes") or [])
        self.assertIn(pack["card_sha256"], [r.get("sha256") for r in recs])
        from probes.final import card_shas
        self.assertEqual(pack["card_sha256"], card_shas(self.root)[A])
        # cartão inalterado: exame aceito e o ciclo carrega o MESMO hash
        code, o, e = cs(self.root, "probes", "check", A)
        self.assertEqual(code, 0, o + e)
        cyc = read_json(sp_path(self.root, "probes", "cycles.json5"))[A]
        self.assertEqual(cyc[-1]["card_sha256"], pack["card_sha256"])
        n = len(cyc)
        # cartão muda depois do exam-pack → exame obsoleto, recusado sem registrar
        self.put_card(A, "Mantém billing correto (mudou depois do pacote).")
        code, o, e = cs(self.root, "probes", "check", A)
        self.assertEqual(code, 1, o + e)
        self.assertIn("obsoleto", e)
        self.assertEqual(len(read_json(sp_path(self.root, "probes", "cycles.json5"))[A]), n)
        code, o, e = cs(self.root, "probes", "check", "--all", "--final")
        self.assertEqual(code, 1, o + e)
        self.assertIn("obsoleto", o + e)
        # reexame: pacote novo do cartão atual → aceito
        pack2 = self.pack()
        self.assertNotEqual(pack2["card_sha256"], pack["card_sha256"])
        code, o, e = cs(self.root, "probes", "check", A)
        self.assertEqual(code, 0, o + e)

    def test_isolated_pack_manifest_has_card_hash(self):
        self.exams("ph2")
        out = os.path.join(self.root, ".swarm", "tmp", "exam", A)
        code, o, e = cs(self.root, "probes", "exam-pack", A, "--out", out)
        self.assertEqual(code, 0, o + e)
        from probes.final import card_shas
        man = read_json(os.path.join(out, "exam.json5"))
        self.assertIn("card_sha256", man)
        self.assertEqual(man["card_sha256"], card_shas(self.root).get(A))

    def test_pack_without_hash_is_legacy(self):
        self.exams("ph3")
        from probes.final import pack_card_drift
        self.assertIsNone(pack_card_drift(self.root, A))  # sem pacote
        self.pack()
        p = sp_path(self.root, "probes", "exams", "%s.questions.json5" % A)
        from team._shared_tmp.common import write_json
        doc = read_json(p)
        doc.pop("card_sha256")
        write_json(self.root, p, doc)
        self.put_card(A, "qualquer")
        self.assertIsNone(pack_card_drift(self.root, A))


if __name__ == "__main__":
    unittest.main()
