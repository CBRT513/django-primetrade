from datetime import date
from django.conf import settings


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
    serial = date_serial(today) % 10000  # 6044

    today_count = DriverSession.objects.filter(
        checked_in_at__date=today
    ).count()

    sequence = today_count + 1
    code = f"{serial}-{sequence:02d}"

    # Handle unlikely collision
    while DriverSession.objects.filter(code=code).exists():
        sequence += 1
        code = f"{serial}-{sequence:02d}"

    return code


def send_checkin_sms(phone: str, code: str) -> bool:
    """Send check-in code to driver via Twilio."""
    try:
        from twilio.rest import Client

        client = Client(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN
        )

        message = client.messages.create(
            body=f"CBRT Check-in code: {code}\n\nShow this code when your load is ready.\n\nQuestions? (513) 921-2400",
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone
        )
        return True
    except Exception as e:
        # Log error but don't fail check-in
        print(f"SMS send failed: {e}")
        return False


def expire_old_sessions():
    """Mark sessions older than 4 hours as expired."""
    from django.utils import timezone
    from datetime import timedelta
    from .models import DriverSession

    cutoff = timezone.now() - timedelta(hours=4)
    DriverSession.objects.filter(
        checked_in_at__lt=cutoff,
        status__in=['waiting', 'assigned', 'ready']
    ).update(status='expired')
