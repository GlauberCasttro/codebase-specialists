<!-- resume-stamp
FEATURES: —
BRANCH: release/desenv-mac
HEAD: 7fdb431
PRODUTO: 35d6171ce3ec09d42ae2ac773183fb923aa56213
ESTADO: 1a3a8766e8690acdf0cabc80e2a32dea4f02a6d5
GATE: —
-->

<!-- carimbo:inicio (gerado por tools/carimbo.sh --write; não edite à mão) -->
```
carimbo: 2026-10-06 16:17 -03 · branch master · HEAD 4dd7cf2 harness: /install instala o pacote dist validado (iter17)
skill: codebase-specialists · VERSION viva 0.9.0 (HEAD: 0.9.0) · último commit da skill: 4dd7cf2 2026-10-06 harness: /install instala o pacote dist validado (iter17)
campanhas ativas: nenhuma
arquivos sujos da skill: 4
  (lista: git status --porcelain)
```
<!-- carimbo:fim -->

# RESUME — codebase-specialists (desenvolvimento)

## Escopo autorizado e limites
- Autorizado: nada em execução (IDLE). A próxima feature é escolha do founder (topo do BACKLOG).
- NÃO autorizado: push (só o founder); abrir feature sem a escolha do founder; mudar git config sem "pode"; nova prova
  real (`claude -p`) sem confirmar o custo (D-09).
- Aguardando decisão: `git config user.email` noreply neste repo; qual a próxima feature (candidatos: B-33 task legível
  com review/submit, B-31 parecer no gate, B-15 fechar legado, B-34 coerência do consultei, B-19, B-28).

## Onde paramos
- 0.11.0 (iter19, c2b74ae) e 0.12.0 (iter21, 7fdb431) entregues e commitadas; estado IDLE; 4 features entregues.
- iter21: oráculo 64/64, portão VERDE com oráculos iter16–21 inteiros, prova real com aplicação 100% (base 0%) e
  pesquisa coerente 3/3; campanha GO conferida pelo founder; B-32 resolvido.
- /install ainda não rodado: a skill instalada nesta máquina é anterior à 0.11.0.

## Próximos passos
1. `/install` (instala a 0.12.0 nesta máquina).
2. Escolher a próxima feature no BACKLOG (/criar-feature).
3. Avisar a sessão da cobaia .NET para rodar `cs.py upgrade --apply` (0.10.1 → 0.12.0) e refazer o piloto da memória.

## Estado do ambiente
- Fora dos commits: local/work/iter19 e iter21 (cópias; podem ser apagadas), portões e notas em local/, prova real
  em ~/cs-prova-iter21/ (r0, r1), backup do features.json em local/backup-iter21/.
- Branch remota release/version-windows existe (outra sessão; números de decisão conflitam com D-21+ daqui).

## Ponteiros
- archive/iter19/iter19.md · archive/iter21/iter21.md · PORTE-WINDOWS.md (0.11.0 e 0.12.0 com cherry-pick) ·
  campanhas/iter21/revisoes/memoria-ciclo2.md · DECISIONS D-22..D-28 · BACKLOG B-29..B-34
