import requests
from urllib.parse import quote


BASE_URL = "https://api2.saleslayer.com/rest/Catalog"


class SalesLayerApiClient:
    def __init__(self, api_key: str):
        self.api_key = api_key.strip()

    def _headers(self, json_mode: bool = False, accept_language: str | None = None) -> dict:
        headers = {
            "X-API-KEY": self.api_key,
            "Accept": "*/*",
            "User-Agent": "SalesLayerApiBrowser/0.1",
        }
        if json_mode:
            headers["Content-Type"] = "application/json"
        if accept_language:
            headers["Accept-Language"] = accept_language
        return headers

    def _build_metadata_url(self, entity: str, custom_entity_denominator: str | None = None) -> str:
        if entity == "CustomEntities":
            if custom_entity_denominator:
                encoded = quote(custom_entity_denominator, safe="")
                return f"{BASE_URL}/CustomEntities('{encoded}')/$metadata"
            return f"{BASE_URL}/CustomEntities/$metadata"

        return f"{BASE_URL}/{entity}/$metadata"

    def _build_get_url(self, entity: str, custom_entity_denominator: str | None = None) -> str:
        if entity == "CustomEntities":
            if not custom_entity_denominator:
                raise ValueError("Para Custom Entities debes indicar un denominator.")
            encoded = quote(custom_entity_denominator, safe="")
            return f"{BASE_URL}/CustomEntities('{encoded}')"
        return f"{BASE_URL}/{entity}"

    def _build_post_url(self, entity: str, custom_entity_denominator: str | None = None) -> str:
        if entity == "CustomEntities":
            if not custom_entity_denominator:
                raise ValueError("Para Custom Entities debes indicar un denominator.")
            encoded = quote(custom_entity_denominator, safe="")
            return f"{BASE_URL}/CustomEntity('{encoded}')"
        return f"{BASE_URL}/{entity}"

    def get_metadata(self, entity: str, custom_entity_denominator: str | None = None) -> str:
        url = self._build_metadata_url(entity, custom_entity_denominator)
        response = requests.get(url, headers=self._headers(), timeout=30)
        response.raise_for_status()
        return response.text

    def get_data(
        self,
        entity: str,
        params: dict,
        custom_entity_denominator: str | None = None
    ) -> dict:
        url = self._build_get_url(entity, custom_entity_denominator)
        response = requests.get(url, headers=self._headers(), params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def post_data(
        self,
        entity: str,
        payload: dict,
        custom_entity_denominator: str | None = None,
        accept_language: str | None = None
    ) -> dict:
        url = self._build_post_url(entity, custom_entity_denominator)
        response = requests.post(
            url,
            headers=self._headers(json_mode=True, accept_language=accept_language),
            json=payload,
            timeout=30
        )
        response.raise_for_status()

        if not response.text.strip():
            return {"status_code": response.status_code, "message": "Empty response body"}

        try:
            return response.json()
        except ValueError:
            return {
                "status_code": response.status_code,
                "raw_response": response.text
            }