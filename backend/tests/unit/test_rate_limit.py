from giftai.core.rate_limit import FixedWindowRateLimiter


class _FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_requests_within_the_limit_are_allowed_then_blocked() -> None:
    clock = _FakeClock()
    limiter = FixedWindowRateLimiter(limit=2, window_seconds=60, clock=clock)

    assert limiter.acquire("user-a") is None
    assert limiter.acquire("user-a") is None
    retry_after = limiter.acquire("user-a")

    assert retry_after is not None
    assert 1 <= retry_after <= 60


def test_each_caller_has_their_own_budget() -> None:
    limiter = FixedWindowRateLimiter(limit=1, window_seconds=60, clock=_FakeClock())

    assert limiter.acquire("user-a") is None
    assert limiter.acquire("user-b") is None


def test_the_budget_resets_in_the_next_window() -> None:
    clock = _FakeClock()
    limiter = FixedWindowRateLimiter(limit=1, window_seconds=60, clock=clock)
    limiter.acquire("user-a")

    clock.now += 60

    assert limiter.acquire("user-a") is None
