from fastapi import FastAPI
from fastapi.responses import ORJSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pathlib import Path

from src.services.fast_pathfinding_service import FastRoutingService
from src.services.overpass_service import fetch_from_overpass
from src.services.graph_builder import build_graph_from_osm

from src.app.api.fast_routing import router as routing_router

# Global routing service
fast_routing_service: FastRoutingService = None

# Phường Vĩnh Tuy, Hai Bà Trưng, Hà Nội (cố định)
VINH_TUY_BBOX = (20.9850, 105.8550, 21.0150, 105.8950)


def init_routing_service():
    """Khởi tạo routing service với bản đồ Vĩnh Tuy"""
    global fast_routing_service
    
    print("Đang khởi tạo Routing Service...")
    print(f"Khu vực: Phường Vĩnh Tuy, bbox: {VINH_TUY_BBOX}")
    
    fast_routing_service = FastRoutingService()
    success = fast_routing_service.load_from_bbox(VINH_TUY_BBOX)
    
    if success:
        print(f"✓ Routing Service sẵn sàng: {fast_routing_service.graph.node_count} nodes, "
              f"{fast_routing_service.graph.edge_count} edges")
    else:
        print("✗ Không thể khởi tạo Routing Service")
        fast_routing_service = None
    
    return fast_routing_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load data at startup"""
    global fast_routing_service

    print("=" * 60)
    print("SMART ROUTING API - Phường Vĩnh Tuy")
    print("=" * 60)
    
    fast_routing_service = init_routing_service()
    
    from src.app.api.fast_routing import set_routing_service
    set_routing_service(fast_routing_service)
    
    app.include_router(routing_router, prefix="/api/v1/routing", tags=["routing"])

    print("\n" + "=" * 60)
    print("API READY!")
    print("=" * 60)
    if fast_routing_service:
        print("\nEndpoints:")
        print("  POST /api/v1/routing/route    - Unified routing (int | [lat,lon] | str)")
        print("  GET  /api/v1/routing/suggest  - Autocomplete địa chỉ local")
        print("  GET  /api/v1/routing/info     - Thông tin service")
        print("\nInput Types:")
        print("  int         - Node ID (từ /suggest) → Fastest")
        print("  [lat, lon]  - Coords (click map) → KD-Tree snap")
        print("  str         - Địa chỉ (manual entry) → FTS5 search")
        print("\nExamples:")
        print('  {"origin": 5629422908, "destination": 8259084794}')
        print('  {"origin": [21.001, 105.855], "destination": [21.010, 105.880]}')
        print('  {"origin": "Pho Vinh Tuy", "destination": "Pho Thanh Nhan"}')
    print()

    yield
    print("Shutting down...")


app = FastAPI(
    lifespan=lifespan,
    title="Routing API - Vĩnh Tuy",
    description="Gay Gay Gay",
    version="36.36.36",
    default_response_class=ORJSONResponse
)

# CORS middleware - cho phép frontend gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cho phép tất cả origins (có thể giới hạn trong production)
    allow_credentials=True,
    allow_methods=["*"],  # Cho phép tất cả methods (GET, POST, OPTIONS, etc.)
    allow_headers=["*"],  # Cho phép tất cả headers
)


@app.get("/health", tags=["health"])
def health_check():
    """Kiểm tra trạng thái API"""
    if fast_routing_service and fast_routing_service.graph:
        return {
            "status": "healthy",
            "area": "Phường Vĩnh Tuy",
            "nodes": fast_routing_service.graph.node_count,
            "edges": fast_routing_service.graph.edge_count,
            "bounds": fast_routing_service.graph.get_bounds()
        }
    return {"status": "unhealthy", "message": "Routing service chưa sẵn sàng"}


@app.get("/", tags=["info"])
def root():
    """Serve frontend HTML"""
    static_dir = Path("static")
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {
        "name": "Smart Routing API",
        "area": "Phường Vĩnh Tuy, Hà Nội",
        "docs": "/docs",
        "health": "/health",
        "frontend": "/static/index.html"
    }

# Mount static files
static_dir = Path("static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
