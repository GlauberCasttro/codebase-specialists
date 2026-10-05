package dispatch

import (
	"encoding/json"
	"os"
	"testing"
)

func TestPickCourierRespectsCapacity(t *testing.T) {
	couriers := []Courier{
		{ID: "c1", Online: true, Active: MaxActivePerCourier, Distance: 0.5},
		{ID: "c2", Online: true, Active: 1, Distance: 2.0},
		{ID: "c3", Online: false, Active: 0, Distance: 0.1},
	}
	got, err := PickCourier(couriers)
	if err != nil || got.ID != "c2" {
		t.Fatalf("want c2, got %v (err %v)", got.ID, err)
	}
}

func TestNoCourierAvailable(t *testing.T) {
	_, err := PickCourier([]Courier{{ID: "c1", Online: true, Active: 3}})
	if err != ErrNoCourierAvailable {
		t.Fatalf("want ErrNoCourierAvailable, got %v", err)
	}
}

func TestAssignOnlyFromCreated(t *testing.T) {
	d := Delivery{ID: "d1", Status: StatusDelivered}
	if _, err := Assign(d, []Courier{{ID: "c1", Online: true}}); err == nil {
		t.Fatal("assigning a delivered delivery must fail")
	}
}

func TestTerminalStatuses(t *testing.T) {
	if CanTransition(StatusDelivered, StatusFailed) || CanTransition(StatusFailed, StatusAssigned) {
		t.Fatal("delivered and failed are terminal")
	}
}

func TestGoldenAssignments(t *testing.T) {
	raw, err := os.ReadFile("testdata/assign_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var cases []struct {
		Couriers []Courier `json:"couriers"`
		Want     string    `json:"want"`
	}
	if err := json.Unmarshal(raw, &cases); err != nil {
		t.Fatal(err)
	}
	for i, tc := range cases {
		got, _ := PickCourier(tc.Couriers)
		if got.ID != tc.Want {
			t.Errorf("case %d: want %s, got %s", i, tc.Want, got.ID)
		}
	}
}
