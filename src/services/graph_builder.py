# src/services/graph_builder.py
"""
Module xây dựng graph tối ưu từ dữ liệu OSM
Pipeline: Parse → Filter → LSCC → Compress → KD-Tree
"""
import math
import numpy as np
from scipy.spatial import KDTree
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Set
from .overpass_service import OSMData, OSMNode, OSMWay


# ======================================================================
# Highway Configuration
# ======================================================================

ALLOWED_HIGHWAYS = {
    "motorway", "motorway_link", "trunk", "trunk_link",
    "primary", "primary_link", "secondary", "secondary_link",
    "tertiary", "tertiary_link", "residential", "living_street",
    "unclassified", "service"
}

EXCLUDED_HIGHWAYS = {
    "abandoned", "construction", "proposed", "planned",
    "footway", "pedestrian", "path", "cycleway", "steps",
    "corridor", "elevator", "escalator", "bridleway", "track"
}

C_HIGHWAY = {
    "motorway": 0.7, "motorway_link": 0.75,
    "trunk": 0.75, "trunk_link": 0.8,
    "primary": 0.8, "primary_link": 0.85,
    "secondary": 1.0, "secondary_link": 1.05,
    "tertiary": 1.1, "tertiary_link": 1.15,
    "residential": 1.2, "living_street": 1.3,
    "unclassified": 1.2, "service": 1.5,
}

C_CONTEXT = {
    "normal": {k: 1.0 for k in C_HIGHWAY},
    "rain": {
        "motorway": 1.05, "motorway_link": 1.1,
        "trunk": 1.1, "trunk_link": 1.15,
        "primary": 1.1, "primary_link": 1.15,
        "secondary": 1.2, "secondary_link": 1.25,
        "tertiary": 1.3, "tertiary_link": 1.35,
        "residential": 1.8, "living_street": 2.0,
        "unclassified": 1.5, "service": 2.5,
    },
    "flood": {
        "motorway": 1.1, "motorway_link": 1.2,
        "trunk": 1.2, "trunk_link": 1.3,
        "primary": 1.2, "primary_link": 1.3,
        "secondary": 1.5, "secondary_link": 1.6,
        "tertiary": 2.0, "tertiary_link": 2.2,
        "residential": 3.0, "living_street": 4.0,
        "unclassified": 2.5, "service": 5.0,
    }
}

SPEED_LIMITS = {
    "motorway": 100, "motorway_link": 60,
    "trunk": 80, "trunk_link": 50,
    "primary": 60, "primary_link": 40,
    "secondary": 50, "secondary_link": 35,
    "tertiary": 40, "tertiary_link": 30,
    "residential": 30, "living_street": 20,
    "unclassified": 30, "service": 20,
}


# ======================================================================
# Data Classes
# ======================================================================

@dataclass
class GraphNode:
    id: int
    lat: float
    lon: float
    
    def __hash__(self):
        return hash(self.id)
    
    def __eq__(self, other):
        return isinstance(other, GraphNode) and self.id == other.id


@dataclass
class GraphEdge:
    from_node: int
    to_node: int
    way_id: int
    length: float
    highway_type: str
    name: str = ""
    speed: float = 30.0
    c_highway: float = 1.0
    geometry: List[Tuple[float, float]] = field(default_factory=list)
    
    def get_weight(self, weather: str = "normal") -> float:
        c_context = C_CONTEXT.get(weather, C_CONTEXT["normal"]).get(self.highway_type, 1.0)
        return self.length * self.c_highway * c_context
    
    @property
    def travel_time(self) -> float:
        return (self.length / 1000) / self.speed * 3600


@dataclass
class LightGraph:
    nodes: Dict[int, GraphNode] = field(default_factory=dict)
    adjacency: Dict[int, List[Tuple[int, GraphEdge]]] = field(default_factory=dict)
    reverse_adjacency: Dict[int, List[Tuple[int, GraphEdge]]] = field(default_factory=dict)
    
    _node_ids: np.ndarray = None
    _node_coords: np.ndarray = None
    _kdtree: KDTree = None
    
    def add_node(self, node: GraphNode):
        self.nodes[node.id] = node
        if node.id not in self.adjacency:
            self.adjacency[node.id] = []
        if node.id not in self.reverse_adjacency:
            self.reverse_adjacency[node.id] = []
    
    def add_edge(self, edge: GraphEdge):
        if edge.from_node not in self.adjacency:
            self.adjacency[edge.from_node] = []
        if edge.to_node not in self.reverse_adjacency:
            self.reverse_adjacency[edge.to_node] = []
        self.adjacency[edge.from_node].append((edge.to_node, edge))
        self.reverse_adjacency[edge.to_node].append((edge.from_node, edge))
    
    def build_kdtree(self):
        if not self.nodes:
            return
        node_list = list(self.nodes.items())
        self._node_ids = np.array([nid for nid, _ in node_list])
        self._node_coords = np.array([[n.lat, n.lon] for _, n in node_list])
        self._kdtree = KDTree(self._node_coords)
        print(f"  KD-Tree: {len(self._node_ids)} nodes indexed")
    
    def find_nearest_node(self, lat: float, lon: float) -> Optional[int]:
        if self._kdtree is None:
            self.build_kdtree()
        if self._kdtree is None:
            return None
        _, idx = self._kdtree.query([lat, lon])
        return int(self._node_ids[idx])
    
    def get_neighbors(self, node_id: int) -> List[Tuple[int, GraphEdge]]:
        return self.adjacency.get(node_id, [])
    
    def get_node(self, node_id: int) -> Optional[GraphNode]:
        return self.nodes.get(node_id)
    
    def has_node(self, node_id: int) -> bool:
        return node_id in self.nodes
    
    @property
    def node_count(self) -> int:
        return len(self.nodes)
    
    @property
    def edge_count(self) -> int:
        return sum(len(edges) for edges in self.adjacency.values())
    
    def get_bounds(self) -> Tuple[float, float, float, float]:
        if not self.nodes:
            return (0, 0, 0, 0)
        lats = [n.lat for n in self.nodes.values()]
        lons = [n.lon for n in self.nodes.values()]
        return (min(lats), min(lons), max(lats), max(lons))


# ======================================================================
# Utility Functions
# ======================================================================

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def is_oneway(tags: dict) -> bool:
    return tags.get("oneway", "no") in ("yes", "1", "true", "-1")


def is_reverse_oneway(tags: dict) -> bool:
    return tags.get("oneway") == "-1"


# ======================================================================
# Step 1: Parse & Filter
# ======================================================================

def filter_valid_ways(osm_data: OSMData) -> List[OSMWay]:
    valid_ways = []
    for way in osm_data.ways:
        highway = way.tags.get("highway", "")
        if highway and highway not in EXCLUDED_HIGHWAYS and highway in ALLOWED_HIGHWAYS:
            valid_ways.append(way)
    print(f"  Filter: {len(valid_ways)}/{len(osm_data.ways)} ways")
    return valid_ways


def build_raw_graph(osm_data: OSMData, valid_ways: List[OSMWay]) -> LightGraph:
    graph = LightGraph()
    
    used_node_ids: Set[int] = set()
    for way in valid_ways:
        used_node_ids.update(way.nodes)
    
    for node_id in used_node_ids:
        if node_id in osm_data.nodes:
            osm_node = osm_data.nodes[node_id]
            graph.add_node(GraphNode(id=osm_node.id, lat=osm_node.lat, lon=osm_node.lon))
    
    for way in valid_ways:
        highway_type = way.tags.get("highway", "unclassified")
        name = way.tags.get("name", "")
        speed = SPEED_LIMITS.get(highway_type, 30)
        c_highway = C_HIGHWAY.get(highway_type, 1.0)
        
        oneway = is_oneway(way.tags)
        reverse = is_reverse_oneway(way.tags)
        
        for i in range(len(way.nodes) - 1):
            from_id, to_id = way.nodes[i], way.nodes[i + 1]
            if from_id not in graph.nodes or to_id not in graph.nodes:
                continue
            
            from_node, to_node = graph.nodes[from_id], graph.nodes[to_id]
            length = haversine_distance(from_node.lat, from_node.lon, to_node.lat, to_node.lon)
            geometry = [(from_node.lon, from_node.lat), (to_node.lon, to_node.lat)]
            
            if reverse:
                graph.add_edge(GraphEdge(to_id, from_id, way.id, length, highway_type, name, speed, c_highway, list(reversed(geometry))))
            elif oneway:
                graph.add_edge(GraphEdge(from_id, to_id, way.id, length, highway_type, name, speed, c_highway, geometry))
            else:
                graph.add_edge(GraphEdge(from_id, to_id, way.id, length, highway_type, name, speed, c_highway, geometry))
                graph.add_edge(GraphEdge(to_id, from_id, way.id, length, highway_type, name, speed, c_highway, list(reversed(geometry))))
    
    print(f"  Raw graph: {graph.node_count} nodes, {graph.edge_count} edges")
    return graph


# ======================================================================
# Step 2: LSCC Filtering (Kosaraju's Algorithm)
# ======================================================================

def find_largest_scc(graph: LightGraph) -> Set[int]:
    """
    Tìm Largest Strongly Connected Component (LSCC) sử dụng Kosaraju's Algorithm
    Đây là "Lục địa chính" - đảm bảo từ bất kỳ node nào cũng đến được node khác
    """
    if not graph.nodes:
        return set()
    
    # Step 1: DFS trên graph gốc, ghi nhận finish time
    visited = set()
    finish_order = []
    
    def dfs1(node):
        stack = [(node, False)]
        while stack:
            n, processed = stack.pop()
            if processed:
                finish_order.append(n)
                continue
            if n in visited:
                continue
            visited.add(n)
            stack.append((n, True))
            for neighbor, _ in graph.adjacency.get(n, []):
                if neighbor not in visited:
                    stack.append((neighbor, False))
    
    for node_id in graph.nodes:
        if node_id not in visited:
            dfs1(node_id)
    
    # Step 2: DFS trên reverse graph theo thứ tự finish time giảm dần
    visited.clear()
    sccs = []
    
    def dfs2(start):
        component = []
        stack = [start]
        while stack:
            n = stack.pop()
            if n in visited:
                continue
            visited.add(n)
            component.append(n)
            for neighbor, _ in graph.reverse_adjacency.get(n, []):
                if neighbor not in visited:
                    stack.append(neighbor)
        return component
    
    for node_id in reversed(finish_order):
        if node_id not in visited:
            scc = dfs2(node_id)
            sccs.append(scc)
    
    # Tìm SCC lớn nhất
    largest_scc = max(sccs, key=len) if sccs else []
    
    print(f"  SCC Analysis: {len(sccs)} components found")
    print(f"  LSCC (Lục địa chính): {len(largest_scc)} nodes ({len(largest_scc)*100//graph.node_count}%)")
    
    # Log các ốc đảo bị loại bỏ
    islands_count = len(sccs) - 1
    islands_nodes = graph.node_count - len(largest_scc)
    if islands_count > 0:
        print(f"  Loại bỏ: {islands_count} ốc đảo ({islands_nodes} nodes)")
    
    return set(largest_scc)


def filter_to_lscc(graph: LightGraph, lscc_nodes: Set[int]) -> LightGraph:
    """Lọc graph chỉ giữ lại các nodes trong LSCC"""
    filtered = LightGraph()
    
    for node_id in lscc_nodes:
        if node_id in graph.nodes:
            filtered.add_node(graph.nodes[node_id])
    
    for from_node, neighbors in graph.adjacency.items():
        if from_node not in lscc_nodes:
            continue
        for to_node, edge in neighbors:
            if to_node in lscc_nodes:
                filtered.add_edge(edge)
    
    return filtered


# ======================================================================
# Step 3: Geometry Packing (Compress degree-2 nodes)
# ======================================================================

def compress_graph(graph: LightGraph) -> LightGraph:
    """Nén đồ thị: merge các node bậc 2, giữ geometry đầy đủ"""
    compressed = LightGraph()
    
    nodes_to_keep: Set[int] = set()
    degree_2_nodes: Set[int] = set()
    
    for node_id in graph.nodes:
        out_neighbors = set(n for n, _ in graph.adjacency.get(node_id, []))
        in_neighbors = set(n for n, _ in graph.reverse_adjacency.get(node_id, []))
        unique_neighbors = out_neighbors | in_neighbors
        
        if len(unique_neighbors) == 2:
            out_types = set(e.highway_type for _, e in graph.adjacency.get(node_id, []))
            in_types = set(e.highway_type for _, e in graph.reverse_adjacency.get(node_id, []))
            if len(out_types | in_types) == 1:
                degree_2_nodes.add(node_id)
            else:
                nodes_to_keep.add(node_id)
        else:
            nodes_to_keep.add(node_id)
    
    for node_id in nodes_to_keep:
        compressed.add_node(graph.nodes[node_id])
    
    processed_edges: Set[Tuple[int, int]] = set()
    
    for start_node in nodes_to_keep:
        for neighbor_id, edge in graph.adjacency.get(start_node, []):
            if (start_node, neighbor_id) in processed_edges:
                continue
            
            path_nodes = [start_node, neighbor_id]
            geometry = list(edge.geometry)
            total_length = edge.length
            
            current, prev = neighbor_id, start_node
            
            while current in degree_2_nodes:
                next_edges = [(n, e) for n, e in graph.adjacency.get(current, []) if n != prev]
                if not next_edges:
                    break
                next_node, next_edge = next_edges[0]
                path_nodes.append(next_node)
                if next_edge.geometry:
                    geometry.extend(next_edge.geometry[1:])
                total_length += next_edge.length
                prev, current = current, next_node
            
            end_node = path_nodes[-1]
            if end_node in nodes_to_keep:
                new_edge = GraphEdge(
                    start_node, end_node, edge.way_id, total_length,
                    edge.highway_type, edge.name, edge.speed, edge.c_highway, geometry
                )
                compressed.add_edge(new_edge)
                processed_edges.add((start_node, end_node))
    
    print(f"  Compress: {graph.node_count} → {compressed.node_count} nodes, "
          f"{graph.edge_count} → {compressed.edge_count} edges")
    
    return compressed


# ======================================================================
# Main Build Function (Full Pipeline)
# ======================================================================

def build_graph_from_osm(osm_data: OSMData) -> LightGraph:
    """
    Pipeline hoàn chỉnh:
    1. Parse & Filter ways
    2. Build raw graph
    3. LSCC Filtering (loại bỏ ốc đảo)
    4. Compress (gom node bậc 2)
    5. Build KD-Tree
    """
    print("Building graph...")
    
    # Step 1: Filter
    valid_ways = filter_valid_ways(osm_data)
    if not valid_ways:
        print("  Không có ways hợp lệ!")
        return LightGraph()
    
    # Step 2: Raw graph
    raw_graph = build_raw_graph(osm_data, valid_ways)
    
    # Step 3: LSCC Filtering
    lscc_nodes = find_largest_scc(raw_graph)
    if not lscc_nodes:
        print("  Không tìm thấy LSCC!")
        return LightGraph()
    
    lscc_graph = filter_to_lscc(raw_graph, lscc_nodes)
    
    # Step 4: Compress
    final_graph = compress_graph(lscc_graph)
    
    # Step 5: KD-Tree (chỉ từ LSCC nodes)
    final_graph.build_kdtree()
    
    print(f"  ✓ Final: {final_graph.node_count} nodes, {final_graph.edge_count} edges")
    
    return final_graph


# ======================================================================
# Export Functions
# ======================================================================

def graph_to_geojson(graph: LightGraph) -> dict:
    features = []
    seen = set()
    
    for from_node, neighbors in graph.adjacency.items():
        for to_node, edge in neighbors:
            key = tuple(sorted([from_node, to_node]))
            if key in seen:
                continue
            seen.add(key)
            
            features.append({
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": edge.geometry or []},
                "properties": {
                    "highway": edge.highway_type,
                    "name": edge.name,
                    "length": edge.length
                }
            })
    
    return {"type": "FeatureCollection", "features": features}


def copy_graph_with_modifications(
    original: LightGraph,
    blocked_edges: Set[Tuple[int, int]] = None,
    weight_multipliers: Dict[Tuple[int, int], float] = None
) -> LightGraph:
    blocked_edges = blocked_edges or set()
    weight_multipliers = weight_multipliers or {}
    
    new_graph = LightGraph()
    new_graph.nodes = original.nodes.copy()
    new_graph._node_ids = original._node_ids
    new_graph._node_coords = original._node_coords
    new_graph._kdtree = original._kdtree
    
    for from_node, neighbors in original.adjacency.items():
        for to_node, edge in neighbors:
            if (from_node, to_node) in blocked_edges:
                continue
            
            if (from_node, to_node) in weight_multipliers:
                new_edge = GraphEdge(
                    edge.from_node, edge.to_node, edge.way_id, edge.length,
                    edge.highway_type, edge.name, edge.speed,
                    edge.c_highway * weight_multipliers[(from_node, to_node)],
                    edge.geometry
                )
                new_graph.add_edge(new_edge)
            else:
                new_graph.add_edge(edge)
    
    return new_graph
