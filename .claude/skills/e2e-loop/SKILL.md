---
name: e2e-loop
description: Roda a régua do desenvolvimento da codebase-specialists e conduz a correção de falhas dentro do escopo — suítes da skill nos 2 Pythons (python3 e /usr/bin/python3), a suíte do próprio harness (harness-dev), oráculos da feature, oráculo intacto, nenhum def removido e privacidade. Durante a feature seleciona as suítes pelo arquivo tocado (regra determinística em e2e.py); no fechamento e no portão roda tudo. Use para rodar a régua, validar uma task ou a feature, verificar regressão, ou quando o founder pedir "roda os testes", "valida a entrega", "a régua passa?".
---

# /e2e-loop — validar a codebase-specialists

O script decide o que rodar; você lê o resultado e diagnostica. Ajuda: `python3 .claude/tools/e2e.py --help`.

Por que seletiva durante a feature: o portão completo leva dezenas de minutos e roda todas as suítes nos 2 Pythons.
Rodá-lo a cada task troca minutos de diagnóstico por horas de espera. A seleção é um **mapa por caminho** (não um
grafo de import): o que ela não pega, a régua completa pega — por isso a completa é obrigatória no fechamento e no
portão.

## Pré-condições

1. Feature ativa: leia o escopo autorizado e os CAs. Arquivos da feature SEMPRE explícitos (ou `--lista ARQ`; o zsh não
   faz word-split de `$VAR`).
2. `python3` e `/usr/bin/python3` existem. Ausente ⇒ **NOT_RUN** (o script marca); não instale nada.
3. A régua roda na CÓPIA de trabalho (`local/work/<f>/codebase-specialists`) durante a feature e no portão (cópia limpa
   = HEAD + só os arquivos da feature) no fechamento. Nunca empacote o projeto vivo para "testar".

## Procedimento

1. **Régua** (o que existe):
   ```bash
   python3 .claude/tools/e2e.py regua --brief
   ```
   Suítes: `harness-dev` (`.claude/tools/tests`), cada `scripts/<x>` com `tests/`, `evals` (`evals/tests`); pythons e
   verificações extras (def removido, privacidade, oráculo intacto, pacote sem vazamento) em `.claude/tools/regua.json`.
2. **Seleção** pelo arquivo tocado:
   ```bash
   python3 .claude/tools/e2e.py selecionar --arquivos <tocados> --json      # ou --lista ARQ
   python3 .claude/tools/e2e.py selecionar --lista <arquivos-da-feature> --fechamento --json
   ```
   `.claude/**` ⇒ só `harness-dev`; `scripts/<x>/**` ⇒ só `x`; `evals/**` ⇒ `evals`; arquivo que nenhuma regra cobre
   (SKILL.md, references/, docs/, `.claude/package/`…) ⇒ **completa** (por segurança); `--fechamento` ⇒ completa.
3. **Rodar** nos 2 Pythons:
   ```bash
   python3 .claude/tools/e2e.py rodar --suites harness-dev,emit --dry-run   # os comandos, sem rodar
   python3 .claude/tools/e2e.py rodar --suites harness-dev,emit             # PASS/FAIL por suíte × Python + RESULTADO
   ```
   Na fase **fechamento** (task QA e antes do aceite), a régua é o **portão**, em background, acompanhando o
   `portao.out` até `FIM`:
   ```bash
   bash .claude/tools/portao.sh <f> --lista <arquivos-da-feature> --oraculo campanhas/<f>/oraculo:<modulo>
   ```
   (`.claude/tools/portao.sh`: cópia limpa, todas as suítes + `harness-dev` nos 2 Pythons, os oráculos pedidos e
   nenhum `def` removido vs HEAD; termina em `RESULTADO: VERDE|VERMELHO` e `FIM`.) Mais o oráculo intacto:
   `python3 .claude/tools/ac/ac.py --work campanhas/<f> oracle verify`.
4. **Falha:** para cada uma, reprodução mínima (o teste focado, nos 2 Pythons, `-q`), causa e arquivos atingidos.
   Corrija só se o pedido autoriza e só nos `Arquivos permitidos`; senão entregue o diagnóstico concreto. Não afrouxe
   teste, não edite oráculo (só mudança oficial decidida pelo founder), não "conserte" o portão.
5. Depois de uma correção: o teste afetado, depois `rodar` de novo. Pare ao passar; não repita régua verde sem
   mudança. No máximo 3 ciclos sem progresso (a mesma falha voltando), então reporte o bloqueio com evidência e o que
   falta.
6. Reporte: CAs cobertos (CA → teste/oráculo → resultado), a saída do `rodar`/portão, limites (a régua não mede
   qualidade de uso real) e onde estão as evidências (`local/portao-<f>/`).

## Integridade

- O veredito sai da saída do script (`rodar`, `portao.out`); não escreva nem edite esses arquivos à mão.
- O portão testa a cópia limpa; só entra no commit o que ele testou (`conferir-commit.sh`, no `/fechar-feature`).
- **NOT_RUN ≠ FAIL ≠ PASS.** Zero testes descobertos, skip novo, Python ausente ⇒ NOT_RUN. Suíte pulada por recurso
  privado ausente é skip da linha de base, não skip novo.
- A régua prova regressão automatizada; aceite humano e revisão continuam separados.
