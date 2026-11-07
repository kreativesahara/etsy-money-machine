import base64
from pathlib import Path
from typing import Any, Dict, List
import httpx

PRINTIFY_API_BASE = "https://api.printify.com/v1"


class PrintifyClient:
    """Wrapper for Printify REST API v1."""

    def __init__(self, api_token: str, shop_id: str, timeout: float = 60.0) -> None:
        self.api_token = api_token
        self.shop_id = shop_id
        self.timeout = timeout

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    def upload_image(self, file_path: Path) -> str:
        b64_contents = base64.b64encode(file_path.read_bytes()).decode("utf-8")
        payload = {"file_name": file_path.name, "contents": b64_contents}
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                f"{PRINTIFY_API_BASE}/uploads/images.json",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()["id"]

    def create_product(
        self,
        image_id: str,
        title: str,
        description: str,
        tags: List[str],
        blueprint_id: int = 12,
        print_provider_id: int = 99,
        variant_ids: List[int] = [45740, 45742, 45744, 45746],
        price_cents: int = 2499,
    ) -> str:
        variants_payload = [
            {"id": vid, "price": price_cents, "is_enabled": True} for vid in variant_ids
        ]
        payload: Dict[str, Any] = {
            "title": title,
            "description": description,
            "tags": tags,
            "blueprint_id": blueprint_id,
            "print_provider_id": print_provider_id,
            "variants": variants_payload,
            "print_areas": [
                {
                    "variant_ids": variant_ids,
                    "placeholders": [
                        {
                            "position": "front",
                            "images": [
                                {
                                    "id": image_id,
                                    "x": 0.5,
                                    "y": 0.5,
                                    "scale": 1.0,
                                    "angle": 0,
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                f"{PRINTIFY_API_BASE}/shops/{self.shop_id}/products.json",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()["id"]

    def publish_product(self, product_id: str) -> Dict[str, Any]:
        payload = {
            "title": True,
            "description": True,
            "images": True,
            "variants": True,
            "tags": True,
            "keyFeatures": True,
            "shipping_template": True,
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                f"{PRINTIFY_API_BASE}/shops/{self.shop_id}/products/{product_id}/publish.json",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            return resp.json() if resp.content else {"status": "published"}
