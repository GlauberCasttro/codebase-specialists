// Package tracking turns GPS pings into ETAs.
package tracking

import (
	"math"
	"time"
)

const earthRadiusKm = 6371.0

// MinSpeedKmh is the floor used for ETA so a stopped courier never yields an infinite ETA.
const MinSpeedKmh = 8.0

// Ping is one GPS position reported by the courier app. At is always UTC.
type Ping struct {
	Lat, Lng float64
	At       time.Time
}

// DistanceKm is the haversine distance between two pings.
func DistanceKm(a, b Ping) float64 {
	dLat := rad(b.Lat - a.Lat)
	dLng := rad(b.Lng - a.Lng)
	h := math.Sin(dLat/2)*math.Sin(dLat/2) + math.Cos(rad(a.Lat))*math.Cos(rad(b.Lat))*math.Sin(dLng/2)*math.Sin(dLng/2)
	return 2 * earthRadiusKm * math.Asin(math.Sqrt(h))
}

// ETA estimates time to destination from the current speed, never below MinSpeedKmh.
func ETA(remainingKm, speedKmh float64) time.Duration {
	if speedKmh < MinSpeedKmh {
		speedKmh = MinSpeedKmh
	}
	return time.Duration(remainingKm / speedKmh * float64(time.Hour))
}

func rad(deg float64) float64 { return deg * math.Pi / 180 }
