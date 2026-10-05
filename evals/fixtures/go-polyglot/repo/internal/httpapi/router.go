// Package httpapi exposes the REST API with chi.
package httpapi

import (
	"encoding/json"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"

	"github.com/acme/fleetd/internal/dispatch"
)

// Router builds the HTTP routes. Handlers never touch SQL directly; they call storage.
func Router(store DeliveryStore) http.Handler {
	r := chi.NewRouter()
	r.Get("/healthz", func(w http.ResponseWriter, _ *http.Request) { w.WriteHeader(http.StatusNoContent) })
	r.Post("/v1/deliveries", createDelivery(store))
	return r
}

// DeliveryStore is the subset of storage.Deliveries the API needs.
type DeliveryStore interface {
	CreateDelivery(r *http.Request, d dispatch.Delivery) error
}

func createDelivery(store DeliveryStore) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		d := dispatch.Delivery{ID: uuid.NewString(), Status: dispatch.StatusCreated}
		if err := store.CreateDelivery(r, d); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusCreated)
		_ = json.NewEncoder(w).Encode(d)
	}
}
