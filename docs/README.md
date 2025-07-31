# SpaceX Launch Tracker

A full-stack application that provides up-to-date SpaceX launch information without relying on third-party APIs.

## Project Structure

```
spacex-launch-tracker/
├── src/                    # Python backend source code
├── tests/                  # Test files
├── docs/                   # Documentation
├── scripts/                # Database and utility scripts
├── venv/                   # Python virtual environment
├── docker-compose.yml      # Docker services configuration
├── Dockerfile.backend      # Backend container configuration
├── Dockerfile.frontend     # Frontend container configuration
├── requirements.txt        # Python dependencies
└── .gitignore             # Git ignore rules
```

## Development Setup

### Prerequisites
- Python 3.11+
- Docker and Docker Compose
- Node.js 18+ (for frontend)

### Local Development

1. **Clone and setup Python environment:**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   playwright install
   ```

2. **Start services with Docker:**
   ```bash
   docker-compose up -d postgres redis
   ```

3. **Run backend locally:**
   ```bash
   uvicorn src.main:app --reload
   ```

### Docker Development

Start all services:
```bash
docker-compose up --build
```

Services will be available at:
- Backend API: http://localhost:8000
- Frontend: http://localhost:3000
- PostgreSQL: localhost:5432
- Redis: localhost:6379

## Features (Planned)

- Ethical web scraping from multiple sources
- Real-time launch countdown timers
- Historical launch data browsing
- Search and filtering capabilities
- Admin dashboard for monitoring
- Automated data refresh every 6 hours
- Fault-tolerant operation with caching

## Technology Stack

- **Backend**: FastAPI, SQLAlchemy, Celery
- **Frontend**: Next.js, TypeScript
- **Database**: PostgreSQL
- **Cache/Broker**: Redis
- **Scraping**: Playwright, BeautifulSoup4
- **Deployment**: Docker, Docker Compose