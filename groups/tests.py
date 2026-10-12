"""
Integration tests for the GroupEvent RSVP workflow.

Covers status submission, membership access, rendered RSVP controls, idempotent
updates, group-page counts, and representative SQL query shapes.
"""

import uuid

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from inline_snapshot import snapshot
from inline_snapshot_django import snapshot_queries

from groups.models import Group, GroupMember, GroupEvent, GroupEventRSVP

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
