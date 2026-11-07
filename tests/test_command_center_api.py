from pathlib import Path
from fastapi.testclient import TestClient
from api.server import app, STATE_FILE_PATH
from main import execute_pipeline


def test_store_aware_pipeline_and_live_telemetry_callbacks(tmp_path: Path):
    events: list[dict] = []

    final_state = execute_pipeline(
        seed_category="Rainy Bookstore & Cedarwood",
        dry_run=True,
        output_dir=tmp_path,
        confidence_sequence=[0.64, 0.95],
        store_id="store_2",
        event_callback=lambda e: events.append(e),
    )

    assert final_state.status == "completed"
    assert final_state.store_id == "store_2"
    assert final_state.revision_count == 1
    assert final_state.niche_brief is not None
    assert final_state.niche_brief.product_category == "candle"
    assert final_state.seo_listing is not None
    assert len(final_state.seo_listing.tags) == 13
    assert all(len(t) <= 20 for t in final_state.seo_listing.tags)

    event_types = [e["type"] for e in events]
    assert "NODE_STARTED" in event_types
    assert "AUDIT_RETRY" in event_types
    assert "NODE_COMPLETED" in event_types


def test_command_center_api_endpoints():
    client = TestClient(app)

    # Reset demo state first
    reset_res = client.post("/api/reset")
    assert reset_res.status_code == 200
    assert STATE_FILE_PATH.exists()

    # Check telemetry for store_2 (Candles)
    tel_res = client.get("/api/telemetry?store_id=store_2")
    assert tel_res.status_code == 200
    tel_data = tel_res.json()
    assert "store_1" in tel_data["stores"]
    assert "store_2" in tel_data["stores"]
    assert "store_3" in tel_data["stores"]
    assert len(tel_data["designs_by_store"]["store_2"]) == 4

    # Verify rendered PNG image serving
    first_design = tel_data["designs_by_store"]["store_1"][0]
    img_res = client.get(first_design["raw_image_url"])
    assert img_res.status_code == 200
    assert img_res.headers["content-type"] == "image/png"

    # Trigger interactive store_3 (Custom Portrait) run with retry simulation
    run_res = client.post(
        "/api/run",
        json={
            "store_id": "store_3",
            "seed_category": "Regal Renaissance Corgi Portrait",
            "dry_run": True,
            "simulate_retry": True,
        },
    )
    assert run_res.status_code == 200
    run_data = run_res.json()
    assert run_data["design"]["store_id"] == "store_3"
    assert run_data["design"]["category"] == "portrait"
    assert run_data["design"]["revision_count"] == 1
    assert len(run_data["design"]["seo_tags"]) == 13

    # Audit queue for store_1
    audit_res = client.post("/api/audit-queue", json={"store_id": "store_1"})
    assert audit_res.status_code == 200
    assert audit_res.json()["upgraded_count"] >= 1

    # Single-design re-render
    design_id = run_data["design"]["id"]
    rerender_res = client.post(f"/api/designs/{design_id}/rerender")
    assert rerender_res.status_code == 200
    assert rerender_res.json()["design"]["revision_count"] == 2

    # Handoff live for store_1
    handoff_res = client.post("/api/handoff-live", json={"store_id": "store_1"})
    assert handoff_res.status_code == 200
    assert handoff_res.json()["published_count"] >= 1

    # Reset back to clean baseline after test
    client.post("/api/reset")

