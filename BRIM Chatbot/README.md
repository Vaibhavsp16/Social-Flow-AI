# BRIM AI — Full-Stack Chatbot Platform

BRIM AI is an industry-centric chatbot platform enabling businesses to create, customize, test, and deploy intelligent AI assistants tailored to their specific industry knowledge and workflows.

---

## 🏗 System Architecture

```text
                               ┌───────────────────────────┐
                               │   React Frontend (Vite)   │
                               │  - Modern Dashboard & UI  │
                               │  - Bot Creation Wizard    │
                               │  - Bot Overview & Editor  │
                               │  - Interactive Preview    │
                               └─────────────┬─────────────┘
                                             │  HTTP/REST (JWT)
                                             ▼
                               ┌───────────────────────────┐
                               │     FastAPI Backend       │
                               │  - Modular Architecture   │
                               │  - Pydantic Validation    │
                               │  - Password Hashing (BCR) │
                               │  - JWT Auth Middleware    │
                               └─────────────┬─────────────┘
                                             │  SQLAlchemy ORM
                                             ▼
                               ┌───────────────────────────┐
                               │   PostgreSQL (Docker)     │
                               │  - Users                  │
                               │  - Projects               │
                               │  - Bots                   │
                               └───────────────────────────┘
```

---

## 📋 Prerequisites

Ensure you have the following installed on your machine:

- **Node.js** (v18+ or v22+)
- **Python** (v3.10+ or v3.13+)
- **Docker** & **Docker Compose**

---

## 🚀 Quick Start Guide

### 1. Start PostgreSQL Database (Docker)

From the `BRIM Chatbot` directory, run:

```bash
docker compose up -d
```

This starts PostgreSQL 16 (with pgvector) on port `5433` (mapped from 5432 to avoid host collisions) with automatic health checks and persistent volume storage.

### 2. Start Backend API Server

Open a terminal and navigate to `BRIM Chatbot/backend`:

```bash
cd backend

# (Optional) Create and activate a virtual environment
python -m venv venv
# Windows:
.\venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the FastAPI server with hot-reloading
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API Base**: `http://localhost:8000`
- **Swagger Docs**: `http://localhost:8000/docs`
- **Health Check**: `http://localhost:8000/health`

### 3. Start React Frontend

Open a second terminal and navigate to `BRIM Chatbot/frontend`:

```bash
cd frontend

# Install packages
npm install

# Start Vite development server
npm run dev
```

The frontend will be running at:
- **App URL**: `http://localhost:5173`

---

## 🔐 Environment Variables

Copy `.env.example` to `.env` in both the root and backend folders as needed:

```ini
# Database
POSTGRES_SERVER=127.0.0.1
POSTGRES_PORT=5433
POSTGRES_DB=brim_ai_db
POSTGRES_USER=brim_user
POSTGRES_PASSWORD=brim_password_2026

# Backend
PROJECT_NAME="BRIM AI Backend"
API_V1_STR="/api"
SECRET_KEY=brim_super_secret_jwt_key_change_in_production_2026_xyz
ACCESS_TOKEN_EXPIRE_MINUTES=1440
ALGORITHM=HS256

# Frontend
VITE_API_BASE_URL=http://localhost:8000/api
```

---

## 📡 API Endpoints Reference

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/` | Service health and meta info | No |
| `GET` | `/health` | Health check endpoint | No |
| `GET` | `/api/industries` | Predefined industries list | No |
| `POST` | `/api/auth/signup` | Register new user account | No |
| `POST` | `/api/auth/login` | Login and receive JWT access token | No |
| `GET` | `/api/auth/me` | Current authenticated user profile | Yes |
| `POST` | `/api/projects` | Create a new project | Yes |
| `GET` | `/api/projects` | List user's projects | Yes |
| `GET` | `/api/projects/{id}` | Get project by ID | Yes |
| `PUT` | `/api/projects/{id}` | Update project details | Yes |
| `DELETE` | `/api/projects/{id}` | Delete a project | Yes |
| `POST` | `/api/bots` | Create a new bot under a project | Yes |
| `GET` | `/api/bots` | List all bots belonging to user | Yes |
| `GET` | `/api/bots/{id}` | Get bot details & associated project | Yes |
| `PUT` | `/api/bots/{id}` | Update bot details & settings | Yes |
| `DELETE` | `/api/bots/{id}` | Delete a bot | Yes |
| `GET` | `/api/bots/{bot_id}/knowledge` | List all knowledge sources for a bot | Yes |
| `POST` | `/api/bots/{bot_id}/knowledge/upload` | Upload document or image file (PDF, DOC, DOCX, TXT, PNG, JPG, WEBP) | Yes |
| `POST` | `/api/bots/{bot_id}/knowledge/website` | Ingest and clean website page URL | Yes |
| `POST` | `/api/knowledge/websites` | Ingest website URL (direct endpoint) | Yes |
| `POST` | `/api/bots/{bot_id}/knowledge/social` | Store & validate social media profile link | Yes |
| `POST` | `/api/bots/{bot_id}/knowledge/instruction` | Add custom prompt instructions, tone, and rules | Yes |
| `GET` | `/api/knowledge/{id}` | Get knowledge source details | Yes |
| `PUT` | `/api/knowledge/{id}` | Update knowledge source details | Yes |
| `DELETE` | `/api/knowledge/{id}` | Delete knowledge source & stored file | Yes |
| `POST` | `/api/bots/{bot_id}/chat` | Ask a single grounded question (retrieval + answer + citations) | Yes |
| `POST` | `/api/public/bots/{slug}/chat` | Same as above, unauthenticated, via the bot's shareable slug | No |
| `POST` | `/api/conversations` | Create a new conversation for a bot | Yes |
| `GET` | `/api/conversations` | List the user's conversations (optional `bot_id` filter) | Yes |
| `GET` | `/api/conversations/{id}` | Get a conversation with its full message history | Yes |
| `PUT` | `/api/conversations/{id}` | Update conversation status / state | Yes |
| `DELETE` | `/api/conversations/{id}` | Delete a conversation and its messages | Yes |
| `POST` | `/api/conversations/{id}/messages` | Send a message: runs intent detection, retrieval and grounded generation | Yes |
| `GET` | `/api/conversations/{id}/messages` | List the persisted messages of a conversation | Yes |
| `GET` | `/api/bots/{bot_id}/conversations` | Conversation summaries for a bot (message counts, last message) | Yes |

---

## 🧪 Running Automated Tests

To run the backend test suite:

```bash
cd backend
python -m pytest tests
```

---

## 🏢 Predefined Industries

Industries are strictly validated against the official centralized list:
- Real Estate
- E-commerce
- Healthcare
- Education
- Finance & Banking
- Travel & Hospitality
- Legal Services
- Technology & SaaS
- Manufacturing
- Automotive
- Marketing & Advertising
- Logistics & Supply Chain
- Food & Restaurant
- Fitness & Wellness
- Professional Services
- Other

---

## 📁 Project Directory Structure

```text
BRIM Chatbot/
├── docker-compose.yml              # PostgreSQL Docker service
├── .env.example                    # Environment template
├── .gitignore                      # Git ignore rules
├── README.md                       # Documentation
├── BRIM_Chatbot_Frontend_Prototype_Updated.html  # Approved UX prototype reference
│
├── frontend/                       # React (Vite) Application
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── components/             # Reusable UI components (Navbar, Sidebar, StatCard, BotCard, Modal, Toast...)
│       ├── pages/                  # Screen views (Login, Signup, Dashboard, MyBots, CreateBot, BotOverview...)
│       ├── layouts/                # MainLayout and AuthLayout
│       ├── routes/                 # ProtectedRoute and AppRoutes
│       ├── services/               # API service layer (authService, projectService, botService)
│       ├── context/                # AuthContext and ToastContext
│       ├── constants/              # Predefined industries
│       ├── index.css               # Full design tokens & responsive CSS
│       ├── App.jsx
│       └── main.jsx
│
└── backend/                        # FastAPI Python Application
    ├── requirements.txt
    ├── tests/
    │   └── test_api.py             # Pytest automated test suite
    └── app/
        ├── main.py                 # FastAPI app entry point & CORS
        ├── core/                   # Config, security, JWT, constants
        ├── database/               # Session & engine setup
        ├── models/                 # SQLAlchemy models (User, Project, Bot)
        ├── schemas/                # Pydantic validation schemas
        ├── api/                    # Routers (auth, projects, bots, deps)
        └── services/               # Business logic services
```
