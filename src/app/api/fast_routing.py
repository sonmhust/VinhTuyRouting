# src/app/api/fast_routing.py
"""
Unified Routing API
- Single endpoint nhận node_id (int), coords ([lat, lon]), hoặc address (str)
- Tự động resolve input type và route
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import ORJSONResponse
from typing import Optional, List, Dict, Any, Literal, Union
from pydantic import BaseModel, Field, field_validator
import time

from src.services.fast_pathfinding_service import FastRoutingService
from src.services.graph_builder import C_HIGHWAY, C_CONTEXT

router = APIRouter(default_response_class=ORJSONResponse)

_routing_service: Optional[FastRoutingService] = None

# Threshold cho exact match (score >= này thì dùng node_id trực tiếp)
EXACT_MATCH_THRESHOLD = 80


def set_routing_service(service: FastRoutingService):
    global _routing_service
    _routing_service = service


def _check_service():
    if _routing_service is None or _routing_service.graph is None:
        raise HTTPException(status_code=503, detail="Service chưa sẵn sàng")


# ======================================================================
# Pydantic Models
# ======================================================================

class RouteRequest(BaseModel):
    """
    Unified Route Request
    
    origin/destination có thể là:
    - int: Node ID (từ /suggest hoặc đã biết trước)
    - List[float]: Tọa độ [lat, lon] (từ click map)
    - str: Địa chỉ văn bản (manual entry - gõ và bấm Enter)
    
    Examples:
        {"origin": 5629422908, "destination": [21.0045, 105.8433]}
        {"origin": [21.001, 105.855], "destination": [21.010, 105.880]}
        {"origin": "Phố Vĩnh Tuy", "destination": "Ngõ 121 Lê Thanh Nghị"}
        {"origin": "Phố Vĩnh Tuy", "destination": [21.010, 105.880]}
    """
    origin: Union[int, List[float], str] = Field(
        ..., 
        description="Điểm bắt đầu: node_id (int), [lat, lon], hoặc địa chỉ (str)"
    )
    destination: Union[int, List[float], str] = Field(
        ..., 
        description="Điểm kết thúc: node_id (int), [lat, lon], hoặc địa chỉ (str)"
    )
    weather: Literal["normal", "rain", "flood"] = Field(
        default="normal",
        description="Điều kiện thời tiết"
    )
    blocking_geometries: List[Dict[str, Any]] = Field(
        default=[],
        description="Vùng cấm đi qua (GeoJSON)"
    )
    flood_areas: List[Dict[str, Any]] = Field(
        default=[],
        description="Vùng ngập (tăng trọng số)"
    )
    
    @field_validator('origin', 'destination')
    @classmethod
    def validate_point(cls, v):
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            if len(v.strip()) < 2:
                raise ValueError("Địa chỉ phải có ít nhất 2 ký tự")
            return v.strip()
        if isinstance(v, list):
            if len(v) != 2:
                raise ValueError("Tọa độ phải có đúng 2 phần tử [lat, lon]")
            if not all(isinstance(x, (int, float)) for x in v):
                raise ValueError("Tọa độ phải là số")
            lat, lon = v
            if not (-90 <= lat <= 90):
                raise ValueError(f"Latitude phải trong khoảng [-90, 90], got {lat}")
            if not (-180 <= lon <= 180):
                raise ValueError(f"Longitude phải trong khoảng [-180, 180], got {lon}")
            return v
        raise ValueError("Phải là node_id (int), [lat, lon], hoặc địa chỉ (str)")


class ResolvedNode(BaseModel):
    """Kết quả resolve một điểm"""
    node_id: int
    lat: float
    lon: float
    input_type: str  # "node_id", "coords", "address_exact", "address_fuzzy"
    snapped: bool  # True nếu đã snap từ coords
    matched_address: Optional[str] = None  # Địa chỉ đã match (nếu input là str)
    match_score: Optional[float] = None  # Score của match (nếu input là str)


# ======================================================================
# Core Logic: Resolve Node
# ======================================================================

def _resolve_node(point: Union[int, List[float], str]) -> ResolvedNode:
    """
    Resolve input thành Node ID
    
    - Nếu int: Kiểm tra node tồn tại trong graph
    - Nếu [lat, lon]: Smart snap bằng KD-Tree đến LSCC
    - Nếu str: Tìm trong FTS5 database
      + Exact/High match (score >= 80): dùng node_id trực tiếp
      + Fuzzy/Partial match: dùng coords rồi snap
    
    Returns:
        ResolvedNode với thông tin đầy đủ
    
    Raises:
        HTTPException nếu không resolve được
    """
    # Case 1: Input là node_id (int)
    if isinstance(point, int):
        if not _routing_service.graph.has_node(point):
            raise HTTPException(
                status_code=400,
                detail=f"Node ID {point} không tồn tại trong graph"
            )
        node = _routing_service.graph.get_node(point)
        return ResolvedNode(
            node_id=point,
            lat=node.lat,
            lon=node.lon,
            input_type="node_id",
            snapped=False
        )
    
    # Case 2: Input là address (str) - Manual Entry
    if isinstance(point, str):
        # Bước 1: Tìm kiếm trong FTS5 database
        results = _routing_service.search_address(point, limit=1)
        
        if not results:
            raise HTTPException(
                status_code=400,
                detail=f"Không tìm thấy địa chỉ: '{point}'"
            )
        
        best_match = results[0]
        match_score = best_match.get("score", 0)
        
        # Bước 2: Phân loại kết quả
        if match_score >= EXACT_MATCH_THRESHOLD:
            # Exact/High Match → Dùng node_id trực tiếp (NHANH)
            return ResolvedNode(
                node_id=best_match["node_id"],
                lat=best_match["lat"],
                lon=best_match["lon"],
                input_type="address_exact",
                snapped=False,
                matched_address=best_match["address"],
                match_score=match_score
            )
        else:
            # Fuzzy/Partial Match → Dùng coords rồi snap (AN TOÀN)
            # Vì kết quả không chắc chắn, ta dùng tọa độ trung tâm và snap
            node_id = _routing_service.find_nearest_node(
                best_match["lat"], 
                best_match["lon"]
            )
            
            if node_id is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Không tìm thấy node gần địa chỉ: '{point}'"
                )
            
            node = _routing_service.graph.get_node(node_id)
            return ResolvedNode(
                node_id=node_id,
                lat=node.lat,
                lon=node.lon,
                input_type="address_fuzzy",
                snapped=True,
                matched_address=best_match["address"],
                match_score=match_score
            )
    
    # Case 3: Input là [lat, lon] - Click Map
    else:
        lat, lon = point
        node_id = _routing_service.find_nearest_node(lat, lon)
        
        if node_id is None:
            raise HTTPException(
                status_code=400,
                detail=f"Không tìm thấy node gần tọa độ [{lat}, {lon}]"
            )
        
        node = _routing_service.graph.get_node(node_id)
        return ResolvedNode(
            node_id=node_id,
            lat=node.lat,
            lon=node.lon,
            input_type="coords",
            snapped=True
        )


def _process_geometries(blocking, flood):
    """Xử lý blocking/flood geometries"""
    all_ban = blocking or []
    
    for geom in (flood or []):
        if "properties" not in geom:
            geom["properties"] = {}
        geom["properties"]["blockType"] = "flood"
    
    all_geoms = all_ban + (flood or [])
    
    if not all_geoms or _routing_service is None:
        return set(), {}
    
    return _routing_service.apply_blocking_geometries(all_geoms)


# ======================================================================
# UNIFIED ROUTING ENDPOINT
# ======================================================================

@router.post("/route", response_class=ORJSONResponse)
def unified_route(request: RouteRequest):
    """
    🚀 UNIFIED ROUTING ENDPOINT
    
    Nhận **node_id (int)**, **coords ([lat, lon])**, hoặc **address (str)** cho origin/destination.
    
    ## Input Types:
    
    | Type | Format | Example | Khi nào dùng |
    |------|--------|---------|--------------|
    | Node ID | `int` | `5629422908` | User chọn từ /suggest |
    | Coords | `[lat, lon]` | `[21.0045, 105.8433]` | User click map |
    | Address | `str` | `"Phố Vĩnh Tuy"` | User gõ và bấm Enter |
    
    ## Performance:
    
    - **Node ID → Node ID**: ~1-2ms (fastest, skip KD-Tree)
    - **Address (exact) → Node ID**: ~2-3ms (FTS5 search + direct routing)
    - **Address (fuzzy) → Coords**: ~3-5ms (FTS5 + KD-Tree snap)
    - **Coords → Coords**: ~3-5ms (cần 2x KD-Tree lookup)
    
    ## Address Resolution Logic:
    
    1. Tìm trong FTS5 database
    2. Nếu **exact match** (score >= 80): dùng `node_id` trực tiếp → **NHANH**
    3. Nếu **fuzzy match**: dùng coords rồi KD-Tree snap → **AN TOÀN**
    
    ## Examples:
    
    ```json
    // Node ID (từ /suggest - fastest)
    {"origin": 5629422908, "destination": 8259084794}
    
    // Coords (click map)
    {"origin": [21.001, 105.855], "destination": [21.010, 105.880]}
    
    // Address (manual entry)
    {"origin": "Phố Vĩnh Tuy", "destination": "Ngõ 121 Lê Thanh Nghị"}
    
    // Mixed
    {"origin": 5629422908, "destination": "Phố Thanh Nhàn"}
    {"origin": "Phố Vĩnh Tuy", "destination": [21.010, 105.880]}
    
    // Với weather
    {"origin": "Phố Vĩnh Tuy", "destination": "Phố Thanh Nhàn", "weather": "rain"}
    ```
    """
    _check_service()
    
    start_time = time.perf_counter()
    
    try:
        # Step 1: Resolve origin và destination
        origin_resolved = _resolve_node(request.origin)
        dest_resolved = _resolve_node(request.destination)
        
        resolve_time = time.perf_counter() - start_time
        
        # Check same node
        if origin_resolved.node_id == dest_resolved.node_id:
            raise HTTPException(
                status_code=400,
                detail="Origin và destination trùng nhau"
            )
        
        # Step 2: Process blocking geometries
        blocked, multipliers = _process_geometries(
            request.blocking_geometries,
            request.flood_areas
        )
        
        # Step 3: Execute routing (use node IDs directly)
        result = _routing_service.find_route_by_node_ids(
            origin_resolved.node_id,
            dest_resolved.node_id,
            request.weather,
            blocked,
            multipliers
        )
        
        total_time = time.perf_counter() - start_time
        
        # Step 4: Enrich response
        if "error" not in result:
            # Build resolved info
            origin_info = {
                "node_id": origin_resolved.node_id,
                "lat": origin_resolved.lat,
                "lon": origin_resolved.lon,
                "input_type": origin_resolved.input_type,
                "snapped": origin_resolved.snapped
            }
            if origin_resolved.matched_address:
                origin_info["matched_address"] = origin_resolved.matched_address
                origin_info["match_score"] = origin_resolved.match_score
            
            dest_info = {
                "node_id": dest_resolved.node_id,
                "lat": dest_resolved.lat,
                "lon": dest_resolved.lon,
                "input_type": dest_resolved.input_type,
                "snapped": dest_resolved.snapped
            }
            if dest_resolved.matched_address:
                dest_info["matched_address"] = dest_resolved.matched_address
                dest_info["match_score"] = dest_resolved.match_score
            
            result["resolved"] = {
                "origin": origin_info,
                "destination": dest_info
            }
            result["stats"]["resolve_time_ms"] = round(resolve_time * 1000, 2)
            result["stats"]["total_time_ms"] = round(total_time * 1000, 2)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ======================================================================
# Geocoding Endpoints (Local - SQLite FTS5)
# ======================================================================

@router.get("/suggest", response_class=ORJSONResponse)
def suggest_address(
    q: str = Query(..., min_length=2, description="Chuỗi tìm kiếm (min 2 ký tự)"),
    limit: int = Query(default=5, ge=1, le=20, description="Số kết quả tối đa")
):
    """
    Autocomplete địa chỉ - LOCAL, không gọi API bên ngoài
    
    Thời gian response: < 5ms
    
    ## Flow:
    1. User gõ địa chỉ → FE gọi endpoint này
    2. Nhận danh sách gợi ý với `node_id`
    3. User chọn → FE gửi `node_id` vào `/route`
    
    ## Response:
    ```json
    {
        "results": [
            {"node_id": 5629422908, "address": "Phố Vĩnh Tuy", "lat": 21.005, "lon": 105.865, "score": 100}
        ]
    }
    ```
    """
    _check_service()
    
    start = time.perf_counter()
    results = _routing_service.search_address(q, limit)
    elapsed_ms = (time.perf_counter() - start) * 1000
    
    return {
        "query": q,
        "results": results,
        "count": len(results),
        "time_ms": round(elapsed_ms, 2)
    }


@router.get("/geocoding/stats", response_class=ORJSONResponse)
def get_geocoding_stats():
    """Thống kê local geocoding database"""
    _check_service()
    return _routing_service.get_geocoding_stats()


# ======================================================================
# Info Endpoints
# ======================================================================

@router.get("/info", response_class=ORJSONResponse)
def get_info():
    """Thông tin service"""
    if _routing_service is None or _routing_service.graph is None:
        return {"status": "not_ready"}
    
    bounds = _routing_service.graph.get_bounds()
    geocoding = _routing_service.get_geocoding_stats()
    
    return {
        "status": "ready",
        "graph": {
            "nodes": _routing_service.graph.node_count,
            "edges": _routing_service.graph.edge_count,
            "bounds": {
                "min_lat": bounds[0], 
                "min_lon": bounds[1], 
                "max_lat": bounds[2], 
                "max_lon": bounds[3]
            }
        },
        "geocoding": geocoding,
        "weather_conditions": ["normal", "rain", "flood"],
        "input_types": {
            "node_id": "int - User chọn từ /suggest (fastest)",
            "coords": "[lat, lon] - User click map",
            "address": "str - User gõ và bấm Enter (manual entry)"
        },
        "endpoints": {
            "route": "POST /route - Unified routing (node_id, coords, hoặc address)",
            "suggest": "GET /suggest?q=... - Autocomplete địa chỉ"
        }
    }


@router.get("/coefficients", response_class=ORJSONResponse)
def get_coefficients(weather: Literal["normal", "rain", "flood"] = Query(default="normal")):
    """Bảng hệ số trọng số theo thời tiết"""
    ctx = C_CONTEXT.get(weather, C_CONTEXT["normal"])
    return {
        "weather": weather,
        "coefficients": sorted([
            {
                "type": t, 
                "c_highway": C_HIGHWAY[t], 
                "c_context": ctx.get(t, 1.0), 
                "total": round(C_HIGHWAY[t] * ctx.get(t, 1.0), 3)
            }
            for t in C_HIGHWAY
        ], key=lambda x: x["total"])
    }


@router.get("/nearest-node", response_class=ORJSONResponse)
def find_nearest_node(lat: float, lon: float):
    """
    Tìm node gần nhất (KD-Tree)
    
    Hữu ích để debug hoặc preview snap position
    """
    _check_service()
    
    node_id = _routing_service.find_nearest_node(lat, lon)
    if node_id is None:
        return {"error": "Không tìm thấy"}
    
    node = _routing_service.graph.get_node(node_id)
    return {"node_id": node_id, "lat": node.lat, "lon": node.lon}
