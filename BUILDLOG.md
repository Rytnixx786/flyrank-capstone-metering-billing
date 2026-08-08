# BUILDLOG.md — AI Build Transparency Log

Documenting engineering choices, AI assistance, corrections, and manual overrides throughout the capstone build.

---

## Phase 1: Design & Architecture (Date: 2026-08-08)

### What We Designed:
1. Multi-tenant database schema (`tenants`, `plans`, `subscriptions`, `usage_events`, `processed_webhooks`).
2. Composite unique index `UNIQUE(tenant_id, idempotency_key)` to enforce database-level idempotency and prevent double-counting under network retries.
3. Integer money math storage strategy (micro-cents / cents) to prevent floating-point rounding bugs.
4. Submission pack manifest files (`capstone.yaml`, `EVIDENCE.md`, `BUILDLOG.md`, `.env.example`).

---

## Phase 2: Core Billing Logic & Idempotency (Date: 2026-08-08)

### What We Built:
1. `models.py` & `database.py`: Built SQLAlchemy ORM models with SQLite/PostgreSQL engine support and unique composite index on `(tenant_id, idempotency_key)`.
2. `metering_service.py`: Implemented atomic `MeterService.record_usage_event` handling fast-path cached deduplication and database-level constraint handling.
3. `quota_service.py`: Implemented `QuotaService` evaluating monthly usage against plan quotas (`Free`: 1k calls / 100k tokens; `Pro`: 100k calls / 10M tokens).
4. `app.py`: Created FastAPI endpoints `POST /api/v1/generate` and `GET /api/v1/usage` enforcing HTTP `429` (Too Many Requests with `Retry-After`) and HTTP `402` (Payment Required).
5. `test_billing_core.py`: Wrote automated test suite verifying **Probe 1 (Idempotent Deduplication)** and **Probe 2 (Quota Boundary at 999, 1000, 1001 calls)**. 100% green test pass in 0.59s.

### AI Assistance & Engineering Decisions:
- **AI Suggested:** Global idempotency key lookups.
- **Correction Made:** Enforced tenant-scoped idempotency keys `UNIQUE(tenant_id, idempotency_key)` to prevent cross-tenant key collision attacks.
- **AI Suggested:** Generic HTTP 400 for quota errors.
- **Correction Made:** Enforced semantic status codes (**HTTP 429** for quota limits with `Retry-After` header, **HTTP 402** for lapsed plans) per § 4 specification.
