# API Reference & Architecture Documentation

Base URL: `http://127.0.0.1:8000`
All protected endpoints below are mounted under `/api/v1` (configurable via `API_PREFIX` in `.env`).
Interactive docs: `GET /docs` (Swagger UI) and `GET /redoc`.

---

## 1. Authentication Endpoints (`/api/v1/auth`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/register` | Register new SaaS account, returns JWT access & refresh tokens |
| POST | `/api/v1/auth/login` | Authenticate user credentials, returns JWT tokens & sets HttpOnly cookie |
| POST | `/api/v1/auth/refresh` | Refresh expired access token using valid refresh token or cookie |
| POST | `/api/v1/auth/logout` | Revoke active sessions & clear session cookies |
| POST | `/api/v1/auth/verify-email/request` | Generate email verification token |
| POST | `/api/v1/auth/verify-email/confirm` | Confirm email address using verification token |
| POST | `/api/v1/auth/password-reset/request` | Initiate password reset token flow |
| POST | `/api/v1/auth/password-reset/confirm` | Complete password reset & invalidate active sessions |
| GET  | `/api/v1/auth/profile` | Get current user profile and settings |
| PUT  | `/api/v1/auth/profile` | Update username, email, timezone, language, and notification settings |
| POST | `/api/v1/auth/profile/avatar` | Update avatar image URL |
| GET  | `/api/v1/auth/sessions` | List active user login sessions |
| DELETE | `/api/v1/auth/sessions/{id}` | Revoke specific session |
| POST | `/api/v1/auth/sessions/revoke-all` | Revoke all active sessions across devices |
| POST | `/api/v1/auth/api-keys` | Generate new API key with friendly label |

---

## 2. Organizations & Teams Endpoints (`/api/v1/orgs`)

| Method | Path | Required Role | Description |
|--------|------|---------------|-------------|
| POST   | `/api/v1/orgs` | Authenticated User | Create a new Organization (Creator automatically becomes Owner) |
| GET    | `/api/v1/orgs` | Authenticated User | List all Organizations the user belongs to |
| GET    | `/api/v1/orgs/{org_id}` | Member (Any Role) | Get Organization details, branding, and settings |
| PUT    | `/api/v1/orgs/{org_id}` | Owner, Admin | Update Organization name, slug, branding, and settings |
| DELETE | `/api/v1/orgs/{org_id}` | Owner | Delete Organization and cascade all memberships/invitations |
| POST   | `/api/v1/orgs/{org_id}/transfer-ownership` | Owner | Transfer Organization ownership to another member |
| GET    | `/api/v1/orgs/{org_id}/members` | Member (Any Role) | List all organization members and their roles |
| PUT    | `/api/v1/orgs/{org_id}/members/{user_id}/role` | Owner, Admin, Manager | Update a member's role (Respecting hierarchy rules) |
| DELETE | `/api/v1/orgs/{org_id}/members/{user_id}` | Owner, Admin, Manager, Self | Remove a member or leave organization |
| POST   | `/api/v1/orgs/{org_id}/invitations` | Owner, Admin, Manager | Invite a team member by email with a assigned role |
| GET    | `/api/v1/orgs/{org_id}/invitations` | Owner, Admin, Manager | List pending organization invitations |
| POST   | `/api/v1/orgs/invitations/accept` | Authenticated User | Accept an invitation token to join an organization |
| POST   | `/api/v1/orgs/invitations/reject` | Authenticated User | Reject an invitation token |
| DELETE | `/api/v1/orgs/{org_id}/invitations/{id}` | Owner, Admin, Manager | Cancel a pending team invitation |
| GET    | `/api/v1/orgs/{org_id}/audit-logs` | Owner, Admin | View Organization audit trail events |

---

## 3. Role-Based Access Control (RBAC) Matrix

| Permission / Action | Owner | Admin | Manager | Member | Viewer |
|---------------------|:-----:|:-----:|:-------:|:------:|:------:|
| View Org & Members (`org:read`) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Update Branding & Settings (`org:update_settings`) | ✅ | ✅ | ❌ | ❌ | ❌ |
| Invite Members (`member:invite`) | ✅ | ✅ | ✅ | ❌ | ❌ |
| Manage Pending Invitations | ✅ | ✅ | ✅ | ❌ | ❌ |
| Change Member Role (`member:change_role`) | ✅ | ✅ (up to Admin) | ✅ (Member/Viewer) | ❌ | ❌ |
| Remove Member (`member:remove`) | ✅ | ✅ (non-Owner/Admin) | ✅ (Member/Viewer) | Self-only | Self-only |
| View Audit Logs (`audit:read`) | ✅ | ✅ | ❌ | ❌ | ❌ |
| Transfer Ownership (`org:transfer_ownership`) | ✅ | ❌ | ❌ | ❌ | ❌ |
| Delete Organization (`org:delete`) | ✅ | ❌ | ❌ | ❌ | ❌ |

---

## 4. System Audit Logging (`/api/v1/audit-logs`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/audit-logs` | Query, filter, search, and paginate system audit events |
| GET | `/api/v1/audit-logs/export` | Download audit logs as CSV (`format=csv`) or JSON (`format=json`) |

### Tracked Actions
- `user.login` – User login session establishment
- `user.logout` – User session termination
- `user.password_change` – Password update/reset
- `user.profile_update` – Profile or avatar modification
- `org.created` – Organization creation
- `invitation.sent` – Organization team invitation dispatched
- `invitation.accepted` – Team invitation accepted
- `role.changed` – Member role promotion/demotion
- `member.removed` – Member removal or self-exit
- `org.deleted` – Organization deletion
- `project.created` – Website/Project added
- `project.deleted` – Website/Project deleted
- `api_key.created` – API key generation
- `settings.changed` – Organization settings/branding updated

### Audit Schema (`audit_logs` table)
- `id`: Integer (Primary Key)
- `created_at`: Timestamp (ISO format, UTC)
- `user_id`: Nullable Foreign Key (`users.id`)
- `organization_id`: Nullable Foreign Key (`organizations.id`)
- `action`: String (Indexed action identifier)
- `target_resource`: String (e.g., `user:1`, `org:2`, `project:5`)
- `ip_address`: String (Client IP address)
- `user_agent`: String (Client HTTP User Agent)
- `details`: JSON Object (Contextual metadata payload)

---

## 5. System & SEO Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET    | `/health`, `/api/v1/health` | Kubernetes liveness probe check |
| GET    | `/ready`, `/api/v1/ready` | Kubernetes readiness probe (checks DB & Redis status) |
| GET    | `/metrics`, `/api/v1/metrics` | Prometheus metrics exposition format |
| GET    | `/api/v1/websites` | List tracked user websites |
| POST   | `/api/v1/audit` | Run technical SEO audit on a URL (Rate Limited) |
| GET    | `/api/v1/audit/{id}` | List saved audit results for a website |
| GET    | `/api/v1/scraper/robots` | Fetch and parse robots.txt (Redis/TTL Cached) |
| GET    | `/api/v1/scraper/sitemap` | Fetch and parse sitemap.xml (Redis/TTL Cached) |
| GET    | `/api/v1/metrics/whois` | Lookup domain WHOIS registration (Redis/TTL Cached) |
| POST   | `/api/v1/keywords` | Expand seed keyword into ideas (Rate Limited, Redis Cached) |
| POST   | `/api/v1/metrics/domain` | Domain metrics (Rate Limited, Redis Cached) |
| POST   | `/api/v1/jobs/crawl` | Enqueue async background site crawl job (Redis Queue) |
| POST   | `/api/v1/jobs/audit` | Enqueue async background technical audit job (Redis Queue) |
| POST   | `/api/v1/jobs/keywords` | Enqueue async background keyword research job (Redis Queue) |
| POST   | `/api/v1/jobs/rank` | Enqueue async background SERP rank check job (Redis Queue) |
| GET    | `/api/v1/jobs` | List user's background jobs with filtering & pagination |
| GET    | `/api/v1/jobs/{id}` | Get background job execution status & result |
| DELETE | `/api/v1/jobs/{id}` | Delete background job |
