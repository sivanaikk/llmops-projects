import math


def in_flight(rps, latency_s):
    return rps * latency_s


def replicas(rps, p95_latency_s, per_pod_concurrency, headroom, zones):
    return max(zones, math.ceil(in_flight(rps, p95_latency_s) * (1 + headroom) / per_pod_concurrency))


def tokens_per_second(rps, tokens_per_run):
    return rps * tokens_per_run
