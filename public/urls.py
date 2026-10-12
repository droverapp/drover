from django.urls import path
from . import views

urlpatterns = [
    path("service-worker.js", views.service_worker, name="service_worker"),
    path("", views.home, name="home"),
    path("mapview/", views.mapview, name="mapview"),
    path("sms-reply/", views.sms_reply, name="sms_reply"),
]
