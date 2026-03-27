#!/bin/sh
set -e

# Retry migrations (Postgres on Render can take a few seconds after first deploy)
set +e
attempt=0
max=15
until python manage.py migrate --noinput; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge "$max" ]; then
    echo "ERROR: migrate failed after $max attempts"
    exit 1
  fi
  echo "migrate: waiting for database (attempt $attempt/$max), retry in 2s..."
  sleep 2
done
set -e

# PORT is set by Render. WEB_CONCURRENCY: use 1 on 512MB plans if you see OOM kills.
exec gunicorn pdf_qa.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --timeout "${GUNICORN_TIMEOUT:-120}" \
  --graceful-timeout 30 \
  --max-requests "${GUNICORN_MAX_REQUESTS:-500}" \
  --max-requests-jitter "${GUNICORN_MAX_REQUESTS_JITTER:-50}" \
  --access-logfile - \
  --error-logfile -
