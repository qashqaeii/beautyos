"""Tests for phase-eight read-only deployment probe."""
import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest


SPEC = importlib.util.spec_from_file_location(
    "staging_smoke", Path(__file__).resolve().parents[1] / "scripts" / "staging_smoke.py"
)
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


@pytest.mark.parametrize("url", [
    "http://staging.example.invalid",
    "https://user:pass@staging.example.invalid",
    "https://staging.example.invalid/health/",
    "https://staging.example.invalid/?token=abc",
    "https://staging.example.invalid/#secret",
])
def test_probe_refuses_unsafe_or_non_root_url(url):
    with pytest.raises(ValueError):
        smoke.check_target(url)


def test_probe_allows_https_staging_and_explicit_local_http():
    assert smoke.check_target("https://staging.example.invalid") == "https://staging.example.invalid"
    with pytest.raises(ValueError):
        smoke.check_target("http://127.0.0.1:8000")
    assert smoke.check_target("http://127.0.0.1:8000", True) == "http://127.0.0.1:8000"


def test_health_probe_checks_expected_json_and_does_not_use_post():
    class Response:
        status = 200
        url = "https://staging.example.invalid/health/"
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def read(self, size):
            return b'{"status":"ok"}'

    with patch.object(smoke, "urlopen", return_value=Response()) as fetch:
        ok, info = smoke.probe("https://staging.example.invalid", "/health/", 2)
        assert (ok, info) == (True, "ok")
        assert fetch.call_args.args[0].get_method() == "GET"


def test_smoke_fails_closed_on_unavailable_probe(capsys):
    with patch.object(smoke, "probe", side_effect=[
        (True, "ok"), (False, "HTTPError"),
    ]):
        assert smoke.main(["--base-url", "https://staging.example.invalid"]) == 1
    assert "FAIL" in capsys.readouterr().out
