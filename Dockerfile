# --- Build stage ---
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt


# --- Runtime stage ---
FROM python:3.11-slim AS runtime

LABEL maintainer="LegalDocTracker Team"
LABEL description="Contract Lifecycle Management API"

WORKDIR /app

# Runtime OS deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy project source
COPY . .

# Ensure static files directory exists
RUN mkdir -p /app/staticfiles /app/media

RUN chown -R appuser:appuser /app

USER appuser

ENV DJANGO_SETTINGS_MODULE=config.settings.local
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/admin/ || exit 1

CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--timeout", "90", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
