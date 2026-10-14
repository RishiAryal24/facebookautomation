# PyLoom AI-Powered Facebook Page Engagement & Automation System

An enterprise-ready, policy-compliant Facebook Page automation and engagement platform designed and developed in accordance with **ANNEX A** and the **PyLoom Memorandum of Engagement (MoE)**.

---

## 🌟 Key Features

### 1. Bilingual AI Engine (English & Nepali)
- Powered by **Google Gemini** with intelligent contextual reasoning.
- Seamlessly handles **Nepali in Devanagari script** (नेपाली), **Romanized Nepali** (e.g., *"kati parcha hola?"*), and **English**.
- Configurable response styles & tones: **Friendly, Professional, Customer Support, and Promotional**.

### 2. Dual Automation Modes
- **Mode A: Full Autonomous Auto-Pilot:** Automatically scans posts, drafts replies, screens for safety, likes the comment, and posts the reply to Facebook without human intervention.
- **Mode B: Supervised Approval Queue (Human-in-the-Loop):** AI drafts responses and displays them in an interactive triage queue where operators can **Approve with 1 click**, **Edit inline**, **Regenerate with a new tone/language**, or **Reject**.

### 3. Safety Guardrails & Meta Platform Compliance
- **Restricted Keywords Blacklist:** Blocks auto-replies to sensitive comments (e.g. complaints, scam accusations, refunds) and alerts operators.
- **Operating Hours Scheduler:** Restricts automated replies to business hours (e.g., 08:00 AM – 10:00 PM NPT).
- **Rate-Limiting:** Protects Page health by capping actions (e.g., maximum 30 replies/hour).
- **Emergency Kill Switch:** Single-click global emergency halt to pause all automations instantly.
- **AES-128 Fernet Encryption:** Secures Meta Page access tokens at rest.

### 4. Comprehensive Dashboard & Reporting
- Executive KPIs: Connected Pages, Monitored Posts, Total Ingested Comments, Pending Queue, Published Count, Total Likes.
- Complete audit trail with timestamps, status badges, and error diagnostics.
- Built-in **Simulation & Testing Lab** to test comments live without needing an approved Meta App.

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

### 2. Setup Frontend
```powershell
cd frontend
npm install
npm run dev
```
- Web Dashboard will be available at: `http://localhost:5173`

---

## 🔑 Environment Configuration (`backend/.env`)

Copy `backend/.env.example` to `backend/.env` and update credentials:

```ini
# Google Gemini API Key
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash

# Meta / Facebook Graph API Credentials
META_APP_ID=your_meta_app_id
META_APP_SECRET=your_meta_app_secret
META_VERIFY_TOKEN=pyloom_meta_webhook_verify_token_2026

# Simulation Mode (Set to false when using live Facebook tokens)
SIMULATION_MODE=true
```

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
│   │   │   ├── gemini_service.py     # Bilingual Gemini AI comment & sentiment engine
│   │   │   ├── meta_client.py        # Meta Graph API client (Live & Sandbox modes)
│   │   │   └── automation_runner.py  # Automation runner, rate-limiter & policy engine
│   │   ├── config.py        # Settings
│   │   └── main.py          # FastAPI application entry point
│   ├── requirements.txt
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
│   │   │   ├── RulesManager.jsx     # Keyword blacklist & custom rules
│   │   │   ├── AuditLogs.jsx        # Audit logs & action history
│   │   │   └── Simulator.jsx        # Interactive live testing lab
│   │   ├── api.js           # Axios backend API client
│   │   └── App.jsx
│   ├── package.json
│   └── vite.config.js
│
├── ANNEX A.docx
└── PyLoom_Facebook_Automation_MoE_Branded.docx
```

---

## 📜 Contractual Alignment
This implementation strictly fulfills:
- **ANNEX A** (Scope of Work and Functional Features: Dashboard, Facebook Page Integration, Post Monitoring, AI Comment Automation, Facebook Like/Engagement Workflows, Automation Settings, Reports/Notifications, and Security/Administration).
- **PyLoom MoE** (Legitimate audience growth, authentic interactions, policy compliance, and executive performance reporting).
