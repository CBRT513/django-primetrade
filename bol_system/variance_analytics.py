"""
Weight Variance Analysis — all statistical computation for the variance report.
Keeps views.py thin per fat-models/thin-views pattern.
"""
import statistics
from decimal import Decimal
from .models import BOL, Product
from .security import get_tenant_filter


OUTLIER_THRESHOLD = 5.0   # percent
CRITICAL_THRESHOLD = 10.0  # percent


def compute_variance_report(product_id, tenant_filter):
    """
    Build the full variance report dict for a single product.

    Args:
        product_id: Product PK
        tenant_filter: dict from get_tenant_filter(request)

    Returns:
        dict with all report sections, or None if product not found.
    """
    try:
        product = Product.objects.get(id=product_id, **tenant_filter)
    except Product.DoesNotExist:
        return None

    bols = list(
        BOL.objects.filter(product=product, is_void=False, **tenant_filter)
        .select_related('carrier')
        .order_by('-date')
    )

    total_bols = len(bols)
    paired = []       # both weights exist
    missing = []      # no official weight
    bucket_only = []  # same as missing, but used for inventory calc

    for bol in bols:
        net = _to_float(bol.net_tons)
        official = _to_float(bol.official_weight_tons)

        if official is not None and net is not None and net > 0:
            variance_tons = official - net
            variance_pct = (variance_tons / net) * 100
            paired.append({
                'bol': bol,
                'net_tons': net,
                'official_tons': official,
                'variance_tons': round(variance_tons, 4),
                'variance_pct': round(variance_pct, 2),
            })
        else:
            missing.append(bol)
            if net is not None:
                bucket_only.append({'bol': bol, 'net_tons': net})

    # --- Section 1: Executive Summary ---
    with_official = len(paired)
    without_official = len(missing)
    coverage_pct = round((with_official / total_bols * 100), 1) if total_bols > 0 else 0

    summary = {
        'total_bols': total_bols,
        'with_official': with_official,
        'without_official': without_official,
        'coverage_pct': coverage_pct,
    }

    # --- Section 2: Bucket Weight Accuracy ---
    accuracy = _compute_accuracy(paired)

    # --- Section 3: Inventory Comparison ---
    inventory = _compute_inventory(product, bols, paired, bucket_only, accuracy)

    # --- Section 4: Carrier Variance ---
    carriers = _compute_carrier_variance(paired)

    # --- Section 5: Buyer Summary ---
    buyers = _compute_buyer_summary(bols)

    # --- Section 6: Flagged Outliers ---
    outliers = _compute_outliers(paired)

    # --- Section 7: Missing Official Weights ---
    missing_list = [{
        'id': b.id,
        'bol_number': b.bol_number,
        'date': b.date,
        'net_tons': round(_to_float(b.net_tons) or 0, 2),
        'buyer_name': b.buyer_name,
        'carrier_name': b.carrier_name,
    } for b in missing]

    return {
        'product': product,
        'summary': summary,
        'accuracy': accuracy,
        'inventory': inventory,
        'carriers': carriers,
        'buyers': buyers,
        'outliers': outliers,
        'missing': missing_list,
    }


def _compute_accuracy(paired):
    """Section 2: Bucket Weight Accuracy stats for all and clean data."""
    if not paired:
        return {'has_data': False}

    all_pcts = [p['variance_pct'] for p in paired]
    clean = [p for p in paired if abs(p['variance_pct']) <= OUTLIER_THRESHOLD]
    clean_pcts = [p['variance_pct'] for p in clean]

    result = {
        'has_data': True,
        'all': _variance_stats(all_pcts),
        'all_count_heavier': sum(1 for v in all_pcts if v > 0),
        'all_count_lighter': sum(1 for v in all_pcts if v < 0),
    }

    if len(clean_pcts) >= 2:
        result['clean'] = _variance_stats(clean_pcts)
        result['clean_count_heavier'] = sum(1 for v in clean_pcts if v > 0)
        result['clean_count_lighter'] = sum(1 for v in clean_pcts if v < 0)
        result['has_clean'] = True
    else:
        result['has_clean'] = False

    return result


def _variance_stats(pcts):
    """Mean, median, stdev for a list of variance percentages."""
    stats = {
        'count': len(pcts),
        'mean': round(statistics.mean(pcts), 2),
        'median': round(statistics.median(pcts), 2),
    }
    if len(pcts) >= 2:
        stats['stdev'] = round(statistics.stdev(pcts), 2)
    else:
        stats['stdev'] = None
    return stats


def _compute_inventory(product, bols, paired, bucket_only, accuracy):
    """Section 3: Three inventory scenarios."""
    start_tons = float(product.start_tons)

    # Scenario 1: Bucket Only (canonical)
    bucket_total = sum(_to_float(b.net_tons) or 0 for b in bols if not b.is_void)
    bucket_remaining = round(start_tons - bucket_total, 2)

    # Scenario 2: Hybrid (official where available, else bucket)
    hybrid_total = 0
    for b in bols:
        if b.is_void:
            continue
        official = _to_float(b.official_weight_tons)
        net = _to_float(b.net_tons) or 0
        hybrid_total += official if official is not None else net
    hybrid_remaining = round(start_tons - hybrid_total, 2)

    # Scenario 3: Best Estimate (hybrid + correction on bucket-only)
    correction_factor = 0
    if accuracy.get('has_clean') and accuracy['clean']['mean'] != 0:
        correction_factor = accuracy['clean']['mean']

    best_total = 0
    for b in bols:
        if b.is_void:
            continue
        official = _to_float(b.official_weight_tons)
        net = _to_float(b.net_tons) or 0
        if official is not None:
            best_total += official
        else:
            # Apply correction factor to bucket-only BOLs
            best_total += net * (1 + correction_factor / 100)
    best_remaining = round(start_tons - best_total, 2)

    return {
        'start_tons': round(start_tons, 2),
        'bucket_shipped': round(bucket_total, 2),
        'bucket_remaining': bucket_remaining,
        'hybrid_shipped': round(hybrid_total, 2),
        'hybrid_remaining': hybrid_remaining,
        'best_shipped': round(best_total, 2),
        'best_remaining': best_remaining,
        'correction_factor': round(correction_factor, 2),
    }


def _compute_carrier_variance(paired):
    """Section 4: Group by carrier, avg variance %, count."""
    by_carrier = {}
    for p in paired:
        name = p['bol'].carrier_name
        if name not in by_carrier:
            by_carrier[name] = []
        by_carrier[name].append(p['variance_pct'])

    result = []
    for name, pcts in sorted(by_carrier.items()):
        result.append({
            'carrier_name': name,
            'bol_count': len(pcts),
            'avg_variance_pct': round(statistics.mean(pcts), 2),
            'min_variance_pct': round(min(pcts), 2),
            'max_variance_pct': round(max(pcts), 2),
        })
    return result


def _compute_buyer_summary(bols):
    """Section 5: Group by buyer, BOL count + total net_tons."""
    by_buyer = {}
    for b in bols:
        if b.is_void:
            continue
        name = b.buyer_name
        if name not in by_buyer:
            by_buyer[name] = {'count': 0, 'net_tons': 0}
        by_buyer[name]['count'] += 1
        by_buyer[name]['net_tons'] += _to_float(b.net_tons) or 0

    result = []
    for name, data in sorted(by_buyer.items()):
        result.append({
            'buyer_name': name,
            'bol_count': data['count'],
            'total_net_tons': round(data['net_tons'], 2),
        })
    return result


def _compute_outliers(paired):
    """Section 6: BOLs with >5% absolute variance."""
    outliers = []
    for p in paired:
        abs_var = abs(p['variance_pct'])
        if abs_var > OUTLIER_THRESHOLD:
            if p['variance_pct'] < 0:
                cause = "Possible bucket over-read"
            else:
                cause = "Possible bucket under-read"
            if abs_var > CRITICAL_THRESHOLD:
                cause += " — Critical"

            outliers.append({
                'id': p['bol'].id,
                'bol_number': p['bol'].bol_number,
                'date': p['bol'].date,
                'net_tons': round(p['net_tons'], 2),
                'official_tons': round(p['official_tons'], 2),
                'variance_pct': p['variance_pct'],
                'cause': cause,
            })

    outliers.sort(key=lambda x: abs(x['variance_pct']), reverse=True)
    return outliers


def _to_float(val):
    """Safely convert Decimal/string to float, or None."""
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None
