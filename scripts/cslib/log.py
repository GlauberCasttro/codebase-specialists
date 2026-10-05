"""Ledger append-only em <alvo>/.swarm/state/ledger.jsonl.

Todo bloqueio, kill-switch e execução de fase grava uma linha. Campos: ts (UTC ISO-8601), event,
actor + campos livres (JSON-serializáveis). O ledger NÃO entra em comparação de determinismo.
"""

import datetime
import os

from . import jsonio
from . import paths


def ledger_path(target):
    return os.path.join(paths.state_dir(target), "ledger.jsonl")


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def ledger(target, event, actor="cs.py", **fields):
    rec = {"ts": now_iso(), "event": event, "actor": actor}
    rec.update(fields)
    jsonio.append_jsonl(ledger_path(target), rec, target=target)
    return rec


def read_ledger(target):
    p = ledger_path(target)
    if not os.path.exists(p):
        return []
    import json
    out = []
    with open(p, "rb") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line.decode("utf-8")))
    return out
