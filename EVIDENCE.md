# EVIDENCE.md — Definition-of-Done Proof Matrix

Every box below corresponds to a core Definition-of-Done requirement from § 6. Pasted outputs prove correctness.

---

## 1. METERING

- [ ] **A billable action creates exactly one usage event, even under retries — deduplicated by idempotency key.**
  ```text
  [PENDING PROOF: Will paste curl transcript or unit test log in Phase 2]
  ```

- [ ] **A test proves double-counting cannot happen.**
  ```text
  [PENDING PROOF: Will paste pytest execution output for test_idempotent_metering]
  ```

---

## 2. QUOTAS

- [ ] **Usage is checked against the tenant's plan; requests over the limit are rejected.**
  ```text
  [PENDING PROOF: Will paste quota enforcement logs in Phase 2]
  ```

- [ ] **Responses carry the correct status codes (429 / 402) and a message explaining why.**
  ```text
  [PENDING PROOF: Will paste HTTP 429 & HTTP 402 JSON responses]
  ```

---

## 3. COST CALCULATION

- [ ] **Monthly usage rolls up into a cost figure per tenant.**
  ```text
  [PENDING PROOF: Will paste GET /api/v1/usage rollup JSON]
  ```

- [ ] **AI token pricing handles cached input tokens, reasoning tokens, and output pricing correctly.**
  ```text
  [PENDING PROOF: Will paste token pricing calculator unit test output]
  ```

- [ ] **Pricing constants are pinned and covered by tests.**
  ```text
  [PENDING PROOF: Will paste test_pricing_constants output]
  ```

---

## 4. STRIPE INTEGRATION

- [ ] **Subscription checkout works end-to-end in Stripe test mode.**
  ```text
  [PENDING PROOF: Will paste Stripe CLI trigger transcript]
  ```

- [ ] **Webhooks verify signatures, ignore duplicate events, and update tenant plan/status.**
  ```text
  [PENDING PROOF: Will paste forged vs valid webhook test log in Phase 3]
  ```

---

## 5. DATA MODEL, TESTS & DOCUMENTATION

- [ ] **Database includes tenants, plans, subscriptions, and usage events; customer data isolated per tenant.**
  ```text
  [PENDING PROOF: Will paste schema migrations or table inspection]
  ```

- [ ] **Tests cover: duplicate usage prevention, quota boundary cases, cost calculations, invalid webhook rejection, duplicate-webhook handling.**
  ```text
  [PENDING PROOF: Will paste 100% green test suite summary in Phase 4]
  ```

- [ ] **README + architecture diagram + setup instructions + submission-pack files present.**
  ```text
  [PENDING PROOF: Will confirm submission pack file list]
  ```
