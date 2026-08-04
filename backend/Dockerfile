# Multi-stage Dockerfile for KORAL Backend
# Production-grade with security hardening

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY backend/requirements.txt .

# Create virtualenv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

# Security: Add non-root user
RUN groupadd -r koral && useradd -r -g koral koral

# Set working directory
WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code as a package
COPY backend/ ./backend/
COPY shared/ ./shared/
COPY feedback/ ./feedback/
COPY threshold/ ./threshold/
COPY alembic/ ./alembic/
COPY alembic.ini ./alembic.ini
COPY database/ ./database/

# Create temporary directories with proper permissions
RUN mkdir -p /tmp/app && chown -R koral:koral /tmp/app

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Security: Set permissions
RUN chmod -R 555 /app && chmod -R 755 /tmp/app && chmod 555 /app/feedback /app/threshold

# Health check
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import sys,urllib.request; u=urllib.request.urlopen('http://localhost:8000/health', timeout=5); sys.exit(0 if u.getcode()==200 else 1)"

# Switch to non-root user
USER koral

# Expose port
EXPOSE 8000

# Run migrations, then start the application
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4"]
