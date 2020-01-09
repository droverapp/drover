from django.db import models

class ShortURL(models.Model):
    shortened_id = models.CharField(unique=True, editable=False, max_length=8)
    path = models.CharField(editable=False, max_length=100)
