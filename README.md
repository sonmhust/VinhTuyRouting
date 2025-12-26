A high-performance routing system with flood zone avoidance, optimized for Vietnamese urban areas. Features one-directional A* pathfinding, spatial indexing (KD-Tree, STRtree), local geocoding, and dynamic weight adjustments for weather conditions.

**Key Features:**
- ⚡ Fast routing: < 5ms for complex routes
- 🗺️ Flood zone avoidance with STRtree spatial queries
- 📍 Local geocoding with SQLite FTS5
- 🎯 Graph compression: 50%+ size reduction
- 🌧️ Dynamic weights for normal/rain/flood conditions

## 🌟 Features

### Core Functionality
- **Smart Routing**: One-directional A* pathfinding with dynamic weight adjustments
- **Flood Zone Avoidance**: Automatic route adjustment to avoid flood areas using STRtree spatial queries
- **Geocoding Services**: Local geocoding with SQLite FTS5, convert addresses to coordinates
- **Interactive Map**: Streamlit-based web interface with real-time route visualization
- **Dynamic Constraints**: Support for flood areas, blocked zones, and weather conditions
- **Graph Compression**: 50%+ size reduction by merging degree-2 nodes

### Technical Features
- **FastAPI Backend**: High-performance REST API with automatic documentation
- **Spatial Indexing**: KD-Tree for nearest node lookup, STRtree for spatial queries
- **Graph Optimization**: LSCC filtering, compression, and efficient data structures
- **Local Geocoding**: SQLite FTS5 with fuzzy matching, no external API required
- **Caching System**: Intelligent caching for Overpass API responses
- **Performance**: < 5ms routing time for complex routes

## 🏗️ Architecture

```
Map-Routing-Overpass-Turbo/
├── src/
│   ├── app/                    # FastAPI application
│   │   └── api/                # API endpoints
│   ├── frontend/               # Streamlit web interface
│   └── services/               # Core services
│       ├── graph_builder.py   # Graph construction (OSM → Graph)
│       ├── fast_pathfinding_service.py  # A* routing
│       ├── overpass_service.py          # OSM data fetching
│       ├── local_geocoding_service.py   # Address search
│       ├── flood_zone_service.py       # Flood zone management
├── docker-compose.yml          # Docker orchestration
├── Dockerfile                  # Container configuration
└── requirements.txt            # Python dependencies
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Docker and Docker Compose (optional)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Map-Routing-Overpass-Turbo
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the FastAPI server**
   ```bash
   uvicorn main:app --reload
   ```

4. **Start the Streamlit frontend (optional)**
   ```bash
   streamlit run src/frontend/app_streamlit.py
   ```

5. **Run with Docker Compose (optional)**
   ```bash
   docker-compose up --build
   ```

## 📡 API Documentation

### Base URL
- FastAPI: `http://localhost:8000`
- Streamlit: `http://localhost:8501`

### API Endpoints

#### Geocoding Services
- **POST** `/api/v1/geocoding/loc-to-coords`
  - Convert address to coordinates
  - Request: `{"address": "119 Lê Thanh Nghị, Hà Nội"}`
  - Response: `{"latitude": 21.0245, "longitude": 105.8412, "address": "..."}`

- **POST** `/api/v1/geocoding/coords-to-loc`
  - Convert coordinates to address
  - Query params: `latitude`, `longitude`

#### Routing Services
- **POST** `/api/v1/routing/find-standard-route`
  - Find optimal route between two addresses
  - Request body:
    ```json
    {
      "start_address": "119 Lê Thanh Nghị, Hà Nội",
      "end_address": "Cầu Vĩnh Tuy, Hà Nội",
      "blocking_geometries": [],
      "flood_areas": [],
      "ban_areas": []
    }
    ```

- **GET** `/health`
  - Health check endpoint

### Interactive API Documentation
Visit `http://localhost:8000/docs` for Swagger UI documentation.

## 🗺️ Web Interface

The Streamlit web interface provides:

### Map Features
- **Interactive Drawing**: Draw flood areas, restricted zones, and one-way roads
- **Route Visualization**: Real-time route display with distance and time estimates
- **Address Search**: Find routes by entering start and end addresses
- **Constraint Management**: Add/remove various types of road constraints

### Interface Tabs
1. **Flood Areas**: Mark areas with increased flood risk (blue overlay)
2. **Restricted Areas**: Mark completely blocked areas (red overlay)
3. **Address Routing**: Find routes between specific addresses

## 🔧 Configuration

### Graph Configuration
- **Data Source**: OpenStreetMap via Overpass API
- **Graph Format**: Custom LightGraph structure with spatial indexing
- **Compression**: Enabled by default (merge degree-2 nodes)

### Flood Zone Management
- **Storage**: SQLite database (`flood_zones.db`)
- **Types**: Polygon, Circle, MultiPolygon
- **Query**: STRtree spatial queries for fast edge detection

### Caching
- **Overpass Cache**: Cached OSM data responses in JSON format
- **Graph Cache**: Pre-computed graph structures for faster loading
- **Geocoding**: In-memory SQLite FTS5 database

### Production Deployment
```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Service Architecture
- **FastAPI**: REST API server (port 8000)
- **Streamlit**: Web interface (port 8501, optional)
- **SQLite**: Local storage for flood zones and geocoding
- **Overpass API**: External service for OSM data

## 📊 Performance

### Benchmark Results

See `BENCHMARK_REPORT.md` for detailed performance metrics.

**Key Performance Indicators:**
- **Routing Speed:** < 5ms for complex routes
- **Graph Compression:** 50%+ size reduction (nodes & edges)
- **Spatial Queries:** O(log N) with STRtree for flood zone detection
- **Geocoding:** < 100ms for address search

### Optimization Features
- **Graph Compression:** Merge degree-2 nodes, 50%+ size reduction
- **Spatial Indexing:** KD-Tree for nearest node (O(log N)), STRtree for spatial queries
- **One-directional A*:** Simplified algorithm, direct geometry construction
- **Graph Caching:** Pre-loaded graph structures from Overpass API
- **Local Geocoding:** SQLite FTS5 with fuzzy matching

### Running Benchmarks

```bash
# Run all benchmarks
python run_benchmark.py

# Analyze execution time breakdown
python analyze_execution_time.py
```

## 🧪 Testing

### Test Files
- `test_flood_areas_impact.py` - Test flood zone avoidance
- `test_routing_performance_flood.py` - Performance benchmarking

### Running Tests
```bash
# Run flood impact test
python test_flood_areas_impact.py

# Run performance test
python test_routing_performance_flood.py
```

## 🔧 Technical Details

### Graph Building Pipeline
1. **Parse & Filter:** Extract valid highways from OSM data
2. **LSCC Filtering:** Keep only largest strongly connected component
3. **Compression:** Merge degree-2 nodes (optional, enabled by default)
4. **Spatial Indexing:** Build KD-Tree and STRtree

### Routing Algorithm
- **Algorithm:** One-directional A* (optimized from bidirectional)
- **Geometry:** Direct construction, no merging required
- **Weight System:** Dynamic weights based on highway type and weather
- **Flood Handling:** Penalty multipliers or edge blocking

### Spatial Data Structures
- **KD-Tree:** Fast nearest node lookup (O(log N))
- **STRtree:** Fast spatial queries for flood zones (O(log N))

## 📝 Notes

- System optimized for Vietnamese urban areas, particularly Hanoi
- Graph loading is one-time cost (~4s), routing performance is < 5ms
- Compression reduces graph size by 50%+ with minimal impact on accuracy
- All coordinates use WGS84 (lat/lon) format
