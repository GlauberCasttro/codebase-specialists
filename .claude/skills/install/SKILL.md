---
name: install
description: Instala (ou atualiza) a skill codebase-specialists NESTA máquina a partir deste projeto — travas do git, pacote gerado e validado, link $HOME/.claude/skills/codebase-specialists → dist/codebase-specialists (backup do que houver lá) e conferência do instalado, via .claude/tools/instalar.sh. Use numa máquina nova, depois de fechar uma feature (`/fechar-feature`), quando o SessionStart disser que o pacote instalado está desatualizado ou que as travas faltavam, ou quando o founder pedir "instala a skill", "atualiza a skill instalada".
disable-model-invocation: true
---

# install

O script decide; esta skill só chama. A versão instalada É O PACOTE (`dist/codebase-specialists`), não o projeto.

1. Ensaio (não escreve nada): `bash .claude/tools/instalar.sh --dry-run` — travas, pacote, link e se haveria backup.
2. Instalação: `bash .claude/tools/instalar.sh` (roda o `package.sh` completo; leva alguns segundos). Tem de
   terminar em `instalado:`. Falha do pacote ⇒ exit != 0 e a instalação anterior continua intacta: relate o motivo
   (VERSION não commitada, validação reprovada) e corrija pelo fluxo de feature.
3. Conferência (não escreve nada): `bash .claude/tools/instalar.sh --check` — exit 0 = em dia.
4. Relate ao founder: link, VERSION, origem (HEAD) e o caminho do backup se o script citou `skills-backup-`.

Nunca apague backup nem mexa à mão em `~/.claude/skills/`. A senha das aprovações (`frase definir`) é do founder,
no terminal dele: nunca peça no chat.
