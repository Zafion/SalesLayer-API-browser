import requests


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

    def get_metadata(self, entity: str) -> str:
        url = f"{BASE_URL}/{entity}/$metadata"
        response = requests.get(url, headers=self._headers(), timeout=30)
        response.raise_for_status()
        return response.text

    def get_data(self, entity: str, params: dict) -> dict:
        url = f"{BASE_URL}/{entity}"
        response = requests.get(url, headers=self._headers(), params=params, timeout=30)
        response.raise_for_status()
        return response.json()