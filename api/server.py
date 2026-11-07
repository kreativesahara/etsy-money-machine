import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from main import execute_pipeline

app = FastAPI(
    title="Etsy Production Terminal API",
    description="FastAPI + WebSocket backend for the Autonomous Etsy POD Multi-Agent Pipeline",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DASHBOARD_HTML_PATH = Path(__file__).resolve().parent.parent / "dashboard" / "index.html"


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, event: Dict[str, Any]) -> None:
        stale: List[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_json(event)
            except Exception:
                stale.append(connection)
        for conn in stale:
            self.disconnect(conn)


manager = ConnectionManager()

STORES_TELEMETRY: Dict[str, Dict[str, Any]] = {
    "store_1": {
        "id": "store_1",
        "label": "ETSY 1: APPAREL",
        "visits": "71.5K",
        "orders": 264,
        "conversion_rate": "0.3%",
        "revenue": 10915.27,
        "active_agents": 3,
        "live_workflows": 9,
    },
    "store_2": {
        "id": "store_2",
        "label": "ETSY 2: CANDLES",
        "visits": "24.1K",
        "orders": 98,
        "conversion_rate": "0.4%",
        "revenue": 3180.50,
        "active_agents": 3,
        "live_workflows": 5,
    },
    "store_3": {
        "id": "store_3",
        "label": "ETSY 3: CUSTOM PORTRAIT PRODUCTS",
        "visits": "14.8K",
        "orders": 52,
        "conversion_rate": "0.35%",
        "revenue": 1904.23,
        "active_agents": 3,
        "live_workflows": 4,
    },
}

RECENT_DESIGNS: List[Dict[str, Any]] = [
    {
        "id": "dsn-01",
        "design_title": "IN MY GARDEN ERA DESIGN",
        "phrase": "In My Garden Era",
        "category": "apparel",
        "render_confidence": 0.92,
        "status": "APPROVED",
        "printify_product_id": "prod_mock_77310",
    },
    {
        "id": "dsn-02",
        "design_title": "COFFEE AND COZY DESIGN",
        "phrase": "Coffee & Cozy Reading Club",
        "category": "apparel",
        "render_confidence": 0.88,
        "status": "APPROVED",
        "printify_product_id": "prod_mock_77311",
    },
    {
        "id": "dsn-03",
        "design_title": "BOOK CLUB BABE DESIGN",
        "phrase": "Book Club Babe",
        "category": "apparel",
        "render_confidence": 0.79,
        "status": "APPROVED",
        "printify_product_id": "prod_mock_77312",
    },
    {
        "id": "dsn-04",
        "design_title": "BOTANICAL APOTHECARY DESIGN",
        "phrase": "Quiet Morning Apothecary",
        "category": "candle",
        "render_confidence": 0.75,
        "status": "QUEUED_AUDIT",
        "printify_product_id": "prod_mock_77313",
    },
]


class RunPipelineRequest(BaseModel):
    seed_category: str = "botanical book club apparel"
    dry_run: bool = True


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    if DASHBOARD_HTML_PATH.exists():
        return FileResponse(DASHBOARD_HTML_PATH)
    return HTMLResponse("<h1>Etsy Production Terminal Backend Running</h1>")


@app.get("/api/telemetry")
async def get_telemetry() -> Dict[str, Any]:
    return {
        "stores": STORES_TELEMETRY,
        "total_revenue": 16000.00,
        "designs": RECENT_DESIGNS,
        "crews": [
            {
                "agent": "FORGE",
                "role": "Product Fabrication - Printify routing queue",
                "status": "ONLINE",
                "detail": "Uploading 4500x5400 @ 300 DPI PNGs to Blueprint #12",
            },
            {
                "agent": "MUSE",
                "role": "Image Design Agent - GPT Images 2",
                "status": "RENDERING",
                "detail": "GPT IMAGES 2: rendering standalone floral shirt artwork",
            },
            {
                "agent": "SEO / LISTING AGENT",
                "role": "Drafting thumbnail order & 13 tags",
                "status": "ACTIVE",
                "detail": "Expanding long-tail tags: soft girl, book club, coffee, garden gift",
            },
        ],
    }


@app.post("/api/run")
async def trigger_pipeline_run(req: RunPipelineRequest) -> Dict[str, Any]:
    await manager.broadcast(
        {
            "type": "AGENT_EVENT",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "ULTRON",
            "message": f"Dispatching pipeline run for seed category: '{req.seed_category}'",
        }
    )
    state = await asyncio.to_thread(
        execute_pipeline,
        seed_category=req.seed_category,
        dry_run=req.dry_run,
    )
    payload = state.model_dump()
    if state.design_asset and state.audit_result:
        RECENT_DESIGNS.insert(
            0,
            {
                "id": f"dsn-{len(RECENT_DESIGNS) + 1:02d}",
                "design_title": f"{state.design_asset.design_title} DESIGN",
                "phrase": state.niche_brief.phrase_on_product if state.niche_brief else "",
                "category": state.niche_brief.product_category if state.niche_brief else "apparel",
                "render_confidence": state.audit_result.render_confidence,
                "status": "APPROVED" if state.audit_result.approved else "HELD",
                "printify_product_id": state.printify_product_id or "pending",
            },
        )
        del RECENT_DESIGNS[4:]

    await manager.broadcast(
        {
            "type": "PIPELINE_COMPLETED",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "state": payload,
            "designs": RECENT_DESIGNS,
        }
    )
    return {"status": "ok", "pipeline_state": payload}


@app.post("/api/approve/{product_id}")
async def approve_and_handoff(product_id: str) -> Dict[str, Any]:
    for item in RECENT_DESIGNS:
        if item.get("printify_product_id") == product_id or item.get("id") == product_id:
            item["status"] = "PUBLISHED"
    event = {
        "type": "HANDOFF_APPROVED",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "product_id": product_id,
        "message": f"FORGE: Product {product_id} approved and routed to Etsy live publishing queue.",
    }
    await manager.broadcast(event)
    return event


@app.websocket("/ws/terminal")
async def terminal_websocket(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        await websocket.send_json(
            {
                "type": "INITIAL_SNAPSHOT",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "stores": STORES_TELEMETRY,
                "designs": RECENT_DESIGNS,
            }
        )
        while True:
            data = await websocket.receive_text()
            await websocket.send_json(
                {
                    "type": "ACK",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "received": data,
                }
            )
    except WebSocketDisconnect:
        manager.disconnect(websocket)
