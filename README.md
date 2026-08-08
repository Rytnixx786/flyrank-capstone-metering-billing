# Usage Metering & Billing Engine (`flyrank-capstone-metering-billing`)

> **FlyRank Internship · Backend AI Engineering Track · Capstone**  
> An idempotent, multi-tenant usage metering, quota enforcement, and Stripe-integrated billing service.

---

## 🏛️ 1. Architecture Overview

The system processes three distinct execution paths: **Metering & Quota Path**, **Usage Rollup Path**, and **Stripe Webhook Sync Path**.

```text
Client ──► POST /api/v1/generate (Billable Request)
            │  Headers: X-Tenant-ID, Idempotency-Key
            │
            ├─► 1. MeterService.record(tenant, type, qty, idempotencyKey)
            │      ├─ Duplicate Key? ➔ Return original cached payload (0 new events)
            │      └─ New Key? ➔ Atomically store usage_event
            │
            └─► 2. QuotaCheck.verify(tenant, requestedQty)
                   ├─ Allowed (Usage <= Limit) ➔ Allow billable action
                   ├─ Exceeded Quota ➔ HTTP 429 Too Many Requests
                   └─ Lapsed Subscription ➔ HTTP 402 Payment Required

Client ──► GET /api/v1/usage (Rollup Read Path)
            └─► Aggregates usage_events ➔ Returns { used, limit, cost_cents }

Stripe (Test Mode) ──► Signed Webhook ──► POST /api/v1/webhooks/stripe
                            ├─ Verify Signature (whsec_...) ➔ Forged ➔ HTTP 400
                            ├─ Check Event Deduplication ➔ Replayed ➔ Ignored
                            └─ Sync Tenant Plan ➔ Update Free ➔ Pro
```

---

## 🗄️ 2. Multi-Tenant Data Model

All customer data is isolated per tenant. Money amounts and token costs are stored strictly as **Integers (cents / micro-units)** to prevent floating-point rounding errors.

```text
+-------------------+           +-------------------+           +-----------------------+
|     tenants       |           |   subscriptions   |           |         plans         |
+-------------------+           +-------------------+           +-----------------------+
| id (PK)           | 1       * | id (PK)           | *       1 | id (PK: 'free','pro') |
| name              | <-------- | tenant_id (FK)    | --------> | name                  |
| created_at        |           | plan_id (FK)      |           | monthly_api_limit     |
+-------------------+           | stripe_sub_id     |           | monthly_token_limit   |
          |                     | status ('active') |           | price_cents           |
          | 1                   +-------------------+           +-----------------------+
          |
          | *                   +-------------------+
          +-------------------> |   usage_events    |
                                +-------------------+
                                | id (PK)           |
                                | tenant_id (FK)    |
                                | usage_type        |
                                | quantity          |
                                | idempotency_key   |  <=== UNIQUE INDEX(tenant_id, idempotency_key)
                                | timestamp         |
                                +-------------------+
```

---

## 🔌 3. API Specifications & Contracts

### 1. Billable Action: `POST /api/v1/generate`
- **Headers:** `X-Tenant-ID: <tenant_id>`, `Idempotency-Key: <unique_key>`
- **Request Payload:**
  ```json
  {
    "prompt": "Analyze dataset query",
    "input_tokens": 1000,
    "cached_input_tokens": 400,
    "output_tokens": 500,
    "reasoning_tokens": 100
  }
  ```
- **Responses:**
  - `200 OK`: Billable action approved & metered.
  - `429 Too Many Requests`: Usage quota exceeded.
  - `402 Payment Required`: Plan upgrade / subscription renewal required.

### 2. Usage Rollup: `GET /api/v1/usage`
- **Headers:** `X-Tenant-ID: <tenant_id>`
- **Response Payload:**
  ```json
  {
    "tenant_id": "tenant_123",
    "plan_id": "free",
    "period": "2026-08",
    "api_calls": { "used": 450, "limit": 1000 },
    "ai_tokens": { "used": 45000, "limit": 100000 },
    "token_breakdown": {
      "input_tokens": 1000,
      "cached_input_tokens": 400,
      "output_tokens": 500,
      "reasoning_tokens": 100
    },
    "usage_cost_micro_cents": 900,
    "estimated_cost_cents": 1
  }
  ```

### 3. Stripe Checkout Session: `POST /api/v1/checkout/session`
- **Headers:** `X-Tenant-ID: <tenant_id>`
- **Query Params:** `plan_id=pro`

### 4. Stripe Webhook: `POST /api/v1/webhooks/stripe`
- **Headers:** `Stripe-Signature: t=...,v1=...`
- **Events Handled:** `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`.

---

## 🎤 4. 6-Minute Failure Demo Presentation Script (§ 13)
The complete step-by-step presentation script for human and evaluator demos is documented in [`DEMO_GUIDE.md`](DEMO_GUIDE.md).

---

## 🛠️ 5. Setup & Running Instructions

### 1. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run System & Open Swagger UI
```bash
python app.py
```
Open [http://localhost:8000/docs](http://localhost:8000/docs) in your browser.

### 4. Run Test Suite
```bash
python -m pytest -v
```

---

## 🚫 6. Non-Goals Definition (§ 7)
- **No Real Payments:** Runs in Stripe Test Mode only (`4242 4242 4242 4242`).
- **No Real LLM API Calls:** Token counts are simulated in the API body.
- **No Invoicing or Proration in Core:** Core scope focuses strictly on correctness, idempotency, boundary honesty, and webhook sync.
