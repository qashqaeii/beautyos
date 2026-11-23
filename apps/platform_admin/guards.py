from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def platform_required(view):
    """Staff and salon ownership do not confer platform operator privileges."""

    @wraps(view)
    @login_required
    def wrapped(request, *args, **kwargs):
        if not request.user.is_active or not request.user.is_superuser:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapped
