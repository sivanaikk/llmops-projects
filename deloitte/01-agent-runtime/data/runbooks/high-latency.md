# Runbook: high latency
Tags: latency, p95, slow, timeout
1. Check whether the latency is in the service or a dependency (traces, span breakdown).
2. Check saturation: CPU throttling, connection pool exhaustion, queue depth.
3. If a deploy happened in the last hour, roll back first and investigate after.
4. Scale out if saturation is the cause and the HPA has not reacted.
