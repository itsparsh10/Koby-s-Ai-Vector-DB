# Production image: Django + Gunicorn + WhiteNoise (ML stack is heavy — use ≥2GB RAM on your host)
FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=pdf_qa.settings

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x docker-entrypoint.sh

# Bake static files for WhiteNoise (secret only needed for collectstatic import chain)
ENV DJANGO_SECRET_KEY=collectstatic-build-placeholder DEBUG=False
RUN python manage.py collectstatic --noinput
ENV DJANGO_SECRET_KEY=

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
