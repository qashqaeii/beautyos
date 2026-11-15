from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import reverse


def salon_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if request.salon is None:
            return redirect(reverse("salons_onboarding:create"))
        return view_func(request, *args, **kwargs)

    return _wrapped
