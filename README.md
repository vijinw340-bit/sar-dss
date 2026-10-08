# 🛰️ SAR-DSS — Search and Rescue Decision Support System

**Organization:** Airports Authority of India (AAI)

**Project:** A software tool to aid Search and Rescue (SAR) operations by calculating and plotting the probable search area of a missing aircraft from its **Last Known Position (LKP)**.

SAR-DSS is a modern GIS-based web application that lets SAR officers create a mission, input the last known telemetry of a missing aircraft, and instantly compute:

- Possible aircraft position
- Search radius & search area
- Desired area coverage
- Probability zones (High / Medium / Low)
- Recommended search pattern
- Search sectors with aircraft assignment
- Risk analysis and search-priority ranking

Everything is visualized on an interactive Leaflet map with aviation-grade UI.

---

## ✨ Features

### Authentication
- JWT-based login with password hashing (bcrypt)
- Role-based access: `admin` and `sar_officer`
- Role-guarded APIs and UI routes

### Dashboard
- Total missions, active missions, completed missions, aircraft missing today
- Live map preview of active missions
- Recent activity feed, weather widget, notifications

### Mission Management
- Full mission CRUD (create, update, pause, complete, delete)
- Mission timeline & history
- Mission search + filter (by status, aircraft, date range)
- CSV / PDF export, email delivery of reports

### Search-Area Calculation Engine
- `Distance = Ground Speed × Elapsed Time`
- Search radius = distance + wind correction + navigation uncertainty + pilot deviation
- Weather severity expands uncertainty
- Circular and polygonal search regions (GeoJSON)

### Probability Engine
- Divides search area into High / Medium / Low probability zones
- Uses heading, wind, elapsed time, speed and terrain data
- Red / Orange / Yellow heat visualization

### Search Pattern Module
- Expanding Square, Sector Search, Parallel Track, Creeping Line, Track Line
- Rule-based automatic recommendation engine
- Patterns rendered as waypoint polylines on the map

### Sector Division
- Automatic split of search area into Sectors A, B, C, D…
- Color-coded sectors, aircraft assignment per sector

### GIS Map
- LKP marker, aircraft icon, search radius circle, search polygon
- Probability heat zones, nearby airports, water bodies, terrain
- OSM base layers (street / satellite / terrain / dark) with layer switcher
- Grid coordinates, zoom controls, dark mode

### Reports
- Professional PDF (ReportLab): mission details, map image, search radius,
  probability map, search pattern, weather, wind, coverage, sector details,
  officer name, generation time

### Bonus Intelligence ("AI") Features
- Crash-location prediction (wind & heading drift modelling)
- Weather impact prediction
- Automatic search-priority ranking across missions
- Mission risk analysis
- Smart search-pattern recommendations
- Search-area evolution simulation over time

---

## 🧰 Tech Stack

| Layer     | Technology |
|-----------|-----------|
| Frontend  | React 18, TypeScript, Vite, Tailwind CSS, shadcn-style UI, React Router, Framer Motion, Chart.js, Leaflet, React-Leaflet, OSM |
| Backend   | Python 3.12+, FastAPI, SQLAlchemy 2.0, Pydantic v2, Uvicorn |
| Database  | PostgreSQL 15+ with PostGIS |
| Auth      | JWT (PyJWT), bcrypt (passlib) |
| PDF       | ReportLab + Matplotlib |
| Deploy    | Docker Compose, Nginx (frontend) |

---

## 📁 Project Structure

```
├── client/                      # React + TypeScript frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── charts/          # Chart.js charts
│   │   │   ├── layout/          # Navbar, Sidebar, Shell
│   │   │   ├── map/             # Leaflet GIS components
│   │   │   ├── mission/         # Mission form, detail widgets
│   │   │   └── ui/              # shadcn-style primitives
│   │   ├── context/             # Auth + Theme providers
│   │   ├── lib/                 # api client, utils, hooks
│   │   ├── pages/               # Route pages
│   │   ├── types/               # TypeScript domain types
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── Dockerfile
│   └── nginx.conf
│
└── server/                      # FastAPI backend
    ├── app/
    │   ├── api/                 # Routers (auth, missions, reports...)
    │   ├── core/                # config, database, security
    │   ├── models/              # SQLAlchemy models
    │   ├── schemas/             # Pydantic schemas
    │   ├── services/            # GIS, calculation, probability engines
    │   ├── sql/                 # init.sql, seed.sql
    │   └── main.py
    ├── requirements.txt
    └── Dockerfile
```

---

## 🚀 Quick Start with Docker (recommended)

Prerequisites: Docker + Docker Compose.

```bash
cp .env.example .env
docker compose up --build -d
```

Then open:

- Frontend: http://localhost:5173
- API docs:  http://localhost:8000/docs
- Health:    http://localhost:8000/api/v1/health

The first startup bootstraps an admin account (defaults from `.env`):
- **Username:** `admin`
- **Password:** `Admin@123`

> ⚠️ Change these credentials before any production deployment.

---

## 🧑‍💻 Local Development

### 1. Database (PostGIS)

```bash
docker compose up -d db
# OR use a local PostGIS instance and set DATABASE_URL accordingly
```

### 2. Backend

```bash
cd server
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate        # Linux/macOS

pip install -r requirements.txt
cp ../.env.example ../.env

# create schema + tables + seed
uvicorn app.main:app --reload --port 8000
```

Tables are created automatically by SQLAlchemy on startup. You can also run the raw PostGIS SQL:

```bash
psql -U sar -d sar_dss -f app/sql/init.sql
psql -U sar -d sar_dss -f app/sql/seed.sql
```

### 3. Frontend

```bash
cd client
npm install
npm run dev
```

Frontend runs at http://localhost:5173 and proxies `/api` to `http://localhost:8000`.

---

## 🔌 API Overview

Base URL: `/api/v1`

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| POST | `/auth/register` | Create user | public |
| POST | `/auth/login` | Login → JWT | public |
| GET | `/auth/me` | Current user | user |
| GET | `/dashboard/stats` | Dashboard stats | user |
| GET | `/dashboard/activities` | Recent activity | user |
| GET | `/dashboard/missions-overview` | Mission data for map | user |
| GET/POST | `/missions` | List / create mission | user |
| GET/PATCH/DELETE | `/missions/{id}` | Mission CRUD | user / admin(delete) |
| POST | `/missions/{id}/calculate` | Re-run GIS calculations | user |
| GET | `/missions/{id}/search-area` | Search area GeoJSON | user |
| GET | `/missions/{id}/pattern` | Recommended pattern | user |
| GET | `/missions/{id}/probability` | Probability zones | user |
| GET | `/missions/{id}/sectors` | Sectors | user |
| PATCH | `/sectors/{id}` | Assign aircraft to sector | user |
| GET | `/missions/{id}/analysis` | AI risk analysis | user |
| GET | `/missions/{id}/simulation?hours=N` | Search-area simulation | user |
| POST | `/missions/{id}/reports` | Generate PDF report | user |
| GET | `/missions/{id}/reports` | List reports | user |
| POST | `/missions/{id}/reports/{rid}/email` | Email a report | user |
| GET | `/missions/export/csv` | Export all missions CSV | user |
| GET | `/missions/{id}/export/csv` | Export single mission CSV | user |
| GET | `/aircraft` / POST | Aircraft catalog | user / admin |
| GET | `/weather/live?lat&lon` | Live weather (Open-Meteo) | user |
| POST | `/weather/snapshot` | Store weather snapshot | user |
| GET | `/notifications` | Notifications | user |
| GET | `/users` | List users | admin |
| PATCH | `/users/{id}` | Update user / role | admin |

Full interactive docs at `/docs` (Swagger UI).

---

## 🧮 Calculation Methodology

### Elapsed time
```
elapsed_hours = now − time_of_last_contact
```

### Distance
```
distance_nm = ground_speed_kts × elapsed_hours
```

### Search radius
```
radius_nm =
    distance_nm
  + wind_correction      (drift component, scaled by wind speed)
  + navigation_uncertainty (5% of distance + 2 nm base)
  + pilot_deviation        (10% of distance)
```
Severe weather (`weather_impact ≥ 0.8`) expands all uncertainty terms. Minimum radius is clamped to 5 nm.

### Desired area coverage
The software provides the area to sweep per standard SAR planning (track spacing derived from pattern type), output as `desired_coverage_pct` = planned swept area / total search area.

### Probability zones
A bivariate-normal style distribution centred on the *predicted position*
(predicted = LKP offset by heading track and wind drift):
- **High** (red)    — inner ~35% radius band   (~55% cumulative probability)
- **Medium** (orange) — middle ~35% radius band (~30%)
- **Low** (yellow)   — outer ~30% radius band    (~15%)

### Pattern recommendation rules
| Condition | Recommended pattern |
|---|---|
| High LKP accuracy | Expanding Square |
| Route known / tracked | Creeping Line |
| Very large search area | Parallel Track |
| Low confidence / uncertain | Sector Search |
| Well-defined flight path | Track Line |

### Sectors
The search circle is divided into `N` equal angular sectors (default 4) labelled **A, B, C, D**, each with its own color and assignable search aircraft.

---

## 🛡️ Security

- JWT access tokens with configurable expiry
- bcrypt password hashing (passlib)
- Role-based authorization (admin vs sar_officer)
- Pydantic input validation on every endpoint
- SQLAlchemy parameterized queries → SQL-injection safe
- Server-rendered (FastAPI) data, React escapes output → XSS-safe
- CORS restricted to configured origins
- Environment-driven secrets via `.env` (never committed)

---

## 🌐 Outbound Privacy (VPN / Proxy Egress — no Tor)

SAR-DSS makes outbound calls for **live weather** (Open-Meteo), **static map
images** (PDF reports) and **browser map tiles** (Leaflet). By default those
requests leave from the server's public IP. The backend routes every one of
them through configurable VPN/proxy infrastructure:

| Mode | Behaviour |
|---|---|
| `direct` | No proxy — unchanged behaviour. (Transparent to OS-level VPNs like WireGuard/OpenVPN, which auto-route everything anyway.) |
| `rotate` | Round-robin over `OUTBOUND_PROXIES` — a different exit node per request. |
| `random` | A random pool member per request. |
| `failover` | Stick to the last working exit; fall through the pool on errors. |
| `chain` | Multi-hop SOCKS/HTTP tunnelling through `OUTBOUND_PROXY_CHAIN` nodes — a miniature private relay network. |

Both `socks5://`, `socks4://` and `http://` (CONNECT) proxy types are
supported; HTTPS targets are still TLS-authenticated end-to-end *after* the
final hop (the tunnel is a raw TCP stream, so the proxy can never see your
keys — exactly how a real VPN behaves).

```bash
# .env
OUTBOUND_MODE=rotate
OUTBOUND_PROXIES=socks5://user:pass@vpn1.example:1080,socks5://vpn2.example:1080

# or a two-hop private relay
OUTBOUND_MODE=chain
OUTBOUND_PROXY_CHAIN=socks5://nodeA:1080 -> socks5://nodeB:1080
```

Browser map tiles are relayed through `/api/v1/tiles/<provider>/...` so the
**operator's client IP never touches the upstream tile server** either — all
map traffic exits via the backend egress above. Runtime status:

```bash
curl http://localhost:8000/api/v1/health
```

Implementation: `server/app/services/netroute.py` — see also
`server/app/api/routers/tiles.py`, `server/app/services/weather.py` and
`server/app/services/report_pdf.py`.

---

## 🧪 Testing

### Backend
```bash
cd server
pip install -r requirements.txt
python -m pytest tests/ -v
```
Tests cover the GIS calculation engine, probability engine, pattern generation, sector division, and the authentication flow (with an in-memory SQLite fixture for auth tests).

### Frontend
```bash
cd client
npm run lint
npm run build        # type-checks + production build
```

---

## 🌍 Deployment

### Production with Docker Compose
```bash
cp .env.example .env
# set SECRET_KEY, admin creds, CORS origins for your domain
docker compose up --build -d
docker compose ps
```

The frontend container serves the optimized static build via Nginx and proxies `/api` to the backend service.

### Manual deployment
1. Run PostgreSQL/PostGIS (managed or local).
2. Deploy the FastAPI app with a production ASGI server:
   ```bash
   cd server
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
   ```
3. Build and serve the frontend:
   ```bash
   cd client
   npm run build
   # serve dist/ with any static server / CDN, point VITE_API_URL to the backend
   ```

### Backups
The PostGIS volume (`db_data`) contains all mission data. Back it up with `pg_dump`.

---

## 📝 Environment Variables

See [`.env.example`](./.env.example) for the full list with comments. Key ones:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLAlchemy connection string |
| `SECRET_KEY` | JWT signing secret |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime |
| `CORS_ORIGINS` | Allowed frontend origins |
| `ADMIN_USERNAME/EMAIL/PASSWORD` | Bootstrap admin |
| `VITE_API_URL` | Backend base URL for the client |

---

## 🗺️ Database Schema

Tables: `users`, `aircraft`, `missions`, `search_areas`, `search_patterns`, `probability_zones`, `sectors`, `reports`, `weather_snapshots`, `activity_logs`.

All spatial data is stored both as standard float coordinates (for portability) and as PostGIS `geometry(Point/LineString/Polygon, 4326)` columns (for advanced spatial queries). See `server/app/sql/init.sql`.

---

## 📄 License

Internal project scaffold for the Airports Authority of India. Provided for demonstration and deployment within AAI's SAR operations environment.

---

Made for safer skies. ✈️
