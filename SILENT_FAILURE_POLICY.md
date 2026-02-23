# Silent Failure Policy
**Effective:** February 2026
**Status:** MANDATORY — No exceptions

## The Rule

At any integration boundary — email sends, PDF generation, CSV/Excel exports, webhook calls, background tasks, external API calls — exception handling MUST follow these requirements:

### If you catch an exception, you MUST:
1. **Log at ERROR level** (not warning, not info)
2. **Include context** — at minimum: the record ID, the function name, and the exception message
3. **Surface the failure** — return an error state that is visible somewhere (admin UI, Sentry alert, task status, API error response)

### You MUST NOT:
- `except Exception: return False` (swallows everything, surfaces nothing)
- `except: pass` (swallows everything, continues silently)
- `except Exception as e: logger.info(...)` (logs at wrong level, won't trigger alerts)
- Catch broadly and return a success-like response

### Acceptable Patterns

```python
# GOOD — logs at error level with context, returns error state
try:
    send_bol_notification(bol)
except Exception as e:
    logger.error(
        f"BOL notification failed for BOL {bol.id}: {e}",
        exc_info=True,  # includes full traceback in logs
        extra={'bol_id': bol.id, 'tenant': bol.tenant.code}
    )
    return {'email_sent': False, 'error': str(e)}
```

```python
# GOOD — narrow exception, re-raises unexpected errors
try:
    pdf_bytes = generate_bol_pdf(bol)
except PdfGenerationError as e:
    logger.error(f"PDF generation failed for BOL {bol.id}: {e}", exc_info=True)
    raise  # let caller handle
except Exception as e:
    logger.error(f"Unexpected error generating PDF for BOL {bol.id}: {e}", exc_info=True)
    raise  # never swallow unexpected errors
```

### Unacceptable Patterns

```python
# BAD — swallows error, caller thinks success
try:
    send_bol_notification(bol)
except Exception:
    return False

# BAD — logs at info level, no context, no one will see it
try:
    generate_pdf(bol)
except Exception as e:
    logger.info(f"PDF failed: {e}")
    pass

# BAD — catches everything, continues as if nothing happened
try:
    export_to_csv(queryset)
except:
    pass
```

## Integration Boundaries (Where This Applies)

This policy applies to ALL code at these boundaries:
- **Email sends** — `send_mail()`, `EmailMessage`, notification functions
- **PDF generation** — ReportLab, WeasyPrint, any PDF builder
- **File exports** — CSV, Excel, any file generation
- **External API calls** — webhooks, third-party services
- **Background tasks** — Celery tasks, management commands called by cron
- **SSO/Auth callbacks** — JWT validation, OAuth flows

## For AI Assistants

When writing or modifying code at integration boundaries:
1. Never use bare `except:` or `except Exception: pass/return False`
2. Always log at `logger.error()` with `exc_info=True`
3. Always include the primary record ID in the log message
4. If the original code has a silent failure pattern, fix it as part of your change
5. If you're unsure whether something is an integration boundary, treat it as one
