from django.urls import path
from . import views

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path(
        "push-subscriptions/",
        views.register_webpush_subscription,
        name="register_webpush_subscription",
    ),
    path(
        "push-subscriptions/revoke/",
        views.revoke_webpush_subscription,
        name="revoke_webpush_subscription",
    ),
]
