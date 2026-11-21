import threading
from datetime import date

import pandas as pd
import pytest
import requests

from retail_pipeline import mock_api
from retail_pipeline.contracts import CONTRACTS
from retail_pipeline.validation import validate


@pytest.fixture()
def server():
    srv = mock_api.serve("127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_rows_are_deterministic():
    assert mock_api.rows_for_day(date(2026, 1, 5)) == mock_api.rows_for_day(date(2026, 1, 5))


def test_api_range_is_end_exclusive(server):
    data = requests.get(f"{server}/v1/marketing/spend", params={"start": "2026-01-01", "end": "2026-01-03"}, timeout=5).json()["data"]
    assert {r["spend_date"] for r in data} == {"2026-01-01", "2026-01-02"}


def test_api_validates_params(server):
    assert requests.get(f"{server}/v1/marketing/spend", timeout=5).status_code == 400


def test_flaky_api_returns_503(server, monkeypatch):
    monkeypatch.setenv("MOCK_API_FLAKY", "1")
    assert requests.get(f"{server}/v1/marketing/spend?start=2026-01-01&end=2026-01-02", timeout=5).status_code == 503


def test_api_output_passes_through_contract():
    rows = [r for d in range(1, 29) for r in mock_api.rows_for_day(date(2026, 2, d))]
    res = validate(pd.DataFrame(rows).astype("string"), CONTRACTS["marketing_spend"])
    assert res.rows_valid > 100
