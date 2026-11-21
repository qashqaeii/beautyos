"""Demo data is allowed only with explicit non-production settings opt-in."""
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings


@pytest.mark.parametrize("command", ["seed_demo", "seed_demo_salon"])
@pytest.mark.parametrize("debug", [False, True])
def test_seed_denied_without_opt_in(monkeypatch, command, debug):
    monkeypatch.setenv("ALLOW_DEMO_SEED", "1")
    with override_settings(DEBUG=debug, ALLOW_DEMO_SEED=False):
        with pytest.raises(CommandError, match="disabled in production"):
            call_command(command, "--dry-run", verbosity=0)


@pytest.mark.parametrize("command", ["seed_demo", "seed_demo_salon"])
@pytest.mark.parametrize("debug", [False, True])
def test_seed_denied_in_production_even_if_opted_in(monkeypatch, command, debug):
    # Test the command guard directly without loading production configuration.
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "config.settings.production")
    monkeypatch.setenv("ALLOW_DEMO_SEED", "1")
    with override_settings(DEBUG=debug, ALLOW_DEMO_SEED=True):
        with pytest.raises(CommandError, match="disabled in production"):
            call_command(command, "--dry-run", verbosity=0)


@pytest.mark.django_db
@pytest.mark.parametrize("command", ["seed_demo", "seed_demo_salon"])
def test_demo_seed_can_dry_run_with_explicit_nonproduction_opt_in(monkeypatch, command):
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "config.settings.local")
    monkeypatch.delenv("ALLOW_DEMO_SEED", raising=False)
    # pytest-django forces DEBUG=False during normal tests; explicit local
    # ALLOW_DEMO_SEED still permits the existing seeded test data.
    from apps.accounts.models import User
    from apps.salons.models import Salon
    users_before, salons_before = User.objects.count(), Salon.objects.count()
    with override_settings(DEBUG=False, ALLOW_DEMO_SEED=True):
        call_command(command, "--dry-run", verbosity=0)
    assert User.objects.count() == users_before
    assert Salon.objects.count() == salons_before
