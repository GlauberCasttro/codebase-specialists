<!-- carimbo:inicio (gerado por tools/carimbo.sh --write; não edite à mão) -->
```
(ainda não gerado neste projeto — rode `bash .claude/tools/carimbo.sh --write` na próxima save-session)
```
<!-- carimbo:fim -->

# RESUME — codebase-specialists (desenvolvimento)

## Onde paramos (2026-10-06)
- **0.9.0 pronta.** Este repositório virou o PROJETO completo da skill (raiz = skill; `.claude/` = harness de
  desenvolvimento com o motor de campanhas embutido em `.claude/tools/ac/`; `campanhas/` = oráculos das campanhas
  M5 e iter9–iter16 + histórico; `local/` gitignored). Histórico anterior preservado: 0.7.0 e 0.8.0 eram o pacote
  público; o commit "codebase-specialists 0.9.0 — projeto completo de desenvolvimento" substitui o conteúdo.
- **iter15** (skills geradas em inglês + guia de cada skill; VERSION 0.9.0) ENTREGUE — commit `be1d03c` no
  repositório privado de origem (2026-10-06 10:40); campanha fechada (GO).
- **iter16** (correções de uso real na cobaia .NET: BOM em C#, dotfile no exame, refino no `--fast`, history,
  `using`/`namespace` em string C#, linha da aresta C#, `why` por documento, cópia do exame com painel pendente,
  check-diff pós-aceite) ENTREGUE — commit `da3ea45` no repositório de origem (2026-10-06 11:32); campanha fechada (GO).
- Nenhuma campanha ativa. O ledger das campanhas (`.auto-correcao/`) ficou só na máquina original.
- Pacote 0.9.0 gerado e validado por `.claude/tools/package.sh` (dist/ é gitignored; não publicado).

## Próximos passos (em ordem)
1. Publicar o pacote 0.9.0 quando o founder quiser: `bash .claude/tools/package.sh` (gera e valida `dist/`) →
   o founder decide onde publicar (release/anexo) e faz o push. Skill `package`.
2. Avisar a sessão da cobaia .NET para rodar o upgrade (`cs.py upgrade` → `--apply`) com a 0.9.0.
3. Depois, BACKLOG na ordem de prioridade (B-03 refino `--fast`, B-02 upgrade real no repositório-piloto, B-06,
   B-07, B-04, B-05, B-01 só com custo confirmado).

## Pendências de decisão do founder
- D-13: U5 (commit pós-accept) no layout PLANO continua barrado? (pendente de confirmação — B-05)
- Custo da medição real da iter11 (B-01): confirmar antes de rodar.
- Onde e quando publicar o pacote 0.9.0 (B-08).
