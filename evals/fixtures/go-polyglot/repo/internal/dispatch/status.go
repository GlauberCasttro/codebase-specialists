// Package dispatch assigns deliveries to couriers and owns the delivery lifecycle.
package dispatch

import "fmt"

// DeliveryStatus mirrors the Postgres enum delivery_status (migrations/0002_delivery_status_enum.up.sql).
// Adding a value here REQUIRES a new migration that adds it to the enum; never edit 0002.
type DeliveryStatus string

const (
	StatusCreated   DeliveryStatus = "created"
	StatusAssigned  DeliveryStatus = "assigned"
	StatusPickedUp  DeliveryStatus = "picked_up"
	StatusDelivered DeliveryStatus = "delivered"
	StatusFailed    DeliveryStatus = "failed"
)

// allowedTransitions: created -> assigned -> picked_up -> delivered | failed.
// assigned may also fail (courier no-show). delivered and failed are terminal.
var allowedTransitions = map[DeliveryStatus][]DeliveryStatus{
	StatusCreated:   {StatusAssigned},
	StatusAssigned:  {StatusPickedUp, StatusFailed},
	StatusPickedUp:  {StatusDelivered, StatusFailed},
	StatusDelivered: {},
	StatusFailed:    {},
}

// ErrInvalidTransition is returned when a status change is not in allowedTransitions.
type ErrInvalidTransition struct{ From, To DeliveryStatus }

func (e ErrInvalidTransition) Error() string {
	return fmt.Sprintf("invalid delivery transition %s -> %s", e.From, e.To)
}

// CanTransition reports whether from -> to is allowed.
func CanTransition(from, to DeliveryStatus) bool {
	for _, s := range allowedTransitions[from] {
		if s == to {
			return true
		}
	}
	return false
}
