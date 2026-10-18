import json

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from groups.models import GroupMember

from .forms import SignUpForm
from .models import WebPushSubscription
from .push import is_allowed_push_endpoint


def _safe_next_redirect(request):
    next_url = request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect("dashboard")


def signup(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get("username")
            raw_password = form.cleaned_data.get("password1")
            user = authenticate(username=username, password=raw_password)
            login(request, user)
            return _safe_next_redirect(request)
    else:
        form = SignUpForm()
    return render(request, "signup.html", {"form": form})


def login_view(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]

        user = authenticate(username=username, password=password)
        if user is not None and user.is_active:
            login(request, user)
            return _safe_next_redirect(request)
    return render(request, "login.html", {"next": request.GET.get("next", None)})


def logout_view(request):
    logout(request)
    return redirect("home")


@login_required
@ensure_csrf_cookie
def dashboard(request):
    owned_groups = (
        GroupMember.objects.select_related("group")
        .filter(Q(group__owner=request.user) | Q(user=request.user))
        .filter(is_deleted=False, is_admin=True)
    )
    member_groups = (
        GroupMember.objects.select_related("group")
        .filter(user=request.user, is_deleted=False)
        .exclude(group__owner=request.user)
        .exclude(is_admin=True)
    )
    return render(
        request,
        "dashboard.html",
        {
            "owned_groups": owned_groups,
            "member_groups": member_groups,
            "webpush_enabled": bool(
                settings.WEBPUSH_VAPID_PUBLIC_KEY and settings.WEBPUSH_VAPID_PRIVATE_KEY
            ),
            "webpush_public_key": settings.WEBPUSH_VAPID_PUBLIC_KEY,
        },
    )


def _json_request_payload(request):
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


@login_required
@require_POST
def register_webpush_subscription(request):
    if not settings.WEBPUSH_VAPID_PUBLIC_KEY or not settings.WEBPUSH_VAPID_PRIVATE_KEY:
        return JsonResponse({"error": "Web Push is not configured"}, status=503)

    payload = _json_request_payload(request)
    keys = payload.get("keys") if payload else None
    endpoint = payload.get("endpoint") if payload else None
    p256dh = keys.get("p256dh") if isinstance(keys, dict) else None
    auth = keys.get("auth") if isinstance(keys, dict) else None
    if (
        not is_allowed_push_endpoint(endpoint)
        or not isinstance(p256dh, str)
        or not p256dh
        or not isinstance(auth, str)
        or not auth
    ):
        return JsonResponse({"error": "Invalid subscription"}, status=400)

    _subscription, created = WebPushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={"user": request.user, "p256dh": p256dh, "auth": auth},
    )
    return JsonResponse({"subscribed": True}, status=201 if created else 200)


@login_required
@require_POST
def revoke_webpush_subscription(request):
    payload = _json_request_payload(request)
    endpoint = payload.get("endpoint") if payload else None
    if not isinstance(endpoint, str) or not endpoint:
        return JsonResponse({"error": "Invalid subscription"}, status=400)

    WebPushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
    return HttpResponse(status=204)
