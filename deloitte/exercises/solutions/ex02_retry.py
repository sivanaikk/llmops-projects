class DeadlineExceeded(Exception):
    pass


def retry_call(fn, is_retryable, attempts, base, max_delay, deadline_remaining, sleep, rng):
    for n in range(1, attempts + 1):
        if deadline_remaining() <= 0:
            raise DeadlineExceeded()
        try:
            return fn()
        except Exception as e:
            if not is_retryable(e) or n == attempts:
                raise
            delay = rng.uniform(0, min(max_delay, base * 2 ** (n - 1)))
            sleep(min(delay, max(0.0, deadline_remaining())))
