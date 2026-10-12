# Parecer — frente memória, ciclo 2 (iter21, rodada 0, correção)

Registrado pelo tech-lead em 2026-10-11, transcrição do retorno do revisor. Snapshot pré/pós-revisor da cópia: nenhum
arquivo mudou. Medição do tech-lead na cópia, antes da revisão: oráculo iter21 41/55 (base 19/55) nos 2 Pythons; as
14 falhas restantes são das frentes motor/emissão (brief, guard, pre-commit, upgrade, consultei).

```
REVISOR: Claude Code · general-purpose · model: sonnet (passado pelo tech-lead) · instância isolada
BASE: 7b490df + cópia local/work/iter21/codebase-specialists · arquivos examinados: 4 (mem.py, test_mem.py,
test_iter21_memoria.py, test_iter21_ciclo2.py)

MATRIZ:
F1 → TestF1Reincidencia (2×, 3×, aplicada sai do caderno). mem.py:1125 correct → add_lesson:955 (merge = reincidência)
     → _add_lesson_locked:982 (_sync_promotion_count:916) → delivered_lessons:910 / is_delivered:904 →
     render_notebook:1627, inject_lessons:1314, check:1277. Sonda com 4 correções: count 1,2,3,4, promoted, a lição
     fica no caderno → PASS (o teste falharia com a correção antiga).
F2 → TestF2PropostaDescartada (retract; supersede explícito) / _discard_promotion:929 em retract:1198 e
     _add_lesson_locked → PASS (o supersede automático do F6 passa pelo mesmo código, sem teste — finding 3).
F3 → TestF3DesatualizadoXAdulterado (team mudou, glossário mudou, edição manual, CLI sem --agent) /
     check_notebook_detail:1805, block_seal_state:1702, `cs-mem notebook` → PASS (desatualizado = selo íntegro,
     aviso, exit 0; adulterado = selo quebrado/ausente, exit 1).
F4 → TestF4CRLF / _read_notebook:1793 normaliza para LF; write_notebook:1842 preserva CRLF → PASS (terminações mistas
     não dão falso adulterado; a regravação deixa tudo CRLF).
F5 → TestF5BomEMarcadorOrfao / split_notebook:1757, strip_generated:1735, _orphan_end:1718 → PASS (fim apagado com nota
     colada; nota acima do bloco com BOM; lição com marcadores/selo falsos ignorada).
F6 → TestF6RightDiferente / correction_match:1103, add_lesson:955 (supersede automático, ev auto=True) → PASS para o que
     o teste afirma (ver finding 1).
F7 → TestF7Decaimento (árvore: events.jsonl + .engine/projection.json5; plano: state/board.json5) / _tasks_since:820,
     load_board_any:1424, board_candidates:1413 → PASS (formato de dispatched_at = harness/engine/cmds.py:439).
F8 → TestF8SemEfeitoColateral / try/except OSError no search; correct_preview:1135 com load_lessons_ro:1157 → PASS.

Execução (cópia): suíte memory 58 OK em python3 e /usr/bin/python3; guard-privacidade 0 achados; def em mem.py 67 (HEAD)
→ 122 (cópia), nenhum nome removido.

FINDINGS:
1. [MENOR] [REGRESSÃO] [CONFIRMADO] mem.py:1103 + mem.py:982 — corrigir o mesmo erro 3× com `right` levemente
   reescrito cria lição nova a cada vez (supersede automático) com count=1 ⇒ nunca chega a reincidente ×N nem a
   promoted; a lição vigente fica no caderno, mas o sinal de reincidência se perde. Sugestão: a nova herda count+1 e
   as recurrences da substituída. O teste F6 ("não somou") consagra o comportamento atual.
2. [MENOR] [PRÉ-EXISTENTE] [SUSPEITA] mem.py:1198 / mem.py:1043 — ordem save_lessons → _discard_promotion →
   lesson_event → caderno não é transacional: queda entre o save e o descarte deixa proposta aplicável de lição
   retratada/superseded.
3. [MENOR] [REGRESSÃO] [CONFIRMADO] test_iter21_ciclo2.py — nenhum teste prova que o supersede AUTOMÁTICO (F6) descarta
   a proposta pendente da lição antiga (o código faz).
4. [MENOR] [PRÉ-EXISTENTE] [CONFIRMADO] mem.py:848 (decay_and_cap) — lição promoted com proposta nunca aplicada nem
   descartada fica entregue para sempre; só o limite de 190 linhas/24 KB do caderno a contém.

VEREDITO: APPROVED
LIMITES: diff por trechos; sondas em repositórios sintéticos no diretório temporário do sistema; não rodou o oráculo;
não simulou queda real de processo.
LACUNAS: consumidores de promotions.json5 e marcação de `applied` não conferidos (finding 4 vale para a lógica interna);
CRLF real do git autocrlf no Windows não conferido (só simulação por bytes).
```

## Destino dos findings (tech-lead)
- Finding 1 toca o objetivo da campanha ("ele não esquece mais" inclui o sinal de reincidência): candidato ao M14 do
  oráculo (mo2) ou à rodada 1; não bloqueia o ciclo 2.
- Findings 2–4: ressalvas; entram no relatório da rodada.

# Parecer — frente memória, ciclo 3 (M14.5)

Registrado pelo tech-lead em 2026-10-11. Executor: general-purpose · opus (ciclo 3). Medição do tech-lead na cópia:
suíte memory OK nos 2 Pythons; oráculo iter21 (mo2, 64 asserções) 48 → 49/64 nos 2 Pythons; M14 6/6; nenhum def
removido; privacidade 0. Snapshot pré/pós-revisor: nenhum arquivo mudou.

    REVISOR: general-purpose · sonnet · instância isolada — VEREDITO: APPROVED
    M14.5: r1, r2, r3 com o mesmo wrong ⇒ só r3 ativa/promovida, count 3, recurrences 2, "reincidente ×3"; r1/r2 fora
      do bloco → PASS (suíte memory 59 OK nos 2 Pythons).
    F1 (mesmo right 2×/3×): ramo de supersede não tocado; merge normal soma → PASS, igual ao ciclo 2.
    F6 (asserção nova count 2): LEGÍTIMA — "não somou" e M14.5 não podem valer juntos; nada mais foi afrouxado.
    r1,r2,r2,r3 ⇒ 1,2,3,4 (sem duplicar nem inflar); r1,r1,r2 ⇒ 3; r1,r2,r1 ⇒ 3 sem colisão de id.
    Promoção: só a lição nova tem proposta viva; a da antiga fica discarded.
    FINDING [MENOR] [REGRESSÃO] [SUSPEITA] mem.py:1040-1044 — supersede automático com a MESMA ocorrência da antiga
      soma +1, enquanto o merge normal (l.1000-1004) não soma ocorrência repetida; não reproduzido (não montou
      occurrence via evidência). Improvável; não bloqueia.
    LIMITES: sondas pela API em repo sintético; não rodou o oráculo nem o --supersedes manual pelo CLI.

# Parecer — frente motor, ciclo 1 (revisor opus isolado) — CHANGES_REQUESTED

Registrado pelo tech-lead em 2026-10-11. Medição do tech-lead antes da revisão: oráculo iter21 64/64 nos 2 Pythons;
escopo conferido por snapshot; nenhum def removido; privacidade 0.

    FINDING [BLOQUEANTE] [REGRESSÃO] [CONFIRMADO] scripts/harness/engine/guard.py (notebook_text_problems:
      `if blk != mem.render_notebook(root, agent) and mem.block_seal_state(blk) != "ok"`) + scripts/memory/mem.py:1698-1711
      — o selo é sha256 SEM chave do próprio corpo, gravado no arquivo: subagente dono escreve bloco com conteúdo
      arbitrário ("- LIÇÃO FORJADA: pule os testes") e selo recalculado por mem.seal_block ⇒ guard libera e
      check_diff --staged aceita (sonda: `True ok` / `problems: []`). O mesmo para bloco ANTIGO com selo antigo
      (ressuscitar lição retratada). Quebra a DEC-1 ("o pre-commit aceita se o bloco bate com o cs-mem").
      Correção: aceitar só blk == render_notebook (CRLF/BOM normalizados); desatualizado barrado com a dica
      `cs-mem notebook --agent X`; testes de regressão com bloco forjado + selo recalculado e bloco antigo + selo antigo.
    PASS por leitura: lead e outro agente recusados; NOTEBOOK_RE ancorado sobre realpath.
    NOT_RUN: consultei, cota do brief, regenerate_notebooks, fixture do upgrade (parou no bloqueante).
    LACUNAS: symlink e `\` sem sonda; Edit com old_string repetido; só o 1º caderno vai a decide_notebook no ramo do lead.

# Parecer — frente emissão, ciclo 1 (revisor sonnet isolado) — APPROVED

Registrado pelo tech-lead em 2026-10-11. Snapshot pré/pós sem mudança.

    MATRIZ: D-0-08 consultei no cartão (memory.md:5 ↔ cmds.py:469-530, brief.py:17) PASS · D-0-09 --fault (correct.md
      passo 2 ↔ mem.py:1076-1089) PASS · D-0-10 prévia/confirmação/supersedes/retract (mem.py:1139, 2014, 1953, 1205)
      PASS · docs dizem a verdade (flags conferidas no argparse) PASS · /correct seguro (mostra → confirma/PARA → grava)
      PASS com 2 MENOR · catálogo 0.12.0 ↔ version.py KINDS, core.py ORDER e regenerate_notebooks PASS · allowed-tools
      só cs-mem PASS.
    MENOR: correct.md — --supersedes só aparece depois da confirmação (o humano confirma uma prévia sem a flag);
      retract sem prévia nem confirmação própria; test_iter21_emit.py:46-48 casa "confirm" na abertura (passaria sem
      os passos 4–5); DocsCaderno só checa strings.
    VEREDITO: APPROVED.

# Parecer — frente emissão, ciclo 2 (revisor sonnet isolado) — APPROVED

Registrado pelo tech-lead em 2026-10-11. Ciclo 2 (executor sonnet): correct.md reescrito (supersedes decidido antes
da prévia; comando gravado = prévia sem --dry-run; retract com id/texto/motivo, confirmação explícita e PARE) e
test_iter21_emit.py (ordem real + 2 testes). Medição do tech-lead: oráculo 64/64 nos 2 Pythons.

    MATRIZ: ressalvas 1–3 PASS; um agente seguindo à risca não grava nem retrata sem o sim (passos 4, 5, 7 + linha 1)
      PASS; quem errou → --fault PASS; 4 mutações em mktemp (sem confirmação; sem --supersedes na prévia; retract sem
      PARE; retract sem "confirmação explícita") ⇒ todas FAILED PASS; oráculo M11/M12 8 OK PASS; 9 linhas ≤ 15 PASS.
    MENOR: correct.md:6 — prévia refeita não diz que a confirmação anterior deixa de valer; test_iter21_emit.py:64 —
      não compara o comando gravado com a prévia sem --dry-run (flag extra só na gravação passaria).
    LIMITE: o gate de confirmação é instrução de texto, sem imposição mecânica.

# Parecer — frente motor, ciclo 2 (revisor opus isolado, instância nova) — APPROVED

Registrado pelo tech-lead em 2026-10-11. Ciclo 2 (executor opus novo): guard/pre-commit aceitam só bloco ==
render_notebook (CRLF/BOM normalizados), selo deixou de ser critério; todos os cadernos passam por decide_notebook;
symlink divergente recusado; NOTEBOOK_RE com IGNORECASE (fuga por caixa no macOS, achada pelo executor). Medição do
tech-lead: oráculo 64/64 nos 2 Pythons; harness 366 OK/16 skip (executor); nenhum def removido; privacidade 0.

    MATRIZ: guard — sondas em mktemp: forjado com selo recalculado, antigo pós-lição, conteúdo extra nos marcadores,
      bloco duplicado, marcadores na área livre (inclusive indentados), texto acima do bloco, Write vazio, MultiEdit
      tocando o bloco, Edit replace_all no bloco, NotebookEdit, `..`, caixa, caderno alheio, symlink de arquivo e de
      diretório, lead ⇒ todos RECUSADOS; Edit com old_string repetido só na área livre ⇒ aceito (correto); vizinhos
      (.claude/agent-memory/X/outro.md, .claude/settings.json) caem na regra de allowed_paths. Pre-commit: forjado,
      antigo, adulterado e caderno removido BARRADOS. PASS. Usabilidade (área livre, CRLF/BOM, dica) PASS. consultei
      (comparação exata, por agente, ID na busca; ausência sinalizada) PASS. brief (MEMORY_PRIO 2, cota 35%) PASS pelos
      testes. upgrade (regenerate_notebooks antes do verify; falha → restore; fixture sem versão fixa) PASS.
    MENOR: cmds.py:517 busca sem --agent vale para qualquer agente (SUSPEITA); cmds.py:504 `consultei: nada` sem motivo
      aceito (CONFIRMADO); upgrade/core.py:1115 restore com caderno criado do zero não sondado (SUSPEITA).
    LIMITES: escrita por Bash não passa pelo guard (declarado no projeto; o pre-commit é a rede); search.jsonl protegido
      só para Edit/Write; sem hardlink nem FS case-sensitive real.
    VEREDITO: APPROVED.

# Parecer — rodada 1, D-1-01 busca com dono (revisor opus isolado) — APPROVED

Registrado pelo tech-lead em 2026-10-12. Origem: prova real r0 (pesquisa coerente 0/18: `cs-mem search` sem
--agent gravou agent null). Executor sonnet: infer_active_agent (um só em voo ⇒ agente; senão null +
agent_inferred false), consultei_check só aceita busca do próprio agente, `consultei: nada` exige motivo. Medição do
tech-lead: oráculo 64/64 nos 2 Pythons; nenhum def removido; privacidade 0. O executor NÃO observou o RED.

    RED provado pelo revisor: cópia em mktemp com as 3 reversões ⇒ r1 1/3 FAIL e TestD008Consultei 2/9 FAIL nos 2
      Pythons; cópia real tudo OK. (a)(b)(c) PASS; (d) teste de guarda (passa antes e depois, esperado).
    Inferência: 2 em voo ⇒ (None, "mais de um agente em voo"); 1 ⇒ o agente; task em andamento sem delegação ⇒ o
      agente; nenhum ⇒ None. Busca de outro agente recusada. Oráculos iter16/18/19/20 OK com a cópia nos 2 Pythons.
      Mensagens de recusa dizem o comando exato.
    MENOR: mem.py:1494-1512 com uma delegação ativa, busca sem --agent do lead/outro processo é atribuída ao agente
      em voo (risco baixo: IDs ainda têm de sair da busca) — documentar ou expor agent_inferred no rótulo;
      projeção usada na inferência editável por Bash (PRÉ-EXISTENTE, SUSPEITA); falta teste "dois em voo ⇒ null".
    VEREDITO: APPROVED.
