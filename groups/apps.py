from django.apps import AppConfig


class GroupsConfig(AppConfig):
    name = "groups"

    def ready(self):
        from django.urls import register_converter
        from .converters import RSVPStatusConverter

        register_converter(RSVPStatusConverter, "rsvstatus")
