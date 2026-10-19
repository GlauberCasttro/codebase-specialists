<!-- resume-stamp
FEATURES: —
BRANCH: release/desenv-mac
HEAD: e920288
PRODUTO: 6da785c653a66f951dbbeb4d0d3ff81225315133
ESTADO: 289d2e5ac0d512f76fb53ae29e41d9c031a5fa6d
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
- Autorizado: nenhuma feature em execução (IDLE). A iter26 (0.14.0) foi aceita pelo founder ("ok", 2026-10-19) e
  fechada; instalada nesta máquina; a cobaia .NET já está na 0.14.0. O founder aceitou (2026-10-19, "pode seguir sua
  recomendacao") abrir a próxima feature como iter27 = CLI e motor inteiros em inglês (B-72 + B-68 + B-71), antes da
  task melhor.
- NÃO autorizado: iniciar a criação sem o founder invocar `/criar-feature`; push; publicar o pacote (B-08); `claude -p`
  sem confirmar custo (D-09); editar a v8 daqui; rodar o portão dentro de subagente (B-70).
- Aguardando decisão: as perguntas da E1 da iter27.

## Onde paramos
- 0.14.0 entregue (iter26): `8401adc` + mudanças oficiais de oráculo iter10 `244006a`, iter13 `d12e026`, iter19
  `58ebdc9`, iter23 `e920288`. Oráculo 15/51 → 51/51; portão VERDE nos 2 Pythons; D-35 sem regressão.
- Cobaia .NET: upgrade 0.14.0 OK (validate --strict OK, events intacto, commit do alvo bc1b31c); B-49 ainda não provado
  no uso real (exige task despachada). Achados viraram B-71 e B-72.

## Próximos passos
1. Founder: `/criar-feature iter27 — CLI e motor inteiros em inglês (B-72 + B-68 + B-71)`. Na E2, medir produto +
   oráculos antigos + doctests (lição da iter26, B-70c).
2. Depois: iter28 task melhor; iter29 métricas (`cs-state metrics`); B-61, B-50, B-48, B-70.

## Estado do ambiente
- Cópias e portões em local/work/iter26, local/portao-iter26, local/tech-lead/iter26, local/mo10, local/mo13,
  local/mo19 (rascunhos de mudança oficial), local/d35, local/d35b (evidências); as antigas local/work/iter19..iter25
  podem ser apagadas.
- Sessões da cobaia .NET mandam achados por SendMessage para esta sessão (nomes em local/).

## Ponteiros
- archive/iter26/iter26.md · LAST_DELIVERY.md · BACKLOG B-68..B-72 · DECISIONS D-40..D-45 · PORTE-WINDOWS.md
  (0.13.1, 0.14.0)
