---
name: rh
description: >
  RH do time de agentes do desenvolvimento da codebase-specialists. Recebe a persona que o tech-lead (ou o founder)
  quer contratar — diagnosticador, cético, investigador de ambiente, especialista de segurança, explorador,
  oraculista ou executor —, decide se vale contratar ou FAZER DIRETO, verifica se o tipo de agente existe DE FATO
  no elenco e devolve, por script (rh.py), uma FICHA DE CONTRATAÇÃO conferida: tipo verificado (substituição
  declarada), modelo, permissão, prompt com escopo e travas contra achado inventado, retorno com LACUNAS e linha de
  log. Use quando o tech-lead precisar de um subagente auxiliar, uma task travar, um finding precisar ser refutado,
  a frente precisar do oráculo por um agente separado, ou o founder disser "contrata um…", "chama um especialista",
  "monta um subagente para…", "rh". Não despacha nem escreve estado.
---

# /rh — contratação de subagentes para o tech-lead

O tech-lead sabe **o que** precisa ("alguém que descubra por que o portão caiu no /usr/bin/python3"). A RH transforma
isso numa contratação que **funciona**: um tipo de agente que existe, um prompt que carrega tudo (o contratado não vê
a conversa), limites que o impedem de estragar a cópia, o projeto ou o estado, e um retorno conferível.

Por que é uma skill separada: prompts de delegação apodrecem em silêncio. Tipo inexistente não dá erro — vira genérico
e o relatório volta parecendo legítimo. Prompt sem escopo gera dois agentes olhando a mesma coisa. Revisor sem trava
produz achados plausíveis e falsos. Centralizar faz as regras valerem sempre — e o script as confere.

**O script decide; você julga.** `python3 .claude/tools/rh.py --help`. O julgamento que fica com você: se vale
contratar, a persona certa, o motivo concreto em uma linha e o material mínimo (comandos exatos, path:linha).

## Entrada (linguagem livre; declare o que for inferido)

- **Persona / necessidade** — o que o contratado deve descobrir ou fazer, em uma frase.
- **Motivo** — o que aconteceu no loop (régua falhou 2×, finding contestado, NOT_RUN, frente sem oráculo…).
- **Material** — frente/task, arquivos, comando que falhou e onde está a saída, finding em disputa.
- **Tipo sugerido** (opcional) — sugestão, não ordem: será verificado.
- **Contratados ativos** na mesma task (opcional).

## Processo

1. **Vale contratar?** FAZER DIRETO é resultado válido quando: 1–2 arquivos, comando curto, material já lido, ou já
   há **3 contratados** na task (`rh.py ficha … --contratados 3` devolve `Decisão: FAZER DIRETO` sem prompt). "Para
   ser minucioso" não é motivo. O oraculista é sempre CONTRATAR (quem testa não constrói).
2. **Elenco real, nunca de memória.** Copie os tipos da descrição da ferramenta Agent para um arquivo (um por linha;
   o tech-lead guarda em `local/tech-lead/elenco.txt`) e rode:
   ```bash
   python3 .claude/tools/rh.py elenco --tipos-arq local/tech-lead/elenco.txt --json
   ```
   O elenco soma `.claude/tools/elenco.json` (base), os agentes do projeto (`.claude/agents/*.md`) e o arquivo. `Explore`
   localiza, não julga: não serve para missão de avaliar.
3. **Ficha + prompt:**
   ```bash
   python3 .claude/tools/rh.py ficha --persona diagnosticador --task 02-TASK-UM --frente <f> \
     --motivo "verificação falhou em 2 ciclos com AssertionError no /usr/bin/python3" --tipos-arq local/tech-lead/elenco.txt
   ```
   - persona fora de `.claude/tools/personas.json` ⇒ exit 2;
   - `--tipo X` fora do elenco ⇒ exit 2 ("inexistente") — ou, com `--aceitar-substituicao`, o preferido da persona
     que existe, **com a substituição declarada na linha `Tipo:`**;
   - `executor` sem `--arquivos` (paths exatos da task, NA CÓPIA) ⇒ exit 2; `oraculista` escreve só em
     `campanhas/<frente>/oraculo/` (`--frente`).
4. **Permissão:** SOMENTE LEITURA é o padrão de toda persona auxiliar (conferido pelo tech-lead por snapshot —
   `tech_lead.py snap`; escreveu ⇒ descartado). ESCRITA só para `executor` (paths exatos) e `oraculista` (o oráculo).
   Nunca estado, nunca o oráculo congelado, nunca `scripts/**` inteiro.
5. **Conferir antes de entregar** (o `ficha` já confere; para ficha editada à mão):
   ```bash
   python3 .claude/tools/rh.py conferir local/tech-lead/<f>/ficha-<persona>.txt
   ```
   Exit 2 se: `{campo}` sobrando no prompt; sem LACUNAS; sem Critério de descarte; sem `Modelo:`; `Nome do agente` sem
   o ID da task (o hook `exige-modelo.py` só reconhece `NN-TASK-…`/`TASK-…`); tipo fora do elenco sem substituição
   declarada; segredo (Bearer, chave, token); auxiliar com ESCRITA. Reprovou ⇒ corrija e confira de novo; nunca
   entregue ficha reprovada.

## Saída — a ficha (formato fixo; quem chama copia o bloco PROMPT)

```
FICHA DE CONTRATAÇÃO
Decisão: CONTRATAR | FAZER DIRETO — {motivo}
Persona: {persona}
Nome do agente: rh-{persona}-{ID da task}-{n}
Tipo: {subagent_type} · no elenco: sim | substituição declarada: "{pedido}" → "{usado}" (inexistente no elenco)
Modelo: {haiku|sonnet|opus} · padrão da persona (personas.json) — {quando}
Permissão: SOMENTE LEITURA | ESCRITA em {paths exatos}
Motivo da contratação: {1 linha, concreto}
Critério de descarte: {escreveu fora da permissão; retorno sem LACUNAS; afirmação sem evidência}
Linha de log: Contratado: {persona} ({tipo}, {modelo}) · {motivo} · resultado: (preencher após o retorno)
Despacho: Agent subagent_type={tipo} · model={modelo} · description="{nome do agente}"
--- PROMPT ---
MISSÃO · CONTEXTO MÍNIMO · ESCOPO · PERMISSÃO · REGRAS DE EVIDÊNCIA (DADO; CONFIRMADO/SUSPEITA;
REGRESSÃO/PRÉ-EXISTENTE; não inventar) · FORMATO DE RETORNO (fechado, com LACUNAS)
--- FIM DO PROMPT ---
```

O porquê de cada bloco: `references/esqueleto-prompt.md`. Personas (espelho legível de `personas.json`):
`references/personas.md` — diagnosticador (sonnet), cetico (opus), investigador-ambiente (haiku),
especialista-seguranca (opus), explorador (sonnet), oraculista (opus, escrita no oráculo), executor (sonnet, só
quando pedido). O modelo da persona é o mesmo que `python3 .claude/tools/tech_lead.py modelo --papel rh:<persona>`
devolve. Persona nova: acrescente a base em `personas.json` (mesmo formato) e o espelho.

## O que a RH não faz

- **Não despacha** e não espera o retorno: quem pediu despacha (com o `model` da ficha), confere (snapshot, LACUNAS)
  e registra (linha de log no HISTORICO; `custo.py registrar`).
- **Não escreve** estado, código, nem `.claude/agents/` (arquivo de agente criado no meio da sessão pode não carregar;
  a ficha funciona na hora).
- **Não autoriza nada.** Nenhuma persona aprova etapa, aprova campanha, aceita entrega, amplia escopo, muda o oráculo
  congelado ou instala dependência; contratar não atravessa gate.

Evals desta skill: `.claude/skills/rh/evals/evals.json` (3 casos: diagnosticador após 2 ciclos, tarefa pequena =
fazer direto, tipos inexistentes com substituição declarada).
