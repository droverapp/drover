import json
import re
from unittest.mock import patch

from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from users.models import User, WebPushSubscription


class WebPushSubscriptionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="push-user@example.com", password="pw"
        )
        self.other_user = User.objects.create_user(
            username="other-push-user@example.com", password="pw"
        )
        self.client.force_login(self.user)
        self.register_url = reverse("register_webpush_subscription")
        self.revoke_url = reverse("revoke_webpush_subscription")

    def _post_subscription(self, endpoint, p256dh="public-key", auth="auth-key"):
        return self.client.post(
            self.register_url,
            data=json.dumps(
                {"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}}
            ),
            content_type="application/json",
        )

    def test_registration_stores_multiple_devices_and_updates_one_endpoint(self):
        endpoint_one = "https://fcm.googleapis.com/fcm/send/device-one"
        endpoint_two = "https://web.push.apple.com/device-two"
        configured = override_settings(
            WEBPUSH_VAPID_PUBLIC_KEY="public-vapid-key",
            WEBPUSH_VAPID_PRIVATE_KEY="private-vapid-key",
        )
        with configured:
            first_response = self._post_subscription(endpoint_one)
            update_response = self._post_subscription(
                endpoint_one, "updated-key", "updated-auth"
            )
            second_response = self._post_subscription(
                endpoint_two, "second-key", "second-auth"
            )

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(second_response.status_code, 201)
        self.assertEqual(WebPushSubscription.objects.filter(user=self.user).count(), 2)
        first = WebPushSubscription.objects.get(endpoint=endpoint_one)
        self.assertEqual(first.user, self.user)
        self.assertEqual(first.p256dh, "updated-key")
        self.assertEqual(first.auth, "updated-auth")
        self.assertEqual(first_response.json(), {"subscribed": True})

    def test_registration_rejects_untrusted_endpoint_hosts(self):
        with override_settings(
            WEBPUSH_VAPID_PUBLIC_KEY="public-vapid-key",
            WEBPUSH_VAPID_PRIVATE_KEY="private-vapid-key",
        ):
            response = self._post_subscription("https://127.0.0.1/internal")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(WebPushSubscription.objects.count(), 0)

    def test_registration_is_disabled_without_vapid_configuration(self):
        with override_settings(
            WEBPUSH_VAPID_PUBLIC_KEY="", WEBPUSH_VAPID_PRIVATE_KEY=""
        ):
            response = self._post_subscription(
                "https://fcm.googleapis.com/fcm/send/device-one"
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(WebPushSubscription.objects.count(), 0)

    def test_registration_requires_login_and_csrf(self):
        anonymous_client = Client()
        response = anonymous_client.post(
            self.register_url,
            data=json.dumps(
                {
                    "endpoint": "https://fcm.googleapis.com/fcm/send/device-one",
                    "keys": {"p256dh": "public-key", "auth": "auth-key"},
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 302)

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        with override_settings(
            WEBPUSH_VAPID_PUBLIC_KEY="public-vapid-key",
            WEBPUSH_VAPID_PRIVATE_KEY="private-vapid-key",
        ):
            response = csrf_client.post(
                self.register_url,
                data=json.dumps(
                    {
                        "endpoint": "https://fcm.googleapis.com/fcm/send/device-one",
                        "keys": {"p256dh": "public-key", "auth": "auth-key"},
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(WebPushSubscription.objects.count(), 0)

    def test_user_can_revoke_only_their_own_subscription(self):
        endpoint = "https://fcm.googleapis.com/fcm/send/device-one"
        subscription = WebPushSubscription.objects.create(
            user=self.user, endpoint=endpoint, p256dh="public-key", auth="auth-key"
        )
        self.client.force_login(self.other_user)
        response = self.client.post(
            self.revoke_url,
            data=json.dumps({"endpoint": endpoint}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 204)
        self.assertTrue(WebPushSubscription.objects.filter(pk=subscription.pk).exists())

        self.client.force_login(self.user)
        response = self.client.post(
            self.revoke_url,
            data=json.dumps({"endpoint": endpoint}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            WebPushSubscription.objects.filter(pk=subscription.pk).exists()
        )


class WebPushDeliveryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="delivery-user@example.com", password="pw"
        )

    def _subscription(self, endpoint):
        return WebPushSubscription.objects.create(
            user=self.user,
            endpoint=endpoint,
            p256dh="public-key",
            auth="auth-key",
        )

    @patch("users.push.webpush")
    def test_sender_uses_bounded_vapid_request_and_serializes_payload(
        self, webpush_mock
    ):
        endpoint = "https://fcm.googleapis.com/fcm/send/device-one"
        self._subscription(endpoint)
        payload = {"title": "New Drover message", "url": "/groups/example/"}

        with override_settings(
            WEBPUSH_VAPID_PUBLIC_KEY="public-vapid-key",
            WEBPUSH_VAPID_PRIVATE_KEY="private-vapid-key",
            WEBPUSH_VAPID_SUBJECT="mailto:push@example.com",
        ):
            from users.push import send_web_push_to_user

            send_web_push_to_user(self.user, payload)

        webpush_mock.assert_called_once_with(
            subscription_info={
                "endpoint": endpoint,
                "keys": {"p256dh": "public-key", "auth": "auth-key"},
            },
            data=json.dumps(payload),
            vapid_private_key="private-vapid-key",
            vapid_claims={"sub": "mailto:push@example.com"},
            timeout=5,
            ttl=3600,
        )

    @patch("users.push.webpush")
    def test_sender_removes_gone_endpoints_and_continues_after_errors(
        self, webpush_mock
    ):
        from types import SimpleNamespace

        from pywebpush import WebPushException

        endpoints = [
            "https://fcm.googleapis.com/fcm/send/device-one",
            "https://fcm.googleapis.com/fcm/send/device-two",
            "https://web.push.apple.com/device-three",
        ]
        for endpoint in endpoints:
            self._subscription(endpoint)
        webpush_mock.side_effect = [
            WebPushException("gone", response=SimpleNamespace(status_code=410)),
            WebPushException("busy", response=SimpleNamespace(status_code=503)),
            None,
        ]

        with override_settings(
            WEBPUSH_VAPID_PUBLIC_KEY="public-vapid-key",
            WEBPUSH_VAPID_PRIVATE_KEY="private-vapid-key",
            WEBPUSH_VAPID_SUBJECT="mailto:push@example.com",
        ):
            from users.push import send_web_push_to_user

            send_web_push_to_user(self.user, {"title": "New Drover message"})

        self.assertEqual(webpush_mock.call_count, 3)
        self.assertEqual(WebPushSubscription.objects.filter(user=self.user).count(), 2)

    @patch("users.push.webpush")
    def test_sender_skips_invalid_existing_endpoints(self, webpush_mock):
        self._subscription("https://127.0.0.1/internal")

        with override_settings(
            WEBPUSH_VAPID_PUBLIC_KEY="public-vapid-key",
            WEBPUSH_VAPID_PRIVATE_KEY="private-vapid-key",
        ):
            from users.push import send_web_push_to_user

            send_web_push_to_user(self.user, {"title": "New Drover message"})

        webpush_mock.assert_not_called()

    @patch("users.push.webpush")
    def test_sender_skips_users_without_subscriptions(self, webpush_mock):
        with override_settings(
            WEBPUSH_VAPID_PUBLIC_KEY="public-vapid-key",
            WEBPUSH_VAPID_PRIVATE_KEY="private-vapid-key",
        ):
            from users.push import send_web_push_to_user

            send_web_push_to_user(self.user, {"title": "New Drover message"})

        webpush_mock.assert_not_called()


class WebPushDashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="dashboard-user@example.com", password="pw"
        )
        self.client.force_login(self.user)
        self.url = reverse("dashboard")

    def test_dashboard_exposes_only_public_key_and_sets_csrf_cookie(self):
        with override_settings(
            WEBPUSH_VAPID_PUBLIC_KEY="public-vapid-key",
            WEBPUSH_VAPID_PRIVATE_KEY="private-vapid-secret",
        ):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-public-key="public-vapid-key"', html=False)
        self.assertNotContains(response, "private-vapid-secret", html=False)
        self.assertIn("csrftoken", response.cookies)

    def test_dashboard_keeps_normal_use_when_push_is_not_configured(self):
        with override_settings(
            WEBPUSH_VAPID_PUBLIC_KEY="", WEBPUSH_VAPID_PRIVATE_KEY=""
        ):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="web-push-toggle"', html=False)
        self.assertContains(response, 'data-enabled="false"', html=False)


class PasswordResetAndRedirectTests(TestCase):
    def setUp(self):
        mail.outbox = []
        self.legacy_user = User.objects.create_user(
            username="legacy@example.com",
            email="",
            password="OldPassword1!",
        )

    def test_login_page_links_to_forgot_password(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("password_reset"))

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_reset_flow_works_for_username_only_accounts(self):
        response = self.client.post(
            reverse("password_reset"),
            {"email": "legacy@example.com"},
        )
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["legacy@example.com"])

        match = re.search(r"/users/reset/[^/]+/[^/\s]+/", mail.outbox[0].body)
        self.assertIsNotNone(match)
        confirm_response = self.client.get(match.group(0), follow=True)
        self.assertEqual(confirm_response.status_code, 200)

        set_url = confirm_response.redirect_chain[-1][0]
        reset_response = self.client.post(
            set_url,
            {
                "new_password1": "NewStrongPass1!",
                "new_password2": "NewStrongPass1!",
            },
        )
        self.assertRedirects(reset_response, reverse("password_reset_complete"))
        self.legacy_user.refresh_from_db()
        self.assertTrue(self.legacy_user.check_password("NewStrongPass1!"))

    def test_signup_populates_email_and_rejects_external_next_redirect(self):
        response = self.client.post(
            f"{reverse('signup')}?next=https://evil.example/phish",
            {
                "first_name": "Ada",
                "last_name": "Lovelace",
                "username": "ada@example.com",
                "contact_number": "+12025550199",
                "password1": "ValidPass1!",
                "password2": "ValidPass1!",
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        user = User.objects.get(username="ada@example.com")
        self.assertEqual(user.email, "ada@example.com")

    def test_login_allows_relative_next_and_blocks_external_next(self):
        external = self.client.post(
            f"{reverse('login')}?next=https://evil.example/steal",
            {"username": "legacy@example.com", "password": "OldPassword1!"},
        )
        self.assertRedirects(external, reverse("dashboard"))
        self.client.logout()

        internal = self.client.post(
            f"{reverse('login')}?next=/groups/create/",
            {"username": "legacy@example.com", "password": "OldPassword1!"},
        )
        self.assertRedirects(internal, "/groups/create/")
