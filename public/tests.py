from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from requests.exceptions import RequestException

from groups.models import Group, GroupEvent, GroupMember, GroupMessage

User = get_user_model()


class MapViewAndLocationSearchTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="mapper@example.com", password="pw"
        )
        self.client.force_login(self.user)

    def test_mapview_renders_valid_coordinates_in_data_attributes(self):
        response = self.client.get(
            reverse("mapview"), {"lat": "40.7128", "lon": "-74.0060"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-lat="40.7128"', html=False)
        self.assertContains(response, 'data-lon="-74.006"', html=False)

    def test_mapview_rejects_non_numeric_or_out_of_range_coordinates(self):
        xss_attempt = self.client.get(
            reverse("mapview"),
            {"lat": "0,0]);alert(1);//", "lon": "-74.0"},
        )
        out_of_range = self.client.get(
            reverse("mapview"),
            {"lat": "120.0", "lon": "200.0"},
        )

        self.assertEqual(xss_attempt.status_code, 302)
        self.assertEqual(out_of_range.status_code, 302)

    @patch("public.views.requests.get")
    def test_location_search_proxies_caches_and_identifies_user_agent(self, mock_get):
        upstream = MagicMock()
        upstream.json.return_value = [
            {
                "display_name": "Central Park, New York, NY",
                "lat": "40.785091",
                "lon": "-73.968285",
                "licence": "Data © OpenStreetMap contributors",
            },
            {"display_name": "Invalid coords", "lat": "not-a-float", "lon": "0"},
        ]
        mock_get.return_value = upstream

        with override_settings(
            OSM_SEARCH_URL="https://nominatim.openstreetmap.org/search",
            OSM_USER_AGENT="DroverTest/1.0",
        ):
            first = self.client.get(
                reverse("location_search"), {"q": "Central Park", "limit": "5"}
            )
            second = self.client.get(
                reverse("location_search"), {"q": "central park", "limit": "5"}
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(mock_get.call_count, 1)
        mock_get.assert_called_once_with(
            "https://nominatim.openstreetmap.org/search",
            params={"q": "Central Park", "format": "json", "limit": 5},
            headers={"User-Agent": "DroverTest/1.0"},
            timeout=5,
        )
        self.assertEqual(
            first.json(),
            [
                {
                    "display_name": "Central Park, New York, NY",
                    "lat": "40.785091",
                    "lon": "-73.968285",
                    "licence": "Data © OpenStreetMap contributors",
                }
            ],
        )

    @patch("public.views.requests.get")
    def test_location_search_skips_short_queries_and_handles_upstream_errors(
        self, mock_get
    ):
        short_resp = self.client.get(reverse("location_search"), {"q": "ny"})
        self.assertEqual(short_resp.status_code, 200)
        self.assertEqual(short_resp.json(), [])
        mock_get.assert_not_called()

        mock_get.side_effect = RequestException("upstream down")
        err_resp = self.client.get(reverse("location_search"), {"q": "Boston Common"})
        self.assertEqual(err_resp.status_code, 200)
        self.assertEqual(err_resp.json(), [])

    def test_event_venue_map_link_rejects_javascript_scheme(self):
        group = Group.objects.create(name="Map Group", owner=self.user)
        GroupMember.objects.create(
            user=self.user, group=group, owner=True, is_admin=True
        )
        response = self.client.post(
            reverse("edit_group", args=[group.id]),
            {
                "description": "desc",
                "venue": "NYC",
                "event_id[]": ["0"],
                "event_name[]": ["Concert"],
                "event_time[]": ["01/02/2026 03:04 PM"],
                "event_instructions[]": [""],
                "event_venue_name[]": ["Hall"],
                "event_venue_address[]": ["123 Main"],
                "event_venue_map[]": ["javascript:alert(1)"],
            },
        )
        self.assertEqual(response.status_code, 302)
        event = GroupEvent.objects.get(group=group, name="Concert")
        self.assertEqual(event.venue_map_link, "")


class InboundSMSReplyTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="sms-admin@example.com",
            password="pw",
            contact_number="+12025550401",
        )
        self.member = User.objects.create_user(
            username="sms-member@example.com",
            password="pw",
            contact_number="+12025550402",
        )
        self.group = Group.objects.create(name="SMS Group", owner=self.admin)
        GroupMember.objects.create(
            user=self.admin, group=self.group, owner=True, is_admin=True
        )
        GroupMember.objects.create(user=self.member, group=self.group)
        self.announcement = GroupMessage.objects.create(
            group=self.group,
            sender=self.admin,
            message="Bus leaves at 9am",
            message_type="AM",
        )

    @override_settings(TWILIO_AUTH_TOKEN="")
    @patch("public.views.send_web_push_to_user")
    @patch("public.views.send_text_message")
    def test_inbound_sms_from_member_creates_reply_and_notifies_admin(
        self, send_sms, send_push
    ):
        response = self.client.post(
            reverse("sms_reply"),
            {"From": "+12025550402", "Body": "Running 5 minutes late"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Your reply has been sent to SMS Group.", response.content.decode()
        )

        reply = GroupMessage.objects.get(reply_to=self.announcement)
        self.assertEqual(reply.sender, self.member)
        self.assertEqual(reply.receiver, self.admin)
        self.assertEqual(reply.message, "Running 5 minutes late")
        self.assertEqual(reply.message_type, "MA")
        send_sms.assert_called_once()
        self.assertEqual(send_sms.call_args.args[0], "+12025550401")
        send_push.assert_called_once()
        self.assertEqual(send_push.call_args.args[0], self.admin)

    @override_settings(TWILIO_AUTH_TOKEN="")
    @patch("public.views.send_text_message")
    def test_inbound_sms_from_unknown_number_returns_fallback_instruction(
        self, send_sms
    ):
        response = self.client.post(
            reverse("sms_reply"),
            {"From": "+12025550999", "Body": "Who is this?"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Do Not Reply via SMS", response.content.decode())
        self.assertEqual(
            GroupMessage.objects.filter(reply_to=self.announcement).count(), 0
        )
        send_sms.assert_not_called()

    @override_settings(TWILIO_AUTH_TOKEN="secret-twilio-token")
    def test_sms_reply_enforces_twilio_signature_when_token_configured(self):
        from twilio.request_validator import RequestValidator

        unsigned = self.client.post(
            reverse("sms_reply"),
            {"From": "+12025550402", "Body": "Spoofed"},
        )
        self.assertEqual(unsigned.status_code, 403)

        url = f"http://testserver{reverse('sms_reply')}"
        params = {"From": "+12025550402", "Body": "Signed reply"}
        signature = RequestValidator("secret-twilio-token").compute_signature(
            url, params
        )
        with (
            patch("public.views.send_text_message"),
            patch("public.views.send_web_push_to_user"),
        ):
            signed = self.client.post(
                reverse("sms_reply"),
                params,
                HTTP_X_TWILIO_SIGNATURE=signature,
            )
        self.assertEqual(signed.status_code, 200)
        self.assertTrue(
            GroupMessage.objects.filter(
                reply_to=self.announcement, message="Signed reply"
            ).exists()
        )
