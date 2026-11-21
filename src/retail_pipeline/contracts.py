"""Data contracts: the expected schema and quality rules for every ingested table."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Column:
    name: str
    dtype: str  # string | int | float | datetime | date
    nullable: bool = True
    min: float | None = None
    max: float | None = None
    allowed: tuple[str, ...] | None = None
    regex: str | None = None


@dataclass(frozen=True)
class TableContract:
    name: str
    source: str  # postgres | csv | api
    primary_key: tuple[str, ...]
    columns: tuple[Column, ...]
    version_column: str | None = None  # latest version wins when duplicates exist
    incremental_column: str | None = None
    lookback_hours: int = 6
    description: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]


STATUSES = ("placed", "shipped", "delivered", "cancelled", "returned")
CHANNELS = ("organic", "paid_search", "social", "email", "affiliate")
EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

CONTRACTS: dict[str, TableContract] = {
    "customers": TableContract(
        name="customers",
        source="postgres",
        primary_key=("customer_id",),
        version_column="updated_at",
        incremental_column="updated_at",
        description="Customer master data from the operational database",
        columns=(
            Column("customer_id", "int", nullable=False, min=1),
            Column("email", "string", nullable=False, regex=EMAIL_RE),
            Column("full_name", "string", nullable=False),
            Column("city", "string"),
            Column("country", "string"),
            Column("segment", "string", nullable=False, allowed=("consumer", "premium", "business")),
            Column("signup_date", "date", nullable=False),
            Column("updated_at", "datetime", nullable=False),
        ),
    ),
    "orders": TableContract(
        name="orders",
        source="postgres",
        primary_key=("order_id",),
        version_column="updated_at",
        incremental_column="updated_at",
        description="E-commerce order headers",
        columns=(
            Column("order_id", "int", nullable=False, min=1),
            Column("customer_id", "int", nullable=False, min=1),
            Column("order_ts", "datetime", nullable=False),
            Column("status", "string", nullable=False, allowed=STATUSES),
            Column("channel", "string", nullable=False, allowed=CHANNELS),
            Column("updated_at", "datetime", nullable=False),
        ),
    ),
    "order_items": TableContract(
        name="order_items",
        source="postgres",
        primary_key=("order_item_id",),
        version_column="updated_at",
        incremental_column="updated_at",
        description="Order line items",
        columns=(
            Column("order_item_id", "int", nullable=False, min=1),
            Column("order_id", "int", nullable=False, min=1),
            Column("product_id", "int", nullable=False, min=1),
            Column("quantity", "int", nullable=False, min=1, max=100),
            Column("unit_price", "float", nullable=False, min=0),
            Column("discount", "float", nullable=False, min=0, max=1),
            Column("updated_at", "datetime", nullable=False),
        ),
    ),
    "payments": TableContract(
        name="payments",
        source="postgres",
        primary_key=("payment_id",),
        version_column="updated_at",
        incremental_column="updated_at",
        description="Payment-system transactions",
        columns=(
            Column("payment_id", "int", nullable=False, min=1),
            Column("order_id", "int", nullable=False, min=1),
            Column("method", "string", nullable=False, allowed=("card", "upi", "wallet", "cod", "netbanking")),
            Column("amount", "float", nullable=False, min=0),
            Column("status", "string", nullable=False, allowed=("captured", "failed", "refunded")),
            Column("paid_at", "datetime", nullable=False),
            Column("updated_at", "datetime", nullable=False),
        ),
    ),
    "products": TableContract(
        name="products",
        source="csv",
        primary_key=("product_id",),
        version_column="updated_at",
        incremental_column="updated_at",
        description="Product catalogue delivered as a CSV drop",
        columns=(
            Column("product_id", "int", nullable=False, min=1),
            Column("sku", "string", nullable=False),
            Column("product_name", "string", nullable=False),
            Column("category", "string", nullable=False),
            Column("brand", "string"),
            Column("unit_cost", "float", nullable=False, min=0),
            Column("list_price", "float", nullable=False, min=0),
            Column("updated_at", "datetime", nullable=False),
        ),
    ),
    "inventory_snapshots": TableContract(
        name="inventory_snapshots",
        source="csv",
        primary_key=("snapshot_date", "product_id", "warehouse"),
        description="Daily stock level files per warehouse",
        lookback_hours=24,
        columns=(
            Column("snapshot_date", "date", nullable=False),
            Column("product_id", "int", nullable=False, min=1),
            Column("warehouse", "string", nullable=False),
            Column("stock_on_hand", "int", nullable=False, min=0),
            Column("reorder_level", "int", nullable=False, min=0),
        ),
    ),
    "marketing_spend": TableContract(
        name="marketing_spend",
        source="api",
        primary_key=("spend_date", "channel", "campaign"),
        description="Daily marketing spend pulled from a REST API (late corrections are re-pulled)",
        lookback_hours=72,
        columns=(
            Column("spend_date", "date", nullable=False),
            Column("channel", "string", nullable=False, allowed=CHANNELS),
            Column("campaign", "string", nullable=False),
            Column("impressions", "int", nullable=False, min=0),
            Column("clicks", "int", nullable=False, min=0),
            Column("spend", "float", nullable=False, min=0),
            Column("currency", "string", nullable=False),
        ),
    ),
}

PG_TYPES = {
    "string": "text",
    "int": "bigint",
    "float": "numeric(18,4)",
    "datetime": "timestamp",
    "date": "date",
}
