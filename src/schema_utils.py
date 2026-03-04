from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SchemaValidationError(ValueError):
    pass


_TYPE_MAP = {
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "object": dict,
    "array": list,
    "null": type(None),
}


def load_schema(schema_name: str, schema_dir: str | Path | None = None) -> dict[str, Any]:
    if schema_dir is None:
        schema_dir = Path(__file__).resolve().parent / "schemas"
    path = Path(schema_dir) / schema_name
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _is_valid_type(value: Any, expected: str | list[str]) -> bool:
    expected_types = expected if isinstance(expected, list) else [expected]
    for t in expected_types:
        py_type = _TYPE_MAP.get(t)
        if py_type is None:
            continue
        if t == "integer" and isinstance(value, bool):
            continue
        if t == "number" and isinstance(value, bool):
            continue
        if isinstance(value, py_type):
            return True
    return False


def validate_record(record: Any, schema: dict[str, Any], path: str = "$") -> None:
    if "type" in schema and not _is_valid_type(record, schema["type"]):
        raise SchemaValidationError(f"{path}: expected type {schema['type']}, got {type(record).__name__}")

    if "enum" in schema and record not in schema["enum"]:
        raise SchemaValidationError(f"{path}: value {record!r} not in enum {schema['enum']!r}")

    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        if "object" in schema_type and isinstance(record, dict):
            schema_type = "object"
        elif "array" in schema_type and isinstance(record, list):
            schema_type = "array"
        else:
            return

    if schema_type == "object":
        required = schema.get("required", [])
        for key in required:
            if key not in record:
                raise SchemaValidationError(f"{path}: missing required key '{key}'")

        properties = schema.get("properties", {})
        additional_allowed = schema.get("additionalProperties", True)

        for key, value in record.items():
            child_path = f"{path}.{key}"
            if key in properties:
                validate_record(value, properties[key], child_path)
            elif not additional_allowed:
                raise SchemaValidationError(f"{child_path}: additional property not allowed")

    elif schema_type == "array":
        item_schema = schema.get("items")
        if item_schema is not None:
            for idx, item in enumerate(record):
                validate_record(item, item_schema, f"{path}[{idx}]")


__all__ = ["SchemaValidationError", "load_schema", "validate_record"]
