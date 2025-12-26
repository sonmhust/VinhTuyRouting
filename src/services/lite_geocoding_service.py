# src/services/lite_geocoding_service.py
"""
LITE Geocoding Service với Linear Interpolation
- Parse địa chỉ: tách số nhà và tên đường
- Linear interpolation cho số nhà không có trong OSM
- Virtual node khi điểm không nằm trên graph
"""
import sqlite3
import math
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from .local_geocoding_service import LocalGeocodingDB
from .graph_builder import GraphNode, GraphEdge, LightGraph, haversine_distance


@dataclass
class InterpolatedPoint:
    """Điểm được nội suy từ số nhà"""
    lat: float
    lon: float
    house_number: int
    street_name: str
    method: str  # "exact", "interpolated", "fallback"


@dataclass
class VirtualNode:
    """Node ảo khi điểm không nằm trên graph"""
    lat: float
    lon: float
    neighbors: List[Tuple[int, float]]  # [(node_id, distance)]
    source: str  # "interpolated", "coordinate"


def parse_address(address: str) -> Tuple[Optional[int], str]:
    """
    Parse địa chỉ thành số nhà và tên đường
    
    Ví dụ:
        "88 Phố Lạc Trung" -> (88, "Phố Lạc Trung")
        "Phố Lạc Trung" -> (None, "Phố Lạc Trung")
        "Ngõ 77 Phố Kim Ngưu" -> (None, "Ngõ 77 Phố Kim Ngưu")
    
    Returns:
        (house_number, street_name)
    """
    # Pattern: số nhà ở đầu, sau đó là tên đường
    # Ví dụ: "88 Phố Lạc Trung", "123 Đường ABC"
    pattern = r'^(\d+)\s+(.+)$'
    match = re.match(pattern, address.strip())
    
    if match:
        house_num = int(match.group(1))
        street = match.group(2).strip()
        return house_num, street
    
    # Không có số nhà, trả về toàn bộ làm tên đường
    return None, address.strip()


def linear_interpolate_house_number(
    geocoding_db: LocalGeocodingDB,
    house_number: int,
    street_name: str
) -> Optional[InterpolatedPoint]:
    """
    Nội suy tuyến tính tọa độ số nhà dựa trên các số nhà có sẵn trên đường
    
    Args:
        geocoding_db: LocalGeocodingDB instance
        house_number: Số nhà cần tìm
        street_name: Tên đường
    
    Returns:
        InterpolatedPoint hoặc None nếu không tìm thấy đường
    """
    if not geocoding_db or not geocoding_db.conn:
        return None
    
    cursor = geocoding_db.conn.cursor()
    
    # Tìm tất cả số nhà trên đường này
    cursor.execute("""
        SELECT house_number, lat, lon, node_id
        FROM addresses
        WHERE street_name = ? AND house_number != '' AND house_number IS NOT NULL
        ORDER BY CAST(house_number AS INTEGER)
    """, (street_name,))
    
    houses = []
    for row in cursor.fetchall():
        try:
            num = int(row['house_number'])
            houses.append((num, row['lat'], row['lon'], row['node_id']))
        except (ValueError, TypeError):
            continue
    
    if not houses:
        return None
    
    # Tìm số nhà chính xác
    for num, lat, lon, node_id in houses:
        if num == house_number:
            return InterpolatedPoint(
                lat=lat,
                lon=lon,
                house_number=house_number,
                street_name=street_name,
                method="exact"
            )
    
    # Tìm 2 số nhà gần nhất để nội suy
    # Tìm số nhà nhỏ hơn gần nhất
    lower = None
    for num, lat, lon, node_id in houses:
        if num < house_number:
            if lower is None or num > lower[0]:
                lower = (num, lat, lon)
    
    # Tìm số nhà lớn hơn gần nhất
    upper = None
    for num, lat, lon, node_id in houses:
        if num > house_number:
            if upper is None or num < upper[0]:
                upper = (num, lat, lon)
    
    # Nội suy tuyến tính
    if lower and upper:
        num1, lat1, lon1 = lower
        num2, lat2, lon2 = upper
        
        # Công thức nội suy
        ratio = (house_number - num1) / (num2 - num1)
        lat = lat1 + (lat2 - lat1) * ratio
        lon = lon1 + (lon2 - lon1) * ratio
        
        return InterpolatedPoint(
            lat=lat,
            lon=lon,
            house_number=house_number,
            street_name=street_name,
            method="interpolated"
        )
    
    # Fallback: dùng số nhà gần nhất
    if lower:
        return InterpolatedPoint(
            lat=lower[1],
            lon=lower[2],
            house_number=house_number,
            street_name=street_name,
            method="fallback_lower"
        )
    
    if upper:
        return InterpolatedPoint(
            lat=upper[1],
            lon=upper[2],
            house_number=house_number,
            street_name=street_name,
            method="fallback_upper"
        )
    
    return None


def find_closest_edge(
    graph: LightGraph,
    lat: float,
    lon: float,
    max_distance: float = 50.0
) -> Optional[Tuple[int, int, float, Tuple[float, float]]]:
    """
    Tìm edge gần nhất với điểm (lat, lon)
    
    Returns:
        (from_node_id, to_node_id, distance, projected_point) hoặc None
        projected_point: (lat, lon) của điểm chiếu vuông góc
    """
    min_dist = float('inf')
    closest_edge = None
    projected = None
    
    for from_node_id, neighbors in graph.adjacency.items():
        from_node = graph.nodes.get(from_node_id)
        if not from_node:
            continue
        
        for to_node_id, edge in neighbors:
            to_node = graph.nodes.get(to_node_id)
            if not to_node:
                continue
            
            # Tính khoảng cách từ điểm đến đoạn thẳng
            dist, proj = point_to_line_segment_distance(
                lat, lon,
                from_node.lat, from_node.lon,
                to_node.lat, to_node.lon
            )
            
            if dist < min_dist and dist <= max_distance:
                min_dist = dist
                closest_edge = (from_node_id, to_node_id, dist)
                projected = proj
    
    if closest_edge:
        return (*closest_edge, projected)
    return None


def point_to_line_segment_distance(
    px: float, py: float,
    x1: float, y1: float,
    x2: float, y2: float
) -> Tuple[float, Tuple[float, float]]:
    """
    Tính khoảng cách từ điểm P đến đoạn thẳng AB và điểm chiếu vuông góc
    
    Returns:
        (distance_in_meters, (projected_lat, projected_lon))
    """
    # Vector AB
    dx = x2 - x1
    dy = y2 - y1
    
    # Vector AP
    apx = px - x1
    apy = py - y1
    
    # Tính t (tham số trên đoạn AB)
    dot = apx * dx + apy * dy
    len_sq = dx * dx + dy * dy
    
    if len_sq == 0:
        # A và B trùng nhau
        dist = haversine_distance(px, py, x1, y1)
        return dist, (x1, y1)
    
    t = max(0, min(1, dot / len_sq))
    
    # Điểm chiếu vuông góc
    proj_lat = x1 + t * dx
    proj_lon = y1 + t * dy
    
    # Khoảng cách
    dist = haversine_distance(px, py, proj_lat, proj_lon)
    
    return dist, (proj_lat, proj_lon)


def create_virtual_node(
    graph: LightGraph,
    lat: float,
    lon: float,
    max_distance: float = 50.0
) -> Optional[VirtualNode]:
    """
    Tạo virtual node từ điểm (lat, lon) bằng cách chiếu xuống edge gần nhất
    
    Returns:
        VirtualNode hoặc None nếu không tìm thấy edge gần
    """
    edge_info = find_closest_edge(graph, lat, lon, max_distance)
    if not edge_info:
        return None
    
    from_node_id, to_node_id, dist, (proj_lat, proj_lon) = edge_info
    
    # Tạo neighbors: kết nối với 2 node của edge
    neighbors = []
    
    from_node = graph.nodes.get(from_node_id)
    to_node = graph.nodes.get(to_node_id)
    
    if from_node:
        dist_to_from = haversine_distance(proj_lat, proj_lon, from_node.lat, from_node.lon)
        neighbors.append((from_node_id, dist_to_from))
    
    if to_node:
        dist_to_to = haversine_distance(proj_lat, proj_lon, to_node.lat, to_node.lon)
        neighbors.append((to_node_id, dist_to_to))
    
    return VirtualNode(
        lat=proj_lat,
        lon=proj_lon,
        neighbors=neighbors,
        source="interpolated" if dist > 0 else "coordinate"
    )


def search_with_interpolation(
    geocoding_db: LocalGeocodingDB,
    graph: LightGraph,
    query: str,
    limit: int = 5
) -> List[Dict]:
    """
    Tìm kiếm địa chỉ với hỗ trợ linear interpolation
    
    Args:
        geocoding_db: LocalGeocodingDB instance
        graph: LightGraph instance
        query: Địa chỉ cần tìm (ví dụ: "88 Phố Lạc Trung")
        limit: Số kết quả tối đa
    
    Returns:
        List[Dict] với keys: node_id, lat, lon, address, score, address_type, 
        interpolation_method, virtual_node
    """
    # Parse địa chỉ
    house_number, street_name = parse_address(query)
    
    results = []
    
    # Nếu có số nhà, thử interpolation
    if house_number is not None and street_name:
        interpolated = linear_interpolate_house_number(
            geocoding_db, house_number, street_name
        )
        
        if interpolated:
            # Tạo virtual node
            virtual = create_virtual_node(graph, interpolated.lat, interpolated.lon)
            
            if virtual:
                # Tạo kết quả với virtual node
                # Sử dụng node_id của neighbor đầu tiên làm node_id chính
                main_node_id = virtual.neighbors[0][0] if virtual.neighbors else None
                
                results.append({
                    "node_id": main_node_id,
                    "lat": virtual.lat,
                    "lon": virtual.lon,
                    "address": f"{house_number} {street_name}",
                    "score": 100.0,
                    "address_type": "house",
                    "interpolation_method": interpolated.method,
                    "virtual_node": virtual,
                    "original_query": query
                })
    
    # Tìm kiếm thông thường (FTS5)
    fts_results = geocoding_db.search(query, limit)
    for r in fts_results:
        # Tránh duplicate
        if not any(res.get("node_id") == r.node_id for res in results):
            results.append({
                "node_id": r.node_id,
                "lat": r.lat,
                "lon": r.lon,
                "address": r.address,
                "score": r.score,
                "address_type": r.address_type,
                "interpolation_method": None,
                "virtual_node": None,
                "original_query": query
            })
    
    # Sắp xếp theo score
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    return results[:limit]

