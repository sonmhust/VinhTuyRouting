# src/app/api/flood_zones.py
"""
Admin & User endpoints for flood zones
- Admin: CRUD flood zones (stored in SQLite)
- User: fetch active zones
"""
from fastapi import APIRouter, HTTPException, Body, Path, Query
from fastapi.responses import ORJSONResponse
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from src.services import flood_zone_service as fzs


router = APIRouter(default_response_class=ORJSONResponse)


# ============================
# Schemas
# ============================
class FloodZoneCreate(BaseModel):
    name: str
    type: str = "polygon"  # polygon | circle | multipolygon
    geometry: Dict[str, Any]
    severity: float = 5.0
    is_active: bool = True


class FloodZoneUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    geometry: Optional[Dict[str, Any]] = None
    severity: Optional[float] = None
    is_active: Optional[bool] = None


# ============================
# Admin endpoints
# ============================
@router.get("/admin/flood-zones", response_class=ORJSONResponse)
def admin_list_flood_zones(include_inactive: bool = Query(default=True)):
    """Lấy danh sách tất cả flood zones (kể cả inactive nếu muốn)"""
    zones = fzs.list_zones(include_inactive=include_inactive)
    return {"count": len(zones), "items": zones}


@router.post("/admin/flood-zones", response_class=ORJSONResponse)
def admin_create_flood_zone(payload: FloodZoneCreate):
    zone_id = fzs.create_zone(payload.dict())
    return {"id": zone_id, "message": "Created"}


@router.put("/admin/flood-zones/{zone_id}", response_class=ORJSONResponse)
def admin_update_flood_zone(zone_id: int = Path(...), payload: FloodZoneUpdate = Body(...)):
    ok = fzs.update_zone(zone_id, {k: v for k, v in payload.dict().items() if v is not None})
    if not ok:
        raise HTTPException(status_code=404, detail="Not found or no changes")
    return {"id": zone_id, "message": "Updated"}


@router.delete("/admin/flood-zones/{zone_id}", response_class=ORJSONResponse)
def admin_delete_flood_zone(zone_id: int = Path(...)):
    ok = fzs.delete_zone(zone_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")
    return {"id": zone_id, "message": "Deleted"}


# ============================
# User endpoints
# ============================
@router.get("/user/flood-zones", response_class=ORJSONResponse)
def user_active_flood_zones():
    """Trả về các vùng ngập đang active để FE hiển thị cảnh báo"""
    zones = fzs.get_active_zones()
    return {"count": len(zones), "items": zones}

