"""Release 6 checks: probes, fail-closed production config and OTP transport."""
import os
import subprocess
import sys
from unittest.mock import patch
from urllib.parse import parse_qs

import pytest
from django.test import override_settings

from apps.accounts.sms import KavenegarOTPProvider


@pytest.mark.django_db
def test_health_liveness_and_readiness(client):
    live = client.get("/health/")
    ready = client.get("/health/ready/")
    assert live.status_code == 200
    assert live.json()["status"] == "ok"
    assert ready.status_code == 200
    assert ready.json() == {"status": "ok"}
    assert "no-cache" in ready.headers["Cache-Control"]


@pytest.mark.django_db
def test_readiness_fails_closed_without_exposing_database_details(client):
    with patch("apps.core.urls.connections") as db_connections:
        db_connections.__getitem__.side_effect = RuntimeError("secret-db-connection-detail")
        response = client.get("/health/ready/")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert "secret-db-connection-detail" not in response.content.decode()


def _production_settings_process(**changes):
    env = os.environ.copy()
    env.update({
        "DJANGO_SETTINGS_MODULE": "config.settings.production",
        "SECRET_KEY": "test-only-7ajMb2yN5kKr9PqsH4sUw3F6dZL1gSx0eCr8Qv2B",
        "DATABASE_URL": "postgresql://test:test@127.0.0.1:5432/test",
        "ALLOWED_HOSTS": "beautyos.example.invalid",
        "CSRF_TRUSTED_ORIGINS": "https://beautyos.example.invalid",
        "BEAUTYOS_SMS_PROVIDER": "apps.accounts.sms.KavenegarOTPProvider",
        "BEAUTYOS_KAVENEGAR_API_KEY": "test-only-no-messages-sent",
        "BEAUTYOS_KAVENEGAR_SENDER": "ci-only",
        "BEAUTYOS_AUTOMATION_SEND_ENABLED": "False",
    })
    env.update(changes)
    return subprocess.run(
        [sys.executable, "-c",
         "import django; django.setup(); from django.conf import settings; "
         "assert settings.DEBUG is False"],
        env=env, capture_output=True, text=True, timeout=30,
    )


def test_production_settings_requires_explicit_hosts():
    assert _production_settings_process().returncode == 0
    assert _production_settings_process(ALLOWED_HOSTS="localhost,127.0.0.1").returncode != 0
    assert _production_settings_process(ALLOWED_HOSTS="*").returncode != 0


def test_production_otp_gate_rejects_unsafe_provider_or_missing_credentials():
    assert _production_settings_process(
        BEAUTYOS_SMS_PROVIDER="apps.accounts.sms.DevSMSProvider").returncode != 0
    assert _production_settings_process(BEAUTYOS_KAVENEGAR_API_KEY="").returncode != 0


@override_settings(
    BEAUTYOS_KAVENEGAR_API_KEY="test-only-secret",
    BEAUTYOS_KAVENEGAR_SENDER="100000",
)
def test_kavenegar_otp_does_not_log_code_or_reuse_marketing_transport(capsys):
    with patch("urllib.request.urlopen") as urlopen:
        urlopen.return_value.__enter__.return_value.read.return_value = (
            b'{"return":{"status":200},"entries":[{"messageid":1234}]}'
        )
        KavenegarOTPProvider().send_otp("+989121234567", "123456", "login")
        request = urlopen.call_args.args[0]
        params = parse_qs(request.data.decode())
        assert params["receptor"] == ["09121234567"]
        assert params["sender"] == ["100000"]
        assert "123456" in params["message"][0]
    assert "123456" not in capsys.readouterr().out
