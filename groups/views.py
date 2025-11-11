import datetime
import bleach

from django.db.models import Q, Count, OuterRef, Subquery
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from users.models import User

from .models import Group, GroupMember, GroupSchedule, GroupMessage, GroupMessageImage
from .emails import send_invitation_email
from .sms import send_text_message
from shortener.utils import generate_short_url


@login_required
def create_group(request):
    if request.method == "POST":
        event_date = (
            datetime.datetime.strptime(
                request.POST["event_date"], "%m/%d/%Y %I:%M %p"
            ).strftime("%Y-%m-%d %H:%M")
            if request.POST["event_date"]
            else None
        )
        group = Group(
            name=request.POST["name"],
            event_date=event_date,
            description=bleach.clean(request.POST["description"], tags=["p", "strong", "i", "u", "b", "em", "a"]),
            #image=request.FILES["group_image"],
            venue=request.POST["venue"],
            owner=request.user,
        )
        group.save()
        group_member = GroupMember(user=request.user, is_admin=True, group=group)
        group_member.save()
        for index in range(len(request.POST.getlist("schedule_name[]"))):
            schedule_time = datetime.datetime.strptime(
                request.POST.getlist("schedule_time[]")[index], "%m/%d/%Y %I:%M %p"
            ).strftime("%Y-%m-%d %H:%M")
            schedule = GroupSchedule(
                name=request.POST.getlist("schedule_name[]")[index],
                schedule_time=schedule_time,
                instructions=request.POST.getlist("schedule_instructions[]")[index],
                venue_name=request.POST.getlist("schedule_venue_name[]")[index],
                venue_address=request.POST.getlist("schedule_venue_address[]")[index],
                venue_map_link=request.POST.getlist("schedule_venue_map[]")[index],
                group=group,
            )
            schedule.save()

        return redirect("dashboard")
    return render(request, "create_group.html")


@login_required
def edit_group(request, group_id):
    group = Group.objects.filter(group_id=group_id).first()
    group_member = GroupMember.objects.filter(
        group=group, user=request.user, is_deleted=False
    ).first()
    if group_member and group_member.is_admin:
        group_members = group.groupmember_set.filter(is_deleted=False).all()
        schedules = group.groupschedule_set.all().order_by("schedule_time")
        if request.method == "POST":
            if request.POST["event_date"]:
                group.event_date = datetime.datetime.strptime(
                    request.POST["event_date"], "%m/%d/%Y %I:%M %p"
                ).strftime("%Y-%m-%d %H:%M")
            #group.image = request.FILES["group_image"]
            group.description = bleach.clean(request.POST["description"], tags=["p", "strong", "i", "u", "b", "em", "a"])
            group.venue = request.POST["venue"]
            group.save()

            for index in range(len(request.POST.getlist("schedule_name[]"))):
                if request.POST.getlist("schedule_time[]")[index]:
                    schedule_time = datetime.datetime.strptime(
                        request.POST.getlist("schedule_time[]")[index],
                        "%m/%d/%Y %I:%M %p",
                    ).strftime("%Y-%m-%d %H:%M")
                schedule_id = int(request.POST.getlist("schedule_id[]")[index])
                if schedule_id == 0:
                    # new schedule
                    schedule_time = datetime.datetime.strptime(
                        request.POST.getlist("schedule_time[]")[index],
                        "%m/%d/%Y %I:%M %p",
                    ).strftime("%Y-%m-%d %H:%M")
                    schedule = GroupSchedule(
                        name=request.POST.getlist("schedule_name[]")[index],
                        schedule_time=schedule_time,
                        instructions=request.POST.getlist("schedule_instructions[]")[
                            index
                        ],
                        venue_name=request.POST.getlist("schedule_venue_name[]")[index],
                        venue_address=request.POST.getlist("schedule_venue_address[]")[
                            index
                        ],
                        venue_map_link=request.POST.getlist("schedule_venue_map[]")[
                            index
                        ],
                        group=group,
                    )
                    schedule.save()
                else:
                    # old schedule
                    schedule = GroupSchedule.objects.filter(id=schedule_id).first()
                    if schedule:
                        schedule.name = request.POST.getlist("schedule_name[]")[index]
                        schedule.schedule_time = schedule_time
                        schedule.instructions = request.POST.getlist(
                            "schedule_instructions[]"
                        )[index]
                        schedule.venue_name = request.POST.getlist(
                            "schedule_venue_name[]"
                        )[index]
                        schedule.venue_address = request.POST.getlist(
                            "schedule_venue_address[]"
                        )[index]
                        schedule.venue_map_link = request.POST.getlist(
                            "schedule_venue_map[]"
                        )[index]
                        schedule.save()

            # Edit Old Schedules if changed

            return redirect("view_group", group.group_id)
        return render(
            request,
            "edit_group.html",
            {"group": group, "group_members": group_members, "schedules": schedules},
        )
    return redirect("dashboard")


@login_required
def view_group(request, group_id):
    group = Group.objects.filter(group_id=group_id).first()
    group_member = GroupMember.objects.filter(
        group=group, user=request.user, is_deleted=False
    ).first()
    if group_member:
        group_members = group.groupmember_set.filter(is_deleted=False).all()
        schedules = group.groupschedule_set.all().order_by("schedule_time")
        return render(
            request,
            "view_group.html",
            {
                "group": group,
                "is_admin": group_member.is_admin,
                "group_members": group_members,
                "schedules": schedules,
            },
        )
    return redirect("dashboard")


@login_required
def add_group_member(request, group_id):
    group = Group.objects.filter(group_id=group_id).first()
    current_group_member = GroupMember.objects.filter(
        group=group, user=request.user, is_deleted=False
    ).first()
    if current_group_member and current_group_member.is_admin:
        invite_url = "{}://{}{}".format(
            request.scheme, request.get_host(), group.get_invite_url()
        )
        if request.method == "POST":
            user = User.objects.filter(username=request.POST["email"]).first()
            if user:
                new_group_member = GroupMember(
                    user=user, group=group, is_admin=request.POST.get("is_admin", False)
                )
                new_group_member.save()
                send_invitation_email(
                    group.name,
                    "invites@droverapp.com",
                    [request.POST["email"]],
                )
            else:
                send_invitation_email(
                    group.name,
                    "invites@droverapp.com",
                    [request.POST["email"]],
                    invite_url,
                )
            return redirect("view_group", group.group_id)
        return render(request, "add_member.html")
    return redirect("dashboard")


@login_required
def edit_group_member(request, group_id, member_id):
    group = Group.objects.filter(group_id=group_id).first()
    current_group_member = GroupMember.objects.filter(
        group=group, user=request.user, is_deleted=False
    ).first()
    if current_group_member and current_group_member.is_admin:
        member = GroupMember.objects.filter(
            group=group, member_id=member_id, is_deleted=False
        ).first()
        if member:
            if request.method == "POST":
                member.is_admin = request.POST.get("is_admin", None) == "on"
                member.save()
                return redirect("edit_group", group.group_id)
            return render(
                request, "edit_member.html", {"member": member, "group": group}
            )
    return redirect("dashboard")


@login_required
@require_http_methods(["POST"])
def remove_group_member(request, group_id, member_id):
    if request.method == "POST":
        group = Group.objects.filter(group_id=group_id).first()
        current_group_member = GroupMember.objects.filter(
            group=group, user=request.user, is_deleted=False
        ).first()
        if current_group_member and current_group_member.is_admin:
            member = GroupMember.objects.filter(
                group=group, member_id=member_id, is_deleted=False
            ).first()
            if member:
                member.is_deleted = True
                member.save()
                return redirect("edit_group", group.group_id)
    return redirect("dashboard")


@login_required
def send_message(request, group_id):
    group = Group.objects.filter(group_id=group_id).first()
    current_group_member = GroupMember.objects.filter(
        group=group, user=request.user, is_deleted=False
    ).first()
    if current_group_member:
        if request.method == "POST":
            message_type = "AM" if current_group_member.is_admin else "MA"
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
                    group_message=message,
                    image=request.FILES["message-image"]
                )
                message_image.save()
            
            message_receivers = GroupMember.objects.filter(
                group=group, is_admin=message_type == "MA", is_deleted=False
            )
            message_url = "{}://{}{}".format(
                request.scheme,
                request.get_host(),
                generate_short_url(
                    reverse(
                        "conversation_details",
                        kwargs={
                            "group_id": group.group_id,
                            "message_id": message.message_id,
                        },
                    )
                ),
            )
            for receiver in message_receivers:
                send_text_message(
                    receiver.user.contact_number, request.POST["message"], message_url
                )
            return redirect("view_group", group.group_id)
        return render(
            request, "compose_message.html", {"is_admin": current_group_member.is_admin}
        )
    return redirect("dashboard")


@login_required
def invite(request, group_id):
    group = Group.objects.filter(group_id=group_id).first()
    current_group_member = GroupMember.objects.filter(
        group=group, user=request.user, is_deleted=False
    ).first()
    if group and not current_group_member:
        if request.method == "POST":
            new_group_member = GroupMember(
                user=request.user, group=group, is_admin=False
            )
            new_group_member.save()
            return redirect("view_group", group.group_id)
        return render(request, "group_invite.html", {"group_name": group.name})
    return redirect("dashboard")


@login_required
def inbox(request, group_id):
    group = Group.objects.filter(group_id=group_id).first()
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
    group = Group.objects.filter(group_id=group_id).first()
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
                        GroupMessage.objects.filter(reply_to=OuterRef("message_id"))
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
                        GroupMessage.objects.filter(reply_to=OuterRef("message_id"))
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
                        GroupMessage.objects.filter(reply_to=OuterRef("message_id"))
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
                        GroupMessage.objects.filter(reply_to=OuterRef("message_id"))
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
    group = Group.objects.filter(group_id=group_id).first()
    current_group_member = GroupMember.objects.filter(
        group=group, user=request.user, is_deleted=False
    ).first()
    if current_group_member:
        if request.method == "POST":
            message_type = "AM" if current_group_member.is_admin else "MA"
            receiver = User.objects.filter(
                username=request.POST["receiver_email"]
            ).first()
            message = GroupMessage(
                message=request.POST["reply"],
                sender=request.user,
                receiver=receiver,
                reply_to=message_id,
                group=group,
                message_time=datetime.datetime.now(),
                message_type=message_type,
            )
            message.save()

            message_url = "{}://{}{}".format(
                request.scheme,
                request.get_host(),
                generate_short_url(
                    reverse(
                        "message_details",
                        kwargs={
                            "group_id": group.group_id,
                            "message_id": message.message_id,
                        },
                    )
                ),
            )
            send_text_message(
                receiver.contact_number, request.POST["reply"], message_url
            )
            return redirect("view_group", group.group_id)
        if current_group_member.is_admin:
            message = GroupMessage.objects.filter(
                group=group, message_id=message_id
            ).first()
        else:
            message = GroupMessage.objects.filter(
                group=group, message_id=message_id
            ).first()

        return render(
            request, "message_details.html", {"group": group, "message": message}
        )
    return redirect("dashboard")


@login_required
def conversation_details(request, group_id, message_id):
    group = Group.objects.filter(group_id=group_id).first()
    current_group_member = GroupMember.objects.filter(
        group=group, user=request.user, is_deleted=False
    ).first()
    if current_group_member:
        if request.method == "POST":
            message_type = "AM" if current_group_member.is_admin else "MA"
            receiver = User.objects.filter(
                username=request.POST["receiver_email"]
            ).first()
            message = GroupMessage(
                message=request.POST["reply"],
                sender=request.user,
                receiver=receiver,
                reply_to=message_id,
                group=group,
                message_time=datetime.datetime.now(),
                message_type=message_type,
            )
            message.save()

            message_url = "{}://{}{}".format(
                request.scheme,
                request.get_host(),
                generate_short_url(
                    reverse(
                        "conversation_details",
                        kwargs={
                            "group_id": group.group_id,
                            "message_id": message.message_id,
                        },
                    )
                ),
            )
            send_text_message(
                receiver.contact_number, request.POST["reply"], message_url
            )
            return redirect("conversation_details", group_id, message_id)
        message = GroupMessage.objects.filter(
            group=group, message_id=message_id
        ).first()
        conversations = (
            GroupMessage.objects.filter(group=group, reply_to=message_id)
            .filter(Q(sender=request.user) | Q(receiver=request.user))
            .all()
        )

        sender = message.sender
        if sender == request.user:
            for conversation in conversations:
                if (
                    conversation.sender != request.user
                    and message.message_type != conversation.message_type
                ):
                    sender = conversation.sender
                    break

        return render(
            request,
            "conversation_details.html",
            {
                "group": group,
                "message": message,
                "conversations": conversations,
                "sender": sender,
            },
        )
    return redirect("dashboard")
