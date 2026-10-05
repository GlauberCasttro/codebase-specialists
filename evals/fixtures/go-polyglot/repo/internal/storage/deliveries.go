package storage

import (
	"context"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/acme/fleetd/internal/dispatch"
)

// Deliveries persists dispatch.Delivery rows.
type Deliveries struct{ pool *pgxpool.Pool }

func NewDeliveries(pool *pgxpool.Pool) *Deliveries { return &Deliveries{pool: pool} }

const insertDelivery = `
INSERT INTO deliveries (id, status, created_at)
VALUES ($1, $2::delivery_status, $3)`

// Create stores a new delivery; created_at is converted to UTC (timestamptz column).
func (s *Deliveries) Create(ctx context.Context, d dispatch.Delivery) error {
	_, err := s.pool.Exec(ctx, insertDelivery, d.ID, string(d.Status), d.CreatedAt.UTC())
	return err
}

const updateStatus = `
UPDATE deliveries SET status = $2::delivery_status, courier_id = NULLIF($3, ''), updated_at = $4
WHERE id = $1`

// UpdateStatus writes a status change already validated by dispatch.CanTransition.
func (s *Deliveries) UpdateStatus(ctx context.Context, d dispatch.Delivery) error {
	_, err := s.pool.Exec(ctx, updateStatus, d.ID, string(d.Status), d.CourierID, time.Now().UTC())
	return err
}

const activeByCourier = `
SELECT courier_id, count(*) FROM deliveries
WHERE status IN ('assigned', 'picked_up') AND courier_id IS NOT NULL
GROUP BY courier_id`

// ActiveCounts returns how many active deliveries each courier has.
func (s *Deliveries) ActiveCounts(ctx context.Context) (map[string]int, error) {
	rows, err := s.pool.Query(ctx, activeByCourier)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := map[string]int{}
	for rows.Next() {
		var id string
		var n int
		if err := rows.Scan(&id, &n); err != nil {
			return nil, err
		}
		out[id] = n
	}
	return out, rows.Err()
}
