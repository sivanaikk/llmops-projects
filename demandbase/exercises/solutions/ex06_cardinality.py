class CardinalityGuard:
    def __init__(self, allowed, overflow="other"):
        self.allowed, self.overflow = allowed, overflow

    def label(self, name, value):
        allowed = self.allowed[name]
        return value if value in allowed else self.overflow


def series_count(events, guard, labels):
    return len({tuple(guard.label(n, e.get(n)) for n in labels) for e in events})
