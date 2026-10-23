# Runbook: tool dependency down (AgentToolCircuitOpen)

The circuit breaker is doing its job: calls to the failing tool fail fast, and
the agent gets an error observation instead of hanging.

1. Which tool? The alert label `tool`. Check that dependency's own health and its owner's status page.
2. User impact: answers that need the tool degrade to "couldn't look it up". Tell the product owner.
3. If the dependency stays down for a long time, consider removing the tool from the
   registry (config change) so the model stops trying it and wasting steps.
4. The breaker half-opens every 30s; recovery is automatic once the dependency is back.
