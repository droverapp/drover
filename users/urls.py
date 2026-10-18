from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views
from .forms import EmailOrUsernamePasswordResetForm

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            form_class=EmailOrUsernamePasswordResetForm,
            template_name="password_reset_form.html",
            email_template_name="password_reset_email.html",
            subject_template_name="password_reset_subject.txt",
            success_url=reverse_lazy("password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="password_reset_confirm.html",
            success_url=reverse_lazy("password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
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
