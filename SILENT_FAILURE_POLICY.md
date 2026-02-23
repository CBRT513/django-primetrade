# Silent Failure Policy

## Rule
Never silently swallow exceptions at integration boundaries (S3, APIs, DB writes, PDF generation, email sending).

### If you catch an exception, you MUST:
1. **Log at ERROR level** (not warning, not info)
2. **Include context** — at minimum: the record ID, the function name, and the exception message
3. **Surface the failure** — do at least ONE of the following:
   - **Re-raise** the exception (let the caller handle it)
   - **Return a typed error** object or dict with error details (e.g., `{'email_sent': False, 'error': str(e)}`)
   - **Mark status on the record** and save it (e.g., `bol.email_status = 'FAILED'; bol.save()`)
   - **Capture to Sentry** via `sentry_sdk.capture_exception(e)`

   Logging at error level alone is NOT sufficient to "surface" a failure. The failure must be discoverable by someone who is not reading logs.

### Anti-patterns (DO NOT):
```python
# BAD: silent swallow
try:
    upload_to_s3(file)
except Exception:
    pass

# BAD: log at wrong level
try:
    send_email(bol)
except Exception as e:
    logger.warning(f"Email failed: {e}")  # Should be logger.error

# BAD: log only, no surface
try:
    generate_pdf(bol)
except Exception as e:
    logger.error(f"PDF failed: {e}")
    # Nothing returned, no status update, caller thinks it succeeded
```

### Correct patterns:
```python
# GOOD: re-raise after logging
try:
    upload_to_s3(file)
except Exception as e:
    logger.error(f"S3 upload failed for {file.name}: {e}", exc_info=True)
    raise

# GOOD: return error state
try:
    send_email(bol)
except Exception as e:
    logger.error(f"Email failed for BOL {bol.id}: {e}", exc_info=True)
    return {'email_sent': False, 'error': str(e)}

# GOOD: mark status on record
try:
    pdf_url = generate_pdf(bol)
except Exception as e:
    logger.error(f"PDF generation failed for BOL {bol.id}: {e}", exc_info=True)
    bol.pdf_status = 'FAILED'
    bol.save(update_fields=['pdf_status'])
    return None
```
