"""Mede o oráculo por requisito: `python3 medir.py` (usa $CS_SKILL_DIR como o test_uso_real).
Imprime uma linha por teste (requisito, id, resultado) e o placar por requisito."""
import os
import sys
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# (requisito, predicado sobre o id do teste) — a 1ª regra que casa vence
RULES = [
    ("U12", lambda i: ".TestU12" in i), ("U11", lambda i: ".TestU11" in i), ("U6", lambda i: ".test_u6_" in i), ("U7", lambda i: ".test_u7_" in i),
    ("U1", lambda i: ".TestU1" in i),
    ("U2b", lambda i: ".test_u2b_" in i), ("U2", lambda i: ".TestU2" in i),
    ("U3", lambda i: ".TestU3" in i), ("U4", lambda i: ".TestU4" in i),
    ("U8", lambda i: ".test_u8_" in i), ("U9", lambda i: ".test_u9_" in i), ("U10", lambda i: ".test_u10_" in i),
    ("U5", lambda i: ".TestU5" in i),
]
ORDER = ["U1", "U2", "U2b", "U3", "U4", "U5", "U6", "U7", "U8", "U9", "U10", "U11", "U12"]


def req_of(tid):
    for r, f in RULES:
        if f(tid):
            return r
    return "?"


class Rec(unittest.TextTestResult):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.status = {}

    def addSuccess(self, t):
        super().addSuccess(t)
        self.status[t.id()] = "ok"

    def addFailure(self, t, err):
        super().addFailure(t, err)
        self.status[t.id()] = "FAIL"

    def addError(self, t, err):
        super().addError(t, err)
        self.status[getattr(t, "id", lambda: str(t))()] = "ERROR"


def main():
    suite = unittest.defaultTestLoader.loadTestsFromName("test_uso_real")
    ids = []

    def walk(s):
        for x in s:
            if isinstance(x, unittest.TestSuite):
                walk(x)
            else:
                ids.append(x.id())
    walk(suite)
    with open(os.devnull, "w") as dn:
        res = unittest.TextTestRunner(stream=dn, resultclass=Rec, verbosity=0).run(suite)
    st = dict(res.status)
    for tid in ids:  # erro de setUpClass derruba a classe inteira
        if tid not in st:
            cls = tid.rsplit(".", 1)[0]
            st[tid] = "ERROR" if any(cls.rsplit(".", 1)[-1] in k for k, v in st.items() if v == "ERROR") else "?"
    score = {}
    for tid in ids:
        r = req_of(tid)
        print("%-4s %-5s %s" % (r, st[tid], tid.replace("test_uso_real.", "")))
        ok, n = score.get(r, (0, 0))
        score[r] = (ok + (st[tid] == "ok"), n + 1)
    errs = [k for k, v in st.items() if v == "ERROR" and k not in ids]
    for e in errs:
        print("ERRO   %s" % e)
    print("placar: " + "  ".join("%s %d/%d" % (r, score[r][0], score[r][1]) for r in ORDER if r in score))
    tot = sum(v[0] for v in score.values()), sum(v[1] for v in score.values())
    print("total: %d/%d passam" % tot)
    return 0


if __name__ == "__main__":
    sys.exit(main())
