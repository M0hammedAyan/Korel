FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY main.py .
COPY db.py .

# Health check
HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD python -c "import httpx; httpx.get('http://localhost:8008/health', timeout=5)" || exit 1

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8008", "--workers", "2"]
