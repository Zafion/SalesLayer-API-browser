def _escape_odata_string(value: str) -> str:
    return str(value).replace("'", "''")


def _normalize_boolean(value: str) -> str:
    normalized = str(value).strip().lower()

    if normalized in {"true", "1", "yes", "y", "si", "sí"}:
        return "true"
    if normalized in {"false", "0", "no", "n"}:
        return "false"

    raise ValueError(
        "Valor booleano no válido. Usa true/false, yes/no, si/no o 1/0."
    )


def _normalize_number(value: str) -> str:
    text = str(value).strip().replace(",", ".")

    try:
        number = float(text)
    except ValueError as e:
        raise ValueError(f"Valor numérico no válido: {value}") from e

    if number.is_integer():
        return str(int(number))
    return str(number)


def _normalize_value_for_type(field_type: str, value: str) -> str:
    normalized_type = (field_type or "").strip().lower()

    if normalized_type in {"integer", "integer | null", "number", "number | null"}:
        return _normalize_number(value)

    if normalized_type in {"boolean", "boolean | null"}:
        return _normalize_boolean(value)

    escaped = _escape_odata_string(value)
    return f"'{escaped}'"


def _build_filter_expression(field: str, field_type: str, operator: str, value: str) -> str:
    normalized_value = _normalize_value_for_type(field_type, value)

    if operator == "contains":
        return f"contains({field},{normalized_value})"
    if operator == "startswith":
        return f"startswith({field},{normalized_value})"
    if operator == "endswith":
        return f"endswith({field},{normalized_value})"

    return f"{field} {operator} {normalized_value}"


def build_params(
    selected_fields: list[str],
    filters: list[dict],
    top: int | None = None
) -> dict:
    params = {}

    if selected_fields:
        params["$select"] = ",".join(selected_fields)

    built_filters = []
    for item in filters:
        field = item["field"]
        field_type = item.get("field_type", "string")
        operator = item["operator"]
        value = item["value"]
        joiner = item.get("joiner", "and").lower()

        if value is None or str(value).strip() == "":
            continue

        expression = _build_filter_expression(field, field_type, operator, str(value).strip())
        built_filters.append({
            "joiner": joiner,
            "expression": expression,
        })

    if built_filters:
        filter_text = built_filters[0]["expression"]
        for item in built_filters[1:]:
            joiner = "or" if item["joiner"] == "or" else "and"
            filter_text += f" {joiner} {item['expression']}"
        params["$filter"] = filter_text

    if top:
        params["$top"] = str(top)

    return params