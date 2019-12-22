from twilio.rest import Client
from django.conf import settings

def send_text_message(to_number, message):
    print(to_number)
    client = Client(settings.TWILIO_SSID, settings.TWILIO_AUTH_TOKEN)
    message = client.messages.create(
        to=to_number,
        from_=settings.FROM_NUMBER,
        body=message
    )
    print(message.__dict__)
    print(message.status)