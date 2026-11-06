FROM python:3.12-slim

LABEL maintainer="Web Builders <https://20057amo.github.io/webbuilders/>"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production

WORKDIR /app

# Create a non-root user and group. gunicorn >= 26 keeps its control socket in
# $HOME, so the account needs a writable home directory even though the app
# itself only writes to /app/downloads.
RUN groupadd -r appuser && \
    useradd -r -g appuser -d /home/appuser appuser && \
    mkdir -p /home/appuser && \
    chown appuser:appuser /home/appuser

# ffmpeg is required to merge video/audio streams; curl backs the healthcheck;
# gosu lets the root entrypoint drop privileges without a shell wrapper.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        gosu \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

COPY . .

# Create downloads folder and change ownership to the non-root user
RUN mkdir -p downloads && chown -R appuser:appuser /app

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT:-5000}/api/health" || exit 1

# The entrypoint starts as root, fixes bind-mount permissions, then execs gosu.
# A single gthread worker keeps the in-memory task registry shared while SSE
# progress streams get their own threads instead of starving the sync worker.
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 1 --worker-class gthread --threads 16 --timeout 120 --access-logfile - --error-logfile - app:app"]
