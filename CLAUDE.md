# PrimeTrade - Project Context
**Project:** django-primetrade
**Domain:** prt.barge2rail.com
**Stack:** Django + Django REST Framework + PostgreSQL
**Deployment:** Render PaaS
**Last Updated:** November 2025

**Shared Django patterns:** `../CLAUDE.md`
**Universal patterns:** `../../CLAUDE.md`

---

## Business Context

### What This Is
Primary logistics application for barge2rail.com operations. Replaces 15+ fragmented Google Sheets with unified web application.

### Primary Users
- Office staff (data entry, reporting)
- Field technicians (mobile access for real-time updates)
- Management (analytics, oversight)

### Purpose
Consolidate all logistics operations into single system:
- Customer/supplier database
- Barge tracking
- Repair tracking
- Employee management
- Bill of Lading (BOL) generation
- Analytics and reporting

---

## Integration Points

### System 1: SSO (barge2rail-auth)
**Purpose:** Authentication for all users
**Integration Method:** OAuth token validation, shared user identity
**Critical Dependency:** Depends on SSO for authentication
**Domain:** sso.barge2rail.com

### System 2: Google Workspace
**Purpose:** Identity provider (via SSO), potential future integrations
**Integration Method:** Via SSO OAuth flow
**Future:** May integrate Google Calendar, Sheets, Drive

---

## Deployment Details

### Domain & Hosting
- **Production:** prt.barge2rail.com
- **Platform:** Render PaaS
- **Database:** PostgreSQL (managed by Render)
- **SSL:** Auto-SSL via Render

### Environment Variables
Set in Render dashboard:
```
BASE_URL=https://prt.barge2rail.com
SSO_URL=https://sso.barge2rail.com
SECRET_KEY=[Django secret]
DEBUG=False
ALLOWED_HOSTS=prt.barge2rail.com
DATABASE_URL=[provided by Render]
```

---

## Development Status

**Current State:** Active development
**Priority:** HIGH - This system unblocks operational efficiency

### Key Features (Planned/In Progress)
- User authentication via SSO
- Customer/supplier database
- Barge tracking and status
- Repair request management
- BOL generation and PDF export
- Analytics dashboard
- Mobile-responsive interface

---

## Working With This System

### Project Repository
Location: `/Users/cerion/Projects/django-primetrade`

### Related Documentation
- **Shared Django patterns:** `../CLAUDE.md`
- **Universal patterns:** `../../CLAUDE.md`
- **SSO integration:** `../sso/CLAUDE.md`

### When to Update This File
- Architecture decisions finalized
- Integration points added/changed
- Deployment configuration changes
- Lessons learned from development/production

---

**Note:** This file will be expanded as the project develops. Document business logic quirks, lessons learned, and project-specific patterns here.
