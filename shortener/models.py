import uuid
from django.db import models
from django.utils import timezone


class ShortURL(models.Model):
    """
    Model to store shortened URLs.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shortened_id = models.CharField(unique=True, editable=False, max_length=8)
    path = models.CharField(editable=False, max_length=200)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    redirect_count = models.PositiveIntegerField(default=0)
    
    def __str__(self):
        return f"{self.shortened_id} -> {self.path}"
    
    def is_expired(self):
        if self.expires_at is None:
            return False
        return self.expires_at <= timezone.now()
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['shortened_id']),
            models.Index(fields=['created_at']),
        ]