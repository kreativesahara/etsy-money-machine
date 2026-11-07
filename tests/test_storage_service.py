from pathlib import Path
from schemas.models import (
    AuditResult,
    DesignAsset,
    EtsySEOListing,
    NicheBrief,
    PipelineState,
)
from services.storage_service import StorageService


def test_storage_service_saves_and_lists_runs_with_volume_fallback(tmp_path: Path):
    raw_file = tmp_path / "sample_raw.png"
    print_file = tmp_path / "sample_4500x5400.png"
    raw_file.write_bytes(b"PNG_RAW_BYTES")
    print_file.write_bytes(b"PNG_PRINT_BYTES")

    store_file = tmp_path / "runs.jsonl"
    storage = StorageService(
        database_url=None,
        local_store_path=store_file,
        s3_enabled=False,
    )

    state = PipelineState(
        seed_category="botanical book club apparel",
        niche_brief=NicheBrief(
            niche_name="In My Garden Era Floral",
            target_persona="Book club & gardening enthusiasts",
            aesthetic_style="Cozy watercolor botanical",
            phrase_on_product="In My Garden Era",
            seed_keywords=["garden era", "book club"],
            product_category="apparel",
        ),
        design_asset=DesignAsset(
            design_title="IN MY GARDEN ERA FLORAL",
            prompt_used="Standalone t-shirt graphic",
            raw_image_path=str(raw_file),
            print_ready_path=str(print_file),
        ),
        audit_result=AuditResult(
            approved=True,
            render_confidence=0.93,
            spelling_verified=True,
            transparent_background_clean=True,
            trademark_safe=True,
            critique_notes="Clean edges",
        ),
        seo_listing=EtsySEOListing(
            title="In My Garden Era Shirt | Cozy Botanical Book Club Tee",
            description="Created with AI assistance and printed with Printify.",
            tags=["in my garden era", "book club shirt"],
        ),
        printify_product_id="prod_mock_77310",
        revision_count=0,
        status="completed",
    )

    saved = storage.save_pipeline_run(state)
    assert saved["seed_category"] == "botanical book club apparel"
    assert saved["status"] == "completed"
    assert saved["approved"] is True
    assert saved["printify_product_id"] == "prod_mock_77310"
    assert saved["raw_image_uri"].startswith("file:///")
    assert saved["print_ready_uri"].startswith("file:///")

    recent = storage.list_recent_runs(limit=5)
    assert len(recent) == 1
    assert recent[0]["id"] == saved["id"]
    assert recent[0]["render_confidence"] == 0.93


def test_storage_service_persists_to_docker_postgres_when_running(tmp_path: Path):
    storage = StorageService(
        database_url="postgresql://etsy_admin:etsy_secret_password@localhost:5434/etsy_pod_db",
        local_store_path=tmp_path / "pg_fallback.jsonl",
        s3_enabled=False,
    )
    if not storage.ensure_postgres_schema():
        return

    state = PipelineState(
        seed_category="cozy soy candle gift",
        store_id="store_2",
        status="completed",
        printify_product_id="prod_store_2_candle",
    )
    saved = storage.save_pipeline_run(state)
    assert saved["storage_backend"] == "postgresql"

    runs = storage.list_recent_runs(limit=5)
    assert any(r["id"] == saved["id"] for r in runs)
