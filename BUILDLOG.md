# BUILDLOG.md — AI Build Transparency Log

Documenting engineering choices, AI assistance, corrections, and manual overrides throughout the capstone build.

---

## Phase 1: Design & Architecture (Date: 2026-08-08)

### What We Designed:
1. Multi-tenant database schema (`tenants`, `plans`, `subscriptions`, `usage_events`, `processed_webhooks`).
2. Composite unique index `UNIQUE(tenant_id, idempotency_key)` to enforce database-level idempotency and prevent double-counting under network retries.
3. Integer money math storage strategy (micro-cents / cents) to prevent floating-point rounding bugs.
4. Submission pack manifest files (`capstone.yaml`, `EVIDENCE.md`, `BUILDLOG.md`, `.env.example`).

### AI Assistance & Architectural Adjustments:
- **AI Suggested:** Storing costs as floats (`$0.0015`).
- **Correction Made:** Overrode AI suggestion to enforce integer micro-units (`150 micro-cents per token`), adhering strictly to § 14 money math standards.
- **AI Suggested:** Global idempotency key lookups across all tenants.
- **Correction Made:** Scoped idempotency composite keys to tenant isolation (`UNIQUE(tenant_id, idempotency_key)`), ensuring multi-tenant data safety.
