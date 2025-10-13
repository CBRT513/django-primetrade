FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create ALL necessary directories
RUN mkdir -p /app/logs /app/staticfiles /app/media

# Set proper permissions
RUN chmod -R 755 /app/logs /app/staticfiles /app/media

# Run everything at runtime when env vars exist
CMD python manage.py migrate && \
    python manage.py createcachetable && \
    python manage.py collectstatic --noinput && \
    gunicorn primetrade_project.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --timeout 120
