"""Fail-closed gateway registry for subscription payments.

No provider is enabled until its server-to-server adapter is implemented and
registered here. Browser redirects are never trusted payment evidence.
"""
from django.core.exceptions import ImproperlyConfigured, ValidationError


class GatewayVerificationError(ValidationError):
    pass


def verify_subscription_payment(*, provider, order):
    """Return verified evidence only after a real provider-side API verification.

    This entrypoint deliberately has no fallback or mock implementation in
    production. Adding a provider requires a reviewed, server-side adapter.
    """
    if provider not in SUPPORTED_PROVIDERS:
        raise GatewayVerificationError("درگاه پرداخت پشتیبانی نمی‌شود.")
    adapter = SUPPORTED_PROVIDERS[provider]
    if adapter is None:
        raise ImproperlyConfigured("درگاه پرداخت هنوز پیکربندی نشده است.")
    return adapter.verify(order=order)


# Deliberately empty until a real merchant account and provider are selected.
SUPPORTED_PROVIDERS = {}
