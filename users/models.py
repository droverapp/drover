from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    contact_number = models.CharField(max_length=20)
    name = models.CharField(max_length=255, blank=True, null=True)
