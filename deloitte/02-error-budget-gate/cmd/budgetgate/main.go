// budgetgate: SLOs as code and error-budget-based production admission.
//
//	budgetgate rules  --slos slos/                      # Prometheus rules for every SLO
//	budgetgate check  --slo slos/agent-runtime.yaml \
//	                  --prometheus http://prometheus:9090 --change-type feature
//
// check exits 0 (admit), 1 (deny) or 2 (usage/config error). It is run as a CI
// job before production deploys and as an Argo CD PreSync hook, so the same
// policy applies whichever way a release is attempted.
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"time"

	"github.com/sivanaikk/llmops-projects/deloitte/budgetgate/slo"
)

func main() {
	if len(os.Args) < 2 {
		usage()
	}
	switch os.Args[1] {
	case "rules":
		os.Exit(rules(os.Args[2:]))
	case "check":
		os.Exit(check(os.Args[2:]))
	default:
		usage()
	}
}

func usage() {
	fmt.Fprintln(os.Stderr, "usage: budgetgate rules|check [flags]  (-h for flags)")
	os.Exit(2)
}

func loadDir(dir string) ([]*slo.Spec, error) {
	paths, _ := filepath.Glob(filepath.Join(dir, "*.yaml"))
	sort.Strings(paths)
	if len(paths) == 0 {
		return nil, fmt.Errorf("no *.yaml SLO specs in %s", dir)
	}
	var specs []*slo.Spec
	for _, p := range paths {
		s, err := slo.Load(p)
		if err != nil {
			return nil, err
		}
		specs = append(specs, s)
	}
	return specs, nil
}

func rules(args []string) int {
	fs := flag.NewFlagSet("rules", flag.ExitOnError)
	dir := fs.String("slos", "slos", "directory of SLO specs")
	out := fs.String("out", "", "write here instead of stdout")
	_ = fs.Parse(args)
	specs, err := loadDir(*dir)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 2
	}
	y, err := slo.RenderRules(specs)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 2
	}
	if *out == "" {
		os.Stdout.Write(y)
		return 0
	}
	if err := os.WriteFile(*out, y, 0o644); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 2
	}
	return 0
}

func check(args []string) int {
	fs := flag.NewFlagSet("check", flag.ExitOnError)
	spec := fs.String("slo", "", "SLO spec file")
	prom := fs.String("prometheus", os.Getenv("PROMETHEUS_URL"), "Prometheus base URL")
	change := fs.String("change-type", "feature", "feature | fix | rollback")
	ticket := fs.String("override-ticket", "", "approved change/incident ticket allowing a fix while blocked")
	timeout := fs.Duration("timeout", 15*time.Second, "query timeout")
	_ = fs.Parse(args)
	if *spec == "" || *prom == "" {
		fmt.Fprintln(os.Stderr, "check needs --slo and --prometheus (or PROMETHEUS_URL)")
		return 2
	}
	if *change != "feature" && *change != "fix" && *change != "rollback" {
		fmt.Fprintln(os.Stderr, "--change-type must be feature, fix or rollback")
		return 2
	}
	s, err := slo.Load(*spec)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 2
	}
	ctx, cancel := context.WithTimeout(context.Background(), *timeout)
	defer cancel()
	q := &slo.PromClient{BaseURL: *prom, Bearer: os.Getenv("PROMETHEUS_BEARER_TOKEN")}
	d := slo.Evaluate(ctx, q, s, slo.Request{ChangeType: *change, OverrideTicket: *ticket}, time.Now())
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	_ = enc.Encode(d)
	if d.Allowed {
		return 0
	}
	return 1
}
