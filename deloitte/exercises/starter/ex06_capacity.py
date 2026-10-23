"""Exercise 06: capacity planning with Little's law.

Little's law: average number in the system  L = lambda * W
(arrival rate x time each request spends in the system).

Agent requests take seconds, so a modest request rate needs a lot of concurrency.

* in_flight(rps, latency_s) -> L
* replicas(rps, p95_latency_s, per_pod_concurrency, headroom, zones) ->
      ceil(in_flight(rps, p95) * (1 + headroom) / per_pod_concurrency), but at least `zones`
      (one pod per availability zone, so losing a zone doesn't take you to zero)
* tokens_per_second(rps, tokens_per_run) -> load on the model tier

Run:  make check EX=06
"""


def in_flight(rps: float, latency_s: float) -> float:
    raise NotImplementedError


def replicas(rps: float, p95_latency_s: float, per_pod_concurrency: int, headroom: float, zones: int) -> int:
    raise NotImplementedError


def tokens_per_second(rps: float, tokens_per_run: float) -> float:
    raise NotImplementedError
