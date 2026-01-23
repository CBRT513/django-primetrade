import logging
import re
from datetime import date, timedelta
from django.conf import settings

logger = logging.getLogger('kiosk')


def date_serial(d: date) -> int:
    """Excel-style date serial (days since 1899-12-30)."""
    excel_epoch = date(1899, 12, 30)
    return (d - excel_epoch).days


def generate_session_code() -> str:
    """
    Generate unique session code: XXXX-NN
    XXXX = date serial mod 10000
    NN = daily sequence number
    Example: 6044-01 (January 22, 2026, first check-in)
    """
    from .models import DriverSession

    today = date.today()
    serial = date_serial(today) % 10000

    today_count = DriverSession.objects.filter(
        checked_in_at__date=today
    ).count()

    sequence = today_count + 1
    code = f"{serial}-{sequence:02d}"

    # Handle unlikely collision
    while DriverSession.objects.filter(code=code).exists():
        sequence += 1
        code = f"{serial}-{sequence:02d}"

    logger.debug(f"Generated session code: {code}")
    return code


def normalize_phone(phone: str) -> str:
    """Convert (513) 555-1234 to +15135551234 for Twilio."""
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 10:
        return f"+1{digits}"
    elif len(digits) == 11 and digits.startswith('1'):
        return f"+{digits}"
    return phone  # Return as-is if unexpected format


def send_checkin_sms(phone: str, code: str) -> dict:
    """
    Send check-in code to driver via Twilio.

    Returns:
        dict with 'success' (bool) and 'error' (str or None)
    """
    # Check if Twilio is configured
    if not getattr(settings, 'TWILIO_ACCOUNT_SID', None) or not settings.TWILIO_ACCOUNT_SID:
        logger.info(f"[{code}] SMS skipped - Twilio not configured")
        return {'success': False, 'error': 'SMS not configured'}

    if not phone:
        logger.warning(f"[{code}] SMS skipped - no phone number provided")
        return {'success': False, 'error': 'No phone number'}

    try:
        from twilio.rest import Client

        client = Client(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN
        )

        normalized_phone = normalize_phone(phone)
        message = client.messages.create(
            body=f"CBRT Check-in code: {code}\n\nShow this code when your load is ready.\n\nQuestions? (513) 921-2400",
            from_=settings.TWILIO_PHONE_NUMBER,
            to=normalized_phone
        )
        logger.info(f"[{code}] SMS sent to {normalized_phone} - SID: {message.sid}")
        return {'success': True, 'error': None}

    except Exception as e:
        logger.error(f"[{code}] SMS send failed to {phone}: {str(e)}")
        return {'success': False, 'error': str(e)}


def expire_old_sessions():
    """Mark sessions older than 4 hours as expired."""
    from django.utils import timezone
    from .models import DriverSession

    cutoff = timezone.now() - timedelta(hours=4)
    expired_count = DriverSession.objects.filter(
        checked_in_at__lt=cutoff,
        status__in=['waiting', 'assigned', 'ready']
    ).update(status='expired')

    if expired_count > 0:
        logger.info(f"Expired {expired_count} old driver sessions")
