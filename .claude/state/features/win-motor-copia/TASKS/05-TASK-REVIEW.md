# 05-TASK-REVIEW — Revisão isolada da cópia do motor e do matcher

id: 05-TASK-REVIEW
feature: win-motor-copia
tipo: REVIEW
grupo: —
agente: revisor isolado (/revisor, sem escrita)
CA: CA-01, CA-02, CA-03, CA-04, CA-05
depends: 04-TASK-QA (revisa o que o portão aprovou)
status: DONE
gate: PASS

## Goal
Revisar o diff das tasks 02 e 03 contra os CAs, a fonte `auto-correcao@30e2da6` e as evidências do QA; parecer
APPROVED ou CHANGES_REQUESTED com `arquivo:linha`. NÃO editar nada.

## Contexto
CA-01..CA-05. Pontos de atenção: as 2 linhas do layout são as únicas diferenças do `ac.py`; o ORIGEM confere; o
`.gitattributes` tem uma regra só; o settings.json mudou uma linha.

## Subtasks
1. Diff de cada arquivo contra a fonte e contra o HEAD.
2. Conferir as evidências do QA (portao.out, oráculo nos 2 shells).
3. Parecer com achados evidenciados.

## Invariants
- Revisão é leitura: nenhum arquivo do projeto muda.

## Scope IN / OUT
IN: diff e evidências. OUT: correção (volta à task dona).

## Arquivos permitidos
- `.claude/state/features/win-motor-copia/TASKS/05-TASK-REVIEW.md`

## AC
- Parecer registrado no Handoff, com cada achado em `arquivo:linha`.

## DoD
- APPROVED, ou CHANGES_REQUESTED devolvido à task dona.

## Verificação
```bash
git diff --stat HEAD -- .claude/tools/ac .claude/settings.json .gitattributes
```

## Handoff
- Revisor real: subagente general-purpose · opus · instância nova (nunca executou nada na feature), modo feature.
  VEREDITO: APPROVED. Matriz CA-01..CA-05 PASS; cada classe do oráculo verde na cópia e vermelha no HEAD pelo motivo
  (25 falhas no HEAD); selftest 135 contém literalmente os 44 DENY e 30 ALLOW antigos com o mesmo veredito; escopo
  medido por índice temporário = exatamente os 6 arquivos; 0 `def` removido. Tech-lead conferiu por snapshot que o
  revisor não escreveu na cópia.
- Findings (todos MENOR · PRÉ-EXISTENTE, nenhum bloqueante): (1) `hook_aprovacao.py:130` — `ps_lex` trata `{`/`}`
  como separador: `python3 ${AC} gate stop` pela ferramenta PowerShell passa (pelo Bash é negado); limite fora da
  lista DEC-5 do docstring — é do motor (projeto auto-correcao), candidato a item lá; (2) `.claude/settings.json:5`
  — guard-git continua com matcher `Bash`: git push/reset/stash pela ferramenta PowerShell não passam pelo guard —
  candidato a explicitar na B-15; (3) `carimbo.sh:40-41` — já ressalvado na 02 (B-15).
- Limites: matcher sem teste ao vivo nesta revisão (evidência ao vivo: prova da win-hook); frase no console real só
  por mocks — o critério do B-16 "frase/gate no PowerShell deste projeto" depende do founder.
