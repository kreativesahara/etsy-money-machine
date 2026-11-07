import argparse
import base64
import hashlib
import io
import json
import math
import re
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable
from unittest.mock import MagicMock, patch
from PIL import Image, ImageDraw, ImageFont

from config.settings import MissingCredentialsError, get_settings
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
from services.etsy_client import etsy_api_key_header
from services.storage_service import StorageService

STORE_BLUEPRINTS: dict[str, dict[str, Any]] = {
    "store_1": {
        "category": "apparel",
        "blueprint_id": 12,
        "blueprint_name": "Bella+Canvas 3001 Unisex Tee",
        "print_provider_id": 99,
        "price_usd": 24.99,
    },
    "store_2": {
        "category": "candle",
        "blueprint_id": 384,
        "blueprint_name": "9oz Amber Glass Soy Candle",
        "print_provider_id": 72,
        "price_usd": 28.99,
    },
    "store_3": {
        "category": "portrait",
        "blueprint_id": 55,
        "blueprint_name": "Custom Matte Portrait Canvas",
        "print_provider_id": 41,
        "price_usd": 39.99,
    },
}


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for font_name in ["consolab.ttf", "consola.ttf", "courbd.ttf", "arialbd.ttf", "arial.ttf"]:
        try:
            return ImageFont.truetype(font_name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap_phrase_lines(phrase: str, max_chars_per_line: int = 16) -> list[str]:
    words = phrase.upper().split()
    lines: list[str] = []
    current = ""
    for w in words:
        candidate = f"{current} {w}".strip()
        if len(candidate) <= max_chars_per_line or not current:
            current = candidate
        else:
            lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines[:4]


def _generate_mock_transparent_png_b64(
    phrase: str = "IN MY GARDEN ERA",
    category: str = "apparel",
    subtitle: str = "ORIGINAL STUDIO ARTWORK // 300 DPI",
) -> str:
    """Create a stylized transparent RGBA merchandise graphic in memory and return base64 PNG."""
    width, height = 500, 600
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    digest = int(hashlib.md5(f"{phrase}:{category}".encode("utf-8")).hexdigest()[:8], 16)
    palettes = [
        ((0, 255, 102, 255), (74, 222, 128, 235), (167, 243, 208, 220)),
        ((52, 211, 153, 255), (16, 185, 129, 235), (209, 250, 229, 220)),
        ((134, 239, 172, 255), (34, 197, 94, 235), (240, 253, 244, 225)),
    ]
    primary, secondary, highlight = palettes[digest % len(palettes)]
    dark_fill = (6, 24, 14, 215)

    font_title = _load_font(34)
    font_sub = _load_font(15)
    font_micro = _load_font(12)

    cx, cy = width // 2, height // 2

    if category == "candle":
        # Apothecary double-lined alchemy label crest
        draw.rounded_rectangle([(46, 56), (454, 544)], radius=24, fill=dark_fill, outline=primary, width=4)
        draw.rounded_rectangle([(60, 70), (440, 530)], radius=18, outline=secondary, width=2)
        # Corner botanical diamonds
        for px, py in [(80, 90), (420, 90), (80, 510), (420, 510)]:
            draw.polygon([(px, py - 8), (px + 8, py), (px, py + 8), (px - 8, py)], fill=primary)
        # Top apothecary header
        draw.text((cx, 112), "SMALL BATCH BOTANICAL SOY CANDLE", fill=secondary, font=font_sub, anchor="mm")
        draw.line([(110, 134), (390, 134)], fill=secondary, width=2)
        # Central botanical vessel & flame emblem
        draw.ellipse([(cx - 48, 158), (cx + 48, 254)], outline=primary, width=3)
        draw.polygon([(cx, 174), (cx + 16, 212), (cx, 236), (cx - 16, 212)], fill=highlight, outline=primary)
        # Footer apothecary stamp
        draw.line([(100, 442), (400, 442)], fill=secondary, width=2)
        draw.text((cx, 468), "HAND POURED • NATURAL ESSENTIAL OILS • 9 OZ", fill=highlight, font=font_micro, anchor="mm")
        draw.text((cx, 496), subtitle, fill=secondary, font=font_micro, anchor="mm")
        text_y_start = 290

    elif category == "portrait":
        # Ornate regal portrait medallion & Victorian frame
        draw.rounded_rectangle([(44, 48), (456, 552)], radius=36, fill=dark_fill, outline=primary, width=4)
        draw.ellipse([(95, 78), (405, 378)], outline=primary, width=5)
        draw.ellipse([(109, 92), (391, 364)], outline=secondary, width=2)
        # Crown / star rays above portrait crest
        for angle_deg in range(-60, 61, 20):
            rad = math.radians(angle_deg - 90)
            x1 = cx + int(158 * math.cos(rad))
            y1 = 228 + int(158 * math.sin(rad))
            x2 = cx + int(174 * math.cos(rad))
            y2 = 228 + int(174 * math.sin(rad))
            draw.line([(x1, y1), (x2, y2)], fill=primary, width=3)
        # Stylized regal pet/portrait bust silhouette inside medallion
        draw.ellipse([(cx - 34, 152), (cx + 34, 220)], fill=secondary, outline=highlight, width=2)
        # Regal ears/crown detail
        draw.polygon([(cx - 28, 160), (cx - 42, 128), (cx - 10, 150)], fill=primary)
        draw.polygon([(cx + 28, 160), (cx + 42, 128), (cx + 10, 150)], fill=primary)
        draw.polygon([(cx - 64, 330), (cx - 38, 232), (cx + 38, 232), (cx + 64, 330)], fill=secondary, outline=primary, width=3)
        # Ribbon banner below medallion
        draw.rounded_rectangle([(68, 392), (432, 516)], radius=12, fill=dark_fill, outline=primary, width=3)
        draw.text((cx, 534), "BESPOKE HEIRLOOM ILLUSTRATION • 300 DPI", fill=secondary, font=font_micro, anchor="mm")
        text_y_start = 418

    else:
        # Apparel: Botanical arch + sunburst + floral sprigs
        draw.rounded_rectangle([(48, 52), (452, 548)], radius=180, fill=dark_fill, outline=primary, width=4)
        draw.rounded_rectangle([(62, 66), (438, 534)], radius=168, outline=secondary, width=2)
        # Sunburst rays in upper arch
        arch_cy = 205
        for angle_deg in range(195, 346, 15):
            rad = math.radians(angle_deg)
            x1 = cx + int(52 * math.cos(rad))
            y1 = arch_cy + int(52 * math.sin(rad))
            x2 = cx + int(118 * math.cos(rad))
            y2 = arch_cy + int(118 * math.sin(rad))
            draw.line([(x1, y1), (x2, y2)], fill=secondary, width=2)
        draw.arc([(cx - 44, arch_cy - 44), (cx + 44, arch_cy + 44)], start=180, end=360, fill=primary, width=4)
        # Botanical leaf sprigs
        for offset in (-75, -35, 35, 75):
            draw.ellipse([(cx + offset - 14, 212), (cx + offset + 14, 228)], outline=highlight, width=2)
        draw.line([(96, 244), (404, 244)], fill=primary, width=3)
        draw.line([(96, 464), (404, 464)], fill=secondary, width=2)
        draw.text((cx, 492), "EST. 2026 • BOTANICAL APPAREL CLUB", fill=highlight, font=font_sub, anchor="mm")
        draw.text((cx, 516), subtitle, fill=secondary, font=font_micro, anchor="mm")
        text_y_start = 278

    lines = _wrap_phrase_lines(phrase, max_chars_per_line=16)
    line_height = 42 if len(lines) <= 3 else 34
    for idx, line in enumerate(lines):
        y_pos = text_y_start + idx * line_height
        # Subtle shadow + crisp neon foreground
        draw.text((cx + 2, y_pos + 2), line, fill=(0, 0, 0, 230), font=font_title, anchor="mm")
        draw.text((cx, y_pos), line, fill=primary, font=font_title, anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format="PNG", dpi=(300, 300))
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _synthesize_seed_artifacts(
    seed_category: str,
    store_id: str = "store_1",
) -> tuple[NicheBrief, EtsySEOListing]:
    """Synthesize a store-authentic NicheBrief and 13-tag EtsySEOListing for any seed category."""
    store_cfg = STORE_BLUEPRINTS.get(store_id, STORE_BLUEPRINTS["store_1"])
    category = store_cfg["category"]

    # Preserve exact default fixture for default apparel seed
    if seed_category.strip().lower() == "botanical book club apparel" and store_id == "store_1":
        brief = NicheBrief(
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
        seo = EtsySEOListing(
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
        return brief, seo

    cleaned = re.sub(r"[^a-zA-Z0-9\s&']", " ", seed_category).strip()
    words = [w for w in cleaned.split() if len(w) > 1] or ["Cozy", "Botanical"]
    title_words = " ".join(w.capitalize() for w in words[:4])
    short_stem = " ".join(w.lower() for w in words[:2])[:12].strip() or "cozy style"

    if category == "candle":
        phrase = title_words if len(title_words) <= 26 else " ".join(w.capitalize() for w in words[:3])
        niche_name = f"{phrase} Soy Candle"
        persona = f"Home fragrance & {short_stem} lovers"
        aesthetic = "Minimalist apothecary label crest with vintage botanical line art"
        seo_title = (
            f"{phrase} Scented Soy Candle | Cozy Apothecary Jar Gift | "
            f"Hand Poured Aesthetic Room Decor | Botanical Aromatherapy Candle"
        )[:140]
        base_tags = [
            f"{short_stem} candle"[:20],
            "soy wax candle",
            "apothecary jar",
            "cozy home gift",
            "aromatherapy gift",
            "botanical candle",
            "bookish candle",
            "hygge room decor",
            "relaxing scent gift",
            "aesthetic jar",
            "housewarming gift",
            "natural soy candle",
            "mindful ritual",
        ]
    elif category == "portrait":
        phrase = title_words if len(title_words) <= 26 else " ".join(w.capitalize() for w in words[:3])
        niche_name = f"{phrase} Custom Portrait"
        persona = f"Pet parents, couples & {short_stem} gift shoppers"
        aesthetic = "Bespoke heirloom watercolor & regal portrait illustration"
        seo_title = (
            f"Custom {phrase} Portrait | Personalized Heirloom Wall Art | "
            f"Bespoke Pet & Family Illustration Canvas | Memorial & Housewarming Gift"
        )[:140]
        base_tags = [
            f"{short_stem} art"[:20],
            "custom pet portrait",
            "family portrait",
            "regal dog canvas",
            "bespoke wall art",
            "pet memorial gift",
            "couple portrait",
            "custom illustration",
            "heirloom canvas",
            "personalized gift",
            "dog mom gift",
            "cat lover portrait",
            "custom portrait mug",
        ]
    else:
        phrase = title_words if len(title_words) <= 26 else " ".join(w.capitalize() for w in words[:3])
        niche_name = f"{phrase} Graphic"
        persona = f"Enthusiasts of {short_stem} & cozy lifestyle"
        aesthetic = "Vintage botanical arch with crisp retro serif typography"
        seo_title = (
            f"{phrase} Shirt | Cozy Vintage {title_words} Graphic Tee | "
            f"Bella Canvas Unisex Sweatshirt | Aesthetic Lover Gift"
        )[:140]
        base_tags = [
            f"{short_stem} shirt"[:20],
            f"{short_stem} gift"[:20],
            "cozy graphic tee",
            "retro aesthetic",
            "bella canvas tee",
            "bookish club shirt",
            "cottagecore apparel",
            "soft girl shirt",
            "vintage floral tee",
            "everyday cozy tee",
            "gift for her",
            "indie graphic shirt",
            "trendy hobby tee",
        ]

    # Ensure exactly 13 valid tags <= 20 chars
    valid_tags: list[str] = []
    for t in base_tags:
        clean_t = t.strip()[:20]
        if clean_t and clean_t not in valid_tags:
            valid_tags.append(clean_t)
    while len(valid_tags) < 13:
        valid_tags.append(f"studio tag {len(valid_tags) + 1}"[:20])

    brief = NicheBrief(
        niche_name=niche_name,
        target_persona=persona,
        aesthetic_style=aesthetic,
        phrase_on_product=phrase,
        seed_keywords=valid_tags[:5],
        product_category=category,
    )
    seo = EtsySEOListing(
        title=seo_title,
        description=(
            f"Elevate your daily ritual with our original '{phrase}' {category} design. "
            f"Crafted for {persona.lower()} with {aesthetic.lower()}.\n\n"
            "Transparency Disclosure: Original artwork was created with AI assistance and is "
            "printed to order with our production partner Printify."
        ),
        tags=valid_tags[:13],
        ai_disclosure_included=True,
    )
    return brief, seo


def build_mock_openai_client(
    seed_category: str = "botanical book club apparel",
    confidence_sequence: list[float] | None = None,
    store_id: str = "store_1",
) -> MagicMock:
    """Build a mocked OpenAI client returning structured Pydantic responses and PNG bytes."""
    if confidence_sequence is None:
        confidence_sequence = [0.91]

    call_idx = {"audit": 0}
    client = MagicMock()

    mock_brief, mock_seo = _synthesize_seed_artifacts(seed_category=seed_category, store_id=store_id)

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
                    f"Crisp '{mock_brief.phrase_on_product}' lettering, clean alpha channel, verified 300 DPI print-ready."
                    if conf >= 0.75
                    else f"Kerning blur detected on '{mock_brief.phrase_on_product}' outer glyphs ({int(conf*100)}% < 75% gate); requesting Muse re-render."
                ),
            )
        elif response_format is EtsySEOListing:
            parsed = mock_seo
        else:
            raise ValueError(f"Unexpected response_format: {response_format}")

        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=parsed))])

    client.beta.chat.completions.parse.side_effect = _mock_parse

    b64_png = _generate_mock_transparent_png_b64(
        phrase=mock_brief.phrase_on_product,
        category=mock_brief.product_category,
    )
    client.images.generate.return_value = SimpleNamespace(
        data=[SimpleNamespace(b64_json=b64_png)]
    )
    return client


def execute_pipeline(
    seed_category: str = "botanical book club apparel",
    dry_run: bool = True,
    output_dir: Path | None = None,
    confidence_sequence: list[float] | None = None,
    store_id: str = "store_1",
    event_callback: Callable[[dict[str, Any]], None] | None = None,
    step_delay_ms: int = 0,
) -> PipelineState:
    """Execute the full Ultron LangGraph multi-agent pipeline with optional live telemetry callbacks."""
    settings = get_settings()
    target_output_dir = Path(output_dir or settings.output_dir)
    store_cfg = STORE_BLUEPRINTS.get(store_id, STORE_BLUEPRINTS["store_1"])

    def _emit(event_type: str, agent: str, node: str, message: str, extra: dict[str, Any] | None = None) -> None:
        if event_callback is not None:
            payload: dict[str, Any] = {
                "type": event_type,
                "agent": agent,
                "node": node,
                "store_id": store_id,
                "message": message,
            }
            if extra:
                payload.update(extra)
            event_callback(payload)
        if step_delay_ms > 0:
            time.sleep(step_delay_ms / 1000.0)

    def _wrap_nodes(raw_nova, raw_muse, raw_audit, raw_seo, raw_forge):
        def nova_wrapped(s):
            _emit(
                "NODE_STARTED",
                "NOVA",
                "nova_research",
                f"Scanning high-velocity Etsy listings for '{seed_category}' & screening USPTO trademarks...",
            )
            out = raw_nova(s)
            brief = out.niche_brief
            _emit(
                "NODE_COMPLETED",
                "NOVA",
                "nova_research",
                f"Synthesized NicheBrief '{brief.niche_name}' -> Phrase: \"{brief.phrase_on_product}\"",
                {"niche_brief": brief.model_dump() if brief else None},
            )
            return out

        def muse_wrapped(s):
            state_obj = PipelineState(**s) if isinstance(s, dict) else s
            rev = state_obj.revision_count
            _emit(
                "NODE_STARTED",
                "MUSE",
                "muse_designer",
                f"Rendering transparent PNG via GPT Images 2 (rev {rev}) + 4500x5400 LANCZOS 300 DPI upscale...",
                {"revision_count": rev},
            )
            out = raw_muse(s)
            asset = out.design_asset
            _emit(
                "NODE_COMPLETED",
                "MUSE",
                "muse_designer",
                f"Generated 4500x5400 @ 300 DPI print-ready asset: {Path(asset.print_ready_path).name}",
                {"design_asset": asset.model_dump() if asset else None, "revision_count": out.revision_count},
            )
            return out

        def audit_wrapped(s):
            _emit(
                "NODE_STARTED",
                "AUDIT GATE",
                "audit_gate",
                "Running Vision QA inspection (exact OCR spelling, clean alpha channel, >=75% threshold)...",
            )
            out = raw_audit(s)
            audit = out.audit_result
            pct = int(round((audit.render_confidence if audit else 0.0) * 100))
            if audit and audit.approved:
                _emit(
                    "NODE_COMPLETED",
                    "AUDIT GATE",
                    "audit_gate",
                    f"PASSED QA ({pct}% confidence >= 75%). {audit.critique_notes}",
                    {"audit_result": audit.model_dump(), "approved": True, "revision_count": out.revision_count},
                )
            elif out.status == "designing":
                _emit(
                    "AUDIT_RETRY",
                    "AUDIT GATE",
                    "audit_gate",
                    f"HELD ({pct}% < 75% threshold). Routing back to MUSE for re-render (revision #{out.revision_count})...",
                    {"audit_result": audit.model_dump() if audit else None, "approved": False, "revision_count": out.revision_count},
                )
            else:
                _emit(
                    "NODE_COMPLETED",
                    "AUDIT GATE",
                    "audit_gate",
                    f"HALTED after max revisions ({pct}% confidence).",
                    {"audit_result": audit.model_dump() if audit else None, "approved": False, "revision_count": out.revision_count},
                )
            return out

        def seo_wrapped(s):
            _emit(
                "NODE_STARTED",
                "SEO AGENT",
                "seo_listing",
                "Drafting 140-char Etsy title, buyer description with AI disclosure, and 13x20-char long-tail tags...",
            )
            out = raw_seo(s)
            seo = out.seo_listing
            _emit(
                "NODE_COMPLETED",
                "SEO AGENT",
                "seo_listing",
                f"Prepared 13 tags ({', '.join(seo.tags[:4])}...) & title: \"{seo.title[:54]}...\"",
                {"seo_listing": seo.model_dump() if seo else None},
            )
            return out

        def forge_wrapped(s):
            _emit(
                "NODE_STARTED",
                "FORGE",
                "forge_printify",
                f"Uploading 4500x5400 PNG to Printify Blueprint #{store_cfg['blueprint_id']} ({store_cfg['blueprint_name']})...",
            )
            out = raw_forge(s)
            _emit(
                "NODE_COMPLETED",
                "FORGE",
                "forge_printify",
                f"Created Printify Product {out.printify_product_id} on {store_cfg['blueprint_name']} (${store_cfg['price_usd']}).",
                {"printify_product_id": out.printify_product_id},
            )
            return out

        return nova_wrapped, muse_wrapped, audit_wrapped, seo_wrapped, forge_wrapped

    if dry_run:
        openai_client = build_mock_openai_client(
            seed_category=seed_category,
            confidence_sequence=confidence_sequence,
            store_id=store_id,
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

        # Preserve exact "prod_mock_77310" for default test case, generate deterministic ID otherwise
        if seed_category == "botanical book club apparel" and store_id == "store_1":
            mock_prod_id = "prod_mock_77310"
        else:
            short_hash = hashlib.md5(f"{store_id}:{seed_category}".encode("utf-8")).hexdigest()[:5]
            mock_prod_id = f"prod_{store_id}_{short_hash}"

        with (
            patch("agents.nova_research.fetch_trending_etsy_listings", return_value=mock_listings),
            patch("agents.forge_printify.upload_artwork_to_printify", return_value="img_mock_99481"),
            patch("agents.forge_printify.create_printify_product", return_value=mock_prod_id),
            patch("agents.forge_printify.publish_printify_product", return_value=None),
        ):
            n_fn, m_fn, a_fn, s_fn, f_fn = _wrap_nodes(
                lambda s: run_nova_research_node(s, openai_client, "mock-etsy-key"),
                lambda s: run_muse_designer_node(s, openai_client, target_output_dir),
                lambda s: run_audit_gate_node(
                    s, openai_client, min_confidence=settings.min_render_confidence
                ),
                lambda s: run_seo_listing_node(s, openai_client),
                lambda s: run_forge_printify_node(
                    s,
                    token="mock-printify-token",
                    shop_id=settings.printify_shop_id,
                    blueprint_id=store_cfg["blueprint_id"],
                    print_provider_id=store_cfg["print_provider_id"],
                    auto_publish=settings.auto_publish_enabled,
                ),
            )
            graph = build_ultron_graph(
                nova_fn=n_fn,
                muse_fn=m_fn,
                audit_fn=a_fn,
                seo_fn=s_fn,
                forge_fn=f_fn,
            )
            initial_state = PipelineState(seed_category=seed_category, store_id=store_id)
            result = graph.invoke(initial_state)
            final_state = PipelineState(**result) if isinstance(result, dict) else result
            storage = StorageService(
                database_url=settings.database_url,
                s3_enabled=settings.s3_enabled,
                s3_endpoint_url=settings.s3_endpoint_url,
                s3_access_key=settings.s3_access_key,
                s3_secret_key=settings.s3_secret_key,
                s3_bucket_name=settings.s3_bucket_name,
                s3_region=settings.s3_region,
            )
            storage.save_pipeline_run(final_state)
            return final_state

    # Live execution mode with real API clients
    missing = settings.missing_live_credentials()
    if missing:
        raise MissingCredentialsError(
            "Live run needs real credentials; these are unset or still placeholders: "
            + ", ".join(missing)
            + ". Copy .env.example to .env and fill them in, or use dry-run mode."
        )

    from openai import OpenAI

    openai_client = OpenAI(api_key=settings.openai_api_key)
    etsy_api_key = etsy_api_key_header(settings.etsy_api_keystring, settings.etsy_shared_secret)
    n_fn, m_fn, a_fn, s_fn, f_fn = _wrap_nodes(
        lambda s: run_nova_research_node(s, openai_client, etsy_api_key),
        lambda s: run_muse_designer_node(s, openai_client, target_output_dir),
        lambda s: run_audit_gate_node(
            s, openai_client, min_confidence=settings.min_render_confidence
        ),
        lambda s: run_seo_listing_node(s, openai_client),
        lambda s: run_forge_printify_node(
            s,
            token=settings.printify_api_token,
            shop_id=settings.printify_shop_id,
            blueprint_id=store_cfg["blueprint_id"],
            print_provider_id=store_cfg["print_provider_id"],
            auto_publish=settings.auto_publish_enabled,
        ),
    )
    graph = build_ultron_graph(
        nova_fn=n_fn,
        muse_fn=m_fn,
        audit_fn=a_fn,
        seo_fn=s_fn,
        forge_fn=f_fn,
    )
    initial_state = PipelineState(seed_category=seed_category, store_id=store_id)
    result = graph.invoke(initial_state)
    final_state = PipelineState(**result) if isinstance(result, dict) else result
    storage = StorageService(
        database_url=settings.database_url,
        s3_enabled=settings.s3_enabled,
        s3_endpoint_url=settings.s3_endpoint_url,
        s3_access_key=settings.s3_access_key,
        s3_secret_key=settings.s3_secret_key,
        s3_bucket_name=settings.s3_bucket_name,
        s3_region=settings.s3_region,
    )
    storage.save_pipeline_run(final_state)
    return final_state


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
        "--store-id",
        type=str,
        default="store_1",
        help="Target store profile (store_1: Apparel, store_2: Candles, store_3: Custom Portraits).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(Path(__file__).resolve().parent / "artifacts" / "renders"),
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
        store_id=args.store_id,
    )

    print("=== ETSY PRODUCTION TERMINAL :: ULTRON PIPELINE SUMMARY ===")
    print(json.dumps(final_state.model_dump(), indent=2))


if __name__ == "__main__":
    main()
