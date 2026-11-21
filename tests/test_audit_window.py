from datetime import date, datetime, timedelta

from retail_pipeline.audit import compute_window

HIST = datetime(2026, 1, 1)
LB = timedelta(hours=6)


def test_first_run_starts_at_history_start():
    start, end = compute_window(date(2026, 3, 10), None, None, LB, HIST)
    assert start == HIST and end == datetime(2026, 3, 11)


def test_next_run_starts_at_watermark_minus_lookback():
    start, end = compute_window(date(2026, 3, 11), datetime(2026, 3, 11), None, LB, HIST)
    assert start == datetime(2026, 3, 10, 18) and end == datetime(2026, 3, 12)


def test_rerun_of_successful_date_reuses_identical_window():
    prev = (datetime(2026, 3, 10, 18), datetime(2026, 3, 11))
    # watermark has since moved on - the window must still be the original one (idempotent re-run)
    assert compute_window(date(2026, 3, 10), datetime(2026, 3, 20), prev, LB, HIST) == prev
