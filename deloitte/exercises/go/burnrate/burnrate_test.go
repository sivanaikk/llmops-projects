package burnrate

import (
	"math"
	"testing"
)

var policy = Policy{MinBudgetRemaining: 0.10, MaxFastBurn: 14.4, MaxSlowBurn: 6}

func near(a, b float64) bool { return math.Abs(a-b) < 1e-9 }

func TestBurnRate(t *testing.T) {
	if !near(BurnRate(0.01, 0.99), 1) || !near(BurnRate(0.144, 0.99), 14.4) || !near(BurnRate(0, 0.995), 0) {
		t.Fatal("burn rate = error ratio / error budget")
	}
}

func TestBudgetRemaining(t *testing.T) {
	if !near(BudgetRemaining(0.002, 0.99), 0.8) || !near(BudgetRemaining(0.015, 0.99), -0.5) {
		t.Fatal("remaining = 1 - window ratio / error budget")
	}
}

func TestHealthyReleaseShips(t *testing.T) {
	ok, reasons := Decide(0.002, 0.001, 0.002, 0.99, policy, "feature", false)
	if !ok || len(reasons) != 0 {
		t.Fatalf("expected admit, got %v %v", ok, reasons)
	}
}

func TestEachRuleBlocks(t *testing.T) {
	cases := map[string][3]float64{
		"low budget": {0.0095, 0.001, 0.001},
		"fast burn":  {0.001, 0.2, 0.01},
		"slow burn":  {0.001, 0.05, 0.07},
	}
	for name, r := range cases {
		ok, reasons := Decide(r[0], r[1], r[2], 0.99, policy, "feature", false)
		if ok || len(reasons) != 1 {
			t.Errorf("%s: expected exactly one blocking reason, got %v %v", name, ok, reasons)
		}
	}
}

func TestFixNeedsTicketFeatureNever(t *testing.T) {
	if ok, _ := Decide(0.02, 0.01, 0.01, 0.99, policy, "fix", false); ok {
		t.Error("fix without ticket must be denied while blocked")
	}
	if ok, _ := Decide(0.02, 0.01, 0.01, 0.99, policy, "fix", true); !ok {
		t.Error("fix with ticket must pass")
	}
	if ok, _ := Decide(0.02, 0.01, 0.01, 0.99, policy, "feature", true); ok {
		t.Error("a ticket must not unlock a feature")
	}
}

func TestRollbackAlwaysShips(t *testing.T) {
	if ok, _ := Decide(0.5, 0.9, 0.9, 0.99, policy, "rollback", false); !ok {
		t.Error("rollbacks are always admitted")
	}
}
