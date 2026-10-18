import hashlib
import math
from pathlib import Path

import requests
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.core.cache import cache
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from requests.exceptions import RequestException
from twilio.twiml.messaging_response import MessagingResponse


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


@csrf_exempt
def sms_reply(request):
    if request.method == "POST":
        """Respond to incoming calls with a simple text message."""
        # Start our TwiML response
        resp = MessagingResponse()

        # Add a message
        resp.message(
            "Do Not Reply via SMS. Please visit the link given in previous message to send a reply"
        )

        return HttpResponse(str(resp))
    return redirect("home")
