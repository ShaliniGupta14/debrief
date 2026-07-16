#!/bin/sh
set -e

# Railway's CLI has no way to override a service's start command (that's a
# dashboard-only setting) -- SERVICE_ROLE lets one image/Dockerfile serve
# both the api and worker services, selected by an env var each service sets
# via `railway variable set`, rather than needing manual dashboard config.
if [ "$SERVICE_ROLE" = "worker" ]; then
  exec arq app.workers.worker.WorkerSettings
else
  alembic upgrade head
  exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
fi
