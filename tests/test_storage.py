import pandas as pd

from retail_pipeline.storage import LocalStore


def test_roundtrip_list_and_size(tmp_path):
    store = LocalStore(tmp_path)
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    store.put_dataframe(df, "raw/csv/t/ingest_date=2026-01-01/b1.parquet")
    store.put_dataframe(df, "quarantine/t/b1.parquet")
    pd.testing.assert_frame_equal(store.get_dataframe("raw/csv/t/ingest_date=2026-01-01/b1.parquet"), df)
    assert store.list_keys("raw/") == ["raw/csv/t/ingest_date=2026-01-01/b1.parquet"]
    assert store.size_bytes("raw/") > 0 and store.size_bytes("nothing/") == 0
