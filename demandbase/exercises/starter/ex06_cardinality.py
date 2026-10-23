"""Exercise 06: keep metric cardinality bounded.   (concept: 05-llm-observability/LEARN.md)

Every distinct label combination is a separate time series that the metrics
backend stores and bills for. One `user_id` label can turn 10 series into 10 million.

* CardinalityGuard(allowed: dict[str, set[str]], overflow="other")
    .label(name, value) -> value if it's in allowed[name], else overflow
    (a label name not in `allowed` at all is a programming error: raise KeyError)
* series_count(events, guard, labels) -> number of distinct label tuples after guarding,
    where events is a list of dicts and labels is the ordered list of label names to use.

Run:  make check EX=06
"""


class CardinalityGuard:
    def __init__(self, allowed: dict[str, set[str]], overflow: str = "other"):
        self.allowed, self.overflow = allowed, overflow

    def label(self, name: str, value: str | None) -> str:
        raise NotImplementedError


def series_count(events: list[dict], guard: CardinalityGuard, labels: list[str]) -> int:
    raise NotImplementedError
