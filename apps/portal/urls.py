from django.urls import path
from .views.auth import login_view, logout_view, me_view
from .views.dashboard import dashboard_view
from .views.calls import (
    calls_list_view, call_detail_view,
    recording_serve_view, bulk_delete_view, bulk_mark_view, calls_export_csv_view,
)
from .views.alerts import alerts_list_view, alert_detail_view, resend_alert_email_view
from .views.followups import (
    followups_list_view, followup_detail_view,
    followup_claim_view, followup_add_note_view,
)
from .views.reports import reports_view
from .views.settings_view import notification_preferences_view, site_config_view
from .views.realtime import realtime_summary_view
from .views.export_view import export_call_view, delete_call_view, delete_all_calls_view
from .views.knowledge import (
    knowledge_list_view, knowledge_upload_view,
    knowledge_delete_view, knowledge_resync_view,
)
from .views.prompts import (
    prompts_list_view, prompt_detail_view,
    prompt_regenerate_view, prompt_upload_audio_view, prompt_audio_serve_view,
)

urlpatterns = [
    # Auth
    path('auth/login/',  login_view,  name='portal_login'),
    path('auth/logout/', logout_view, name='portal_logout'),
    path('auth/me/',     me_view,     name='portal_me'),

    # Dashboard
    path('dashboard/', dashboard_view, name='portal_dashboard'),

    # Real-time polling
    path('realtime/', realtime_summary_view, name='portal_realtime'),

    # Calls
    path('calls/',                                          calls_list_view,       name='portal_calls_list'),
    path('calls/delete-all/',                               delete_all_calls_view, name='portal_calls_delete_all'),
    path('calls/bulk-delete/',                              bulk_delete_view,      name='portal_calls_bulk_delete'),
    path('calls/bulk-mark/',                                bulk_mark_view,        name='portal_calls_bulk_mark'),
    path('calls/export-csv/',                               calls_export_csv_view, name='portal_calls_export_csv'),
    path('calls/<uuid:pk>/',                                call_detail_view,      name='portal_call_detail'),
    path('calls/<uuid:pk>/export/',                         export_call_view,      name='portal_call_export'),
    path('calls/<uuid:pk>/delete/',                         delete_call_view,      name='portal_call_delete'),
    path('calls/<uuid:pk>/recording/<uuid:turn_id>/',       recording_serve_view,  name='portal_call_recording'),

    # Alerts
    path('alerts/',                          alerts_list_view,        name='portal_alerts_list'),
    path('alerts/<uuid:pk>/',                alert_detail_view,       name='portal_alert_detail'),
    path('alerts/<uuid:pk>/resend-email/',   resend_alert_email_view, name='portal_alert_resend'),

    # Follow-ups
    path('followups/',                      followups_list_view,     name='portal_followups_list'),
    path('followups/<uuid:pk>/',            followup_detail_view,    name='portal_followup_detail'),
    path('followups/<uuid:pk>/claim/',      followup_claim_view,     name='portal_followup_claim'),
    path('followups/<uuid:pk>/add-note/',   followup_add_note_view,  name='portal_followup_note'),

    # Knowledge base (RAG)
    path('knowledge/',                     knowledge_list_view,   name='portal_knowledge_list'),
    path('knowledge/upload/',              knowledge_upload_view, name='portal_knowledge_upload'),
    path('knowledge/<uuid:pk>/delete/',    knowledge_delete_view, name='portal_knowledge_delete'),
    path('knowledge/<uuid:pk>/resync/',    knowledge_resync_view, name='portal_knowledge_resync'),

    # Call prompts
    path('prompts/',                              prompts_list_view,       name='portal_prompts_list'),
    path('prompts/<str:stem>/',                   prompt_detail_view,      name='portal_prompt_detail'),
    path('prompts/<str:stem>/regenerate/',        prompt_regenerate_view,  name='portal_prompt_regen'),
    path('prompts/<str:stem>/upload-audio/',      prompt_upload_audio_view,  name='portal_prompt_audio'),
    path('prompts/<str:stem>/audio/',             prompt_audio_serve_view,   name='portal_prompt_audio_serve'),

    # Reports
    path('reports/', reports_view, name='portal_reports'),

    # Settings
    path('settings/notifications/', notification_preferences_view, name='portal_notif_prefs'),
    path('settings/site-config/',   site_config_view,              name='portal_site_config'),
]
