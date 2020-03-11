import uuid
from django.db import models
from django.conf import settings
from datetime import datetime

class Group(models.Model):
    group_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    event_date = models.DateTimeField(blank=True, null=True)
    venue = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

    def get_invite_url(self):
        from django.urls import reverse
        from shortener.utils import generate_short_url
        return generate_short_url(reverse('invite', args=[self.group_id]))


class GroupMember(models.Model):
    member_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    is_admin = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)


class GroupSchedule(models.Model):
    name = models.CharField(max_length=255)
    schedule_time = models.DateTimeField()
    instructions = models.TextField(blank=True)
    venue_name = models.CharField(max_length=255, null=True, blank=True)
    venue_address=models.TextField(blank=True)
    venue_map_link = models.CharField(max_length=255)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)


class GroupMessage(models.Model):
    STATUSES = [
        ('P', 'Pending'),
        ('S', 'Successfully Sent'),
        ('F', 'Sending Failed'),
    ]
    TYPES = [
        ('AM', 'Admin to Members'),
        ('MA', 'Member to Admin'),
    ]
    message_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    message = models.TextField()
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='message_sent', on_delete=models.CASCADE)
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='message_received', on_delete=models.CASCADE, blank=True, null=True)
    reply_to = models.UUIDField(blank=True, null=True)
    message_time = models.DateTimeField(default=datetime.now, blank=True, null=True)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    status = models.CharField(max_length=1, choices=STATUSES, default='P')
    message_type = models.CharField(max_length=2, choices=TYPES, default='AM')
