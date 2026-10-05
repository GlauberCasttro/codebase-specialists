package tracking

import (
	"math"
	"testing"
	"time"
)

func TestDistanceSaoPauloRio(t *testing.T) {
	sp := Ping{Lat: -23.5505, Lng: -46.6333}
	rj := Ping{Lat: -22.9068, Lng: -43.1729}
	if d := DistanceKm(sp, rj); math.Abs(d-361) > 5 {
		t.Fatalf("want ~361km, got %.1f", d)
	}
}

func TestETAUsesSpeedFloor(t *testing.T) {
	if got := ETA(8, 0); got != time.Hour {
		t.Fatalf("stopped courier must use MinSpeedKmh, got %v", got)
	}
}
