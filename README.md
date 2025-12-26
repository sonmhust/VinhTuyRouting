# Map Routing Overpass Turbo

A high-performance routing system with flood zone avoidance, optimized for Vietnamese urban areas. Features one-directional A* pathfinding, spatial indexing (KD-Tree, STRtree), local geocoding, and dynamic weight adjustments for weather conditions. Enhanced with beautiful Tết (Lunar New Year) theme UI.

**Key Features:**
- ⚡ Fast routing: < 5ms for complex routes
- 🗺️ Flood zone avoidance with STRtree spatial queries
- 📍 Local geocoding with SQLite FTS5
- 🎯 Graph compression: 50%+ size reduction
- 🌧️ Dynamic weights for normal/rain/flood conditions
- 🎨 Beautiful Tết theme with Lottie animations

## 🌟 Features

### Core Functionality
- **Smart Routing**: One-directional A* pathfinding with dynamic weight adjustments
- **Flood Zone Avoidance**: Automatic route adjustment to avoid flood areas using STRtree spatial queries
- **Geocoding Services**: Local geocoding with SQLite FTS5, convert addresses to coordinates
- **Interactive Map**: Leaflet-based web interface with real-time route visualization
- **Dynamic Constraints**: Support for flood areas, blocked zones, and weather conditions
- **Graph Compression**: 50%+ size reduction by merging degree-2 nodes

### UI/UX Features
- **Tết Theme**: Beautiful Lunar New Year theme with festive decorations
- **Lottie Animations**: Cherry blossom, fireworks, and coin animations
- **Falling Petals**: Animated flower petals falling across the interface
- **Golden Route Visualization**: Green route lines with shimmer effects
- **Responsive Design**: Mobile-friendly interface

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
├── main.py                    # FastAPI application entry point
├── requirements.txt          # Python dependencies
├── README.md                 # Project documentation
├── STRUCTURE.md              # Project structure details
├── workflow.md               # Technical workflow documentation
│
├── src/                      # Source code
│   ├── app/                  # API endpoints
│   │   └── api/
│   │       ├── fast_routing.py    # Main routing API
│   │       └── flood_zones.py     # Flood zone API
│   │
│   ├── services/             # Core services
│   │   ├── fast_pathfinding_service.py  # A* routing
│   │   ├── graph_builder.py             # Graph construction
│   │   ├── overpass_service.py          # OSM data fetching
│   │   ├── local_geocoding_service.py   # Address search
│   │   ├── flood_zone_service.py         # Flood zone management
│   │   └── cache/                        # Service cache
│   │
│   └── frontend/             # Frontend cache
│       └── cache/
│
├── static/                   # Static assets
│   ├── css/
│   │   └── tet-theme.css    # Tết theme stylesheet
│   └── js/
│       └── tet-theme.js     # Tết theme JavaScript
│
├── templates/                # HTML templates
│   └── index.html           # Main frontend page
│
├── Components/              # Lottie animation files
│   ├── Cherry Blossom.json
│   ├── Blossom.json
│   ├── Coin.json
│   └── Fireworks.json
│
└── logs/                    # Application logs
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- pip package manager

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/sonmhust/VinhTuyRouting.git
   cd Map-Routing-Overpass-Turbo
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the FastAPI server**

   **Option 1: Direct Python execution (Development)**
   ```bash
   python main.py
   ```

   **Option 2: Uvicorn CLI (Development with auto-reload)**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

   **Option 3: Production (Multi-worker)**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
   ```

4. **Access the application**
   - Frontend: `http://localhost:8000`
   - API Docs: `http://localhost:8000/docs`
   - Health Check: `http://localhost:8000/health`

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
- **Area**: Phường Vĩnh Tuy, Hai Bà Trưng, Hà Nội (configurable in `main.py`)

### Flood Zone Management
- **Storage**: SQLite database (`src/services/cache/flood_zones.db`)
- **Types**: Polygon, Circle, MultiPolygon
- **Query**: STRtree spatial queries for fast edge detection

### Caching
- **Overpass Cache**: Cached OSM data responses in JSON format (`src/services/cache/overpass/`)
- **Graph Cache**: Pre-computed graph structures for faster loading
- **Geocoding**: In-memory SQLite FTS5 database

### Tết Theme Configuration
- **CSS**: `static/css/tet-theme.css`
- **JavaScript**: `static/js/tet-theme.js`
- **Animations**: Lottie JSON files in `Components/`
- Theme automatically loads on page initialization

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

### Performance Metrics
- **Graph Loading**: ~4-5 seconds (one-time cost at startup)
- **Routing Time**: < 5ms for complex routes
- **Geocoding**: < 1ms for FTS5 search
- **Memory Usage**: ~50-100 MB (compressed graph)

## 📝 Notes

- System optimized for Vietnamese urban areas, particularly Hanoi
- Graph loading is one-time cost (~4s), routing performance is < 5ms
- Compression reduces graph size by 50%+ with minimal impact on accuracy
- All coordinates use WGS84 (lat/lon) format
- Tết theme can be disabled by removing theme CSS/JS includes

## 🐛 Troubleshooting

### Port 8000 Already in Use
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:8000 | xargs kill -9
```

### Service Not Starting
- Check Python version: `python --version` (requires 3.11+)
- Verify dependencies: `pip install -r requirements.txt`
- Check logs in `logs/` directory

## 📄 License

This project is open source and available under the MIT License.

## 🙏 Acknowledgments

- OpenStreetMap for map data
- Leaflet.js for map visualization
- FastAPI for the web framework
- Lottie for animations
