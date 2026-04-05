from django.urls import path
from . import views

urlpatterns = [
    path('call/', views.receive_call, name='receive_call'),
    path('ask/',  views.ask_question,  name='ask_question'),
]
