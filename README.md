# LegalDocTracker

> **Contract Lifecycle Management API** — built with Django REST Framework, PostgreSQL, MongoDB, JWT auth, Docker, and GitHub Actions CI/CD.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Client / API Consumer                       │
└──────────────────────────────┬──────────────────────────────────────┘
                               │  HTTP (REST)
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Django REST Framework                           │
│                                                                     │
│  ┌──────────┐   ┌─────────────┐   ┌──────────────┐                 │
│  │  Views   │──▶│ Serializers │──▶│   Services   │                 │
│  └──────────┘   └─────────────┘   └──────┬───────┘                 │
│       │                                   │                         │
│       │ JWT Auth (SimpleJWT)              │                         │
└───────┼───────────────────────────────────┼─────────────────────────┘
        │                                   │
        ▼                                   ▼
┌──────────────────┐              ┌──────────────────────┐
│   PostgreSQL     │              │       MongoDB        │
│                  │              │                      │
│  Contract        │              │  contract_clauses    │
│  Party           │              │  { contract_id,      │
│  ContractEvent   │              │    clause_number,    │
│                  │              │    clause_text,      │
│  (relational     │              │    clause_type,      │
│   metadata)      │              │    flagged_keywords} │
└──────────────────┘              └──────────────────────┘
```

---

## Quick Start (Docker)

### Prerequisites
- Docker ≥ 24
- Docker Compose ≥ 2.20

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/your-org/LegalDocTracker.git
cd LegalDocTracker

# 2. Create your environment file
cp .env.example .env
# Edit .env and set a real DJANGO_SECRET_KEY

# 3. Bring up all services
docker compose up --build

# 4. Create a superuser (in a separate terminal)
docker compose exec web python manage.py createsuperuser

# 5. Access the API
open http://localhost:8000/api/contracts/

# 6. Access the Admin panel
open http://localhost:8000/admin/
```

---

## Local Development (no Docker)

### Requirements
- Python 3.11+
- PostgreSQL 15+
- MongoDB 7+

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set environment variables
cp .env.example .env
# Fill in DB_HOST, MONGO_URI, DJANGO_SECRET_KEY, etc.

# 4. Run migrations
python manage.py migrate

# 5. Create superuser
python manage.py createsuperuser

# 6. Start dev server
python manage.py runserver
```

---

## API Reference

### Authentication

All endpoints require a valid JWT Bearer token (except `/api/auth/token/`).

```
POST /api/auth/token/          Obtain access + refresh tokens
POST /api/auth/token/refresh/  Refresh access token
POST /api/auth/token/verify/   Verify a token
```

#### Example

```bash
# Obtain token
curl -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}'

# Use token
export TOKEN=<access_token>
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/contracts/
```

---

### Contracts

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/contracts/` | Create a new contract |
| `GET` | `/api/contracts/` | List contracts (with filters) |
| `GET` | `/api/contracts/{id}/` | Contract detail + clause count |
| `PATCH` | `/api/contracts/{id}/status/` | Transition contract status |
| `GET` | `/api/contracts/expiring-soon/` | Contracts expiring within 7 days |
| `POST` | `/api/contracts/{id}/clauses/` | Add clause (MongoDB) |
| `GET` | `/api/contracts/{id}/clauses/` | List clauses (MongoDB) |

#### Create Contract

```bash
curl -X POST http://localhost:8000/api/contracts/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Vendor NDA 2025",
    "parties": [{"name": "Acme Corp"}, {"name": "Beta Ltd"}],
    "expires_at": "2025-12-31T23:59:00Z"
  }'
```

#### List with Filters

```bash
# Filter by status
GET /api/contracts/?status=REVIEW

# Filter by expiry
GET /api/contracts/?expires_before=2025-06-01T00:00:00Z
```

#### Status Update

```bash
curl -X PATCH http://localhost:8000/api/contracts/1/status/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "REVIEW", "notes": "Sent to legal team."}'
```

**Valid status transitions:**

```
DRAFT   → REVIEW, EXPIRED
REVIEW  → SIGNED, DRAFT, EXPIRED
SIGNED  → EXPIRED
EXPIRED → (terminal — no further transitions)
```

#### Add Clause (MongoDB)

```bash
curl -X POST http://localhost:8000/api/contracts/1/clauses/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "clause_number": 1,
    "clause_text": "The vendor shall deliver goods within 30 days.",
    "clause_type": "DELIVERY",
    "flagged_keywords": ["30 days", "deliver"]
  }'
```

---

## Running Tests

```bash
# All tests
pytest contracts/tests/ -v

# With coverage
pytest contracts/tests/ -v --cov=contracts --cov-report=html

# Skip slow tests
pytest contracts/tests/ -v -m "not slow"
```

---

## Project Structure

```
LegalDocTracker/
├── config/
│   ├── settings/
│   │   ├── base.py          # Shared settings (DB, DRF, JWT, logging)
│   │   ├── local.py         # Dev overrides (DEBUG=True, browsable API)
│   │   └── production.py    # Prod hardening (HTTPS, HSTS, Sentry)
│   ├── urls.py              # Root URL config (admin + JWT + API)
│   └── wsgi.py
├── contracts/
│   ├── models.py            # Contract, Party, ContractEvent ORM models
│   ├── serializers.py       # Input/output validation & representation
│   ├── services.py          # Business logic & status transition matrix
│   ├── views.py             # APIView endpoints + custom exception handler
│   ├── admin.py             # Django Admin (badges, inline events)
│   ├── urls.py              # App URL routes
│   └── tests/
│       ├── conftest.py      # Fixtures (users, clients, MongoDB mock)
│       └── test_contracts.py # 17 pytest tests
├── mongo_store/
│   ├── client.py            # Singleton PyMongo client (LRU cached)
│   └── clause_store.py      # Clause document CRUD + index management
├── docker-compose.yml       # PostgreSQL + MongoDB + Django services
├── Dockerfile               # Multi-stage build (builder + runtime)
├── pytest.ini               # pytest configuration
├── requirements.txt
└── .github/
    └── workflows/
        └── ci.yml           # lint → test → docker build pipeline
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DJANGO_SECRET_KEY` | — | **Required.** Django secret key |
| `DJANGO_SETTINGS_MODULE` | `config.settings.local` | Settings module |
| `DB_NAME` | `legaldoctracker` | PostgreSQL database name |
| `DB_USER` | `postgres` | PostgreSQL user |
| `DB_PASSWORD` | `postgres` | PostgreSQL password |
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `MONGO_URI` | `mongodb://localhost:27017` | MongoDB connection URI |
| `MONGO_DB_NAME` | `legaldoctracker` | MongoDB database name |
| `ALLOWED_HOSTS` | `` | Comma-separated allowed hosts |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000` | Comma-separated CORS origins |

---

## CI/CD Pipeline

The GitHub Actions pipeline runs on every push to `main`/`develop` and on PRs:

```
Lint (flake8)
    │
    ▼
Test (pytest-django)
  ├── PostgreSQL 15 service container
  └── MongoDB 7 service container
    │
    ▼
Docker Build (multi-stage)
  └── Validates Dockerfile correctness
```

---

## Django Admin

Access at `/admin/` — features:
- **Contract**: colour-coded status badges, inline event history, date hierarchy
- **Party**: filterable by role, searchable by name/email
- **ContractEvent**: read-only audit log (no add/edit permissions)

---

## License

MIT © LegalDocTracker Contributors
