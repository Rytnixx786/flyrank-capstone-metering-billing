import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from app import app
from models import Tenant, Plan, Subscription, UsageEvent

# Setup in-memory test database with StaticPool to keep connection open in SQLite
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    # Seed plans
    plan_free = Plan(id="free", name="Free Plan", monthly_api_limit=1000, monthly_token_limit=100000, price_cents=0)
    plan_pro = Plan(id="pro", name="Pro Plan", monthly_api_limit=100000, monthly_token_limit=10000000, price_cents=2900)
    db.add_all([plan_free, plan_pro])

    # Seed tenant 1: active free tenant
    t1 = Tenant(id="test_tenant_1", name="Active Tenant")
    s1 = Subscription(tenant_id="test_tenant_1", plan_id="free", status="active")
    db.add_all([t1, s1])

    # Seed tenant 2: lapsed tenant
    t2 = Tenant(id="test_tenant_lapsed", name="Lapsed Tenant")
    s2 = Subscription(tenant_id="test_tenant_lapsed", plan_id="free", status="canceled")
    db.add_all([t2, s2])

    # Seed tenant 3: tenant at 999 API calls (near quota boundary)
    t3 = Tenant(id="test_tenant_boundary", name="Boundary Tenant")
    s3 = Subscription(tenant_id="test_tenant_boundary", plan_id="free", status="active")
    u3 = UsageEvent(
        tenant_id="test_tenant_boundary",
        usage_type="api_call",
        quantity=999,
        idempotency_key="initial_seed_999",
        response_payload='{"status": "seeded"}'
    )
    db.add_all([t3, s3, u3])

    db.commit()
    db.close()

    yield

    Base.metadata.drop_all(bind=engine)


# ====================================================================
# PROBE 1: Exactly-Once Metering & Idempotency Guarantee
# ====================================================================
def test_probe_1_idempotent_metering_prevents_double_counting():
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
    db = TestingSessionLocal()
    event_count = db.query(UsageEvent).filter(
        UsageEvent.tenant_id == "test_tenant_1",
        UsageEvent.idempotency_key == "unique_ik_001"
    ).count()
    db.close()

    assert event_count == 1, "PROBE 1 FAILED: Double-counting occurred!"


# ====================================================================
# PROBE 2: Quota Boundary Honesty (At 999, 1000, 1001 Calls)
# ====================================================================
def test_probe_2_quota_boundary_at_999_1000_1001():
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
def test_lapsed_subscription_returns_http_402():
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
def test_get_usage_rollup():
    """Verify GET /api/v1/usage returns current month rollup"""
    headers = {"X-Tenant-ID": "test_tenant_boundary"}
    response = client.get("/api/v1/usage", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == "test_tenant_boundary"
    assert data["api_calls"]["used"] == 999
    assert data["api_calls"]["limit"] == 1000
