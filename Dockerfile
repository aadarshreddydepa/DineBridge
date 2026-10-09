FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 app

COPY --chown=app:app manage.py /app/manage.py
COPY --chown=app:app api /app/api
COPY --chown=app:app dinebridge /app/dinebridge
COPY --chown=app:app db/migrations /app/db/migrations
COPY --chown=app:app db/migrate.py /app/db/migrate.py

USER app
EXPOSE 8000
CMD ["sh", "-c", "exec gunicorn dinebridge.asgi:application -k uvicorn_worker.UvicornWorker --workers 1 --bind 0.0.0.0:${PORT:-8000}"]
