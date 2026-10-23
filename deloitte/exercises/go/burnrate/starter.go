//go:build !solution

// Exercise 07 (Go): the error-budget release decision.   (concept: 02-error-budget-gate/LEARN.md)
//
// Implement the three functions below. Run:
//
//	make check-go          # your code (this file)
//	make check-go SOLUTION=1
package burnrate

// BurnRate is how fast the error budget is being spent relative to plan:
// errorRatio / (1 - objective). 1.0 means exactly on budget for the window.
func BurnRate(errorRatio, objective float64) float64 {
	panic("TODO: implement BurnRate")
}

// BudgetRemaining over the SLO window: 1 - errorRatioWindow/(1 - objective).
// Negative means the budget is overspent.
func BudgetRemaining(errorRatioWindow, objective float64) float64 {
	panic("TODO: implement BudgetRemaining")
}

// Policy for admitting a release.
type Policy struct {
	MinBudgetRemaining float64 // e.g. 0.10
	MaxFastBurn        float64 // 1h burn, e.g. 14.4
	MaxSlowBurn        float64 // 6h burn, e.g. 6
}

// Decide returns whether a release may ship and why not.
//   - changeType "rollback" is always allowed (never block the way out of an incident)
//   - otherwise deny when budget < MinBudgetRemaining, 1h burn > MaxFastBurn, or 6h burn > MaxSlowBurn
//   - a denied "fix" is allowed if hasTicket is true; a "feature" never is
//
// Reasons: one string per violated rule, in the order above (any wording).
func Decide(ratioWindow, ratio1h, ratio6h, objective float64, p Policy, changeType string, hasTicket bool) (bool, []string) {
	panic("TODO: implement Decide")
}
