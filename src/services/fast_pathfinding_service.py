# src/services/fast_pathfinding_service.py
"""
Service pathfinding tối ưu
- A* với heapq
- itertools.chain cho geometry reconstruction
- KD-Tree nearest node
- Local geocoding với SQLite FTS5
"""
import heapq
import time
from itertools import chain
from typing import List, Dict, Tuple, Optional, Set, Any
from dataclasses import dataclass
from shapely.geometry import LineString, shape

from .graph_builder import (
    LightGraph, GraphNode, GraphEdge,
    haversine_distance, build_graph_from_osm, C_CONTEXT
)
from shapely.geometry import shape
from .overpass_service import fetch_from_overpass, OSMData
from .local_geocoding_service import (
    init_local_geocoding, get_geocoding_db,
    LocalGeocodingDB, SearchResult
)


@dataclass(slots=True)
class PathResult:
    """Kết quả tìm đường - dùng slots để tối ưu memory"""
    success: bool
    path: List[int] = None
    distance: float = 0.0
    duration: float = 0.0
    geometry: List[Tuple[float, float]] = None  # Raw coords, không wrap dict
    error: str = None
    stats: dict = None


def heuristic(node1: GraphNode, node2: GraphNode) -> float:
    """Heuristic admissible: khoảng cách × hệ số min"""
    return haversine_distance(node1.lat, node1.lon, node2.lat, node2.lon) * 0.7


def _merge_geometries(edges: List[GraphEdge], graph: LightGraph = None, path_nodes: List[int] = None) -> List[Tuple[float, float]]:
    """
    Merge geometry từ nhiều edges sử dụng REAL geometry từ edges
    Logic chuẩn xác: Theo dõi current_node để xác định chiều đúng của mỗi edge
    
    Args:
        edges: Danh sách các edges trong path
        graph: Graph để lấy node coordinates (fallback)
        path_nodes: Danh sách node IDs trong path (từ start đến end)
    
    Returns:
        List các tọa độ (lon, lat) đã được merge đúng chiều
    """
    if not edges:
        return []
    
    def calc_dist(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        """Tính khoảng cách giữa 2 điểm (lon, lat) - dùng Euclidean đơn giản cho so sánh"""
        return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5
    
    result = []
    
    # Xác định start_node từ path_nodes hoặc edge đầu tiên
    if path_nodes and len(path_nodes) > 0:
        current_node = path_nodes[0]
    elif edges:
        # Nếu không có path_nodes, giả định edge đầu tiên đi từ from_node
        current_node = edges[0].from_node
    else:
        return []
    
    for i, edge in enumerate(edges):
        if edge.geometry and len(edge.geometry) >= 2:
            # Edge có real geometry
            segment = list(edge.geometry)
            
            # KIỂM TRA HƯỚNG: Đây là chỗ quan trọng nhất
            if edge.from_node == current_node:
                # Cạnh thuận chiều: [from_node -> to_node]
                # Không cần reverse, điểm tiếp theo sẽ là to_node
                current_node = edge.to_node
            elif edge.to_node == current_node:
                # Cạnh ngược chiều: [to_node -> from_node]
                # PHẢI REVERSE để có thứ tự điểm từ current_node đi ra
                segment.reverse()
                current_node = edge.from_node
            else:
                # Edge không nối với current_node - có thể do lỗi path
                # Fallback: dùng khoảng cách để xác định chiều
                if graph:
                    current_node_obj = graph.get_node(current_node)
                    from_node_obj = graph.get_node(edge.from_node)
                    to_node_obj = graph.get_node(edge.to_node)
                    
                    if current_node_obj and from_node_obj and to_node_obj:
                        dist_to_from = calc_dist(
                            (current_node_obj.lon, current_node_obj.lat),
                            (from_node_obj.lon, from_node_obj.lat)
                        )
                        dist_to_to = calc_dist(
                            (current_node_obj.lon, current_node_obj.lat),
                            (to_node_obj.lon, to_node_obj.lat)
                        )
                        
                        if dist_to_to < dist_to_from:
                            # to_node gần hơn: edge đi từ from_node -> to_node, cần reverse
                            segment.reverse()
                            current_node = edge.from_node
                        else:
                            # from_node gần hơn: edge đi từ from_node -> to_node, đúng chiều
                            current_node = edge.to_node
            
            # Nối vào đường tổng, bỏ điểm đầu để tránh duplicate với điểm cuối đoạn trước
            if not result:
                # Edge đầu tiên: thêm toàn bộ
                result.extend(segment)
            else:
                # Các edge sau: skip điểm đầu nếu trùng với điểm cuối của result
                last_p = result[-1]
                if calc_dist(last_p, segment[0]) < 1e-6:  # Trùng điểm (tolerance nhỏ)
                    result.extend(segment[1:])
                else:
                    result.extend(segment)
        else:
            # Edge không có geometry: tạo từ nodes (fallback)
            if graph:
                from_node = graph.get_node(edge.from_node)
                to_node = graph.get_node(edge.to_node)
                if from_node and to_node:
                    from_coord = (from_node.lon, from_node.lat)
                    to_coord = (to_node.lon, to_node.lat)
                    
                    # Kiểm tra hướng
                    if edge.from_node == current_node:
                        # Thuận chiều: from_node -> to_node
                        segment_coords = [from_coord, to_coord]
                        current_node = edge.to_node
                    elif edge.to_node == current_node:
                        # Ngược chiều: to_node -> from_node, cần reverse
                        segment_coords = [to_coord, from_coord]
                        current_node = edge.from_node
                    else:
                        # Fallback: dùng khoảng cách
                        current_node_obj = graph.get_node(current_node)
                        if current_node_obj:
                            dist_to_from = calc_dist(
                                (current_node_obj.lon, current_node_obj.lat),
                                from_coord
                            )
                            dist_to_to = calc_dist(
                                (current_node_obj.lon, current_node_obj.lat),
                                to_coord
                            )
                            
                            if dist_to_to < dist_to_from:
                                segment_coords = [to_coord, from_coord]
                                current_node = edge.from_node
                            else:
                                segment_coords = [from_coord, to_coord]
                                current_node = edge.to_node
                        else:
                            segment_coords = [from_coord, to_coord]
                            current_node = edge.to_node
                    
                    # Nối vào result
                    if not result:
                        result.extend(segment_coords)
                    else:
                        last_p = result[-1]
                        if calc_dist(last_p, segment_coords[0]) < 1e-6:
                            result.extend(segment_coords[1:])
                        else:
                            result.extend(segment_coords)
    
    return result


def _reconstruct_path_with_geometry(
    came_from: Dict[int, int],
    came_from_edge: Dict[int, GraphEdge],
    end_id: int,
    graph: LightGraph
) -> Tuple[List[int], List[Tuple[float, float]], float, float]:
    """
    Reconstruct path và xây dựng geometry trực tiếp - không merge
    Đảm bảo path liên tục, không có gap
    
    Returns:
        (path, geometry, distance, duration)
    """
    # Reconstruct path từ end về start
    path = []
    current = end_id
    while current is not None:
        path.append(current)
        current = came_from.get(current)
    
    path.reverse()  # Từ start đến end
    
    # Xây dựng geometry trực tiếp từ path
    geometry = []
    total_dist = 0.0
    total_dur = 0.0
    
    if len(path) < 2:
        return path, geometry, total_dist, total_dur
    
    # Duyệt từng cặp node liên tiếp trong path
    for i in range(len(path) - 1):
        from_node_id = path[i]
        to_node_id = path[i + 1]
        
        # Lấy edge từ came_from_edge
        edge = came_from_edge.get(to_node_id)
        
        if not edge:
            # Edge không tồn tại - path không liên tục (lỗi)
            # Fallback: tạo geometry từ 2 nodes
            from_node = graph.get_node(from_node_id)
            to_node = graph.get_node(to_node_id)
            if from_node and to_node:
                if not geometry:
                    geometry.append((from_node.lon, from_node.lat))
                geometry.append((to_node.lon, to_node.lat))
            continue
        
        # Validate: edge phải nối đúng from_node và to_node
        if edge.from_node != from_node_id and edge.to_node != from_node_id:
            # Edge không khớp với path - có thể do lỗi
            # Fallback: tạo geometry từ nodes
            from_node = graph.get_node(from_node_id)
            to_node = graph.get_node(to_node_id)
            if from_node and to_node:
                if not geometry:
                    geometry.append((from_node.lon, from_node.lat))
                geometry.append((to_node.lon, to_node.lat))
            continue
        
        # Xác định hướng edge
        if edge.from_node == from_node_id:
            # Edge đi từ from_node -> to_node (thuận chiều)
            if edge.geometry and len(edge.geometry) >= 2:
                # Sử dụng real geometry
                segment = edge.geometry
            else:
                # Fallback: tạo từ nodes
                from_node = graph.get_node(from_node_id)
                to_node = graph.get_node(to_node_id)
                if from_node and to_node:
                    segment = [(from_node.lon, from_node.lat), (to_node.lon, to_node.lat)]
                else:
                    continue
        else:
            # Edge đi từ to_node -> from_node (ngược chiều), cần reverse
            if edge.geometry and len(edge.geometry) >= 2:
                # Reverse geometry
                segment = list(reversed(edge.geometry))
            else:
                # Fallback: tạo từ nodes (đã reverse)
                from_node = graph.get_node(from_node_id)
                to_node = graph.get_node(to_node_id)
                if from_node and to_node:
                    segment = [(from_node.lon, from_node.lat), (to_node.lon, to_node.lat)]
                else:
                    continue
        
        # Nối segment vào geometry (skip điểm đầu nếu trùng)
        if not geometry:
            geometry.extend(segment)
        else:
            # Kiểm tra điểm cuối của geometry và điểm đầu của segment
            last_p = geometry[-1]
            first_p = segment[0]
            # Tolerance: 1e-6 độ (khoảng 0.1m)
            if abs(last_p[0] - first_p[0]) < 1e-6 and abs(last_p[1] - first_p[1]) < 1e-6:
                geometry.extend(segment[1:])
            else:
                geometry.extend(segment)
        
        total_dist += edge.length
        total_dur += edge.travel_time
    
    return path, geometry, total_dist, total_dur


def _collect_edges_and_stats(
    came_from: Dict[int, int],
    came_from_edge: Dict[int, GraphEdge],
    end_id: int
) -> Tuple[List[int], List[GraphEdge], float, float]:
    """
    Thu thập path, edges, distance, duration trong một lần duyệt
    (Legacy function - giữ lại để tương thích)
    """
    path = [end_id]
    edges = []
    total_dist = 0.0
    total_dur = 0.0
    
    current = end_id
    while current in came_from:
        edge = came_from_edge[current]
        edges.append(edge)
        total_dist += edge.length
        total_dur += edge.travel_time
        current = came_from[current]
        path.append(current)
    
    path.reverse()
    edges.reverse()
    return path, edges, total_dist, total_dur


def astar_search(
    graph: LightGraph,
    start_id: int,
    end_id: int,
    weather: str = "normal",
    penalty_map: Dict[Tuple[int, int], float] = None,
    blocked_edges: Set[Tuple[int, int]] = None
) -> PathResult:
    """
    One-directional A* search - tối ưu, xây dựng geometry trực tiếp, không merge
    
    Args:
        graph: LightGraph
        start_id, end_id: Node IDs
        weather: Điều kiện thời tiết
        penalty_map: Dict[(from, to)] -> multiplier cho flood areas
        blocked_edges: Set[(from, to)] - edges bị chặn hoàn toàn
    
    Performance:
        - Không copy graph
        - Penalty lookup: O(1)
        - Blocked check: O(1)
        - Geometry được xây dựng trực tiếp trong reconstruct, không merge
    """
    start_time = time.perf_counter()
    
    if not graph.has_node(start_id) or not graph.has_node(end_id):
        return PathResult(success=False, error="Start hoặc end node không tồn tại")
    
    start_node = graph.get_node(start_id)
    end_node = graph.get_node(end_id)
    
    # Default empty collections
    if penalty_map is None:
        penalty_map = {}
    if blocked_edges is None:
        blocked_edges = set()
    
    # Priority queue: (f_score, counter, node_id)
    counter = 0
    open_set = [(0.0, counter, start_id)]
    
    came_from: Dict[int, int] = {}
    came_from_edge: Dict[int, GraphEdge] = {}
    g_score: Dict[int, float] = {start_id: 0.0}
    
    open_set_hash: Set[int] = {start_id}
    closed_set: Set[int] = set()
    nodes_visited = 0
    
    while open_set:
        _, _, current = heapq.heappop(open_set)
        
        if current in closed_set:
            continue
        
        open_set_hash.discard(current)
        nodes_visited += 1
        
        if current == end_id:
            elapsed = time.perf_counter() - start_time
            # Reconstruct path và geometry trực tiếp - không merge
            path, geometry, dist, dur = _reconstruct_path_with_geometry(
                came_from, came_from_edge, end_id, graph
            )
            
            return PathResult(
                success=True,
                path=path,
                distance=dist,
                duration=dur,
                geometry=geometry,
                stats={
                    "nodes_visited": nodes_visited,
                    "search_time_ms": elapsed * 1000,
                    "path_length": len(path),
                    "algorithm": "astar_optimized",
                    "weather": weather
                }
            )
        
        closed_set.add(current)
        current_g = g_score[current]
        
        for neighbor_id, edge in graph.get_neighbors(current):
            if neighbor_id in closed_set:
                continue
            
            edge_key = (current, neighbor_id)
            
            # O(1) check blocked
            if edge_key in blocked_edges:
                continue
            
            # Base weight
            weight = edge.get_weight(weather)
            
            # O(1) penalty lookup
            if edge_key in penalty_map:
                weight *= penalty_map[edge_key]
            
            tentative_g = current_g + weight
            
            if neighbor_id not in g_score or tentative_g < g_score[neighbor_id]:
                came_from[neighbor_id] = current
                came_from_edge[neighbor_id] = edge
                g_score[neighbor_id] = tentative_g
                
                neighbor_node = graph.get_node(neighbor_id)
                f = tentative_g + heuristic(neighbor_node, end_node)
                
                if neighbor_id not in open_set_hash:
                    counter += 1
                    heapq.heappush(open_set, (f, counter, neighbor_id))
                    open_set_hash.add(neighbor_id)
    
    elapsed = time.perf_counter() - start_time
    return PathResult(
        success=False,
        error="Không tìm thấy đường đi",
        stats={"nodes_visited": nodes_visited, "search_time_ms": elapsed * 1000}
    )


def bidirectional_astar(
    graph: LightGraph,
    start_id: int,
    end_id: int,
    weather: str = "normal",
    penalty_map: Dict[Tuple[int, int], float] = None,
    blocked_edges: Set[Tuple[int, int]] = None
) -> PathResult:
    """
    [DEPRECATED] Bidirectional A* - Đã thay thế bằng astar_search
    
    Hàm này có vấn đề khi merge geometries từ 2 hướng, có thể gây "đường chéo".
    Sử dụng astar_search thay thế - one-directional A* với geometry được xây dựng trực tiếp.
    
    Args:
        graph: LightGraph (immutable - không modify)
        start_id, end_id: Node IDs
        weather: Điều kiện thời tiết
        penalty_map: Dict[(from, to)] -> multiplier cho flood areas (O(1) lookup)
        blocked_edges: Set[(from, to)] - edges bị chặn hoàn toàn
    
    Performance:
        - Không copy graph
        - Penalty lookup: O(1) với hash map
        - Blocked check: O(1) với set
    
    Note: Hàm này redirect về astar_search để tương thích ngược
    """
    # Redirect to optimized one-directional A*
    return astar_search(graph, start_id, end_id, weather, penalty_map, blocked_edges)


# ======================================================================
# FastRoutingService
# ======================================================================

class FastRoutingService:
    """Service routing tối ưu với KD-Tree, flexible weighting và local geocoding"""
    
    __slots__ = ['graph', 'osm_data', 'geocoding_db']
    
    def __init__(self, graph: LightGraph = None):
        self.graph = graph
        self.osm_data: Optional[OSMData] = None
        self.geocoding_db: Optional[LocalGeocodingDB] = None
    
    def load_from_bbox(self, bbox: Tuple[float, float, float, float], use_cache: bool = True) -> bool:
        """Load graph từ BBOX và khởi tạo local geocoding"""
        osm_data = fetch_from_overpass(bbox, use_cache)
        if osm_data:
            self.osm_data = osm_data
            self.graph = build_graph_from_osm(osm_data)
            
            # Khởi tạo local geocoding với OSM data
            if self.graph:
                graph_node_ids = set(self.graph.nodes.keys())
                self.geocoding_db = init_local_geocoding(osm_data, graph_node_ids)
            
            return True
        return False
    
    def search_address(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Tìm kiếm địa chỉ (autocomplete)
        
        Returns:
            List[Dict] với keys: node_id, lat, lon, address, score, address_type
        """
        if not self.geocoding_db:
            return []
        
        results = self.geocoding_db.search(query, limit)
        return [
            {
                "node_id": r.node_id,
                "lat": r.lat,
                "lon": r.lon,
                "address": r.address,
                "score": r.score,
                "address_type": r.address_type
            }
            for r in results
        ]
    
    def get_geocoding_stats(self) -> Dict:
        """Thống kê local geocoding DB"""
        if not self.geocoding_db:
            return {"status": "not_initialized"}
        return self.geocoding_db.get_stats()
    
    def find_nearest_node(self, lat: float, lon: float) -> Optional[int]:
        return self.graph.find_nearest_node(lat, lon) if self.graph else None
    
    def find_route(
        self,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
        weather_condition: str = "normal",
        blocked_edges: Set[Tuple[int, int]] = None,
        weight_multipliers: Dict[Tuple[int, int], float] = None
    ) -> dict:
        """Tìm đường từ tọa độ - cần KD-Tree snap"""
        if not self.graph:
            return {"error": "Graph chưa được load"}
        
        if weather_condition not in C_CONTEXT:
            weather_condition = "normal"
        
        start_id = self.find_nearest_node(start_lat, start_lon)
        end_id = self.find_nearest_node(end_lat, end_lon)
        
        if start_id is None:
            return {"error": "Không tìm thấy node gần điểm bắt đầu"}
        if end_id is None:
            return {"error": "Không tìm thấy node gần điểm kết thúc"}
        if start_id == end_id:
            return {"error": "Hai điểm quá gần nhau"}
        
        return self._execute_routing(start_id, end_id, weather_condition, blocked_edges, weight_multipliers)
    
    def find_route_by_node_ids(
        self,
        start_node_id: int,
        end_node_id: int,
        weather_condition: str = "normal",
        blocked_edges: Set[Tuple[int, int]] = None,
        weight_multipliers: Dict[Tuple[int, int], float] = None
    ) -> dict:
        """
        Tìm đường trực tiếp từ node_id - NHANH NHẤT
        Skip hoàn toàn KD-Tree snap vì node_id đã biết chính xác
        """
        if not self.graph:
            return {"error": "Graph chưa được load"}
        
        if weather_condition not in C_CONTEXT:
            weather_condition = "normal"
        
        if not self.graph.has_node(start_node_id):
            return {"error": f"Start node {start_node_id} không tồn tại trong graph"}
        if not self.graph.has_node(end_node_id):
            return {"error": f"End node {end_node_id} không tồn tại trong graph"}
        if start_node_id == end_node_id:
            return {"error": "Start và end node trùng nhau"}
        
        return self._execute_routing(start_node_id, end_node_id, weather_condition, blocked_edges, weight_multipliers)
    
    def _execute_routing(
        self,
        start_id: int,
        end_id: int,
        weather_condition: str,
        blocked_edges: Set[Tuple[int, int]] = None,
        penalty_map: Dict[Tuple[int, int], float] = None
    ) -> dict:
        """
        Core routing logic với Weight Overlay
        
        KHÔNG copy graph - truyền penalty_map trực tiếp vào A*
        """
        result = astar_search(
            self.graph, 
            start_id, 
            end_id, 
            weather_condition,
            penalty_map=penalty_map,
            blocked_edges=blocked_edges
        )
        
        if not result.success:
            return {"error": result.error, "stats": result.stats}
        
        # Return dict structure tối ưu cho ORJSON
        return {
            "distance": result.distance,
            "duration": result.duration / 60,
            "route": {
                "type": "Feature",
                "properties": {"weather": weather_condition},
                "geometry": {
                    "type": "LineString",
                    "coordinates": result.geometry
                }
            },
            "path": result.path,
            "stats": result.stats
        }
    
    def find_affected_edges_fast(
        self,
        geometries: List[Dict[str, Any]]
    ) -> Tuple[Set[Tuple[int, int]], Dict[Tuple[int, int], float]]:
        """
        Tìm edges bị ảnh hưởng bởi flood/block geometries - SỬ DỤNG STRtree
        
        Performance: O(log N) per geometry thay vì O(N)
        
        Args:
            geometries: List GeoJSON features với properties.blockType
        
        Returns:
            (blocked_edges, penalty_map)
            - blocked_edges: Set[(from, to)] - edges bị chặn hoàn toàn
            - penalty_map: Dict[(from, to)] -> multiplier (flood areas)
        """
        blocked: Set[Tuple[int, int]] = set()
        penalty_map: Dict[Tuple[int, int], float] = {}
        
        if not geometries or not self.graph:
            return blocked, penalty_map
        
        # Ensure STRtree is built
        if self.graph._strtree is None:
            self.graph.build_strtree()
        
        for geom_dict in geometries:
            try:
                geom_data = geom_dict.get("geometry", geom_dict)
                props = geom_dict.get("properties", {})
                geom_shape = shape(geom_data)
                
                block_type = props.get("blockType", "block")
                
                # Lấy penalty multiplier từ properties (default: 5.0 cho flood)
                penalty = props.get("penalty", 5.0 if block_type == "flood" else None)
                
                # STRtree query - O(log N)
                affected_edges = self.graph.query_edges_in_geometry(geom_shape)
                
                for edge_key in affected_edges:
                    if block_type == "flood" and penalty is not None:
                        # Flood area: tăng weight rất cao để né hoàn toàn
                        # Nếu penalty >= 100, coi như block (tránh đi xuyên qua)
                        if penalty >= 100.0:
                            blocked.add(edge_key)
                            # Xóa khỏi penalty_map nếu có
                            penalty_map.pop(edge_key, None)
                        else:
                            # Tăng weight, nếu đã có penalty, lấy max
                            current_penalty = penalty_map.get(edge_key, 1.0)
                            penalty_map[edge_key] = max(current_penalty, penalty)
                    else:
                        # Block hoàn toàn
                        blocked.add(edge_key)
                        
            except Exception:
                continue
        
        return blocked, penalty_map
    
    # Legacy method - redirect to fast version
    def apply_blocking_geometries(
        self,
        geometries: List[Dict[str, Any]]
    ) -> Tuple[Set[Tuple[int, int]], Dict[Tuple[int, int], float]]:
        """Legacy wrapper - uses STRtree internally"""
        return self.find_affected_edges_fast(geometries)


_routing_service: Optional[FastRoutingService] = None

def get_routing_service() -> FastRoutingService:
    global _routing_service
    if _routing_service is None:
        _routing_service = FastRoutingService()
    return _routing_service
