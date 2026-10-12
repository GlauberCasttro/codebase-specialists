# iter21 — memória dos agentes que não esquece (0.12.0)

Feature `legado` (campanha adotada em 2026-10-08, conduzida pelo método /auto-correcao). Entregue em 2026-10-12, commit
`7fdb431`. Fechamento manual com autorização do founder (D-18/B-15: o `feature.py fechar` não fecha legado).

## Resumo
Objetivo do founder: "provar que o agente fez Y, foi corrigido, a memória foi atualizada e ele não esquece mais".
Entregue: caderno `.claude/agent-memory/<agente>/MEMORY.md` (bloco gerado pelo cs-mem + área livre, DEC-1); brief
com MEMÓRIA em cota reservada acima de TERMOS e termos por relevância; `consultei:` ensinado no cartão/brief e
conferido no submit (mentira recusada, ausência sinalizada — DEC-2); `/correct` que pergunta quem errou
(`--fault brief|agent`), mostra a prévia exata e confirma antes de gravar ou retratar; reincidência contada pelo erro
(inclusive com o certo reescrito); supersede/retract; rastro de busca com dono; guard/pre-commit do caderno; upgrade
que regenera os cadernos; VERSION 0.12.0 com migração harness+emit.

## Medição (critério de parada)
| Medida | Base (0.11.0) | Final |
|---|---|---|
| Oráculo mecânico iter21 (mo3, 64 asserções) | 20/64 (D 0/44, R 20/20) | 64/64 nos 2 Pythons |
| Prova real `claude -p` — aplicação em depois / sem-gatilho / persistência | 0% / 33% / 0% (base2) | 100% / 100% / 100% |
| Prova real — pesquisa coerente (config pesquisa) | — | r0 2/3 → r1 3/3 |
| Portão 0.12.0 (24 arquivos, 2 Pythons) | — | VERDE; harness 369; oráculos iter21 64, iter16 48, iter18 38, iter19 39, iter20 24 inteiros; nenhum def removido |
Custo das provas reais: US$ 6,31 (r0 4,78 · r1 1,53).

## Linha do tempo
- 2026-10-08: campanha adotada; intake → plano; base real 0% de aplicação; DEC-1 aprovada (plan:DEC-1).
- 2026-10-11: frente memória ciclos 1–3 (F1–F8, M14.5) aprovados; mo2 do oráculo (M14/M15) oficializada (D-23);
  0.11.0 trazida para a cópia; frentes motor e emissão despachadas.
- 2026-10-12: motor ciclo 1 REPROVADO (BLOQUEANTE: selo sem chave aceitava bloco forjado) → ciclo 2 APPROVED;
  emissão ciclo 2 APPROVED; correção fechada; B-32 resolvido (mudança oficial mo1 em iter18/19/20); prova real r0
  (aplicação 100%; coerência 0 por defeito do medidor); rodada 1 D-1-01 (busca com dono) APPROVED; mo3 (medidor do
  rastro) oficializada; recontagem offline; aprovações e conferência do founder; portão VERDE; commit 7fdb431.

## Frentes e revisões (pareceres integrais: `campanhas/iter21/revisoes/memoria-ciclo2.md`)
- memória (scripts/memory/**): ciclos 1–3, revisões isoladas APPROVED.
- motor (scripts/harness/engine/{brief,cmds,guard,hcore,state,views}.py, scripts/upgrade/**): ciclo 1 CHANGES_REQUESTED
  (selo forjável), ciclo 2 APPROVED após sondas de 15+ vetores (forjado, antigo, duplicado, marcadores na área livre,
  MultiEdit, replace_all, NotebookEdit, `..`, caixa, symlink de arquivo e diretório, lead, caderno alheio).
- emissão (scripts/emit/**, assets/templates/**, docs, VERSION, README, migrations): ciclo 1 APPROVED com ressalvas
  de segurança do /correct, ciclo 2 APPROVED (4 mutações reprovadas pelos testes).
- rodada 1 D-1-01 (mem.py + cmds.py): APPROVED; RED provado pelo revisor em cópia revertida.

## Oráculo
`campanhas/iter21/oraculo/` congelado com mudanças oficiais: mo1 (permissão do parser, M13), mo2 (M14 reincidência,
M15 caderno editado de verdade), mo3 (medidor da prova real lê o rastro pelo arquivo e pelo agente; `--recontar`
offline). Calibrações: mo2 falha no HEAD e passa no corretor exceto o defeito real M14.5; mo3 offline-check 39/39.

## Decisões técnicas
- Guard/pre-commit aceitam o bloco só se igual ao render atual do cs-mem; o selo vira diagnóstico.
- NOTEBOOK_RE case-insensitive (fuga por caixa no macOS); symlink com dono divergente recusado.
- Busca sem `--agent` infere o agente só com UMA delegação em voo; consultei só aceita busca do próprio agente.
- Reincidência herdada no supersede automático (a reincidência é do erro, não da redação do certo).
- Oráculos de versão relativos (B-32): versão ≥ X e X no catálogo.

## Aprendizados
- Oráculo 64/64 não bastou: a revisão isolada achou um furo de segurança que o oráculo (que testa uso legítimo) não
  pega. Revisão por instância nova continua obrigatória com o placar no máximo.
- O medidor também tem defeito: a coerência 0 da prova vinha do `prova_real.py` procurar a palavra "search" numa linha
  que o contrato não tem. Ler o artefato antes de concluir "o produto falhou".
- O caderno não fez diferença nesta prova (sem-caderno 100%): o brief corrigido já entrega a lição. Não inflar o valor.
- Executor que não observa RED: pedir ao revisor que prove o RED revertendo a correção numa cópia.
- Fechamento de legado segue manual (B-15).

## Ressalvas (MENOR, abertas)
Busca do lead sem --agent com uma delegação ativa é atribuída ao agente em voo; projeção usada na inferência editável
por Bash; falta teste "dois em voo ⇒ null"; `consultei: "x" -> nada encontrado` lido como ID "nada" (pode inflar a
coerência); coerência fora da config pesquisa oscila (r1 depois 1/3); /correct: prévia refeita não diz que a
confirmação anterior caducou; gate de confirmação é instrução de texto.

## Arquivos da feature (commit 7fdb431)
README.md, VERSION, assets/templates/{correct,memory}.md, docs/{03-memoria-e-licoes,06-referencia-cli,09-upgrade}.md,
references/migrations.json5, scripts/emit/platforms.py, scripts/emit/tests/test_iter21_emit.py,
scripts/harness/engine/{brief,cmds,guard,hcore,state,views}.py, scripts/harness/tests/test_iter21_motor.py,
scripts/memory/mem.py, scripts/memory/tests/{test_iter21_ciclo2,test_iter21_memoria,test_iter21_r1,test_mem}.py,
scripts/upgrade/core.py, scripts/upgrade/tests/test_iter19_upgrade.py; campanhas/iter21/** e as mudanças oficiais
mo1 de campanhas/iter18, iter19, iter20.
