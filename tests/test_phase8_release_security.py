"""Phase eight release gates: deterministic checks without production access."""
import pytest
from django.test import override_settings

from apps.core.management.commands.release_check import production_host_findings


@override_settings(
    ALLOWED_HOSTS=["beautyos.example.invalid"],
    CSRF_TRUSTED_ORIGINS=["https://beautyos.example.invalid"],
    SECURE_SSL_REDIRECT=True,
    SESSION_COOKIE_SECURE=True,
    CSRF_COOKIE_SECURE=True,
)
def test_release_https_host_gate_accepts_explicit_secure_configuration():
    assert production_host_findings() == []


@pytest.mark.parametrize("hosts", [
    ["*"],
    ["localhost", "127.0.0.1"],
    [".example.com"],
])
@override_settings(
    CSRF_TRUSTED_ORIGINS=["https://beautyos.example.invalid"],
    SECURE_SSL_REDIRECT=True, SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True,
)
def test_release_gate_rejects_unsafe_hosts(hosts):
    with override_settings(ALLOWED_HOSTS=hosts):
        assert any("ALLOWED_HOSTS" in error for error in production_host_findings())


@pytest.mark.parametrize("origins", [
    [], ["http://beautyos.example.invalid"],
    ["https://*.example.invalid"],
])
@override_settings(
    ALLOWED_HOSTS=["beautyos.example.invalid"],
    SECURE_SSL_REDIRECT=True, SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True,
)
def test_release_gate_rejects_unsafe_csrf_origins(origins):
    with override_settings(CSRF_TRUSTED_ORIGINS=origins):
        assert any("CSRF_TRUSTED_ORIGINS" in error for error in production_host_findings())


@override_settings(
    ALLOWED_HOSTS=["beautyos.example.invalid"],
    CSRF_TRUSTED_ORIGINS=["https://beautyos.example.invalid"],
    SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False,
)
def test_release_gate_rejects_insecure_transport_and_cookies():
    findings = production_host_findings()
    assert any("SECURE_SSL_REDIRECT" in error for error in findings)
    assert any("cookies" in error for error in findings)
