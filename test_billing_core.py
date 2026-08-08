import pytest
from models import UsageEvent


# ====================================================================
# PROBE 1: Exactly-Once Metering & Idempotency Guarantee
# ====================================================================
def test_probe_1_idempotent_metering_prevents_double_counting(client, db_session):
    """PROBE 1: Sending the exact same request twice with 1 idempotency key creates 1 event"""
    headers = {
        "X-Tenant-ID": "test_tenant_1",
        "Idempotency-Key": "unique_ik_001"
    }
    payload = {
        "prompt": "Test idempotency prompt",
        "input_tokens": 100,
        "output_tokens": 50
    }

    # First Request
    response1 = client.post("/api/v1/generate", json=payload, headers=headers)
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["status"] == "allowed"
    assert data1["is_cached_deduplicated"] is False

    # Second Retried Request with same Idempotency-Key
    response2 = client.post("/api/v1/generate", json=payload, headers=headers)
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["status"] == "allowed"
    assert data2["is_cached_deduplicated"] is True

    # Verify DB usage events count for this key is exactly 1
    event_count = db_session.query(UsageEvent).filter(
        UsageEvent.tenant_id == "test_tenant_1",
        UsageEvent.idempotency_key == "unique_ik_001"
    ).count()

    assert event_count == 1, "PROBE 1 FAILED: Double-counting occurred!"


# ====================================================================
# PROBE 2: Quota Boundary Honesty (At 999, 1000, 1001 Calls)
# ====================================================================
def test_probe_2_quota_boundary_at_999_1000_1001(client):
    """PROBE 2: Call at 1000 (boundary) succeeds; call at 1001 returns HTTP 429 Too Many Requests"""

    # Request at call 1000 (Tenant is currently at 999)
    headers_1000 = {
        "X-Tenant-ID": "test_tenant_boundary",
        "Idempotency-Key": "ik_call_1000"
    }
    payload = {"prompt": "Boundary call 1000", "input_tokens": 10, "output_tokens": 10}

    res_1000 = client.post("/api/v1/generate", json=payload, headers=headers_1000)
    assert res_1000.status_code == 200, f"Call 1000 failed unexpectedly: {res_1000.text}"
    assert res_1000.json()["status"] == "allowed"

    # Request at call 1001 (Quota exceeded)
    headers_1001 = {
        "X-Tenant-ID": "test_tenant_boundary",
        "Idempotency-Key": "ik_call_1001"
    }
    res_1001 = client.post("/api/v1/generate", json=payload, headers=headers_1001)

    assert res_1001.status_code == 429, f"PROBE 2 FAILED: Expected HTTP 429, got {res_1001.status_code}"
    assert "Retry-After" in res_1001.headers
    data_1001 = res_1001.json()
    assert data_1001["error"]["code"] == "quota_exceeded"
    assert "quota exceeded" in data_1001["error"]["message"].lower()


# ====================================================================
# TEST: Lapsed Plan Refusal (HTTP 402 Payment Required)
# ====================================================================
def test_lapsed_subscription_returns_http_402(client):
    """Verify that a tenant with canceled/past_due status returns HTTP 402 Payment Required"""
    headers = {
        "X-Tenant-ID": "test_tenant_lapsed",
        "Idempotency-Key": "ik_lapsed_001"
    }
    payload = {"prompt": "Lapsed test prompt", "input_tokens": 10, "output_tokens": 10}

    response = client.post("/api/v1/generate", json=payload, headers=headers)
    assert response.status_code == 402
    data = response.json()
    assert data["error"]["code"] == "payment_required"


# ====================================================================
# TEST: Usage Rollup Endpoint (GET /api/v1/usage)
# ====================================================================
def test_get_usage_rollup(client):
    """Verify GET /api/v1/usage returns current month rollup"""
    headers = {"X-Tenant-ID": "test_tenant_boundary"}
    response = client.get("/api/v1/usage", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == "test_tenant_boundary"
    assert data["api_calls"]["used"] == 999
    assert data["api_calls"]["limit"] == 1000
