#!/usr/bin/env python3
"""Read-only Phase 8 HTTP smoke probe. Never sends credentials or writes data."""
import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


def check_target(url, allow_local_http=False):
    parts = urlsplit(url)
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("Base URL must not contain credentials, query or fragment.")
    local = parts.hostname in {"localhost", "127.0.0.1", "::1"}
    if parts.scheme != "https" and not (
        allow_local_http and local and parts.scheme == "http"
    ):
        raise ValueError("HTTPS is mandatory except explicitly authorized local HTTP.")
    if not parts.hostname or parts.path not in ("", "/"):
        raise ValueError("Provide the root origin only, without a path.")
    return urlunsplit((parts.scheme, parts.netloc, "", "", ""))


def probe(origin, path, timeout):
    request = Request(origin + path, headers={"Accept": "application/json"}, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                return False, f"HTTP {response.status}"
            if urlsplit(response.url).netloc != urlsplit(origin).netloc:
                return False, "cross-origin redirect"
            payload = json.loads(response.read(4096).decode("utf-8"))
            if payload != {"status": "ok"}:
                return False, "unexpected health payload"
            return True, "ok"
    except (HTTPError, URLError, TimeoutError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return False, type(exc).__name__


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only BeautyOS liveness/readiness check.")
    parser.add_argument("--base-url", required=True, help="Staging HTTPS origin, e.g. https://staging.example.com")
    parser.add_argument("--allow-local-http", action="store_true", help="Only for localhost/127.0.0.1 testing")
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args(argv)
    if not 0 < args.timeout <= 30:
        parser.error("--timeout must be between 0 and 30 seconds.")
    try:
        origin = check_target(args.base_url, args.allow_local_http)
    except ValueError as exc:
        parser.error(str(exc))
    failed = False
    for path in ("/health/", "/health/ready/"):
        ok, reason = probe(origin, path, args.timeout)
        print(f"{path}  {'PASS' if ok else 'FAIL'} ({reason})")
        failed |= not ok
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
