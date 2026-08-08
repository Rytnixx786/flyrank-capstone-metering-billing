import os
import logging
from datetime import datetime, timezone
from database import SessionLocal, init_db
from models import Tenant, Plan, Subscription, UsageEvent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SeedScript")


def seed_database():
    init_db()
    db = SessionLocal()

    try:
        # 1. Create Default Plans
        plans_data = [
            {
                "id": "free",
                "name": "Free Tier",
                "monthly_api_limit": 1000,
                "monthly_token_limit": 100000,
                "price_cents": 0
            },
            {
                "id": "pro",
                "name": "Pro Tier",
                "monthly_api_limit": 100000,
                "monthly_token_limit": 10000000,
                "price_cents": 2900  # $29.00 / month
            }
        ]

        for p_data in plans_data:
            existing_plan = db.query(Plan).filter(Plan.id == p_data["id"]).first()
            if not existing_plan:
                plan = Plan(**p_data)
                db.add(plan)
                logger.info(f"Created Plan: {plan.id}")

        db.commit()

        # 2. Create Demo Tenants
        tenants_data = [
            {"id": "tenant_free", "name": "Free Tier Tenant", "plan_id": "free", "status": "active"},
            {"id": "tenant_pro", "name": "Pro Tier Tenant", "plan_id": "pro", "status": "active"},
            {"id": "tenant_lapsed", "name": "Lapsed Tenant", "plan_id": "free", "status": "canceled"},
            {"id": "tenant_near_quota", "name": "Boundary Tenant", "plan_id": "free", "status": "active"}
        ]

        for t_data in tenants_data:
            existing_tenant = db.query(Tenant).filter(Tenant.id == t_data["id"]).first()
            if not existing_tenant:
                tenant = Tenant(id=t_data["id"], name=t_data["name"])
                db.add(tenant)
                db.flush()

                subscription = Subscription(
                    tenant_id=tenant.id,
                    plan_id=t_data["plan_id"],
                    status=t_data["status"]
                )
                db.add(subscription)
                logger.info(f"Created Tenant: {tenant.id} with Plan: {t_data['plan_id']} ({t_data['status']})")

        db.commit()

        # 3. Seed tenant_near_quota to exactly 999 API calls
        near_quota_tenant = db.query(Tenant).filter(Tenant.id == "tenant_near_quota").first()
        if near_quota_tenant:
            # Check existing usage count
            existing_count = db.query(UsageEvent).filter(
                UsageEvent.tenant_id == "tenant_near_quota",
                UsageEvent.usage_type == "api_call"
            ).count()

            if existing_count < 999:
                needed = 999 - existing_count
                event = UsageEvent(
                    tenant_id="tenant_near_quota",
                    usage_type="api_call",
                    quantity=needed,
                    idempotency_key="seed_boundary_api_calls",
                    response_payload='{"status": "seeded"}'
                )
                db.add(event)
                db.commit()
                logger.info(f"Seeded 'tenant_near_quota' with {needed} API calls (Total: 999/1000).")

        logger.info("Database seeding completed successfully.")

    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
