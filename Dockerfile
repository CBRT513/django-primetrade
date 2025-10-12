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

# Run migrations, collect static files, and start server (at runtime when env vars exist)
CMD python manage.py migrate && \
    python manage.py collectstatic --noinput && \
    gunicorn primetrade_project.wsgi:application --bind 0.0.0.0:$PORT
