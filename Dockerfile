# Python base image
FROM python:3.12-slim

# Prevents Python from writing .pyc files and buffers
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Workdir
WORKDIR /app

# System deps (optional: libpq for psycopg2-binary is bundled, so minimal)
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install requirements
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Expose the port (informational)
EXPOSE 8000

# Environment defaults
ENV PORT=8000 \
    HOST=0.0.0.0 \
    FLASK_DEBUG=0

# Start with gunicorn
CMD ["gunicorn", "app:app", "--workers", "2", "--threads", "2", "--timeout", "120", "--bind", "0.0.0.0:8000"]
