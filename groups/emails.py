
from django.core.mail import send_mail

#This isn't going to work right now, need to finish adding format strings
def send_invitation_email(group_name, from_email, to_email, invite_link=None):
    if invite_link:
        subject = f"You've been invited to join a group on Drover!: {group_name}"
        message = f"Hi there! You've been invited to join the group {group_name} on Drover, the new way to get everyone together! Invitation URL: {invite_link}"
        send_mail(
            subject,
            message,
            from_email,
            to_email,
            fail_silently=False
        )
    else:
        subject = f'Drover: You have been added to the group {group_name}'
        message = f'Welcome to group {group_name}'
        send_mail(
            subject,
            message,
            from_email,
            to_email,
            fail_silently=False
        )
