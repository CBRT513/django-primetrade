#!/bin/bash
# Post-change verification script
# Usage: ./scripts/verify_changes.sh [base_branch]

set -e

BASE_BRANCH="${1:-main}"

echo "=== Post-Change Verification ==="
echo "Comparing against: $BASE_BRANCH"
echo ""

# Get changed Python files
MERGE_BASE=$(git merge-base HEAD "$BASE_BRANCH" 2>/dev/null || echo "$BASE_BRANCH")
CHANGED_PY_FILES=$(git diff --name-only "$MERGE_BASE" HEAD -- '*.py' 2>/dev/null || true)

if [ -z "$CHANGED_PY_FILES" ]; then
    echo "No Python files changed. Nothing to verify."
    exit 0
fi

echo "Changed Python files:"
echo "$CHANGED_PY_FILES" | sed 's/^/  /'
echo ""

# Step 1: Raw constant usage outside weight_constants.py
echo "--- Step 1: Raw Weight Constant Usage ---"
RAW_USAGE=$(grep -rn "LBS_PER_SHORT_TON\|LBS_PER_METRIC_TON\|SHORT_TONS_PER_METRIC_TON" --include="*.py" . \
    | grep -v "weight_constants.py" \
    | grep -v "import" \
    | grep -v "__pycache__" || true)

if [ -n "$RAW_USAGE" ]; then
    echo "   ⚠️  Raw constant usage found (should use conversion functions):"
    echo "$RAW_USAGE" | sed 's/^/   /'
else
    echo "   ✅ No raw constant usage outside weight_constants.py"
fi
echo ""

# Step 2: Bare Decimal() calls
echo "--- Step 2: Bare Decimal() Calls ---"
BARE_DECIMAL=$(grep -rn "Decimal(" --include="*.py" . \
    | grep -v "Decimal(str(" \
    | grep -v "Decimal('" \
    | grep -v "Decimal(\"" \
    | grep -v "weight_constants" \
    | grep -v "migrations" \
    | grep -v "__pycache__" \
    | grep -v "_to_decimal" || true)

if [ -n "$BARE_DECIMAL" ]; then
    echo "   ⚠️  Bare Decimal() calls (may need Decimal(str(x)) for float safety):"
    echo "$BARE_DECIMAL" | head -10 | sed 's/^/   /'
else
    echo "   ✅ No bare Decimal() calls found"
fi
echo ""

# Step 3: Silent failure audit on changed files
# NOTE: This only audits changed files. For importer coverage,
# manually grep for modules that import the changed files.
echo "--- Step 3: Silent Failure Audit (changed files) ---"
if [ -n "$CHANGED_PY_FILES" ]; then
    BARE_EXCEPT=$(echo "$CHANGED_PY_FILES" | xargs grep -n "except:" 2>/dev/null || true)

    if [ -n "$BARE_EXCEPT" ]; then
        echo "   🔴 BARE except: clauses (must specify exception type):"
        echo "$BARE_EXCEPT" | sed 's/^/   /'
    fi

    PASS_AFTER_EXCEPT=$(echo "$CHANGED_PY_FILES" | xargs grep -A1 "except" 2>/dev/null | grep "pass" || true)
    if [ -n "$PASS_AFTER_EXCEPT" ]; then
        echo "   🔴 POTENTIAL SILENT FAILURES (except + pass):"
        echo "$PASS_AFTER_EXCEPT" | sed 's/^/   /'
    fi

    if [ -z "$BARE_EXCEPT" ] && [ -z "$PASS_AFTER_EXCEPT" ]; then
        echo "   ✅ No obvious silent failures in changed files"
    fi

    # Check for logging at wrong level near except blocks
    WRONG_LEVEL=$(echo "$CHANGED_PY_FILES" | xargs grep -A5 "except" 2>/dev/null | grep -E "logger\.(info|warning|debug)\(" || true)
    if [ -n "$WRONG_LEVEL" ]; then
        echo ""
        echo "   ⚠️  Exception handlers logging below ERROR level (review against SILENT_FAILURE_POLICY.md):"
        echo "$WRONG_LEVEL" | head -10 | sed 's/^/   /'
        echo "   Policy requires logger.error() at integration boundaries"
    fi
fi
echo ""

echo "=== Verification Complete ==="
