package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/acme/fleetd/internal/dispatch"
	"github.com/acme/fleetd/internal/httpapi"
	"github.com/acme/fleetd/internal/storage"
)

type store struct{ d *storage.Deliveries }

func (s store) CreateDelivery(r *http.Request, d dispatch.Delivery) error {
	d.CreatedAt = time.Now().UTC()
	return s.d.Create(r.Context(), d)
}

func main() {
	ctx := context.Background()
	pool, err := storage.Open(ctx, os.Getenv("DATABASE_URL"))
	if err != nil {
		log.Fatal(err)
	}
	defer pool.Close()
	addr := ":" + envOr("PORT", "8080")
	log.Printf("fleetd listening on %s", addr)
	log.Fatal(http.ListenAndServe(addr, httpapi.Router(store{storage.NewDeliveries(pool)})))
}

func envOr(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}
