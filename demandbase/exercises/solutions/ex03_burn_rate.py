def error_budget(slo):
    return 1 - slo


def burn_rate(error_ratio, slo):
    return error_ratio / error_budget(slo)


def budget_spent(burn, hours, window_days=28):
    return burn * hours / (window_days * 24)


def should_page(ratio_1h, ratio_5m, slo, factor=14.4):
    return burn_rate(ratio_1h, slo) > factor and burn_rate(ratio_5m, slo) > factor


def hours_to_exhaustion(remaining, burn, window_days=28):
    if burn <= 0:
        return float("inf")
    return remaining * window_days * 24 / burn
