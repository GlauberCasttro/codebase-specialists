# WORKFLOW — codebase-specialists

Frente = campanha no motor embutido, em `campanhas/<frente>/` (oráculo versionado; `.auto-correcao/` local).
O estado mecânico de cada campanha é o `ac.py status` (o carimbo lista as ativas); aqui fica o porquê e a ordem.
Atualizado em 2026-10-06 (criação do projeto completo; iter15 e iter16 entregues e fechadas).

## Frentes ativas

Nenhuma.

## Fila

1. Pacote 0.9.0 (BACKLOG B-08): `bash .claude/tools/package.sh` → founder confere e decide a publicação.
2. Aviso à sessão da cobaia .NET para rodar o upgrade com a 0.9.0 (B-08, parte 2).
3. B-03 refino `--fast` gasta o slot.
4. B-02 upgrade real no repositório-piloto.
5. B-06 lembrete "comite antes do close"; B-07 senha em amend/resolve/stop/abort.
6. B-04 limites C#; B-05 U5 no layout plano (depende de D-13).
7. B-01 medição real iter11 (só com custo confirmado pelo founder).

## Últimas entregas

Commits do repositório privado de origem (antes deste projeto existir); a tabela completa por campanha está em
`campanhas/README.md`.

| commit | data | o quê |
|---|---|---|
| `da3ea45` | 2026-10-06 11:32 | correções de uso real na cobaia .NET (iter16) |
| `be1d03c` | 2026-10-06 10:40 | 0.9.0: skills geradas em inglês + guia de cada skill (iter15) |
| `18e3496` | 2026-10-05 22:54 | senha do humano na aprovação do mandato (iter14) |
| `9d1ab30` | 2026-10-05 21:18 | medição: pacotes de entrada, caminho único, evals nos 2 layouts, backup fora do repo (iter11, parcial) |
| `fcb1e6f` | 2026-10-05 19:53 | skills para Cursor/Copilot/Codex, task sincronizada, init em árvore (iter13) |
| `2c90621` | 2026-10-05 19:19 | upgrade em uso real (iter12) |
| `1837be7` | 2026-10-05 18:45 | 0.8.0: modo autônomo (mandato, M5) |

Neste repositório: `d3b2576` (pacote 0.7.0), `077fab2` (pacote 0.8.0) e o commit do projeto completo 0.9.0.
