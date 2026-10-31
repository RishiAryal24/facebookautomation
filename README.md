# PyLoom AI-Powered Facebook Page Engagement & Automation System

A Facebook Page engagement prototype, being hardened against the requirements in **ANNEX A** and the **PyLoom Memorandum of Engagement (MoE)**. It is not yet certified as enterprise-ready or production-ready; see the current [project audit](./docs/PROJECT_AUDIT.md).

---

## 🌟 Key Features

### 1. Bilingual AI Engine (English & Nepali)
- Powered by **Google Gemini** with intelligent contextual reasoning.
- Seamlessly handles **Nepali in Devanagari script** (नेपाली), **Romanized Nepali** (e.g., *"kati parcha hola?"*), and **English**.
- Configurable response styles & tones: **Friendly, Professional, Customer Support, and Promotional**.
- Uses the asynchronous Gemini client, validates structured responses, and records whether a draft came from Gemini, a configured automation template, or a local fallback.
- Local fallback templates are disabled by default. To enable them, explicitly set `ENABLE_LOCAL_AI_FALLBACK=true`; fallback drafts are labelled and are never auto-published.

### 2. Dual Automation Modes
- **Mode A: Safety-checked auto-publishing:** Signed Meta webhook comments may be replied to automatically only when the Gemini result is high-confidence, non-negative, not restricted, and within operating-hour/rate limits.
- **Mode B: Supervised Approval Queue (Human-in-the-Loop):** AI drafts responses and displays them in an interactive triage queue where operators can **Approve with 1 click**, **Edit inline**, **Regenerate with a new tone/language**, or **Reject**.
- Negative, restricted-keyword, template-rule, and local-fallback replies remain in the comment approval queue. AI post generation always creates a separate administrator-reviewed content draft.

### 3. Safety Guardrails & Meta Platform Compliance
- **Restricted Keywords Blacklist:** Blocks auto-replies to sensitive comments (e.g. complaints, scam accusations, refunds) and alerts operators.
- **Operating Hours Scheduler:** Restricts automated replies to business hours (e.g., 08:00 AM – 10:00 PM NPT).
- **Scheduled content generation:** Daily, Page-local IANA timezone schedules create drafts only. Persisted generation runs prevent duplicate jobs across restarts; scheduled publication times are planning metadata and never trigger Facebook requests.
- **Verified manual Page publishing:** Content must first be approved, simulation mode must be off, and the administrator must explicitly confirm. The backend sends an explicit `published=true` request, records Meta's HTTP result and sanitized response details, then verifies the returned post ID and `is_published` state before recording success. Scheduled content is never published automatically in this development phase.
- **Rate-Limiting:** Protects Page health by capping actions (e.g., maximum 30 replies/hour).
- **Emergency Kill Switch:** Single-click global emergency halt to pause all automations instantly.
- **AES-128 Fernet Encryption:** Secures Meta Page access tokens at rest.

### 4. Comprehensive Dashboard & Reporting
- Executive KPIs: Connected Pages, Monitored Posts, Total Ingested Comments, Pending Queue, Published Count, Total Likes.
- Action logs with timestamps, status badges, and error diagnostics (actor attribution and complete event coverage are not yet implemented).
- Built-in **Simulation & Testing Lab** to exercise comment handling without publishing to Facebook.
- Advertising delivery management for existing campaigns, with daily delivery snapshots and a server-enforced **NPR 5.00/day** maximum budget. Campaign/ad creation is not supported.

### AI content generation workflow

The **AI Content** dashboard configures daily Gemini draft generation per Page
(defaults: 09:00 Asia/Kathmandu, one post, English/Nepali, professional and
engaging tone, rotating categories, administrator approval required). Use
**Generate Now** for an immediate draft. Captions and content versions, job
results/errors, approvals, rejections, and scheduled times are stored in the
database. Regeneration updates a draft only after Gemini returns validated
content; failures preserve the previous draft.

Relevant API operations are under `/api/v1/posts`: `GET/PUT
/automation-config`, `POST /generate-draft`, `POST /{id}/regenerate`,
`PUT /{id}/draft`, `POST /{id}/approve`, `POST /{id}/reject`,
`GET /scheduled`, `POST/DELETE /{id}/schedule`, and `GET /history`.
Automatic content publishing is forced off; scheduling is not publishing.

---

## 🚀 Quick Start Guide

### Prerequisites
- **Python:** 3.12+
- **Node.js:** 20+ (with npm)

### 1. Setup Backend
```powershell
# In the project root
python -m venv .venv
.venv\Scripts\activate
pip install -r backend\requirements.txt

# Start backend server (port 8000)
python backend\run.py
```
- Swagger API Docs will be available at: `http://localhost:8000/docs`

### Run Backend Tests
```powershell
cd backend
pip install -r requirements-dev.txt
python -m pytest
```

### 2. Setup Frontend
```powershell
cd frontend
npm install
npm run dev
```
- Web Dashboard will be available at: `http://localhost:5173`

### Docker Compose deployment

The Compose stack runs one FastAPI process, one PostgreSQL database, and a
production-built frontend served by Nginx. The API runs one process because its
APScheduler jobs are in-process; do not scale the backend horizontally unless
scheduler coordination is moved to a shared job store/worker.

1. Copy `deploy/compose.env.example` to the repository-root `.env` and set a
   long random alphanumeric database password and the public frontend origin.
   For example, generate the password with
   `python -c "import secrets; print(secrets.token_hex(32))"` using a trusted
   local Python installation.
2. Copy `backend/.env.example` to `backend/.env`. Generate unique `SECRET_KEY`,
   `ENCRYPTION_KEY`, and `META_VERIFY_TOKEN` values, set the initial admin
   email/password, and provide only authorized Meta/Gemini credentials. Keep
   both environment files private and out of version control.
3. Before deploying, review the Meta App settings, webhook URL, Page and Ads
   permissions, and budget guardrails. No real ad changes are made until an
   authorized Marketing API token and Ad Account are configured.
4. Build and start with `docker compose up --build -d`. The UI is bound to
   `127.0.0.1:8080`; put a TLS-terminating reverse proxy in front of it for
   public access. Inspect health with `docker compose ps` and logs with
   `docker compose logs`.
5. Back up the `postgres_data` volume and rotate deployment secrets according
   to your operations policy.

Production mode skips demo Page/content seeding. It requires valid
application/encryption/webhook secrets, secure auth cookies, simulation disabled,
and an explicit CORS origin. Compose uses PostgreSQL via `asyncpg`; local
development continues to default to SQLite. Validate rendered settings with
`docker compose config` after preparing the environment files. Docker must be
installed to build or run this stack.

---

## 🔑 Environment Configuration (`backend/.env`)

Copy `backend/.env.example` to `backend/.env` and update credentials:

```ini
# Generate a unique SECRET_KEY (at least 32 characters) and Fernet ENCRYPTION_KEY.
# Set INITIAL_ADMIN_EMAIL and a unique INITIAL_ADMIN_PASSWORD (12+ characters)
# before the first backend start to provision the initial Super Admin.
ENVIRONMENT=development
SECRET_KEY=replace_with_a_unique_random_secret
ENCRYPTION_KEY=replace_with_a_valid_fernet_key
INITIAL_ADMIN_EMAIL=admin@example.com
INITIAL_ADMIN_PASSWORD=replace_with_a_unique_password

# Google Gemini API Key
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
ENABLE_LOCAL_AI_FALLBACK=false

# Meta / Facebook Graph API Credentials
META_APP_ID=your_meta_app_id
META_APP_SECRET=your_meta_app_secret
META_VERIFY_TOKEN=choose_a_random_webhook_verification_token
META_GRAPH_API_VERSION=v26.0

# Simulation Mode (Set to false when using live Facebook tokens)
SIMULATION_MODE=true

# Default timezone for newly connected Pages; can be overridden per Page.
DEFAULT_TIMEZONE=Asia/Kathmandu
```

Generate keys from the activated backend environment:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Page IDs and Page Access Tokens are entered through the Connect Facebook Page
form and belong to individual database records. The backend validates submitted
credentials with read-only Meta Graph API calls before saving tokens encrypted
in the database. The global app secret and encryption key remain in the backend
environment. Replace any token exposed in chat, logs, or screenshots; never
paste credentials into support conversations.

To verify a Page's `CREATE_CONTENT` task without publishing, the form also
accepts a temporary User Access Token for the read-only `/me/accounts` check.
That User token is sent only for validation and is never stored or returned;
only the validated Page token is encrypted in the Page record.

The header's **Simulation ON/OFF** switch controls the running backend process.
When simulation is on, real Page credentials can still be validated using
read-only Meta requests, but post publishing is blocked. Switching simulation
off is allowed only after at least one Page has a connected, validated token
for the configured Meta app with `pages_manage_posts`, `pages_read_engagement`, and the Page task
`CREATE_CONTENT`. The switch applies immediately and resets to the
`SIMULATION_MODE` value in `backend/.env` when the backend restarts. Keep the
environment default at `true` for safe startup. Manual live publishing is
available only for approved content in the AI Content view, after explicit
administrator confirmation; it is recorded as successful only after Meta
returns a post ID and a follow-up Graph API read confirms it is published.
Scheduled content is never published automatically in this development phase.

The backend refuses to start with missing/invalid signing, encryption, or
webhook verification secrets. Keep `backend/.env` private and never commit real
credentials. The initial administrator is created only when both initial-admin
values are configured; the former built-in demo password is no longer used.
Real Meta webhook POSTs require `META_APP_SECRET` so `X-Hub-Signature-256` can
be verified. Keep `ENABLE_LOCAL_AI_FALLBACK=false` for production: without a
Gemini key or on API/response failure, generation returns an explicit error
instead of silently substituting content.

---

## 📁 Project Structure

```
facebookautomation/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # REST Endpoints (Auth, Pages, Posts, Comments, Rules, Reports, Webhook)
│   │   ├── core/            # Database async engine, JWT, Fernet token encryption
│   │   ├── db/              # Database schema migrations & bilingual demo data seeder
│   │   ├── models/          # SQLAlchemy relational models (User, Page, Post, Comment, Rule, Log)
│   │   ├── schemas/         # Pydantic request and response schemas
│   │   ├── services/
│   │   │   ├── gemini_service.py     # Gemini comment replies and brand-aware content drafts
│   │   │   ├── meta_client.py        # Meta Page Graph API client
│   │   │   ├── meta_ads_client.py    # Meta Marketing API client (Live & Sandbox modes)
│   │   │   ├── ads_manager.py        # Campaign sync and daily delivery snapshots
│   │   │   └── automation_runner.py  # Draft generation, comment runner, rate-limiter & policy engine
│   │   ├── config.py        # Settings
│   │   └── main.py          # FastAPI application entry point
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── run.py
│   └── .env.example
│
├── frontend/                # React (Vite) + Tailwind CSS Dashboard
│   ├── src/
│   │   ├── components/      # Navbar, Sidebar
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx        # Executive KPIs and live activity stream
│   │   │   ├── ApprovalQueue.jsx    # Bilingual AI review, edit, approve & regenerate
│   │   │   ├── ConnectedPages.jsx   # Facebook Page connections & rate-limit controls
│   │   │   ├── PostMonitor.jsx      # Feed posts and comment engagement
│   │   │   ├── ContentAutomation.jsx # AI draft settings, approvals, scheduling & history
│   │   │   ├── RulesManager.jsx     # Keyword blacklist & custom rules
│   │   │   ├── AuditLogs.jsx        # Audit logs & action history
│   │   │   └── Simulator.jsx        # Interactive live testing lab
│   │   ├── api.js           # Axios backend API client
│   │   └── App.jsx
│   ├── package.json
│   ├── Dockerfile
│   └── vite.config.js
│
├── compose.yaml             # Single-instance API + PostgreSQL + frontend
├── deploy/compose.env.example
├── ANNEX A.docx
└── PyLoom_Facebook_Automation_MoE_Branded.docx
```

---

## 📜 Contractual Alignment
This implementation strictly fulfills:
- **ANNEX A** (Scope of Work and Functional Features: Dashboard, Facebook Page Integration, Post Monitoring, AI Comment Automation, Facebook Like/Engagement Workflows, Automation Settings, Reports/Notifications, and Security/Administration).
- **PyLoom MoE** (Legitimate audience growth, authentic interactions, policy compliance, and executive performance reporting).
