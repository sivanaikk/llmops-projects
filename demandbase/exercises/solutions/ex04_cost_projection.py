def shadow_price(model, prompt_tokens, completion_tokens, table):
    inp, out = table.get(model, (0.0, 0.0))
    return (prompt_tokens * inp + completion_tokens * out) / 1_000_000


def project_month_end(spend_so_far, day_of_month, hour, days_in_month):
    elapsed = max((day_of_month - 1) + hour / 24, 1 / 24)
    return spend_so_far / elapsed * days_in_month


def alert(spend, projected, budget):
    out = []
    used = spend / budget
    if used >= 1:
        out.append(("critical", f"{used:.0%} of budget used"))
    elif used >= 0.8:
        out.append(("warning", f"{used:.0%} of budget used"))
    elif used >= 0.5:
        out.append(("info", f"{used:.0%} of budget used"))
    if projected > budget and spend < budget:
        out.append(("warning", f"on pace for ${projected:.2f} vs ${budget:.2f}"))
    return out
