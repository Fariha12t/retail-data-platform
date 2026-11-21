import pandas as pd
import pytest

from retail_pipeline.contracts import CONTRACTS
from retail_pipeline.validation import SchemaError, validate


def order_item_rows(**overrides):
    row = {"order_item_id": 1, "order_id": 10, "product_id": 5, "quantity": 2, "unit_price": 9.5,
           "discount": 0.1, "updated_at": "2026-01-01 10:00:00"}
    row.update(overrides)
    return row


def test_valid_rows_pass_and_are_typed():
    df = pd.DataFrame([order_item_rows(), order_item_rows(order_item_id=2)])
    res = validate(df, CONTRACTS["order_items"])
    assert res.rows_valid == 2 and res.rows_quarantined == 0
    assert str(res.clean["quantity"].dtype) == "Int64"
    assert pd.api.types.is_datetime64_any_dtype(res.clean["updated_at"])


@pytest.mark.parametrize(
    "bad, reason",
    [
        ({"quantity": 0}, "quantity:below_min"),
        ({"quantity": "abc"}, "quantity:invalid_type"),
        ({"quantity": 2.5}, "quantity:invalid_type"),
        ({"unit_price": -1}, "unit_price:below_min"),
        ({"discount": 1.5}, "discount:above_max"),
        ({"order_id": None}, "order_id:null"),
        ({"updated_at": "not a date"}, "updated_at:invalid_type"),
    ],
)
def test_bad_rows_are_quarantined_with_reason(bad, reason):
    df = pd.DataFrame([order_item_rows(), order_item_rows(order_item_id=2, **bad)])
    res = validate(df, CONTRACTS["order_items"])
    assert res.rows_valid == 1
    assert res.rows_quarantined == 1
    assert reason in res.quarantine.iloc[0]["_reasons"]
    assert res.issues[reason] == 1


def test_duplicates_keep_latest_version():
    df = pd.DataFrame([
        order_item_rows(quantity=1, updated_at="2026-01-01 10:00:00"),
        order_item_rows(quantity=3, updated_at="2026-01-01 12:00:00"),
        order_item_rows(quantity=2, updated_at="2026-01-01 11:00:00"),
    ])
    res = validate(df, CONTRACTS["order_items"])
    assert res.duplicates_removed == 2
    assert res.clean.iloc[0]["quantity"] == 3


def test_missing_column_is_schema_drift():
    df = pd.DataFrame([order_item_rows()]).drop(columns=["unit_price"])
    with pytest.raises(SchemaError, match="unit_price"):
        validate(df, CONTRACTS["order_items"])


def test_extra_columns_are_reported_and_dropped():
    df = pd.DataFrame([order_item_rows(new_col="x")])
    res = validate(df, CONTRACTS["order_items"])
    assert res.extra_columns == ["new_col"]
    assert "new_col" not in res.clean.columns


def test_string_rules_email_and_allowed_values():
    base = {"customer_id": 1, "email": "a@b.com", "full_name": "A B", "city": "X", "country": "IN",
            "segment": "Premium", "signup_date": "2026-01-01", "updated_at": "2026-01-02 00:00:00"}
    df = pd.DataFrame([base, {**base, "customer_id": 2, "email": "a#b.com"}, {**base, "customer_id": 3, "segment": "vip"}])
    res = validate(df, CONTRACTS["customers"])
    assert res.rows_valid == 1  # "Premium" is accepted case-insensitively
    assert set(res.issues) == {"email:bad_format", "segment:not_allowed"}
    assert res.clean.iloc[0]["segment"] == "premium"


def test_blank_strings_count_as_null_for_numbers():
    row = {"snapshot_date": "2026-01-01", "product_id": "", "warehouse": "BLR", "stock_on_hand": "5", "reorder_level": "10"}
    res = validate(pd.DataFrame([row]), CONTRACTS["inventory_snapshots"])
    assert res.rows_quarantined == 1 and "product_id:null" in res.issues


def test_empty_frame_is_fine():
    df = pd.DataFrame(columns=CONTRACTS["orders"].column_names)
    res = validate(df, CONTRACTS["orders"])
    assert res.rows_in == 0 and res.rows_valid == 0
