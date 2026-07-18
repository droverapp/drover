from twilio.rest import Client
from django.conf import settings


def send_text_message(to_number, message, message_url):
    if getattr(settings, 'TWILIO_API_KEY', None) and getattr(settings, 'TWILIO_API_SECRET', None):
        client = Client(settings.TWILIO_API_KEY, settings.TWILIO_API_SECRET, settings.TWILIO_ACCOUNT_SID)
    else:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    message_body = "{}.\n Please visit {} to reply.".format(message, message_url)
    message_request = client.messages.create(
        to=to_number, from_=settings.FROM_NUMBER, body=message_body
    )
    print(message_request.__dict__)
    print(message_request.status)
