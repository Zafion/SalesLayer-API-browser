import requests
from urllib.parse import quote


BASE_URL = "https://api2.saleslayer.com/rest/Catalog"


class SalesLayerApiClient:
    def __init__(self, api_key: str):
        self.api_key = api_key.strip()

    def _headers(self) -> dict:
        return {
            "X-API-KEY": self.api_key,
            "Accept": "*/*",
            "User-Agent": "SalesLayerApiBrowser/0.1"
        }

    def _build_metadata_url(self, entity: str, custom_entity_denominator: str | None = None) -> str:
        if entity == "CustomEntities":
            if custom_entity_denominator:
                encoded = quote(custom_entity_denominator, safe="")
                return f"{BASE_URL}/CustomEntities('{encoded}')/$metadata"
            return f"{BASE_URL}/CustomEntities/$metadata"

        return f"{BASE_URL}/{entity}/$metadata"

    def _build_data_url(self, entity: str, custom_entity_denominator: str | None = None) -> str:
        if entity == "CustomEntities":
            if not custom_entity_denominator:
                raise ValueError("Para Custom Entities debes indicar un denominator.")
            encoded = quote(custom_entity_denominator, safe="")
            return f"{BASE_URL}/CustomEntities('{encoded}')"

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
        url = self._build_data_url(entity, custom_entity_denominator)
        response = requests.get(url, headers=self._headers(), params=params, timeout=30)
        response.raise_for_status()
        return response.json()