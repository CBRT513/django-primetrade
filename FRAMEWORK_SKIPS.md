# FRAMEWORK_SKIPS

## Deviation: MEDIUM RISK parallel operation shortened to 5–6 day soft launch
- Project: django-primetrade
- Date: 2025-10-29
- Convention Reference: BARGE2RAIL_CODING_CONVENTIONS_v1.2.md (Deployment Standards → Environment Tiers / Deployment Checklist)
- Reason: First-time production launch; no existing working system to run in parallel. Technical change is frontend-only (session auth), SSO backend unchanged.
- Risk Mitigations:
  - Three-Perspective Review before deploy
  - Coverage ≥ 70%
  - Intensive daily verification Days 1–5
  - Defined rollback triggers and emergency login SOP
- Approval: Clif (Business Owner)
