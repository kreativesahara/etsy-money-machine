import base64
from pathlib import Path
import httpx
from schemas.models import PipelineState

PRINTIFY_API_BASE = "https://api.printify.com/v1"


def upload_artwork_to_printify(token: str, file_path: Path) -> str:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    b64_contents = base64.b64encode(Path(file_path).read_bytes()).decode("utf-8")
    payload = {"file_name": Path(file_path).name, "contents": b64_contents}
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(f"{PRINTIFY_API_BASE}/uploads/images.json", headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()["id"]


def create_printify_product(
    token: str,
    shop_id: str,
    image_id: str,
    title: str,
    description: str,
    tags: list[str],
    blueprint_id: int = 12,
    print_provider_id: int = 99,
    variant_ids: list[int] = [45740, 45742, 45744, 45746],
) -> str:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    variants_payload = [{"id": vid, "price": 2499, "is_enabled": True} for vid in variant_ids]
    payload = {
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
                        "images": [{"id": image_id, "x": 0.5, "y": 0.5, "scale": 1.0, "angle": 0}],
                    }
                ],
            }
        ],
    }
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            f"{PRINTIFY_API_BASE}/shops/{shop_id}/products.json",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()["id"]


def publish_printify_product(token: str, shop_id: str, product_id: str) -> None:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "title": True,
        "description": True,
        "images": True,
        "variants": True,
        "tags": True,
        "keyFeatures": True,
        "shipping_template": True,
    }
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            f"{PRINTIFY_API_BASE}/shops/{shop_id}/products/{product_id}/publish.json",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()


def run_forge_printify_node(
    state: PipelineState,
    token: str,
    shop_id: str,
    blueprint_id: int = 12,
    print_provider_id: int = 99,
    auto_publish: bool = False,
) -> PipelineState:
    if isinstance(state, dict):
        state = PipelineState(**state)

    if state.design_asset is None or state.seo_listing is None:
        raise ValueError("Forge Printify node requires both design_asset and seo_listing.")

    print_ready_path = Path(state.design_asset.print_ready_path)
    image_id = upload_artwork_to_printify(token=token, file_path=print_ready_path)
    product_id = create_printify_product(
        token=token,
        shop_id=shop_id,
        image_id=image_id,
        title=state.seo_listing.title,
        description=state.seo_listing.description,
        tags=state.seo_listing.tags,
        blueprint_id=blueprint_id,
        print_provider_id=print_provider_id,
    )

    if auto_publish:
        publish_printify_product(token=token, shop_id=shop_id, product_id=product_id)

    state.printify_product_id = product_id
    state.status = "completed"
    return state
