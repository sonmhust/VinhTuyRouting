# src/services/flood_zone_service.py
"""
SQLite store cho flood zones (admin quản lý, user sử dụng)
Schema:
  id INTEGER PRIMARY KEY AUTOINCREMENT
  name TEXT
  type TEXT ('polygon' | 'circle' | 'multipolygon')
  geometry TEXT (GeoJSON string)
  severity REAL (penalty multiplier, ví dụ 5.0)
  is_active INTEGER (0/1)
  updated_at TEXT (ISO timestamp)
"""
import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


DEFAULT_DB_PATH = Path(__file__).parent / "cache" / "flood_zones.db"
DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _get_conn(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path = DEFAULT_DB_PATH):
    """Tạo bảng nếu chưa có"""
    with _get_conn(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS flood_zones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                geometry TEXT NOT NULL,
                severity REAL DEFAULT 5.0,
                is_active INTEGER DEFAULT 1,
                updated_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.commit()


def list_zones(include_inactive: bool = True, db_path: Path = DEFAULT_DB_PATH) -> List[Dict]:
    init_db(db_path)
    query = "SELECT * FROM flood_zones"
    params = ()
    if not include_inactive:
        query += " WHERE is_active = 1"
    with _get_conn(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def create_zone(data: Dict, db_path: Path = DEFAULT_DB_PATH) -> int:
    init_db(db_path)
    with _get_conn(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO flood_zones (name, type, geometry, severity, is_active, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                data["name"],
                data.get("type", "polygon"),
                json.dumps(data["geometry"]),
                float(data.get("severity", 5.0)),
                1 if data.get("is_active", True) else 0,
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
        return cur.lastrowid


def update_zone(zone_id: int, data: Dict, db_path: Path = DEFAULT_DB_PATH) -> bool:
    init_db(db_path)
    fields = []
    values = []
    for key in ("name", "type", "geometry", "severity", "is_active"):
        if key in data:
            fields.append(f"{key} = ?")
            if key == "geometry":
                values.append(json.dumps(data[key]))
            elif key == "is_active":
                values.append(1 if data[key] else 0)
            else:
                values.append(data[key])
    if not fields:
        return False
    values.append(datetime.utcnow().isoformat())
    values.append(zone_id)
    set_clause = ", ".join(fields + ["updated_at = ?"])
    with _get_conn(db_path) as conn:
        cur = conn.execute(
            f"UPDATE flood_zones SET {set_clause} WHERE id = ?",
            tuple(values),
        )
        conn.commit()
        return cur.rowcount > 0


def delete_zone(zone_id: int, db_path: Path = DEFAULT_DB_PATH) -> bool:
    init_db(db_path)
    with _get_conn(db_path) as conn:
        cur = conn.execute("DELETE FROM flood_zones WHERE id = ?", (zone_id,))
        conn.commit()
        return cur.rowcount > 0


def get_active_zones(db_path: Path = DEFAULT_DB_PATH) -> List[Dict]:
    return list_zones(include_inactive=False, db_path=db_path)


def to_geojson_features(rows: List[Dict]) -> List[Dict]:
    """Convert rows to GeoJSON features with blockType=flood and penalty=severity"""
    features = []
    for row in rows:
        geom = row.get("geometry")
        try:
            geom_obj = json.loads(geom) if isinstance(geom, str) else geom
        except Exception:
            continue
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "blockType": "flood",
                    "penalty": float(row.get("severity", 5.0)),
                    "id": row.get("id"),
                    "name": row.get("name"),
                    "is_active": bool(row.get("is_active")),
                },
                "geometry": geom_obj,
            }
        )
    return features

