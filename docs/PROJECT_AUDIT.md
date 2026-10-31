# Project Audit

**Review date:** 2026-10-28
**Scope:** Static review of the repository as checked out on `main`. No application
credentials were used and no live Meta or Gemini requests were made. This is a
Phase 1 audit, not a production-readiness certification.

## Repository structure

```text
facebookautomation/
├── .gitignore
├── README.md
├── start.bat
├── ANNEX A.docx
├── PyLoom_Facebook_Automation_MoE_Branded.docx
├── ~$NNEX A.docx                         # Office temporary/lock file in checkout
├── backend/
│   ├── .env.example
│   ├── migrate.py
│   ├── requirements.txt
│   ├── run.py
│   └── app/
│       ├── config.py
│       ├── main.py
│       ├── api/
│       │   └── v1/
│       │       ├── auth.py
│       │       ├── comments.py
│       │       ├── pages.py
│       │       ├── posts.py
│       │       ├── reports.py
│       │       ├── rules.py
│       │       └── webhook.py
│       ├── core/
│       │   ├── database.py
│       │   └── security.py
│       ├── db/
│       │   └── init_db.py
│       ├── models/
│       │   ├── __init__.py
│       │   └── entities.py
│       ├── schemas/
│       │   ├── __init__.py
│       │   └── schemas.py
│       └── services/
│           ├── automation_runner.py
│           ├── gemini_service.py
│           ├── meta_client.py
│           └── scheduler.py
└── frontend/
    ├── .gitignore
    ├── .oxlintrc.json
    ├── index.html
    ├── package-lock.json
    ├── package.json
    ├── README.md
    ├── vite.config.js
    ├── public/
    │   ├── favicon.svg
    │   └── icons.svg
    └── src/
        ├── App.css
        ├── App.jsx
        ├── api.js
        ├── index.css
        ├── main.jsx
        ├── assets/
        │   ├── hero.png
        │   ├── react.svg
        │   └── vite.svg
        ├── components/
        │   ├── Navbar.jsx
        │   └── Sidebar.jsx
        └── pages/
            ├── ApprovalQueue.jsx
            ├── AuditLogs.jsx
            ├── ConnectedPages.jsx
            ├── Dashboard.jsx
            ├── PostMonitor.jsx
            ├── RulesManager.jsx
            └── Simulator.jsx
```

At the time of this historical Phase 1 review, no test directory, test files,
deployment manifests, ad module, or docs directory existed. The frontend has an
`npm` lockfile; Python dependencies are listed as minimum versions rather than
being locked to a reproducible environment.

## Product and implementation summary

The application is a React/Vite dashboard with a FastAPI/SQLAlchemy service. Its
central workflow is to receive or simulate a Facebook Page comment, create a
reply draft through Gemini or a local fallback, and queue or publish the reply.
It also has page and post management screens, keyword/rule CRUD, action logs,
basic dashboard totals, and an in-process daily-post scheduler.

The database models and most dashboard actions are connected to persistent
SQLite-backed API operations. The repository also contains Meta Graph API
request code. However, the available code is best described as a
simulation-oriented prototype with partial live-integration paths:

- In development/simulation, startup creates database tables and seeds a demo
  page, posts, comments, and restricted keywords. Production mode skips demo
  Page/content seeding; the configured administrator and restricted keywords
  are still provisioned.
- `MetaGraphClient` returns synthetic data or success-shaped responses for
  missing/mock tokens. The `SIMULATION_MODE` setting does not gate these
  branches.
- Gemini is optional; missing or failing Gemini calls silently use local
  templates.
- Page connection accepts a manually entered token rather than using Meta OAuth
  and validating granted permissions.
- APIs are not consistently authenticated or authorized.

## Feature status

| Area | Status | Evidence and gap |
|---|---|---|
| Dashboard | Partial | Metrics and recent action logs are fetched, but several claims and values are incomplete or static. It has no ads, spend, scheduled-job, or failed-job data. |
| Facebook Pages | Partial | CRUD, settings, automation toggles, and feed sync exist. Token validity/permissions/expiry are not checked, and the UI sends Page ID 1 assumptions elsewhere. |
| Posts | Partial | List, generate draft, publish, monitoring toggle, and delete work through endpoints. Editing a draft, scheduling/rescheduling/cancellation, page selection, and reliable publishing state are absent. |
| Comment intake | Partial | A webhook path and simulator use the processing pipeline. Polling/comment retrieval is not wired into sync; the Meta comments-fetch helper is unused and returns no simulated comments. |
| Comment approval | Partial | Queue, approve, reject, and regenerate endpoints exist and the approval UI is wired. There is no dedicated full comments/search screen, and approval has no role restriction. |
| AI replies/posts | Partial | Gemini client and English/Nepali prompt/fallback code exist. Failures are hidden behind fallback text, fallback is not explicitly enabled, outputs are not validated/moderated, and an async method performs a synchronous SDK call. |
| Restricted keywords | Partial | Global keyword records can be listed/created/deleted and checked in the comment pipeline. Per-page scope is absent; the stored action is not honored; the UI has no edit path. |
| Automation rules | Not functionally applied | Rules can be listed/created/deleted. The comment processor never evaluates them; update/enable controls are not exposed by the UI or API. |
| Audit logs | Partial | Action logs are persisted and listed, but event coverage is incomplete and logs can contain response content. No pagination cursor/export or actor identity is recorded. |
| Scheduling | Partial / not production-safe | APScheduler runs in application memory every 15 minutes. It has no persistent job records, timezone setting, retry history, or multi-worker coordination. Draft creation does not increment the daily counter and can therefore repeat. |
| Simulation | Partial / unsafe separation | The simulator reaches the same processing/publishing code. `SIMULATION_MODE` is not enforced by the Meta client, so an auto-approved page with a real token could publish from a simulated workflow. |
| Authentication | Insecure / disconnected | Login/register and JWT helpers exist, but frontend has no login/logout flow and most API routes have no authentication dependency. Role-based authorization is absent. |
| Advertising | Partial implementation | Existing campaign/account reads, daily delivery snapshots, and admin-only budget/status controls are implemented. The server caps campaign daily budgets at NPR 5.00. Campaign creation and live account validation remain out of scope/unverified. |
| Engagement analytics | Missing / minimal | Only aggregate comment/page/post/reply/like counts are surfaced. No date filtering, charts, post performance history, export, reach, shares, or engagement rate. |
| Settings / user administration | Missing | No profile, role management, account settings, AI settings UI, or notification configuration. |
| Tests | Missing | No automated backend, frontend, or end-to-end tests were found in the repository. |

## Frontend-to-backend integration gaps

The feature-by-feature route and persistence mapping is in
[API_INTEGRATION_MATRIX.md](./API_INTEGRATION_MATRIX.md). Important observed
integration gaps:

1. The dashboard, simulator, and post generator assume `page_id: 1`; they do not
   choose the relevant connected Page.
2. The frontend has no authentication flow or token-bearing API client.
3. Multiple fetch screens catch errors only with `console.error`; users can see
   an empty/zero state instead of an actionable load failure.
4. Some mutations use browser `alert`/`confirm`; pending-state/duplicate-submit
   prevention is inconsistent.
5. The Dashboard's safety values (including “8 blocked” and “30 actions/hr”)
   are hardcoded, not derived from stored settings.
6. The post page does not provide scheduling or draft editing, even though
   related scheduling fields exist in the model.
7. There is no advertising, analytics, profile/settings, or dedicated
   comments/search page.
8. The “Published to Facebook” client filter treats every non-draft status,
   including `failed`, as published.
9. The UI presents “Live” and “AI” language even when the backend returns
   simulated results or locally generated fallback text.

## Database and API gaps

### Existing persistence

`entities.py` defines `User`, `FacebookPage`, `Post`, `Comment`,
`RestrictedKeyword`, `AutomationRule`, and `ActionLog`. The models persist
current records and selected counters. Core API handlers generally commit
changes to the database.

### Missing or incomplete data structures

- No durable webhook-event/idempotency record, scheduled-job execution history,
  refresh/session/revocation record, or user-to-page/company ownership model.
- No ad account, campaign, ad set, creative, approval-request, or engagement
  metric entities.
- No indexes/constraints for several workflow invariants beyond individual
  primary/unique IDs; no tenant boundary.
- `ActionLog` has no actor/user relationship, and logs cover only selected
  outcomes.
- Scheduler state and execution history are not persisted.

### API coverage

Existing API groups are auth, pages, posts, comments, rules, reports, and
webhook. The routes do not implement the complete scope: no Meta OAuth/callback,
token validation, ad/analytics, scheduled-post/job management, user/role
administration, comment search/reply outside approval, or settings APIs.
Frontend access to implemented endpoints does not imply authorization: most
routes do not depend on the authentication helper.

## Security findings

These are static-review findings, not results from an external penetration test.

| Risk | Finding |
|---|---|
| Critical | Most data and mutation endpoints, including page management, publishing, rule changes, and emergency stop/resume, do not require authentication. |
| Critical | `get_current_user` grants the seeded default administrator to requests without a token when that account exists. |
| High | Public registration accepts role and active-state fields from `UserCreate`, allowing a caller to request privileged roles. No role checks are applied to endpoints. |
| High | A seeded `admin@pyloom.com` account uses a known static password (`admin123`). |
| High | Development fallback `SECRET_KEY`, Fernet `ENCRYPTION_KEY`, and webhook verify token are hardcoded defaults in config and repeated in `.env.example`; startup does not reject defaults. |
| High | CORS is configured with `allow_origins=["*"]` and credentials enabled instead of using the configured origin allowlist. |
| High | Simulation is not isolated from publishing: `SIMULATION_MODE` is unused in the Meta client, while simulated comments share the ordinary auto-publish path. |
| Medium | Webhook POST events are not authenticated with `X-Hub-Signature-256`; only the GET verification handshake checks the verify token. |
| Medium | Page tokens are entered directly in the UI and sent to the backend without OAuth, permission/expiry validation, or a token-status workflow. The response schema does not expose the token, which is positive, but the input path remains a production risk. |
| Medium | `decrypt_token` catches every exception and returns the input unchanged; this can turn ciphertext/configuration errors into opaque Meta authentication failures. |
| Medium | Gemini exceptions and parse failures silently produce fallback content without identifying it to operators; some exceptions are printed rather than handled through structured/redacted logging. |
| Medium | There is no request throttling, per-user/page authorization, or consistent actor audit trail. |
| Medium | SQLite startup uses `create_all` and broad exception swallowing around ad-hoc `ALTER TABLE` statements; the separate SQLite migration script is not versioned and does not provide a production migration path. |

## Meta and Gemini integration status

### Meta

`meta_client.py` contains Graph API calls for Page details, feed retrieval,
comment retrieval, comment replies, likes, and Page feed posts. These use HTTPX
and request timeouts, and call `raise_for_status()` for non-simulation
responses. The code has no OAuth flow, permission checks, token expiry/status
checks, retry/backoff, pagination handling, signature verification, or
configurable mock/live boundary. The installed Graph API version is configured
as `v21.0`. No Marketing API integration exists. Live behavior was not tested
because no authorization credentials were provided.

### Gemini

`gemini_service.py` includes bilingual prompt and generation logic plus local
templates. API key configuration is optional. Generation exceptions and JSON
parse errors fall through to local templates; this is not surfaced as an AI
failure or explicitly gated fallback. No generation tests were found.

## Dependency, configuration, and deployment issues

- Backend requirements use unbounded minimum constraints (for example
  `fastapi>=...`) and there is no Python lockfile.
- Frontend dependency versions are present in `package-lock.json`; build/lint
  behavior was not included in this static audit.
- `.env.example` repeats development secrets and `config.py` has the same
  insecure fallbacks. A secret-free template and production validation are
  required.
- Default database is local SQLite; there is no PostgreSQL configuration or
  migration framework.
- `run.py` binds to `127.0.0.1` and enables reload, appropriate for local
  development but not a deployment server.
- CORS settings in configuration are not used by the app's middleware.
- Scheduler launches in every application process and is not coordinated across
  multiple workers.
- The frontend API base URL is hardcoded to `http://localhost:8000`.
- No Docker/Compose, CI workflow, production server configuration, backup
  instructions, or deployment guide is present.
- `start.bat` and the Windows Office temporary `~$NNEX A.docx` need review
  before considering the checkout deployable or clean.

## Test status and audit limitations

No test files or test-runner configuration were found. No automated tests,
frontend build, backend startup, live Graph API call, or Gemini call was run as
part of this static Phase 1 audit. Therefore, no feature is certified as
passing end-to-end tests. Credentials and a Meta app/Page authorization are
required before live integration checks can be attempted.

## Phase 1 exit status

**Complete:** repository inventory, feature/gap review, frontend/backend route
mapping, database/API review, security/configuration findings, and the required
API integration matrix have been documented.

**Not started:** implementation phases. Per the requested phase gate, work should
not move to Phase 2 until this audit phase is accepted as complete.
