from typing import Any, Dict, List, Optional
import httpx

ETSY_BASE_URL = "https://api.etsy.com/v3/application"


class EtsyClient:
    """Wrapper for Etsy Open API v3 OAuth2 & REST endpoints."""

    def __init__(
        self,
        api_keystring: str,
        oauth_access_token: Optional[str] = None,
        shop_id: Optional[str] = None,
        timeout: float = 20.0,
    ) -> None:
        self.api_keystring = api_keystring
        self.oauth_access_token = oauth_access_token
        self.shop_id = shop_id
        self.timeout = timeout

    def _headers(self, require_oauth: bool = False) -> Dict[str, str]:
        headers = {"x-api-key": self.api_keystring}
        if require_oauth and self.oauth_access_token:
            headers["Authorization"] = f"Bearer {self.oauth_access_token}"
        return headers

    def find_all_listings_active(
        self,
        keywords: str,
        limit: int = 25,
        sort_on: str = "score",
    ) -> List[Dict[str, Any]]:
        params = {
            "keywords": keywords,
            "limit": limit,
            "sort_on": sort_on,
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(
                f"{ETSY_BASE_URL}/listings/active",
                headers=self._headers(),
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

        return [
            {
                "listing_id": item.get("listing_id"),
                "title": item.get("title"),
                "tags": item.get("tags", []),
                "favorites": item.get("num_favorers", 0),
                "views": item.get("views", 0),
            }
            for item in data.get("results", [])
        ]

    def get_shop_listings(self, state: str = "active", limit: int = 25) -> List[Dict[str, Any]]:
        if not self.shop_id:
            raise ValueError("shop_id is required to query shop listings.")
        params = {"state": state, "limit": limit}
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(
                f"{ETSY_BASE_URL}/shops/{self.shop_id}/listings",
                headers=self._headers(require_oauth=True),
                params=params,
            )
            resp.raise_for_status()
            return resp.json().get("results", [])
