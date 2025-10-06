#!/bin/bash
# Phase 1 Setup Script for Django PrimeTrade

set -e  # Exit on error

echo "========================================="
echo "Django PrimeTrade - Phase 1 Setup"
echo "========================================="
echo ""

# Check if we're in the right directory
if [ ! -f "manage.py" ]; then
    echo "Error: Please run this script from the django-primetrade directory"
    exit 1
fi

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Error: Please activate your virtual environment first:"
    echo "  source venv/bin/activate"
    exit 1
fi

echo "Step 1: Generating SECRET_KEY..."
SECRET_KEY=$(python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
echo "Generated SECRET_KEY: $SECRET_KEY"
echo ""

echo "Step 2: Creating .env file..."
if [ -f ".env" ]; then
    echo "Warning: .env file already exists. Backing up to .env.backup"
    cp .env .env.backup
fi

cat > .env << EOF
DEBUG=True
SECRET_KEY=$SECRET_KEY
ALLOWED_HOSTS=localhost,127.0.0.1
EOF

echo ".env file created successfully"
echo ""

echo "Step 3: Running migrations..."
python manage.py makemigrations
python manage.py migrate
echo ""

echo "Step 4: Creating logs directory..."
mkdir -p logs
echo "logs/ directory created"
echo ""

echo "========================================="
echo "Setup Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Create a superuser:"
echo "   python manage.py createsuperuser"
echo ""
echo "2. Start the development server:"
echo "   python manage.py runserver"
echo ""
echo "3. Visit http://localhost:8000/login/"
echo ""
echo "See PHASE1_COMPLETE.md for full documentation."
echo ""
