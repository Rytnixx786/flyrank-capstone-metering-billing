import pytest


# ====================================================================
# PROBE 3: Stripe Test Checkout flips Tenant Free -> Pro via Webhook
# ====================================================================
def test_probe_3_stripe_checkout_flips_tenant_free_to_pro(client):
    """PROBE 3: Completed Stripe Checkout webhook updates tenant plan from Free to Pro"""
    headers = {"X-Tenant-ID": "test_tenant_free"}

    # 1. Verify initial state is Free plan (1,000 API calls)
    res_before = client.get("/api/v1/usage", headers=headers)
    assert res_before.status_code == 200
    assert res_before.json()["plan_id"] == "free"
    assert res_before.json()["api_calls"]["limit"] == 1000

    # 2. Simulate Stripe checkout.session.completed webhook
    webhook_event = {
        "id": "evt_test_checkout_100",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_session_100",
                "client_reference_id": "test_tenant_free",
                "subscription": "sub_test_stripe_100",
                "metadata": {"tenant_id": "test_tenant_free", "plan_id": "pro"}
            }
        }
    }
    webhook_headers = {"Stripe-Signature": "t=valid_test_signature"}

    res_webhook = client.post("/api/v1/webhooks/stripe", json=webhook_event, headers=webhook_headers)
    assert res_webhook.status_code == 200, f"Webhook failed: {res_webhook.text}"
    assert res_webhook.json()["processed"] is True

    # 3. Verify tenant plan is flipped to Pro (100,000 API calls / $29 cost)
    res_after = client.get("/api/v1/usage", headers=headers)
    assert res_after.status_code == 200
    data_after = res_after.json()
    assert data_after["plan_id"] == "pro"
    assert data_after["api_calls"]["limit"] == 100000
    assert data_after["estimated_cost_cents"] == 2900


# ====================================================================
# PROBE 4: Forged Webhook Rejection & Event Replay Deduplication
# ====================================================================
def test_probe_4_forged_webhook_rejected_and_replay_deduplicated(client):
    """PROBE 4: Forged webhook returns 400. Replayed real event is processed exactly once."""

    # 1. Forged Webhook Rejection (Bad Signature)
    forged_event = {
        "id": "evt_forged_999",
        "type": "checkout.session.completed",
        "data": {"object": {"client_reference_id": "test_tenant_free", "metadata": {"plan_id": "pro"}}}
    }
    forged_headers = {"Stripe-Signature": "t=test_signature_forged"}

    res_forged = client.post("/api/v1/webhooks/stripe", json=forged_event, headers=forged_headers)
    assert res_forged.status_code == 400, f"PROBE 4 FAILED: Forged webhook allowed! {res_forged.text}"

    # 2. Replay Protection (Send same event twice)
    valid_event = {
        "id": "evt_replay_test_200",
        "type": "checkout.session.completed",
        "data": {"object": {"client_reference_id": "test_tenant_free", "metadata": {"plan_id": "pro"}}}
    }
    valid_headers = {"Stripe-Signature": "t=valid_test_signature"}

    # First delivery
    res_first = client.post("/api/v1/webhooks/stripe", json=valid_event, headers=valid_headers)
    assert res_first.status_code == 200
    assert res_first.json()["processed"] is True

    # Replayed second delivery
    res_replay = client.post("/api/v1/webhooks/stripe", json=valid_event, headers=valid_headers)
    assert res_replay.status_code == 200
    assert res_replay.json()["processed"] is False
    assert "already processed" in res_replay.json()["message"]


# ====================================================================
# TEST: Stripe Checkout Session Endpoint
# ====================================================================
def test_create_checkout_session_endpoint(client):
    """Verify POST /api/v1/checkout/session returns session payload"""
    headers = {"X-Tenant-ID": "test_tenant_free"}
    response = client.post("/api/v1/checkout/session?plan_id=pro", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert "checkout_url" in data
    assert data["tenant_id"] == "test_tenant_free"
    assert data["plan_id"] == "pro"
