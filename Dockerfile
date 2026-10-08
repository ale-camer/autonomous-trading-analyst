# Multi-stage production container for Autonomous Trading Analyst
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies required for compilation, psycopg, and container healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root application user matching AIRFLOW_UID (50000)
RUN groupadd -g 50000 trader && \
    useradd -u 50000 -g trader -m -s /bin/bash trader

WORKDIR /app
RUN chown -R trader:trader /app

# Copy dependency definition and source code
COPY --chown=trader:trader pyproject.toml README.md ./
COPY --chown=trader:trader src/ ./src/
COPY --chown=trader:trader dags/ ./dags/

# Install application package with all optional extras
RUN pip install --no-cache-dir .[all]

# Switch to non-root execution context
USER trader

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=5 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["uvicorn", "autonomous_trading_analyst.api:app", "--host", "0.0.0.0", "--port", "8080"]
