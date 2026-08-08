import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from app import app
from models import Tenant, Plan, Subscription, UsageEvent

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


@pytest.fixture(scope="session")
def test_engine():
    return engine


@pytest.fixture(autouse=True)
def setup_test_db(test_engine):
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()

    # Clear previous data
    db.query(UsageEvent).delete()
    db.query(Subscription).delete()
    db.query(Tenant).delete()
    db.query(Plan).delete()
    db.commit()

    # Seed plans
    plan_free = Plan(id="free", name="Free Plan", monthly_api_limit=1000, monthly_token_limit=100000, price_cents=0)
    plan_pro = Plan(id="pro", name="Pro Plan", monthly_api_limit=100000, monthly_token_limit=10000000, price_cents=2900)
    db.add_all([plan_free, plan_pro])

    # Seed tenants
    t1 = Tenant(id="test_tenant_1", name="Active Tenant")
    s1 = Subscription(tenant_id="test_tenant_1", plan_id="free", status="active")

    t2 = Tenant(id="test_tenant_lapsed", name="Lapsed Tenant")
    s2 = Subscription(tenant_id="test_tenant_lapsed", plan_id="free", status="canceled")

    t3 = Tenant(id="test_tenant_boundary", name="Boundary Tenant")
    s3 = Subscription(tenant_id="test_tenant_boundary", plan_id="free", status="active")
    u3 = UsageEvent(
        tenant_id="test_tenant_boundary",
        usage_type="api_call",
        quantity=999,
        idempotency_key="initial_seed_999",
        response_payload='{"status": "seeded"}'
    )

    t4 = Tenant(id="test_tenant_free", name="Free Plan Tenant")
    s4 = Subscription(tenant_id="test_tenant_free", plan_id="free", status="active")

    db.add_all([t1, s1, t2, s2, t3, s3, u3, t4, s4])
    db.commit()
    db.close()

    yield

    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    return TestClient(app)
