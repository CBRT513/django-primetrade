# AWS S3 Setup Guide for PrimeTrade BOL Storage

This guide walks you through setting up AWS S3 for permanent, reliable BOL PDF storage.

## Table of Contents
1. [Overview](#overview)
2. [AWS Account Setup](#aws-account-setup)
3. [Create S3 Bucket](#create-s3-bucket)
4. [Create IAM User](#create-iam-user)
5. [Configure Django Application](#configure-django-application)
6. [Migrate Existing PDFs](#migrate-existing-pdfs)
7. [Testing](#testing)
8. [Production Deployment](#production-deployment)
9. [Cost Monitoring](#cost-monitoring)
10. [Troubleshooting](#troubleshooting)

---

## Overview

### Why S3?
- **Permanent storage**: Files persist across deployments (Render's filesystem is ephemeral)
- **99.999999999% durability**: AWS guarantees your files won't be lost
- **Scalable**: Handles unlimited documents
- **Cost-effective**: ~$3/year for expected usage
- **Secure**: Signed URLs with automatic expiration
- **Customer access**: Share documents securely with customers

### Architecture
```
┌──────────────┐      Create BOL       ┌─────────────┐
│  Office User │  ─────────────────►   │   Django    │
└──────────────┘                       │ Application │
                                       └──────┬──────┘
                                              │
                                              │ Upload PDF
                                              ▼
                                       ┌─────────────┐
                                       │   AWS S3    │
                                       │   Bucket    │
                                       └──────┬──────┘
                                              │
                                              │ Signed URL
                                              ▼
┌──────────────┐      Download BOL     ┌─────────────┐
│   Customer   │  ◄─────────────────   │   Django    │
└──────────────┘                       │ Application │
                                       └─────────────┘
```

---

## AWS Account Setup

### Step 1: Create AWS Account (if needed)

1. Go to [aws.amazon.com](https://aws.amazon.com)
2. Click "Create an AWS Account"
3. Enter email, password, and account name
4. Provide payment information (required, but usage will be minimal)
5. Verify phone number
6. Choose **Basic Support Plan** (free)

**Estimated time**: 10 minutes

---

## Create S3 Bucket

### Step 2: Create the Storage Bucket

1. **Log in to AWS Console**
   - Go to [console.aws.amazon.com](https://console.aws.amazon.com)
   - Sign in with your AWS account

2. **Navigate to S3**
   - Search for "S3" in the top search bar
   - Click "S3" to open the S3 dashboard

3. **Create Bucket**
   - Click **"Create bucket"** button
   - **Bucket name**: `primetrade-documents` (must be globally unique)
     - If taken, try: `primetrade-bols`, `cbrt-documents`, etc.
   - **AWS Region**: Select **US East (Ohio) us-east-2**
     - This is geographically closest to Cincinnati
     - Lower latency and costs

4. **Configure Bucket Settings**
   - **Object Ownership**: Select **"ACLs disabled (recommended)"**
   - **Block Public Access**: ✅ **KEEP ALL CHECKED**
     - ✅ Block all public access
     - We'll use signed URLs for secure access
   - **Bucket Versioning**: **Enable**
     - Keeps history of all document versions
     - Can recover from accidental deletions
   - **Default encryption**: **Enable** (Server-side encryption with Amazon S3 managed keys - SSE-S3)
   - **Object Lock**: **Disable** (not needed unless regulatory requirement)

5. **Create Bucket**
   - Click **"Create bucket"**
   - You should see success message

**Result**: You now have a private S3 bucket named `primetrade-documents` in us-east-2

---

## Create IAM User

### Step 3: Create Service Account for Django

Django needs credentials to upload/download files to S3. We'll create a dedicated IAM user with limited permissions (principle of least privilege).

1. **Navigate to IAM**
   - Search for "IAM" in the top search bar
   - Click "IAM" to open Identity and Access Management

2. **Create User**
   - In left sidebar, click **"Users"**
   - Click **"Create user"** button
   - **User name**: `primetrade-django`
   - **Access type**: Select **"Programmatic access"** only (no AWS console access)
   - Click **"Next"**

3. **Set Permissions**
   - Select **"Attach policies directly"**
   - **DO NOT** use `AmazonS3FullAccess` (too broad)
   - Click **"Create policy"** (opens new tab)

4. **Create Custom Policy** (in new tab)
   - Click **"JSON"** tab
   - Paste this policy (replace `primetrade-documents` if you used different name):

   ```json
   {
       "Version": "2012-10-17",
       "Statement": [
           {
               "Sid": "ListBucket",
               "Effect": "Allow",
               "Action": [
                   "s3:ListBucket"
               ],
               "Resource": [
                   "arn:aws:s3:::primetrade-documents"
               ]
           },
           {
               "Sid": "UploadDownloadDeleteObjects",
               "Effect": "Allow",
               "Action": [
                   "s3:PutObject",
                   "s3:GetObject",
                   "s3:DeleteObject",
                   "s3:GetObjectVersion"
               ],
               "Resource": [
                   "arn:aws:s3:::primetrade-documents/*"
               ]
           }
       ]
   }
   ```

   - Click **"Next: Tags"** (skip tags)
   - Click **"Next: Review"**
   - **Policy name**: `PrimetradeDjangoS3Access`
   - **Description**: `Allow Django app to read/write BOL PDFs to primetrade-documents bucket`
   - Click **"Create policy"**
   - Close this tab

5. **Attach Policy to User** (back to original tab)
   - Click refresh button on policies list
   - Search for `PrimetradeDjangoS3Access`
   - ✅ Check the policy
   - Click **"Next"**

6. **Review and Create**
   - Review the user details
   - Click **"Create user"**

7. **CRITICAL: Save Credentials**
   - You'll see **Access key ID** and **Secret access key**
   - Click **"Download .csv"** or copy both values immediately
   - **⚠️ YOU CANNOT VIEW THE SECRET KEY AGAIN AFTER LEAVING THIS PAGE**
   - Store securely (password manager, .env file)

   Example:
   ```
   Access Key ID:     AKIAIOSFODNN7EXAMPLE
   Secret Access Key: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
   ```

**Result**: You now have AWS credentials for Django to access S3

---

## Configure Django Application

### Step 4: Update Environment Variables

#### Local Development (.env file)

1. **Copy credentials to .env**:
   ```bash
   # Keep USE_S3=False for local development (uses local filesystem)
   USE_S3=False

   # But add credentials for migration script
   AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
   AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
   AWS_STORAGE_BUCKET_NAME=primetrade-documents
   AWS_S3_REGION_NAME=us-east-2
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

   This installs:
   - `django-storages==1.14.2` - Django S3 integration
   - `boto3==1.34.14` - AWS SDK for Python

#### Production (Render Dashboard)

1. **Log in to Render**: [dashboard.render.com](https://dashboard.render.com)

2. **Navigate to your service**: Click on `primetrade` service

3. **Add Environment Variables**:
   - Go to **"Environment"** tab
   - Add the following variables:

   | Key | Value | Notes |
   |-----|-------|-------|
   | `USE_S3` | `True` | Enable S3 in production |
   | `AWS_ACCESS_KEY_ID` | `AKIA...` | Your access key ID |
   | `AWS_SECRET_ACCESS_KEY` | `wJal...` | Your secret key (sensitive!) |
   | `AWS_STORAGE_BUCKET_NAME` | `primetrade-documents` | Your bucket name |
   | `AWS_S3_REGION_NAME` | `us-east-2` | Ohio region |

4. **Save changes** - Render will automatically redeploy

**Security Note**: Never commit AWS credentials to Git!

---

## Migrate Existing PDFs

### Step 5: Upload Local PDFs to S3

If you have existing BOL PDFs in your local `media/bol_pdfs/` directory, migrate them to S3:

1. **Dry run** (see what would be uploaded without actually uploading):
   ```bash
   python manage.py migrate_pdfs_to_s3 --dry-run
   ```

2. **Review output**:
   ```
   ======================================================================
   BOL PDF Migration to S3
   ======================================================================
   DRY RUN MODE - No files will be uploaded

   Found 4 BOL records in database

     → PRT-2025-0002: Would upload to bols/2025/PRT-2025-0002.pdf
     → PRT-2025-0003: Would upload to bols/2025/PRT-2025-0003.pdf
     → PRT-2025-0004: Would upload to bols/2025/PRT-2025-0004.pdf
     → PRT-2025-0005: Would upload to bols/2025/PRT-2025-0005.pdf

   ======================================================================
   Migration Summary
   ======================================================================
   Total BOL records:    4
   PDFs found locally:   4
   PDFs missing:         0
   Would upload:         4
   ======================================================================
   ```

3. **Run actual migration**:
   ```bash
   # Enable S3 temporarily for migration
   export USE_S3=True

   # Run migration
   python manage.py migrate_pdfs_to_s3

   # Disable S3 for local development
   export USE_S3=False
   ```

4. **Verify in AWS Console**:
   - Go to S3 → `primetrade-documents` bucket
   - Navigate to `bols/2025/` folder
   - You should see all uploaded PDFs

**File Organization**:
```
primetrade-documents/
└── bols/
    ├── 2025/
    │   ├── PRT-2025-0001.pdf
    │   ├── PRT-2025-0002.pdf
    │   └── ...
    ├── 2026/
    │   └── ...
    └── ...
```

---

## Testing

### Step 6: Verify S3 Integration

#### Test PDF Upload (Local → S3)

1. **Enable S3 in local environment**:
   ```bash
   # Edit .env
   USE_S3=True
   ```

2. **Create a test BOL**:
   - Visit http://localhost:8001/office.html
   - Create a new BOL
   - Submit

3. **Verify upload**:
   - Check Django response - should return S3 URL:
     ```json
     {
       "pdf_url": "https://primetrade-documents.s3.amazonaws.com/bols/2025/PRT-2025-0006.pdf?..."
     }
     ```
   - Go to AWS Console → S3 → primetrade-documents
   - File should appear in `bols/2025/`

#### Test PDF Download

1. **Get download URL**:
   ```bash
   curl -H "Cookie: sessionid=..." \
        http://localhost:8001/api/bol/1/download/
   ```

2. **Response**:
   ```json
   {
     "downloadUrl": "https://primetrade-documents.s3.amazonaws.com/bols/2025/PRT-2025-0006.pdf?X-Amz-Algorithm=...",
     "expiresIn": 86400,
     "bolNumber": "PRT-2025-0006",
     "fileName": "PRT-2025-0006.pdf"
   }
   ```

3. **Open URL** - PDF should download

4. **Check expiration** - URL should expire after 24 hours

#### Test Audit Logging

1. **Download a BOL** via API or web interface

2. **Check audit logs**:
   ```bash
   python manage.py shell
   ```

   ```python
   from bol_system.models import AuditLog
   AuditLog.objects.filter(action='BOL_DOWNLOADED').latest('created_at')
   # Should show download event with user email and timestamp
   ```

---

## Production Deployment

### Step 7: Deploy to Render

1. **Commit changes**:
   ```bash
   git add .
   git commit -m "feat: Add AWS S3 storage for BOL PDFs"
   git push origin claude/repo-analysis-011CUoE3b2q87No7CHwV8M89
   ```

2. **Verify Render environment variables**:
   - Dashboard → primetrade service → Environment tab
   - Confirm all AWS variables are set correctly

3. **Deploy**:
   - Render automatically deploys on git push
   - Or manually trigger: Dashboard → "Manual Deploy"

4. **Monitor deployment**:
   - Watch logs: Dashboard → Logs tab
   - Look for successful startup message

5. **Migrate existing production PDFs** (if any on Render):
   ```bash
   # SSH into Render (if possible) or use Render Shell
   python manage.py migrate_pdfs_to_s3
   ```

6. **Test in production**:
   - Go to https://django-primetrade.onrender.com
   - Create a new BOL
   - Verify PDF uploads to S3
   - Download the BOL
   - Check that URL is signed and temporary

---

## Cost Monitoring

### Step 8: Set Up Billing Alerts

1. **Navigate to AWS Billing**:
   - Click your account name (top right)
   - Select **"Billing Dashboard"**

2. **Create Budget**:
   - Click **"Budgets"** in left sidebar
   - Click **"Create budget"**
   - Template: **"Zero spend budget"**
   - Or set custom: **$1/month** threshold
   - Add email alert

3. **Monitor Usage**:
   - Dashboard → **"Cost Explorer"**
   - Filter by Service: **S3**
   - Check monthly costs

### Expected Costs

| Month | Storage | Operations | Egress | Total |
|-------|---------|------------|--------|-------|
| 1 | $0.001 | $0.007 | $0.30 | **~$0.31** |
| 6 | $0.006 | $0.042 | $1.80 | **~$1.85** |
| 12 | $0.012 | $0.084 | $3.60 | **~$3.70** |

**First Year**: ~$3-4 total

---

## Troubleshooting

### Common Issues

#### 1. "Access Denied" Error

**Symptom**: `botocore.exceptions.ClientError: An error occurred (403) when calling the PutObject operation: Access Denied`

**Solution**:
- Verify IAM policy includes `s3:PutObject` permission
- Check bucket name matches in IAM policy and .env
- Ensure credentials are correct (no typos)

#### 2. "Bucket Does Not Exist"

**Symptom**: `The specified bucket does not exist`

**Solution**:
- Verify bucket name in `.env` matches AWS Console
- Check region matches (`us-east-2`)
- Bucket names are case-sensitive

#### 3. PDFs Not Uploading

**Symptom**: BOL created but PDF missing in S3

**Solution**:
- Check `USE_S3=True` in environment
- Check Django logs: `tail -f logs/primetrade.log`
- Verify AWS credentials are loaded:
  ```python
  from django.conf import settings
  print(settings.AWS_ACCESS_KEY_ID)  # Should not be empty
  ```

#### 4. Signed URLs Not Working

**Symptom**: Download URL returns 403 Forbidden

**Solution**:
- Signed URLs expire after 24 hours - generate fresh URL
- Check IAM user has `s3:GetObject` permission
- Verify `AWS_QUERYSTRING_AUTH=True` in settings

#### 5. Migration Script Fails

**Symptom**: `migrate_pdfs_to_s3` command errors

**Solution**:
- Ensure `USE_S3=True` when running migration
- Check local PDF files exist: `ls media/bol_pdfs/`
- Verify AWS credentials are set in environment

### Debug Checklist

```bash
# 1. Check environment variables
python manage.py shell
from django.conf import settings
print("USE_S3:", settings.USE_S3)
print("Bucket:", settings.AWS_STORAGE_BUCKET_NAME)
print("Region:", settings.AWS_S3_REGION_NAME)

# 2. Test S3 connection
from django.core.files.storage import default_storage
print("Storage backend:", type(default_storage))
# Should show: <class 'storages.backends.s3boto3.S3Boto3Storage'>

# 3. Test file upload
from django.core.files.base import ContentFile
path = default_storage.save('test.txt', ContentFile(b'Hello S3'))
print("Uploaded to:", path)

# 4. Test file download
url = default_storage.url('test.txt')
print("Download URL:", url)

# 5. Clean up
default_storage.delete('test.txt')
```

### Getting Help

- **AWS Support**: https://console.aws.amazon.com/support
- **Django-storages docs**: https://django-storages.readthedocs.io/
- **Project logs**: `/home/user/django-primetrade/logs/primetrade.log`

---

## Security Best Practices

### ✅ DO:
- Keep AWS credentials in `.env` file (not committed to git)
- Use IAM policies with least privilege
- Enable bucket versioning
- Enable encryption at rest
- Monitor billing alerts
- Rotate credentials periodically (every 90 days)
- Use signed URLs for customer access

### ❌ DON'T:
- Commit AWS credentials to git
- Make S3 bucket public
- Use root AWS account credentials
- Share access keys
- Disable encryption
- Give overly broad IAM permissions (e.g., `s3:*`)

---

## Next Steps

Once S3 is working:

1. **Backup Strategy**:
   - Consider cross-region replication for disaster recovery
   - AWS Backup service for automated backups

2. **Archive Old Documents**:
   - Create lifecycle policy to move old BOLs to Glacier (cheaper storage)
   - Example: After 1 year, transition to S3 Glacier ($0.004/GB/month)

3. **Customer Portal**:
   - Build customer-facing interface to view their BOLs
   - Use signed URLs with expiration for secure access

4. **Monitoring**:
   - Set up CloudWatch alerts for unusual S3 activity
   - Monitor access logs for security audits

---

## Summary

You've now set up:
- ✅ S3 bucket for permanent BOL storage
- ✅ IAM user with secure, limited permissions
- ✅ Django integration with django-storages
- ✅ PDF migration from local to S3
- ✅ Signed URLs for secure customer access
- ✅ Audit logging for compliance

**Total setup time**: 1-2 hours
**Ongoing cost**: ~$3-4/year
**Reliability**: 99.999999999% durability

Your BOL PDFs are now safely stored in the cloud! 🎉
