# Image for running the CLI, dbt and the dashboard (docker compose run --rm pipeline ...)
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app/src DBT_PROFILES_DIR=/app/dbt
COPY requirements-dashboard.txt requirements.txt ./
RUN pip install --no-cache-dir -r requirements-dashboard.txt
COPY . .
CMD ["python", "-m", "retail_pipeline.cli", "--help"]
