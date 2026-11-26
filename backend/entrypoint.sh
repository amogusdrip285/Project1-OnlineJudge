#!/bin/sh
# Apply DB migrations, then start the API. The judge waits for this container to be healthy.
set -e
alembic upgrade head
if [ "${SEED_ON_START:-false}" = "true" ]; then
  python -m scripts.seed
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
