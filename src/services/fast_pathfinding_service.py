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
    haversine_distance, copy_graph_with_modifications,
    build_graph_from_osm, C_CONTEXT
)
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


def _merge_geometries(edges: List[GraphEdge]) -> List[Tuple[float, float]]:
    """
    Merge geometry từ nhiều edges sử dụng itertools.chain
    Tối ưu: O(n) với generator, không allocate list trung gian
    """
    if not edges:
        return []
    
    # First edge: lấy toàn bộ geometry
    first_geom = edges[0].geometry if edges[0].geometry else []
    
    # Remaining edges: skip point đầu (trùng với point cuối của edge trước)
    rest_geoms = (e.geometry[1:] if e.geometry else [] for e in edges[1:])
    
    # Chain tất cả lại - không tạo list trung gian
    return list(chain(first_geom, *rest_geoms))


def _collect_edges_and_stats(
    came_from: Dict[int, int],
    came_from_edge: Dict[int, GraphEdge],
    end_id: int
) -> Tuple[List[int], List[GraphEdge], float, float]:
    """
    Thu thập path, edges, distance, duration trong một lần duyệt
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
    weather: str = "normal"
) -> PathResult:
    """A* search với flexible weighting"""
    start_time = time.perf_counter()
    
    if not graph.has_node(start_id):
        return PathResult(success=False, error="Start node không tồn tại")
    if not graph.has_node(end_id):
        return PathResult(success=False, error="End node không tồn tại")
    
    start_node = graph.get_node(start_id)
    end_node = graph.get_node(end_id)
    
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
            path, edges, dist, dur = _collect_edges_and_stats(came_from, came_from_edge, end_id)
            coords = _merge_geometries(edges)
            
            return PathResult(
                success=True,
                path=path,
                distance=dist,
                duration=dur,
                geometry=coords,
                stats={
                    "nodes_visited": nodes_visited,
                    "search_time_ms": elapsed * 1000,
                    "path_length": len(path),
                    "weather": weather
                }
            )
        
        closed_set.add(current)
        current_g = g_score[current]
        
        for neighbor_id, edge in graph.get_neighbors(current):
            if neighbor_id in closed_set:
                continue
            
            tentative_g = current_g + edge.get_weight(weather)
            
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
    weather: str = "normal"
) -> PathResult:
    """Bidirectional A* - tìm từ 2 phía"""
    start_time = time.perf_counter()
    
    if not graph.has_node(start_id) or not graph.has_node(end_id):
        return PathResult(success=False, error="Start hoặc end node không tồn tại")
    
    start_node = graph.get_node(start_id)
    end_node = graph.get_node(end_id)
    
    # Forward
    counter_f = 0
    open_f = [(0.0, counter_f, start_id)]
    g_f: Dict[int, float] = {start_id: 0.0}
    came_from_f: Dict[int, int] = {}
    came_from_edge_f: Dict[int, GraphEdge] = {}
    closed_f: Set[int] = set()
    
    # Backward
    counter_b = 0
    open_b = [(0.0, counter_b, end_id)]
    g_b: Dict[int, float] = {end_id: 0.0}
    came_from_b: Dict[int, int] = {}
    came_from_edge_b: Dict[int, GraphEdge] = {}
    closed_b: Set[int] = set()
    
    best_cost = float('inf')
    meeting_node = None
    nodes_visited = 0
    
    while open_f and open_b:
        min_f = open_f[0][0] if open_f else float('inf')
        min_b = open_b[0][0] if open_b else float('inf')
        if min_f + min_b >= best_cost:
            break
        
        # Expand forward
        if open_f:
            _, _, current = heapq.heappop(open_f)
            if current not in closed_f:
                closed_f.add(current)
                nodes_visited += 1
                
                if current in closed_b:
                    cost = g_f[current] + g_b[current]
                    if cost < best_cost:
                        best_cost = cost
                        meeting_node = current
                
                for neighbor_id, edge in graph.get_neighbors(current):
                    if neighbor_id in closed_f:
                        continue
                    tentative_g = g_f[current] + edge.get_weight(weather)
                    if neighbor_id not in g_f or tentative_g < g_f[neighbor_id]:
                        came_from_f[neighbor_id] = current
                        came_from_edge_f[neighbor_id] = edge
                        g_f[neighbor_id] = tentative_g
                        f = tentative_g + heuristic(graph.get_node(neighbor_id), end_node)
                        counter_f += 1
                        heapq.heappush(open_f, (f, counter_f, neighbor_id))
        
        # Expand backward
        if open_b:
            _, _, current = heapq.heappop(open_b)
            if current not in closed_b:
                closed_b.add(current)
                nodes_visited += 1
                
                if current in closed_f:
                    cost = g_f[current] + g_b[current]
                    if cost < best_cost:
                        best_cost = cost
                        meeting_node = current
                
                for neighbor_id, edge in graph.reverse_adjacency.get(current, []):
                    if neighbor_id in closed_b:
                        continue
                    tentative_g = g_b[current] + edge.get_weight(weather)
                    if neighbor_id not in g_b or tentative_g < g_b[neighbor_id]:
                        came_from_b[neighbor_id] = current
                        came_from_edge_b[neighbor_id] = edge
                        g_b[neighbor_id] = tentative_g
                        f = tentative_g + heuristic(graph.get_node(neighbor_id), start_node)
                        counter_b += 1
                        heapq.heappush(open_b, (f, counter_b, neighbor_id))
    
    elapsed = time.perf_counter() - start_time
    
    if meeting_node is None:
        return PathResult(
            success=False,
            error="Không tìm thấy đường đi",
            stats={"nodes_visited": nodes_visited, "search_time_ms": elapsed * 1000}
        )
    
    # Reconstruct path với chain
    path_f, edges_f, dist_f, dur_f = _collect_edges_and_stats(came_from_f, came_from_edge_f, meeting_node)
    
    # Backward path
    path_b = []
    edges_b = []
    dist_b = dur_b = 0.0
    current = meeting_node
    while current in came_from_b:
        edge = came_from_edge_b[current]
        edges_b.append(edge)
        dist_b += edge.length
        dur_b += edge.travel_time
        current = came_from_b[current]
        path_b.append(current)
    
    # Merge geometries
    # Forward: normal order
    coords_f = _merge_geometries(edges_f)
    
    # Backward: reverse each edge's geometry
    coords_b_parts = []
    for edge in edges_b:
        if edge.geometry:
            reversed_geom = list(reversed(edge.geometry))
            if coords_b_parts:
                coords_b_parts.append(reversed_geom[1:])  # Skip first (duplicate)
            else:
                coords_b_parts.append(reversed_geom)
    
    coords_b = list(chain.from_iterable(coords_b_parts))
    
    # Combine: skip first of coords_b (duplicate with last of coords_f)
    if coords_f and coords_b:
        all_coords = coords_f + coords_b[1:]
    else:
        all_coords = coords_f or coords_b
    
    return PathResult(
        success=True,
        path=path_f + path_b,
        distance=dist_f + dist_b,
        duration=dur_f + dur_b,
        geometry=all_coords,
        stats={
            "nodes_visited": nodes_visited,
            "search_time_ms": elapsed * 1000,
            "path_length": len(path_f) + len(path_b),
            "algorithm": "bidirectional_astar",
            "weather": weather
        }
    )


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
        weight_multipliers: Dict[Tuple[int, int], float] = None
    ) -> dict:
        """Core routing logic - shared by both find_route methods"""
        working_graph = self.graph
        if blocked_edges or weight_multipliers:
            working_graph = copy_graph_with_modifications(
                self.graph, blocked_edges or set(), weight_multipliers or {}
            )
        
        result = bidirectional_astar(working_graph, start_id, end_id, weather_condition)
        
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
    
    def apply_blocking_geometries(
        self,
        geometries: List[Dict[str, Any]]
    ) -> Tuple[Set[Tuple[int, int]], Dict[Tuple[int, int], float]]:
        """Xử lý blocking geometries"""
        blocked: Set[Tuple[int, int]] = set()
        multipliers: Dict[Tuple[int, int], float] = {}
        
        if not geometries or not self.graph:
            return blocked, multipliers
        
        for geom_dict in geometries:
            try:
                geom_data = geom_dict.get("geometry", geom_dict)
                props = geom_dict.get("properties", {})
                geom_shape = shape(geom_data)
                is_flood = props.get("blockType") == "flood"
                
                for from_node, neighbors in self.graph.adjacency.items():
                    from_n = self.graph.nodes.get(from_node)
                    if not from_n:
                        continue
                    
                    for to_node, edge in neighbors:
                        to_n = self.graph.nodes.get(to_node)
                        if not to_n:
                            continue
                        
                        edge_line = LineString(edge.geometry) if edge.geometry else \
                                    LineString([(from_n.lon, from_n.lat), (to_n.lon, to_n.lat)])
                        
                        if edge_line.intersects(geom_shape):
                            if is_flood:
                                multipliers[(from_node, to_node)] = 2.0
                            else:
                                blocked.add((from_node, to_node))
            except Exception:
                continue
        
        return blocked, multipliers


_routing_service: Optional[FastRoutingService] = None

def get_routing_service() -> FastRoutingService:
    global _routing_service
    if _routing_service is None:
        _routing_service = FastRoutingService()
    return _routing_service
