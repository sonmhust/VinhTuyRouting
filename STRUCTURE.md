# Project Structure

## Cấu trúc thư mục

```
.
├── src/
│   ├── main.py                 # File khởi tạo FastAPI
│   ├── app/                    # API endpoints
│   │   └── api/
│   │       ├── fast_routing.py
│   │       └── flood_zones.py
│   └── services/               # Core services
│       ├── fast_pathfinding_service.py
│       ├── graph_builder.py
│       ├── overpass_service.py
│       ├── local_geocoding_service.py
│       └── ...
├── static/                     # Tài nguyên tĩnh
│   ├── css/                    # Stylesheet
│   └── js/                     # JavaScript files
├── templates/                  # HTML templates
│   └── index.html              # File HTML chính
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Thay đổi so với cấu trúc cũ

### Trước:
- `main.py` ở root
- `static/index.html` chứa cả HTML

### Sau:
- `src/main.py` - FastAPI app entry point
- `templates/index.html` - HTML template
- `static/css/` và `static/js/` - Tách riêng CSS và JS

## Cách chạy

### Development
```bash
uvicorn src.main:app --reload
```

### Production (Docker)
```bash
docker-compose up
```

## Imports

Tất cả imports trong `src/main.py` sử dụng absolute imports từ `src.`:
```python
from src.services.fast_pathfinding_service import FastRoutingService
from src.app.api.fast_routing import router as routing_router
```

## Static Files

- CSS: `/static/css/`
- JS: `/static/js/`
- Templates: `/templates/index.html` (served at `/`)

