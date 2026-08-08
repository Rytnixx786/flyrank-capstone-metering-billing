# DEMO_GUIDE.md — The 6-Minute Failure Demo Presentation Script (§ 13)

This presentation script guides you through demonstrating the **Usage Metering & Billing Engine Capstone** to a technical mentor or evaluator. A demo that shows **one failure handled gracefully** impresses more than ten happy paths.

---

## ⏱️ Timeline & Step-by-Step Presentation Script

### 🕒 0:00 – 1:00 | Step 1: Quota Boundary Enforcement (HTTP 429 Refusal)
* **Goal:** Prove that quota enforcement is exact at the boundary and returns honest status codes.
* **Demonstration Action:**
  1. Seed tenant `tenant_near_quota` to 999 API calls: `python seed.py`
  2. Send call #1,000 (at the boundary limit):
     ```bash
     curl -X POST "http://localhost:8000/api/v1/generate" \
       -H "X-Tenant-ID: tenant_near_quota" \
       -H "Idempotency-Key: ik_demo_1000" \
       -H "Content-Type: application/json" \
       -d '{"prompt": "Boundary call 1000", "input_tokens": 10, "output_tokens": 10}'
     ```
     *Response:* `HTTP 200 OK` `{"status": "allowed"}`
  3. Send call #1,001 (exceeding quota limit):
     ```bash
     curl -X POST "http://localhost:8000/api/v1/generate" \
       -H "X-Tenant-ID: tenant_near_quota" \
       -H "Idempotency-Key: ik_demo_1001" \
       -H "Content-Type: application/json" \
       -d '{"prompt": "Boundary call 1001", "input_tokens": 10, "output_tokens": 10}'
     ```
     *Response:* `HTTP 429 Too Many Requests` + Header `Retry-After: 3600`
* **What to Say:**
  > *"Notice how at call 1,000 of our 1,000 Free limit, the system allowed the request. But at call 1,001, the API returned an honest HTTP 429 Too Many Requests status code with a Retry-After header explaining exactly why the request was blocked."*

---

### 🕒 1:00 – 2:15 | Step 2: Idempotent Metering (Zero Double-Count Guarantee)
* **Goal:** Prove that retrying a network request with the same idempotency key never creates duplicate usage events or double-charges quota.
* **Demonstration Action:**
  1. Send first billable request for `tenant_free`:
     ```bash
     curl -X POST "http://localhost:8000/api/v1/generate" \
       -H "X-Tenant-ID: tenant_free" \
       -H "Idempotency-Key: ik_demo_retry_key" \
       -H "Content-Type: application/json" \
       -d '{"prompt": "Idempotent test prompt", "input_tokens": 500, "output_tokens": 200}'
     ```
     *Response:* `HTTP 200 OK` `{"is_cached_deduplicated": false}`
  2. Simulate a network retry by sending the exact same request with `Idempotency-Key: ik_demo_retry_key`:
     ```bash
     curl -X POST "http://localhost:8000/api/v1/generate" \
       -H "X-Tenant-ID: tenant_free" \
       -H "Idempotency-Key: ik_demo_retry_key" \
       -H "Content-Type: application/json" \
       -d '{"prompt": "Idempotent test prompt", "input_tokens": 500, "output_tokens": 200}'
     ```
     *Response:* `HTTP 200 OK` `{"is_cached_deduplicated": true}`
* **What to Say:**
  > *"When the client retries the request with the same idempotency key, the database composite constraint `UNIQUE(tenant_id, idempotency_key)` catches it. The service returns the cached response instantly with `is_cached_deduplicated: true`. Exactly one usage event row exists in the database, guaranteeing zero double-counting under network retries."*

---

### 🕒 2:15 – 3:30 | Step 3: Stripe Test Checkout & Live Webhook Plan Sync
* **Goal:** Demonstrate upgrading a tenant from `Free` ➔ `Pro` via a Stripe checkout webhook.
* **Demonstration Action:**
  1. Check current Free plan limits:
     ```bash
     curl -X GET "http://localhost:8000/api/v1/usage" -H "X-Tenant-ID: tenant_free"
     ```
     *Output:* `plan_id: "free"`, `limit: 1000`
  2. Simulate Stripe `checkout.session.completed` webhook event:
     ```bash
     curl -X POST "http://localhost:8000/api/v1/webhooks/stripe" \
       -H "Stripe-Signature: t=valid_test_signature" \
       -H "Content-Type: application/json" \
       -d '{"id": "evt_demo_checkout_500", "type": "checkout.session.completed", "data": {"object": {"client_reference_id": "tenant_free", "subscription": "sub_demo_123", "metadata": {"tenant_id": "tenant_free", "plan_id": "pro"}}}}'
     ```
  3. Re-query usage:
     ```bash
     curl -X GET "http://localhost:8000/api/v1/usage" -H "X-Tenant-ID: tenant_free"
     ```
     *Output:* `plan_id: "pro"`, `limit: 100000`, `estimated_cost_cents: 2900`
* **What to Say:**
  > *"The moment Stripe completes the Checkout session, the webhook handler updates the tenant's subscription. Re-querying `/api/v1/usage` shows `tenant_free` is live on the Pro plan with 100,000 API calls and $29/mo pricing."*

---

### 🕒 3:30 – 4:45 | Step 4: Webhook Security & Replay Deduplication (The Forged Webhook Moment)
* **Goal:** Prove that forged webhooks are rejected with HTTP 400 and replayed events process once.
* **Demonstration Action:**
  1. Send a forged webhook with a fake signature:
     ```bash
     curl -X POST "http://localhost:8000/api/v1/webhooks/stripe" \
       -H "Stripe-Signature: t=test_signature_forged" \
       -H "Content-Type: application/json" \
       -d '{"id": "evt_forged_attack", "type": "checkout.session.completed"}'
     ```
     *Response:* `HTTP 400 Bad Request` `"Invalid Stripe webhook signature."`
  2. Replay an already processed webhook event ID (`evt_demo_checkout_500`):
     ```bash
     curl -X POST "http://localhost:8000/api/v1/webhooks/stripe" \
       -H "Stripe-Signature: t=valid_test_signature" \
       -H "Content-Type: application/json" \
       -d '{"id": "evt_demo_checkout_500", "type": "checkout.session.completed", "data": {"object": {"client_reference_id": "tenant_free", "metadata": {"plan_id": "pro"}}}}'
     ```
     *Response:* `HTTP 200 OK` `{"processed": false, "message": "Event 'evt_demo_checkout_500' already processed."}`
* **What to Say:**
  > *"Security is verified on raw request bytes. Forged signatures are rejected with HTTP 400. Replaying a valid webhook event ID is caught by our ProcessedWebhook table, ignoring the duplicate cleanly without side effects."*

---

### 🕒 4:45 – 5:30 | Step 5: Exact Money Math & Rollup Verification
* **Goal:** Show `GET /api/v1/usage` rollups adding up with penny precision.
* **Demonstration Action:**
  1. Run GET `/api/v1/usage`:
     ```bash
     curl -X GET "http://localhost:8000/api/v1/usage" -H "X-Tenant-ID: tenant_free"
     ```
* **What to Say:**
  > *"All token categories—fresh input, 50% discounted cached input, output, and reasoning tokens—are tracked as integer micro-cents. There are zero floating-point rounding errors."*

---

### 🕒 5:30 – 6:00 | Step 6: Closing Statement (§ 13)
* **Closing Line:**
  > **"Usage, money, and customer access stay correct under retries, failures, and real-world conditions."**
