import json
import logging
from urllib.parse import urlsplit

from django.conf import settings
from pywebpush import WebPushException, webpush
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)

_ALLOWED_PUSH_HOSTS = {"fcm.googleapis.com", "web.push.apple.com"}
_PUSH_TIMEOUT_SECONDS = 5
_PUSH_TTL_SECONDS = 3600


def is_allowed_push_endpoint(endpoint):
    if not isinstance(endpoint, str) or len(endpoint) > 4096:
        return False

    try:
        parsed = urlsplit(endpoint)
        port = parsed.port
    except ValueError:
        return False

    return (
        parsed.scheme == "https"
        and parsed.hostname in _ALLOWED_PUSH_HOSTS
        and port in (None, 443)
        and parsed.username is None
        and parsed.password is None
        and parsed.path.startswith("/")
    )


def send_web_push_to_user(user, payload):
    if not settings.WEBPUSH_VAPID_PUBLIC_KEY or not settings.WEBPUSH_VAPID_PRIVATE_KEY:
        return

    for subscription in user.web_push_subscriptions.all():
        if not is_allowed_push_endpoint(subscription.endpoint):
            logger.warning(
                "Skipping Web Push subscription %s with an unsupported endpoint",
                subscription.pk,
            )
            continue

        try:
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {
                        "p256dh": subscription.p256dh,
                        "auth": subscription.auth,
                    },
                },
                data=json.dumps(payload),
                vapid_private_key=settings.WEBPUSH_VAPID_PRIVATE_KEY,
                vapid_claims={"sub": settings.WEBPUSH_VAPID_SUBJECT},
                timeout=_PUSH_TIMEOUT_SECONDS,
                ttl=_PUSH_TTL_SECONDS,
            )
        except WebPushException as error:
            if error.status_code in (404, 410):
                subscription.delete()
            else:
                logger.warning(
                    "Web Push failed for subscription %s (HTTP %s)",
                    subscription.pk,
                    error.status_code,
                )
        except RequestException:
            logger.warning(
                "Web Push request failed for subscription %s", subscription.pk
            )
