package dispatch

import (
	"errors"
	"sort"
	"time"
)

// MaxActivePerCourier is the business limit of deliveries a courier carries at once
// (enforced again by the CHECK constraint in migrations/0003_courier_capacity.up.sql).
const MaxActivePerCourier = 3

// ErrNoCourierAvailable means every courier is at capacity or offline.
var ErrNoCourierAvailable = errors.New("no courier available")

// Courier is a person delivering parcels. Never call them "driver" in code or API.
type Courier struct {
	ID       string
	Online   bool
	Active   int // deliveries currently assigned or picked up
	Distance float64 // km to the pickup point
}

// Delivery is one parcel moving from pickup to drop-off.
type Delivery struct {
	ID        string
	Status    DeliveryStatus
	CourierID string
	CreatedAt time.Time // always UTC
}

// PickCourier chooses the closest online courier with spare capacity; ties go to the
// courier with fewer active deliveries, then by ID for determinism.
func PickCourier(couriers []Courier) (Courier, error) {
	candidates := make([]Courier, 0, len(couriers))
	for _, c := range couriers {
		if c.Online && c.Active < MaxActivePerCourier {
			candidates = append(candidates, c)
		}
	}
	if len(candidates) == 0 {
		return Courier{}, ErrNoCourierAvailable
	}
	sort.Slice(candidates, func(i, j int) bool {
		a, b := candidates[i], candidates[j]
		if a.Distance != b.Distance {
			return a.Distance < b.Distance
		}
		if a.Active != b.Active {
			return a.Active < b.Active
		}
		return a.ID < b.ID
	})
	return candidates[0], nil
}

// Assign moves a created delivery to assigned for the chosen courier.
func Assign(d Delivery, couriers []Courier) (Delivery, error) {
	if !CanTransition(d.Status, StatusAssigned) {
		return d, ErrInvalidTransition{From: d.Status, To: StatusAssigned}
	}
	c, err := PickCourier(couriers)
	if err != nil {
		return d, err
	}
	d.Status = StatusAssigned
	d.CourierID = c.ID
	return d, nil
}
