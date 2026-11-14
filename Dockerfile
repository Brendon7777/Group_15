# LTSM Portal – container image.  Build:  docker build -t ltsm-portal .
# Run:  docker run -p 8000:8000 -e SECRET_KEY=<long random value> ltsm-portal
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    PORT=8000

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT', '8000'))"

# ONE worker on purpose: the sample data lives in each worker's memory, so several workers would show different data.
# Raise --workers only after the data moves to the database.
CMD ["sh", "-c", "gunicorn --workers 1 --threads 4 --bind 0.0.0.0:${PORT} app:app"]
