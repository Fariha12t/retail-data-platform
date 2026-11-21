import pytest

from retail_pipeline.retry import retry


def test_retries_then_succeeds():
    calls, sleeps = [], []

    @retry(attempts=4, base_delay=1, sleep=sleeps.append)
    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise ConnectionError("boom")
        return "ok"

    assert flaky() == "ok"
    assert len(calls) == 3 and len(sleeps) == 2


def test_raises_after_max_attempts():
    calls = []

    @retry(attempts=3, sleep=lambda _: None)
    def always_fails():
        calls.append(1)
        raise ValueError("nope")

    with pytest.raises(ValueError):
        always_fails()
    assert len(calls) == 3


def test_only_listed_exceptions_are_retried():
    calls = []

    @retry(attempts=5, exceptions=(ConnectionError,), sleep=lambda _: None)
    def wrong_error():
        calls.append(1)
        raise KeyError("x")

    with pytest.raises(KeyError):
        wrong_error()
    assert len(calls) == 1
