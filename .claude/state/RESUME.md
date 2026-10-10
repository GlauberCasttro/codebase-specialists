<!-- resume-stamp
FEATURES: iter19
BRANCH: master
HEAD: 97a1718
PRODUTO: 5e08335652440fa31bbba2ce63b205ef2970580c
ESTADO: 25d84dd29a6091848b4e2f84f005b4e42f708c46
GATE: PENDENTE
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
- Autorizado: feature iter19 (B-14, 0.11.0) aberta pelo /criar-feature com E1–E5 aprovadas pelo founder ("ok" em
  cada etapa, 2026-10-07); chaves em inglês (D-19); mandato M5 e memória fora; migração por evento novo (D-20).
- NÃO autorizado: começar a correção antes de o founder rodar no terminal dele o script de aprovação da iter19
  (gerado em local/); traduzir chaves do mandato (B-21); mexer em memória do cs-mem, logs JSONL ou config JSON5;
  publicar/push do pacote; corrigir B-19 ou os defeitos de harness B-15..B-18 junto com a iter19.
- Aguardando decisão: aprovação da iter19 (com a senha); publicação do pacote 0.10.1.

## Onde paramos
- 0.10.0 (iter18, `5e8f6b2`) e 0.10.1 (iter20, `97a1718`) entregues, campanhas concluídas, pacote 0.10.1 validado e
  instalado nesta máquina; a segunda cobaia .NET fez o upgrade 0.9.0→0.10.1 (commit do upgrade sem --no-verify) e
  validou R2/R3 em uso real.
- iter19 aberta: oráculo congelado `1083cc4a985e` (39 testes; base 11/39 nos 2 Pythons); task 01 DONE (1/8).

## Próximos passos
1. Founder: rodar no terminal dele o script de aprovação da iter19 que está em local/ (com a senha).
2. `/tech-lead` da iter19: cópia de trabalho (`bash .claude/tools/copia.sh iter19`), G1 02→03→04, G2 05, G3 06 em
   paralelo ao G1; depois QA (portão com oráculos iter19, iter16, iter18 R1–R7 — caminhos literais, nunca `$VAR:t…`
   no zsh — e iter20) e REVIEW.
3. `/fechar-feature iter19` → `/package` → `/install` → avisar a segunda cobaia .NET do upgrade para 0.11.0.

## Estado do ambiente
- Fora do commit do estado: `campanhas/iter19/` e `campanhas/README.md` (vão no commit da feature);
  `campanhas/iter17|iter18|iter20/{base,remedicao}.json` e `campanhas/harness-dev/*.json` (notas de medição locais,
  não versionadas); `evals/fixtures/py-billing/repo/tests/fixtures/legacy-dotnet/obj/` (artefato de build
  pré-existente).
- `features.json`: iter18 e iter20 (legado) movidas à mão para entregues com autorização do founder (backups em
  `local/features-antes-*.json`) — B-15.
- Cópias de trabalho e portões em `local/work/` e `local/portao-*`.

## Ponteiros
- Feature: `.claude/state/features/iter19/` (FEATURE.md, TASKS/, propostas/E1–E5) · investigação: `propostas/E2.md` ·
  campanha: `campanhas/iter19/`
- BACKLOG: B-14 (em feature), B-15..B-21 · DECISIONS: D-17..D-20
