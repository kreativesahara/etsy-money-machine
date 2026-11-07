# Autonomous Etsy Print-on-Demand (POD) Multi-Agent Blueprint

This specification translates the gamified "Space Dungeon / Etsy Production Terminal" multi-agent simulation into a production-ready Python codebase and retro-terminal CRT dashboard.

## 1. System Overview & Simulation-to-Production Mapping

| Video Component | Role in the Simulation | Production Module | Core APIs & Libraries |
| :--- | :--- | :--- | :--- |
| **Ultron (Center Station)** | Supervisor agent ("Hermes agent") scheduling and monitoring worker rooms | `agents/ultron_supervisor.py` | LangGraph (`StateGraph`) |
| **Nova (Research Lab)** | Identifies high-velocity Etsy listings and proven buyer niches ("sell what sells") | `agents/nova_research.py` | Etsy Open API v3 (`findAllListingsActive`) + Trademark Screen |
| **Muse (Etsy Room Crew)** | Generates transparent shirt/mug/candle graphics (e.g., "In My Garden Era", "Book Club Babe") | `agents/muse_designer.py` | OpenAI `gpt-image-2` + Pillow (`4500x5400` @ 300 DPI LANCZOS upscaling) |
| **Audit Gate** | Scores artwork quality (75% render confidence) and holds defective renders | `agents/audit_gate.py` | Multimodal Vision LLM (`gpt-4o`) structured output + trademark/policy filter |
| **SEO / Listing Agent** | Expands long-tail buyer tags ("soft girl, book club, coffee, garden gift") and titles | `agents/seo_listing.py` | Structured LLM output enforcing Etsy's 140-char title and 13x20-char tag limits |
| **Forge (Product Fabrication)** | Uploads artwork to POD templates and routes products to the publishing queue | `agents/forge_printify.py` | Printify REST API v1 + Etsy Open API v3 Listings |
| **Etsy Production Terminal** | Green-phosphor CRT dashboard showing room crews, active workflows, and live renders | `dashboard/index.html` & `api/server.py` | FastAPI WebSockets + Tailwind CSS CRT terminal UI |

## 2. Quick Commands

```powershell
# Run end-to-end dry run locally with mocked APIs
.\.venv\Scripts\python.exe main.py --dry-run

# Simulate an Audit Gate retry loop (< 0.75 confidence on attempt 1 -> re-render -> pass on attempt 2)
.\.venv\Scripts\python.exe main.py --dry-run --simulate-retry

# Run unit tests
.\.venv\Scripts\python.exe -m pytest -v

# Launch the FastAPI + WebSocket server & CRT Dashboard on http://127.0.0.1:8000
.\.venv\Scripts\python.exe -m uvicorn api.server:app --reload --port 8000
```
