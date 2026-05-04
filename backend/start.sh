#!/bin/sh
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Seeding form templates..."
python -m app.form_templates.seed

echo "Starting server on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
