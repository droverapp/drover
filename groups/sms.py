from twilio.rest import Client
from django.conf import settings

def send_text_message(to_number, message, message_url):
    client = Client(settings.TWILIO_SSID, settings.TWILIO_AUTH_TOKEN)
    message_body = '{}.\n Please visit {} to reply.'.format(message, message_url)
    message_request = client.messages.create(
        to=to_number,
        from_=settings.FROM_NUMBER,
        body=message_body
    )
    print(message_request.__dict__)
    print(message_request.status)