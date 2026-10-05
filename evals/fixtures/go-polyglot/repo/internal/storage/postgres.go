// Package storage is the only package that talks SQL. Queries use pgx v5 and must match
// the schema produced by migrations/ (status values mirror the delivery_status enum).
package storage

import (
	"context"
	"fmt"

	"github.com/jackc/pgx/v5/pgxpool"
)

// Open connects with a pool; DATABASE_URL comes from the environment (see deploy/deploy.sh).
func Open(ctx context.Context, url string) (*pgxpool.Pool, error) {
	pool, err := pgxpool.New(ctx, url)
	if err != nil {
		return nil, fmt.Errorf("storage: open: %w", err)
	}
	if err := pool.Ping(ctx); err != nil {
		return nil, fmt.Errorf("storage: ping: %w", err)
	}
	return pool, nil
}
