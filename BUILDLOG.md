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

---

## Phase 3: Stripe Integration & Webhooks (Date: 2026-08-08)

### What We Built:
1. `stripe_service.py`: Built `StripeService` handling Stripe Checkout session generation, HMAC-SHA256 signature verification (`Stripe-Signature`), raw body parsing, and event deduplication via `ProcessedWebhook`.
2. `app.py`: Added endpoints `POST /api/v1/checkout/session` and `POST /api/v1/webhooks/stripe`.
3. `test_stripe_integration.py`: Wrote automated test suite verifying **Probe 3 (Checkout webhook flips tenant Free -> Pro)** and **Probe 4 (Forged webhook 400 rejection & replay deduplication)**.
4. 100% green test pass across full suite (7/7 tests passing in 0.97s).

---

## Phase 4: Cost Calculation & AI-Token Rules (Date: 2026-08-08)

### What We Built:
1. `pricing_config.py`: Defined pinned pricing constants in micro-cents (`INPUT`: 150/1k, `CACHED`: 75/1k, `OUTPUT`: 600/1k, `REASONING`: 600/1k) and integer ceiling rounding conversion helper.
2. `models.py` & `metering_service.py`: Extended `UsageEvent` model and `MeterService` to record detailed token breakdown categories and cost micro-cents.
3. `app.py`: Updated `POST /api/v1/generate` and `GET /api/v1/usage` to return token category breakdowns and exact micro-cent rollups.
4. `test_cost_calculation.py`: Wrote automated test suite verifying **Probe 5 (Pinned pricing rules for cached inputs and reasoning tokens)**.
5. `EVIDENCE.md`: Checked off 100% of Definition-of-Done requirements with pasted proof logs across all 5 Probes. 9/9 tests passing in 1.03s.
