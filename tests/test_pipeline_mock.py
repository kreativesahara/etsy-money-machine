from pathlib import Path
from PIL import Image
from main import execute_pipeline


def test_end_to_end_pipeline_dry_run_success(tmp_path: Path):
    final_state = execute_pipeline(
        seed_category="botanical book club apparel",
        dry_run=True,
        output_dir=tmp_path,
        confidence_sequence=[0.93],
    )

    assert final_state.status == "completed"
    assert final_state.revision_count == 0
    assert final_state.niche_brief is not None
    assert final_state.design_asset is not None
    assert final_state.audit_result is not None
    assert final_state.audit_result.approved is True
    assert final_state.seo_listing is not None
    assert len(final_state.seo_listing.tags) == 13
    assert final_state.printify_product_id == "prod_mock_77310"

    # Verify upscaled 4500x5400 PNG was written at 300 DPI
    upscaled_path = Path(final_state.design_asset.print_ready_path)
    assert upscaled_path.exists()
    with Image.open(upscaled_path) as img:
        assert img.size == (4500, 5400)


def test_audit_gate_loops_back_to_muse_when_confidence_below_075(tmp_path: Path):
    # First audit scores 0.60 (< 0.75) -> loops back to muse_designer -> second audit scores 0.89 -> approved
    final_state = execute_pipeline(
        seed_category="botanical book club apparel",
        dry_run=True,
        output_dir=tmp_path,
        confidence_sequence=[0.60, 0.89],
    )

    assert final_state.status == "completed"
    assert final_state.revision_count == 1
    assert final_state.audit_result is not None
    assert final_state.audit_result.approved is True
    assert final_state.audit_result.render_confidence == 0.89
    assert final_state.printify_product_id == "prod_mock_77310"


def test_audit_gate_halts_after_max_revisions(tmp_path: Path):
    # Three consecutive low-confidence renders (< 0.75) -> halts after revision_count reaches 2
    final_state = execute_pipeline(
        seed_category="botanical book club apparel",
        dry_run=True,
        output_dir=tmp_path,
        confidence_sequence=[0.50, 0.61, 0.70],
    )

    assert final_state.status == "halted"
    assert final_state.revision_count == 2
    assert final_state.audit_result is not None
    assert final_state.audit_result.approved is False
    assert final_state.printify_product_id is None
