from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from requests.exceptions import RequestException

from groups.models import Group, GroupEvent, GroupMember

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
