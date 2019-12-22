from django.contrib import admin
from .models import Group, GroupMember, GroupSchedule

admin.site.register(Group)
admin.site.register(GroupMember)
admin.site.register(GroupSchedule)
