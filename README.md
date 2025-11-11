# PrimeTrade - BOL Management System

Logistics application for barge2rail.com - streamlines Bill of Lading (BOL) management, customer tracking, and operational workflows.

**Status:** ✅ Production (deployed on Render)
**Authentication:** SSO integration with Google Workspace OAuth
**Framework:** Django 5.2.8 + Django REST Framework

---

## Features

- **BOL Management:** Create, track, and generate professional BOL PDFs
- **Customer Portal:** Client-specific product access
- **PDF Watermarking:** Official weight stamping for certified BOLs
- **Release Tracking:** Manage customer releases and load assignments
- **Role-Based Access:** Office, Admin, and Client roles with granular permissions
- **SSO Authentication:** Seamless Google Workspace integration
- **Mobile-Friendly:** Responsive design for field technicians

---

## Architecture

**Stack:**
- Django 5.2.8
- Django REST Framework 3.16.1
- PostgreSQL (production) / SQLite (development)
- WhiteNoise for static files
- AWS S3 for PDF storage (production)

**Authentication:**
- SSO OAuth v2 with JWT signature verification
- Session-based auth for long-duration workflows
- Role-based middleware for page access control

**Deployment:**
- Platform: Render PaaS
- Domain: primetrade.barge2rail.com
- Auto-deploy: GitHub `main` branch
- SSL: Automatic via Render

---

## Quick Start

### Prerequisites

- Python 3.13+
- Virtual environment
- PostgreSQL (production) or SQLite (development)
- SSO credentials (from sso.barge2rail.com)

### Local Development

```bash
# Clone repository
git clone https://github.com/CBRT513/django-primetrade.git
cd django-primetrade

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env and add your SSO credentials

# Run migrations
python manage.py migrate

# Create cache table for OAuth state
python manage.py createcachetable

# Collect static files
python manage.py collectstatic --noinput

# Run development server
python manage.py runserver 127.0.0.1:8001
```

Visit: `http://127.0.0.1:8001/`

### Environment Variables

Required in `.env`:

```bash
SECRET_KEY=your-django-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

SSO_BASE_URL=https://sso.barge2rail.com
SSO_CLIENT_ID=app_your_client_id
SSO_CLIENT_SECRET=your_client_secret
SSO_REDIRECT_URI=http://localhost:8001/auth/callback/
```

See `.env.example` for complete configuration options.

---

## Testing Status

**Current test coverage:** 40%

**What's tested:**
- ✅ JWT signature verification (100%)
- ✅ PDF watermarking (91%)
- ✅ Data models (85%)

**Known gaps:**
- ⚠️ OAuth flow (36% coverage)
- ⚠️ API endpoints (12% coverage)

See [TESTING.md](TESTING.md) for detailed coverage report and [TEST_IMPROVEMENT_PLAN.md](TEST_IMPROVEMENT_PLAN.md) for planned improvements.

⚠️ **Note:** JWT verification is fully tested (100%), but OAuth flow has known gaps. See testing documentation before making authentication changes.

### Running Tests

```bash
# Run all tests
python manage.py test

# Run with coverage
coverage run --source='.' manage.py test
coverage report --skip-empty
coverage html  # View htmlcov/index.html

# Run specific tests
python manage.py test primetrade_project.test_jwt_verification
python manage.py test bol_system.test_pdf_watermark
```

---

## Project Structure

```
django-primetrade/
├── bol_system/             # BOL management app
│   ├── models.py          # BOL, Customer, Product, Carrier models
│   ├── views.py           # REST API endpoints
│   ├── serializers.py     # DRF serializers
│   ├── pdf_generator.py   # PDF creation logic
│   ├── pdf_watermark.py   # Official weight stamping
│   └── test_*.py          # Test files
├── primetrade_project/     # Project configuration
│   ├── settings.py        # Django settings
│   ├── urls.py            # URL routing
│   ├── auth_views.py      # SSO OAuth implementation
│   ├── middleware.py      # RBAC middleware
│   └── test_*.py          # Test files
├── templates/              # HTML templates
├── static/                 # Static assets (CSS, JS, images)
├── staticfiles/            # Collected static files (production)
├── .env.example            # Environment variable template
├── requirements.txt        # Python dependencies
├── TESTING.md              # Test coverage documentation
└── TEST_IMPROVEMENT_PLAN.md # Test improvement roadmap
```

---

## Deployment

**Platform:** Render PaaS
**URL:** https://primetrade.barge2rail.com

### Deploy Process

1. Push to `main` branch → Auto-deploy triggered
2. Render runs migrations: `python manage.py migrate`
3. Render collects static files: `python manage.py collectstatic --noinput`
4. Health check: Verify app is running

### Environment Variables (Render)

Set in Render Dashboard → Environment tab:

- `SECRET_KEY` - Django secret key (generate new for production)
- `DEBUG` - Set to `False`
- `ALLOWED_HOSTS` - `primetrade.barge2rail.com`
- `DATABASE_URL` - PostgreSQL connection string (auto-set by Render)
- `SSO_BASE_URL` - `https://sso.barge2rail.com`
- `SSO_CLIENT_ID` - From SSO admin panel
- `SSO_CLIENT_SECRET` - From SSO admin panel
- `SSO_REDIRECT_URI` - `https://primetrade.barge2rail.com/auth/callback/`
- `USE_S3` - `True` (enable S3 for PDF storage)
- `AWS_ACCESS_KEY_ID` - AWS credentials
- `AWS_SECRET_ACCESS_KEY` - AWS credentials
- `AWS_STORAGE_BUCKET_NAME` - `primetrade-documents`

### Monitoring

- **Logs:** Render Dashboard → Logs tab
- **Metrics:** Render Dashboard → Metrics tab
- **Health Check:** `https://primetrade.barge2rail.com/api/health/`

---

## Security

### Authentication

- **Primary:** SSO OAuth with Google Workspace
- **JWT Verification:** RSA signature with JWKS endpoint
- **Session Management:** Secure cookies, HTTPS only
- **CSRF Protection:** Enabled for all POST requests

### Authorization

- **Roles:** Office, Admin, Client
- **Middleware:** `RoleBasedAccessMiddleware` enforces page-level access
- **Decorators:** `@require_primetrade_role` for view-level permissions

### Security Headers

- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `Secure-Browser-XSS-Filter: 1`
- HTTPS enforced in production
- Secure cookies (`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`)

---

## Documentation

- **TESTING.md** - Test coverage status and gaps
- **TEST_IMPROVEMENT_PLAN.md** - Test improvement roadmap
- **SSO_DIRECT_LOGIN.md** - OAuth flow documentation
- **ARCHITECTURE_OVERVIEW.md** - System architecture
- **DEPLOYMENT_CHECKLIST_MEDIUM.md** - Deployment procedures
- **CLAUDE.md** - Development guidelines and patterns

---

## Contributing

### Development Guidelines

1. Follow PEP 8 for Python code
2. Add tests for new features (target: 70%+ coverage)
3. Update documentation for significant changes
4. Test locally before pushing
5. Create feature branches for new work

### Git Workflow

```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Make changes and commit
git add .
git commit -m "feat: your feature description"

# Push to remote
git push origin feature/your-feature-name

# Create pull request for review
```

### Before Deploying

- [ ] Tests passing: `python manage.py test`
- [ ] Coverage check: `coverage report`
- [ ] Local testing: Run dev server and test manually
- [ ] Documentation updated
- [ ] Environment variables configured

---

## Support

**Technical Lead:** Clif (clif@barge2rail.com)
**Issues:** GitHub Issues
**Documentation:** See `/docs` folder

---

## License

Proprietary - Cincinnati Barge & Rail Terminal, LLC

---

## Changelog

### November 9, 2025
- 🗑️ Removed emergency login endpoint (unused, security gap)
- 🚀 Added feature flag control for debug authentication logging
- 📊 Documented test coverage (40%) and improvement plan

### November 7, 2025
- ✅ Deployed JWT signature verification (RSA + JWKS)
- 🔒 Enhanced security: Token tampering now blocked

### October 12, 2025
- ✅ Initial SSO integration with Google Workspace OAuth
- ✅ Direct SSO login (removed choice screen)
- ✅ RBAC middleware for role-based page access

---

**Built with ❤️ for barge2rail.com logistics operations**
