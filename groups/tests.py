"""
Integration tests for the GroupEvent RSVP workflow.

Covers status submission, membership access, rendered RSVP controls, idempotent
updates, group-page counts, and representative SQL query shapes.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from inline_snapshot import snapshot
from inline_snapshot_django import snapshot_queries

from groups.models import Group, GroupEvent, GroupEventRSVP, GroupMember, GroupMessage
from groups.sms import send_text_message

User = get_user_model()


class RSVPTestView(TestCase):
    """Integration tests for the rsvp_event view."""

    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="pw")
        self.member = User.objects.create_user(username="member", password="pw")
        self.outsider = User.objects.create_user(username="outsider", password="pw")
        self.group = Group.objects.create(name="G1", owner=self.owner)
        self.member_ship = GroupMember.objects.create(
            user=self.member, group=self.group, owner=False, is_admin=True
        )
        self.event = GroupEvent.objects.create(
            group=self.group, name="Party", event_time="2026-12-01T00:00:00Z"
        )

    def _rsvp_url(self, event_id=None):
        return reverse(
            "rsvp_event",
            kwargs={
                "group_id": self.group.id,
                "event_id": event_id or self.event.id,
            },
        )

    def test_member_can_rsvp_going(self):
        """Member POSTs to RSVP — creates GroupEventRSVP, redirects to view_group."""
        from django.test import Client

        c = Client()
        c.post("/users/login/", {"username": "member", "password": "pw"})
        resp = c.post(self._rsvp_url(), {"status": "going"})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            resp["Location"].endswith(reverse("view_group", args=[self.group.id]))
        )
        rsvp = GroupEventRSVP.objects.get(event=self.event, user=self.member)
        self.assertEqual(rsvp.status, GroupEventRSVP.Status.GOING)

    def test_member_can_change_rsvp(self):
        """Member already RSVP'd — changing status updates, not duplicates."""
        from django.test import Client

        c = Client()
        c.post("/users/login/", {"username": "member", "password": "pw"})
        c.post(self._rsvp_url(), {"status": "going"})
        resp = c.post(self._rsvp_url(), {"status": "not_going"})
        self.assertEqual(resp.status_code, 302)
        rsvp = GroupEventRSVP.objects.get(event=self.event, user=self.member)
        self.assertEqual(rsvp.status, GroupEventRSVP.Status.NOT_GOING)
        self.assertEqual(GroupEventRSVP.objects.filter(event=self.event).count(), 1)

    def test_repeating_same_rsvp_is_idempotent(self):
        from django.test import Client

        c = Client()
        c.post("/users/login/", {"username": "member", "password": "pw"})
        c.post(self._rsvp_url(), {"status": "going"})
        resp = c.post(self._rsvp_url(), {"status": "going"})

        self.assertEqual(resp.status_code, 302)
        rsvp = GroupEventRSVP.objects.get(event=self.event, user=self.member)
        self.assertEqual(rsvp.status, GroupEventRSVP.Status.GOING)

    def test_invalid_status_does_not_create_rsvp(self):
        c = Client()
        c.force_login(self.member)
        resp = c.post(self._rsvp_url(), {"status": "unknown"})

        self.assertEqual(resp.status_code, 302)
        self.assertFalse(GroupEventRSVP.objects.filter(event=self.event).exists())

    def test_non_member_cannot_rsvp(self):
        """User not in the group gets 403/404."""
        from django.test import Client

        c = Client()
        c.post("/users/login/", {"username": "outsider", "password": "pw"})
        resp = c.post(self._rsvp_url(), {"status": "going"})
        self.assertIn(resp.status_code, [403, 404])

    def test_unauthenticated_redirected(self):
        """Anonymous user is redirected to login."""
        from django.test import Client

        c = Client()
        resp = c.post(self._rsvp_url(), {"status": "going"})
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/users/login/", resp["Location"])


class RSVPTestTemplate(TestCase):
    """Integration tests for RSVP display in the view_group template."""

    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="pw")
        self.member = User.objects.create_user(username="member", password="pw")
        self.group = Group.objects.create(name="G1", owner=self.owner)
        GroupMember.objects.create(user=self.member, group=self.group)
        self.event = GroupEvent.objects.create(
            group=self.group, name="Party", event_time="2026-12-01T00:00:00Z"
        )
        GroupEventRSVP.objects.create(
            event=self.event, user=self.member, status=GroupEventRSVP.Status.GOING
        )
        GroupEventRSVP.objects.create(
            event=self.event, user=self.owner, status=GroupEventRSVP.Status.NOT_GOING
        )

    def test_view_group_shows_rsvp_counts(self):
        from django.test import Client

        c = Client()
        c.post("/users/login/", {"username": "member", "password": "pw"})
        resp = c.get(reverse("view_group", args=[self.group.id]))
        self.assertEqual(resp.status_code, 200)
        # Template should render RSVP counts
        self.assertContains(resp, "Going")
        self.assertContains(resp, "Not Going")
        # Total count
        self.assertContains(resp, "1 Going")
        self.assertContains(resp, "1 Not Going")

    def test_view_group_shows_member_rsvp_status(self):
        from django.test import Client

        c = Client()
        c.post("/users/login/", {"username": "member", "password": "pw"})
        resp = c.get(reverse("view_group", args=[self.group.id]))
        self.assertEqual(resp.status_code, 200)
        # Member's own status should be displayed
        self.assertContains(resp, "Going")

    def test_view_group_shows_rsvp_toggle_button(self):
        """Template renders a clickable RSVP toggle for the event."""
        from django.test import Client

        c = Client()
        c.post("/users/login/", {"username": "member", "password": "pw"})
        resp = c.get(reverse("view_group", args=[self.group.id]))
        self.assertEqual(resp.status_code, 200)
        # RSVP toggle URL should be in the page
        rsvp_url = reverse(
            "rsvp_event",
            kwargs={"group_id": self.group.id, "event_id": self.event.id},
        )
        self.assertEqual(
            resp.content.count(f'<form method="post" action="{rsvp_url}"'.encode()), 1
        )
        self.assertContains(resp, 'name="status" value="going"', html=False)
        self.assertContains(resp, 'name="status" value="maybe"', html=False)
        self.assertContains(resp, 'name="status" value="not_going"', html=False)


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
                "description": "Updated group description",
                "venue": "Updated group venue",
                "event_id[]": event_ids,
                "event_name[]": ["New name"] * len(event_ids),
                "event_time[]": ["01/02/2026 03:04 PM"] * len(event_ids),
                "event_instructions[]": ["Bring a dish"] * len(event_ids),
                "event_venue_name[]": ["Community Hall"] * len(event_ids),
                "event_venue_address[]": ["123 Main Street"] * len(event_ids),
                "event_venue_map[]": ["https://maps.example.com/hall"] * len(event_ids),
            },
        )

    def test_zero_sentinel_creates_event_with_submitted_details(self):
        response = self.post_events(["0"])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(GroupEvent.objects.filter(group=self.group).count(), 2)
        new_event = GroupEvent.objects.get(group=self.group, name="New name")
        self.assertEqual(new_event.instructions, "Bring a dish")
        self.assertEqual(new_event.venue_name, "Community Hall")
        self.assertEqual(new_event.venue_address, "123 Main Street")

    def test_empty_sentinel_creates_new_event(self):
        response = self.post_events([""])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(GroupEvent.objects.filter(group=self.group).count(), 2)

    def test_existing_uuid_updates_all_event_details_in_place(self):
        response = self.post_events([str(self.event.id)])
        self.assertEqual(response.status_code, 302)
        self.event.refresh_from_db()
        self.assertEqual(self.event.name, "New name")
        self.assertEqual(
            self.event.event_time.strftime("%Y-%m-%d %H:%M"), "2026-01-02 15:04"
        )
        self.assertEqual(self.event.instructions, "Bring a dish")
        self.assertEqual(self.event.venue_name, "Community Hall")
        self.assertEqual(self.event.venue_address, "123 Main Street")
        self.assertEqual(self.event.venue_map_link, "https://maps.example.com/hall")
        self.assertEqual(GroupEvent.objects.filter(group=self.group).count(), 1)
        self.group.refresh_from_db()
        self.assertEqual(self.group.description, "Updated group description")
        self.assertEqual(self.group.venue, "Updated group venue")

    def test_unknown_uuid_is_404(self):
        response = self.post_events([str(uuid.uuid4())])
        self.assertEqual(response.status_code, 404)

    def test_non_uuid_integer_id_is_404(self):
        response = self.post_events(["12345"])
        self.assertEqual(response.status_code, 404)

    def test_foreign_group_event_is_404(self):
        response = self.post_events([str(self.foreign_event.id)])
        self.assertEqual(response.status_code, 404)


class RSVPFullWorkflowTest(TestCase):
    """End-to-end integration tests: the whole RSVP process.

    Walks the full user journey through real views and URLs:
    login -> create group -> create event -> RSVP -> view -> change -> repeat.
    """

    def setUp(self):
        self.c = Client()

    def _login(self, username, password="pw"):
        resp = self.c.post(
            "/users/login/", {"username": username, "password": password}
        )
        self.assertEqual(resp.status_code, 302, f"login failed for {username}")

    def _create_group(self, name="My Group"):
        """Create a group via the real create_group view."""
        resp = self.c.post(
            "/groups/create/",
            {
                "name": name,
                "venue": "V",
                "description": "<p>D</p>",
                "event_name[]": [],
                "event_id[]": [],
                "event_time[]": [],
            },
        )
        self.assertIn(resp.status_code, [200, 302])
        return Group.objects.filter(name=name).latest("created_at")

    def _add_event(self, group, event_name="My Event"):
        """Create an event via the real edit_group view (event_id=0 sentinel)."""
        resp = self.c.post(
            reverse("edit_group", kwargs={"group_id": group.id}),
            {
                "name": group.name,
                "venue": group.venue or "V",
                "description": group.description or "<p>D</p>",
                "event_name[]": [event_name],
                "event_id[]": ["0"],
                "event_time[]": ["01/15/2026 02:00 PM"],
                "event_instructions[]": ["Bring snacks"],
                "event_venue_name[]": ["Venue A"],
                "event_venue_address[]": ["123 Street"],
                "event_venue_map[]": ["http://map.example.com"],
            },
        )
        self.assertEqual(resp.status_code, 302)
        return GroupEvent.objects.get(group=group, name=event_name)

    def _rsvp(self, group, event, status):
        """RSVP via the real rsvp_event view."""
        return self.c.post(
            reverse(
                "rsvp_event",
                kwargs={"group_id": group.id, "event_id": event.id},
            ),
            {"status": status},
        )

    def test_full_workflow_create_group_event_rsvp(self):
        """Full journey: login -> create group -> create event -> RSVP -> verify."""
        User.objects.create_user(username="workflow_user", password="pw")
        self._login("workflow_user")
        user = User.objects.get(username="workflow_user")

        group = self._create_group("Workflow Group")
        self.assertTrue(GroupMember.objects.filter(group=group, user=user).exists())

        event = self._add_event(group, "Movie Night")
        self.assertEqual(event.group, group)

        resp = self._rsvp(group, event, "going")
        self.assertEqual(resp.status_code, 302)
        rsvp = GroupEventRSVP.objects.get(event=event, user=user)
        self.assertEqual(rsvp.status, GroupEventRSVP.Status.GOING)

        resp = self.c.get(reverse("view_group", kwargs={"group_id": group.id}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Movie Night")
        self.assertContains(resp, "Going")
        self.assertContains(resp, "1 Going")

    def test_full_workflow_multi_user_rsvp_counts(self):
        """Multiple users RSVP with different statuses; counts shown correctly."""
        owner = User.objects.create_user(username="owner1", password="pw")
        m1 = User.objects.create_user(username="member1", password="pw")
        m2 = User.objects.create_user(username="member2", password="pw")
        group = Group.objects.create(name="Multi", owner=owner)
        GroupMember.objects.create(user=owner, group=group, owner=True, is_admin=True)
        GroupMember.objects.create(user=m1, group=group)
        GroupMember.objects.create(user=m2, group=group)
        event = GroupEvent.objects.create(group=group, name="Picnic")

        self.c.post("/users/login/", {"username": "owner1", "password": "pw"})
        self._rsvp(group, event, "going")
        self.c.post("/users/login/", {"username": "member1", "password": "pw"})
        self._rsvp(group, event, "going")
        self.c.post("/users/login/", {"username": "member2", "password": "pw"})
        self._rsvp(group, event, "not_going")

        self.assertEqual(GroupEventRSVP.objects.filter(event=event).count(), 3)
        self.assertEqual(
            GroupEventRSVP.objects.filter(
                event=event, status=GroupEventRSVP.Status.GOING
            ).count(),
            2,
        )
        self.assertEqual(
            GroupEventRSVP.objects.filter(
                event=event, status=GroupEventRSVP.Status.NOT_GOING
            ).count(),
            1,
        )

        self.c.post("/users/login/", {"username": "owner1", "password": "pw"})
        resp = self.c.get(reverse("view_group", kwargs={"group_id": group.id}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "2 Going")
        self.assertContains(resp, "1 Not Going")

    def test_full_workflow_repeating_rsvp_is_idempotent(self):
        """A repeated status submission preserves the user's RSVP."""
        owner = User.objects.create_user(username="owner2", password="pw")
        user = User.objects.create_user(username="changer", password="pw")
        group = Group.objects.create(name="Change", owner=owner)
        GroupMember.objects.create(user=user, group=group)
        event = GroupEvent.objects.create(group=group, name="Dinner")

        self.c.post("/users/login/", {"username": "changer", "password": "pw"})

        self._rsvp(group, event, "going")
        rsvp = GroupEventRSVP.objects.get(event=event, user=user)
        self.assertEqual(rsvp.status, GroupEventRSVP.Status.GOING)

        self._rsvp(group, event, "maybe")
        rsvp.refresh_from_db()
        self.assertEqual(rsvp.status, GroupEventRSVP.Status.MAYBE)

        self._rsvp(group, event, "maybe")
        rsvp.refresh_from_db()
        self.assertEqual(rsvp.status, GroupEventRSVP.Status.MAYBE)
        self.assertEqual(
            GroupEventRSVP.objects.filter(event=event, user=user).count(), 1
        )

        resp = self.c.get(reverse("view_group", kwargs={"group_id": group.id}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Your RSVP: Maybe")

    def test_full_workflow_rsvp_deleted_when_event_deleted(self):
        """Deleting an event cascades to its RSVPs."""
        owner = User.objects.create_user(username="owner3", password="pw")
        user = User.objects.create_user(username="cascader", password="pw")
        group = Group.objects.create(name="Cascade", owner=owner)
        GroupMember.objects.create(user=user, group=group)
        event = GroupEvent.objects.create(group=group, name="To Delete")
        self.c.post("/users/login/", {"username": "cascader", "password": "pw"})
        self._rsvp(group, event, "going")
        self.assertEqual(GroupEventRSVP.objects.filter(event=event).count(), 1)

        event.delete()
        self.assertEqual(GroupEventRSVP.objects.count(), 0)

    def test_full_workflow_non_member_cannot_rsvp_or_view(self):
        """A user outside the group can't RSVP or even view the group page."""
        owner = User.objects.create_user(username="owner4", password="pw")
        User.objects.create_user(username="outsider2", password="pw")
        group = Group.objects.create(name="Private", owner=owner)
        event = GroupEvent.objects.create(group=group, name="Secret")

        self.c.post("/users/login/", {"username": "outsider2", "password": "pw"})
        resp = self._rsvp(group, event, "going")
        self.assertIn(resp.status_code, [302, 403, 404])
        self.assertFalse(GroupEventRSVP.objects.filter(event=event).exists())
        resp = self.c.get(reverse("view_group", kwargs={"group_id": group.id}))
        self.assertEqual(resp.status_code, 302)

    def test_rsvp_and_group_page_query_variants(self):
        """Snapshot SQL for group-page read and RSVP create/update/no-op paths."""
        owner = User.objects.create_user(username="snapshot-owner", password="pw")
        user = User.objects.create_user(username="snapshot-member", password="pw")
        group = Group.objects.create(name="Snapshots", owner=owner)
        GroupMember.objects.create(user=user, group=group)
        event = GroupEvent.objects.create(group=group, name="Query Event")
        self.c.force_login(user)

        with snapshot_queries() as view_queries:
            response = self.c.get(reverse("view_group", kwargs={"group_id": group.id}))
        self.assertEqual(response.status_code, 200)
        assert view_queries == snapshot(
            [
                "SELECT ... FROM django_session WHERE ... LIMIT ...",
                "SELECT ... FROM users_user WHERE ... LIMIT ...",
                "SELECT ... FROM groups_group WHERE ... ORDER BY ... DESC LIMIT ...",
                "SELECT ... FROM groups_groupmember INNER JOIN users_user ON ... WHERE ... ORDER BY ... ASC LIMIT ...",
                "SELECT ... FROM shortener_shorturl WHERE ... ORDER BY ... DESC LIMIT ...",
                "SELECT ... FROM shortener_shorturl WHERE ... ORDER BY ... DESC LIMIT ...",
                "INSERT INTO shortener_shorturl (...) VALUES (...)",
                "SELECT ... FROM groups_groupevent LEFT OUTER JOIN groups_groupeventrsvp ON ... WHERE ... GROUP BY ... ORDER BY ... ASC",
            ]
        )

        with snapshot_queries() as create_queries:
            self._rsvp(group, event, "going")
        assert create_queries == snapshot(
            [
                "SELECT ... FROM django_session WHERE ... LIMIT ...",
                "SELECT ... FROM users_user WHERE ... LIMIT ...",
                "SELECT ... FROM groups_group WHERE ... ORDER BY ... DESC LIMIT ...",
                "SELECT ... FROM groups_groupevent WHERE ... ORDER BY ... DESC LIMIT ...",
                "SELECT ... FROM groups_groupmember INNER JOIN users_user ON ... WHERE ... ORDER BY ... ASC LIMIT ...",
                "SELECT ... FROM groups_groupeventrsvp WHERE ... LIMIT ...",
                "SAVEPOINT s1",
                "INSERT INTO groups_groupeventrsvp (...) VALUES (...)",
                "RELEASE SAVEPOINT s1",
            ]
        )
        rsvp = GroupEventRSVP.objects.get(event=event, user=user)
        self.assertEqual(rsvp.status, GroupEventRSVP.Status.GOING)

        with snapshot_queries() as update_queries:
            self._rsvp(group, event, "maybe")
        assert update_queries == snapshot(
            [
                "SELECT ... FROM django_session WHERE ... LIMIT ...",
                "SELECT ... FROM users_user WHERE ... LIMIT ...",
                "SELECT ... FROM groups_group WHERE ... ORDER BY ... DESC LIMIT ...",
                "SELECT ... FROM groups_groupevent WHERE ... ORDER BY ... DESC LIMIT ...",
                "SELECT ... FROM groups_groupmember INNER JOIN users_user ON ... WHERE ... ORDER BY ... ASC LIMIT ...",
                "SELECT ... FROM groups_groupeventrsvp WHERE ... LIMIT ...",
                "UPDATE groups_groupeventrsvp SET ... = ... WHERE ...",
            ]
        )
        rsvp.refresh_from_db()
        self.assertEqual(rsvp.status, GroupEventRSVP.Status.MAYBE)

        with snapshot_queries() as idempotent_queries:
            self._rsvp(group, event, "maybe")
        assert idempotent_queries == snapshot(
            [
                "SELECT ... FROM django_session WHERE ... LIMIT ...",
                "SELECT ... FROM users_user WHERE ... LIMIT ...",
                "SELECT ... FROM groups_group WHERE ... ORDER BY ... DESC LIMIT ...",
                "SELECT ... FROM groups_groupevent WHERE ... ORDER BY ... DESC LIMIT ...",
                "SELECT ... FROM groups_groupmember INNER JOIN users_user ON ... WHERE ... ORDER BY ... ASC LIMIT ...",
                "SELECT ... FROM groups_groupeventrsvp WHERE ... LIMIT ...",
            ]
        )
        rsvp.refresh_from_db()
        self.assertEqual(rsvp.status, GroupEventRSVP.Status.MAYBE)
        self.assertEqual(
            GroupEventRSVP.objects.filter(event=event, user=user).count(), 1
        )


class GroupMessageFlowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin", password="pw", contact_number="+12025550101"
        )
        self.second_admin = User.objects.create_user(
            username="second-admin", password="pw", contact_number="+12025550102"
        )
        self.member = User.objects.create_user(
            username="member", password="pw", contact_number="+12025550103"
        )
        self.other_member = User.objects.create_user(
            username="other-member", password="pw", contact_number="+12025550104"
        )
        self.deleted_member = User.objects.create_user(
            username="deleted-member", password="pw", contact_number="+12025550105"
        )
        self.group = Group.objects.create(name="Messages", owner=self.admin)
        GroupMember.objects.create(
            user=self.admin, group=self.group, owner=True, is_admin=True
        )
        GroupMember.objects.create(
            user=self.second_admin, group=self.group, is_admin=True
        )
        GroupMember.objects.create(user=self.member, group=self.group)
        GroupMember.objects.create(user=self.other_member, group=self.group)
        GroupMember.objects.create(
            user=self.deleted_member, group=self.group, is_deleted=True
        )
        self.send_url = reverse("send_message", kwargs={"group_id": self.group.id})
        self.inbox_url = reverse("inbox", kwargs={"group_id": self.group.id})

    @patch("groups.views.send_web_push_to_user")
    @patch("groups.views.send_text_message")
    def test_admin_message_persists_and_targets_active_members(
        self, send_sms, send_push
    ):
        self.client.force_login(self.admin)
        response = self.client.post(self.send_url, {"message": "Meeting at noon"})

        self.assertEqual(response.status_code, 302)
        message = GroupMessage.objects.get(group=self.group, sender=self.admin)
        self.assertEqual(message.message, "Meeting at noon")
        self.assertEqual(message.message_type, "AM")
        self.assertCountEqual(
            [call.args[0] for call in send_sms.call_args_list],
            ["+12025550103", "+12025550104"],
        )
        for sent_call in send_sms.call_args_list:
            self.assertEqual(sent_call.args[1], "Meeting at noon")
            self.assertTrue(sent_call.args[2].startswith("http://testserver/"))
        self.assertCountEqual(
            [push_call.args[0] for push_call in send_push.call_args_list],
            [self.member, self.other_member],
        )
        for push_call in send_push.call_args_list:
            payload = push_call.args[1]
            self.assertEqual(payload["title"], "New Drover message")
            self.assertEqual(payload["body"], "Open Drover to view the message.")
            self.assertNotIn("Meeting at noon", payload["body"])

    @patch("groups.views.send_web_push_to_user")
    @patch("groups.views.send_text_message")
    def test_member_message_persists_and_targets_active_admins(
        self, send_sms, send_push
    ):
        self.client.force_login(self.member)
        response = self.client.post(self.send_url, {"message": "Need approval"})

        self.assertEqual(response.status_code, 302)
        message = GroupMessage.objects.get(group=self.group, sender=self.member)
        self.assertEqual(message.message, "Need approval")
        self.assertEqual(message.message_type, "MA")
        self.assertCountEqual(
            [call.args[0] for call in send_sms.call_args_list],
            ["+12025550101", "+12025550102"],
        )
        self.assertCountEqual(
            [push_call.args[0] for push_call in send_push.call_args_list],
            [self.admin, self.second_admin],
        )

    def test_member_inbox_shows_own_messages_and_admin_broadcasts_only(self):
        broadcast = GroupMessage.objects.create(
            group=self.group, sender=self.admin, message="Everyone", message_type="AM"
        )
        direct = GroupMessage.objects.create(
            group=self.group,
            sender=self.admin,
            receiver=self.member,
            message="For you",
            message_type="AM",
        )
        own = GroupMessage.objects.create(
            group=self.group,
            sender=self.member,
            message="My question",
            message_type="MA",
        )
        another_member = GroupMessage.objects.create(
            group=self.group,
            sender=self.other_member,
            receiver=self.admin,
            message="Not yours",
            message_type="MA",
        )

        self.client.force_login(self.member)
        response = self.client.get(self.inbox_url)

        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(
            [message.pk for message in response.context["sent_messages"]], [own.pk]
        )
        self.assertCountEqual(
            [message.pk for message in response.context["received_messages"]],
            [broadcast.pk, direct.pk],
        )

        self.client.force_login(self.admin)
        response = self.client.get(self.inbox_url)
        self.assertCountEqual(
            [message.pk for message in response.context["sent_messages"]],
            [broadcast.pk, direct.pk],
        )
        self.assertCountEqual(
            [message.pk for message in response.context["received_messages"]],
            [own.pk, another_member.pk],
        )

    @patch("groups.views.send_web_push_to_user")
    @patch("groups.views.send_text_message")
    def test_nonmember_cannot_send_or_read_inbox(self, send_sms, send_push):
        outsider = User.objects.create_user(username="outsider", password="pw")
        self.client.force_login(outsider)

        send_response = self.client.post(self.send_url, {"message": "No access"})
        inbox_response = self.client.get(self.inbox_url)

        self.assertEqual(send_response.status_code, 302)
        self.assertEqual(inbox_response.status_code, 302)
        self.assertFalse(GroupMessage.objects.filter(group=self.group).exists())
        send_sms.assert_not_called()
        send_push.assert_not_called()

    @patch("groups.views.send_text_message")
    def test_push_provider_failure_does_not_interrupt_group_message(self, send_sms):
        from types import SimpleNamespace

        from pywebpush import WebPushException

        from users.models import WebPushSubscription

        WebPushSubscription.objects.create(
            user=self.member,
            endpoint="https://fcm.googleapis.com/fcm/send/device-one",
            p256dh="public-key",
            auth="auth-key",
        )
        self.client.force_login(self.admin)

        with (
            override_settings(
                WEBPUSH_VAPID_PUBLIC_KEY="public-vapid-key",
                WEBPUSH_VAPID_PRIVATE_KEY="private-vapid-key",
            ),
            patch(
                "users.push.webpush",
                side_effect=WebPushException(
                    "busy", response=SimpleNamespace(status_code=503)
                ),
            ) as webpush_mock,
        ):
            response = self.client.post(self.send_url, {"message": "Saved anyway"})

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            GroupMessage.objects.filter(
                group=self.group, sender=self.admin, message="Saved anyway"
            ).exists()
        )
        self.assertEqual(webpush_mock.call_count, 1)
        self.assertEqual(send_sms.call_count, 2)

    def test_sms_helper_uses_account_token_and_formats_link(self):
        with (
            override_settings(
                TWILIO_API_KEY="",
                TWILIO_API_SECRET="",
                TWILIO_ACCOUNT_SID="AC123",
                TWILIO_AUTH_TOKEN="auth-token",
                FROM_NUMBER="+12025550999",
            ),
            patch("groups.sms.Client") as twilio_client,
        ):
            twilio_client.return_value.messages.create.return_value = SimpleNamespace(
                status="queued"
            )
            send_text_message(
                "+12025550123", "Dinner at 6", "https://drover.example/reply/"
            )

        twilio_client.assert_called_once_with("AC123", "auth-token")
        twilio_client.return_value.messages.create.assert_called_once_with(
            to="+12025550123",
            from_="+12025550999",
            body="Dinner at 6.\n Please visit https://drover.example/reply/ to reply.",
        )

    def test_sms_helper_uses_api_key_credentials_when_configured(self):
        with (
            override_settings(
                TWILIO_API_KEY="SK123",
                TWILIO_API_SECRET="api-secret",
                TWILIO_ACCOUNT_SID="AC123",
                FROM_NUMBER="+12025550999",
            ),
            patch("groups.sms.Client") as twilio_client,
        ):
            twilio_client.return_value.messages.create.return_value = SimpleNamespace(
                status="queued"
            )
            send_text_message("+12025550123", "Hello", "https://drover.example/r/")

        twilio_client.assert_called_once_with("SK123", "api-secret", "AC123")
        self.assertEqual(twilio_client.return_value.messages.create.call_count, 1)


class GroupInvitationTests(TestCase):
    def setUp(self):
        mail.outbox = []
        self.admin = User.objects.create_user(username="invite-admin", password="pw")
        self.existing_user = User.objects.create_user(
            username="new-member@example.com", password="pw"
        )
        self.group = Group.objects.create(name="Invites", owner=self.admin)
        GroupMember.objects.create(
            user=self.admin, group=self.group, owner=True, is_admin=True
        )
        self.url = reverse("add_group_member", kwargs={"group_id": self.group.id})
        self.client.force_login(self.admin)

    def test_admin_adds_existing_user_and_sends_membership_email(self):
        with override_settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
        ):
            response = self.client.post(
                self.url, {"email": self.existing_user.username}
            )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            GroupMember.objects.filter(
                group=self.group, user=self.existing_user
            ).exists()
        )
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, [self.existing_user.username])
        self.assertEqual(
            message.subject, "Drover: You have been added to the group Invites"
        )
        self.assertEqual(message.body, "Welcome to group Invites")

    def test_admin_emails_invitation_link_for_unregistered_address(self):
        email = "guest@example.com"

        with override_settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
        ):
            response = self.client.post(self.url, {"email": email})

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            GroupMember.objects.filter(group=self.group, user__username=email).exists()
        )
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, [email])
        self.assertEqual(
            message.subject, "You've been invited to join a group on Drover!: Invites"
        )
        self.assertIn("Invitation URL: http://testserver/", message.body)

    def test_nonadmin_cannot_add_members_or_send_invitation_email(self):
        member = User.objects.create_user(username="invite-member", password="pw")
        GroupMember.objects.create(user=member, group=self.group)
        self.client.force_login(member)

        with override_settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
        ):
            response = self.client.post(self.url, {"email": "guest@example.com"})

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            GroupMember.objects.filter(
                group=self.group, user=self.existing_user
            ).exists()
        )
        self.assertEqual(mail.outbox, [])


class GroupMessageReplyTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="reply-admin", password="pw", contact_number="+12025550201"
        )
        self.member = User.objects.create_user(
            username="reply-member", password="pw", contact_number="+12025550202"
        )
        self.other_member = User.objects.create_user(
            username="reply-other", password="pw", contact_number="+12025550203"
        )
        self.group = Group.objects.create(name="Replies", owner=self.admin)
        GroupMember.objects.create(
            user=self.admin, group=self.group, owner=True, is_admin=True
        )
        GroupMember.objects.create(user=self.member, group=self.group)
        GroupMember.objects.create(user=self.other_member, group=self.group)
        self.admin_message = GroupMessage.objects.create(
            group=self.group,
            sender=self.admin,
            message="Group announcement",
            message_type="AM",
        )
        self.member_message = GroupMessage.objects.create(
            group=self.group,
            sender=self.member,
            message="Question for admins",
            message_type="MA",
        )

    def _url(self, route_name, message, group=None):
        return reverse(
            route_name,
            kwargs={"group_id": (group or self.group).id, "message_id": message.id},
        )

    @patch("groups.views.send_web_push_to_user")
    @patch("groups.views.send_text_message")
    def test_member_reply_uses_announcement_sender_not_posted_receiver(
        self, send_sms, send_push
    ):
        self.client.force_login(self.member)
        response = self.client.post(
            self._url("conversation_details", self.admin_message),
            {"reply": "I can attend", "receiver_email": self.other_member.username},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"], self._url("conversation_details", self.admin_message)
        )
        reply = GroupMessage.objects.get(reply_to=self.admin_message)
        self.assertEqual(reply.message, "I can attend")
        self.assertEqual(reply.sender, self.member)
        self.assertEqual(reply.receiver, self.admin)
        self.assertEqual(reply.message_type, "MA")
        send_sms.assert_called_once()
        self.assertEqual(send_sms.call_args.args[0], self.admin.contact_number)
        self.assertCountEqual(
            [push_call.args[0] for push_call in send_push.call_args_list],
            [self.admin],
        )
        self.assertEqual(
            send_push.call_args.args[1]["url"],
            self._url("conversation_details", self.admin_message),
        )

        response = self.client.get(
            self._url("conversation_details", self.admin_message)
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(reply, response.context["conversations"])

    @patch("groups.views.send_web_push_to_user")
    @patch("groups.views.send_text_message")
    def test_admin_reply_targets_member_author(self, send_sms, send_push):
        self.client.force_login(self.admin)
        response = self.client.post(
            self._url("conversation_details", self.member_message),
            {
                "reply": "We will follow up",
                "receiver_email": self.other_member.username,
            },
        )

        self.assertEqual(response.status_code, 302)
        reply = GroupMessage.objects.get(reply_to=self.member_message)
        self.assertEqual(reply.sender, self.admin)
        self.assertEqual(reply.receiver, self.member)
        self.assertEqual(reply.message_type, "AM")
        self.assertEqual(send_sms.call_args.args[0], self.member.contact_number)
        send_push.assert_called_once()
        self.assertEqual(send_push.call_args.args[0], self.member)
        self.assertEqual(
            send_push.call_args.args[1]["url"],
            self._url("conversation_details", self.member_message),
        )

    @patch("groups.views.send_web_push_to_user")
    @patch("groups.views.send_text_message")
    def test_legacy_message_details_reply_uses_parent_author(self, send_sms, send_push):
        self.client.force_login(self.admin)
        response = self.client.post(
            self._url("message_details", self.member_message),
            {"reply": "I will help", "receiver_email": self.other_member.username},
        )

        self.assertEqual(response.status_code, 302)
        reply = GroupMessage.objects.get(reply_to=self.member_message)
        self.assertEqual(reply.receiver, self.member)
        self.assertEqual(send_sms.call_args.args[0], self.member.contact_number)
        send_push.assert_called_once()
        self.assertEqual(send_push.call_args.args[0], self.member)
        self.assertEqual(
            send_push.call_args.args[1]["url"],
            self._url("conversation_details", self.member_message),
        )

    @patch("groups.views.send_web_push_to_user")
    @patch("groups.views.send_text_message")
    def test_nonparticipant_cannot_view_or_reply_to_private_thread(
        self, send_sms, send_push
    ):
        self.client.force_login(self.other_member)
        url = self._url("conversation_details", self.member_message)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

        response = self.client.get(self._url("message_details", self.member_message))
        self.assertEqual(response.status_code, 404)

        response = self.client.post(
            url,
            {"reply": "Not allowed", "receiver_email": self.admin.username},
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(
            GroupMessage.objects.filter(
                reply_to=self.member_message, sender=self.other_member
            ).exists()
        )
        send_sms.assert_not_called()
        send_push.assert_not_called()

    @patch("groups.views.send_web_push_to_user")
    @patch("groups.views.send_text_message")
    def test_cannot_reply_to_message_from_another_group(self, send_sms, send_push):
        other_group = Group.objects.create(name="Private", owner=self.admin)
        foreign_message = GroupMessage.objects.create(
            group=other_group,
            sender=self.admin,
            message="Not in this group",
            message_type="AM",
        )
        self.client.force_login(self.member)

        url = reverse(
            "conversation_details",
            kwargs={"group_id": self.group.id, "message_id": foreign_message.id},
        )
        response = self.client.post(
            url, {"reply": "Cross-group reply", "receiver_email": self.admin.username}
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(GroupMessage.objects.filter(reply_to=foreign_message).exists())
        send_sms.assert_not_called()
        send_push.assert_not_called()


class EventRSVPAdminRosterAndMessagingTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="rsvp-admin@example.com",
            first_name="Admin",
            last_name="One",
            password="pw",
            contact_number="+12025550301",
        )
        self.going_member = User.objects.create_user(
            username="going@example.com",
            first_name="Going",
            last_name="Member",
            password="pw",
            contact_number="+12025550302",
        )
        self.maybe_member = User.objects.create_user(
            username="maybe@example.com",
            first_name="Maybe",
            last_name="Member",
            password="pw",
            contact_number="+12025550303",
        )
        self.not_going_member = User.objects.create_user(
            username="no@example.com",
            first_name="NotGoing",
            last_name="Member",
            password="pw",
            contact_number="+12025550304",
        )
        self.group = Group.objects.create(name="RSVP Messaging", owner=self.admin)
        GroupMember.objects.create(
            user=self.admin, group=self.group, owner=True, is_admin=True
        )
        GroupMember.objects.create(user=self.going_member, group=self.group)
        GroupMember.objects.create(user=self.maybe_member, group=self.group)
        GroupMember.objects.create(user=self.not_going_member, group=self.group)
        self.event = GroupEvent.objects.create(
            group=self.group,
            name=" Gala ",
            event_time="2026-12-10T18:00:00Z",
        )
        GroupEventRSVP.objects.create(
            event=self.event,
            user=self.going_member,
            status=GroupEventRSVP.Status.GOING,
        )
        GroupEventRSVP.objects.create(
            event=self.event,
            user=self.maybe_member,
            status=GroupEventRSVP.Status.MAYBE,
        )
        GroupEventRSVP.objects.create(
            event=self.event,
            user=self.not_going_member,
            status=GroupEventRSVP.Status.NOT_GOING,
        )

    def test_admin_sees_who_rsvped_while_regular_member_only_sees_counts(self):
        self.client.force_login(self.admin)
        admin_resp = self.client.get(reverse("view_group", args=[self.group.id]))
        self.assertEqual(admin_resp.status_code, 200)
        self.assertContains(admin_resp, "Going Member: Going")
        self.assertContains(admin_resp, "Maybe Member: Maybe")
        self.assertContains(admin_resp, "NotGoing Member: Not Going")

        self.client.force_login(self.going_member)
        member_resp = self.client.get(reverse("view_group", args=[self.group.id]))
        self.assertEqual(member_resp.status_code, 200)
        self.assertNotContains(member_resp, "Maybe Member: Maybe")

    @patch("groups.views.send_web_push_to_user")
    @patch("groups.views.send_text_message")
    def test_admin_can_send_message_filtered_by_event_rsvp_status(
        self, send_sms, send_push
    ):
        self.client.force_login(self.admin)
        url = reverse("send_message", kwargs={"group_id": self.group.id})
        response = self.client.post(
            url,
            {
                "message": "Update for attendees",
                "event_id": str(self.event.id),
                "rsvp_status": "GOING",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            [call.args[0] for call in send_sms.call_args_list],
            [self.going_member.contact_number],
        )
        self.assertEqual(
            [call.args[0] for call in send_push.call_args_list],
            [self.going_member],
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_readding_or_reinviting_removed_member_reactivates_without_integrity_error(
        self,
    ):
        membership = GroupMember.objects.get(group=self.group, user=self.going_member)
        membership.is_deleted = True
        membership.save()

        self.client.force_login(self.admin)
        add_resp = self.client.post(
            reverse("add_group_member", kwargs={"group_id": self.group.id}),
            {"email": self.going_member.username, "is_admin": "on"},
        )
        self.assertEqual(add_resp.status_code, 302)
        membership.refresh_from_db()
        self.assertFalse(membership.is_deleted)
        self.assertTrue(membership.is_admin)


class EventDateHandlingAndRangeTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="dates-owner@example.com", password="pw"
        )
        self.client.force_login(self.owner)

    def test_create_group_allows_events_with_and_without_event_time(self):
        response = self.client.post(
            reverse("create_group"),
            {
                "name": "Reunion Weekend",
                "description": "<p>Family trip</p>",
                "venue": "Lake Tahoe",
                "event_id[]": ["0", "0"],
                "event_name[]": ["Welcome Dinner", "Open Afternoon"],
                "event_time[]": ["06/12/2026 06:00 PM", ""],
                "event_instructions[]": ["Casual", ""],
                "event_venue_name[]": ["Lodge", ""],
                "event_venue_address[]": ["100 Lake Rd", ""],
                "event_venue_map[]": ["", ""],
            },
        )
        self.assertEqual(response.status_code, 302)
        group = Group.objects.get(name="Reunion Weekend")
        dinner = GroupEvent.objects.get(group=group, name="Welcome Dinner")
        afternoon = GroupEvent.objects.get(group=group, name="Open Afternoon")
        self.assertIsNotNone(dinner.event_time)
        self.assertIsNone(afternoon.event_time)

    def test_view_group_displays_overall_event_date_range(self):
        group = Group.objects.create(name="Conference", owner=self.owner)
        GroupMember.objects.create(
            user=self.owner, group=group, owner=True, is_admin=True
        )
        GroupEvent.objects.create(
            group=group,
            name="Day 1 Keynote",
            event_time="2026-09-10T09:00:00Z",
        )
        GroupEvent.objects.create(
            group=group,
            name="Day 3 Closing",
            event_time="2026-09-12T17:00:00Z",
        )
        response = self.client.get(reverse("view_group", args=[group.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sep 10, 2026 – Sep 12, 2026")
