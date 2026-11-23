"""OpenAPI contract tests: status codes, errors, examples and export."""

from __future__ import annotations

from typing import Any

from backend.app.main import app

EXPECTED_RESPONSES: dict[str, set[str]] = {
    "get /": {"200", "429", "500"},
    "get /health": {"200", "500"},
    "post /auth/register": {"201", "409", "413", "422", "429", "500"},
    "post /auth/login": {"200", "401", "413", "422", "429", "500"},
    "get /auth/me": {"200", "401", "429", "500"},
    "post /auth/logout": {"204", "401", "429", "500"},
    "get /profile": {"200", "401", "404", "429", "500"},
    "put /profile": {"200", "401", "413", "422", "429", "500"},
    "post /air/context": {"200", "401", "413", "422", "429", "500"},
    "get /air": {"200", "401", "404", "422", "429", "500"},
    "get /plans": {"200", "401", "422", "429", "500"},
    "get /export": {"200", "401", "422", "429", "500"},
    "post /ask": {"200", "401", "413", "422", "429", "500"},
    "get /documents": {"200", "401", "429", "500"},
    "post /documents": {"201", "401", "409", "413", "422", "429", "500"},
    "delete /documents/{doc_id}": {"204", "401", "404", "422", "429", "500"},
    "post /documents/upload": {
        "201",
        "400",
        "401",
        "409",
        "413",
        "422",
        "429",
        "500",
        "503",
    },
}

BODY_OPERATIONS = {
    "post /auth/register",
    "post /auth/login",
    "put /profile",
    "post /air/context",
    "post /ask",
    "post /documents",
    "post /documents/upload",
}

ERROR_CODES = {"400", "401", "404", "409", "413", "429", "500", "503"}


def _spec() -> dict[str, Any]:
    """Return the annotated OpenAPI document."""
    return app.openapi()


def _operations() -> list[tuple[str, dict[str, Any]]]:
    """Return ``method path`` keys with their operation objects."""
    operations: list[tuple[str, dict[str, Any]]] = []
    for path, path_item in _spec()["paths"].items():
        for method, operation in path_item.items():
            if method in {"get", "post", "put", "delete"}:
                operations.append((f"{method} {path}", operation))
    return operations


def test_response_codes_match_the_documented_contract() -> None:
    """Every operation declares exactly its reachable status codes."""
    actual = {key: set(operation["responses"]) for key, operation in _operations()}
    assert actual == EXPECTED_RESPONSES


def test_every_body_operation_declares_413() -> None:
    """Every operation that accepts a body declares the body-limit branch."""
    actual = {key: set(operation["responses"]) for key, operation in _operations()}
    for key in BODY_OPERATIONS:
        assert "413" in actual[key], f"{key} is missing the 413 response"


def test_every_error_response_uses_the_shared_schema() -> None:
    """Declared errors point at ErrorResponse with a string detail."""
    for key, operation in _operations():
        for code in ERROR_CODES & set(operation["responses"]):
            content = operation["responses"][code].get("content", {})
            schema = content.get("application/json", {}).get("schema", {})
            assert schema.get("$ref", "").endswith("/ErrorResponse"), (key, code)
    detail = _spec()["components"]["schemas"]["ErrorResponse"]["properties"]["detail"]
    assert detail["type"] == "string"


def test_every_schema_field_has_a_description_and_example() -> None:
    """The published schema documents every field it exposes."""
    missing: list[str] = []
    for name, schema in _spec()["components"]["schemas"].items():
        for field, metadata in schema.get("properties", {}).items():
            described = bool(metadata.get("description"))
            exemplified = "example" in metadata or "examples" in metadata
            if not described or not exemplified:
                missing.append(f"{name}.{field}")
    assert missing == []


def test_export_200_declares_markdown_and_json_only() -> None:
    """The export response advertises exactly the two rendered formats."""
    content = _spec()["paths"]["/export"]["get"]["responses"]["200"]["content"]
    assert set(content) == {"application/json", "text/markdown"}
    assert content["text/markdown"]["schema"] == {"type": "string"}
    assert content["application/json"]["schema"]["$ref"].endswith("/PlansResponse")
    assert content["text/markdown"].get("example")


def test_all_tags_are_described() -> None:
    """Every tag used by the API carries a description."""
    tags = _spec()["tags"]
    assert len(tags) == 8
    assert all(tag.get("description") for tag in tags)


def test_openapi_is_cached() -> None:
    """Repeated calls return the same annotated document."""
    assert app.openapi() is app.openapi()
