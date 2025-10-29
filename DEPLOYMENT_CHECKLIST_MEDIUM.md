# DEPLOYMENT_CHECKLIST_MEDIUM

Project: django-primetrade  
Date: __________  
Deployment Window: __________  
Approval: Clif (Business Owner)

## Pre-Deploy (Must be checked before Day 0)
- [ ] Protocol selected: Modified MEDIUM (5–6 day soft launch) documented in FRAMEWORK_SKIPS.md
- [ ] Three-Perspective Review complete (attach notes)
  - [ ] Security: SSO unchanged, CSRF on POSTs, HTTPS, secure cookies, no secrets in code, auth on all endpoints, emergency login SOP
  - [ ] Data Safety: No migrations; verified read/write paths; rollback plan confirmed
  - [ ] Business Logic: Role gating with application_roles['primetrade']; critical workflows validated
- [ ] Test coverage ≥ 70% (attach report)
- [ ] Health check endpoint verified (/api/health/)
- [ ] ENV configured for production (Render dashboard): SECRET_KEY, DEBUG=False, ALLOWED_HOSTS, DATABASE_URL, SSO_*
- [ ] SSO redirect URI registered (production URL)
- [ ] CSRF_TRUSTED_ORIGINS updated for production domains
- [ ] Static files collected in build (collectstatic)
- [ ] Staff training conducted (emergency login SOP, reporting process)

## Day 0 (Deploy)
- [ ] Deploy to Render completed
- [ ] Health check passing
- [ ] Smoke test: login via SSO → dashboard → products/customers/carriers → create BOL → logout
- [ ] Monitoring enabled (logs reviewed)

## Days 1–5 (Soft Launch)
- [ ] Internal Test Cohort defined (names/roles)
- [ ] Daily verification logged (login, CSRF POSTs, role gating, PDFs, error logs)
- [ ] Issues triaged and fixed within 24h
- [ ] Rollback triggers defined and monitored

## Day 5 (Go/No-Go)
- [ ] Review of soft-launch results
- [ ] Security/Data/Business sign-off
- [ ] Decision: Full rollout approved / deferred

## Post-Deploy
- [ ] Week 1 monitoring complete
- [ ] Documentation updated (README, SOP)
- [ ] Lessons learned captured
