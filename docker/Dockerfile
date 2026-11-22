FROM python:3.12-slim

# A release image should default to production even when the runtime forgets
# to provide DJANGO_SETTINGS_MODULE. docker-compose.yml explicitly overrides
# this for local development only.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/ /app/requirements/
RUN pip install --no-cache-dir -r requirements/base.txt gunicorn

# .dockerignore prevents local credentials, databases and media entering the
# image; the application serves its static assets from the collected directory.
COPY . /app/
RUN DJANGO_SETTINGS_MODULE=config.settings.local python manage.py collectstatic --noinput \
    && groupadd --system --gid 10001 beautyos \
    && useradd --system --uid 10001 --gid beautyos --home-dir /app --shell /usr/sbin/nologin beautyos \
    && mkdir -p /app/media \
    && chown -R beautyos:beautyos /app/media /app/staticfiles

USER beautyos
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
