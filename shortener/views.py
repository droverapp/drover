from django.shortcuts import render

from .models import ShortURL
from django.shortcuts import redirect


def shortener_resolver(request, short_path):
    path = ShortURL.objects.filter(shortened_id=short_path).first().path
    return redirect(path)
