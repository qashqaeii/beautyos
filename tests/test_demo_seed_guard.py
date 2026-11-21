"""Do not allow demo data mutation in production-like settings."""
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings


@pytest.mark.parametrize("command", ["seed_demo", "seed_demo_salon"])
@pytest.mark.parametrize(
    ("debug", "opted_in"),
    [(False, False), (False, True), (True, False)],
)
def test_demo_seed_denied_outside_explicit_local_debug(monkeypatch, command, debug, opted_in):
    # An old operator-level environment flag is not authorization to mutate a DB.
    monkeypatch.setenv("ALLOW_DEMO_SEED", "1")
    with override_settings(DEBUG=debug, ALLOW_DEMO_SEED=opted_in):
        with pytest.raises(CommandError, match="disabled in production"):
            call_command(command, "--dry-run", verbosity=0)


@pytest.mark.parametrize("command", ["seed_demo", "seed_demo_salon"])
def test_demo_seed_can_dry_run_in_opted_in_debug(monkeypatch, command):
    monkeypatch.delenv("ALLOW_DEMO_SEED", raising=False)
    with override_settings(DEBUG=True, ALLOW_DEMO_SEED=True):
        call_command(command, "--dry-run", verbosity=0)
