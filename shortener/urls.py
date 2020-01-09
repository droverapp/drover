from django.urls import path
from . import views

urlpatterns = [
    path('<short_path>', views.shortener_resolver, name='shortener_resolver'),
]
