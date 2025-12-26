# Project Structure

## Cấu trúc thư mục

```
.
├── main.py                        # FastAPI application entry point
├── requirements.txt               # Python dependencies
├── README.md                      # Project documentation
├── STRUCTURE.md                   # This file - project structure
├── workflow.md                    # Technical workflow documentation
├── .gitignore                     # Git ignore rules
│
├── src/                           # Source code
│   ├── __init__.py
│   ├── app/                       # API endpoints
│   │   ├── __init__.py
│   │   └── api/
│   │       ├── __init__.py
│   │       ├── fast_routing.py    # Main routing API endpoints
│   │       └── flood_zones.py    # Flood zone API endpoints
│   │
│   ├── services/                  # Core business logic services
│   │   ├── __init__.py
│   │   ├── fast_pathfinding_service.py    # A* pathfinding with flood zones
│   │   ├── graph_builder.py               # OSM graph construction
│   │   ├── overpass_service.py             # Overpass API client
│   │   ├── local_geocoding_service.py     # SQLite FTS5 geocoding
│   │   ├── lite_geocoding_service.py      # Lightweight geocoding
│   │   ├── flood_zone_service.py          # Flood zone management
│   │   ├── astar_with_virtual_node.py     # A* with virtual nodes
│   │   └── cache/                         # Service cache directory
│   │       ├── overpass/                  # Overpass API cache
│   │       └── flood_zones.db             # Flood zones database
│   │
│   └── frontend/                  # Frontend cache
│       ├── __init__.py
│       └── cache/                 # Frontend cache files
│
├── static/                        # Static assets
│   ├── css/
│   │   └── tet-theme.css         # Tết theme stylesheet
│   └── js/
│       └── tet-theme.js          # Tết theme JavaScript
│
├── templates/                     # HTML templates
│   └── index.html                 # Main frontend page
│
├── Components/                    # Lottie animation files
│   ├── Cherry Blossom.json       # Cherry blossom animation
│   ├── Blossom.json              # Blossom animation
│   ├── Coin.json                 # Coin animation
│   └── Fireworks.json            # Fireworks animation
│
└── logs/                         # Application logs directory
```

## Key Components

### Backend (`main.py`)
- FastAPI application entry point
- Lifespan events for service initialization
- Static file mounting (`/static`, `/Components`)
- Template serving (`/templates/index.html`)
- CORS middleware configuration

### API Endpoints (`src/app/api/`)
- **fast_routing.py**: Main routing endpoints
  - `POST /api/v1/routing/route` - Unified routing (int | [lat,lon] | str)
  - `GET /api/v1/routing/suggest` - Address autocomplete
  - `GET /api/v1/routing/info` - Service information
  
- **flood_zones.py**: Flood zone management endpoints

### Services (`src/services/`)
- **fast_pathfinding_service.py**: Core routing service with A* algorithm
- **graph_builder.py**: Builds graph from OSM data with compression and spatial indexing
- **overpass_service.py**: Fetches OSM data from Overpass API with caching
- **local_geocoding_service.py**: SQLite FTS5 full-text search for addresses
- **flood_zone_service.py**: Manages flood zone geometries

### Frontend (`templates/index.html`)
- Leaflet.js map integration
- Tết theme with animations (Lottie)
- Interactive routing interface
- Address search and autocomplete

## Cách chạy

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run with auto-reload
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Production
```bash
# Run without reload
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Health Check
```bash
curl http://localhost:8000/health
```

## Imports

Tất cả imports trong `main.py` sử dụng absolute imports từ `src.`:
```python
from src.services.fast_pathfinding_service import FastRoutingService
from src.app.api.fast_routing import router as routing_router
```

## Static Files & Routes

- **CSS**: `/static/css/tet-theme.css`
- **JS**: `/static/js/tet-theme.js`
- **Lottie Animations**: `/Components/*.json`
- **Frontend**: `/` (serves `templates/index.html`)

## Cache Directories

- `src/services/cache/` - Service-level cache (Overpass API responses, flood zones)
- `src/frontend/cache/` - Frontend cache files
- `logs/` - Application logs

## Environment

- Python 3.11+
- FastAPI 0.104.1
- Uvicorn 0.24.0
- See `requirements.txt` for full dependency list
