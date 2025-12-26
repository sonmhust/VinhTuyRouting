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
- **Interactive Map**: Leaflet-based web interface with real-time route visualization
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
│   ├── frontend/               # Frontend utilities (deprecated)
│   └── services/               # Core services
│       ├── graph_builder.py   # Graph construction (OSM → Graph)
│       ├── fast_pathfinding_service.py  # A* routing
│       ├── overpass_service.py          # OSM data fetching
│       ├── local_geocoding_service.py   # Address search
│       ├── flood_zone_service.py       # Flood zone management
├── static/                     # Frontend (Leaflet HTML)
│   └── index.html             # Main frontend interface
├── main.py                    # FastAPI application entry point
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

4. **Access the frontend**
   - Open browser and navigate to: `http://localhost:8000`
   - The Leaflet-based frontend will be served automatically

5. **Run with Docker Compose (optional)**
   ```bash
   docker-compose up --build
   ```

## 📡 API Documentation

### Base URL
- FastAPI: `http://localhost:8000`
- Frontend: `http://localhost:8000` (served by FastAPI)

### API Endpoints

#### Routing Services
- **POST** `/api/v1/routing/route`
  - Unified routing endpoint (accepts node_id, coordinates, or address)
  - Request body:
    ```json
    {
      "origin": "Phố Vĩnh Tuy",
      "destination": "Phố Thanh Nhàn",
      "weather": "normal",
      "flood_areas": [],
      "blocking_geometries": []
    }
    ```
  - Input types:
    - `int`: Node ID (fastest)
    - `[lat, lon]`: Coordinates (click map)
    - `str`: Address (manual entry)

- **GET** `/api/v1/routing/suggest?q=<query>&limit=5`
  - Autocomplete address search (local FTS5)
  - Returns list of matching addresses with node_id

- **GET** `/api/v1/routing/info`
  - Service information and statistics

- **GET** `/health`
  - Health check endpoint

### Interactive API Documentation
Visit `http://localhost:8000/docs` for Swagger UI documentation.


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
