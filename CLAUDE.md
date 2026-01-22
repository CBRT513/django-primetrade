# PrimeTrade (django-primetrade)
**Domain:** prt.barge2rail.com
**Stack:** Django 5.x + DRF + PostgreSQL (Neon)
**Risk Level:** MEDIUM - BOL generation for operations
**Updated:** January 2026

## Project Map
```
django-primetrade/
├── manage.py
├── primetrade/settings.py   # SSO integration config
├── primetrade/urls.py
├── core/                    # Main app
│   ├── models.py            # BOL, Shipment, Customer
│   ├── views.py             # BOL generation endpoints
│   └── pdf.py               # PDF generation logic
├── templates/
└── requirements.txt
```

## Commands
```bash
cd /Users/cerion/Projects/django-primetrade
source venv/bin/activate

# Local development
python manage.py runserver 8000          # Default port

# Generate test BOL
python manage.py shell
>>> from core.models import BOL
>>> bol = BOL.objects.first()
>>> bol.generate_pdf()

# Deploy (Render auto-deploys on push)
git push origin main
```

## Integration Points
| System | Domain | Dependency |
|--------|--------|------------|
| SSO | sso.barge2rail.com | JWT validation for all auth |
| S3 | AWS | PDF storage |

## Guardrails
- **Don't** generate PDFs synchronously for large batches → **Do** use background tasks
- **Don't** store PDFs locally → **Do** use S3 with signed URLs
- **Don't** skip JWT validation → **Do** verify every request against SSO

## Environment Variables (Render)
```
BASE_URL=https://prt.barge2rail.com
SSO_URL=https://sso.barge2rail.com
SECRET_KEY=xxx
DEBUG=False
ALLOWED_HOSTS=prt.barge2rail.com
DATABASE_URL=[from Render]
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
AWS_S3_BUCKET=xxx
```

## Business Context
Replaces fragmented Google Sheets with unified BOL management:
- Pig iron shipment tracking
- Bill of Lading generation (PDF)
- Customer/supplier database

## Related Docs
- Parent patterns: `../CLAUDE.md`
- SSO integration: `../barge2rail-auth/CLAUDE.md`
