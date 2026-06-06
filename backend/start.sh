#!/bin/sh
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Seeding form templates..."
python -m app.form_templates.seed

echo "Starting server on port ${PORT:-8000}..."
# Use `python -m uvicorn` so the server always runs on the same interpreter as
# `python` above (avoids a PATH `uvicorn` resolving to a different Python that
# may lack `anthropic`).
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
