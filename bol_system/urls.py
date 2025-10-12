from django.urls import path
from . import views
from . import auth_views

urlpatterns = [
    path('products/', views.ProductListView.as_view(), name='products'),
    path('customers/', views.CustomerListView.as_view(), name='customers'),
    path('carriers/', views.carrier_list, name='carriers'),
    path('bol/preview/', views.preview_bol, name='preview_bol'),
    path('bol/confirm/', views.confirm_bol, name='confirm_bol'),
    path('bol/', views.confirm_bol, name='create_bol'),  # Backward compatibility
    path('bol/<int:bol_id>/', views.bol_detail, name='bol_detail'),
    path('balances/', views.balances, name='balances'),
    path('history/', views.bol_history, name='history'),
    path('auth/me/', auth_views.current_user, name='current_user'),
]