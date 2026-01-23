import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from .models import DriverSession
from .services import generate_session_code, send_checkin_sms, expire_old_sessions

logger = logging.getLogger('kiosk')


# === Driver-Facing Views (iPad) ===

def home(request):
    """Kiosk home screen with Check-In / Check-Out buttons."""
    return render(request, 'kiosk/home.html')


def checkin(request):
    """Driver check-in form with comprehensive error handling."""
    if request.method == 'POST':
        code = None
        sms_warning = None

        try:
            # Extract and validate form data
            driver_name = request.POST.get('driver_name', '').strip()
            phone = request.POST.get('phone', '').strip()
            pickup_number = request.POST.get('pickup_number', '').strip()
            carrier_name = request.POST.get('carrier_name', '').strip()
            truck_number = request.POST.get('truck_number', '').strip()
            trailer_number = request.POST.get('trailer_number', '').strip()

            logger.info(f"Check-in started: carrier={carrier_name}, truck={truck_number}")

            # Generate unique code
            code = generate_session_code()

            # Create session
            try:
                session = DriverSession.objects.create(
                    code=code,
                    driver_name=driver_name,
                    phone=phone,
                    pickup_number=pickup_number,
                    carrier_name=carrier_name,
                    truck_number=truck_number,
                    trailer_number=trailer_number,
                )
                logger.info(f"[{code}] Session created: id={session.id}, carrier={carrier_name}")
            except Exception as e:
                logger.error(f"[{code}] Failed to create session: {str(e)}")
                return render(request, 'kiosk/checkin.html', {
                    'error': 'Unable to complete check-in. Please try again or see the office.'
                })

            # Send SMS (non-blocking - check-in succeeds even if SMS fails)
            sms_result = send_checkin_sms(phone, code)
            if not sms_result['success']:
                sms_warning = "SMS could not be sent. Please write down your code."
                logger.warning(f"[{code}] SMS failed but check-in succeeded: {sms_result['error']}")

            # Redirect to success page with SMS warning if needed
            return redirect('kiosk:checkin_success', code=code)

        except Exception as e:
            logger.error(f"Check-in failed unexpectedly: {str(e)}", exc_info=True)
            return render(request, 'kiosk/checkin.html', {
                'error': 'An error occurred. Please try again or see the office.'
            })

    return render(request, 'kiosk/checkin.html')


def checkin_success(request, code):
    """Check-in confirmation screen."""
    session = get_object_or_404(DriverSession, code=code)

    # Check if SMS was sent by looking at recent logs or just show the code prominently
    # The template always shows the code, so driver has it regardless of SMS status
    logger.info(f"[{code}] Showing check-in success screen")

    return render(request, 'kiosk/checkin_success.html', {'session': session})


def checkout_code(request):
    """Enter check-out code with detailed error messages."""
    error = None

    if request.method == 'POST':
        code = request.POST.get('code', '').strip().upper()
        # Remove dash if user included it, then reformat
        code_digits = code.replace('-', '')
        if len(code_digits) == 6:
            code = f"{code_digits[:4]}-{code_digits[4:]}"

        logger.info(f"Checkout code entered: {code}")

        try:
            session = DriverSession.objects.get(code=code)
            logger.info(f"[{code}] Session found: status={session.status}")

            if session.is_expired():
                error = "This code has expired. Please check in again at the kiosk."
                logger.info(f"[{code}] Checkout rejected: expired")
            elif session.status == 'completed':
                error = "This code has already been used for checkout."
                logger.info(f"[{code}] Checkout rejected: already completed")
            elif session.status == 'cancelled':
                error = "This check-in was cancelled. Please see the office."
                logger.info(f"[{code}] Checkout rejected: cancelled")
            elif session.status == 'waiting':
                error = "Your load is not ready yet. Please wait for a text message."
                logger.info(f"[{code}] Checkout rejected: still waiting")
            elif session.status in ('ready', 'assigned'):
                logger.info(f"[{code}] Checkout proceeding to review")
                return redirect('kiosk:checkout_review', code=code)
            else:
                error = "Unable to process. Please see the office."
                logger.warning(f"[{code}] Checkout rejected: unexpected status={session.status}")

        except DriverSession.DoesNotExist:
            error = "Code not recognized. Please check and try again."
            logger.info(f"Checkout code not found: {code}")

    return render(request, 'kiosk/checkout_code.html', {'error': error})


def checkout_review(request, code):
    """Review BOL before signing."""
    session = get_object_or_404(DriverSession, code=code)
    logger.info(f"[{code}] Checkout review screen")

    if session.status not in ('ready', 'assigned') or not session.bol_id:
        logger.warning(f"[{code}] Review redirect: status={session.status}, bol_id={session.bol_id}")
        return redirect('kiosk:checkout_code')

    # Get BOL details from host app
    try:
        from bol_system.kiosk_hooks import get_bol_detail
        bol = get_bol_detail(session.bol_id)
    except Exception as e:
        logger.error(f"[{code}] Failed to get BOL details: {str(e)}")
        bol = None

    return render(request, 'kiosk/checkout_review.html', {
        'session': session,
        'bol': bol,
    })


def checkout_sign(request, code):
    """Signature capture screen with error handling."""
    session = get_object_or_404(DriverSession, code=code)
    error = None

    if request.method == 'POST':
        signature_data = request.POST.get('signature', '')

        if not signature_data:
            error = "Please sign in the box above."
            logger.warning(f"[{code}] Signature submission empty")
        else:
            try:
                # Attach signature to BOL
                from bol_system.kiosk_hooks import attach_signature
                result = attach_signature(session.bol_id, signature_data, session.driver_name)

                if result.get('success'):
                    session.status = 'signed'
                    session.signed_at = timezone.now()
                    session.save()
                    logger.info(f"[{code}] Signature captured successfully")
                    return redirect('kiosk:checkout_complete', code=code)
                else:
                    error = "Could not save signature. Please try again."
                    logger.error(f"[{code}] Signature attach failed: {result.get('error', 'unknown')}")
            except Exception as e:
                error = "An error occurred. Please try again or see the office."
                logger.error(f"[{code}] Signature error: {str(e)}", exc_info=True)

    return render(request, 'kiosk/checkout_sign.html', {
        'session': session,
        'error': error,
    })


def checkout_complete(request, code):
    """Print BOL and show completion screen."""
    session = get_object_or_404(DriverSession, code=code)
    pdf_error = None

    # Mark as completed
    if session.status != 'completed':
        session.status = 'completed'
        session.completed_at = timezone.now()
        session.save()
        logger.info(f"[{code}] Checkout completed")

    # Get PDF URL for printing
    try:
        from bol_system.kiosk_hooks import get_bol_detail
        bol = get_bol_detail(session.bol_id)
        pdf_url = f'/kiosk/bol/{session.bol_id}/pdf/'
    except Exception as e:
        logger.error(f"[{code}] Failed to get BOL for print: {str(e)}")
        bol = None
        pdf_url = None
        pdf_error = "Could not load BOL. Please show this screen to the office."

    return render(request, 'kiosk/checkout_complete.html', {
        'session': session,
        'bol': bol,
        'pdf_url': pdf_url,
        'pdf_error': pdf_error,
    })


# === Office-Facing Views ===

def office_queue(request):
    """Office queue view - see all waiting/assigned/ready drivers."""
    try:
        expire_old_sessions()  # Clean up expired sessions
    except Exception as e:
        logger.error(f"Failed to expire old sessions: {str(e)}")

    waiting = DriverSession.objects.filter(status='waiting').order_by('-checked_in_at')
    assigned = DriverSession.objects.filter(status='assigned').order_by('-checked_in_at')
    ready = DriverSession.objects.filter(status='ready').order_by('-checked_in_at')
    completed_today = DriverSession.objects.filter(
        status='completed',
        completed_at__date=timezone.now().date()
    ).order_by('-completed_at')[:10]

    return render(request, 'kiosk/office/queue.html', {
        'waiting': waiting,
        'assigned': assigned,
        'ready': ready,
        'completed_today': completed_today,
    })


def office_assign(request, session_id):
    """Assign BOL to driver session (form view)."""
    session = get_object_or_404(DriverSession, id=session_id)
    return render(request, 'kiosk/office/assign.html', {'session': session})


@require_http_methods(["POST"])
def office_mark_ready(request, session_id):
    """Mark session as ready for pickup."""
    session = get_object_or_404(DriverSession, id=session_id)
    session.status = 'ready'
    session.save()
    logger.info(f"[{session.code}] Marked ready by office")
    return redirect('kiosk:office_queue')


@require_http_methods(["POST"])
def office_cancel(request, session_id):
    """Cancel a driver session."""
    session = get_object_or_404(DriverSession, id=session_id)
    session.status = 'cancelled'
    session.save()
    logger.info(f"[{session.code}] Cancelled by office")
    return redirect('kiosk:office_queue')


# === API Views ===

def api_bol_search(request):
    """Search BOLs for assignment (AJAX)."""
    query = request.GET.get('q', '')

    try:
        from bol_system.kiosk_hooks import search_bols
        results = search_bols(query, request=request)
        return JsonResponse({'results': results})
    except Exception as e:
        logger.error(f"BOL search failed: {str(e)}")
        return JsonResponse({'results': [], 'error': str(e)})


def api_waiting_drivers(request):
    """Get list of waiting drivers for BOL form dropdown."""
    from datetime import timedelta

    try:
        cutoff = timezone.now() - timedelta(hours=4)
        waiting = DriverSession.objects.filter(
            status='waiting',
            checked_in_at__gte=cutoff
        ).order_by('checked_in_at')

        results = [{
            'id': s.id,
            'code': s.code,
            'carrier_name': s.carrier_name,
            'truck_number': s.truck_number,
            'pickup_number': s.pickup_number,
            'label': f"{s.code} | {s.carrier_name} | Truck {s.truck_number} | {s.pickup_number}"
        } for s in waiting]

        return JsonResponse({'drivers': results})
    except Exception as e:
        logger.error(f"Waiting drivers API failed: {str(e)}")
        return JsonResponse({'drivers': [], 'error': str(e)})


@require_http_methods(["POST"])
def api_assign_bol(request, session_id):
    """Assign BOL to session (AJAX)."""
    try:
        session = get_object_or_404(DriverSession, id=session_id)

        bol_id = request.POST.get('bol_id')
        bol_number = request.POST.get('bol_number', '')

        session.bol_id = bol_id
        session.bol_number = bol_number
        session.status = 'assigned'
        session.assigned_at = timezone.now()
        session.assigned_by = request.user.username if request.user.is_authenticated else 'office'
        session.save()

        logger.info(f"[{session.code}] BOL {bol_number} assigned via API")
        return JsonResponse({'success': True})
    except Exception as e:
        logger.error(f"BOL assignment failed for session {session_id}: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})


# === PWA ===

def pwa_manifest(request):
    """Serve PWA manifest."""
    manifest = {
        "name": "CBRT Driver Kiosk",
        "short_name": "CBRT Kiosk",
        "start_url": "/kiosk/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#005500",
        "icons": [
            {
                "src": "/static/kiosk/icon-192.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "/static/kiosk/icon-512.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    }
    return JsonResponse(manifest)


def service_worker(request):
    """Serve service worker."""
    sw_content = """
self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('fetch', (event) => {
    event.respondWith(fetch(event.request));
});
"""
    return HttpResponse(sw_content, content_type='application/javascript')


# === PDF ===

def bol_pdf(request, bol_id):
    """Serve BOL PDF inline for printing."""
    from bol_system.kiosk_hooks import generate_pdf
    return generate_pdf(bol_id)
