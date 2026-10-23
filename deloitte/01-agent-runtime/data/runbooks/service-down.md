# Runbook: service down
Tags: down, outage, 5xx, unavailable, crashloop
1. Declare an incident and assign an incident commander.
2. Check recent deploys and config changes; roll back the most recent one.
3. Check pods: CrashLoopBackOff, OOMKilled, failed readiness probes.
4. Communicate status every 30 minutes to stakeholders.
