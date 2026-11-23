"""Static-asset exposure: only the public frontend assets are reachable.

``/static`` must never serve the whole ``frontend`` tree. Build tooling
(manifests, lockfiles, lint/format configuration and dotfiles), the shell
document and ``node_modules`` stay private, while the stylesheet, the native ES
modules and the shell at ``/`` remain available.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

FORBIDDEN_PATHS = (
    "/static/package.json",
    "/static/package-lock.json",
    "/static/eslint.config.js",
    "/static/.prettierrc.json",
    "/static/.prettierignore",
    "/static/.gitignore",
    "/static/index.html",
    "/static/node_modules/.package-lock.json",
    "/static/node_modules/left-pad/package.json",
)

TRAVERSAL_PATHS = (
    "/static/js/%2e%2e/package.json",
    "/static/js/..%2fpackage.json",
    "/static/%2e%2e/SECURITY.md",
    "/static/js/%2e%2e/%2e%2e/.env",
)


def test_tooling_assets_and_traversal_are_not_served(client: TestClient) -> None:
    """Tooling files, node_modules and traversal attempts all return 404."""
    for path in FORBIDDEN_PATHS + TRAVERSAL_PATHS:
        response = client.get(path)
        assert response.status_code == 404, (path, response.status_code)


def test_public_assets_and_shell_are_served(client: TestClient) -> None:
    """The stylesheet, the ES module entry point and ``/`` still load."""
    styles = client.get("/static/styles.css")
    assert styles.status_code == 200
    assert styles.headers["content-type"].startswith("text/css")

    module = client.get("/static/js/main.js")
    assert module.status_code == 200
    assert "javascript" in module.headers["content-type"]

    shell = client.get("/")
    assert shell.status_code == 200
    assert shell.headers["content-type"].startswith("text/html")
    assert "<!doctype html>" in shell.text.lower()
