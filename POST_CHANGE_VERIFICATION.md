# Post-Change Verification Checklist

Run after every change that touches weight conversions, type coercion, or integration boundaries.

## Quick Check: `scripts/verify_changes.sh`
```bash
./scripts/verify_changes.sh [base_branch]
# Defaults to 'main'
```

## Manual Steps

### 1. Raw Constant Audit
Ensure no code uses weight constants directly in arithmetic:
```bash
grep -rn "LBS_PER_SHORT_TON\|LBS_PER_METRIC_TON\|SHORT_TONS_PER_METRIC_TON" --include="*.py" . \
  | grep -v "weight_constants.py" \
  | grep -v "import"
```
Any hits should use conversion functions instead.

### 2. Silent Failure Audit
Find every try/except block in changed files. Then manually check files that import changed modules — the script flags changed files only, importers require manual grep:
```bash
git diff --name-only $(git merge-base HEAD main) HEAD -- '*.py' | xargs grep -n "except" 2>/dev/null
```
Verify each follows `SILENT_FAILURE_POLICY.md`.

### 3. Type Safety Check
Look for bare `Decimal()` calls on model fields (which may return float):
```bash
grep -rn "Decimal(" --include="*.py" . | grep -v "Decimal(str(" | grep -v "Decimal('" | grep -v "weight_constants" | grep -v "migrations"
```

### 4. None/Empty Guard
Verify weight conversion callsites don't pass potentially-None values without checking:
```bash
grep -rn "short_tons_to_lbs\|lbs_to_short_tons\|metric_tons_to_lbs\|lbs_to_metric_tons" --include="*.py" . | grep -v "weight_constants.py" | grep -v "test_"
```
Each callsite: is the input guaranteed non-None? If not, add a guard or let the TypeError surface.
