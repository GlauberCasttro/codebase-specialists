# fleetd

Serviço de despacho de entregas: atribui **entregas** (`Delivery`) a **entregadores** (`Courier`),
acompanha o status e estima ETA.

- `cmd/fleetd` — binário HTTP (chi)
- `internal/dispatch` — regras de atribuição e ciclo de vida da entrega
- `internal/tracking` — distância (haversine) e ETA
- `internal/storage` — único pacote com SQL (pgx v5)
- `migrations/` — SQL versionado, append-only (ADR 0001)
- `deploy/` — scripts bash de migração, deploy e rollback

Requer Go 1.21 e Postgres 16. `make test` roda `go test ./...`.
`examples/python-client` é um exemplo de cliente para parceiros; não faz parte do serviço.
