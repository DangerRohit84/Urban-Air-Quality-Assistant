"""Custom OpenAPI generation for the shared error contract.

The route decorators declare the errors each endpoint raises. This module
adds the global 500 that any route can produce and annotates FastAPI's
built-in validation schemas so the published contract is complete.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

ERROR_RESPONSE_REF = "#/components/schemas/ErrorResponse"

_VALIDATION_FIELDS: dict[str, dict[str, Any]] = {
    "detail": {
        "description": (
            "One entry per invalid field; submitted values are never echoed."
        ),
        "examples": [
            [{"loc": ["body", "email"], "msg": "Field required", "type": "missing"}]
        ],
    },
    "loc": {
        "description": "Path to the invalid field, e.g. `['body', 'email']`.",
        "examples": [["body", "email"]],
    },
    "msg": {
        "description": "Human-readable validation message.",
        "examples": ["Field required"],
    },
    "type": {
        "description": "Machine-readable validation error code.",
        "examples": ["missing"],
    },
    "input": {
        "description": "Never populated: validation input is not echoed.",
        "examples": [None],
    },
    "ctx": {
        "description": "Never populated: exception context is not echoed.",
        "examples": [{}],
    },
}


def _server_error_response() -> dict[str, Any]:
    """Build the shared 500 response object.

    Returns:
        The OpenAPI response object referencing ``ErrorResponse``.
    """
    return {
        "description": "Unhandled server error; the body never leaks internals.",
        "content": {"application/json": {"schema": {"$ref": ERROR_RESPONSE_REF}}},
    }


def _add_global_server_errors(spec: dict[str, Any]) -> None:
    """Ensure every operation declares the shared 500 response.

    Args:
        spec: The OpenAPI document to update.
    """
    for path_item in spec.get("paths", {}).values():
        for operation in path_item.values():
            if isinstance(operation, dict):
                responses = operation.get("responses")
                if isinstance(responses, dict):
                    responses.setdefault("500", _server_error_response())


def _describe_validation_fields(spec: dict[str, Any]) -> None:
    """Annotate FastAPI's built-in validation schemas.

    Args:
        spec: The OpenAPI document to update.
    """
    schemas = spec.get("components", {}).get("schemas", {})
    for name in ("HTTPValidationError", "ValidationError"):
        properties = schemas.get(name, {}).get("properties", {})
        for field, metadata in properties.items():
            patch = _VALIDATION_FIELDS.get(field)
            if patch is not None:
                metadata.update(patch)


class DocumentedApp(FastAPI):
    """FastAPI application that publishes the shared error contract."""

    def openapi(self) -> dict[str, Any]:
        """Build the OpenAPI schema with global 500s and field examples.

        Returns:
            The cached, fully annotated OpenAPI document.
        """
        if self.openapi_schema is None:
            spec = super().openapi()
            _add_global_server_errors(spec)
            _describe_validation_fields(spec)
            self.openapi_schema = spec
        return self.openapi_schema
