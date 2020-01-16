from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from twilio.twiml.messaging_response import Message, MessagingResponse

def home(request):
    return render(request, 'home.html')

def mapview(request):
    if request.GET.get('lon', None) and request.GET.get('lat', None):
        return render(request, 'mapview.html', 
        {'lat': request.GET.get('lat', None), 'lon': request.GET.get('lon', None)})
    return redirect('home')

@csrf_exempt
def sms_reply(request):
    if request.method == 'POST':
        """Respond to incoming calls with a simple text message."""
        # Start our TwiML response
        resp = MessagingResponse()

        # Add a message
        message = resp.message("Do Not Reply via SMS. Please visit the link given in previous message to send a reply")

        return HttpResponse(str(message))
    return redirect('home')
