//go:build solution

package burnrate

import "fmt"

func BurnRate(errorRatio, objective float64) float64 { return errorRatio / (1 - objective) }

func BudgetRemaining(errorRatioWindow, objective float64) float64 {
	return 1 - errorRatioWindow/(1-objective)
}

type Policy struct {
	MinBudgetRemaining float64
	MaxFastBurn        float64
	MaxSlowBurn        float64
}

func Decide(ratioWindow, ratio1h, ratio6h, objective float64, p Policy, changeType string, hasTicket bool) (bool, []string) {
	if changeType == "rollback" {
		return true, nil
	}
	var reasons []string
	if r := BudgetRemaining(ratioWindow, objective); r < p.MinBudgetRemaining {
		reasons = append(reasons, fmt.Sprintf("budget %.0f%% below %.0f%%", r*100, p.MinBudgetRemaining*100))
	}
	if b := BurnRate(ratio1h, objective); b > p.MaxFastBurn {
		reasons = append(reasons, fmt.Sprintf("1h burn %.1fx", b))
	}
	if b := BurnRate(ratio6h, objective); b > p.MaxSlowBurn {
		reasons = append(reasons, fmt.Sprintf("6h burn %.1fx", b))
	}
	if len(reasons) == 0 {
		return true, nil
	}
	if changeType == "fix" && hasTicket {
		return true, reasons
	}
	return false, reasons
}
