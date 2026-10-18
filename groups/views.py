import datetime
import uuid
from urllib.parse import urlsplit

import bleach
from django.contrib.auth.decorators import login_required
from django.db.models import (
    Case,
    CharField,
    Count,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
)
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from shortener.utils import generate_short_url
from users.models import User
from users.push import send_web_push_to_user

from .emails import send_invitation_email
from .models import (
    Group,
    GroupEvent,
    GroupEventRSVP,
    GroupMember,
    GroupMessage,
    GroupMessageImage,
)
from .sms import send_text_message


def _sanitize_map_link(raw_url):
    if not isinstance(raw_url, str):
        return ""
    candidate = raw_url.strip()
    if not candidate:
        return ""
    parsed = urlsplit(candidate)
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return candidate
    if (
        parsed.scheme == ""
        and parsed.netloc == ""
        and candidate.startswith("/mapview/")
    ):
        return candidate
    return ""


@login_required
def create_group(request):
    if request.method == "POST":
        group = Group(
            name=request.POST["name"],
            description=bleach.clean(
                request.POST["description"],
                tags=["p", "strong", "i", "u", "b", "em", "a"],
            ),
            # image=request.FILES["group_image"],
            venue=request.POST["venue"],
            owner=request.user,
        )
        group.save()
        group_member = GroupMember(
            user=request.user, is_admin=True, owner=True, group=group
        )
        group_member.save()
        for index in range(len(request.POST.getlist("event_name[]"))):
            event_time = datetime.datetime.strptime(
                request.POST.getlist("event_time[]")[index], "%m/%d/%Y %I:%M %p"
            ).strftime("%Y-%m-%d %H:%M")
            event = GroupEvent(
                name=request.POST.getlist("event_name[]")[index],
                event_time=event_time,
                instructions=request.POST.getlist("event_instructions[]")[index],
                venue_name=request.POST.getlist("event_venue_name[]")[index],
                venue_address=request.POST.getlist("event_venue_address[]")[index],
                venue_map_link=_sanitize_map_link(
                    request.POST.getlist("event_venue_map[]")[index]
                ),
                group=group,
            )
            event.save()

        return redirect("dashboard")
    return render(request, "create_group.html")


@login_required
def edit_group(request, group_id):
    group = Group.objects.filter(id=group_id).first()
    group_member = GroupMember.objects.filter(
        group=group, user=request.user, is_deleted=False
    ).first()
    if group_member and group_member.is_admin:
        group_members = group.members.filter(is_deleted=False).all()
        events = group.events.all().order_by("event_time")
        if request.method == "POST":
            # group.image = request.FILES["group_image"]
            group.description = bleach.clean(
                request.POST["description"],
                tags=["p", "strong", "i", "u", "b", "em", "a"],
            )
            group.venue = request.POST["venue"]
            group.save()

            for index in range(len(request.POST.getlist("event_name[]"))):
                if request.POST.getlist("event_time[]")[index]:
                    event_time = datetime.datetime.strptime(
                        request.POST.getlist("event_time[]")[index],
                        "%m/%d/%Y %I:%M %p",
                    ).strftime("%Y-%m-%d %H:%M")
                event_id_raw = request.POST.getlist("event_id[]")[index]
                if not event_id_raw or event_id_raw == "0":
                    # New event: "0"/"" is the frontend sentinel
                    # (static/js/add_event.js); no UUID-pk row can match it.
                    event_time = datetime.datetime.strptime(
                        request.POST.getlist("event_time[]")[index],
                        "%m/%d/%Y %I:%M %p",
                    ).strftime("%Y-%m-%d %H:%M")
                    event = GroupEvent(
                        name=request.POST.getlist("event_name[]")[index],
                        event_time=event_time,
                        instructions=request.POST.getlist("event_instructions[]")[
                            index
                        ],
                        venue_name=request.POST.getlist("event_venue_name[]")[index],
                        venue_address=request.POST.getlist("event_venue_address[]")[
                            index
                        ],
                        venue_map_link=_sanitize_map_link(
                            request.POST.getlist("event_venue_map[]")[index]
                        ),
                        group=group,
                    )
                    event.save()
                else:
                    # Existing event: id must be a valid UUID and must belong
                    # to this group; 404 immediately instead of skipping rows.
                    try:
                        event_id = uuid.UUID(event_id_raw)
                    except ValueError:
                        raise Http404(f"Invalid event id: {event_id_raw!r}")
                    event = get_object_or_404(GroupEvent, id=event_id, group=group)
                    event.name = request.POST.getlist("event_name[]")[index]
                    event.event_time = event_time
                    event.instructions = request.POST.getlist("event_instructions[]")[
                        index
                    ]
                    event.venue_name = request.POST.getlist("event_venue_name[]")[index]
                    event.venue_address = request.POST.getlist("event_venue_address[]")[
                        index
                    ]
                    event.venue_map_link = _sanitize_map_link(
                        request.POST.getlist("event_venue_map[]")[index]
                    )
                    event.save()

            # Edit Old Events if changed

            return redirect("view_group", group.id)
        return render(
            request,
            "edit_group.html",
            {"group": group, "group_members": group_members, "events": events},
        )
    return redirect("dashboard")


@login_required
def view_group(request, group_id):
    group = Group.objects.filter(id=group_id).first()
    group_member = GroupMember.objects.filter(
        group=group, user=request.user, is_deleted=False
    ).first()
    if group_member:
        group_members = group.members.filter(is_deleted=False).all()
        events = (
            group.events.all()
            .order_by("event_time")
            .annotate(
                going_count=Count(
                    "rsvps", filter=Q(rsvps__status=GroupEventRSVP.Status.GOING)
                ),
                not_going_count=Count(
                    "rsvps", filter=Q(rsvps__status=GroupEventRSVP.Status.NOT_GOING)
                ),
                maybe_count=Count(
                    "rsvps", filter=Q(rsvps__status=GroupEventRSVP.Status.MAYBE)
                ),
                my_rsvp_display=Subquery(
                    GroupEventRSVP.objects.filter(
                        event=OuterRef("pk"), user=request.user
                    )
                    .annotate(
                        display=Case(
                            When(
                                status=GroupEventRSVP.Status.GOING,
                                then=Value("Going"),
                            ),
                            When(
                                status=GroupEventRSVP.Status.NOT_GOING,
                                then=Value("Not Going"),
                            ),
                            When(
                                status=GroupEventRSVP.Status.MAYBE,
                                then=Value("Maybe"),
                            ),
                            default=Value(""),
                            output_field=CharField(),
                        )
                    )
                    .values("display")[:1]
                ),
            )
        )
        return render(
            request,
            "view_group.html",
            {
                "group": group,
                "is_admin": group_member.is_admin,
                "group_members": group_members,
                "events": events,
            },
        )
    return redirect("dashboard")


@login_required
def add_group_member(request, group_id):
    group = Group.objects.filter(id=group_id).first()
    current_group_member = GroupMember.objects.filter(
        group=group, user=request.user, is_deleted=False
    ).first()
    if current_group_member and current_group_member.is_admin:
        invite_url = f"{request.scheme}://{request.get_host()}{group.get_invite_url()}"
        if request.method == "POST":
            user = User.objects.filter(username=request.POST["email"]).first()
            if user:
                new_group_member = GroupMember(
                    user=user, group=group, is_admin=request.POST.get("is_admin", False)
                )
                new_group_member.save()
                send_invitation_email(
                    group.name,
                    "kathleen@droverapp.org",
                    [request.POST["email"]],
                )
            else:
                send_invitation_email(
                    group.name,
                    "kathleen@droverapp.org",
                    [request.POST["email"]],
                    invite_url,
                )
            return redirect("view_group", group.id)
        return render(request, "add_member.html")
    return redirect("dashboard")


@login_required
def edit_group_member(request, group_id, member_id):
    group = Group.objects.filter(id=group_id).first()
    current_dr_group_member = GroupMember.objects.filter(
        group=group, user=request.user, is_deleted=False
    ).first()
    if current_dr_group_member and current_dr_group_member.is_admin:
        member = GroupMember.objects.filter(
            group=group, id=member_id, is_deleted=False
        ).first()
        if member:
            if request.method == "POST":
                member.is_admin = request.POST.get("is_admin", None) == "on"
                member.save()
                return redirect("edit_group", group.id)
            return render(
                request, "edit_member.html", {"member": member, "group": group}
            )
    return redirect("dashboard")


@login_required
@require_http_methods(["POST"])
def remove_group_member(request, group_id, member_id):
    if request.method == "POST":
        group = Group.objects.filter(id=group_id).first()
        current_dr_group_member = GroupMember.objects.filter(
            group=group, user=request.user, is_deleted=False
        ).first()
        if current_dr_group_member and current_dr_group_member.is_admin:
            member = GroupMember.objects.filter(
                group=group, id=member_id, is_deleted=False
            ).first()
            if member:
                member.is_deleted = True
                member.save()
                return redirect("edit_group", group.id)
    return redirect("dashboard")


@login_required
def send_message(request, group_id):
    group = Group.objects.filter(id=group_id).first()
    current_dr_group_member = GroupMember.objects.filter(
        group=group, user=request.user, is_deleted=False
    ).first()
    if current_dr_group_member:
        if request.method == "POST":
            message_type = "AM" if current_dr_group_member.is_admin else "MA"
            message = GroupMessage(
                message=request.POST["message"],
                sender=request.user,
                group=group,
                message_time=datetime.datetime.now(),
                message_type=message_type,
            )
            message.save()

            print(request.FILES)
            if request.FILES.get("message-image", ""):
                print("I am there")
                message_image = GroupMessageImage(
                    group_message=message, image=request.FILES["message-image"]
                )
                message_image.save()

            message_receivers = GroupMember.objects.filter(
                group=group, is_admin=message_type == "MA", is_deleted=False
            )
            conversation_path = reverse(
                "conversation_details",
                kwargs={"group_id": group.id, "message_id": message.id},
            )
            message_url = f"{request.scheme}://{request.get_host()}{generate_short_url(conversation_path)}"
            for receiver in message_receivers:
                send_text_message(
                    receiver.user.contact_number, request.POST["message"], message_url
                )
                send_web_push_to_user(
                    receiver.user,
                    {
                        "title": "New Drover message",
                        "body": "Open Drover to view the message.",
                        "url": conversation_path,
                    },
                )
            return redirect("view_group", group.id)
        return render(
            request,
            "compose_message.html",
            {"is_admin": current_dr_group_member.is_admin},
        )
    return redirect("dashboard")


@login_required
def invite(request, group_id):
    group = Group.objects.filter(id=group_id).first()
    current_group_member = GroupMember.objects.filter(
        group=group, user=request.user, is_deleted=False
    ).first()
    if group and not current_group_member:
        if request.method == "POST":
            new_group_member = GroupMember(
                user=request.user, group=group, is_admin=False
            )
            new_group_member.save()
            return redirect("view_group", group.id)
        return render(request, "group_invite.html", {"group_name": group.name})
    return redirect("dashboard")


@login_required
def inbox(request, group_id):
    group = Group.objects.filter(id=group_id).first()
    current_group_member = GroupMember.objects.filter(
        group=group, user=request.user, is_deleted=False
    ).first()
    if current_group_member:
        if current_group_member.is_admin:
            sent_messages = (
                GroupMessage.objects.filter(group=group, message_type="AM")
                .all()
                .order_by("-message_time")
            )
            received_messages = (
                GroupMessage.objects.filter(group=group, message_type="MA")
                .all()
                .order_by("-message_time")
            )
        else:
            sent_messages = (
                GroupMessage.objects.filter(
                    group=group, message_type="MA", sender=request.user
                )
                .all()
                .order_by("-message_time")
            )
            received_messages = (
                GroupMessage.objects.filter(group=group, message_type="AM")
                .filter(Q(receiver=None) | Q(receiver=request.user))
                .all()
                .order_by("-message_time")
            )

        return render(
            request,
            "group_inbox.html",
            {
                "group": group,
                "sent_messages": sent_messages,
                "received_messages": received_messages,
            },
        )
    return redirect("dashboard")


@login_required
def conversations(request, group_id):
    group = Group.objects.filter(id=group_id).first()
    current_group_member = GroupMember.objects.filter(
        group=group, user=request.user, is_deleted=False
    ).first()
    if current_group_member:
        if current_group_member.is_admin:
            sent_messages = (
                GroupMessage.objects.filter(
                    group=group, message_type="AM", reply_to__isnull=True
                )
                .all()
                .order_by("-message_time")
                .annotate(
                    conversation_count=Subquery(
                        GroupMessage.objects.filter(reply_to=OuterRef("id"))
                        .values("reply_to")
                        .annotate(count=Count("pk"))
                        .values("count")
                    )
                )
            )
            received_messages = (
                GroupMessage.objects.filter(
                    group=group, message_type="MA", reply_to__isnull=True
                )
                .all()
                .order_by("-message_time")
                .annotate(
                    conversation_count=Subquery(
                        GroupMessage.objects.filter(reply_to=OuterRef("id"))
                        .values("reply_to")
                        .annotate(count=Count("pk"))
                        .values("count")
                    )
                )
            )
        else:
            sent_messages = (
                GroupMessage.objects.filter(
                    group=group,
                    message_type="MA",
                    sender=request.user,
                    reply_to__isnull=True,
                )
                .all()
                .order_by("-message_time")
                .annotate(
                    conversation_count=Subquery(
                        GroupMessage.objects.filter(reply_to=OuterRef("id"))
                        .values("reply_to")
                        .annotate(count=Count("pk"))
                        .values("count")
                    )
                )
            )
            received_messages = (
                GroupMessage.objects.filter(
                    group=group, message_type="AM", reply_to__isnull=True
                )
                .filter(Q(receiver=None) | Q(receiver=request.user))
                .all()
                .order_by("-message_time")
                .annotate(
                    conversation_count=Subquery(
                        GroupMessage.objects.filter(reply_to=OuterRef("id"))
                        .values("reply_to")
                        .annotate(count=Count("pk"))
                        .values("count")
                    )
                )
            )

        return render(
            request,
            "group_conversation.html",
            {
                "group": group,
                "sent_messages": sent_messages,
                "received_messages": received_messages,
            },
        )
    return redirect("dashboard")


@login_required
def message_details(request, group_id, message_id):
    group = Group.objects.filter(id=group_id).first()
    group_member = GroupMember.objects.filter(
        group=group, user=request.user, is_deleted=False
    ).first()
    if not group_member:
        return redirect("dashboard")

    message = _get_group_message_for_member(
        group, message_id, request.user, group_member
    )
    reply_recipient = _group_message_reply_recipient(
        message, request.user, group_member
    )
    if request.method == "POST":
        if not reply_recipient:
            return HttpResponseForbidden()

        reply = GroupMessage(
            message=request.POST["reply"],
            sender=request.user,
            receiver=reply_recipient,
            reply_to=message,
            group=group,
            message_time=datetime.datetime.now(),
            message_type="AM" if group_member.is_admin else "MA",
        )
        reply.save()

        message_url = "{}://{}{}".format(
            request.scheme,
            request.get_host(),
            generate_short_url(
                reverse(
                    "message_details",
                    kwargs={"group_id": group.id, "message_id": reply.id},
                )
            ),
        )
        send_text_message(
            reply_recipient.contact_number, request.POST["reply"], message_url
        )
        send_web_push_to_user(
            reply_recipient,
            {
                "title": "New Drover message",
                "body": "You have a new reply in Drover.",
                "url": reverse(
                    "conversation_details",
                    kwargs={"group_id": group.id, "message_id": message.id},
                ),
            },
        )
        return redirect("view_group", group.id)

    return render(
        request,
        "message_details.html",
        {"group": group, "message": message, "can_reply": reply_recipient is not None},
    )


@login_required
def conversation_details(request, group_id, message_id):
    group = Group.objects.filter(id=group_id).first()
    group_member = GroupMember.objects.filter(
        group=group, user=request.user, is_deleted=False
    ).first()
    if not group_member:
        return redirect("dashboard")

    message = _get_group_message_for_member(
        group, message_id, request.user, group_member
    )
    reply_recipient = _group_message_reply_recipient(
        message, request.user, group_member
    )
    if request.method == "POST":
        if not reply_recipient:
            return HttpResponseForbidden()

        reply = GroupMessage(
            message=request.POST["reply"],
            sender=request.user,
            receiver=reply_recipient,
            reply_to=message,
            group=group,
            message_time=datetime.datetime.now(),
            message_type="AM" if group_member.is_admin else "MA",
        )
        reply.save()

        message_url = "{}://{}{}".format(
            request.scheme,
            request.get_host(),
            generate_short_url(
                reverse(
                    "conversation_details",
                    kwargs={"group_id": group.id, "message_id": reply.id},
                )
            ),
        )
        send_text_message(
            reply_recipient.contact_number, request.POST["reply"], message_url
        )
        send_web_push_to_user(
            reply_recipient,
            {
                "title": "New Drover message",
                "body": "You have a new reply in Drover.",
                "url": reverse(
                    "conversation_details",
                    kwargs={"group_id": group.id, "message_id": message_id},
                ),
            },
        )
        return redirect("conversation_details", group_id, message_id)

    conversations = (
        GroupMessage.objects.filter(group=group, reply_to_id=message_id)
        .filter(Q(sender=request.user) | Q(receiver=request.user))
        .all()
    )
    return render(
        request,
        "conversation_details.html",
        {
            "group": group,
            "message": message,
            "conversations": conversations,
            "can_reply": reply_recipient is not None,
        },
    )


def _get_group_message_for_member(group, message_id, user, group_member):
    message = get_object_or_404(GroupMessage, group=group, id=message_id)
    if (
        not group_member.is_admin
        and message.sender_id != user.id
        and message.receiver_id != user.id
        and not (message.message_type == "AM" and message.receiver_id is None)
    ):
        raise Http404
    return message


def _group_message_reply_recipient(message, user, group_member):
    if message.sender_id == user.id:
        recipient = message.receiver
    else:
        recipient = message.sender

    if recipient is None or recipient.id == user.id:
        return None
    if not GroupMember.objects.filter(
        group=message.group, user=recipient, is_deleted=False
    ).exists():
        return None
    return recipient


@login_required
def rsvp_event(request, group_id, event_id):
    status = (
        request.POST.get("status")
        if request.method == "POST"
        else request.GET.get("status")
    )
    if status:
        status = status.upper()

    group = Group.objects.filter(id=group_id).first()
    if not group:
        return redirect("dashboard")

    event = GroupEvent.objects.filter(id=event_id, group=group).first()
    if not event:
        return redirect("view_group", group_id=group_id)

    group_member = GroupMember.objects.filter(
        group=group, user=request.user, is_deleted=False
    ).first()
    if not group_member:
        return HttpResponseForbidden()

    if request.method == "POST":
        if status not in GroupEventRSVP.Status.values:
            return redirect("view_group", group_id=group_id)

        rsvp, created = GroupEventRSVP.objects.get_or_create(
            event=event, user=request.user, defaults={"status": status}
        )
        if not created and rsvp.status != status:
            rsvp.status = status
            rsvp.save(update_fields=["status", "updated_at"])

    return redirect("view_group", group_id=group_id)
