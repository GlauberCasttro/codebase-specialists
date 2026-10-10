"""Mede o oráculo por requisito: `python3 medir.py` (usa $CS_SKILL_DIR como o test_iter21; padrão: este projeto).
Imprime uma linha por teste (requisito, tipo D/R, resultado, id) e o placar por requisito.
Tipo: R = não-regressão/sem brecha (nome com regressao|controle|continua|intacta) — passa hoje e depois;
      D = defeito — falha no HEAD da abertura da frente e passa depois da correção."""
import os
import re
import sys
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

ORDER = ["M%d" % i for i in range(1, 14)]
R_KIND = re.compile(r"regressao|controle|continua|intacta")


def req_of(tid):
    m = re.search(r"\.TestM(\d+)", tid)
    return "M%s" % m.group(1) if m else "?"


def kind_of(tid):
    return "R" if R_KIND.search(tid.rsplit(".", 1)[-1]) else "D"


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
    suite = unittest.defaultTestLoader.loadTestsFromName("test_iter21")
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
            cls = tid.rsplit(".", 1)[0].rsplit(".", 1)[-1]
            st[tid] = "ERROR" if any(cls in k for k, v in st.items() if v == "ERROR") else "?"
    score = {}
    for tid in ids:
        r, k = req_of(tid), kind_of(tid)
        print("%-4s %s %-5s %s" % (r, k, st[tid], tid.replace("test_iter21.", "")))
        s = score.setdefault(r, {"ok": 0, "n": 0, "D": [0, 0], "R": [0, 0]})
        good = st[tid] == "ok"
        s["ok"] += good
        s["n"] += 1
        s[k][0] += good
        s[k][1] += 1
    for e in [k for k, v in st.items() if v == "ERROR" and k not in ids]:
        print("ERRO   %s" % e)
    print("placar: " + "  ".join("%s %d/%d" % (r, score[r]["ok"], score[r]["n"]) for r in ORDER if r in score))
    print("por tipo (passam/total): " + "  ".join("%s D %d/%d R %d/%d" % (r, score[r]["D"][0], score[r]["D"][1],
                                                                             score[r]["R"][0], score[r]["R"][1])
                                                 for r in ORDER if r in score))
    tot = sum(v["ok"] for v in score.values()), sum(v["n"] for v in score.values())
    print("total: %d/%d passam" % tot)
    return 0


if __name__ == "__main__":
    sys.exit(main())
