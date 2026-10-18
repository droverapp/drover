import hashlib
import math
from pathlib import Path

import requests
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.core.cache import cache
from django.db.models import Q
from django.http import Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from requests.exceptions import RequestException
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse

from groups.models import GroupMember, GroupMessage
from groups.sms import send_text_message
from shortener.utils import generate_short_url
from users.models import User
from users.push import send_web_push_to_user


def service_worker(request):
    service_worker_path = finders.find("service-worker.js")
    if not service_worker_path:
        raise Http404

    return HttpResponse(
        Path(service_worker_path).read_bytes(),
        content_type="application/javascript",
        headers={"Cache-Control": "no-cache"},
    )


def home(request):
    return render(request, "home.html")


def _parse_coordinate(raw_value, minimum, maximum):
    if raw_value in (None, ""):
        return None
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or not (minimum <= value <= maximum):
        return None
    return value


def mapview(request):
    lat = _parse_coordinate(request.GET.get("lat"), -90.0, 90.0)
    lon = _parse_coordinate(request.GET.get("lon"), -180.0, 180.0)
    if lat is not None and lon is not None:
        return render(
            request,
            "mapview.html",
            {"lat": lat, "lon": lon},
        )
    return redirect("home")


@login_required
def location_search(request):
    query = request.GET.get("q", "").strip()
    if len(query) < 3 or len(query) > 200:
        return JsonResponse([], safe=False)

    try:
        limit = max(1, min(int(request.GET.get("limit", 5)), 10))
    except (TypeError, ValueError):
        limit = 5

    normalized = f"{query.casefold()}:{limit}"
    cache_key = f"osm:search:{hashlib.sha256(normalized.encode('utf-8')).hexdigest()}"
    cached_results = cache.get(cache_key)
    if cached_results is not None:
        return JsonResponse(cached_results, safe=False)

    if not cache.add("osm:nominatim:rate_lock", 1, timeout=1):
        return JsonResponse([], safe=False)

    try:
        response = requests.get(
            settings.OSM_SEARCH_URL,
            params={"q": query, "format": "json", "limit": limit},
            headers={"User-Agent": settings.OSM_USER_AGENT},
            timeout=5,
        )
        response.raise_for_status()
        payload = response.json()
    except (RequestException, ValueError):
        return JsonResponse([], safe=False)

    results = []
    if isinstance(payload, list):
        for item in payload[:limit]:
            if not isinstance(item, dict):
                continue
            lat = _parse_coordinate(item.get("lat"), -90.0, 90.0)
            lon = _parse_coordinate(item.get("lon"), -180.0, 180.0)
            display_name = item.get("display_name")
            if (
                lat is None
                or lon is None
                or not isinstance(display_name, str)
                or not display_name
            ):
                continue
            licence = item.get("licence")
            results.append(
                {
                    "display_name": display_name,
                    "lat": f"{lat:.6f}",
                    "lon": f"{lon:.6f}",
                    "licence": licence if isinstance(licence, str) else "",
                }
            )

    cache.set(cache_key, results, timeout=3600)
    return JsonResponse(results, safe=False)


def _verify_twilio_signature(request):
    auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", "")
    if not auth_token:
        return True
    signature = request.headers.get("X-Twilio-Signature", "")
    if not signature:
        return False
    validator = RequestValidator(auth_token)
    return validator.validate(
        request.build_absolute_uri(), request.POST.dict(), signature
    )


def _find_reply_target_for_sms(sender_user):
    memberships = list(
        GroupMember.objects.filter(user=sender_user, is_deleted=False).select_related(
            "group"
        )
    )
    if not memberships:
        return None, None, None

    membership_by_group_id = {m.group_id: m for m in memberships}
    all_group_ids = list(membership_by_group_id.keys())
    admin_group_ids = [m.group_id for m in memberships if m.is_admin]

    visibility_q = Q(group_id__in=all_group_ids, receiver=sender_user) | Q(
        group_id__in=all_group_ids, message_type="AM", receiver__isnull=True
    )
    if admin_group_ids:
        visibility_q |= Q(group_id__in=admin_group_ids, message_type="MA")

    candidates = (
        GroupMessage.objects.filter(visibility_q)
        .exclude(sender=sender_user)
        .select_related("group", "sender", "reply_to", "reply_to__sender")
        .order_by("-message_time", "-created_at")
    )
    for candidate in candidates:
        root_message = candidate.reply_to or candidate
        recipient = candidate.sender or root_message.sender
        if recipient is None or recipient.id == sender_user.id:
            continue
        if not GroupMember.objects.filter(
            group_id=candidate.group_id, user=recipient, is_deleted=False
        ).exists():
            continue
        return (
            root_message,
            recipient,
            membership_by_group_id[candidate.group_id],
        )
    return None, None, None


@csrf_exempt
def sms_reply(request):
    if request.method == "POST":
        if not _verify_twilio_signature(request):
            return HttpResponseForbidden("Invalid Twilio signature")

        resp = MessagingResponse()
        from_number = request.POST.get("From", "").strip()
        body = request.POST.get("Body", "").strip()
        sender_user = (
            User.objects.filter(contact_number=from_number, is_active=True).first()
            if from_number and body
            else None
        )
        if sender_user:
            root_message, reply_recipient, membership = _find_reply_target_for_sms(
                sender_user
            )
            if root_message and reply_recipient and membership:
                reply = GroupMessage.objects.create(
                    message=body,
                    sender=sender_user,
                    receiver=reply_recipient,
                    reply_to=root_message,
                    group=root_message.group,
                    message_time=timezone.now(),
                    message_type="AM" if membership.is_admin else "MA",
                )
                conversation_path = reverse(
                    "conversation_details",
                    kwargs={
                        "group_id": root_message.group_id,
                        "message_id": root_message.id,
                    },
                )
                if reply_recipient.contact_number:
                    reply_detail_path = reverse(
                        "conversation_details",
                        kwargs={
                            "group_id": root_message.group_id,
                            "message_id": reply.id,
                        },
                    )
                    message_url = f"{request.scheme}://{request.get_host()}{generate_short_url(reply_detail_path)}"
                    send_text_message(reply_recipient.contact_number, body, message_url)
                send_web_push_to_user(
                    reply_recipient,
                    {
                        "title": "New Drover message",
                        "body": "You have a new reply in Drover.",
                        "url": conversation_path,
                    },
                )
                resp.message(f"Your reply has been sent to {root_message.group.name}.")
                return HttpResponse(str(resp), content_type="text/xml")

        resp.message(
            "Do Not Reply via SMS. Please visit the link given in previous message to send a reply"
        )
        return HttpResponse(str(resp), content_type="text/xml")
    return redirect("home")
