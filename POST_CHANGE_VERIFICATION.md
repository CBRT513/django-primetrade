# Post-Change Verification Standard
**Effective:** February 2026
**Applies to:** ALL changes that touch risky code paths

## Why This Exists
On Feb 21, 2026, a weight standardization project introduced a type mismatch (float × Decimal) that broke BOL notification emails in production. The error was invisible because the email send was wrapped in try/except. This standard ensures risky changes are verified before deployment.

## When This Applies (Risk-Based Trigger)

This checklist is MANDATORY when a change touches ANY of:
- **Shared utilities** — `utils/`, constants, helper modules
- **Base classes or mixins** — anything other code inherits from
- **Model fields** — type changes, new fields, renamed fields
- **Template tags or filters** — used across multiple templates
- **Email, PDF, or export code** — integration boundaries
- **Settings or configuration** — Django settings, env vars
- **Background tasks** — Celery tasks, management commands
- **Signals or receivers** — side effects triggered by model changes
- **Authentication or SSO** — security-sensitive paths
- **Weight or billing calculations** — financial accuracy

File count is irrelevant. A one-line change to a shared constant is riskier than renaming 30 templates.

## Verification Checklist

### 1. Type Safety Check
After changing any constant, utility function, or shared module:
```bash
# Find all imports of the changed module
grep -rn "from.*<module>.*import\|import.*<module>" --include="*.py" .

# For each usage, verify type compatibility:
# - What type does the caller pass in?
# - What type does the changed code expect?
# - Will Python raise TypeError, AttributeError, or silently produce wrong results?
```

### 2. Silent Failure Audit
Find every try/except block in changed files AND files that import changed modules:
```bash
# Find exception handlers in affected files
grep -n "except.*:" <affected_files>
```

A handler is a **silent failure** if ALL THREE are true:
1. It does NOT re-raise the exception
2. It does NOT log at `error` level (or send to Sentry)
3. The function is at an integration boundary (email, PDF, export, webhook, task)

Any silent failure found MUST be fixed per `SILENT_FAILURE_POLICY.md` as part of this change.

### 3. Run Django System Checks
```bash
python manage.py check
```

### 4. Import Verification
```bash
# Verify no import errors
python manage.py shell -c "from <new_or_changed_module> import *"

# Verify no circular imports
python -c "import <app>"
```

### 5. Downstream Impact Check
For any change to a model, utility, or constant:
```bash
# Find everything that uses the changed item
grep -rn "<changed_function_or_constant>" --include="*.py" .
```
Verify each caller is compatible. Pay special attention to:
- Email sends (often wrapped in try/except)
- PDF generation (often wrapped in try/except)
- Background tasks / async jobs
- Management commands
- Template tags and filters
- Signals and receivers

### 6. Integration Point Verification
If the change touches code used by integration boundaries:
- [ ] Email sends still work (trigger the flow, check logs)
- [ ] PDF generation still works (generate a test document)
- [ ] CSV/Excel exports still work
- [ ] API endpoints return correct data and types
- [ ] Webhook/callback handlers still work

### 7. Run Tests
```bash
python manage.py test
```

## Evidence Required

Before merging, the developer or AI assistant MUST provide:
1. Output of `python manage.py check`
2. List of all callers of changed modules and their type-compatibility status
3. List of all exception handlers in affected files and whether they comply with SILENT_FAILURE_POLICY.md
4. List of integration touchpoints affected and how each was verified
5. Test results (or explicit statement that no tests exist + manual verification done)

## For AI Assistants (Claude Code, etc.)

When completing a change that triggers this checklist:

1. **BEFORE committing**, run the full verification checklist
2. **Report evidence** — don't just say "done." Provide all 5 items from Evidence Required
3. **Never assume type compatibility.** If a function previously received `int` and now receives `Decimal`, check every callsite
4. **Never assume try/except is harmless.** Check against SILENT_FAILURE_POLICY.md
5. **If you cannot run tests**, explicitly state that and list every usage site for manual verification
6. **Fix silent failure patterns** found during audit — don't just report them

## Quick Reference: Common Type Bombs

| Change | Breaks when | Fix |
|--------|-------------|-----|
| `int` constant → `Decimal` constant | Multiplied by `float` from DB | Use wrapper function with `Decimal(str(value))` |
| String formatting changes | `None` values hit new format | Add `or ""` / `or 0` guards |
| Return type changes | Caller does arithmetic/comparison on result | Update all callers |
| New required parameter | Existing callers don't pass it | Add default value |
| Import path changes | Old import paths in other files | Find and update all imports |
