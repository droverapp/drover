from django import template

register = template.Library()


@register.filter
def get_item(dict_or_obj, key):
    """Template filter: dict|get_item:"key" or dict|get_item:key

    Works with both dict (key lookup) and object attribute fallback.
    Used for RSVP count/status lookups in event templates.
    """
    if dict_or_obj is None:
        return None
    if isinstance(dict_or_obj, dict):
        # Try both string and original key types
        if key in dict_or_obj:
            return dict_or_obj[key]
        return dict_or_obj.get(str(key))
    # Fallback: try attribute
    return getattr(dict_or_obj, key, None)