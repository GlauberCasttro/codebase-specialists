# WORKFLOW — codebase-specialists

<!-- features:inicio (gerado por .claude/tools/feature.py; não edite à mão) -->
**Estado:** IN_PROGRESS
**Features ativas:** win-harness (criar-feature)
**Última entrega:** win-motor-copia (2026-10-09T09:25:15-0300) — .claude/state/archive/win-motor-copia/win-motor-copia.md
<!-- features:fim -->

Feature = campanha no motor embutido, em `campanhas/<feature>/` (oráculo versionado; `.auto-correcao/` local). O estado
mecânico é do `feature.py`/`ac.py status`; aqui ficam o porquê e a ordem. Atualizado em 2026-10-09.

## Sequência de features (compatibilidade com Windows — D-17, branch `release/version-windows`)

- [x] win-motor-copia — motor embutido corrigido para Windows (B-16) · `835dcde`
- [x] win-bash — fechar feature no Windows com o bash do Git (D-20) · `0bac550`
      (aberta antes para destravar o fechamento da win-motor-copia, parada no gate pelo bash do WSL)
- [ ] 1. win-harness (B-15) — harness de desenvolvimento no Windows nativo, sem o atalho `~/bin/python3` · EM CURSO
      (aberta 2026-10-09, D-21; 5/8 tasks) — primeiro porque portão e régua ainda dependem do WSL (~1h30 por
      rodada) e de `python3`/`/usr/bin/python3`
- [ ] 2. B-14 — produto no Windows (scan, harness gerado, verify, CRLF, senha do mandato)
      depois da B-15, para medir o produto com a régua já nativa; custo confirmado antes (D-09)
- [ ] 3. B-08 — pacote 0.10.x com suporte a Windows, publicação decidida pelo founder
- [ ] 4. B-13, B-17, B-03, B-02 e o restante do BACKLOG na ordem de prioridade

## Últimas entregas

| commit | data | o quê |
|---|---|---|
| `835dcde` | 2026-10-09 09:27 | win-motor-copia: motor de campanhas embutido corrigido para Windows |
| `0bac550` | 2026-10-09 09:24 | win-bash: fechar feature no Windows usa o bash do Git, nunca o do WSL |
| `b2498c5` | 2026-10-06 22:51 | harness: frente vira feature (criar-feature, fechar-feature, feature.py) |
| `5e8f6b2` | 2026-10-06 22:02 | 0.10.0: correções de uso real na segunda cobaia .NET (iter18) |
| `2ad9e03` | 2026-10-06 21:25 | harness de desenvolvimento completo (harness-dev) |
| `4dd7cf2` | 2026-10-06 16:16 | /install instala o pacote dist validado (iter17) |

Entregas anteriores (repositório privado de origem): tabela por campanha em `campanhas/README.md`.
