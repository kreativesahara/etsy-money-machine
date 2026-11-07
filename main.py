import argparse
import base64
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from PIL import Image, ImageDraw

from config.settings import get_settings
from schemas.models import (
    AuditResult,
    EtsySEOListing,
    NicheBrief,
    PipelineState,
)
from agents.nova_research import run_nova_research_node
from agents.muse_designer import run_muse_designer_node
from agents.audit_gate import run_audit_gate_node
from agents.seo_listing import run_seo_listing_node
from agents.forge_printify import run_forge_printify_node
from agents.ultron_supervisor import build_ultron_graph


def _generate_mock_transparent_png_b64(phrase: str = "IN MY GARDEN ERA") -> str:
    """Create a valid transparent RGBA PNG in memory and return base64 string."""
    img = Image.new("RGBA", (256, 320), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Draw botanical frame & text placeholder on transparent canvas
    draw.rectangle([(20, 20), (236, 300)], outline=(74, 222, 128, 255), width=4)
    draw.text((36, 150), phrase[:22], fill=(0, 255, 102, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def build_mock_openai_client(
    seed_category: str = "botanical book club apparel",
    confidence_sequence: list[float] | None = None,
) -> MagicMock:
    """Build a mocked OpenAI client returning structured Pydantic responses and PNG bytes."""
    if confidence_sequence is None:
        confidence_sequence = [0.91]

    call_idx = {"audit": 0}
    client = MagicMock()

    mock_brief = NicheBrief(
        niche_name="In My Garden Era Floral",
        target_persona="Book club & gardening enthusiasts",
        aesthetic_style="Cozy watercolor botanical with retro serif typography",
        phrase_on_product="In My Garden Era",
        seed_keywords=[
            "in my garden era",
            "botanical shirt",
            "book club tee",
            "plant lover gift",
            "cottagecore shirt",
        ],
        product_category="apparel",
    )

    mock_seo = EtsySEOListing(
        title=(
            "In My Garden Era Shirt | Cozy Botanical Book Club Tee | "
            "Cottagecore Plant Lover Gift | Retro Floral Gardening Sweatshirt"
        )[:140],
        description=(
            "Celebrate your cozy gardening and reading rituals with our 'In My Garden Era' "
            "botanical graphic tee. Featuring soft watercolor florals and vintage serif typography.\n\n"
            "Transparency Disclosure: Original artwork was created with AI assistance and is "
            "printed to order with our production partner Printify."
        ),
        tags=[
            "in my garden era",
            "garden lover gift",
            "book club shirt",
            "botanical graphic",
            "cottagecore tee",
            "plant mom shirt",
            "floral bookish tee",
            "cozy gardener gift",
            "retro wildflower",
            "reading garden tee",
            "soft girl aesthetic",
            "nature lover shirt",
            "garden club apparel",
        ],
        ai_disclosure_included=True,
    )

    def _mock_parse(*args, **kwargs):
        response_format = kwargs.get("response_format")
        if response_format is NicheBrief:
            parsed = mock_brief
        elif response_format is AuditResult:
            idx = min(call_idx["audit"], len(confidence_sequence) - 1)
            conf = confidence_sequence[idx]
            call_idx["audit"] += 1
            parsed = AuditResult(
                approved=conf >= 0.75,
                render_confidence=conf,
                spelling_verified=True,
                transparent_background_clean=True,
                trademark_safe=True,
                critique_notes=(
                    "Crisp serif lettering, clean alpha channel, verified print-ready."
                    if conf >= 0.75
                    else "Slight kerning blur detected on serif edges; requesting re-render."
                ),
            )
        elif response_format is EtsySEOListing:
            parsed = mock_seo
        else:
            raise ValueError(f"Unexpected response_format: {response_format}")

        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=parsed))])

    client.beta.chat.completions.parse.side_effect = _mock_parse

    b64_png = _generate_mock_transparent_png_b64(mock_brief.phrase_on_product)
    client.images.generate.return_value = SimpleNamespace(
        data=[SimpleNamespace(b64_json=b64_png)]
    )
    return client


def execute_pipeline(
    seed_category: str = "botanical book club apparel",
    dry_run: bool = True,
    output_dir: Path | None = None,
    confidence_sequence: list[float] | None = None,
) -> PipelineState:
    """Execute the full Ultron LangGraph multi-agent pipeline."""
    settings = get_settings()
    target_output_dir = Path(output_dir or settings.output_dir)

    if dry_run:
        openai_client = build_mock_openai_client(
            seed_category=seed_category,
            confidence_sequence=confidence_sequence,
        )
        mock_listings = [
            {
                "title": "In My Garden Era Shirt, Cozy Plant Lover Gift, Botanical Tee",
                "tags": ["garden era", "plant lover gift", "book club babe", "soft girl"],
                "favorites": 1420,
                "views": 18900,
            },
            {
                "title": "Book Club Babe Sweatshirt, Retro Floral Coffee & Reading Gift",
                "tags": ["book club", "coffee lover", "garden gift", "cozy reading"],
                "favorites": 980,
                "views": 12400,
            },
        ]

        with (
            patch("agents.nova_research.fetch_trending_etsy_listings", return_value=mock_listings),
            patch("agents.forge_printify.upload_artwork_to_printify", return_value="img_mock_99481"),
            patch("agents.forge_printify.create_printify_product", return_value="prod_mock_77310"),
            patch("agents.forge_printify.publish_printify_product", return_value=None),
        ):
            graph = build_ultron_graph(
                nova_fn=lambda s: run_nova_research_node(s, openai_client, "mock-etsy-key"),
                muse_fn=lambda s: run_muse_designer_node(s, openai_client, target_output_dir),
                audit_fn=lambda s: run_audit_gate_node(
                    s, openai_client, min_confidence=settings.min_render_confidence
                ),
                seo_fn=lambda s: run_seo_listing_node(s, openai_client),
                forge_fn=lambda s: run_forge_printify_node(
                    s,
                    token="mock-printify-token",
                    shop_id=settings.printify_shop_id,
                    blueprint_id=settings.default_blueprint_id,
                    print_provider_id=settings.default_print_provider_id,
                    auto_publish=settings.auto_publish_enabled,
                ),
            )
            initial_state = PipelineState(seed_category=seed_category)
            result = graph.invoke(initial_state)
            return PipelineState(**result) if isinstance(result, dict) else result

    # Live execution mode with real API clients
    from openai import OpenAI

    openai_client = OpenAI(api_key=settings.openai_api_key)
    graph = build_ultron_graph(
        nova_fn=lambda s: run_nova_research_node(s, openai_client, settings.etsy_api_keystring),
        muse_fn=lambda s: run_muse_designer_node(s, openai_client, target_output_dir),
        audit_fn=lambda s: run_audit_gate_node(
            s, openai_client, min_confidence=settings.min_render_confidence
        ),
        seo_fn=lambda s: run_seo_listing_node(s, openai_client),
        forge_fn=lambda s: run_forge_printify_node(
            s,
            token=settings.printify_api_token,
            shop_id=settings.printify_shop_id,
            blueprint_id=settings.default_blueprint_id,
            print_provider_id=settings.default_print_provider_id,
            auto_publish=settings.auto_publish_enabled,
        ),
    )
    initial_state = PipelineState(seed_category=seed_category)
    result = graph.invoke(initial_state)
    return PipelineState(**result) if isinstance(result, dict) else result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ultron Supervisor CLI — Autonomous Etsy Print-on-Demand Multi-Agent Pipeline"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the complete LangGraph agent state machine locally with mocked API calls.",
    )
    parser.add_argument(
        "--seed-category",
        type=str,
        default="botanical book club apparel",
        help="Seed niche/category for Nova Research Agent.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="artifacts/renders",
        help="Directory to store raw and 4500x5400 @ 300 DPI upscaled artwork.",
    )
    parser.add_argument(
        "--simulate-retry",
        action="store_true",
        help="In --dry-run mode, simulate an initial low-confidence render (0.62) followed by approval (0.94).",
    )
    args = parser.parse_args()

    confidence_seq = [0.62, 0.94] if args.simulate_retry else [0.92]
    final_state = execute_pipeline(
        seed_category=args.seed_category,
        dry_run=args.dry_run,
        output_dir=Path(args.output_dir),
        confidence_sequence=confidence_seq,
    )

    print("=== ETSY PRODUCTION TERMINAL :: ULTRON PIPELINE SUMMARY ===")
    print(json.dumps(final_state.model_dump(), indent=2))


if __name__ == "__main__":
    main()
