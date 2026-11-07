# Statement of Work (SOW) — Autonomous Etsy Print-on-Demand (POD) Multi-Agent System

**Project Name:** Etsy Money Machine (Autonomous Etsy POD Production Terminal)  
**Version:** 2.0.0  
**Status:** Production / Delivered  

---

## 1. Executive Summary & Project Objective

The objective of this project is to design, build, and deploy an autonomous multi-agent Print-on-Demand (POD) production pipeline and real-time Command Center (`Etsy Production Terminal`). The system automates the end-to-end merchandise lifecycle across three Etsy store verticals (**Apparel**, **Soy Candles**, and **Custom Portraits**)—from market trend discovery and trademark screening to 300 DPI artwork generation, multimodal vision quality assurance, Etsy SEO metadata drafting, and Printify product fabrication.

---

## 2. Scope of Work

### 2.1 Multi-Agent Orchestration (`LangGraph` State Machine)
- **Ultron Supervisor (`agents/ultron_supervisor.py`):** Central `StateGraph` orchestrator managing deterministic state transitions (`PipelineState`), conditional QA retry routing, and real-time node telemetry emissions.
- **Nova Research Agent (`agents/nova_research.py`):** Queries active high-velocity Etsy listings via Etsy Open API v3 (`findAllListingsActive`), screens against restricted USPTO trademark phrases, and produces a structured `NicheBrief`.
- **Muse Designer Agent (`agents/muse_designer.py`):** Generates transparent RGBA merchandise artwork via OpenAI `gpt-image-2` and executes automated `LANCZOS` upscaling to Printify's exact **4500x5400 px @ 300 DPI** print specification.
- **Audit Gate Agent (`agents/audit_gate.py`):** Performs multimodal vision QA (`gpt-4o`) verifying exact OCR phrase spelling, alpha-channel cleanliness, and trademark safety. Enforces a `>= 75%` (`0.75`) render confidence threshold with up to 3 automatic re-render loops.
- **SEO & Listing Agent (`agents/seo_listing.py`):** Generates policy-compliant Etsy listing metadata (`EtsySEOListing`) enforcing a `<= 140` character title, mandatory AI & Printify production partner disclosure, and **13 unique long-tail tags** (`<= 20` characters each).
- **Forge Fabrication Agent (`agents/forge_printify.py`):** Uploads print-ready 4500x5400 PNG assets to Printify REST API v1 and creates products mapped to store-specific Blueprints and Print Providers.

### 2.2 Multi-Store Vertical Support
- **Store 1 (`store_1` — Apparel):** Printify Blueprint `#12` (Bella+Canvas 3001 Unisex Tee, Provider `#99`, \$24.99).
- **Store 2 (`store_2` — Candles):** Printify Blueprint `#384` (9oz Amber Glass Soy Candle, Provider `#72`, \$28.99).
- **Store 3 (`store_3` — Custom Portraits):** Printify Blueprint `#55` (Custom Matte Portrait Canvas, Provider `#41`, \$39.99).

### 2.3 Real-Time Command Center & API Server
- **FastAPI + WebSocket Backend (`api/server.py`):** REST endpoints for telemetry, pipeline execution (`/api/run`), batch queue auditing (`/api/audit-queue`), single-design re-rendering (`/api/designs/{id}/rerender`), live publishing handoff (`/api/handoff-live`, `/api/approve/{id}`), state reset (`/api/reset`), and live `/ws/terminal` WebSocket broadcasting.
- **CRT Production Terminal UI (`dashboard/index.html`):** Interactive retro-terminal dashboard displaying multi-store KPIs, live agent node execution progress, design inspector drawers, confidence badges, and one-click handoff controls.

### 2.4 Cloud-Ready Persistence & Containerization
- **Hybrid Storage Layer (`services/storage_service.py`):** Persists structured pipeline run records to **PostgreSQL 17** (`db/init/001_init_schema.sql`) with automatic fallback to local JSONL (`artifacts/storage/pipeline_runs.jsonl`), and uploads PNG renders to **S3/MinIO** object storage when enabled.
- **Docker Infrastructure (`Dockerfile`, `docker-compose.yml`):** Multi-service container orchestration for the FastAPI application, PostgreSQL 17, and MinIO S3-compatible object storage with health checks and persistent volumes.

---

## 3. Deliverables

| # | Deliverable | Location | Description |
| :--- | :--- | :--- | :--- |
| **D1** | **Pydantic v2 Data Contracts** | `schemas/models.py` | Strongly-typed schemas (`NicheBrief`, `DesignAsset`, `AuditResult`, `EtsySEOListing`, `PipelineState`) |
| **D2** | **5-Agent LangGraph Pipeline** | `agents/*.py` | Complete implementation of `NOVA`, `MUSE`, `AUDIT GATE`, `SEO AGENT`, `FORGE`, and `ULTRON` supervisor |
| **D3** | **CLI Runner & Mock Engine** | `main.py` | CLI supporting `--dry-run`, `--store-id`, `--seed-category`, `--simulate-retry`, and live API execution |
| **D4** | **FastAPI + WebSocket Server** | `api/server.py` | REST + WebSocket backend managing multi-store state and live telemetry streaming |
| **D5** | **Command Center Dashboard** | `dashboard/index.html` | Interactive CRT Production Terminal UI for managing all 3 Etsy stores |
| **D6** | **Storage & Etsy Clients** | `services/*.py`, `db/init/` | Etsy Open API v3 header builder/client and PostgreSQL + S3/MinIO + JSONL storage service |
| **D7** | **Container Stack** | `Dockerfile`, `docker-compose.yml` | Production Docker image and 3-service Compose stack (`app`, `postgres`, `minio`) |
| **D8** | **Automated Test Suite** | `tests/test_*.py` | Pytest suite covering state transitions, retry gates, SEO constraints, API routes, and storage |
| **D9** | **Documentation** | `README.md`, `etsy_pod_agent_blueprint.md`, `SOW.md` | Setup, architecture blueprint, operational guide, and Statement of Work |

---

## 4. Acceptance Criteria

1. **Print Specification Compliance:** Every approved design asset must be output as an RGBA PNG upscaled to exactly `4500x5400` pixels at `300 DPI`.
2. **Audit Gate Enforcement:** Any render scoring below `0.75` (`75%`) confidence must be held and routed back to `MUSE` for re-rendering; pipeline halts safely if `revision_count >= 3` without approval.
3. **Etsy Policy & SEO Validation:**
   - Listing titles must not exceed `140` characters.
   - Listing tags must contain up to `13` tags, each strictly `<= 20` characters.
   - Product descriptions must include explicit AI creation and Printify production partner disclosure (`ai_disclosure_included = True`).
4. **Credential Safety:** Live runs (`dry_run=False`) must validate required API keys (`OPENAI_API_KEY`, `ETSY_API_KEYSTRING`, `ETSY_SHARED_SECRET`, `PRINTIFY_API_TOKEN`, `PRINTIFY_SHOP_ID`) via `MissingCredentialsError` before invoking external APIs, and format Etsy's `x-api-key` header as `keystring:shared_secret`.
5. **Test Verification:** 100% of unit and integration tests in `tests/` pass under `pytest -v` without requiring live external network access.

---

## 5. Out of Scope / Assumptions

- **Etsy OAuth Token Refresh UI:** Live Etsy publishing assumes a valid OAuth access token (`ETSY_OAUTH_ACCESS_TOKEN`) or utilizes Printify's native Etsy store integration (`publish.json`) once connected in the Printify dashboard.
- **Automated Ad Spend Management:** Etsy Offsite Ads and promoted listing budget adjustments remain manually controlled by the shop owner.

