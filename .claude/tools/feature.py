#!/usr/bin/env python3
"""feature.py — o controlador da FEATURE do harness de desenvolvimento (skills criar-feature, fechar-feature, tech-lead).

Uma feature = uma mudança na skill = uma campanha no motor embutido (`campanhas/<id>/`). O estado vive em
`.claude/state/` (features.json, features/<id>/, logs/<id>/, archive/<id>/) e SÓ este script o transita; o hook
`guard-estado.py` nega a escrita direta do que é do script. JSON decide; Markdown explica.

Subcomandos:
  status [--json|--brief]                         features ativas (k/t), criação em curso, entregues, WORKFLOW em dia
  criar iniciar <id> --demanda TXT [--dry-run]    E0: pré-condição mecânica; cria eventos.jsonl + CHECKLIST.md
                                                   (mesma id + mesma demanda = retomada; imprime a próxima etapa)
  criar propor <id> --etapa EN [--arquivo ARQ] [--json]
                                                   valida o artefato da etapa corrente (contrato.py) e registra o sha
  criar aprovar <id> --etapa EN --sha SHA --palavra TXT --produzido TXT --proxima TXT [--medido TXT] [--itens TXT]
                                                   marca a caixa com a palavra LITERAL do founder (ok|sim|aprovo…)
  criar rejeitar <id> --etapa EN [--sha SHA] --motivo TXT
                                                   registra a rejeição (append-only); a caixa continua vazia
  criar abrir <id> [--dry-run] [--json]           E1–E5 aprovadas + sha + contrato + overlap ⇒ ac.py init, INDEX,
                                                   HISTORICO, log, features.json, WORKFLOW, README de campanhas
                                                   (nunca commita; não gera o script de aprovação)
  checklist <id> [--json]                         0 = CHECKLIST.md é a projeção exata dos eventos; 2 = adulterado
  adotar <id> [--dry-run]                         campanha existente e não concluída entra como ativa `legado`
  task marcar <id> <task> --status S --gate G [--nota TXT]
                                                   DONE exige gate PASS e Handoff preenchido; atualiza INDEX/HISTORICO
  fechar plano <id> --json                        etapas archive|entrega|limpar|idle feitas (pós-condição no disco)
  fechar check <id> [--json]                      gate de aceite e completude cruzada; NUNCA escreve
  fechar archive <id> --notas ARQ                 documento único archive/<id>/<id>.md (+ marcador em escrita própria)
  fechar entrega|limpar|idle <id>                 LAST_DELIVERY · remove features/<id> e logs/<id> · IDLE em features.json
  fechar commit <id> --mensagem ARQ [--decisions ARQ] [--dry-run] [--json]
                                                   commit SÓ da feature num índice temporário; nunca push
Saída: texto, --json ou --brief (≤ 40 linhas). Exit: 0 ok · 1 recusa (pré-condição/ordem/aprovação/gate) ·
2 lacunas do contrato · 3 uso. Nunca roda gate/preauth/frase do motor (são do founder, no terminal dele).
Variáveis de teste: CS_DEV_SKILL_DIR (raiz do projeto), CS_DEV_AC (motor; o --json de status/abrir mostra qual).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import contrato as C  # noqa: E402
import estado_lib as L  # noqa: E402

APROVA = re.compile(r"^\s*(ok|sim|aprovo|aprovado|aprovada)\b", re.I)


class Recusa(Exception):
    def __init__(self, msg, code=1, lacunas=None):
        Exception.__init__(self, msg)
        self.code = code
        self.lacunas = lacunas or []


# ------------------------------------------------------------------ CHECKLIST (projeção dos eventos)

def projetar_checklist(fid, ev):
    ini = next((e for e in ev if e.get("tipo") == "inicio"), {})
    ap = L.aprovadas(ev)
    linhas = ["# CHECKLIST — criação da feature %s" % fid, "",
              "<!-- gerado por .claude/tools/feature.py a partir de eventos.jsonl; não edite à mão (o hook nega; "
              "`feature.py checklist` detecta adulteração) -->", "",
              'Demanda: "%s"' % ini.get("demanda", ""), ""]
    linhas.append("- [x] **E0 — %s** · OK %s" % (L.NOMES_ETAPA["E0"], ini.get("ts", "?")))
    for e in L.ETAPAS:
        if e in ap:
            linhas.append("- [x] **%s — %s** · OK %s · sha %s" % (e, L.NOMES_ETAPA[e], ap[e]["ts"], ap[e]["sha"][:12]))
        else:
            pend = L.proposta_pendente(ev, e)
            extra = " · proposta %s aguardando decisão" % pend["sha"][:12] if pend else ""
            linhas.append("- [ ] **%s — %s**%s" % (e, L.NOMES_ETAPA[e], extra))
    ab = next((e for e in ev if e.get("tipo") == "abertura"), None)
    linhas.append("- [%s] **Abertura** (ac.py init, INDEX, HISTORICO, WORKFLOW)%s"
                  % ("x" if ab else " ", " · %s" % ab["ts"] if ab else ""))
    linhas += ["", "## Handoffs", "<!-- APPEND-ONLY: uma entrada por decisão; nunca reescrita -->", ""]
    for e in ev:
        t = e.get("tipo")
        if t == "inicio":
            linhas += ["### E0 — %s · CONCLUÍDA %s" % (L.NOMES_ETAPA["E0"], e["ts"]),
                       '- Demanda: "%s"' % e.get("demanda", ""), "- Próxima: E1 — %s" % L.NOMES_ETAPA["E1"], ""]
        elif t == "aprovacao":
            linhas.append("### %s — %s · CONCLUÍDA %s" % (e["etapa"], L.NOMES_ETAPA[e["etapa"]], e["ts"]))
            linhas.append("- Produzido: %s" % e.get("produzido", ""))
            if e.get("medido"):
                linhas.append("- Medido: %s" % e["medido"])
            if e.get("itens"):
                linhas.append("- Itens aprovados: %s" % e["itens"])
            linhas.append('- Aprovação: "%s"' % e.get("palavra", ""))
            linhas.append("- Sha: %s" % e.get("sha", ""))
            linhas.append("- Próxima: %s" % e.get("proxima", ""))
            linhas.append("")
        elif t == "rejeicao":
            linhas += ["### %s — REJEITADA %s · motivo: %s" % (e["etapa"], e["ts"], e.get("motivo", "")),
                       "- Sha rejeitado: %s" % e.get("sha", ""), ""]
        elif t == "abertura":
            linhas += ["### Abertura · %s" % e["ts"], "- Campanha: %s" % e.get("campanha", ""),
                       "- Tasks: %s · primeira: %s" % (e.get("tasks", "?"), e.get("primeira", "?")),
                       "- Próxima: oráculo pelo agente separado → oracle freeze → script-aprovacao.sh (founder)", ""]
    return "\n".join(linhas).rstrip("\n") + "\n"


def registrar_evento(fid, ev_novo, r):
    ev = L.eventos(fid, r)
    ev_novo["seq"] = len(ev) + 1
    ev_novo.setdefault("ts", L.agora())
    L.apensar(os.path.join(L.feature_dir(fid, r), "eventos.jsonl"), json.dumps(ev_novo, ensure_ascii=False) + "\n")
    ev.append(ev_novo)
    L.gravar(os.path.join(L.feature_dir(fid, r), "CHECKLIST.md"), projetar_checklist(fid, ev))
    return ev


def checklist_integro(fid, r):
    ev = L.eventos(fid, r)
    atual = L.ler(os.path.join(L.feature_dir(fid, r), "CHECKLIST.md"))
    esperado = projetar_checklist(fid, ev)
    return bool(ev) and atual == esperado and not any(e.get("tipo") == "invalido" for e in ev)


# ------------------------------------------------------------------ artefatos por etapa

def artefatos(fid, etapa, r):
    fd = L.feature_dir(fid, r)
    if etapa in ("E1", "E2", "E5"):
        return [os.path.join(fd, "propostas", etapa + ".md")]
    if etapa == "E3":
        return [L.feature_md(fd)]
    td = os.path.join(fd, "TASKS")
    ts = [os.path.join(td, n) for n in sorted(os.listdir(td))] if os.path.isdir(td) else []
    return [L.feature_md(fd)] + ts


def sha_etapa(fid, etapa, r):
    return L.sha_arquivos(artefatos(fid, etapa, r), L.feature_dir(fid, r))


def exige_criacao(fid, r):
    ev = L.eventos(fid, r)
    if not ev:
        raise Recusa("feature %s não está em criação (rode `feature.py criar iniciar %s --demanda …`)" % (fid, fid))
    if any(e.get("tipo") == "abertura" for e in ev):
        raise Recusa("feature %s já foi aberta — a criação acabou" % fid)
    return ev


# ------------------------------------------------------------------ criar

def cmd_iniciar(a, r):
    st = L.state(r)
    if not os.path.isdir(st):
        raise Recusa("ABORTADO: .claude/state/ não existe — inicialize o estado com a skill salvar-sessao antes de "
                     "criar uma feature (nada foi escrito)")
    fid = a.id
    if not L.ID_RE.match(fid):
        raise Recusa("id inválido: %r (gramática ^[a-z][a-z0-9]*(-[a-z0-9]+){0,5}$ — é o nome da campanha)" % fid)
    ev = L.eventos(fid, r)
    if ev and not any(e.get("tipo") == "abertura" for e in ev):
        ini = next((e for e in ev if e.get("tipo") == "inicio"), {})
        if ini.get("demanda") != a.demanda:
            raise Recusa("criação de %s em curso com OUTRA demanda (%r) — retome com a mesma demanda ou rejeite"
                         % (fid, ini.get("demanda")))
        prox = L.etapa_corrente(ev) or "abrir"
        print("RETOMADA: criação de %s em curso · próxima etapa: %s (%s)" % (
            fid, prox, L.NOMES_ETAPA.get(prox, "feature.py criar abrir")))
        pend = L.proposta_pendente(ev, prox) if prox in L.ETAPAS else None
        if pend:
            print("  proposta %s pendente: apresente ao founder e registre aprovar/rejeitar" % pend["sha"][:12])
        return 0
    d = L.features(r)
    if fid in L.ids_ativas(r) or any(x["id"] == fid for x in d["entregues"]) or ev:
        raise Recusa("ABORTADO: a feature %s já existe (ativa, entregue ou aberta)" % fid)
    if os.path.exists(L.campanha_dir(fid, r)):
        raise Recusa("ABORTADO: a campanha campanhas/%s já existe — escolha outro id ou `feature.py adotar %s`"
                     % (fid, fid))
    if os.path.exists(os.path.join(st, "archive", fid)):
        raise Recusa("ABORTADO: archive/%s já existe (feature entregue com esse id)" % fid)
    outras = [x for x in L.em_criacao(r) if x != fid]
    if outras:
        raise Recusa("ABORTADO: a criação de %s está em curso — uma criação por vez (termine ou rejeite antes)"
                     % outras[0])
    mx = L.regras(r)["max_features_ativas"]
    if len(d["ativas"]) >= mx:
        raise Recusa("ABORTADO: limite de features ativas atingido (%d/%d: %s) — feche uma com fechar-feature antes"
                     % (len(d["ativas"]), mx, ", ".join(L.ids_ativas(r))))
    if a.dry_run:
        print("dry-run: criaria .claude/state/features/%s/{eventos.jsonl,CHECKLIST.md} (E0 OK; E1..E5 vazias)" % fid)
        return 0
    registrar_evento(fid, {"tipo": "inicio", "etapa": "E0", "demanda": a.demanda}, r)
    print("E0 OK — criação de %s iniciada. CHECKLIST: .claude/state/features/%s/CHECKLIST.md" % (fid, fid))
    print("próxima: E1 — escreva a análise e rode `feature.py criar propor %s --etapa E1 --arquivo <E1.md>`" % fid)
    return 0


def cmd_propor(a, r):
    fid, etapa = a.id, a.etapa
    ev = exige_criacao(fid, r)
    cor = L.etapa_corrente(ev)
    if etapa != cor:
        raise Recusa("só a etapa corrente pode ser proposta: %s (pedida: %s)" % (cor or "nenhuma — abrir", etapa))
    pend = L.proposta_pendente(ev, etapa)
    if pend:
        raise Recusa("a proposta %s de %s ainda não tem decisão — registre aprovar ou rejeitar antes de propor de novo"
                     % (pend["sha"][:12], etapa))
    fd = L.feature_dir(fid, r)
    lac = C.Lacunas()
    if etapa in ("E1", "E2", "E5"):
        src = a.arquivo or os.path.join(fd, "propostas", etapa + ".md")
        txt = L.ler(src)
        if txt is None:
            raise Recusa("proposta %s não encontrada: %s (passe --arquivo)" % (etapa, src), 3)
        C.checar_etapa(etapa, src, lac)
        if etapa == "E1":
            m = re.search(r"(?m)FEATURE-ID[^:\n]*:\s*`?([^\s`]+)", txt)
            if m and m.group(1) != fid:
                lac.add("id_difere:%s" % m.group(1), "FEATURE-ID proposto %s difere da criação %s" % (m.group(1), fid))
    elif etapa == "E3":
        C.checar_feature(L.feature_md(fd), lac, fid)
    else:
        ok, bom, _ = C.sonda()
        if not ok:
            raise Recusa("NOT_RUN: a sonda do contrato não discrimina (%s) — a E4 não pode ser validada"
                         % "; ".join(x["codigo"] for x in bom), 2)
        C.checar_completo(fd, lac)
        fr = L.ler_feature(L.feature_md(fd))
        if fr and fr["id"] != fid:
            lac.add("id_invalido:%s" % fr["id"], "FEATURE-ID difere da feature")
        for t in L.ler_tasks(fd):
            ok, motivos = C.complexidade_ok(t)
            if not ok:
                lac.add("complexidade_invalida:%s" % t["stem"], "; ".join(motivos))
    if lac.itens:
        if a.json:
            print(json.dumps({"feature": fid, "etapa": etapa, "ok": False, "lacunas": lac.itens}, ensure_ascii=False))
        else:
            print("%s recusada: %d lacuna(s)" % (etapa, len(lac.itens)))
            for x in lac.itens:
                print("  - %s — %s" % (x["codigo"], x["msg"]))
        return 2
    if etapa in ("E1", "E2", "E5"):
        dst = os.path.join(fd, "propostas", etapa + ".md")
        if os.path.realpath(src) != os.path.realpath(dst):
            L.gravar(dst, txt)
    sha = sha_etapa(fid, etapa, r)
    registrar_evento(fid, {"tipo": "proposta", "etapa": etapa, "sha": sha}, r)
    obj = {"feature": fid, "etapa": etapa, "sha": sha, "ok": True}
    L.saida(obj, a, "%s proposta (sha %s). Apresente ao founder e PARE: ok / ajustar / pausar." % (etapa, sha[:12]))
    return 0


def cmd_aprovar(a, r):
    fid, etapa = a.id, a.etapa
    ev = exige_criacao(fid, r)
    cor = L.etapa_corrente(ev)
    if etapa != cor:
        raise Recusa("só a etapa corrente pode ser aprovada: %s (pedida: %s)" % (cor, etapa))
    pend = L.proposta_pendente(ev, etapa)
    if not pend:
        raise Recusa("não há proposta pendente de %s (proposta rejeitada não se aprova: proponha de novo)" % etapa)
    if a.sha != pend["sha"]:
        raise Recusa("sha %s não é o da última proposta pendente de %s (%s)" % (a.sha[:12], etapa, pend["sha"][:12]))
    if sha_etapa(fid, etapa, r) != pend["sha"]:
        raise Recusa("o artefato de %s mudou depois de proposto — proponha de novo e reapresente" % etapa)
    if not (a.palavra or "").strip() or not APROVA.match(a.palavra):
        raise Recusa("a aprovação tem de ser a palavra LITERAL do founder começando por ok|sim|aprovo|aprovado "
                     "(recebido: %r) — ajustar/pausar não aprovam" % a.palavra)
    e = {"tipo": "aprovacao", "etapa": etapa, "sha": pend["sha"], "palavra": a.palavra.strip(),
         "produzido": a.produzido, "proxima": a.proxima}
    if a.medido:
        e["medido"] = a.medido
    if a.itens:
        e["itens"] = a.itens
    registrar_evento(fid, e, r)
    L.saida({"feature": fid, "etapa": etapa, "sha": pend["sha"], "aprovada": True}, a,
            "%s aprovada (\"%s\"). Próxima: %s" % (etapa, a.palavra.strip(), a.proxima))
    return 0


def cmd_rejeitar(a, r):
    fid, etapa = a.id, a.etapa
    ev = exige_criacao(fid, r)
    pend = L.proposta_pendente(ev, etapa)
    if not pend:
        raise Recusa("não há proposta pendente de %s para rejeitar" % etapa)
    if a.sha and a.sha != pend["sha"]:
        raise Recusa("sha %s não é o da proposta pendente de %s" % (a.sha[:12], etapa))
    registrar_evento(fid, {"tipo": "rejeicao", "etapa": etapa, "sha": pend["sha"], "motivo": a.motivo}, r)
    print("%s REJEITADA (registrada no CHECKLIST); refaça e proponha de novo. Motivo: %s" % (etapa, a.motivo))
    return 0


def cmd_checklist(a, r):
    ev = L.eventos(a.id, r)
    if not ev:
        raise Recusa("feature %s sem eventos (não está em criação nem foi criada por criar-feature)" % a.id)
    ok = checklist_integro(a.id, r)
    L.saida({"feature": a.id, "ok": ok, "eventos": len(ev)}, a,
            "CHECKLIST de %s: %s" % (a.id, "íntegro (= projeção dos eventos)" if ok else
                                     "ADULTERADO — difere da projeção de eventos.jsonl"))
    return 0 if ok else 2


# ------------------------------------------------------------------ abrir

def overlap(fid, escopo, r):
    """colisão de escopo contra cada ativa: campanha temporária com os mesmos globs + `ac.py overlap`."""
    outras = [x for x in L.ids_ativas(r) if os.path.isdir(os.path.join(L.campanha_dir(x, r), ".auto-correcao"))]
    if not outras:
        return []
    tmp = tempfile.mkdtemp(prefix="feature-overlap-")
    try:
        args = ["init", "--target", r]
        for g in escopo:
            args += ["--scope", g]
        rc, out, err = L.ac(tmp, *(args + ["--problem", "sonda de colisão", "--stop", "0"]), r=r)
        if rc != 0:
            return ["não consegui montar a campanha temporária de colisão: %s" % (err or out).strip()]
        args = ["overlap"]
        for o in outras:
            args += ["--other", L.campanha_dir(o, r)]
        rc, out, err = L.ac(tmp, *args, r=r)
        return [] if rc == 0 else [(err or out).strip().replace(tmp, "<esta feature>")]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def cmd_abrir(a, r):
    fid = a.id
    if fid in L.ids_ativas(r):
        raise Recusa("feature %s já está aberta" % fid)
    ev = exige_criacao(fid, r)
    ap = L.aprovadas(ev)
    falta = [e for e in L.ETAPAS if e not in ap]
    if falta:
        raise Recusa("abertura exige E1–E5 aprovadas; faltam: %s" % ", ".join(falta))
    if not checklist_integro(fid, r):
        raise Recusa("CHECKLIST adulterado (difere da projeção dos eventos) — abertura recusada")
    for e in ("E1", "E2", "E4", "E5"):
        if sha_etapa(fid, e, r) != ap[e]["sha"]:
            raise Recusa("o artefato de %s mudou depois do ok do founder (sha %s ≠ aprovado %s) — proponha de novo"
                         % (e, sha_etapa(fid, e, r)[:12], ap[e]["sha"][:12]))
    fd = L.feature_dir(fid, r)
    lac = C.Lacunas()
    fr, tasks = C.checar_completo(fd, lac)
    if lac.itens:
        raise Recusa("contrato completo com lacunas: %s" % ", ".join(x["codigo"] for x in lac.itens), 2)
    d = L.features(r)
    mx = L.regras(r)["max_features_ativas"]
    if len(d["ativas"]) >= mx:
        raise Recusa("limite de features ativas atingido (%d/%d)" % (len(d["ativas"]), mx))
    w = L.campanha_dir(fid, r)
    if os.path.isdir(os.path.join(w, ".auto-correcao")):
        raise Recusa("a campanha campanhas/%s já existe" % fid)
    col = overlap(fid, fr["escopo"], r)
    if col:
        raise Recusa("COLISÃO de escopo com feature ativa (ac.py overlap) — serialize ou estreite o escopo:\n  "
                     + "\n  ".join(col))
    el = L.elegiveis(tasks)
    primeira = el[0]["stem"] if el else None
    problema = " ".join(fr["historia"].split())
    parada = " ".join(fr["parada"].split())
    escreve = ["campanhas/%s/.auto-correcao/ (ac.py init)" % fid, ".claude/state/features/%s/INDEX.md" % fid,
               ".claude/state/features/%s/HISTORICO.md" % fid, ".claude/state/logs/%s/%s.md" % (fid, fid),
               ".claude/state/features.json", ".claude/state/WORKFLOW.md (bloco gerado)", "campanhas/README.md (linha)",
               ".claude/state/features/%s/CHECKLIST.md (handoff Abertura)" % fid]
    obj = {"feature": fid, "campanha": "campanhas/%s" % fid, "aberta": False, "tasks": len(tasks),
           "primeira": primeira, "motor": L.motor(), "escopo": fr["escopo"], "problem": problema, "stop": parada}
    if a.dry_run:
        obj["dry_run"] = True
        obj["escreveria"] = escreve
        L.saida(obj, a, "dry-run: abriria %s (%d tasks, primeira %s, escopo %s); escreveria:\n  %s"
                % (fid, len(tasks), primeira, ", ".join(fr["escopo"]), "\n  ".join(escreve)))
        return 0
    args = ["init", "--target", r]
    for g in fr["escopo"]:
        args += ["--scope", g]
    args += ["--problem", problema, "--stop", parada]
    rc, out, err = L.ac(w, *args, r=r)
    if rc != 0:
        raise Recusa("ac.py init falhou: %s" % (err or out).strip())
    ts = L.agora()
    L.gravar(os.path.join(fd, "INDEX.md"), L.render_index(fid, tasks))
    e2 = L.ler(os.path.join(fd, "propostas", "E2.md"), "").strip()
    hist = ["# HISTORICO — feature %s" % fid, "", "<!-- APPEND-ONLY: [NOTA] | [PASS] | [REJECT]; escrito pelo feature.py "
            "e pelo tech-lead, em série -->", "",
            "## [NOTA] %s — Abertura da feature %s" % (ts, fid),
            "- campanha: campanhas/%s (ac.py init; escopo: %s)" % (fid, ", ".join(fr["escopo"])),
            "- tasks: %d · primeira: %s" % (len(tasks), primeira), "- investigação aprovada (E2):", ""]
    hist += ["    " + x for x in e2.splitlines()]
    L.gravar(os.path.join(fd, "HISTORICO.md"), "\n".join(hist) + "\n")
    L.gravar(os.path.join(L.state(r), "logs", fid, fid + ".md"),
             "# log da feature %s\n\n## %s — abertura\n- %s\n- campanha campanhas/%s · %d tasks · primeira %s\n"
             % (fid, ts, fr["nome"] or fid, fid, len(tasks), primeira))
    d["ativas"].append({"id": fid, "origem": "criar-feature", "aberta_em": ts, "campanha": "campanhas/%s" % fid})
    L.salvar_features(d, r)
    L.regravar_workflow(d, r)
    readme = os.path.join(r, "campanhas", "README.md")
    txt = L.ler(readme, "# campanhas\n\n| campanha | o quê | commit de entrega | decisão |\n|---|---|---|---|\n")
    if not re.search(r"(?m)^\| %s \|" % re.escape(fid), txt):
        L.gravar(readme, txt.rstrip("\n") + "\n| %s | %s | — | em andamento |\n" % (fid, (fr["nome"] or "").replace("|", "/")))
    registrar_evento(fid, {"tipo": "abertura", "etapa": "abertura", "campanha": "campanhas/%s" % fid,
                           "tasks": len(tasks), "primeira": primeira}, r)
    obj["aberta"] = True
    L.saida(obj, a, "Feature %s aberta (nada commitado). Tasks: %d · primeira: %s · campanha campanhas/%s\n"
                    "Próximo: oráculo por agente separado → `ac.py oracle freeze` → script-aprovacao.sh %s (o "
                    "founder roda no terminal dele)." % (fid, len(tasks), primeira, fid, fid))
    return 0


# ------------------------------------------------------------------ status, adotar, task

def status_obj(r):
    d = L.features(r)
    at = []
    for x in d["ativas"]:
        tasks = L.ler_tasks(L.feature_dir(x["id"], r))
        at.append({"id": x["id"], "origem": x.get("origem"), "progresso": L.progresso(tasks)})
    cri = L.em_criacao(r)
    criacao = None
    if cri:
        criacao = {"id": cri[0], "proxima": L.etapa_corrente(L.eventos(cri[0], r)) or "abrir"}
    return {"estado": "IN_PROGRESS" if d["ativas"] else "IDLE", "ativas": at, "criacao": criacao,
            "entregues": [x["id"] for x in d["entregues"]], "workflow_em_dia": L.workflow_em_dia(d, r),
            "motor": L.motor(), "max_features_ativas": L.regras(r)["max_features_ativas"]}


def cmd_status(a, r):
    j = status_obj(r)
    linhas = ["Estado: %s · ativas %d/%d" % (j["estado"], len(j["ativas"]), j["max_features_ativas"])]
    for x in j["ativas"]:
        linhas.append("  - %s (%s) · %s tasks" % (x["id"], x["origem"], x["progresso"]))
    if j["criacao"]:
        linhas.append("Criação em curso: %s · próxima: %s" % (j["criacao"]["id"], j["criacao"]["proxima"]))
    linhas.append("Entregues: %s" % (", ".join(j["entregues"][-5:]) or "—"))
    linhas.append("WORKFLOW em dia: %s" % ("sim" if j["workflow_em_dia"] else "NÃO (bloco gerado difere do estado)"))
    t = "\n".join(linhas)
    L.saida(j, a, t, t)
    return 0


def cmd_adotar(a, r):
    fid = a.id
    if not L.ID_RE.match(fid):
        raise Recusa("id inválido: %r" % fid)
    st = L.campanha_estado(fid, r)
    if not st:
        raise Recusa("não há campanha campanhas/%s/.auto-correcao — nada a adotar" % fid)
    if st.get("stage") == "concluida":
        raise Recusa("a campanha %s está concluída — não é feature ativa" % fid)
    d = L.features(r)
    if fid in L.ids_ativas(r):
        print("%s já é ativa (%s) — nada a fazer" % (fid, next(x["origem"] for x in d["ativas"] if x["id"] == fid)))
        return 0
    mx = L.regras(r)["max_features_ativas"]
    if len(d["ativas"]) >= mx:
        raise Recusa("limite de features ativas atingido (%d/%d)" % (len(d["ativas"]), mx))
    if a.dry_run:
        print("dry-run: %s entraria em ativas como legado" % fid)
        return 0
    d["ativas"].append({"id": fid, "origem": "legado", "aberta_em": L.agora(), "campanha": "campanhas/%s" % fid})
    L.salvar_features(d, r)
    L.regravar_workflow(d, r)
    print("%s adotada como feature ativa (legado, sem checklist de criação)" % fid)
    return 0


def set_cab(txt, campo, valor):
    novo, n = re.subn(r"(?m)^%s:.*$" % re.escape(campo), "%s: %s" % (campo, valor), txt, count=1)
    return novo if n else txt


def cmd_task_marcar(a, r):
    fid, tid = a.id, a.task
    if fid not in L.ids_ativas(r):
        raise Recusa("feature %s não está ativa" % fid)
    fd = L.feature_dir(fid, r)
    p = os.path.join(fd, "TASKS", tid + ".md")
    t = L.ler_task(p)
    if not t:
        raise Recusa("task %s não existe em features/%s/TASKS/" % (tid, fid))
    if a.status not in ("PENDENTE", "IN_PROGRESS", "DONE") or a.gate not in ("PENDENTE", "PASS", "FAIL"):
        raise Recusa("status ∈ PENDENTE|IN_PROGRESS|DONE e gate ∈ PENDENTE|PASS|FAIL", 3)
    if a.status == "DONE" and a.gate != "PASS":
        raise Recusa("DONE exige gate PASS (recebido %s)" % a.gate)
    if a.status == "DONE" and not t["handoff"]:
        raise Recusa("DONE exige o `## Handoff` preenchido (o que foi entregue, evidência, limites)")
    txt = set_cab(set_cab(t["txt"], "status", a.status), "gate", a.gate)
    L.gravar(p, txt)
    L.gravar(os.path.join(fd, "INDEX.md"), L.render_index(fid, L.ler_tasks(fd)))
    tag = {"PASS": "PASS", "FAIL": "REJECT"}.get(a.gate, "NOTA")
    linhas = ["", "## [%s] %s — %s" % (tag, tid, L.agora()), "- status: %s · gate: %s" % (a.status, a.gate)]
    if a.nota:
        linhas.append("- %s" % a.nota)
    L.apensar(os.path.join(fd, "HISTORICO.md"), "\n".join(linhas) + "\n")
    print("%s → %s/%s · progresso %s" % (tid, a.status, a.gate, L.progresso(L.ler_tasks(fd))))
    return 0


# ------------------------------------------------------------------ fechar

def caminho_archive(fid, r):
    return os.path.join(L.state(r), "archive", fid, fid + ".md")


def archive_completo(fid, r):
    t = L.ler(caminho_archive(fid, r))
    if not t:
        return False
    obrig = ("## Resumo", "## Critérios de aceite", "## Arquivos da feature", "Aceite QA — ACCEPT",
             "Aceite Review — APPROVED")
    t = t.replace("## Arquivos da frente", "## Arquivos da feature")  # COMPAT: archive antigo
    return all(x in t for x in obrig) and t.rstrip().splitlines()[-1] in (L.MARCADOR_ARCHIVE, L.LEGADO_MARCADOR)  # COMPAT


def intrusos_archive(fid, r):
    d = os.path.join(L.state(r), "archive", fid)
    return sorted(x for x in os.listdir(d) if x != fid + ".md") if os.path.isdir(d) else []


def arquivos_da_feature(fid, r):
    """união dos Arquivos permitidos das tasks CORRECAO (enquanto existem); depois da limpeza, do archive."""
    tasks = L.ler_tasks(L.feature_dir(fid, r))
    if tasks:
        out = []
        for t in tasks:
            if t["tipo"] == "CORRECAO":
                out += [x for x in L.arquivos_reais(t) if x not in out]
        return out
    t = L.ler(caminho_archive(fid, r), "")
    return L.itens_codigo(L.secoes(t).get("Arquivos da feature", ""))


def portao_verde(fid, r):
    t = L.ler(os.path.join(r, "local", "portao-" + fid, "portao.out"))
    if not t:
        return False
    ls = t.rstrip().splitlines()
    return "RESULTADO: VERDE" in ls and ls[-1] == "FIM"


def bash_exe():
    """Caminho do bash a usar. No Windows nunca o do WSL (System32): o do PATH fora do System32, senão o do Git
    (bin ou usr/bin sob a raiz do Git, achada a partir do git), senão Recusa. Fora do Windows: "bash"."""
    if os.name != "nt":
        return "bash"
    env = os.environ
    raiz_win = env.get("SystemRoot") or env.get("SYSTEMROOT") or "C:\\Windows"
    sys32 = raiz_win.replace("\\", "/").lower().rstrip("/") + "/system32/"

    def dentro_sys32(p):
        return p.replace("\\", "/").lower().startswith(sys32)

    b = shutil.which("bash")
    if b and not dentro_sys32(b):
        return b
    g = shutil.which("git")
    if g:
        d = g.replace("\\", "/").rsplit("/", 1)[0] if "/" in g.replace("\\", "/") else ""
        partes = d.rsplit("/", 2)
        if len(partes) == 3 and partes[2].lower() == "bin" and partes[1].lower().startswith(("mingw", "clang")):
            raiz = partes[0]
        else:
            raiz = d.rsplit("/", 1)[0] if "/" in d else d
        for rel in ("bin/bash.exe", "usr/bin/bash.exe"):
            c = os.path.normpath(raiz + "/" + rel)
            if os.path.isfile(c) and not dentro_sys32(c):
                return c
    raise Recusa("Git Bash não encontrado: no Windows o fechamento precisa do bash do Git (instale o Git for "
                 "Windows ou ponha o bash dele no PATH); o bash do WSL (System32) não serve")


def conferir_commit(fid, arqs, r):
    if not arqs:
        return False, "sem Arquivos da feature"
    try:
        bash = bash_exe()
    except Recusa as e:
        return False, str(e)
    env = dict(os.environ, CS_DEV_SKILL_DIR=r)
    p = subprocess.run([bash, os.path.join(TOOLS, "conferir-commit.sh"), fid, "--"] + arqs, cwd=r, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    return p.returncode == 0, p.stdout.decode("utf-8", "replace").strip()


def gate_fechamento(fid, r):
    falhas = []

    def f(c, m):
        falhas.append({"codigo": c, "msg": m})

    fd = L.feature_dir(fid, r)
    tasks = L.ler_tasks(fd)
    idx = L.linhas_index(fid, r)
    disco = sorted(t["stem"] for t in tasks)
    done = [t["stem"] for t in tasks if t["status"] == "DONE"]
    if not tasks or not (len(idx) == len(disco) == len(done)) or sorted(idx) != disco:
        f("completude_divergente", "N_index=%d · N_disco=%d · N_done=%d (têm de ser iguais e > 0)"
          % (len(idx), len(disco), len(done)))
    hist = L.ler(os.path.join(fd, "HISTORICO.md"), "")
    for t in tasks:
        if t["status"] != "DONE":
            f("task_aberta:%s" % t["stem"], "%s está %s" % (t["stem"], t["status"] or "sem status"))
        if t["gate"] != "PASS" or not re.search(r"(?m)^## \[PASS\] %s\b" % re.escape(t["stem"]), hist):
            f("gate_ausente:%s" % t["stem"], "%s sem gate PASS no cabeçalho e `## [PASS]` no HISTORICO" % t["stem"])
    fr = L.ler_feature(L.feature_md(fd)) or {}
    if fr.get("aceite_qa") != "ACCEPT":
        f("aceite_ausente:qa", "FEATURE.md sem `### Aceite QA — ACCEPT`")
    if fr.get("aceite_review") != "APPROVED":
        f("aceite_ausente:review", "FEATURE.md sem `### Aceite Review — APPROVED`")
    if not portao_verde(fid, r):
        f("portao_nao_verde", "local/portao-%s/portao.out não termina em RESULTADO: VERDE + FIM" % fid)
    ok, out = conferir_commit(fid, arquivos_da_feature(fid, r), r)
    if not ok:
        f("conferir_commit", "conferir-commit.sh: " + " | ".join(out.splitlines()[-5:]))
    w = L.campanha_dir(fid, r)
    if L.ac(w, "check", "intake.3", r=r)[0] != 0:
        f("campanha_sem_aprovacao", "a campanha não tem a aprovação do founder (ac.py check intake.3 — gate stop): "
                                    "o founder roda local/aprovar-%s.sh no terminal dele" % fid)
    if L.ac(w, "oracle", "verify", r=r)[0] != 0:
        f("oraculo_nao_intacto", "ac.py oracle verify falhou (oráculo não congelado ou mudado fora de oracle change)")
    return falhas


def cmd_fechar_check(a, r):
    falhas = gate_fechamento(a.id, r)
    ok = not falhas
    t = "gate de fechamento de %s: %s" % (a.id, "PASS" if ok else "REPROVADO (%d)" % len(falhas))
    t += "".join("\n  - %s — %s" % (x["codigo"], x["msg"]) for x in falhas)
    L.saida({"feature": a.id, "ok": ok, "falhas": falhas}, a, t, t)
    return 0 if ok else 1


def montar_archive(fid, notas, r):
    fd = L.feature_dir(fid, r)
    fr = L.ler_feature(L.feature_md(fd))
    tasks = L.ler_tasks(fd)
    sn = L.secoes(notas)
    ck = L.ler(os.path.join(fd, "CHECKLIST.md"), "")
    handoffs = ck.split("## Handoffs", 1)[1].split("\n", 2)[-1].strip() if "## Handoffs" in ck else "(sem checklist)"
    hist = L.ler(os.path.join(fd, "HISTORICO.md"), "")
    st = L.campanha_estado(fid, r) or {}
    oraculo = []
    for t in tasks:
        if t["tipo"] == "ORACULO":
            oraculo += L.arquivos_reais(t)
    for p in (st.get("oracle") or {}).get("files") or []:
        rp = L.rel(p, r) if os.path.isabs(p) else p
        if rp not in oraculo:
            oraculo.append(rp)
    out = ["# %s — %s" % (fid, fr["nome"] or fid), "", "## Resumo", sn.get("Resumo", "").strip(), "",
           "## Critérios de aceite"]
    for ca in fr["cas"]:
        out += ["### %s — %s" % (ca["id"], ca["titulo"]), re.sub(r"^- \*\*.*?\*\*\s*", "", ca["texto"]).strip(), ""]
    out += ["## Linha do tempo"]
    for e in L.eventos(fid, r):
        out.append("- %s · %s %s" % (e.get("ts"), e.get("tipo"), e.get("etapa", "")))
    out += ["- " + x[3:] for x in hist.splitlines() if x.startswith("## [")]
    out += ["", "## Tasks", "| id | entrega | tipo | grupo | status | gate |", "|---|---|---|---|---|---|"]
    for t in tasks:
        out.append("| %s | %s | %s | %s | %s | %s |" % (t["stem"], t["entrega"], t["tipo"], t["grupo"], t["status"],
                                                      t["gate"]))
    for t in tasks:
        out += ["", "### Handoff %s" % t["stem"], t["handoff"] or "(vazio)"]
    out += ["", "## Como a feature nasceu", handoffs, "",
            "## Campanha", "- campanha: campanhas/%s · etapa do motor: %s · rodada: %s" % (
                fid, st.get("stage", "?"), st.get("round", "?")),
            "- critério de parada: %s" % (st.get("stop") or fr["parada"]),
            "- escopo: %s" % ", ".join(st.get("scope") or fr["escopo"]), "",
            "## Oráculo"]
    out += ["- `%s`" % x for x in oraculo] or ["- (sem arquivo declarado)"]
    out += ["", "## Decisões técnicas", sn.get("Decisões técnicas", "").strip(), "",
            "## Aprendizados", sn.get("Aprendizados", "").strip(), "", "## Arquivos da feature"]
    out += ["- `%s`" % x for x in arquivos_da_feature(fid, r)]
    out += ["", "## Aceite da Feature", "### Aceite QA — %s" % fr["aceite_qa"],
            "### Aceite Review — %s" % fr["aceite_review"], ""]
    return "\n".join(out)


def cmd_fechar_archive(a, r):
    fid = a.id
    if archive_completo(fid, r):
        print("archive de %s já completo — nada a fazer" % fid)
        return 0
    if not a.notas:
        raise Recusa("--notas ARQ é obrigatório (## Resumo, ## Decisões técnicas, ## Aprendizados)", 3)
    notas = L.ler(a.notas)
    if notas is None:
        raise Recusa("notas não encontradas: %s" % a.notas, 3)
    sn = L.secoes(notas)
    falta = [s for s in ("Resumo", "Decisões técnicas", "Aprendizados") if not sn.get(s, "").strip()]
    if falta:
        raise Recusa("notas sem as seções: %s" % ", ".join(falta))
    falhas = gate_fechamento(fid, r)
    if falhas:
        raise Recusa("gate de fechamento reprovado — nada escrito: %s" % ", ".join(x["codigo"] for x in falhas))
    intr = intrusos_archive(fid, r)
    if intr:
        raise Recusa("archive/%s/ tem arquivo intruso (%s) — o archive é um documento único; não apago nada"
                     % (fid, ", ".join(intr)))
    p = caminho_archive(fid, r)
    L.gravar(p, montar_archive(fid, notas, r))
    L.apensar(p, L.MARCADOR_ARCHIVE + "\n")
    if not archive_completo(fid, r):
        raise Recusa("archive gravado mas não valida — confira %s" % L.rel(p, r))
    print("archive completo: %s" % L.rel(p, r))
    return 0


def exige_archive(fid, r):
    if not archive_completo(fid, r):
        raise Recusa("archive/%s/%s.md não está completo — rode `feature.py fechar archive %s --notas ARQ` antes"
                     % (fid, fid, fid))


def cmd_fechar_entrega(a, r):
    fid = a.id
    exige_archive(fid, r)
    p = os.path.join(L.state(r), "LAST_DELIVERY.md")
    if entrega_feita(fid, r):
        print("LAST_DELIVERY já aponta %s — nada a fazer" % fid)
        return 0
    head = L.git(r, "rev-parse", "--short", "HEAD")[1] or "?"
    L.gravar(p, "# LAST_DELIVERY\n\n**Feature-ID:** %s\n- Fechada em: %s\n- Archive: .claude/state/archive/%s/%s.md\n"
                "- HEAD no fechamento: %s\n" % (fid, L.agora(), fid, fid, head))
    print("LAST_DELIVERY → %s" % fid)
    return 0


def entrega_feita(fid, r):
    t = L.ler(os.path.join(L.state(r), "LAST_DELIVERY.md"), "")
    corpo = [x for x in t.splitlines()[1:] if x.strip()]
    return bool(corpo) and corpo[0] == "**Feature-ID:** %s" % fid


def limpeza_feita(fid, r):
    return not os.path.exists(L.feature_dir(fid, r)) and not os.path.exists(os.path.join(L.state(r), "logs", fid))


def cmd_fechar_limpar(a, r):
    fid = a.id
    exige_archive(fid, r)
    if limpeza_feita(fid, r):
        print("limpeza de %s já feita — nada a fazer" % fid)
        return 0
    for d in (L.feature_dir(fid, r), os.path.join(L.state(r), "logs", fid)):
        shutil.rmtree(d, ignore_errors=True)
    print("removidos features/%s/ e logs/%s/ (o archive é a memória)" % (fid, fid))
    return 0


def idle_feito(fid, r):
    d = L.features(r)
    return fid not in L.ids_ativas(r) and any(x["id"] == fid for x in d["entregues"])


def cmd_fechar_idle(a, r):
    fid = a.id
    if idle_feito(fid, r):
        print("%s já entregue — nada a fazer" % fid)
        return 0
    exige_archive(fid, r)
    intr = intrusos_archive(fid, r)
    if intr:
        raise Recusa("archive/%s/ não é único: intruso(s) %s — remova à mão depois de conferir (não apago)"
                     % (fid, ", ".join(intr)))
    if not limpeza_feita(fid, r):
        raise Recusa("limpeza não feita (features/%s ou logs/%s ainda existem) — `feature.py fechar limpar %s`"
                     % (fid, fid, fid))
    if not entrega_feita(fid, r):
        raise Recusa("LAST_DELIVERY não aponta %s — `feature.py fechar entrega %s`" % (fid, fid))
    d = L.features(r)
    d["ativas"] = [x for x in d["ativas"] if x["id"] != fid]
    d["entregues"].append({"id": fid, "fechada_em": L.agora(), "archive": ".claude/state/archive/%s/%s.md" % (fid, fid)})
    L.salvar_features(d, r)
    L.regravar_workflow(d, r)
    print("%s entregue; estado: %s" % (fid, "IN_PROGRESS" if d["ativas"] else "IDLE"))
    return 0


def cmd_fechar_plano(a, r):
    fid = a.id
    et = [{"id": "archive", "feita": archive_completo(fid, r)}, {"id": "entrega", "feita": entrega_feita(fid, r)},
          {"id": "limpar", "feita": limpeza_feita(fid, r) and archive_completo(fid, r)},
          {"id": "idle", "feita": idle_feito(fid, r)}]
    prox = next((e["id"] for e in et if not e["feita"]), "commit")
    t = "fechamento de %s: %s · próximo: %s" % (fid, " ".join("%s=%s" % (e["id"], "ok" if e["feita"] else "—")
                                                               for e in et), prox)
    L.saida({"feature": fid, "etapas": et, "proxima": prox}, a, t, t)
    return 0


def paths_commit(fid, r, arqs):
    cands = list(arqs) + ["campanhas/%s/oraculo" % fid, "campanhas/README.md",
                          ".claude/state/archive/%s" % fid, ".claude/state/features/%s" % fid,
                          ".claude/state/logs/%s" % fid, ".claude/state/LAST_DELIVERY.md",
                          ".claude/state/WORKFLOW.md", ".claude/state/features.json", ".claude/state/RESUME.md",
                          ".claude/state/BACKLOG.md"]
    out = []
    for p in cands:
        rc, s, _ = L.git(r, "status", "--porcelain", "--untracked-files=all", "--", p)
        if rc == 0 and s.strip():
            out.append(p)
    return out


def privacidade(r, arquivos, msg):
    alvo = [os.path.join(r, x) for x in arquivos if os.path.exists(os.path.join(r, x))]
    env = dict(os.environ, CS_DEV_SKILL_DIR=r)
    ruins = []
    if alvo:
        p = subprocess.run([sys.executable, os.path.join(TOOLS, "guard_privacidade.py")] + alvo, cwd=r, env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
        if p.returncode != 0:
            ruins.append(p.stdout.decode("utf-8", "replace").strip() or "achado nos arquivos")
    if msg:
        p = subprocess.run([sys.executable, os.path.join(TOOLS, "guard_privacidade.py"), "--msg", msg], cwd=r, env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
        if p.returncode != 0:
            ruins.append("mensagem: " + (p.stdout.decode("utf-8", "replace").strip() or "achado"))
    return ruins


def commit_indice_temporario(r, paths, msg, extra_blobs=None):
    """commit a partir do HEAD com SÓ `paths` (+ blobs explícitos), num índice temporário; o índice real só é
    realinhado nesses caminhos (o stage de terceiros fica onde está)."""
    rc, head, err = L.git(r, "rev-parse", "HEAD")
    if rc != 0:
        raise Recusa("sem HEAD: %s" % err)
    fd, idx = tempfile.mkstemp(prefix="indice-feature-")
    os.close(fd)
    os.remove(idx)
    env = {"GIT_INDEX_FILE": idx}
    try:
        for args in (["read-tree", "HEAD"], ["add", "-A", "--"] + paths if paths else None):
            if args:
                rc, _, err = L.git(r, *args, env=env)
                if rc != 0:
                    raise Recusa("git %s falhou: %s" % (args[0], err))
        for dest, src in (extra_blobs or {}).items():
            rc, blob, err = L.git(r, "hash-object", "-w", src)
            if rc != 0:
                raise Recusa("hash-object %s: %s" % (src, err))
            rc, _, err = L.git(r, "update-index", "--add", "--cacheinfo", "100644,%s,%s" % (blob, dest), env=env)
            if rc != 0:
                raise Recusa("update-index %s: %s" % (dest, err))
        rc, tree, err = L.git(r, "write-tree", env=env)
        if rc != 0:
            raise Recusa("write-tree: %s" % err)
        rc, novo, err = L.git(r, "commit-tree", tree, "-p", head, "-F", msg)
        if rc != 0:
            raise Recusa("commit-tree: %s" % err)
        rc, _, err = L.git(r, "update-ref", "HEAD", novo, head)
        if rc != 0:
            raise Recusa("update-ref: %s" % err)
    finally:
        if os.path.exists(idx):
            os.remove(idx)
    todos = list(paths) + list((extra_blobs or {}).keys())
    if todos:
        L.git(r, "reset", "-q", "--", *todos)
    return novo


def cmd_fechar_commit(a, r):
    fid = a.id
    if not idle_feito(fid, r):
        raise Recusa("commit só depois do fechamento até IDLE (`feature.py fechar plano %s --json`)" % fid)
    if L.ac(L.campanha_dir(fid, r), "check", "integracao.3", r=r)[0] != 0:
        raise Recusa("sem a pré-autorização de commit do founder (ac.py check integracao.3 — preauth commit, que o "
                     "founder roda no terminal dele com local/aprovar-%s.sh)" % fid)
    arqs = arquivos_da_feature(fid, r)
    ok, out = conferir_commit(fid, arqs, r)
    if not ok:
        raise Recusa("conferir-commit reprovou (só entra o que o portão testou):\n" + out)
    msg = L.ler(a.mensagem) if a.mensagem else None
    if not msg or not msg.strip():
        raise Recusa("--mensagem ARQ (arquivo com a mensagem do commit) é obrigatório", 3)
    paths = paths_commit(fid, r, arqs)
    extra = {}
    if a.decisions:
        if not os.path.isfile(a.decisions):
            raise Recusa("--decisions: arquivo não existe: %s" % a.decisions, 3)
        extra[".claude/state/DECISIONS.md"] = os.path.realpath(a.decisions)
    priv = privacidade(r, paths, a.mensagem)
    if priv:
        raise Recusa("guard de privacidade achou termo privado — limpe e repita:\n" + "\n".join(priv))
    obj = {"feature": fid, "paths": paths + list(extra.keys()), "commit": None, "dry_run": bool(a.dry_run)}
    if a.dry_run:
        L.saida(obj, a, "dry-run: commitaria só a feature %s:\n  %s" % (fid, "\n  ".join(obj["paths"])))
        return 0
    if not paths and not extra:
        print("nada a commitar da feature %s (já commitada?)" % fid)
        return 0
    novo = commit_indice_temporario(r, paths, os.path.realpath(a.mensagem), extra)
    obj["commit"] = novo
    L.saida(obj, a, "commit %s — só a feature %s (%d caminho(s)); push: nunca (é do founder)"
            % (novo[:12], fid, len(obj["paths"])))
    return 0


# ------------------------------------------------------------------ CLI

def parser():
    ap = argparse.ArgumentParser(prog="feature.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("status")
    s.add_argument("--json", action="store_true")
    s.add_argument("--brief", action="store_true")
    cr = sub.add_parser("criar").add_subparsers(dest="sub")
    s = cr.add_parser("iniciar")
    s.add_argument("id")
    s.add_argument("--demanda", required=True)
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--json", action="store_true")
    s = cr.add_parser("propor")
    s.add_argument("id")
    s.add_argument("--etapa", required=True, choices=L.ETAPAS)
    s.add_argument("--arquivo")
    s.add_argument("--json", action="store_true")
    s = cr.add_parser("aprovar")
    s.add_argument("id")
    s.add_argument("--etapa", required=True, choices=L.ETAPAS)
    s.add_argument("--sha", required=True)
    s.add_argument("--palavra", required=True)
    s.add_argument("--produzido", required=True)
    s.add_argument("--proxima", required=True)
    s.add_argument("--medido")
    s.add_argument("--itens")
    s.add_argument("--json", action="store_true")
    s = cr.add_parser("rejeitar")
    s.add_argument("id")
    s.add_argument("--etapa", required=True, choices=L.ETAPAS)
    s.add_argument("--sha")
    s.add_argument("--motivo", required=True)
    s = cr.add_parser("abrir")
    s.add_argument("id")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("checklist")
    s.add_argument("id")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("adotar")
    s.add_argument("id")
    s.add_argument("--dry-run", action="store_true")
    tk = sub.add_parser("task").add_subparsers(dest="sub")
    s = tk.add_parser("marcar")
    s.add_argument("id")
    s.add_argument("task")
    s.add_argument("--status", required=True)
    s.add_argument("--gate", required=True)
    s.add_argument("--nota")
    fc = sub.add_parser("fechar").add_subparsers(dest="sub")
    for nome in ("plano", "check", "archive", "entrega", "limpar", "idle", "commit"):
        s = fc.add_parser(nome)
        s.add_argument("id")
        s.add_argument("--json", action="store_true")
        s.add_argument("--brief", action="store_true")
        if nome == "archive":
            s.add_argument("--notas")
        if nome == "commit":
            s.add_argument("--mensagem")
            s.add_argument("--decisions")
            s.add_argument("--dry-run", action="store_true")
    return ap


ROTAS = {("status", None): cmd_status, ("criar", "iniciar"): cmd_iniciar, ("criar", "propor"): cmd_propor,
         ("criar", "aprovar"): cmd_aprovar, ("criar", "rejeitar"): cmd_rejeitar, ("criar", "abrir"): cmd_abrir,
         ("checklist", None): cmd_checklist, ("adotar", None): cmd_adotar, ("task", "marcar"): cmd_task_marcar,
         ("fechar", "plano"): cmd_fechar_plano, ("fechar", "check"): cmd_fechar_check,
         ("fechar", "archive"): cmd_fechar_archive, ("fechar", "entrega"): cmd_fechar_entrega,
         ("fechar", "limpar"): cmd_fechar_limpar, ("fechar", "idle"): cmd_fechar_idle,
         ("fechar", "commit"): cmd_fechar_commit}


def main(argv=None):
    ap = parser()
    a = ap.parse_args(argv)
    fn = ROTAS.get((a.cmd, getattr(a, "sub", None)))
    if not fn:
        ap.print_help()
        return 3 if a.cmd else 0
    r = L.raiz()
    try:
        return fn(a, r)
    except Recusa as e:
        if getattr(a, "json", False):
            print(json.dumps({"ok": False, "erro": str(e)}, ensure_ascii=False))
        print("RECUSADO: %s" % e, file=sys.stderr)
        return e.code


if __name__ == "__main__":
    sys.exit(main())
