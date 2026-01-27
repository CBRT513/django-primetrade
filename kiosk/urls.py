from django.urls import path
from . import views

app_name = 'kiosk'

urlpatterns = [
    # Driver-facing (iPad)
    path('', views.home, name='home'),
    path('set-language/', views.set_language, name='set_language'),
    path('menu/', views.menu, name='menu'),
    path('checkin/', views.checkin, name='checkin'),
    path('checkin/success/<str:code>/', views.checkin_success, name='checkin_success'),
    path('checkout/', views.checkout_code, name='checkout_code'),
    path('checkout/<str:code>/', views.checkout_review, name='checkout_review'),
    path('checkout/<str:code>/sign/', views.checkout_sign, name='checkout_sign'),
    path('checkout/<str:code>/complete/', views.checkout_complete, name='checkout_complete'),
    path('bol/<int:bol_id>/pdf/', views.bol_pdf, name='bol_pdf'),

    # Office-facing (desktop)
    path('office/', views.office_queue, name='office_queue'),
    path('office/session/<int:session_id>/assign/', views.office_assign, name='office_assign'),
    path('office/session/<int:session_id>/ready/', views.office_mark_ready, name='office_mark_ready'),
    path('office/session/<int:session_id>/cancel/', views.office_cancel, name='office_cancel'),

    # API
    path('api/bol-search/', views.api_bol_search, name='api_bol_search'),
    path('api/session/<int:session_id>/assign/', views.api_assign_bol, name='api_assign_bol'),
    path('api/waiting-drivers/', views.api_waiting_drivers, name='api_waiting_drivers'),

    # PWA
    path('manifest.json', views.pwa_manifest, name='pwa_manifest'),
    path('sw.js', views.service_worker, name='service_worker'),
]
