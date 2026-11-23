#!/usr/bin/env python
"""Live smoke matrix for the Urban Air Quality Assistant.

Usage::

    python scripts/smoke.py http://127.0.0.1:8000

The script exits 0 only when every check in the matrix succeeds. It uses only
the standard library so it can run against a local uvicorn, a local container
or a deployed environment without installing anything.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT_SECONDS = 15.0

PROFILE = {
    "city": "Delhi",
    "climate_zone": "north",
    "children": True,
    "elderly": False,
    "respiratory": True,
    "commute_mode": "car",
    "commute_km": 10.0,
    "cooking_fuel": "wood",
    "heating_type": "none",
    "budget_level": "low",
}

CONTEXT = {"city": "Delhi", "band": "Poor", "season": "winter", "value": 250}


def _request(
    base_url: str,
    method: str,
    path: str,
    token: str | None = None,
    body: object | None = None,
) -> tuple[int, object]:
    """Perform one HTTP request and return ``(status, payload)``.

    Args:
        base_url: The environment base URL.
        method: The HTTP method.
        path: The request path.
        token: An optional bearer token.
        body: An optional JSON body.

    Returns:
        The status code and the decoded body (or raw text).
    """
    url = base_url.rstrip("/") + path
    if urllib.parse.urlsplit(url).scheme not in {"http", "https"}:
        raise ValueError(f"refusing non-HTTP smoke URL: {url}")
    data = None
    headers: dict[str, str] = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(  # noqa: S310 - scheme checked above
        url, data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(  # noqa: S310 - scheme checked above
            request, timeout=TIMEOUT_SECONDS
        ) as response:
            raw = response.read().decode("utf-8")
            status = response.status
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        status = exc.code
    try:
        payload: object = json.loads(raw) if raw else None
    except json.JSONDecodeError:
        payload = raw
    return status, payload


class _Checker:
    """Collect pass/fail results for the matrix."""

    def __init__(self) -> None:
        """Initialise the counters."""
        self.checks = 0
        self.failures = 0

    def check(self, label: str, condition: bool, detail: str = "") -> bool:
        """Record one check.

        Args:
            label: The human-readable check name.
            condition: Whether the check passed.
            detail: Extra context for a failure.

        Returns:
            The condition, for chaining.
        """
        self.checks += 1
        if condition:
            print(f"[PASS] {label}")
        else:
            self.failures += 1
            suffix = f" - {detail}" if detail else ""
            print(f"[FAIL] {label}{suffix}")
        return condition


def _register(base_url: str, email: str) -> tuple[int, object]:
    """Register a user.

    Args:
        base_url: The environment base URL.
        email: The account email.

    Returns:
        The status and body.
    """
    return _request(
        base_url,
        "POST",
        "/auth/register",
        body={"email": email, "password": "SmokePass123"},
    )


def smoke(base_url: str) -> int:
    """Run the smoke matrix against ``base_url``.

    Args:
        base_url: The environment base URL.

    Returns:
        0 when every check passes, 1 otherwise.
    """
    checker = _Checker()
    suffix = str(time.time_ns())

    status, body = _request(base_url, "GET", "/health")
    checker.check("GET /health is 200", status == 200, f"got {status}")
    if isinstance(body, dict):
        checker.check("health status is ok", body.get("status") == "ok")

    status, body = _register(base_url, f"smoke-{suffix}@example.com")
    checker.check("POST /auth/register is 201", status == 201, f"got {status}")
    token = body.get("token") if isinstance(body, dict) else None
    checker.check("register returns a token", bool(token))

    status, body = _request(
        base_url,
        "POST",
        "/auth/login",
        body={"email": f"smoke-{suffix}@example.com", "password": "SmokePass123"},
    )
    checker.check("POST /auth/login is 200", status == 200, f"got {status}")

    status, _ = _request(base_url, "GET", "/profile", token=token)
    checker.check("GET /profile before PUT is 404", status == 404, f"got {status}")

    status, body = _request(base_url, "PUT", "/profile", token=token, body=PROFILE)
    checker.check("PUT /profile is 200", status == 200, f"got {status}")

    status, _ = _request(base_url, "POST", "/air/context", token=token, body=CONTEXT)
    checker.check("POST /air/context is 200", status == 200, f"got {status}")

    status, body = _request(base_url, "GET", "/air?q=Delhi", token=token)
    checker.check("GET /air?q=Delhi is 200", status == 200, f"got {status}")
    if isinstance(body, dict):
        checker.check("GET /air reports a band", bool(body.get("band")))

    status, body = _request(base_url, "GET", "/plans", token=token)
    checker.check("GET /plans is 200", status == 200, f"got {status}")
    if isinstance(body, dict):
        checker.check(
            "GET /plans has three sections",
            all(body.get(section) for section in ("routines", "hacks", "alternatives")),
        )

    status, body = _request(
        base_url,
        "POST",
        "/ask",
        token=token,
        body={"question": "indoor air purifier"},
    )
    checker.check("POST /ask is 200", status == 200, f"got {status}")
    if isinstance(body, dict):
        checker.check("POST /ask is grounded", body.get("grounded") is True)

    status, body = _request(
        base_url,
        "POST",
        "/documents",
        token=token,
        body={"title": "Smoke note", "text": "smoke marker document"},
    )
    checker.check("POST /documents is 201", status == 201, f"got {status}")
    doc_id = body.get("id") if isinstance(body, dict) else None
    checker.check("document has an id", bool(doc_id))

    status, body = _request(base_url, "GET", "/documents", token=token)
    checker.check("GET /documents is 200", status == 200, f"got {status}")
    if isinstance(body, list):
        checker.check("GET /documents lists the note", len(body) == 1)

    status, _ = _request(base_url, "DELETE", f"/documents/{doc_id}", token=token)
    checker.check("DELETE /documents/{id} is 204", status == 204, f"got {status}")

    status, body = _request(base_url, "GET", "/export?format=json", token=token)
    checker.check("GET /export?format=json is 200", status == 200, f"got {status}")
    if isinstance(body, dict):
        checker.check("export has routines", bool(body.get("routines")))

    status, body = _request(base_url, "GET", "/profile")
    checker.check(
        "GET /profile without a token is 401",
        status == 401 and body == {"detail": "invalid credentials"},
        f"got {status}",
    )

    other_status, other_body = _register(base_url, f"smoke-other-{suffix}@example.com")
    other_token = other_body.get("token") if isinstance(other_body, dict) else None
    checker.check("second user registers", other_status == 201 and bool(other_token))
    if doc_id and other_token:
        status, _ = _request(
            base_url, "DELETE", f"/documents/{doc_id}", token=other_token
        )
        checker.check("cross-user delete is 404", status == 404, f"got {status}")

    print(f"\n{checker.checks - checker.failures}/{checker.checks} checks passed")
    if checker.failures:
        print("SMOKE FAILED")
        return 1
    print("SMOKE PASSED")
    return 0


def main() -> int:
    """Parse the command line and run the matrix.

    Returns:
        The smoke exit code, or 2 when the arguments are invalid.
    """
    if len(sys.argv) != 2:
        print("usage: python scripts/smoke.py <base_url>")
        return 2
    return smoke(sys.argv[1])


if __name__ == "__main__":
    raise SystemExit(main())
