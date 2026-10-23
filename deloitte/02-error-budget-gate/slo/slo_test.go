package slo

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func spec(t *testing.T) *Spec {
	t.Helper()
	s, err := Load("../slos/agent-runtime.yaml")
	if err != nil {
		t.Fatal(err)
	}
	return s
}

// fakeQ answers by matching the range selector in the query.
type fakeQ struct {
	ratios map[string]float64 // window -> error ratio
	err    error
}

func (f fakeQ) Scalar(_ context.Context, q string) (float64, bool, error) {
	if f.err != nil {
		return 0, false, f.err
	}
	for w, v := range f.ratios {
		if strings.Contains(q, "["+w+"]") {
			return v, true, nil
		}
	}
	return 0, false, nil
}

var now = time.Date(2026, 10, 23, 12, 0, 0, 0, time.UTC)

func TestLoadDefaultsAndValidation(t *testing.T) {
	s := spec(t)
	if s.Objective != 0.99 || s.Gate.MaxFastBurn != 14.4 || s.Gate.OnError != "closed" {
		t.Fatalf("unexpected spec: %+v", s)
	}
	bad := filepath.Join(t.TempDir(), "bad.yaml")
	os.WriteFile(bad, []byte("service: Bad_Name\nobjective: 1.2\nwindow: 4 weeks\nsli: {errors: 'sum(x)', total: y}\n"), 0o644)
	_, err := Load(bad)
	if err == nil {
		t.Fatal("expected validation error")
	}
	for _, want := range []string{"kebab-case", "objective", "window", "sli.errors"} {
		if !strings.Contains(err.Error(), want) {
			t.Errorf("error %q missing %q", err, want)
		}
	}
}

func TestRulesContainBurnAlertsAndBudget(t *testing.T) {
	y, err := RenderRules([]*Spec{spec(t)})
	if err != nil {
		t.Fatal(err)
	}
	out := string(y)
	for _, want := range []string{
		"slo:error_ratio:rate5m", "slo:error_ratio:rate28d", "slo:error_budget_remaining",
		"SLOFastBurn", "> 14.4", "SLOSlowBurn", "SLOBudgetExhausted",
		`sum(rate(agent_runs_total{outcome=~"llm_unavailable|deadline|invalid_output"}[1h]))`,
	} {
		if !strings.Contains(out, want) {
			t.Errorf("rules missing %q", want)
		}
	}
}

func TestGateAdmitsHealthyService(t *testing.T) {
	d := Evaluate(context.Background(), fakeQ{ratios: map[string]float64{"28d": 0.002, "1h": 0.001, "6h": 0.002}}, spec(t), Request{ChangeType: "feature"}, now)
	if !d.Allowed || *d.BudgetRemaining < 0.79 || *d.BudgetRemaining > 0.81 {
		t.Fatalf("expected admit with 80%% budget, got %+v", d)
	}
}

func TestGateDeniesWhenBudgetLow(t *testing.T) {
	d := Evaluate(context.Background(), fakeQ{ratios: map[string]float64{"28d": 0.0095, "1h": 0.005, "6h": 0.005}}, spec(t), Request{ChangeType: "feature"}, now)
	if d.Allowed || !strings.Contains(d.Reasons[0], "below the 10.0% minimum") {
		t.Fatalf("expected deny, got %+v", d)
	}
}

func TestGateDeniesDuringFastBurnEvenWithBudget(t *testing.T) {
	d := Evaluate(context.Background(), fakeQ{ratios: map[string]float64{"28d": 0.001, "1h": 0.2, "6h": 0.03}}, spec(t), Request{ChangeType: "feature"}, now)
	if d.Allowed || len(d.Reasons) != 1 || !strings.Contains(d.Reasons[0], "1h burn rate 20.0x") {
		t.Fatalf("expected fast-burn deny, got %+v", d)
	}
}

func TestFixNeedsValidTicketWhileBlocked(t *testing.T) {
	q := fakeQ{ratios: map[string]float64{"28d": 0.02, "1h": 0.01, "6h": 0.01}}
	if d := Evaluate(context.Background(), q, spec(t), Request{ChangeType: "fix"}, now); d.Allowed {
		t.Fatal("fix without ticket must be denied")
	}
	if d := Evaluate(context.Background(), q, spec(t), Request{ChangeType: "fix", OverrideTicket: "please"}, now); d.Allowed {
		t.Fatal("malformed ticket must be denied")
	}
	d := Evaluate(context.Background(), q, spec(t), Request{ChangeType: "fix", OverrideTicket: "CHG-4821"}, now)
	if !d.Allowed || d.Override != "CHG-4821" {
		t.Fatalf("fix with ticket should pass, got %+v", d)
	}
	if d := Evaluate(context.Background(), q, spec(t), Request{ChangeType: "feature", OverrideTicket: "CHG-4821"}, now); d.Allowed {
		t.Fatal("a ticket must not let a feature through")
	}
}

func TestRollbackAlwaysAdmitted(t *testing.T) {
	d := Evaluate(context.Background(), fakeQ{err: errors.New("down")}, spec(t), Request{ChangeType: "rollback"}, now)
	if !d.Allowed {
		t.Fatal("rollback must always pass")
	}
}

func TestFailClosedAndFailOpen(t *testing.T) {
	s := spec(t)
	if d := Evaluate(context.Background(), fakeQ{err: errors.New("connection refused")}, s, Request{}, now); d.Allowed {
		t.Fatal("fail-closed gate must deny when Prometheus is down")
	}
	s.Gate.OnError = "open"
	if d := Evaluate(context.Background(), fakeQ{err: errors.New("connection refused")}, s, Request{}, now); !d.Allowed || !strings.Contains(d.Reasons[0], "WARNING") {
		t.Fatalf("fail-open gate must admit with a warning, got %+v", d)
	}
}

func TestNoTrafficIsAdmitted(t *testing.T) {
	if d := Evaluate(context.Background(), fakeQ{ratios: map[string]float64{}}, spec(t), Request{}, now); !d.Allowed {
		t.Fatal("new service with no traffic should be admitted")
	}
}

func TestPromClientAgainstFakeServer(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Authorization") != "Bearer tok" {
			w.WriteHeader(http.StatusUnauthorized)
			return
		}
		if strings.Contains(r.URL.Query().Get("query"), "[1h]") {
			w.Write([]byte(`{"status":"success","data":{"resultType":"vector","result":[{"metric":{},"value":[1,"0.25"]}]}}`))
			return
		}
		w.Write([]byte(`{"status":"success","data":{"resultType":"vector","result":[]}}`))
	}))
	defer srv.Close()
	c := &PromClient{BaseURL: srv.URL, Bearer: "tok"}
	v, found, err := c.Scalar(context.Background(), "x[1h]")
	if err != nil || !found || v != 0.25 {
		t.Fatalf("got %v %v %v", v, found, err)
	}
	if _, found, _ := c.Scalar(context.Background(), "x[6h]"); found {
		t.Fatal("empty result should be not-found")
	}
	bad := &PromClient{BaseURL: srv.URL}
	if _, _, err := bad.Scalar(context.Background(), "x"); err == nil {
		t.Fatal("expected auth error")
	}
}
