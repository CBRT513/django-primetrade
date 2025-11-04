# AWS S3 Deployment Checklist

Use this checklist to ensure successful deployment of S3 storage for PrimeTrade BOL PDFs.

---

## Pre-Deployment Checklist

### AWS Account Setup
- [ ] AWS account created
- [ ] Billing alerts configured ($1/month threshold)
- [ ] Payment method added

### S3 Bucket Configuration
- [ ] Bucket created: `primetrade-documents`
- [ ] Region: `us-east-2` (Ohio)
- [ ] Block public access: **ENABLED** (all boxes checked)
- [ ] Versioning: **ENABLED**
- [ ] Encryption: **ENABLED** (SSE-S3)
- [ ] Bucket created successfully

### IAM User Setup
- [ ] IAM user created: `primetrade-django`
- [ ] Custom policy created: `PrimetradeDjangoS3Access`
- [ ] Policy attached to user
- [ ] Access Key ID saved securely
- [ ] Secret Access Key saved securely
- [ ] Credentials tested (can list bucket)

### Code Changes
- [ ] `requirements.txt` updated with `django-storages` and `boto3`
- [ ] `settings.py` updated with S3 configuration
- [ ] `pdf_generator.py` updated to use Django storage backend
- [ ] Migration script created: `migrate_pdfs_to_s3.py`
- [ ] Download endpoint added: `/api/bol/<id>/download/`
- [ ] URL route registered in `urls.py`
- [ ] `.env.example` updated with S3 variables
- [ ] `render.yaml` updated with S3 environment variables
- [ ] All changes committed to git

---

## Local Testing Checklist

### Environment Configuration
- [ ] `.env` file updated with AWS credentials
- [ ] `USE_S3=True` set for testing
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] Django can import `storages.backends.s3boto3`

### Test PDF Upload
- [ ] Local development server started
- [ ] Created test BOL
- [ ] PDF uploaded to S3 successfully
- [ ] File visible in AWS Console under `bols/YYYY/`
- [ ] BOL record in database has S3 URL

### Test PDF Download
- [ ] Can retrieve BOL via `/api/bol/<id>/`
- [ ] `pdfUrl` contains signed S3 URL
- [ ] Signed URL works (downloads PDF)
- [ ] URL contains query parameters (signature)
- [ ] Download endpoint works: `/api/bol/<id>/download/`

### Test Migration Script
- [ ] Dry run completed: `python manage.py migrate_pdfs_to_s3 --dry-run`
- [ ] Review output - all files found
- [ ] Actual migration run successfully
- [ ] All PDFs uploaded to S3
- [ ] Database `pdf_url` fields updated
- [ ] Can download all migrated BOLs

### Test Audit Logging
- [ ] Downloaded BOL via API
- [ ] Audit log created with action `BOL_DOWNLOADED`
- [ ] Log contains user email
- [ ] Log contains BOL number

### Revert Local Environment
- [ ] Set `USE_S3=False` in `.env` for local development
- [ ] Local development still works with filesystem storage

---

## Production Deployment Checklist

### Pre-Deployment
- [ ] All code changes committed and pushed to git
- [ ] Git branch merged to main (if using feature branch)
- [ ] Reviewed all changes in git diff
- [ ] No AWS credentials committed to git (verify with `git log -p | grep "AWS_SECRET"`)

### Render Configuration
- [ ] Logged into Render dashboard
- [ ] Navigated to `primetrade` service
- [ ] Environment variables added:
  - [ ] `USE_S3=True`
  - [ ] `AWS_ACCESS_KEY_ID=...`
  - [ ] `AWS_SECRET_ACCESS_KEY=...`
  - [ ] `AWS_STORAGE_BUCKET_NAME=primetrade-documents`
  - [ ] `AWS_S3_REGION_NAME=us-east-2`
- [ ] Saved environment variables

### Deployment
- [ ] Triggered deployment (automatic on push or manual)
- [ ] Deployment completed successfully
- [ ] Health check passing: `/api/health/`
- [ ] No errors in deployment logs

### Post-Deployment Verification
- [ ] Production site accessible: `https://django-primetrade.onrender.com`
- [ ] Can log in successfully
- [ ] Dashboard loads
- [ ] Product list loads

### Test Production S3
- [ ] Created new BOL in production
- [ ] PDF uploaded to S3 (check AWS Console)
- [ ] Can view BOL details
- [ ] PDF URL is S3 signed URL
- [ ] Can download PDF successfully
- [ ] PDF content is correct

### Migration (if needed)
- [ ] Identified existing PDFs on Render (if any)
- [ ] Ran migration script in production
- [ ] Verified all PDFs migrated
- [ ] Tested downloading old BOLs
- [ ] All old BOL PDFs accessible

### Security Verification
- [ ] S3 bucket is private (public access blocked)
- [ ] Trying to access PDF without signature returns 403
- [ ] Signed URLs expire after 24 hours
- [ ] Audit logs working in production
- [ ] No credentials exposed in logs or error messages

---

## Rollback Plan

If something goes wrong, follow these steps:

### Immediate Rollback
1. [ ] Set `USE_S3=False` in Render environment variables
2. [ ] Trigger redeployment
3. [ ] Verify site still works (with local/old PDFs)

### Investigate Issues
1. [ ] Check Render logs for errors
2. [ ] Check AWS CloudTrail for S3 access errors
3. [ ] Verify IAM permissions
4. [ ] Test S3 connection from local environment

### Fix and Re-deploy
1. [ ] Fix identified issues
2. [ ] Test locally
3. [ ] Commit fixes
4. [ ] Set `USE_S3=True` again
5. [ ] Redeploy

---

## Post-Deployment Tasks

### Immediate (Day 1)
- [ ] Monitor Render logs for errors
- [ ] Create 3-5 test BOLs and verify all work
- [ ] Check S3 bucket - all files present
- [ ] Verify customers can download BOLs (if applicable)
- [ ] Document any issues encountered

### Short-term (Week 1)
- [ ] Monitor AWS costs (should be ~$0)
- [ ] Check S3 storage size
- [ ] Review audit logs
- [ ] Train staff on new system (if needed)
- [ ] Update documentation with any findings

### Medium-term (Month 1)
- [ ] Review AWS billing (should be < $1)
- [ ] Archive old local PDFs (optional)
- [ ] Consider setting up lifecycle policies
- [ ] Review and optimize if needed

---

## Success Criteria

All of these should be true:

✅ S3 bucket configured securely (private, encrypted, versioned)
✅ IAM user has minimal required permissions
✅ New BOLs upload to S3 automatically
✅ All existing BOLs migrated to S3
✅ Staff can create and download BOLs
✅ Customers can download BOLs via signed URLs (if implemented)
✅ Audit logging works
✅ No credentials exposed
✅ No errors in production logs
✅ AWS costs < $1/month

---

## Contact Information

**AWS Support**: https://console.aws.amazon.com/support
**Render Support**: https://render.com/docs/support

---

## Notes

_Use this section to document any deployment-specific details, issues encountered, or deviations from the plan:_

---

**Deployment Date**: _______________
**Deployed By**: _______________
**Sign-off**: _______________

---

## Appendix: Quick Commands

### Test S3 Connection
```bash
python manage.py shell
from django.core.files.storage import default_storage
print(default_storage.bucket_name)  # Should print: primetrade-documents
```

### List Files in S3
```bash
python manage.py shell
from django.core.files.storage import default_storage
files = default_storage.listdir('bols/2025/')[1]
for f in files:
    print(f)
```

### Migrate PDFs
```bash
# Dry run
python manage.py migrate_pdfs_to_s3 --dry-run

# Actual migration
python manage.py migrate_pdfs_to_s3
```

### Check Audit Logs
```python
from bol_system.models import AuditLog
AuditLog.objects.filter(action='BOL_DOWNLOADED').count()
```

### Emergency: Disable S3
```bash
# In Render dashboard, set:
USE_S3=False
# Then trigger manual deploy
```
