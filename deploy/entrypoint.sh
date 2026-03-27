#!/bin/sh
set -e
cd /app

if [ -z "$DJANGO_SECRET_KEY" ] && [ "${DEBUG:-false}" != "true" ] && [ "${DEBUG:-False}" != "True" ]; then
  echo "ERROR: DJANGO_SECRET_KEY must be set when DEBUG is not true."
  exit 1
fi

python manage.py migrate --noinput
python manage.py collectstatic --noinput --clear

exec gunicorn pdf_qa.wsgi:application \
  --bind 0.0.0.0:${PORT:-8000} \
  --workers ${GUNICORN_WORKERS:-2} \
  --threads ${GUNICORN_THREADS:-4} \
  --timeout ${GUNICORN_TIMEOUT:-120} \
  --access-logfile - \
  --error-logfile -
