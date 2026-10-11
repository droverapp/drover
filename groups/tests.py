import uuid

from django.test import TestCase
from django.urls import reverse

from users.models import User
from .models import Group, GroupEvent, GroupMember


class EditGroupEventIdTests(TestCase):
    """`edit_group` must treat "0"/"" as the new-event sentinel and 404 on
    any other id that is not a UUID belonging to the group."""

    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="x")
        self.client.force_login(self.owner)
        self.group = Group.objects.create(name="G", owner=self.owner)
        GroupMember.objects.create(
            user=self.owner, group=self.group, is_admin=True, owner=True
        )
        self.event = GroupEvent.objects.create(group=self.group, name="Old")
        other_group = Group.objects.create(name="Other", owner=self.owner)
        self.foreign_event = GroupEvent.objects.create(
            group=other_group, name="Foreign"
        )

    def post_events(self, event_ids):
        url = reverse("edit_group", args=[self.group.id])
        return self.client.post(
            url,
            {
                "description": "d",
                "venue": "v",
                "event_id[]": event_ids,
                "event_name[]": ["New name"] * len(event_ids),
                "event_time[]": ["01/02/2026 03:04 PM"] * len(event_ids),
                "event_instructions[]": [""] * len(event_ids),
                "event_venue_name[]": [""] * len(event_ids),
                "event_venue_address[]": [""] * len(event_ids),
                "event_venue_map[]": [""] * len(event_ids),
            },
        )

    def test_zero_sentinel_creates_new_event(self):
        response = self.post_events(["0"])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(GroupEvent.objects.filter(group=self.group).count(), 2)

    def test_empty_sentinel_creates_new_event(self):
        response = self.post_events([""])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(GroupEvent.objects.filter(group=self.group).count(), 2)

    def test_existing_uuid_updates_in_place(self):
        response = self.post_events([str(self.event.id)])
        self.assertEqual(response.status_code, 302)
        self.event.refresh_from_db()
        self.assertEqual(self.event.name, "New name")
        self.assertEqual(GroupEvent.objects.filter(group=self.group).count(), 1)

    def test_unknown_uuid_is_404(self):
        response = self.post_events([str(uuid.uuid4())])
        self.assertEqual(response.status_code, 404)

    def test_non_uuid_integer_id_is_404(self):
        response = self.post_events(["12345"])
        self.assertEqual(response.status_code, 404)

    def test_foreign_group_event_is_404(self):
        response = self.post_events([str(self.foreign_event.id)])
        self.assertEqual(response.status_code, 404)
