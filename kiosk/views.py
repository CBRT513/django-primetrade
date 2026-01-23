from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from .models import DriverSession
from .services import generate_session_code, send_checkin_sms, expire_old_sessions


# === Driver-Facing Views (iPad) ===

def home(request):
    """Kiosk home screen with Check-In / Check-Out buttons."""
    return render(request, 'kiosk/home.html')


def checkin(request):
    """Driver check-in form."""
    if request.method == 'POST':
        code = generate_session_code()

        session = DriverSession.objects.create(
            code=code,
            driver_name=request.POST.get('driver_name', '').strip(),
            phone=request.POST.get('phone', '').strip(),
            truck_number=request.POST.get('truck_number', '').strip(),
            visit_type=request.POST.get('visit_type', 'pickup'),
            notes=request.POST.get('notes', '').strip(),
        )

        # Send SMS with code
        send_checkin_sms(session.phone, code)

        return redirect('kiosk:checkin_success', code=code)

    return render(request, 'kiosk/checkin.html')


def checkin_success(request, code):
    """Check-in confirmation screen."""
    session = get_object_or_404(DriverSession, code=code)
    return render(request, 'kiosk/checkin_success.html', {'session': session})


def checkout_code(request):
    """Enter check-out code."""
    error = None

    if request.method == 'POST':
        code = request.POST.get('code', '').strip().upper()

        try:
            session = DriverSession.objects.get(code=code)

            if session.is_expired():
                error = "This code has expired. Please see the office."
            elif session.status == 'completed':
                error = "This code has already been used."
            elif session.status not in ('ready', 'assigned'):
                error = "Your load is not ready yet. Please see the office."
            else:
                return redirect('kiosk:checkout_review', code=code)

        except DriverSession.DoesNotExist:
            error = "Code not found. Please check and try again, or see the office."

    return render(request, 'kiosk/checkout_code.html', {'error': error})


def checkout_review(request, code):
    """Review BOL before signing."""
    session = get_object_or_404(DriverSession, code=code)

    if session.status not in ('ready', 'assigned') or not session.bol_id:
        return redirect('kiosk:checkout_code')

    # Get BOL details from host app
    from bol_system.kiosk_hooks import get_bol_detail
    bol = get_bol_detail(session.bol_id)

    return render(request, 'kiosk/checkout_review.html', {
        'session': session,
        'bol': bol,
    })


def checkout_sign(request, code):
    """Signature capture screen."""
    session = get_object_or_404(DriverSession, code=code)

    if request.method == 'POST':
        signature_data = request.POST.get('signature', '')

        if signature_data:
            # Attach signature to BOL
            from bol_system.kiosk_hooks import attach_signature
            result = attach_signature(session.bol_id, signature_data, session.driver_name)

            if result.get('success'):
                session.status = 'signed'
                session.signed_at = timezone.now()
                session.save()
                return redirect('kiosk:checkout_complete', code=code)

    return render(request, 'kiosk/checkout_sign.html', {'session': session})


def checkout_complete(request, code):
    """Print BOL and show completion screen."""
    session = get_object_or_404(DriverSession, code=code)

    # Mark as completed
    if session.status != 'completed':
        session.status = 'completed'
        session.completed_at = timezone.now()
        session.save()

    # Get PDF URL for printing
    from bol_system.kiosk_hooks import get_bol_detail
    bol = get_bol_detail(session.bol_id)

    return render(request, 'kiosk/checkout_complete.html', {
        'session': session,
        'bol': bol,
        'pdf_url': f'/bol/{session.bol_id}/pdf/',
    })


# === Office-Facing Views ===

def office_queue(request):
    """Office queue view - see all waiting/assigned/ready drivers."""
    expire_old_sessions()  # Clean up expired sessions

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
    return redirect('kiosk:office_queue')


@require_http_methods(["POST"])
def office_cancel(request, session_id):
    """Cancel a driver session."""
    session = get_object_or_404(DriverSession, id=session_id)
    session.status = 'cancelled'
    session.save()
    return redirect('kiosk:office_queue')


# === API Views ===

def api_bol_search(request):
    """Search BOLs for assignment (AJAX)."""
    query = request.GET.get('q', '')

    from bol_system.kiosk_hooks import search_bols
    results = search_bols(query, request=request)

    return JsonResponse({'results': results})


@require_http_methods(["POST"])
def api_assign_bol(request, session_id):
    """Assign BOL to session (AJAX)."""
    session = get_object_or_404(DriverSession, id=session_id)

    bol_id = request.POST.get('bol_id')
    bol_number = request.POST.get('bol_number', '')

    session.bol_id = bol_id
    session.bol_number = bol_number
    session.status = 'assigned'
    session.assigned_at = timezone.now()
    session.assigned_by = request.user.username if request.user.is_authenticated else 'office'
    session.save()

    return JsonResponse({'success': True})


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
