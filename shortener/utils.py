import secrets

from django.urls import reverse
from .models import ShortURL


def generate_short_url(path):
    short_url_path = ShortURL.objects.filter(path=path).first()
    if short_url_path:
        return reverse(
            "shortener_resolver", kwargs={"short_path": short_url_path.shortened_id}
        )

    short_url_hash = secrets.token_urlsafe(6)
    while ShortURL.objects.filter(shortened_id=short_url_hash).first():
        short_url_hash = secrets.token_urlsafe(6)
    short_url_path = ShortURL(shortened_id=short_url_hash, path=path)
    short_url_path.save()
    return reverse(
        "shortener_resolver", kwargs={"short_path": short_url_path.shortened_id}
    )
