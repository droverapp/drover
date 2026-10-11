from django.urls import path
from . import views

urlpatterns = [
    path("create/", views.create_group, name="create_group"),
    path("<uuid:group_id>", views.view_group, name="view_group"),
    path("<uuid:group_id>/edit/", views.edit_group, name="edit_group"),
    path("<uuid:group_id>/add-member/", views.add_group_member, name="add_group_member"),
    path(
        "<uuid:group_id>/edit-member/<uuid:member_id>",
        views.edit_group_member,
        name="edit_group_member",
    ),
    path(
        "<uuid:group_id>/remove-member/<uuid:member_id>",
        views.remove_group_member,
        name="remove_group_member",
    ),
    path("<uuid:group_id>/send-message/", views.send_message, name="send_message"),
    path("<uuid:group_id>/invite/", views.invite, name="invite"),
    path("<uuid:group_id>/inbox/", views.inbox, name="inbox"),
    path(
        "<uuid:group_id>/message/<uuid:message_id>", views.message_details, name="message_details"
    ),
    path("<uuid:group_id>/conversation/", views.conversations, name="conversations"),
    path(
        "<uuid:group_id>/conversation/<uuid:message_id>",
        views.conversation_details,
        name="conversation_details",
    ),
    path(
        "<uuid:group_id>/event/<uuid:event_id>/rsvp/<rsvstatus:status>/",
        views.rsvp_event,
        name="rsvp_event",
    ),
]
