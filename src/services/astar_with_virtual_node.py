# src/services/astar_with_virtual_node.py
"""
A* với hỗ trợ Virtual Node
Cho phép bắt đầu/kết thúc từ điểm không nằm trên graph
"""
import heapq
import time
from typing import Dict, List, Tuple, Optional, Set, Any
from dataclasses import dataclass

from .graph_builder import GraphNode, GraphEdge, LightGraph, haversine_distance
from .fast_pathfinding_service import PathResult, _merge_geometries, _collect_edges_and_stats, heuristic
from .lite_geocoding_service import VirtualNode


def astar_with_virtual_nodes(
    graph: LightGraph,
    start_virtual: Optional[VirtualNode] = None,
    start_node_id: Optional[int] = None,
    end_virtual: Optional[VirtualNode] = None,
    end_node_id: Optional[int] = None,
    weather: str = "normal"
) -> PathResult:
    """
    A* search với hỗ trợ virtual nodes
    
    Args:
        graph: LightGraph
        start_virtual: VirtualNode cho điểm bắt đầu (nếu có)
        start_node_id: Node ID thật cho điểm bắt đầu (nếu không dùng virtual)
        end_virtual: VirtualNode cho điểm kết thúc (nếu có)
        end_node_id: Node ID thật cho điểm kết thúc (nếu không dùng virtual)
        weather: Điều kiện thời tiết
    
    Returns:
        PathResult
    """
    start_time = time.perf_counter()
    
    # Xác định start và end nodes
    if start_virtual:
        # Bắt đầu từ virtual node, neighbors là các node thật
        start_neighbors = start_virtual.neighbors
        if not start_neighbors:
            return PathResult(success=False, error="Virtual start node không có neighbors")
        # Dùng node đầu tiên làm node tham chiếu
        start_ref_node_id = start_neighbors[0][0]
        start_ref_node = graph.get_node(start_ref_node_id)
        if not start_ref_node:
            return PathResult(success=False, error="Start reference node không tồn tại")
    elif start_node_id:
        if not graph.has_node(start_node_id):
            return PathResult(success=False, error="Start node không tồn tại")
        start_ref_node_id = start_node_id
        start_ref_node = graph.get_node(start_node_id)
        start_neighbors = None
    else:
        return PathResult(success=False, error="Cần start_virtual hoặc start_node_id")
    
    if end_virtual:
        end_neighbors = end_virtual.neighbors
        if not end_neighbors:
            return PathResult(success=False, error="Virtual end node không có neighbors")
        end_ref_node_id = end_neighbors[0][0]
        end_ref_node = graph.get_node(end_ref_node_id)
        if not end_ref_node:
            return PathResult(success=False, error="End reference node không tồn tại")
    elif end_node_id:
        if not graph.has_node(end_node_id):
            return PathResult(success=False, error="End node không tồn tại")
        end_ref_node_id = end_node_id
        end_ref_node = graph.get_node(end_node_id)
        end_neighbors = None
    else:
        return PathResult(success=False, error="Cần end_virtual hoặc end_node_id")
    
    # Priority queue: (f_score, counter, node_id, is_virtual)
    counter = 0
    
    # Khởi tạo từ virtual node hoặc node thật
    if start_virtual:
        # Bắt đầu từ tất cả neighbors của virtual node
        open_set = []
        g_score: Dict[int, float] = {}
        came_from: Dict[int, Tuple[Optional[int], Optional[VirtualNode]]] = {}  # (parent_node_id, parent_virtual)
        came_from_edge: Dict[int, Optional[GraphEdge]] = {}
        
        for neighbor_id, dist in start_virtual.neighbors:
            # Chi phí từ virtual node đến neighbor
            g_score[neighbor_id] = dist / 1000.0  # Convert meters to km for weight
            came_from[neighbor_id] = (None, start_virtual)  # None = từ virtual node
            came_from_edge[neighbor_id] = None
            
            neighbor_node = graph.get_node(neighbor_id)
            if neighbor_node:
                f = g_score[neighbor_id] + heuristic(neighbor_node, end_ref_node)
                counter += 1
                heapq.heappush(open_set, (f, counter, neighbor_id))
    else:
        open_set = [(0.0, counter, start_ref_node_id)]
        g_score: Dict[int, float] = {start_ref_node_id: 0.0}
        came_from: Dict[int, Tuple[Optional[int], Optional[VirtualNode]]] = {start_ref_node_id: (None, None)}
        came_from_edge: Dict[int, Optional[GraphEdge]] = {}
    
    open_set_hash: Set[int] = set(node_id for _, _, node_id in open_set)
    closed_set: Set[int] = set()
    nodes_visited = 0
    
    while open_set:
        _, _, current = heapq.heappop(open_set)
        
        if current in closed_set:
            continue
        
        open_set_hash.discard(current)
        nodes_visited += 1
        
        # Kiểm tra đích
        if end_virtual:
            # Đích là virtual node, kiểm tra nếu current là một trong neighbors
            if any(neighbor_id == current for neighbor_id, _ in end_virtual.neighbors):
                # Tìm đường đến virtual node
                elapsed = time.perf_counter() - start_time
                
                # Reconstruct path
                path = [current]
                edges = []
                total_dist = 0.0
                total_dur = 0.0
                
                # Thêm chi phí từ current đến virtual end node
                for neighbor_id, dist in end_virtual.neighbors:
                    if neighbor_id == current:
                        total_dist += dist
                        # Estimate travel time (assume 30 km/h)
                        total_dur += (dist / 1000.0) / 30.0 * 3600
                        break
                
                # Reconstruct từ current về start
                while current in came_from:
                    parent_id, parent_virtual = came_from[current]
                    edge = came_from_edge.get(current)
                    
                    if edge:
                        edges.append(edge)
                        total_dist += edge.length
                        total_dur += edge.travel_time
                    
                    if parent_id is None:
                        # Đến virtual start node
                        if parent_virtual:
                            # Thêm chi phí từ virtual start đến current
                            for neighbor_id, dist in parent_virtual.neighbors:
                                if neighbor_id == current:
                                    total_dist += dist
                                    total_dur += (dist / 1000.0) / 30.0 * 3600
                                    break
                        break
                    
                    path.append(parent_id)
                    current = parent_id
                
                path.reverse()
                edges.reverse()
                
                # Merge geometries - sử dụng REAL geometry từ edges với path_nodes
                coords = _merge_geometries(edges, graph, path_nodes=path) if edges else []
                
                # Thêm điểm virtual start và end vào geometry
                if start_virtual and coords:
                    coords.insert(0, (start_virtual.lon, start_virtual.lat))
                if end_virtual and coords:
                    coords.append((end_virtual.lon, end_virtual.lat))
                
                return PathResult(
                    success=True,
                    path=path,
                    distance=total_dist,
                    duration=total_dur / 60.0,  # Convert to minutes
                    geometry=coords,
                    stats={
                        "nodes_visited": nodes_visited,
                        "search_time_ms": elapsed * 1000,
                        "path_length": len(path),
                        "weather": weather,
                        "has_virtual_start": start_virtual is not None,
                        "has_virtual_end": end_virtual is not None
                    }
                )
        else:
            # Đích là node thật
            if current == end_ref_node_id:
                elapsed = time.perf_counter() - start_time
                path, edges, dist, dur = _collect_edges_and_stats_simple(came_from, came_from_edge, end_ref_node_id)
                
                # Thêm chi phí từ virtual start nếu có
                if start_virtual and path:
                    first_node = path[0]
                    for neighbor_id, dist_virtual in start_virtual.neighbors:
                        if neighbor_id == first_node:
                            dist += dist_virtual
                            dur += (dist_virtual / 1000.0) / 30.0 * 3600
                            break
                
                coords = _merge_geometries(edges) if edges else []
                
                # Thêm điểm virtual start vào geometry
                if start_virtual and coords:
                    coords.insert(0, (start_virtual.lon, start_virtual.lat))
                
                return PathResult(
                    success=True,
                    path=path,
                    distance=dist,
                    duration=dur / 60.0,
                    geometry=coords,
                    stats={
                        "nodes_visited": nodes_visited,
                        "search_time_ms": elapsed * 1000,
                        "path_length": len(path),
                        "weather": weather,
                        "has_virtual_start": start_virtual is not None,
                        "has_virtual_end": False
                    }
                )
        
        closed_set.add(current)
        current_g = g_score[current]
        
        # Expand neighbors
        for neighbor_id, edge in graph.get_neighbors(current):
            if neighbor_id in closed_set:
                continue
            
            weight = edge.get_weight(weather)
            tentative_g = current_g + weight
            
            if neighbor_id not in g_score or tentative_g < g_score[neighbor_id]:
                came_from[neighbor_id] = (current, None)
                came_from_edge[neighbor_id] = edge
                g_score[neighbor_id] = tentative_g
                
                neighbor_node = graph.get_node(neighbor_id)
                if neighbor_node:
                    f = tentative_g + heuristic(neighbor_node, end_ref_node)
                    
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


def _collect_edges_and_stats_simple(
    came_from: Dict[int, Tuple[Optional[int], Optional[VirtualNode]]],
    came_from_edge: Dict[int, Optional[GraphEdge]],
    end_id: int
) -> Tuple[List[int], List[GraphEdge], float, float]:
    """Thu thập path, edges, distance, duration (simplified version)"""
    path = [end_id]
    edges = []
    total_dist = 0.0
    total_dur = 0.0
    
    current = end_id
    while current in came_from:
        parent_id, parent_virtual = came_from[current]
        
        edge = came_from_edge.get(current)
        if edge:
            edges.append(edge)
            total_dist += edge.length
            total_dur += edge.travel_time
        
        if parent_id is None:
            break
        
        path.append(parent_id)
        current = parent_id
    
    path.reverse()
    edges.reverse()
    return path, edges, total_dist, total_dur

