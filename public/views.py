from pathlib import Path

from django.contrib.staticfiles import finders
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
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


def mapview(request):
    if request.GET.get("lon", None) and request.GET.get("lat", None):
        return render(
            request,
            "mapview.html",
            {"lat": request.GET.get("lat", None), "lon": request.GET.get("lon", None)},
        )
    return redirect("home")


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
