import json


ENTITY_TITLE_MAP = {
    "Products": "Product",
    "Variants": "Variant",
    "Categories": "Category",
    "CustomEntities": "CustomEntity",
}


def _normalize_type(type_value):
    if isinstance(type_value, list):
        return " | ".join(str(t) for t in type_value)
    if isinstance(type_value, dict):
        return "object"
    return str(type_value) if type_value is not None else "unknown"


def extract_properties_from_metadata(metadata_text: str, selected_entity: str | None = None) -> list[dict]:
    """
    Parsea la respuesta JSON Schema de /$metadata y devuelve una lista de propiedades.
    """

    data = json.loads(metadata_text)

    schemas = data.get("value", [])
    if not isinstance(schemas, list):
        raise ValueError("La metadata no tiene el formato esperado: falta la lista 'value'.")

    expected_title = ENTITY_TITLE_MAP.get(selected_entity, None)

    selected_schema = None

    if expected_title:
        for schema in schemas:
            if schema.get("title") == expected_title:
                selected_schema = schema
                break

    if selected_schema is None:
        # fallback: usar el primero
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