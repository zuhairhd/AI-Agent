from django.urls import path
from .views.auth import login_view, logout_view, me_view
from .views.dashboard import dashboard_view
from .views.calls import calls_list_view, call_detail_view
from .views.alerts import alerts_list_view, alert_detail_view, resend_alert_email_view
from .views.followups import followups_list_view, followup_detail_view
from .views.reports import reports_view
from .views.settings_view import notification_preferences_view

urlpatterns = [
    # Auth
    path('auth/login/',  login_view,  name='portal_login'),
    path('auth/logout/', logout_view, name='portal_logout'),
    path('auth/me/',     me_view,     name='portal_me'),

    # Dashboard
    path('dashboard/', dashboard_view, name='portal_dashboard'),

    # Calls
    path('calls/',       calls_list_view,   name='portal_calls_list'),
    path('calls/<uuid:pk>/', call_detail_view, name='portal_call_detail'),

    # Alerts
    path('alerts/',                          alerts_list_view,        name='portal_alerts_list'),
    path('alerts/<uuid:pk>/',                alert_detail_view,       name='portal_alert_detail'),
    path('alerts/<uuid:pk>/resend-email/',   resend_alert_email_view, name='portal_alert_resend'),

    # Follow-ups
    path('followups/',           followups_list_view,   name='portal_followups_list'),
    path('followups/<uuid:pk>/', followup_detail_view,  name='portal_followup_detail'),

    # Reports
    path('reports/', reports_view, name='portal_reports'),

    # Settings
    path('settings/notifications/', notification_preferences_view, name='portal_notif_prefs'),
]
