FROM postgres:15-bookworm AS postgres15_tools

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Install system dependencies (e.g., for psycopg2 build if needed in future)
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev postgresql-client curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Backup archives must be produced and consumed by the same PostgreSQL major
# as the server. /usr/local/bin precedes Debian's generic client on PATH.
COPY --from=postgres15_tools /usr/lib/postgresql/15/bin/pg_dump /usr/local/bin/pg_dump
COPY --from=postgres15_tools /usr/lib/postgresql/15/bin/pg_restore /usr/local/bin/pg_restore

# We use volume mount for code in docker-compose for dev, but copy it here for completeness
COPY . .

# Wait for entrypoint commands via docker-compose
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
