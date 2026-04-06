from django.urls import path
from . import views

urlpatterns = [
    # Legacy single-turn
    path('call/',                        views.receive_call,  name='receive_call'),
    path('call-status/<str:call_id>/',   views.call_status,   name='call_status'),

    # Knowledge test
    path('ask/',                         views.ask_question,  name='ask_question'),

    # Multi-turn session
    path('session/start/',                          views.session_start, name='session_start'),
    path('session/<str:session_id>/end/',           views.session_end,   name='session_end'),
    path('session/<str:session_id>/turn/',          views.submit_turn,   name='submit_turn'),
    path('turn-status/<str:turn_id>/',              views.turn_status,   name='turn_status'),

    # Health
    path('health/',                                 views.health,        name='health'),
]
