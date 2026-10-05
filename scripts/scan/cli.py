"""`cs.py scan` — roda camadas L0–L10 e grava <alvo>/.swarm/facts/<camada>.json5 + index.json5.

Tudo é computado ANTES de qualquer escrita: se uma camada falha, nada é gravado (exceto blobs de
evidência de comandos executados, que são endereçados por conteúdo e idempotentes).
"""

import os
import sys

from cslib import CsError, SCHEMA_VERSION, gitx, json5io, log, paths
from cslib.evidence import validate_fact
from . import LAYERS
from .context import LAYER_MODULES, Options, ScanContext

GENERATOR = "cs.py scan (codebase-specialists)"
ALL_KEYS = [k for k, _ in LAYERS]
NAME_TO_KEY = {}
for _k, _n in LAYERS:
    NAME_TO_KEY[_n] = _k
    NAME_TO_KEY[_k.lower()] = _k
NAME_TO_KEY.update({"glossary": "L9", "business_rules": "L9", "stack_graph": "L8"})


def parse_layers(spec):
    if not spec:
        return list(ALL_KEYS)
    out = []
    for raw in spec.split(","):
        r = raw.strip()
        if not r:
            continue
        key = r.upper() if r.upper() in LAYER_MODULES else NAME_TO_KEY.get(r.lower())
        if key is None:
            raise CsError("camada desconhecida: %s" % r,
                          "use --layers com %s (ou nomes: %s)" % (",".join(ALL_KEYS),
                                                                  ", ".join(n for _, n in LAYERS)))
        if key not in out:
            out.append(key)
    return sorted(out, key=ALL_KEYS.index)


def outputs_of(key, result):
    """[(nome_do_arquivo_sem_ext, dict)] de um resultado de camada."""
    if "_outputs" in result:
        return sorted(result["_outputs"].items())
    return [(result["layer"], result)]


def header_for(name, key):
    return "%s (%s) — fatos mecânicos do scan; gerado por %s; não editar à mão" % (name, key, GENERATOR)


def scan(target, layers, opts):
    ctx = ScanContext(target, opts)
    commit = gitx.head(ctx.target)
    produced = []
    for key in layers:
        try:
            result = ctx.layer(key)
        except CsError:
            raise
        except Exception as exc:  # bug de camada: falha alta com contexto
            if os.environ.get("CS_DEBUG"):
                raise
            raise CsError("camada %s (%s) falhou: %s: %s" % (key, dict(LAYERS)[key],
                                                             type(exc).__name__, exc),
                          "rode só as outras camadas (--layers) e reporte o erro com o traceback "
                          "(CS_DEBUG=1 mostra)")
        for name, data in outputs_of(key, result):
            facts = data.get("facts") or []
            if not facts:
                raise CsError("camada %s produziu %s sem nenhum fato" % (key, name),
                              "bug: toda camada deve produzir ≥1 fato (inclusive de ausência)")
            errs = [e for f in facts for e in validate_fact(f)]
            if errs:
                raise CsError("camada %s produziu fatos inválidos: %s" % (key, "; ".join(errs[:5])),
                              "bug do produtor da camada")
            doc = dict(data)
            doc["layer"] = name
            doc.update({"schema_version": SCHEMA_VERSION, "scan_key": key, "generator": GENERATOR,
                        "repo_commit": commit})
            produced.append((key, name, doc))
    fdir = paths.facts_dir(ctx.target)
    for key, name, doc in produced:
        json5io.dump(doc, os.path.join(fdir, name + ".json5"), header_for(name, key), target=ctx.target)
    index = rebuild_index(ctx.target)
    log.ledger(ctx.target, "scan", actor="cs.py scan",
               layers=layers, files={name: len(doc["facts"]) for _, name, doc in produced},
               no_exec=opts.no_exec, commit=commit)
    return ctx, produced, index


def rebuild_index(target):
    """index.json5 = {id: camada} de TODOS os facts/*.json5 presentes (ordem determinística)."""
    fdir = paths.facts_dir(target)
    index = {}
    for fn in sorted(os.listdir(fdir)):
        if not fn.endswith(".json5") or fn == "index.json5":
            continue
        data = json5io.read(os.path.join(fdir, fn))
        for f in data.get("facts") or []:
            fid = f.get("id")
            if fid in index:
                raise CsError("id de fato duplicado entre camadas: %s (%s e %s)" % (fid, index[fid],
                                                                                   data.get("layer")),
                              "apague .swarm/facts/ e rode `cs.py scan` completo")
            index[fid] = data.get("layer")
    json5io.dump(index, os.path.join(fdir, "index.json5"), paths.FACTS_INDEX_HEADER, target=target)
    return index


OUTPUT_FILES = {"L8": ["stack", "stack_graph"], "L9": ["business_rules", "glossary"]}


def check_outputs(target, layers):
    """`scan --check`: confere (sem re-escanear) que cada camada pedida tem arquivo legível, ≥1 fato
    válido e todos os ids no index.json5. Falha → CsError(code=1) com o item."""
    fdir = paths.facts_dir(target)
    index = json5io.read(os.path.join(fdir, "index.json5"))
    head = gitx.head(target)
    problems, ok = [], []
    for key in layers:
        for name in OUTPUT_FILES.get(key, [dict(LAYERS)[key]]):
            p = os.path.join(fdir, name + ".json5")
            data = json5io.read(p, required=False)
            if data is None:
                problems.append("%s: %s.json5 ausente" % (key, name))
                continue
            facts = data.get("facts") or []
            errs = [e for f in facts for e in validate_fact(f)]
            missing = [f["id"] for f in facts if f.get("id") not in index]
            if not facts:
                problems.append("%s: %s sem fatos" % (key, name))
            elif errs:
                problems.append("%s: %s com fatos inválidos (%s)" % (key, name, errs[0]))
            elif missing:
                problems.append("%s: %d ids fora do index.json5 (ex.: %s)" % (key, len(missing), missing[0]))
            else:
                stale = data.get("repo_commit") != head
                ok.append("%s %s: %d fatos%s" % (key, name, len(facts),
                                                 " (AVISO: scan de outro commit)" if stale else ""))
    for line in ok:
        sys.stdout.write("ok " + line + "\n")
    if problems:
        raise CsError("scan --check falhou: " + "; ".join(problems),
                      "rode `cs.py scan --layers %s`" % ",".join(layers), code=1)
    return 0


def handler(args):
    layers = parse_layers(args.layers)
    if args.check:
        return check_outputs(args.target, layers)
    opts = Options(no_exec=args.no_exec, timeout=args.timeout, max_commits=args.max_commits,
                   max_deps=args.max_deps, max_exec=args.max_exec,
                   introspect=not args.no_introspect)
    if args.timeout <= 0:
        raise CsError("--timeout deve ser > 0", "ex.: --timeout 300")
    ctx, produced, index = scan(args.target, layers, opts)
    for key, name, doc in produced:
        extra = ""
        if name == "inventory":
            extra = " (%d arquivos; ignorados: %s)" % (
                len(doc["files"]), ", ".join("%s=%d" % (c, sum(v.values()))
                                            for c, v in sorted(doc["ignored"].items())) or "nenhum")
        elif name == "operations":
            extra = " (%s)" % ", ".join("%s=%d" % kv for kv in sorted(doc["summary"].items()))
        sys.stdout.write("%-3s %-15s %4d fatos → .swarm/facts/%s.json5%s\n" % (
            key, name, len(doc["facts"]), name, extra))
    sys.stdout.write("index: %d fatos → .swarm/facts/index.json5\n" % len(index))
    return 0


def register(subparsers):
    p = subparsers.add_parser("scan", help="escaneia o alvo (L0–L10) → .swarm/facts/*.json5",
                              description=__doc__)
    p.add_argument("--layers", default=None,
                   help="camadas separadas por vírgula (default: todas). Ex.: L0,L1,L5")
    p.add_argument("--no-exec", action="store_true",
                   help="não executa comandos do alvo (L7 fica declared; L8 sem introspecção)")
    p.add_argument("--no-introspect", action="store_true", help="L8 sem introspecção de API")
    p.add_argument("--timeout", type=int, default=300, help="timeout por comando executado (s)")
    p.add_argument("--max-commits", type=int, default=2000, help="commits lidos em L5/L6")
    p.add_argument("--max-deps", type=int, default=8, help="dependências críticas introspectadas (L8)")
    p.add_argument("--max-exec", type=int, default=12, help="máximo de comandos executados (L7)")
    p.add_argument("--check", action="store_true",
                   help="não escaneia: confere que as camadas pedidas já existem, válidas e indexadas")
    p.set_defaults(func=handler)
    return p
