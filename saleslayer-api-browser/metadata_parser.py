import json
import re


ENTITY_TITLE_MAP = {
    "Products": "Product",
    "Variants": "Variant",
    "Categories": "Category",
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


def extract_properties_from_metadata(
    metadata_text: str,
    selected_entity: str | None = None,
    custom_entity_denominator: str | None = None
) -> list[dict]:
    data = json.loads(metadata_text)

    schemas = data.get("value", [])
    if not isinstance(schemas, list):
        raise ValueError("La metadata no tiene el formato esperado: falta la lista 'value'.")

    selected_schema = None

    if selected_entity == "CustomEntities":
        if custom_entity_denominator:
            for schema in schemas:
                denominator = _extract_custom_entity_denominator_from_schema(schema)
                if denominator == custom_entity_denominator:
                    selected_schema = schema
                    break
        else:
            if schemas:
                selected_schema = schemas[0]
    else:
        expected_title = ENTITY_TITLE_MAP.get(selected_entity, None)
        if expected_title:
            for schema in schemas:
                if schema.get("title") == expected_title:
                    selected_schema = schema
                    break

    if selected_schema is None:
        if not schemas:
            raise ValueError("La metadata no contiene esquemas.")
        selected_schema = schemas[0]

    properties = selected_schema.get("properties", {})
    required_fields = set(selected_schema.get("required", []))

    result = []

    for field_name, field_schema in properties.items():
        field_type = _normalize_type(field_schema.get("type"))
        field_title = field_schema.get("title", field_name)
        custom_type = field_schema.get("x-custom-type", "")
        is_required = field_name in required_fields

        result.append({
            "entity": selected_schema.get("title", ""),
            "name": field_name,
            "title": field_title,
            "type": field_type,
            "custom_type": custom_type,
            "required": is_required,
        })

    return result