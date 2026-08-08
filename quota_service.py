import logging
from typing import Tuple, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from models import Tenant, Subscription, Plan
from metering_service import MeterService

logger = logging.getLogger("QuotaService")


class QuotaDecision:
    ALLOW = "ALLOW"
    EXCEEDED_QUOTA = "EXCEEDED_QUOTA"
    PAYMENT_REQUIRED = "PAYMENT_REQUIRED"


class QuotaService:

    @staticmethod
    def evaluate_request(
        db: Session,
        tenant_id: str,
        requested_api_calls: int = 1,
        requested_tokens: int = 0
    ) -> Tuple[str, Optional[str], Dict[str, Any]]:
        """
        Evaluate if a request should be allowed, blocked by quota (429), or blocked by payment (402).
        Returns Tuple[decision, error_message, usage_metrics]
        """
        # 1. Fetch Tenant Subscription & Plan
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            return QuotaDecision.PAYMENT_REQUIRED, f"Tenant '{tenant_id}' not found.", {}

        subscription = db.query(Subscription).filter(Subscription.tenant_id == tenant_id).first()
        if not subscription or subscription.status != "active":
            return (
                QuotaDecision.PAYMENT_REQUIRED,
                "Subscription is not active or payment required. Please upgrade to continue.",
                {"status": subscription.status if subscription else "no_subscription"}
            )

        plan = db.query(Plan).filter(Plan.id == subscription.plan_id).first()
        if not plan:
            plan = db.query(Plan).filter(Plan.id == "free").first()

        # 2. Fetch Current Calendar Month Usage
        now = datetime.now(timezone.utc)
        current_usage = MeterService.get_monthly_usage_summary(db, tenant_id, now.year, now.month)

        used_calls = current_usage.get("api_call", 0)
        used_tokens = current_usage.get("ai_tokens", 0)

        new_total_calls = used_calls + requested_api_calls
        new_total_tokens = used_tokens + requested_tokens

        metrics = {
            "plan_id": plan.id,
            "used_api_calls": used_calls,
            "monthly_api_limit": plan.monthly_api_limit,
            "used_ai_tokens": used_tokens,
            "monthly_token_limit": plan.monthly_token_limit,
            "requested_api_calls": requested_api_calls,
            "requested_tokens": requested_tokens
        }

        # 3. Check Quota Boundaries (Strict <= limit)
        if new_total_calls > plan.monthly_api_limit:
            msg = (
                f"Monthly API call quota exceeded. Used: {used_calls}, "
                f"Requested: {requested_api_calls}, Limit: {plan.monthly_api_limit}."
            )
            logger.warning(f"Quota refusal (429): tenant={tenant_id}, reason=api_calls_exceeded")
            return QuotaDecision.EXCEEDED_QUOTA, msg, metrics

        if new_total_tokens > plan.monthly_token_limit:
            msg = (
                f"Monthly AI token quota exceeded. Used: {used_tokens}, "
                f"Requested: {requested_tokens}, Limit: {plan.monthly_token_limit}."
            )
            logger.warning(f"Quota refusal (429): tenant={tenant_id}, reason=ai_tokens_exceeded")
            return QuotaDecision.EXCEEDED_QUOTA, msg, metrics

        logger.info(f"Quota approved: tenant={tenant_id}, plan={plan.id}")
        return QuotaDecision.ALLOW, None, metrics
