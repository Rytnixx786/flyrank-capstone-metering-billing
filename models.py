import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, DateTime, ForeignKey, UniqueConstraint, Index, Text
)
from sqlalchemy.orm import relationship
from database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def current_utc_time() -> datetime:
    return datetime.now(timezone.utc)


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=current_utc_time)

    subscription = relationship("Subscription", back_populates="tenant", uselist=False, cascade="all, delete-orphan")
    usage_events = relationship("UsageEvent", back_populates="tenant", cascade="all, delete-orphan")


class Plan(Base):
    __tablename__ = "plans"

    id = Column(String, primary_key=True)  # e.g., 'free', 'pro'
    name = Column(String, nullable=False)
    monthly_api_limit = Column(Integer, nullable=False)
    monthly_token_limit = Column(Integer, nullable=False)
    price_cents = Column(Integer, nullable=False, default=0)

    subscriptions = relationship("Subscription", back_populates="plan")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, unique=True)
    plan_id = Column(String, ForeignKey("plans.id"), nullable=False, default="free")
    stripe_subscription_id = Column(String, nullable=True)
    status = Column(String, nullable=False, default="active")  # 'active', 'canceled', 'past_due'
    current_period_start = Column(DateTime, default=current_utc_time)
    current_period_end = Column(DateTime, nullable=True)

    tenant = relationship("Tenant", back_populates="subscription")
    plan = relationship("Plan", back_populates="subscriptions")


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    usage_type = Column(String, nullable=False)  # 'api_call', 'ai_tokens'
    quantity = Column(Integer, nullable=False)
    idempotency_key = Column(String, nullable=False)
    response_payload = Column(Text, nullable=True)  # Cached JSON payload for deduplicated retries
    timestamp = Column(DateTime, default=current_utc_time, index=True)

    tenant = relationship("Tenant", back_populates="usage_events")

    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uix_tenant_idempotency_key"),
        Index("idx_tenant_usage_type_time", "tenant_id", "usage_type", "timestamp"),
    )


class ProcessedWebhook(Base):
    __tablename__ = "processed_webhooks"

    event_id = Column(String, primary_key=True)
    event_type = Column(String, nullable=False)
    processed_at = Column(DateTime, default=current_utc_time)
