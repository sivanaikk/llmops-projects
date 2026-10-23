# Runbook: error budget exhausted
Tags: error budget, slo, freeze, burn rate
1. The release gate (budgetgate) blocks non-reliability deploys automatically.
2. Only fixes that reduce error rate may ship, with an override ticket approved by the service owner and SRE.
3. Hold a reliability review; postmortem action items take priority over features.
