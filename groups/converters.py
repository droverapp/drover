class RSVPStatusConverter:
    """Path converter that only matches valid RSVP status slugs.

    Using this converter (instead of <str:status>) makes reverse() raise
    NoReverseMatch for invalid statuses and returns 404 for garbage URLs.
    """
    regex = "going|not_going|maybe"

    def to_python(self, value):
        return value

    def to_url(self, value):
        if value not in ("going", "not_going", "maybe"):
            raise ValueError(f"Invalid RSVP status: {value}")
        return value
