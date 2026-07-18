import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from ckeditor.fields import RichTextField


class Group(models.Model):
    """
    Represents a group in the application.
    """
    # Note: We're changing from IntegerField to UUIDField as primary key
    # This requires data migration
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    venue = models.CharField(max_length=255, blank=True, null=True)
    description = RichTextField(blank=True)
    image = models.ImageField(upload_to="images/", null=True, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='owned_groups'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def get_invite_url(self):
        from django.urls import reverse
        from shortener.utils import generate_short_url

        return generate_short_url(reverse("invite", args=[self.id]))

    class Meta:
        ordering = ['-created_at']


class GroupMember(models.Model):
    """
    Represents a member of a group.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='group_memberships'
    )
    group = models.ForeignKey(
        Group, 
        on_delete=models.CASCADE,
        related_name='members'
    )
    owner = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.group.name}"

    class Meta:
        unique_together = ['user', 'group']
        ordering = ['user__first_name']


class GroupEvent(models.Model):
    """
    Represents an event for groups.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(
        Group, 
        on_delete=models.CASCADE,
        related_name='events'
    )
    name = models.CharField(max_length=120)
    event_time = models.DateTimeField(blank=True, null=True)
    instructions = models.TextField(blank=True, null=True)
    venue_name = models.CharField(max_length=255, blank=True, null=True)
    venue_address = models.TextField(blank=True, null=True)
    venue_map_link = models.CharField(max_length=255, blank=True, null=True)
    # rsvp_open = models.DateTimeField(blank=True, null=True)
    # rsvp_close = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-event_time']
        # ordering = ['-rsvp_open']


class GroupMessage(models.Model):
    """
    Represents a message sent within a group.
    """
    STATUS_CHOICES = [
        ("P", "Pending"),
        ("S", "Successfully Sent"),
        ("F", "Sending Failed"),
    ]
    
    TYPE_CHOICES = [
        ("AM", "Admin to Members"),
        ("MA", "Member to Admin"),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message_type = models.CharField(choices=TYPE_CHOICES, max_length=2)
    group = models.ForeignKey(
        Group, 
        on_delete=models.CASCADE,
        related_name='messages'
    )
    subject = models.CharField(max_length=120, default='No Subject')
    message = RichTextField(default='')
    status = models.CharField(choices=STATUS_CHOICES, max_length=1, default="P")
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='messages_sent',
        null=True,
        blank=True
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='messages_received',
        null=True,
        blank=True
    )
    reply_to = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        related_name='replies',
        null=True,
        blank=True
    )
    message_time = models.DateTimeField(default=timezone.now)
    send_date = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.subject

    class Meta:
        ordering = ['-message_time']


class GroupMessageImage(models.Model):
    """
    Represents an image attached to a group message.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group_message = models.ForeignKey(
        GroupMessage, 
        on_delete=models.CASCADE,
        related_name='message_images',
        default=None,
        null=True
    )
    image = models.ImageField(upload_to="message_images/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.group_message.subject}"

    class Meta:
        ordering = ['-created_at']


class GroupInvite(models.Model):
    """
    Represents an invitation to join a group.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(
        Group, 
        on_delete=models.CASCADE,
        related_name='invites'
    )
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField()
    phone = models.CharField(max_length=17, null=True, blank=True)
    invite_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expired = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.group.name}"

    class Meta:
        ordering = ['-created_at']