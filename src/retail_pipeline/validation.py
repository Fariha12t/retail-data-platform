"""Schema validation, type coercion, quality rules, quarantine and de-duplication."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .contracts import Column, TableContract


class SchemaError(Exception):
    """Raised when the incoming data no longer matches the contract (schema drift)."""


@dataclass
class ValidationResult:
    clean: pd.DataFrame
    quarantine: pd.DataFrame
    rows_in: int
    duplicates_removed: int = 0
    extra_columns: list[str] = field(default_factory=list)
    issues: dict[str, int] = field(default_factory=dict)

    @property
    def rows_valid(self) -> int:
        return len(self.clean)

    @property
    def rows_quarantined(self) -> int:
        return len(self.quarantine)


def _blank_to_na(s: pd.Series) -> pd.Series:
    out = s.astype("object")
    out = out.where(~out.astype("string").str.strip().isin(["", "nan", "None", "NULL", "null"]), None)
    return out


def _coerce(s: pd.Series, col: Column) -> tuple[pd.Series, pd.Series]:
    """Return (coerced values, mask of values that were present but unparseable)."""
    s = _blank_to_na(s)
    present = s.notna()
    if col.dtype in ("int", "float"):
        num = pd.to_numeric(s, errors="coerce")
        bad = present & num.isna()
        if col.dtype == "int":
            bad = bad | (num.notna() & (num % 1 != 0))
            num = num.where(~bad).round().astype("Int64")
        return num, bad
    if col.dtype in ("datetime", "date"):
        ts = pd.to_datetime(s, errors="coerce", utc=True)
        bad = present & ts.isna()
        ts = ts.dt.tz_convert(None)
        if col.dtype == "date":
            ts = ts.dt.normalize()
            return ts.dt.date.where(ts.notna(), None).astype("object"), bad
        return ts, bad
    out = s.astype("string").str.strip()
    return out, pd.Series(False, index=s.index)


def validate(df: pd.DataFrame, contract: TableContract) -> ValidationResult:
    expected = contract.column_names
    missing = [c for c in expected if c not in df.columns]
    if missing:
        raise SchemaError(f"{contract.name}: missing required columns {missing}")
    extra = [c for c in df.columns if c not in expected]

    rows_in = len(df)
    work = pd.DataFrame(index=df.index)
    reasons = pd.Series("", index=df.index, dtype="object")
    issues: dict[str, int] = {}

    def flag(mask: pd.Series, label: str) -> None:
        mask = mask.fillna(False)
        n = int(mask.sum())
        if n:
            issues[label] = issues.get(label, 0) + n
            reasons.loc[mask] = reasons.loc[mask] + label + ";"

    for col in contract.columns:
        values, bad_type = _coerce(df[col.name], col)
        flag(bad_type, f"{col.name}:invalid_type")
        if col.dtype == "string" and col.allowed:
            values = values.str.lower()
        if not col.nullable:
            flag(values.isna() & ~bad_type, f"{col.name}:null")
        if col.min is not None and col.dtype in ("int", "float"):
            flag(values.notna() & (values < col.min), f"{col.name}:below_min")
        if col.max is not None and col.dtype in ("int", "float"):
            flag(values.notna() & (values > col.max), f"{col.name}:above_max")
        if col.allowed:
            flag(values.notna() & ~values.isin(col.allowed), f"{col.name}:not_allowed")
        if col.regex:
            flag(values.notna() & ~values.astype("string").str.match(col.regex, na=False), f"{col.name}:bad_format")
        work[col.name] = values

    bad_rows = reasons != ""
    quarantine = df.loc[bad_rows].astype("string")
    quarantine["_reasons"] = reasons.loc[bad_rows].str.rstrip(";")
    clean = work.loc[~bad_rows].copy()

    before = len(clean)
    if contract.version_column:
        clean = clean.sort_values(contract.version_column, kind="stable")
    clean = clean.drop_duplicates(list(contract.primary_key), keep="last").reset_index(drop=True)
    return ValidationResult(
        clean=clean,
        quarantine=quarantine.reset_index(drop=True),
        rows_in=rows_in,
        duplicates_removed=before - len(clean),
        extra_columns=extra,
        issues=issues,
    )
