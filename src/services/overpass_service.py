# src/services/overpass_service.py
"""
Service để lấy dữ liệu bản đồ từ Overpass API
Trả về dữ liệu JSON gồm nodes và ways
"""
import requests
import json
import hashlib
import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict

# Cache directory
CACHE_DIR = Path(__file__).parent / "cache" / "overpass"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Overpass API endpoints (fallback list)
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]


@dataclass
class OSMNode:
    """Node trong OSM với id, lat, lon"""
    id: int
    lat: float
    lon: float
    tags: dict = field(default_factory=dict)


@dataclass
class OSMWay:
    """Way trong OSM với id, danh sách node IDs, và tags"""
    id: int
    nodes: list  # List of node IDs
    tags: dict = field(default_factory=dict)


@dataclass
class OSMData:
    """Container cho dữ liệu OSM đã parse"""
    nodes: dict  # {node_id: OSMNode}
    ways: list   # List of OSMWay
    
    def to_dict(self) -> dict:
        """Chuyển sang dict để serialize JSON"""
        return {
            "nodes": {
                str(nid): {"id": n.id, "lat": n.lat, "lon": n.lon, "tags": n.tags}
                for nid, n in self.nodes.items()
            },
            "ways": [
                {"id": w.id, "nodes": w.nodes, "tags": w.tags}
                for w in self.ways
            ]
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "OSMData":
        """Khôi phục từ dict"""
        nodes = {
            int(nid): OSMNode(
                id=n["id"],
                lat=n["lat"],
                lon=n["lon"],
                tags=n.get("tags", {})
            )
            for nid, n in data["nodes"].items()
        }
        ways = [
            OSMWay(
                id=w["id"],
                nodes=w["nodes"],
                tags=w.get("tags", {})
            )
            for w in data["ways"]
        ]
        return cls(nodes=nodes, ways=ways)


def _get_cache_key(bbox: tuple) -> str:
    """Tạo cache key từ bounding box"""
    bbox_str = f"{bbox[0]:.6f},{bbox[1]:.6f},{bbox[2]:.6f},{bbox[3]:.6f}"
    return hashlib.sha1(bbox_str.encode()).hexdigest()


def _load_from_cache(cache_key: str) -> Optional[OSMData]:
    """Load dữ liệu từ cache nếu có"""
    cache_file = CACHE_DIR / f"{cache_key}.json"
    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return OSMData.from_dict(data)
        except Exception as e:
            print(f"Lỗi đọc cache: {e}")
    return None


def _save_to_cache(cache_key: str, osm_data: OSMData):
    """Lưu dữ liệu vào cache"""
    cache_file = CACHE_DIR / f"{cache_key}.json"
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(osm_data.to_dict(), f, ensure_ascii=False)
    except Exception as e:
        print(f"Lỗi ghi cache: {e}")


def build_overpass_query(bbox: tuple, highway_types: list = None, include_addresses: bool = True) -> str:
    """
    Xây dựng Overpass QL query để lấy dữ liệu đường VÀ địa chỉ
    
    Args:
        bbox: (min_lat, min_lon, max_lat, max_lon)
        highway_types: Danh sách loại đường cần lấy
        include_addresses: Có lấy dữ liệu địa chỉ (addr:*, name) không
    
    Returns:
        Overpass QL query string
    """
    if highway_types is None:
        # Các loại đường phổ biến cho routing
        highway_types = [
            "motorway", "motorway_link",
            "trunk", "trunk_link", 
            "primary", "primary_link",
            "secondary", "secondary_link",
            "tertiary", "tertiary_link",
            "residential", "living_street",
            "unclassified", "service"
        ]
    
    min_lat, min_lon, max_lat, max_lon = bbox
    bbox_str = f"{min_lat},{min_lon},{max_lat},{max_lon}"
    
    # Xây dựng query lấy ways có highway tag và các nodes liên quan
    highway_filter = "|".join(highway_types)
    
    if include_addresses:
        # Query mở rộng: lấy cả địa chỉ (nodes có addr:housenumber, POIs có name)
        query = f"""
[out:json][timeout:90];
(
  // Roads
  way["highway"~"^({highway_filter})$"]({bbox_str});
  // Addresses - nodes có số nhà
  node["addr:housenumber"]({bbox_str});
  // POIs - các địa điểm có tên
  node["name"]["amenity"]({bbox_str});
  node["name"]["shop"]({bbox_str});
  node["name"]["tourism"]({bbox_str});
  node["name"]["building"]({bbox_str});
);
out body;
>;
out skel qt;
"""
    else:
        query = f"""
[out:json][timeout:60];
(
  way["highway"~"^({highway_filter})$"]({bbox_str});
);
out body;
>;
out skel qt;
"""
    return query


def fetch_from_overpass(bbox: tuple, use_cache: bool = True) -> Optional[OSMData]:
    """
    Lấy dữ liệu từ Overpass API
    
    Args:
        bbox: (min_lat, min_lon, max_lat, max_lon)
        use_cache: Có sử dụng cache không
    
    Returns:
        OSMData object hoặc None nếu lỗi
    """
    cache_key = _get_cache_key(bbox)
    
    # Kiểm tra cache
    if use_cache:
        cached_data = _load_from_cache(cache_key)
        if cached_data:
            print(f"Đã load từ cache: {len(cached_data.nodes)} nodes, {len(cached_data.ways)} ways")
            return cached_data
    
    # Xây dựng query
    query = build_overpass_query(bbox)
    
    # Thử các endpoint
    response = None
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            print(f"Đang thử endpoint: {endpoint}")
            response = requests.post(
                endpoint,
                data={"data": query},
                timeout=120,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            if response.status_code == 200:
                break
        except requests.exceptions.RequestException as e:
            print(f"Lỗi với {endpoint}: {e}")
            continue
    
    if response is None or response.status_code != 200:
        print("Không thể kết nối Overpass API")
        return None
    
    # Parse response
    try:
        raw_data = response.json()
    except json.JSONDecodeError as e:
        print(f"Lỗi parse JSON: {e}")
        return None
    
    osm_data = parse_overpass_response(raw_data)
    
    # Lưu cache
    if use_cache and osm_data:
        _save_to_cache(cache_key, osm_data)
    
    return osm_data


def parse_overpass_response(raw_data: dict) -> OSMData:
    """
    Parse response từ Overpass API thành OSMData
    
    Args:
        raw_data: JSON response từ Overpass
    
    Returns:
        OSMData object
    """
    nodes = {}
    ways = []
    
    elements = raw_data.get("elements", [])
    
    # Đầu tiên, parse tất cả nodes
    for element in elements:
        if element.get("type") == "node":
            node_id = element["id"]
            nodes[node_id] = OSMNode(
                id=node_id,
                lat=element["lat"],
                lon=element["lon"],
                tags=element.get("tags", {})
            )
    
    # Sau đó, parse tất cả ways
    for element in elements:
        if element.get("type") == "way":
            way = OSMWay(
                id=element["id"],
                nodes=element.get("nodes", []),
                tags=element.get("tags", {})
            )
            ways.append(way)
    
    print(f"Đã parse: {len(nodes)} nodes, {len(ways)} ways")
    return OSMData(nodes=nodes, ways=ways)


def fetch_area_by_name(area_name: str, use_cache: bool = True) -> Optional[OSMData]:
    """
    Lấy dữ liệu theo tên khu vực (ví dụ: "Hoàng Mai, Hà Nội")
    
    Args:
        area_name: Tên khu vực
        use_cache: Có sử dụng cache không
    
    Returns:
        OSMData object hoặc None nếu lỗi
    """
    cache_key = hashlib.sha1(area_name.encode()).hexdigest()
    
    # Kiểm tra cache
    if use_cache:
        cached_data = _load_from_cache(cache_key)
        if cached_data:
            print(f"Đã load từ cache: {len(cached_data.nodes)} nodes, {len(cached_data.ways)} ways")
            return cached_data
    
    # Xây dựng query sử dụng area search
    query = f"""
[out:json][timeout:120];
area["name"="{area_name}"]->.searchArea;
(
  way["highway"~"^(motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|secondary_link|tertiary|tertiary_link|residential|living_street|unclassified|service)$"](area.searchArea);
);
out body;
>;
out skel qt;
"""
    
    # Thử các endpoint
    response = None
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            print(f"Đang thử endpoint: {endpoint}")
            response = requests.post(
                endpoint,
                data={"data": query},
                timeout=180,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            if response.status_code == 200:
                break
        except requests.exceptions.RequestException as e:
            print(f"Lỗi với {endpoint}: {e}")
            continue
    
    if response is None or response.status_code != 200:
        print("Không thể kết nối Overpass API")
        return None
    
    try:
        raw_data = response.json()
    except json.JSONDecodeError as e:
        print(f"Lỗi parse JSON: {e}")
        return None
    
    osm_data = parse_overpass_response(raw_data)
    
    if use_cache and osm_data:
        _save_to_cache(cache_key, osm_data)
    
    return osm_data


# ======================================================================
# Các hàm tiện ích
# ======================================================================

def get_highway_speed(highway_type: str) -> float:
    """
    Trả về tốc độ trung bình (km/h) theo loại đường
    """
    speed_map = {
        "motorway": 100,
        "motorway_link": 60,
        "trunk": 80,
        "trunk_link": 50,
        "primary": 60,
        "primary_link": 40,
        "secondary": 50,
        "secondary_link": 35,
        "tertiary": 40,
        "tertiary_link": 30,
        "residential": 30,
        "living_street": 20,
        "unclassified": 30,
        "service": 20,
    }
    return speed_map.get(highway_type, 30)


def is_oneway(tags: dict) -> bool:
    """Kiểm tra way có phải một chiều không"""
    oneway = tags.get("oneway", "no")
    return oneway in ("yes", "1", "true", "-1")


def is_reverse_oneway(tags: dict) -> bool:
    """Kiểm tra way có phải một chiều ngược không (oneway=-1)"""
    return tags.get("oneway") == "-1"

