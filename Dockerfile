FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Collect static files at build time (admin CSS etc.); the values below are only
# placeholders so Django can start. Real values come from the .env file at runtime.
RUN SECRET_KEY=build-only DATABASE_URL=postgres://u:p@localhost:5432/d ALLOWED_HOSTS=localhost \
    python manage.py collectstatic --noinput

RUN useradd --create-home --uid 1000 app \
    && mkdir -p /app/media \
    && chown -R app:app /app/media
USER app

EXPOSE 8000

# Apply migrations, then start Gunicorn.
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers ${GUNICORN_WORKERS:-2} --timeout 60 --access-logfile -"]
