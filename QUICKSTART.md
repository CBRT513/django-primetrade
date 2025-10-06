# Quick Start Guide - Phase 1

## Automated Setup (Recommended)

```bash
cd /Users/cerion/Projects/django-primetrade
source venv/bin/activate
./setup_phase1.sh
```

This will automatically:
- Generate SECRET_KEY
- Create .env file
- Run migrations
- Create logs directory

## Manual Setup (Alternative)

### 1. Generate SECRET_KEY

```bash
cd /Users/cerion/Projects/django-primetrade
source venv/bin/activate
python manage.py shell
```

In the shell:
```python
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
exit()
```

### 2. Create .env File

Create `.env` with:
```
DEBUG=True
SECRET_KEY=<your-generated-key>
ALLOWED_HOSTS=localhost,127.0.0.1
```

### 3. Run Migrations

```bash
python manage.py migrate
```

### 4. Create Superuser

```bash
python manage.py createsuperuser
```

Suggested:
- Username: `admin`
- Email: `clif@barge2rail.com`
- Password: (your choice)

### 5. Start Server

```bash
python manage.py runserver
```

## Access Points

- **Login**: http://localhost:8000/login/
- **Admin**: http://localhost:8000/admin/
- **Office Portal**: http://localhost:8000/office.html (requires login)
- **Client Portal**: http://localhost:8000/client.html (requires login)

## Quick Verification

1. Try to access http://localhost:8000/api/products/ without login → Should redirect to login
2. Login at http://localhost:8000/login/
3. After login, http://localhost:8000/api/products/ should work
4. Create a BOL and check `logs/primetrade.log` for the log entry

## Troubleshooting

### "SECRET_KEY not found" error
- Make sure you created `.env` file in project root
- Make sure it contains `SECRET_KEY=...` line

### Can't login
- Make sure you created a superuser: `python manage.py createsuperuser`
- Check username and password

### Static files not loading
- Run: `python manage.py collectstatic` (if DEBUG=False)
- Make sure DEBUG=True for development

### API returns 403 Forbidden
- Make sure you're logged in
- Check that session cookies are enabled in your browser

## Full Documentation

See `PHASE1_COMPLETE.md` for complete documentation, testing checklist, and deployment notes.
