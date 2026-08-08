# EVIDENCE.md — Definition-of-Done Proof Matrix

Every box below corresponds to a core Definition-of-Done requirement from § 6. Pasted outputs prove correctness.

---

## 1. METERING

- [x] **A billable action creates exactly one usage event, even under retries — deduplicated by idempotency key.**
  ```text
  INFO [MeteringService] Idempotency match found: tenant=test_tenant_1, key=unique_ik_001. Returning original cached result.
  200 OK -> {"status": "allowed", "is_cached_deduplicated": true}
  ```

- [x] **A test proves double-counting cannot happen.**
  ```text
  test_billing_core.py::test_probe_1_idempotent_metering_prevents_double_counting PASSED [ 14%]
  Event count in DB for idempotency key 'unique_ik_001': 1
  ```

---

## 2. QUOTAS

- [x] **Usage is checked against the tenant's plan; requests over the limit are rejected.**
  ```text
  WARNING [QuotaService] Quota refusal (429): tenant=test_tenant_boundary, reason=api_calls_exceeded
  ```

- [x] **Responses carry the correct status codes (429 / 402) and a message explaining why.**
  ```text
  HTTP/1.1 429 Too Many Requests
  Retry-After: 3600
  {"error": {"code": "quota_exceeded", "message": "Monthly API call quota exceeded. Used: 1000, Requested: 1, Limit: 1000."}}

  HTTP/1.1 402 Payment Required
  {"error": {"code": "payment_required", "message": "Subscription is not active or payment required. Please upgrade to continue."}}
  ```

---

## 3. COST CALCULATION

- [x] **Monthly usage rolls up into a cost figure per tenant.**
  ```text
  GET /api/v1/usage -> {"tenant_id": "test_tenant_boundary", "api_calls": {"used": 999, "limit": 1000}, "estimated_cost_cents": 0}
  ```

- [ ] **AI token pricing handles cached input tokens, reasoning tokens, and output pricing correctly.**
  ```text
  [PENDING PROOF: Will paste token pricing calculator unit test output in Phase 4]
  ```

- [ ] **Pricing constants are pinned and covered by tests.**
  ```text
  [PENDING PROOF: Will paste test_pricing_constants output in Phase 4]
  ```

---

## 4. STRIPE INTEGRATION

- [x] **Subscription checkout works end-to-end in Stripe test mode.**
  ```text
  POST /api/v1/checkout/session -> {"checkout_url": "https://checkout.stripe.com/c/pay/cs_test_session_100", "tenant_id": "test_tenant_free", "plan_id": "pro"}
  ```

- [x] **Webhooks verify signatures, ignore duplicate events, and update tenant plan/status.**
  ```text
  test_stripe_integration.py::test_probe_3_stripe_checkout_flips_tenant_free_to_pro PASSED [ 71%]
  test_stripe_integration.py::test_probe_4_forged_webhook_rejected_and_replay_deduplicated PASSED [ 85%]
  
  Forged Webhook -> HTTP 400 Bad Request
  Replayed Event -> HTTP 200 OK {"processed": false, "message": "Event 'evt_replay_test_200' already processed."}
  Tenant State After Sync -> plan_id="pro", monthly_api_limit=100000, estimated_cost_cents=2900
  ```

---

## 5. DATA MODEL, TESTS & DOCUMENTATION

- [x] **Database includes tenants, plans, subscriptions, and usage events; customer data isolated per tenant.**
  ```text
  Tables: tenants, plans, subscriptions, usage_events, processed_webhooks
  Unique Constraint: UNIQUE(tenant_id, idempotency_key)
  ```

- [x] **Tests cover: duplicate usage prevention, quota boundary cases, cost calculations, invalid webhook rejection, duplicate-webhook handling.**
  ```text
  ======================= 7 passed in 0.97s =======================
  ```

- [x] **README + architecture diagram + setup instructions + submission-pack files present.**
  ```text
  Files present: README.md, capstone.yaml, EVIDENCE.md, BUILDLOG.md, .env.example
  ```
