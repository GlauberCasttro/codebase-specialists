# campanhas/ — oráculos das campanhas de desenvolvimento

Cada mudança no produto é uma FRENTE = campanha do motor embutido (`.claude/tools/ac/ac.py`). Aqui fica o que é
versionável de cada campanha: `oraculo/` (ESPEC.md, testes, `base.txt` com a medição inicial, `mudanca-oficial/` com
patch + PORQUE de cada mudança oficial do oráculo). O ledger e o estado da campanha (`<frente>/.auto-correcao/`) são
locais (gitignored) e ficaram só na máquina original para as campanhas abaixo.

Caminhos privados foram trocados por variável de ambiente (testes que precisam de recurso privado PULAM com motivo),
nomes de projetos reais por termos genéricos ("repositório-piloto (projeto-legado)", "cobaia .NET",
"um harness anterior (v8)"). As rodadas `iteration-1` … `iteration-4` (saídas de execução) não vieram para o projeto.

Commits de entrega: do repositório privado de origem, antes deste projeto existir.

| campanha | o quê | commit de entrega | decisão |
|---|---|---|---|
| iter5 | harness destravado e provado E2E: faixas de aceite, escalada, sanitize, upgrade (oráculos nas suítes da skill; sem pasta própria) | `6483606` | sem decisão registrada (motor antigo; entregue) |
| iter6 | D-0-13: retentativa sobre trabalho já na árvore não reprova mais (oráculo na suíte) | `10e5439` | GO (parar: critério atingido) |
| iter7 | D-1-02/D-1-03: despacho fantasma e verify isolado por delegação (oráculo na suíte) | `d4a6c3d` | GO (parar: critério atingido) |
| iter8 | D-1-04: legacy-ack reconhece incoerência de hierarquia pré-existente (oráculo na suíte) | `35cd16e` | sem decisão registrada (motor antigo; entregue) |
| [iter9](iter9/oraculo/ESPEC.md) | 0.6.0: pasta `.swarm/`, harness único, migração do legado (SWARM-DIR-1..4) | `ffe388f` | GO (parar: critério atingido) |
| [iter10](iter10/oraculo/ESPEC.md) | 0.7.0: estado em árvore de pastas, skills de estado, CHORE, `--dry-run`/`check`/`--json` | `3127bf9` | GO (parar: critério atingido) |
| [m5](m5/oraculo/ESPEC.md) | 0.8.0: modo autônomo (mandato, `cs-auto`, máquina de estados, portão humano) | `1837be7` | GO |
| [iter11](iter11/oraculo/ESPEC.md) | medição: pacotes de entrada, caminho único, evals nos 2 layouts, backup fora do repo | `9d1ab30` | PARCIAL (medição real adiada por custo — BACKLOG B-01) |
| [iter12](iter12/oraculo/ESPEC.md) | upgrade em uso real (alvo legado no repositório-piloto) | `2c90621` | GO |
| [iter13](iter13/oraculo/ESPEC.md) | skills para Cursor/Copilot/Codex, task sincronizada, init em árvore | `fcb1e6f` | GO |
| [iter14](iter14/oraculo/ESPEC.md) | senha do humano na aprovação do mandato | `18e3496` | GO |
| [iter15](iter15/oraculo/ESPEC.md) | 0.9.0: skills geradas em inglês (verbo-objeto) + guia de cada skill | `be1d03c` | GO |
| [iter16](iter16/oraculo/ESPEC.md) | correções de uso real na cobaia .NET (BOM, dotfile, refino no `--fast`, history, C# em string, linha da aresta, check-diff pós-aceite) | `da3ea45` | GO |
| [iter18](iter18/oraculo/ESPEC.md) | 0.10.0: correções de uso real na segunda cobaia .NET (tree_sha sem ignorados, reverify de VERIFIED/REVIEWED, gate registra veredito, orquestrador não dita, pre-commit × task não aceita, bashscan, allowed_paths = território) | — | em curso |

`historico/`: notas de retomada e planos de rodada da época (limpos), para contexto — não são estado vivo; o estado
vivo do desenvolvimento está em `.claude/state/`.

Nova campanha: skill `new-front` (cria `campanhas/<frente>/` pelo `ac.py init`); acrescente a linha aqui ao abrir e
preencha commit/decisão no `close-front`.
| win-motor-copia | Motor de campanhas embutido corrigido para Windows | — | em andamento |
| win-bash | Fechar feature no Windows: bash do Git, nunca o do WSL | — | em andamento |
| win-harness | Harness de desenvolvimento no Windows nativo, sem atalho | — | em andamento |
| harness-evolucao | Evolução do harness do produto — classificação, ciclo de vida, JSON, memória e aprendizado por correção | — | em andamento |
