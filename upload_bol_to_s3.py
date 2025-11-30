#!/usr/bin/env python
"""Upload generated BOL PDF to S3"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'primetrade_project.settings')
django.setup()

from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import boto3
from decouple import config

# BOL details
bol_number = "PRT-2025-0009"
local_pdf = "/tmp/PRT-2025-0009.pdf"
s3_path = "bols/2025/PRT-2025-0009.pdf"

# Read the PDF file
with open(local_pdf, 'rb') as f:
    pdf_content = f.read()

# Upload to S3
s3_client = boto3.client(
    's3',
    aws_access_key_id=config('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=config('AWS_SECRET_ACCESS_KEY'),
    region_name=config('AWS_S3_REGION_NAME', default='us-east-2')
)

bucket_name = config('AWS_STORAGE_BUCKET_NAME', default='primetrade-documents')

print(f"Uploading {local_pdf} to s3://{bucket_name}/{s3_path}...")

s3_client.put_object(
    Bucket=bucket_name,
    Key=s3_path,
    Body=pdf_content,
    ContentType='application/pdf',
    CacheControl='max-age=86400',
    # No ACL - using bucket policy
)

# Generate the URL
s3_url = f"https://{bucket_name}.s3.{config('AWS_S3_REGION_NAME', default='us-east-2')}.amazonaws.com/{s3_path}"

print(f"✓ Uploaded successfully!")
print(f"S3 URL: {s3_url}")
print(f"\nNow updating database...")

# Update the database record
import psycopg2
from decouple import config

conn = psycopg2.connect(config('DATABASE_URL'))
cur = conn.cursor()

cur.execute(
    "UPDATE bol_system_bol SET pdf_url = %s WHERE bol_number = %s",
    (s3_path, bol_number)
)
conn.commit()

print(f"✓ Database updated!")
print(f"\nBOL {bol_number} is now available at:")
print(f"{s3_url}")

cur.close()
conn.close()
