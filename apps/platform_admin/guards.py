from functools import wraps

from django.shortcuts import redirect
from django.urls import reverse
from django.core.exceptions import PermissionDenied


def platform_required(view):
    """Staff and salon ownership do not confer platform operator privileges."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(reverse('platform_admin:login'))
        if not request.user.is_active or not request.user.is_superuser:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapped
