---
name: package
description: Gera e valida o PACOTE da codebase-specialists (só o que roda) em dist/codebase-specialists/ + dist/codebase-specialists-<VERSION>.zip, via tools/package.sh — lista de inclusão, limpeza de privacidade, guard-privacidade e instalação de prova num HOME temporário. Use quando o founder pedir "gera o pacote", "empacota a versão", "prepara a 0.x para publicar", depois que as frentes da versão foram commitadas.
disable-model-invocation: true
---

# package

O script decide; esta skill só chama. Fonte padrão = `git archive HEAD` (só o commitado).

1. Pré-condição: `bash .claude/tools/carimbo.sh` — frentes da versão commitadas; VERSION viva = VERSION do HEAD.
2. Ensaio (não escreve nada): `bash .claude/tools/package.sh --dry-run` — mostra o que ENTRA (por pasta) e o que
   FICA DE FORA. Confira que `.claude/`, `campanhas/`, `local/`, `evals/` e `scripts/*/tests/` estão fora.
3. Geração + validação: `bash .claude/tools/package.sh`. Tem de terminar em `== pronto:` com:
   `guard-privacidade: 0 achado(s)`, `vazamentos ...: 0` e os 5 passos (init, harness install, emit, emit validate,
   harness selftest) com exit 0. Qualquer falha ⇒ o .zip não é gerado; corrija pelo fluxo de frente.
   (`--worktree` empacota a árvore de trabalho — só para ensaio; `--manter` guarda o HOME temporário.)
4. Relate ao founder: tamanho do pacote e do .zip, sha256, números da validação.
5. Publicar o pacote (release, outro repositório, anexo) é DECISÃO DO FOUNDER — fora deste script. Depois de
   publicado, avise as sessões que usam a skill (ex.: a da cobaia .NET) para rodar o upgrade e registre a entrega
   no WORKFLOW (`/salvar-sessao`).

Regra nova de limpeza com texto privado entra em `local/regras-privadas.json5` (gitignored); termo privado novo em
`local/termos-privados.txt`. Mudança no MECANISMO (`publicar_regras.py`, `package.sh`) é mudança no harness: passa
pelo fluxo de frente como qualquer outra.
