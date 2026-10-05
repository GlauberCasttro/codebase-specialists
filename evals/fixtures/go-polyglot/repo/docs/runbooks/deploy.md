# Runbook — deploy do fleetd

1. `make test` verde e imagem publicada (`$REGISTRY/fleetd:<tag>`).
2. `deploy/deploy.sh <tag>` — aplica migrações pendentes e depois troca a imagem.
3. Problema? `deploy/rollback.sh <tag-anterior>`. Não rode `*.down.sql` em produção.
