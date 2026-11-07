import base64
import re
from pathlib import Path
from PIL import Image
from openai import OpenAI
from schemas.models import DesignAsset, PipelineState


def upscale_to_printify_spec(
    input_path: Path,
    output_path: Path,
    target_size: tuple[int, int] = (4500, 5400),
) -> None:
    with Image.open(input_path) as img:
        rgba_img = img.convert("RGBA")
        upscaled = rgba_img.resize(target_size, Image.Resampling.LANCZOS)
        upscaled.save(output_path, format="PNG", dpi=(300, 300))


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "design"


def run_muse_designer_node(
    state: PipelineState,
    openai_client: OpenAI,
    output_dir: Path,
) -> PipelineState:
    if isinstance(state, dict):
        state = PipelineState(**state)

    brief = state.niche_brief
    if brief is None:
        raise ValueError("Cannot run Muse Designer without a populated NicheBrief.")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    prompt = (
        f"Standalone t-shirt graphic illustration, isolated on a completely transparent background. "
        f"Style: {brief.aesthetic_style}. "
        f"Centerpiece typography reads exactly: '{brief.phrase_on_product}'. "
        f"Clean edges, high contrast, print-ready merchandise graphic, no t-shirt mockup, no drop shadows."
    )

    result = openai_client.images.generate(
        model="gpt-image-2",
        prompt=prompt,
        size="1024x1536",
        quality="high",
        background="transparent",
    )

    image_bytes = base64.b64decode(result.data[0].b64_json)
    slug = _slugify(brief.niche_name)
    raw_path = output_dir / f"{slug}_raw.png"
    print_path = output_dir / f"{slug}_4500x5400.png"

    raw_path.write_bytes(image_bytes)
    upscale_to_printify_spec(raw_path, print_path)

    state.design_asset = DesignAsset(
        design_title=brief.niche_name.upper(),
        prompt_used=prompt,
        raw_image_path=str(raw_path),
        print_ready_path=str(print_path),
    )
    state.status = "auditing"
    return state
