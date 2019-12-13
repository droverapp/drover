
from django.core.mail import send_mail

def send_invitation_email(group_name, from_email, to_email, invite_link=None):
    if invite_link:
        subject = 'Invitation to Drover: {}'.format(group_name)
        message = 'Invitation URL: {}'.format(invite_link)
        send_mail(
            subject,
            message,
            from_email,
            to_email,
            fail_silently=False
        )
    else:
        subject = 'Drover: You have been added to the group {}'.format(group_name)
        message = 'Welcome to group {}'.format(group_name)
        send_mail(
            subject,
            message,
            from_email,
            to_email,
            fail_silently=False
        )
