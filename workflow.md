# Workflow & Technical Documentation

## 📋 Table of Contents
1. [Tech Stack](#tech-stack)
2. [Data Flow](#data-flow)
3. [Workflow](#workflow)
4. [Project Details](#project-details)

---

## 🛠️ Tech Stack

### Backend
- **Python 3.11+**: Core language
- **FastAPI 0.104.1**: High-performance web framework with automatic OpenAPI documentation
- **Uvicorn 0.24.0**: ASGI server for FastAPI
- **ORJSON 3.9.10**: Fast JSON serialization

### Geospatial & Data Processing
- **Shapely 2.0.2**: Geometric operations (LineString, Polygon, Point, STRtree)
- **NumPy 1.24.0+**: Numerical computing and KD-Tree implementation
- **SciPy 1.11.0+**: Scientific computing (spatial indexing)
- **NetworkX 3.0+**: Graph algorithms (used for LSCC analysis)

### Geocoding & Search
- **SQLite FTS5**: Full-text search for local geocoding
- **RapidFuzz 3.5.0+**: Fuzzy string matching for address search
- **Geopy 2.4.1**: Geocoding utilities

### HTTP & Networking
- **HTTPX 0.23.0+**: Async HTTP client for Overpass API
- **Requests 2.31.0**: HTTP requests (fallback)

### Data Validation
- **Pydantic 2.5.0**: Data validation and settings management

### Frontend
- **Leaflet.js**: Interactive map library
- **Leaflet Draw**: Drawing tools for polygons and circles
- **Vanilla JavaScript**: No framework dependencies

### Infrastructure
- **SQLite**: Local geocoding database and cache storage
- **Uvicorn**: ASGI server for production deployment

---

## 🔄 Data Flow

### 1. Initialization Flow (Startup)

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Startup                       │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  FastAPI Lifespan Event (main.py)                           │
│  - Initialize FastRoutingService                            │
│  - Load graph from BBOX (Vĩnh Tuy)                          │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  FastRoutingService.load_from_bbox()                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 1. Fetch OSM Data (Overpass API)                     │  │
│  │    - Check cache first                                │  │
│  │    - Query Overpass API if cache miss                │  │
│  │    - Parse OSM JSON → OSMData structure               │  │
│  └──────────────────────────────────────────────────────┘  │
│                            │                                 │
│                            ▼                                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 2. Build Graph (graph_builder.py)                    │  │
│  │    - Filter valid highways                            │  │
│  │    - Build raw graph (nodes + edges)                 │  │
│  │    - LSCC filtering (remove islands)                  │  │
│  │    - Compress graph (merge degree-2 nodes)           │  │
│  │    - Build KD-Tree (nearest node lookup)              │  │
│  │    - Build STRtree (spatial queries)                  │  │
│  └──────────────────────────────────────────────────────┘  │
│                            │                                 │
│                            ▼                                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 3. Initialize Local Geocoding                         │  │
│  │    - Extract addresses from OSM data                   │  │
│  │    - Create SQLite FTS5 database                      │  │
│  │    - Index addresses for fast search                  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Service Ready                                              │
│  - Graph: 4197 nodes, 9630 edges (compressed)              │
│  - Geocoding: 1746 addresses indexed                       │
│  - API endpoints active                                    │
└─────────────────────────────────────────────────────────────┘
```

### 2. Routing Request Flow

```
┌─────────────────────────────────────────────────────────────┐
│  Client Request (POST /api/v1/routing/route)               │
│  {                                                          │
│    "origin": "Phố Vĩnh Tuy" | [lat, lon] | node_id,        │
│    "destination": "Phố Thanh Nhàn" | [lat, lon] | node_id, │
│    "weather": "normal" | "rain" | "flood",                 │
│    "flood_areas": [...],                                    │
│    "blocking_geometries": [...]                             │
│  }                                                          │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  API Endpoint (fast_routing.py)                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Step 1: Resolve Origin & Destination                 │  │
│  │                                                       │  │
│  │ Input Type Detection:                                │  │
│  │ - int → Node ID (direct)                             │  │
│  │ - [lat, lon] → KD-Tree snap                          │  │
│  │ - str → FTS5 search → Node ID or Coords              │  │
│  └──────────────────────────────────────────────────────┘  │
│                            │                                 │
│                            ▼                                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Step 2: Process Geometries                           │  │
│  │                                                       │  │
│  │ For each geometry (flood/block):                     │  │
│  │ 1. Convert GeoJSON → Shapely geometry                │  │
│  │ 2. STRtree.query(geometry) → candidate edges         │  │
│  │ 3. Check edge.intersects(geometry) → affected edges  │  │
│  │ 4. Build blocked_edges Set & penalty_map Dict        │  │
│  └──────────────────────────────────────────────────────┘  │
│                            │                                 │
│                            ▼                                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Step 3: Execute Routing                              │  │
│  │                                                       │  │
│  │ A* Search Algorithm:                                 │  │
│  │ 1. Priority queue (f_score = g_score + heuristic)   │  │
│  │ 2. For each neighbor:                                │  │
│  │    - Check if blocked (O(1) set lookup)             │  │
│  │    - Apply penalty if in penalty_map (O(1))         │  │
│  │    - Calculate weight (weather + highway type)       │  │
│  │ 3. Reconstruct path with geometry                     │  │
│  └──────────────────────────────────────────────────────┘  │
│                            │                                 │
│                            ▼                                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Step 4: Build Response                               │  │
│  │                                                       │  │
│  │ {                                                     │  │
│  │   "success": true,                                    │  │
│  │   "path": [node_id, ...],                             │  │
│  │   "distance": 1234.56,                               │  │
│  │   "duration": 120.5,                                  │  │
│  │   "route": {                                          │  │
│  │     "geometry": [[lon, lat], ...],                    │  │
│  │     "type": "Feature"                                 │  │
│  │   },                                                  │  │
│  │   "stats": {...}                                      │  │
│  │ }                                                     │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Client Response (JSON)                                     │
│  - Route geometry for map visualization                     │
│  - Distance, duration, statistics                          │
└─────────────────────────────────────────────────────────────┘
```

### 3. Graph Building Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│  OSM Data (from Overpass API)                                │
│  - Nodes: {id: {lat, lon, tags}}                            │
│  - Ways: {id: {nodes: [...], tags: {...}}}                  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 1: Filter Valid Ways                                  │
│  - Keep only highways (motorway, trunk, primary, etc.)     │
│  - Filter by highway type tags                             │
│  - Remove invalid geometries                               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 2: Build Raw Graph                                    │
│  - Create GraphNode for each OSM node                       │
│  - Create GraphEdge for each way segment                    │
│  - Handle oneway/reverse_oneway                            │
│  - Store geometry (LineString) for each edge                │
│  Result: ~10,772 nodes, ~22,005 edges                       │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 3: LSCC Filtering (Kosaraju's Algorithm)             │
│  - Find largest strongly connected component                │
│  - Remove isolated islands                                 │
│  Result: ~9,681 nodes (89% of original)                    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 4: Graph Compression                                  │
│  - Merge degree-2 nodes (intermediate nodes)               │
│  - Combine edges while preserving geometry                  │
│  Result: ~4,197 nodes, ~9,630 edges (50%+ reduction)      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 5: Build Spatial Indexes                             │
│  - KD-Tree: Nearest node lookup (O(log N))                 │
│  - STRtree: Spatial queries for flood zones (O(log N))      │
│  Result: Graph ready for routing                            │
└─────────────────────────────────────────────────────────────┘
```

### 4. Hard Barriers Flow (apply_hard_barriers)

```
┌─────────────────────────────────────────────────────────────┐
│  Input: List[LineString] (Forbidden Lines)                  │
│  Example:                                                    │
│  [                                                            │
│    LineString([(105.86, 21.00), (105.87, 21.01)]),          │
│    LineString([(105.88, 21.02), (105.89, 21.03)])          │
│  ]                                                            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  For each Forbidden Line:                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 1. Apply Buffer (1e-6 degrees)                         │  │
│  │    - Handle floating-point precision errors            │  │
│  │    - buffered_line = line.buffer(1e-6)                │  │
│  └──────────────────────────────────────────────────────┘  │
│                            │                                 │
│                            ▼                                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 2. STRtree Query (O(log N))                           │  │
│  │    - candidate_indices = strtree.query(buffered_line)│  │
│  │    - Returns indices of edges with intersecting bbox  │  │
│  └──────────────────────────────────────────────────────┘  │
│                            │                                 │
│                            ▼                                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 3. Precise Intersection Check                          │  │
│  │    For each candidate edge:                           │  │
│  │    - Get edge_line from _edge_geometries[idx]         │  │
│  │    - Check edge_line.intersects(buffered_line)        │  │
│  │    - If true: add (u, v) and (v, u) to blocked_edges │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Output: Set[Tuple[int, int]]                               │
│  - Blocked edges (both directions)                          │
│  - Ready to pass to astar_search(blocked_edges=...)        │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔄 Workflow

### Development Workflow

1. **Setup Environment**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run Development Server**
   ```bash
   uvicorn main:app --reload
   ```

3. **Access Services**
   - Frontend: `http://localhost:8000`
   - API Docs: `http://localhost:8000/docs`
   - Health Check: `http://localhost:8000/health`

### Testing Workflow

1. **Run Unit Tests**
   ```bash
   python test_hard_barriers.py
   ```

2. **Test API Endpoints**
   - Use Swagger UI at `/docs`
   - Or use curl/Postman

3. **Test Frontend**
   - Open browser at `http://localhost:8000`
   - Draw flood zones, block roads, find routes

### Deployment Workflow

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run Production Server**
   ```bash
   # Single worker (development)
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   
   # Multiple workers (production)
   uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
   ```

3. **Check Health**
   ```bash
   curl http://localhost:8000/health
   ```

4. **View Logs**
   - Logs are written to `logs/` directory
   - Console output shows service initialization and API requests

### Data Update Workflow

1. **Clear Cache** (if needed)
   ```bash
   rm -rf cache/*.json
   ```

2. **Restart Service**
   - Service will fetch fresh data from Overpass API
   - Graph will be rebuilt

---

## 📊 Project Details

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend Layer                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  static/index.html (Leaflet + Vanilla JS)            │  │
│  │  - Interactive map                                    │  │
│  │  - Draw flood zones (polygon/circle)                 │  │
│  │  - Block roads (select 2 points)                      │  │
│  │  - Route visualization                                │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ HTTP/REST
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                        API Layer                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  src/app/api/fast_routing.py                         │  │
│  │  - POST /route (unified routing)                     │  │
│  │  - GET /suggest (autocomplete)                       │  │
│  │  - GET /info (service stats)                         │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Service Layer                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  FastRoutingService                                   │  │
│  │  - find_route()                                       │  │
│  │  - find_route_by_node_ids()                          │  │
│  │  - search_address()                                   │  │
│  │  - apply_hard_barriers()                             │  │
│  │  - find_affected_edges_fast()                        │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Core Services                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Graph Builder│  │ Pathfinding  │  │ Geocoding   │      │
│  │              │  │              │  │             │      │
│  │ - OSM Parse  │  │ - A* Search  │  │ - FTS5 DB   │      │
│  │ - LSCC Filter│  │ - Geometry   │  │ - Fuzzy Match│      │
│  │ - Compress   │  │ - Weighting  │  │ - Address   │      │
│  │ - KD-Tree    │  │ - Blocking   │  │   Search    │      │
│  │ - STRtree    │  │              │  │             │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Data Layer                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ Overpass API  │  │ SQLite Cache  │  │ Geocoding DB │    │
│  │              │  │              │  │             │    │
│  │ - OSM Data   │  │ - JSON Cache │  │ - FTS5 Index │    │
│  │ - BBOX Query │  │ - Graph Cache │  │ - Addresses  │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

#### 1. Graph Builder (`src/services/graph_builder.py`)
- **Purpose**: Convert OSM data to optimized routing graph
- **Key Functions**:
  - `filter_valid_ways()`: Filter highways from OSM
  - `build_raw_graph()`: Create initial graph structure
  - `find_largest_scc()`: Find largest strongly connected component
  - `compress_graph()`: Merge degree-2 nodes
  - `build_kdtree()`: Build KD-Tree for nearest node lookup
  - `build_strtree()`: Build STRtree for spatial queries

#### 2. Pathfinding Service (`src/services/fast_pathfinding_service.py`)
- **Purpose**: Core routing logic
- **Key Functions**:
  - `astar_search()`: One-directional A* algorithm
  - `apply_hard_barriers()`: Block edges intersecting forbidden lines
  - `find_affected_edges_fast()`: Find edges affected by flood/block zones
  - `get_edges_from_path()`: Extract edges from a path

#### 3. Geocoding Service (`src/services/local_geocoding_service.py`)
- **Purpose**: Local address search without external APIs
- **Key Features**:
  - SQLite FTS5 full-text search
  - Fuzzy matching with RapidFuzz
  - Address extraction from OSM tags

#### 4. Overpass Service (`src/services/overpass_service.py`)
- **Purpose**: Fetch OSM data from Overpass API
- **Key Features**:
  - Intelligent caching
  - BBOX-based queries
  - OSM JSON parsing

#### 5. API Layer (`src/app/api/fast_routing.py`)
- **Purpose**: REST API endpoints
- **Key Endpoints**:
  - `POST /route`: Unified routing (accepts node_id, coords, or address)
  - `GET /suggest`: Address autocomplete
  - `GET /info`: Service information

### Performance Characteristics

#### Graph Building
- **Time**: ~4-5 seconds (one-time cost)
- **Memory**: ~50-100 MB (compressed graph)
- **Size Reduction**: 50%+ with compression

#### Routing
- **Time**: < 5ms for complex routes
- **Spatial Query**: O(log N) with STRtree
- **Nearest Node**: O(log N) with KD-Tree

#### Geocoding
- **Time**: < 1ms for FTS5 search
- **Database**: In-memory SQLite
- **Addresses**: ~1,700 indexed addresses

### Data Structures

#### LightGraph
```python
@dataclass
class LightGraph:
    nodes: Dict[int, GraphNode]           # Node lookup
    adjacency: Dict[int, List[Tuple[int, GraphEdge]]]  # Forward edges
    reverse_adjacency: Dict[int, List[Tuple[int, GraphEdge]]]  # Reverse edges
    _kdtree: KDTree                       # Nearest node lookup
    _strtree: STRtree                     # Spatial queries
    _edge_geometries: List[LineString]    # Edge geometries
    _edge_keys: List[Tuple[int, int]]     # Edge keys (u, v)
```

#### GraphEdge
```python
@dataclass
class GraphEdge:
    from_node: int
    to_node: int
    way_id: int
    length: float
    highway_type: str
    name: str
    speed: float
    c_highway: float
    geometry: List[Tuple[float, float]]  # LineString coordinates
```

### Weight System

#### Highway Coefficients (C_HIGHWAY)
- `motorway`: 0.8
- `trunk`: 0.85
- `primary`: 0.9
- `secondary`: 1.0
- `tertiary`: 1.1
- `residential`: 1.2

#### Weather Context (C_CONTEXT)
- **Normal**: All coefficients = 1.0
- **Rain**: Increased penalties for lower-tier roads
  - `secondary`: 1.5x
  - `tertiary`: 2.0x
- **Flood**: Higher penalties
  - `secondary`: 2.0x
  - `tertiary`: 3.0x

### Spatial Indexing

#### KD-Tree
- **Purpose**: Nearest node lookup
- **Complexity**: O(log N) query, O(N log N) build
- **Usage**: Snap coordinates to nearest graph node

#### STRtree
- **Purpose**: Spatial queries for flood zones and barriers
- **Complexity**: O(log N) query, O(N log N) build
- **Usage**: Find edges intersecting with polygons/lines

### Caching Strategy

1. **Overpass API Cache**
   - Location: `cache/` directory
   - Format: JSON files
   - Key: BBOX hash
   - TTL: Manual (delete to refresh)

2. **Graph Cache**
   - In-memory after first load
   - Persists for application lifetime

3. **Geocoding Database**
   - SQLite in-memory
   - Built from OSM data at startup

### Error Handling

- **Graph Loading**: Returns `None` if OSM fetch fails
- **Routing**: Returns `{"error": "..."}` for invalid requests
- **Geocoding**: Returns empty list if no matches
- **API**: HTTP exceptions with status codes

### Security Considerations

- **CORS**: Enabled for all origins (development)
- **Input Validation**: Pydantic models for request validation
- **SQL Injection**: Parameterized queries in geocoding
- **Rate Limiting**: Not implemented (consider for production)

---

## 📝 Notes

- System optimized for Vietnamese urban areas (Hanoi)
- Graph compression reduces size by 50%+ with minimal accuracy loss
- All coordinates use WGS84 (lat/lon) format
- One-directional A* chosen over bidirectional for geometry accuracy
- Hard barriers use buffer tolerance (1e-6 degrees) for floating-point precision

---

## 🔗 Related Files

- `README.md`: User-facing documentation
- `requirements.txt`: Python dependencies
- `main.py`: FastAPI application entry point
- `test_hard_barriers.py`: Test file for hard barriers functionality

