FROM python:3.12-slim

LABEL maintainer="Web Builders <https://20057amo.github.io/webbuilders/>"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production

WORKDIR /app

# Create a non-root user and group
RUN groupadd -r appuser && useradd -r -g appuser appuser

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create downloads folder and change ownership to the non-root user
RUN mkdir -p downloads && chown -R appuser:appuser /app

# Switch to the non-root user
USER appuser

EXPOSE 5000

# Fix: bind to 0.0.0.0 and use 1 worker with multiple threads to share memory state for progress tracking
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "8", "app:app"]
