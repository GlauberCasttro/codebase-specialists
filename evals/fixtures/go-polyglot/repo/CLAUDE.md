# Notas do time de logística

- Antes de criar migração, avise o canal #fleet-db: o DBA revisa toda migração que altera enum.
- Não rode deploy na sexta depois das 16h (pico de entregas).
- O app do entregador ainda manda `driver_id` em alguns pings antigos; o backend usa `courier_id`.
