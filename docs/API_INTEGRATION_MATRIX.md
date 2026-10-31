# API Integration Matrix

**Review date:** 2026-10-28
“Connected” means the frontend calls a matching backend route; it does not
certify behavior as production-ready. Phase 2 now enforces authentication on
feature routes; see [PROJECT_AUDIT.md](./PROJECT_AUDIT.md) for the initial
static review and its historical findings.

| Frontend feature/action | Frontend request | Backend endpoint / service | Persistent entity | Integration status and required action |
|---|---|---|---|---|
| Dashboard metrics and recent activity | `GET /reports/metrics` from `App.jsx` | `reports.get_metrics` | `FacebookPage`, `Post`, `Comment`, `ActionLog` | Connected, partial. Counts all posts rather than monitored posts; missing scheduled posts, ads/spend, engagement analytics, failed jobs, and some activity states. UI safety metrics are hardcoded. |
| Global emergency halt / resume | `POST /reports/emergency-stop`, `POST /reports/resume-all` from `Navbar.jsx` | `reports.emergency_stop_all`, `reports.resume_all_automations` | `FacebookPage`, `ActionLog` | Connected and role-gated. No actor attribution or scheduler job cancellation. |
| Page listing | `GET /pages/` from `ConnectedPages.jsx` | `pages.list_pages` | `FacebookPage` | Connected. User/page access isolation is absent; load errors are logged to console instead of shown as an error state. |
| Connect Page | `POST /pages/` from the connect form | `pages.connect_page`, `MetaGraphClient.validate_page_credentials` | `FacebookPage`, `Post` | Connected. Live tokens are checked for validity and required permissions; OAuth is not implemented. Credentials are encrypted and never returned. |
| Page settings | `PUT /pages/{page_id}` | `pages.update_page` | `FacebookPage` | Connected and authenticated; administrative settings are role-gated. Page timezone is validated as an IANA timezone. |
| Enable/disable page automation | `POST /pages/{page_id}/toggle-automation` | `pages.toggle_automation` | `FacebookPage`, `ActionLog` | Connected and authenticated; privileged action is role-gated. |
| Toggle auto-approval | `PUT /pages/{page_id}` with `auto_approve_enabled` | `pages.update_page` | `FacebookPage` | Connected and role-gated. Auto-publishing is restricted to Gemini-generated, non-negative, unflagged replies. |
| Sync page posts | `POST /pages/{page_id}/sync` | `pages.sync_page_posts`, `MetaGraphClient.fetch_page_posts` | `FacebookPage`, `Post` | Connected, partial. No pagination; external errors are not translated consistently; sync does not ingest comments. |
| Disconnect Page | `DELETE /pages/{page_id}` | `pages.disconnect_page` | `FacebookPage` and cascaded records | Connected and role-gated; destructive cascade still removes local page history. |
| List posts | `GET /posts/` | `posts.list_posts` | `Post` | Connected. Frontend fetches all posts and filters locally; no page selector or pagination. |
| Generate a post draft | `POST /posts/generate-draft` | `posts.generate_post_draft` → `AutomationEngine.generate_daily_post` → Gemini | `Post` | Connected and authenticated. Manual generation always saves a draft; fallback requires explicit configuration and its source is persisted. UI currently hardcodes `page_id: 1`. |
| Edit post draft | `PUT /posts/{post_id}/draft` | `posts.update_post_draft` | `Post` | Connected; only draft posts can be edited. |
| Publish post draft | `POST /posts/{post_id}/publish` | `posts.publish_draft` → `AutomationEngine.publish_draft_post` | `Post`, `FacebookPage`, `ActionLog` | Connected and role-gated; API rejects non-drafts and empty captions. |
| Discard post | `DELETE /posts/{post_id}` | `posts.delete_post` | `Post` | Connected and role-gated; deletion is not audited. |
| Toggle post monitoring | `POST /posts/{post_id}/toggle-monitoring` | `posts.toggle_monitoring` | `Post` | Connected and role-gated. The effect on webhook processing is incomplete; webhook handling does not check the post's monitoring flag. |
| Scheduled posts | No scheduling UI/API call | Scheduler polls due Page-local slots every five minutes | `FacebookPage`, `Post`, `ScheduledPostRun`, `ActionLog` | Persistent per-slot run state, bounded retries, error history, timezone-aware scheduling, non-overlapping in-process checks, and duplicate-run prevention. No user-managed scheduled-post endpoint or multi-process APScheduler store. |
| Approval queue | `GET /comments/queue` | `comments.get_approval_queue` | `Comment`, `Post`, `FacebookPage` | Connected. Pending state and empty state exist; loading errors are only logged to console. |
| All comments and filters | No frontend request | `GET /comments/` (`comments.list_comments`) | `Comment`, `Post`, `FacebookPage` | Backend only. No comments list/search screen is wired. |
| Approve/edit reply | `POST /comments/{comment_id}/approve` | `comments.approve_comment` → `AutomationEngine.approve_and_publish_comment` → Meta reply/like | `Comment`, `FacebookPage`, `ActionLog` | Connected and role-gated; publishing requires a non-empty reply and records failures. |
| Reject reply | `POST /comments/{comment_id}/reject` | `comments.reject_comment` | `Comment`, `ActionLog` | Connected and role-gated; operator identity is not yet recorded. |
| Regenerate reply | `POST /comments/{comment_id}/regenerate` | `comments.regenerate_comment` → async `GeminiService` | `Comment` | Connected; generation source is persisted, fallback is opt-in and visibly labelled, and unavailable/invalid Gemini output returns an explicit error. No draft-version history. |
| Simulate comment | `POST /comments/simulate` | `comments.simulate_incoming_comment` → `AutomationEngine.process_incoming_comment` | `Comment`, `Post`, `ActionLog` | Connected and role-gated. Simulated comments are marked and cannot be auto-published or manually published. UI hardcodes `page_id: 1`. |
| Meta webhook verification | No frontend request | `GET /webhook/` | No persistent entity | Meta-facing endpoint only. Verify token handshake exists. |
| Meta webhook event | No frontend request | `POST /webhook/` → `AutomationEngine.process_incoming_comment` | `FacebookPage`, `Post`, `Comment`, `ActionLog` | Meta signature (`X-Hub-Signature-256`) is verified before parsing; endpoint is disabled in simulation mode; duplicate comments are protected by a unique comment ID and replay-safe handling. No separate raw webhook-event record. |
| Restricted keywords | `GET /rules/keywords`, `POST /rules/keywords`, `DELETE /rules/keywords/{id}` | `rules.list_keywords`, `add_keyword`, `delete_keyword` | `RestrictedKeyword` | Connected CRUD subset. No edit route/UI; global scope only; stored `action` does not control behavior (matches always prevent auto-publish). |
| Automation rules | `GET /rules/`, `POST /rules/`, `DELETE /rules/{id}` | `rules.list_rules`, `create_rule`, `delete_rule` | `AutomationRule` | Matching active keyword templates are applied and queued for human review; page-specific rules take precedence. No edit/enable route or UI. |
| Audit log list/filter | `GET /reports/logs?status=...` | `reports.list_action_logs` | `ActionLog` | Connected. No actor attribution or frontend pagination/date filters/export; action coverage incomplete. |
| Login / session / logout | `POST /auth/login`, `GET /auth/me`, `POST /auth/refresh`, `POST /auth/logout` | `auth.login`, `auth.get_me`, `auth.refresh`, `auth.logout` | `User`, `UserSession` | Connected. Short-lived in-memory access token, HttpOnly rotating refresh cookie, and persistent hashed refresh-token sessions. |
| Registration / user role | `POST /auth/register` | `auth.register` | `User` | Connected and administrator-only; role selection is constrained by caller privileges. |
| Advertising account and campaigns | `GET /ads/account`, `GET /ads/campaigns`, `POST /ads/sync` | `ads.get_account`, `ads.list_campaigns`, `ads.sync_campaigns` → `MetaAdsClient`, `AdsManager` | `AdCampaign`, `AdCampaignDailyDelivery` | Connected and authenticated. Reads existing campaigns and daily spend/delivery; simulation mode is explicit. Live account authorization has not been verified. |
| Advertising budget and delivery controls | `PATCH /ads/campaigns/{id}/budget`, `PATCH /ads/campaigns/{id}/status` | Ads routes → `MetaAdsClient` | `AdCampaign`, `AdCampaignDailyDelivery` | Admin-only. Server enforces NPR currency and a maximum NPR 5.00 campaign daily budget; lifetime-budget campaigns cannot be activated or budget-managed. Does not create campaigns/ad sets/ads; live writes have not been tested. |
| Analytics / report export | No charts/export request | `GET /reports/metrics` and `/reports/logs` only | Current counters and `ActionLog` | Minimal only. No date-range queries, post-level historical metrics, shares/reach, campaign metrics, charts, or export. |
| Settings / account profile | No frontend screen or request | `GET /auth/me` is the only profile-adjacent route; no settings API | `User`, `FacebookPage` | Missing. No role administration, account preferences, integrations settings, notification settings, or security settings UI. |

## Existing backend endpoint inventory

All paths below are mounted below `/api/v1` except the root/health checks and
Meta webhook path (the webhook is still mounted below `/api/v1`).

| Method and path | Handler | Purpose |
|---|---|---|
| `POST /auth/login` | `auth.login` | Verify password and issue access JWT |
| `GET /auth/me` | `auth.get_me` | Return current user through `get_current_user` |
| `POST /auth/refresh` | `auth.refresh` | Rotate refresh session and issue a new access JWT |
| `POST /auth/logout` | `auth.logout` | Revoke refresh session |
| `POST /auth/register` | `auth.register` | Create user (administrator-only) |
| `GET /pages/` | `pages.list_pages` | List connected pages |
| `POST /pages/` | `pages.connect_page` | Create page and try initial Meta sync |
| `GET /pages/{page_id}` | `pages.get_page` | Read one page |
| `PUT /pages/{page_id}` | `pages.update_page` | Update settings/token |
| `POST /pages/{page_id}/toggle-automation` | `pages.toggle_automation` | Toggle page automation |
| `POST /pages/{page_id}/sync` | `pages.sync_page_posts` | Sync Page feed |
| `DELETE /pages/{page_id}` | `pages.disconnect_page` | Delete connected Page and cascaded local data |
| `GET /posts/` | `posts.list_posts` | List/filter posts |
| `GET /posts/drafts` | `posts.list_draft_posts` | List drafts |
| `POST /posts/generate-draft` | `posts.generate_post_draft` | Generate a post draft |
| `PUT /posts/{post_id}/draft` | `posts.update_post_draft` | Edit an unpublished post draft |
| `POST /posts/{post_id}/publish` | `posts.publish_draft` | Publish an existing post draft |
| `GET /posts/{post_id}` | `posts.get_post` | Read one post |
| `POST /posts/{post_id}/toggle-monitoring` | `posts.toggle_monitoring` | Toggle monitoring flag |
| `DELETE /posts/{post_id}` | `posts.delete_post` | Delete post |
| `GET /comments/queue` | `comments.get_approval_queue` | List pending approvals |
| `GET /comments/` | `comments.list_comments` | List comments with status/page/language filters |
| `POST /comments/{comment_id}/approve` | `comments.approve_comment` | Publish approved reply |
| `POST /comments/{comment_id}/reject` | `comments.reject_comment` | Reject pending reply |
| `POST /comments/{comment_id}/regenerate` | `comments.regenerate_comment` | Regenerate AI draft |
| `POST /comments/simulate` | `comments.simulate_incoming_comment` | Inject a simulated comment |
| `GET /rules/keywords` | `rules.list_keywords` | List restricted keywords |
| `POST /rules/keywords` | `rules.add_keyword` | Add restricted keyword |
| `DELETE /rules/keywords/{keyword_id}` | `rules.delete_keyword` | Delete restricted keyword |
| `GET /rules/` | `rules.list_rules` | List automation rules |
| `POST /rules/` | `rules.create_rule` | Create automation rule |
| `DELETE /rules/{rule_id}` | `rules.delete_rule` | Delete automation rule |
| `GET /reports/metrics` | `reports.get_metrics` | Aggregate dashboard values |
| `GET /reports/logs` | `reports.list_action_logs` | List action logs |
| `POST /reports/emergency-stop` | `reports.emergency_stop_all` | Pause page automation |
| `POST /reports/resume-all` | `reports.resume_all_automations` | Resume page automation |
| `GET /webhook/` | `webhook.verify_webhook` | Meta webhook subscription handshake |
| `POST /webhook/` | `webhook.handle_webhook_event` | Receive page webhook changes |
| `GET /health` | `main.health_check` | Basic service response |
| `GET /` | `main.root` | API welcome and docs links |
