from django.shortcuts import redirect, get_object_or_404
from .models import ShortURL


def shortener_resolver(request, short_path):
    short_url = get_object_or_404(ShortURL, shortened_id=short_path)
    return redirect(short_url.path)
