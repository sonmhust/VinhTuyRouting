# src/services/local_geocoding_service.py
"""
Local Geocoding Service sử dụng SQLite FTS5
- Không phụ thuộc API bên ngoài
- Tìm kiếm địa chỉ < 5ms
- Autocomplete khi gõ
"""
import sqlite3
import math
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass

# RapidFuzz cho fuzzy matching (optional, fallback nếu không có)
try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

from .overpass_service import OSMData


# ======================================================================
# Data Classes
# ======================================================================

@dataclass
class AddressEntry:
    """Một địa chỉ trong database"""
    node_id: int
    lat: float
    lon: float
    address: str  # Full address string
    house_number: str
    street_name: str
    address_type: str  # "house", "street", "poi"
    rank_score: int  # Để sắp xếp (street > house)


@dataclass 
class SearchResult:
    """Kết quả tìm kiếm"""
    node_id: int
    lat: float
    lon: float
    address: str
    score: float
    address_type: str


# ======================================================================
# Address Extraction from OSM Data
# ======================================================================

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Khoảng cách giữa 2 điểm (meters)"""
    R = 6371000
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def extract_addresses_from_osm(osm_data: OSMData, graph_node_ids: Set[int]) -> List[AddressEntry]:
    """
    Trích xuất địa chỉ từ OSM data:
    1. Nodes có addr:housenumber
    2. Ways có name (đường/ngõ)
    3. Spatial join để tạo full address
    """
    addresses = []
    
    # 1. Thu thập tất cả street names từ ways
    streets = []  # [(way_id, name, nodes_coords)]
    for way in osm_data.ways:
        name = way.tags.get("name", "")
        if not name:
            continue
        
        # Lấy tọa độ trung tâm của way
        way_coords = []
        for node_id in way.nodes:
            if node_id in osm_data.nodes:
                n = osm_data.nodes[node_id]
                way_coords.append((n.lat, n.lon))
        
        if way_coords:
            # Tính centroid
            center_lat = sum(c[0] for c in way_coords) / len(way_coords)
            center_lon = sum(c[1] for c in way_coords) / len(way_coords)
            
            # Thêm way như một địa chỉ (đường/ngõ)
            # Tìm node gần nhất trong graph
            nearest_node = None
            min_dist = float('inf')
            for node_id in way.nodes:
                if node_id in graph_node_ids:
                    nearest_node = node_id
                    break
            
            if nearest_node and nearest_node in osm_data.nodes:
                n = osm_data.nodes[nearest_node]
                addresses.append(AddressEntry(
                    node_id=nearest_node,
                    lat=n.lat,
                    lon=n.lon,
                    address=name,
                    house_number="",
                    street_name=name,
                    address_type="street",
                    rank_score=100  # Streets rank higher
                ))
            
            streets.append((way.id, name, center_lat, center_lon, way.nodes))
    
    # 2. Thu thập nodes có địa chỉ (house number)
    for node_id, node in osm_data.nodes.items():
        house_num = node.tags.get("addr:housenumber", "")
        if not house_num:
            continue
        
        # Tìm street gần nhất
        street_name = node.tags.get("addr:street", "")
        
        if not street_name and streets:
            # Spatial join: tìm way gần nhất
            min_dist = float('inf')
            for way_id, name, way_lat, way_lon, way_nodes in streets:
                dist = haversine_distance(node.lat, node.lon, way_lat, way_lon)
                if dist < min_dist:
                    min_dist = dist
                    street_name = name
        
        if street_name:
            full_address = f"{house_num} {street_name}"
        else:
            full_address = house_num
        
        # Tìm node gần nhất trong graph để snap
        nearest_graph_node = None
        min_dist = float('inf')
        for gn_id in graph_node_ids:
            if gn_id in osm_data.nodes:
                gn = osm_data.nodes[gn_id]
                dist = haversine_distance(node.lat, node.lon, gn.lat, gn.lon)
                if dist < min_dist:
                    min_dist = dist
                    nearest_graph_node = gn_id
        
        if nearest_graph_node and min_dist < 100:  # Trong 100m
            gn = osm_data.nodes[nearest_graph_node]
            addresses.append(AddressEntry(
                node_id=nearest_graph_node,
                lat=gn.lat,
                lon=gn.lon,
                address=full_address,
                house_number=house_num,
                street_name=street_name,
                address_type="house",
                rank_score=50  # Houses rank lower than streets
            ))
    
    # 3. Thu thập POIs (places có name)
    for node_id, node in osm_data.nodes.items():
        name = node.tags.get("name", "")
        if not name:
            continue
        
        # Skip nếu đã có trong addresses
        if any(a.address == name for a in addresses):
            continue
        
        # Tìm node gần nhất trong graph
        nearest_graph_node = None
        min_dist = float('inf')
        for gn_id in graph_node_ids:
            if gn_id in osm_data.nodes:
                gn = osm_data.nodes[gn_id]
                dist = haversine_distance(node.lat, node.lon, gn.lat, gn.lon)
                if dist < min_dist:
                    min_dist = dist
                    nearest_graph_node = gn_id
        
        if nearest_graph_node and min_dist < 100:
            gn = osm_data.nodes[nearest_graph_node]
            addresses.append(AddressEntry(
                node_id=nearest_graph_node,
                lat=gn.lat,
                lon=gn.lon,
                address=name,
                house_number="",
                street_name="",
                address_type="poi",
                rank_score=80  # POIs rank between streets and houses
            ))
    
    print(f"  Extracted {len(addresses)} addresses ({sum(1 for a in addresses if a.address_type=='street')} streets, "
          f"{sum(1 for a in addresses if a.address_type=='house')} houses, "
          f"{sum(1 for a in addresses if a.address_type=='poi')} POIs)")
    
    return addresses


# ======================================================================
# SQLite FTS5 Database
# ======================================================================

class LocalGeocodingDB:
    """SQLite FTS5 database cho local geocoding"""
    
    def __init__(self, db_path: str = ":memory:"):
        """
        Args:
            db_path: Đường dẫn database. ":memory:" cho in-memory DB
        """
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._init_db()
    
    def _init_db(self):
        """Khởi tạo database với FTS5"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
        # Tạo bảng chính
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS addresses (
                id INTEGER PRIMARY KEY,
                node_id INTEGER NOT NULL,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                address TEXT NOT NULL,
                house_number TEXT,
                street_name TEXT,
                address_type TEXT,
                rank_score INTEGER DEFAULT 50
            )
        """)
        
        # Tạo FTS5 virtual table với unicode61 tokenizer
        self.conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS address_search USING fts5(
                address,
                content='addresses',
                content_rowid='id',
                tokenize='unicode61 remove_diacritics 2'
            )
        """)
        
        # Index cho node_id lookup
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_node_id ON addresses(node_id)")
        
        self.conn.commit()
    
    def populate(self, addresses: List[AddressEntry]):
        """Đưa dữ liệu vào database"""
        cursor = self.conn.cursor()
        
        # Clear existing data
        cursor.execute("DELETE FROM addresses")
        cursor.execute("DELETE FROM address_search")
        
        # Insert addresses
        cursor.executemany("""
            INSERT INTO addresses (node_id, lat, lon, address, house_number, street_name, address_type, rank_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (a.node_id, a.lat, a.lon, a.address, a.house_number, a.street_name, a.address_type, a.rank_score)
            for a in addresses
        ])
        
        # Rebuild FTS index
        cursor.execute("INSERT INTO address_search(address_search) VALUES('rebuild')")
        
        self.conn.commit()
        print(f"  FTS5 DB populated with {len(addresses)} entries")
    
    def search(self, query: str, limit: int = 5) -> List[SearchResult]:
        """
        Tìm kiếm địa chỉ với FTS5
        
        Args:
            query: Chuỗi tìm kiếm
            limit: Số kết quả tối đa
        
        Returns:
            List of SearchResult
        """
        if not query or len(query) < 2:
            return []
        
        cursor = self.conn.cursor()
        
        # Prefix search với FTS5
        # Escape special characters và thêm * cho prefix matching
        safe_query = query.replace('"', '""').replace("'", "''")
        
        try:
            # FTS5 MATCH với prefix
            cursor.execute("""
                SELECT 
                    a.node_id, a.lat, a.lon, a.address, a.address_type, a.rank_score,
                    bm25(address_search) as fts_score
                FROM address_search s
                JOIN addresses a ON s.rowid = a.id
                WHERE address_search MATCH ?
                ORDER BY a.rank_score DESC, fts_score
                LIMIT ?
            """, (f'"{safe_query}"*', limit))
            
            results = []
            for row in cursor.fetchall():
                results.append(SearchResult(
                    node_id=row['node_id'],
                    lat=row['lat'],
                    lon=row['lon'],
                    address=row['address'],
                    score=row['rank_score'] - row['fts_score'],  # Higher is better
                    address_type=row['address_type']
                ))
            
            # Nếu không có kết quả từ FTS, thử LIKE
            if not results:
                cursor.execute("""
                    SELECT node_id, lat, lon, address, address_type, rank_score
                    FROM addresses
                    WHERE address LIKE ?
                    ORDER BY rank_score DESC
                    LIMIT ?
                """, (f'%{safe_query}%', limit))
                
                for row in cursor.fetchall():
                    results.append(SearchResult(
                        node_id=row['node_id'],
                        lat=row['lat'],
                        lon=row['lon'],
                        address=row['address'],
                        score=row['rank_score'],
                        address_type=row['address_type']
                    ))
            
            # Fuzzy matching với RapidFuzz nếu có
            if HAS_RAPIDFUZZ and len(results) < limit:
                cursor.execute("SELECT node_id, lat, lon, address, address_type, rank_score FROM addresses")
                all_addresses = cursor.fetchall()
                
                existing_ids = {r.node_id for r in results}
                fuzzy_results = []
                
                for row in all_addresses:
                    if row['node_id'] in existing_ids:
                        continue
                    ratio = fuzz.partial_ratio(query.lower(), row['address'].lower())
                    if ratio > 60:  # Threshold
                        fuzzy_results.append((ratio, SearchResult(
                            node_id=row['node_id'],
                            lat=row['lat'],
                            lon=row['lon'],
                            address=row['address'],
                            score=ratio,
                            address_type=row['address_type']
                        )))
                
                # Sort by ratio and add top results
                fuzzy_results.sort(key=lambda x: x[0], reverse=True)
                for _, result in fuzzy_results[:limit - len(results)]:
                    results.append(result)
            
            return results
            
        except sqlite3.OperationalError as e:
            # Fallback to LIKE if FTS fails
            cursor.execute("""
                SELECT node_id, lat, lon, address, address_type, rank_score
                FROM addresses
                WHERE address LIKE ?
                ORDER BY rank_score DESC
                LIMIT ?
            """, (f'%{safe_query}%', limit))
            
            return [
                SearchResult(
                    node_id=row['node_id'],
                    lat=row['lat'],
                    lon=row['lon'],
                    address=row['address'],
                    score=row['rank_score'],
                    address_type=row['address_type']
                )
                for row in cursor.fetchall()
            ]
    
    def get_by_node_id(self, node_id: int) -> Optional[SearchResult]:
        """Lấy địa chỉ theo node_id"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT node_id, lat, lon, address, address_type, rank_score
            FROM addresses
            WHERE node_id = ?
            LIMIT 1
        """, (node_id,))
        
        row = cursor.fetchone()
        if row:
            return SearchResult(
                node_id=row['node_id'],
                lat=row['lat'],
                lon=row['lon'],
                address=row['address'],
                score=row['rank_score'],
                address_type=row['address_type']
            )
        return None
    
    def get_stats(self) -> Dict:
        """Thống kê database"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM addresses")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT address_type, COUNT(*) FROM addresses GROUP BY address_type")
        by_type = {row[0]: row[1] for row in cursor.fetchall()}
        
        return {"total": total, "by_type": by_type}
    
    def close(self):
        """Đóng connection"""
        if self.conn:
            self.conn.close()
            self.conn = None


# ======================================================================
# Global Instance
# ======================================================================

_geocoding_db: Optional[LocalGeocodingDB] = None


def init_local_geocoding(osm_data: OSMData, graph_node_ids: Set[int]) -> LocalGeocodingDB:
    """
    Khởi tạo local geocoding database từ OSM data
    
    Args:
        osm_data: Dữ liệu OSM đã parse
        graph_node_ids: Set các node_id trong routing graph (LSCC)
    
    Returns:
        LocalGeocodingDB instance
    """
    global _geocoding_db
    
    print("Building local geocoding database...")
    
    # Extract addresses
    addresses = extract_addresses_from_osm(osm_data, graph_node_ids)
    
    # Create and populate DB
    _geocoding_db = LocalGeocodingDB(":memory:")  # In-memory for speed
    _geocoding_db.populate(addresses)
    
    stats = _geocoding_db.get_stats()
    print(f"  ✓ Local geocoding ready: {stats['total']} addresses")
    
    return _geocoding_db


def get_geocoding_db() -> Optional[LocalGeocodingDB]:
    """Lấy global geocoding DB instance"""
    return _geocoding_db

