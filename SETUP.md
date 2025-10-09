# Django PrimeTrade Setup Guide

## Prerequisites

- Python 3.9+ installed
- Access to https://sso.barge2rail.com admin panel
- Git installed

---

## Local Development Setup

### 1. Clone Repository (if needed)

```bash
git clone <repository-url>
cd django-primetrade
```

### 2. Get SSO Credentials

1. Go to https://sso.barge2rail.com/admin
2. Navigate to Applications
3. Find or create "PrimeTrade" application
4. Copy the `client_id` (starts with `app_`)
5. Copy the `client_secret`
6. Note the configured redirect URIs

### 3. Configure Environment Variables

```bash
# Copy the template
cp .env.example .env
```

Edit `.env` and replace placeholder values:

```bash
# Django Settings
SECRET_KEY=your-actual-django-secret-key-change-this
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# SSO Configuration
SSO_BASE_URL=https://sso.barge2rail.com
SSO_CLIENT_ID=app_1a2b3c4d5e6f7g8h  # ← Your actual client_id
SSO_CLIENT_SECRET=your_actual_secret_here  # ← Your actual client_secret
SSO_REDIRECT_URI=http://localhost:8001/auth/callback/
SSO_SCOPES=openid email profile
```

**IMPORTANT:**
- Never commit `.env` to git (it's in .gitignore)
- Generate a new SECRET_KEY for production
- Update redirect URI to match SSO admin configuration

### 4. Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate it
# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### 5. Install Dependencies

```bash
pip install -r requirements.txt
```

### 6. Run Migrations

```bash
python manage.py migrate
```

### 7. Create Superuser (optional)

```bash
python manage.py createsuperuser
```

### 8. Start Development Server

```bash
python manage.py runserver 8001
```

Application will be available at: http://localhost:8001

---

## Production Deployment

### 1. Update Production Environment

Create `.env` on production server with:

```bash
SECRET_KEY=production-secret-key-generate-new-one
DEBUG=False
ALLOWED_HOSTS=primetrade.barge2rail.com,www.primetrade.barge2rail.com

SSO_BASE_URL=https://sso.barge2rail.com
SSO_CLIENT_ID=app_production_client_id
SSO_CLIENT_SECRET=production_client_secret
SSO_REDIRECT_URI=https://primetrade.barge2rail.com/auth/callback/
SSO_SCOPES=openid email profile
```

**Make sure redirect URI is registered in SSO admin!**

### 2. Collect Static Files

```bash
python manage.py collectstatic --noinput
```

### 3. Run Migrations

```bash
python manage.py migrate
```

### 4. Start with Production Server

```bash
gunicorn primetrade_project.wsgi:application --bind 0.0.0.0:8001
```

---

## Security Best Practices

### ✅ DO:
- Keep `.env` in `.gitignore`
- Use different credentials for dev/production
- Generate strong SECRET_KEY for production
- Set DEBUG=False in production
- Use HTTPS in production
- Regularly rotate secrets

### ❌ DON'T:
- Never commit `.env` with real credentials
- Never use DEBUG=True in production
- Never share client secrets publicly
- Never use the same SECRET_KEY in multiple environments

---

## Project Structure

```
django-primetrade/
├── .env.example           # Template (commit this)
├── .env                   # Your credentials (NEVER commit)
├── .gitignore             # Includes .env
├── requirements.txt       # Python dependencies
├── manage.py              # Django management script
├── SETUP.md               # This file
├── primetrade_project/
│   ├── settings.py        # Django settings (loads from .env)
│   ├── urls.py
│   └── wsgi.py
└── bol_system/            # Main application
    ├── models.py
    ├── views.py
    └── ...
```

---

## Accessing SSO Configuration in Code

SSO settings are automatically loaded from `.env` into Django settings:

```python
from django.conf import settings

# Use in your code
sso_url = settings.SSO_BASE_URL
client_id = settings.SSO_CLIENT_ID
client_secret = settings.SSO_CLIENT_SECRET
redirect_uri = settings.SSO_REDIRECT_URI
scopes = settings.SSO_SCOPES
```

---

## Troubleshooting

### "SSO credentials not configured" warning

**Cause:** Missing SSO credentials in `.env`

**Fix:**
1. Verify `.env` file exists
2. Check `SSO_CLIENT_ID` and `SSO_CLIENT_SECRET` are set
3. Make sure there are no typos in variable names
4. Restart Django server after changing `.env`

### "Invalid redirect_uri" error from SSO

**Cause:** Redirect URI doesn't match SSO admin configuration

**Fix:**
1. Check `SSO_REDIRECT_URI` in `.env`
2. Go to SSO admin → Applications → PrimeTrade
3. Add the exact URI to "Redirect URIs" field
4. URIs must match exactly (including trailing slashes)

### "Invalid client credentials" error

**Cause:** Wrong client_id or client_secret

**Fix:**
1. Verify credentials in `.env` match SSO admin
2. Check for extra spaces or line breaks
3. Ensure application is marked "Active" in SSO admin
4. Try regenerating credentials in SSO admin

### Environment variables not loading

**Cause:** `.env` file not found or syntax error

**Fix:**
1. Ensure `.env` is in project root (same directory as `manage.py`)
2. Check for syntax errors (no spaces around `=`)
3. Restart Django development server
4. Check file is actually named `.env` not `.env.txt`

---

## Generating a New SECRET_KEY

```python
# Run in Python shell
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
```

Or use this one-liner:

```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

---

## Support

For issues:
1. Check Django logs in `logs/primetrade.log`
2. Enable DEBUG=True temporarily (development only)
3. Check SSO server logs in Django admin
4. Contact: clif@barge2rail.com

---

## Additional Resources

- Django Documentation: https://docs.djangoproject.com/
- SSO Server Admin: https://sso.barge2rail.com/admin
- OAuth 2.0 Specification: https://oauth.net/2/
- python-decouple Documentation: https://github.com/henriquebastos/python-decouple
