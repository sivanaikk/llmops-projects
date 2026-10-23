package slo

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"regexp"
	"strconv"
	"time"
)

// Querier evaluates an instant PromQL query that returns a single value.
type Querier interface {
	Scalar(ctx context.Context, query string) (value float64, found bool, err error)
}

// PromClient queries the Prometheus HTTP API (also works with Thanos, Mimir,
// Azure Monitor managed Prometheus and Amazon Managed Prometheus endpoints).
type PromClient struct {
	BaseURL string
	Bearer  string
	HTTP    *http.Client
}

func (p *PromClient) Scalar(ctx context.Context, query string) (float64, bool, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, p.BaseURL+"/api/v1/query?query="+url.QueryEscape(query), nil)
	if err != nil {
		return 0, false, err
	}
	if p.Bearer != "" {
		req.Header.Set("Authorization", "Bearer "+p.Bearer)
	}
	client := p.HTTP
	if client == nil {
		client = &http.Client{Timeout: 10 * time.Second}
	}
	resp, err := client.Do(req)
	if err != nil {
		return 0, false, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return 0, false, fmt.Errorf("prometheus returned %s", resp.Status)
	}
	var body struct {
		Status string `json:"status"`
		Data   struct {
			Result []struct {
				Value [2]any `json:"value"`
			} `json:"result"`
		} `json:"data"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
		return 0, false, err
	}
	if body.Status != "success" {
		return 0, false, fmt.Errorf("query failed: %s", body.Status)
	}
	if len(body.Data.Result) == 0 {
		return 0, false, nil
	}
	s, ok := body.Data.Result[0].Value[1].(string)
	if !ok {
		return 0, false, fmt.Errorf("unexpected value type")
	}
	v, err := strconv.ParseFloat(s, 64)
	return v, err == nil, err
}

// Request describes the release asking for admission.
type Request struct {
	ChangeType     string // "feature" | "fix" | "rollback"
	OverrideTicket string // e.g. CHG-1234, approved outside the pipeline (segregation of duties)
}

// Decision is what the gate prints (as JSON) and turns into an exit code.
type Decision struct {
	Service         string   `json:"service"`
	SLO             string   `json:"slo"`
	Allowed         bool     `json:"allowed"`
	Reasons         []string `json:"reasons"`
	BudgetRemaining *float64 `json:"budget_remaining,omitempty"`
	Burn1h          *float64 `json:"burn_rate_1h,omitempty"`
	Burn6h          *float64 `json:"burn_rate_6h,omitempty"`
	Override        string   `json:"override,omitempty"`
	CheckedAt       string   `json:"checked_at"`
}

var ticketRe = regexp.MustCompile(`^(CHG|INC)-\d{3,}$`)

// Evaluate decides whether a release may proceed. It queries the raw SLI
// (not the recording rules) so it works even before the rules are deployed.
func Evaluate(ctx context.Context, q Querier, s *Spec, req Request, now time.Time) Decision {
	d := Decision{Service: s.Service, SLO: s.Name, Allowed: true, CheckedAt: now.UTC().Format(time.RFC3339)}

	// Rollbacks always go through: blocking the way back out of an incident makes it worse.
	if req.ChangeType == "rollback" {
		d.Reasons = append(d.Reasons, "rollback: always admitted")
		return d
	}

	query := func(window string) (*float64, error) {
		v, found, err := q.Scalar(ctx, s.ratioExpr(window))
		if err != nil || !found {
			return nil, err
		}
		return &v, nil
	}
	ratioWindow, err1 := query(s.Window)
	ratio1h, err2 := query("1h")
	ratio6h, err3 := query("6h")
	if err := firstErr(err1, err2, err3); err != nil {
		if s.Gate.OnError == "open" {
			d.Reasons = append(d.Reasons, "WARNING: SLO data unavailable, gate configured fail-open: "+err.Error())
			return d
		}
		d.Allowed = false
		d.Reasons = append(d.Reasons, "SLO data unavailable, gate is fail-closed: "+err.Error())
		return d
	}
	if ratioWindow == nil {
		d.Reasons = append(d.Reasons, "no traffic in the SLO window yet: admitted")
		return d
	}

	budget := s.ErrorBudget()
	remaining := 1 - *ratioWindow/budget
	d.BudgetRemaining = &remaining
	var blockers []string
	if remaining < s.Gate.MinBudgetRemaining {
		blockers = append(blockers, fmt.Sprintf("error budget remaining %.1f%% is below the %.1f%% minimum",
			remaining*100, s.Gate.MinBudgetRemaining*100))
	}
	if ratio1h != nil {
		b := *ratio1h / budget
		d.Burn1h = &b
		if b > s.Gate.MaxFastBurn {
			blockers = append(blockers, fmt.Sprintf("1h burn rate %.1fx exceeds %.1fx: an incident is likely in progress", b, s.Gate.MaxFastBurn))
		}
	}
	if ratio6h != nil {
		b := *ratio6h / budget
		d.Burn6h = &b
		if b > s.Gate.MaxSlowBurn {
			blockers = append(blockers, fmt.Sprintf("6h burn rate %.1fx exceeds %.1fx", b, s.Gate.MaxSlowBurn))
		}
	}
	if len(blockers) == 0 {
		d.Reasons = append(d.Reasons, fmt.Sprintf("budget %.1f%% remaining; burn rates within policy", remaining*100))
		return d
	}

	// Error-budget policy: only reliability fixes may ship while blocked, and
	// only with a change ticket approved by someone other than the author.
	if req.ChangeType == "fix" && ticketRe.MatchString(req.OverrideTicket) {
		d.Override = req.OverrideTicket
		d.Reasons = append(blockers, "admitted as a reliability fix under "+req.OverrideTicket)
		return d
	}
	d.Allowed = false
	d.Reasons = blockers
	if req.ChangeType == "fix" {
		d.Reasons = append(d.Reasons, "fix releases need --override-ticket CHG-#### or INC-#### to pass while blocked")
	}
	return d
}

func firstErr(errs ...error) error {
	for _, e := range errs {
		if e != nil {
			return e
		}
	}
	return nil
}
