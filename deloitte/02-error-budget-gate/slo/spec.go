// Package slo turns SLO specs into Prometheus rules and release decisions.
package slo

import (
	"fmt"
	"os"
	"regexp"
	"strconv"
	"strings"
	"time"

	"gopkg.in/yaml.v3"
)

// Spec is one SLO, co-owned by the product team and SRE.
type Spec struct {
	Service     string  `yaml:"service"`
	Name        string  `yaml:"name"`
	Description string  `yaml:"description"`
	Owner       string  `yaml:"owner"`
	Objective   float64 `yaml:"objective"` // e.g. 0.995
	Window      string  `yaml:"window"`    // e.g. 28d
	SLI         SLI     `yaml:"sli"`
	Gate        Gate    `yaml:"gate"`
}

// SLI is a ratio of bad events to all events, both as counter selectors.
// They are wrapped as sum(rate(<selector>[<range>])) so one spec yields every window.
type SLI struct {
	Errors string `yaml:"errors"`
	Total  string `yaml:"total"`
}

// Gate is the release-admission policy for the service.
type Gate struct {
	// Deny releases when less than this fraction of the budget is left.
	MinBudgetRemaining float64 `yaml:"min_budget_remaining"`
	// Deny while the 1h burn rate is above this (14.4 = 2% of a 28d budget per hour).
	MaxFastBurn float64 `yaml:"max_fast_burn"`
	// Deny while the 6h burn rate is above this.
	MaxSlowBurn float64 `yaml:"max_slow_burn"`
	// When Prometheus can't be reached: "closed" (deny) or "open" (allow and warn).
	OnError string `yaml:"on_error"`
}

var selectorRe = regexp.MustCompile(`^[a-zA-Z_:][a-zA-Z0-9_:]*(\{.*\})?$`)

// Load reads one spec file and applies defaults.
func Load(path string) (*Spec, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var s Spec
	if err := yaml.Unmarshal(raw, &s); err != nil {
		return nil, fmt.Errorf("%s: %w", path, err)
	}
	s.applyDefaults()
	if err := s.Validate(); err != nil {
		return nil, fmt.Errorf("%s: %w", path, err)
	}
	return &s, nil
}

func (s *Spec) applyDefaults() {
	if s.Window == "" {
		s.Window = "28d"
	}
	if s.Name == "" {
		s.Name = "availability"
	}
	if s.Gate.MaxFastBurn == 0 {
		s.Gate.MaxFastBurn = 14.4
	}
	if s.Gate.MaxSlowBurn == 0 {
		s.Gate.MaxSlowBurn = 6
	}
	if s.Gate.OnError == "" {
		s.Gate.OnError = "closed"
	}
}

// Validate rejects specs that would generate broken or meaningless rules.
func (s *Spec) Validate() error {
	var errs []string
	if !regexp.MustCompile(`^[a-z0-9][a-z0-9-]*$`).MatchString(s.Service) {
		errs = append(errs, "service must be lowercase kebab-case")
	}
	if s.Objective <= 0 || s.Objective >= 1 {
		errs = append(errs, "objective must be between 0 and 1 (exclusive)")
	}
	if _, err := ParseDuration(s.Window); err != nil {
		errs = append(errs, err.Error())
	}
	for name, sel := range map[string]string{"sli.errors": s.SLI.Errors, "sli.total": s.SLI.Total} {
		if !selectorRe.MatchString(strings.TrimSpace(sel)) {
			errs = append(errs, name+" must be a counter selector like metric_total{label=\"x\"}")
		}
	}
	if s.Gate.OnError != "closed" && s.Gate.OnError != "open" {
		errs = append(errs, "gate.on_error must be closed or open")
	}
	if len(errs) > 0 {
		return fmt.Errorf("invalid SLO %q: %s", s.Service, strings.Join(errs, "; "))
	}
	return nil
}

// ErrorBudget is the allowed bad-event fraction.
func (s *Spec) ErrorBudget() float64 { return 1 - s.Objective }

// ParseDuration accepts Prometheus-style durations including days and weeks.
func ParseDuration(v string) (time.Duration, error) {
	m := regexp.MustCompile(`^(\d+)([smhdw])$`).FindStringSubmatch(v)
	if m == nil {
		return 0, fmt.Errorf("window %q must look like 28d, 6h or 30m", v)
	}
	n, _ := strconv.Atoi(m[1])
	unit := map[string]time.Duration{"s": time.Second, "m": time.Minute, "h": time.Hour, "d": 24 * time.Hour, "w": 7 * 24 * time.Hour}[m[2]]
	return time.Duration(n) * unit, nil
}
