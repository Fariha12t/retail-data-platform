"""Central configuration, read from environment variables (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy.engine import URL


def _load_dotenv(path: Path = Path(".env")) -> None:
    """Tiny .env loader so the CLI works outside Docker without extra dependencies."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.split(" #")[0].strip()
        os.environ.setdefault(key.strip(), value)


@dataclass(frozen=True)
class Settings:
    pg_host: str
    pg_port: int
    pg_db: str
    pg_user: str
    pg_password: str
    storage_backend: str
    s3_bucket: str
    s3_endpoint_url: str | None
    s3_region: str
    local_lake_dir: Path
    landing_dir: Path
    reports_dir: Path
    api_base_url: str
    history_start: date
    slack_webhook_url: str | None
    alert_email_to: str | None
    smtp_host: str | None
    smtp_port: int
    smtp_user: str | None
    smtp_password: str | None
    freshness_max_age_hours: float
    monthly_budget_usd: float
    s3_price_per_gb_month: float
    db_price_per_gb_month: float
    compute_price_per_hour: float

    @property
    def db_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg2",
            username=self.pg_user,
            password=self.pg_password,
            host=self.pg_host,
            port=self.pg_port,
            database=self.pg_db,
        )


def get_settings() -> Settings:
    """Read settings fresh each call so tests can monkeypatch the environment."""
    _load_dotenv()
    e = os.environ.get
    return Settings(
        pg_host=e("PG_HOST", "localhost"),
        pg_port=int(e("PG_PORT", "5432")),
        pg_db=e("PG_DB", "warehouse"),
        pg_user=e("PG_USER", "warehouse"),
        pg_password=e("PG_PASSWORD", "warehouse"),
        storage_backend=e("STORAGE_BACKEND", "local").lower(),
        s3_bucket=e("S3_BUCKET", "retail-raw"),
        s3_endpoint_url=e("S3_ENDPOINT_URL") or None,
        s3_region=e("AWS_DEFAULT_REGION", "ap-south-1"),
        local_lake_dir=Path(e("LOCAL_LAKE_DIR", "data/lake")),
        landing_dir=Path(e("LANDING_DIR", "data/landing")),
        reports_dir=Path(e("REPORTS_DIR", "reports")),
        api_base_url=e("API_BASE_URL", "http://localhost:8000"),
        history_start=date.fromisoformat(e("SOURCE_HISTORY_START") or "2024-01-01"),
        slack_webhook_url=e("SLACK_WEBHOOK_URL") or None,
        alert_email_to=e("ALERT_EMAIL_TO") or None,
        smtp_host=e("SMTP_HOST") or None,
        smtp_port=int(e("SMTP_PORT", "587")),
        smtp_user=e("SMTP_USER") or None,
        smtp_password=e("SMTP_PASSWORD") or None,
        freshness_max_age_hours=float(e("FRESHNESS_MAX_AGE_HOURS", "26")),
        monthly_budget_usd=float(e("MONTHLY_BUDGET_USD", "25")),
        s3_price_per_gb_month=float(e("S3_PRICE_PER_GB_MONTH", "0.023")),
        db_price_per_gb_month=float(e("DB_PRICE_PER_GB_MONTH", "0.115")),
        compute_price_per_hour=float(e("COMPUTE_PRICE_PER_HOUR", "0.10")),
    )
