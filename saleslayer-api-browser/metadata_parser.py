import json
import re


ENTITY_TITLE_MAP = {
    "Products": "Product",
    "Variants": "Variant",
    "Categories": "Category",
}


SIMPLE_TYPES = {
    "string",
    "string | null",
    "integer",
    "integer | null",
    "number",
    "number | null",
    "boolean",
    "boolean | null",
}


def _normalize_type(type_value):
    if isinstance(type_value, list):
        return " | ".join(str(t) for t in type_value)
    if isinstance(type_value, dict):
        return "object"
    return str(type_value) if type_value is not None else "unknown"


def _extract_custom_entity_denominator_from_schema(schema: dict) -> str | None:
    candidates = [
        schema.get("title", ""),
        schema.get("$id", ""),
        schema.get("description", ""),
    ]

    patterns = [
        r"CustomEntities\('(.+?)'\)",
        r"CustomEntity\('(.+?)'\)",
    ]

    for candidate in candidates:
        if not candidate:
            continue

        for pattern in patterns:
            match = re.search(pattern, candidate)
            if match:
                return match.group(1)

    return None


def extract_custom_entities_tables(metadata_text: str) -> list[dict]:
    data = json.loads(metadata_text)

    schemas = data.get("value", [])
    if not isinstance(schemas, list):
        raise ValueError("La metadata no tiene el formato esperado: falta la lista 'value'.")

    tables = []

    for schema in schemas:
        denominator = _extract_custom_entity_denominator_from_schema(schema)
        if not denominator:
            continue

        title = schema.get("title", denominator)
        tables.append({
            "denominator": denominator,
            "title": title,
        })

    unique = {}
    for table in tables:
        unique[table["denominator"]] = table

    return sorted(unique.values(), key=lambda x: x["denominator"].lower())


def _select_schema(
    schemas: list[dict],
    selected_entity: str | None = None,
    custom_entity_denominator: str | None = None
) -> dict:
    if selected_entity == "CustomEntities":
        if custom_entity_denominator:
            for schema in schemas:
                denominator = _extract_custom_entity_denominator_from_schema(schema)
                if denominator == custom_entity_denominator:
                    return schema
        if schemas:
            return schemas[0]
    else:
        expected_title = ENTITY_TITLE_MAP.get(selected_entity, None)
        if expected_title:
            for schema in schemas:
                if schema.get("title") == expected_title:
                    return schema

    if not schemas:
        raise ValueError("La metadata no contiene esquemas.")
    return schemas[0]


def _is_postable_property(field_name: str, field_schema: dict, field_type: str, schema: dict) -> bool:
    if field_type not in SIMPLE_TYPES:
        return False

    custom_type = field_schema.get("x-custom-type", "")
    if custom_type == "status":
        return False

    identifier_attr = schema.get("x-storage-object-identifier-attribute")
    status_attr = schema.get("x-storage-object-status-attribute")

    if field_name == identifier_attr:
        return False
    if field_name == status_attr:
        return False

    lowered = field_name.lower()
    if lowered.endswith("_id"):
        return False
    if lowered.endswith("_creation"):
        return False
    if lowered.endswith("_modify"):
        return False

    return True


def extract_properties_from_metadata(
    metadata_text: str,
    selected_entity: str | None = None,
    custom_entity_denominator: str | None = None
) -> list[dict]:
    data = json.loads(metadata_text)

    schemas = data.get("value", [])
    if not isinstance(schemas, list):
        raise ValueError("La metadata no tiene el formato esperado: falta la lista 'value'.")

    selected_schema = _select_schema(schemas, selected_entity, custom_entity_denominator)

    properties = selected_schema.get("properties", {})
    required_fields = set(selected_schema.get("required", []))

    result = []

    for field_name, field_schema in properties.items():
        field_type = _normalize_type(field_schema.get("type"))
        field_title = field_schema.get("title", field_name)
        custom_type = field_schema.get("x-custom-type", "")
        is_required = field_name in required_fields
        is_postable = _is_postable_property(field_name, field_schema, field_type, selected_schema)

        result.append({
            "entity": selected_schema.get("title", ""),
            "name": field_name,
            "title": field_title,
            "type": field_type,
            "custom_type": custom_type,
            "required": is_required,
            "postable": is_postable,
        })

    return result