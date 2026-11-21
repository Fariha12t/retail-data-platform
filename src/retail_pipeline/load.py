"""Idempotent loading into the warehouse raw schema."""
from __future__ import annotations

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from .audit import utcnow
from .contracts import PG_TYPES, TableContract


def ensure_raw_table(conn, contract: TableContract) -> None:
    cols = ", ".join(f'"{c.name}" {PG_TYPES[c.dtype]}' for c in contract.columns)
    conn.execute(text("create schema if not exists raw"))
    conn.execute(
        text(
            f'create table if not exists raw."{contract.name}" ({cols}, '
            f"_batch_id text not null, _ingested_at timestamp not null, _source_file text)"
        )
    )
    conn.execute(text(f'create index if not exists "ix_raw_{contract.name}_batch" on raw."{contract.name}" (_batch_id)'))


def load_raw(engine: Engine, contract: TableContract, df: pd.DataFrame, batch_id: str, source_file: str) -> int:
    """Replace the rows of one batch in a single transaction (delete + insert = idempotent)."""
    with engine.begin() as conn:
        ensure_raw_table(conn, contract)
        conn.execute(text(f'delete from raw."{contract.name}" where _batch_id = :b'), {"b": batch_id})
        if df.empty:
            return 0
        out = df.copy()
        out["_batch_id"] = batch_id
        out["_ingested_at"] = utcnow()
        out["_source_file"] = source_file
        out.to_sql(contract.name, conn, schema="raw", if_exists="append", index=False, method="multi", chunksize=2000)
        return len(out)
