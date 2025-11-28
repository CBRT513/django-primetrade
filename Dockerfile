FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
# - postgresql-client: for database operations
# - WeasyPrint dependencies: libpango, libcairo, fonts for PDF generation
# - poppler-utils: for pdf2image (pdftoppm)
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz-subset0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    fonts-liberation \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create logs directory
RUN mkdir -p logs

# Expose port
EXPOSE 8000

# Create startup script that runs migrations, cache table, collectstatic, then starts server
RUN echo '#!/bin/bash\n\
set -e\n\
echo "=== Running migrations ==="\n\
python manage.py migrate --noinput || { echo "Migration failed!"; exit 1; }\n\
echo "=== Migrations complete ==="\n\
echo "=== Creating cache table ==="\n\
python manage.py createcachetable\n\
echo "=== Collecting static files ==="\n\
python manage.py collectstatic --noinput\n\
echo "=== Starting server ==="\n\
gunicorn primetrade_project.wsgi:application --bind 0.0.0.0:8000 --workers 2 --threads 4 --timeout 60\n\
' > /app/start.sh && chmod +x /app/start.sh

# Use startup script as entrypoint
CMD ["/app/start.sh"]
