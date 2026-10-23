"""Exercise 02: retry with exponential backoff, full jitter and a deadline.

Retries turn a blip into a success, and a real outage into a pile-up. The rules:

* Retry only errors that `is_retryable(exc)` says are transient (429, 5xx, timeouts).
  A 400 will fail the same way every time; retrying it wastes time and money.
* Backoff: attempt n (1-based) sleeps  uniform(0, min(max_delay, base * 2**(n-1)))
  ("full jitter", so many clients don't retry in lock-step).
* Never sleep past the deadline: cap each sleep at `deadline_remaining()`, and if
  `deadline_remaining() <= 0` before an attempt, raise DeadlineExceeded.
* After the last attempt, re-raise the last error.
* Use the injected `sleep` and `rng` (random.Random), never time.sleep/random directly.

Run:  make check EX=02
"""


class DeadlineExceeded(Exception):
    pass


def retry_call(fn, is_retryable, attempts, base, max_delay, deadline_remaining, sleep, rng):
    raise NotImplementedError
