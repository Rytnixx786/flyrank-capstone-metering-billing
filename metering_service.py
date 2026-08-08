import json
import logging
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, extract

from models import UsageEvent, Tenant, Subscription, Plan
from pricing_config import CostCalculator

logger = logging.getLogger("MeteringService")


class MeterService:

    @staticmethod
    def get_existing_event(db: Session, tenant_id: str, idempotency_key: str) -> Optional[UsageEvent]:
        """Check if an idempotency key has already been recorded for this tenant"""
        return db.query(UsageEvent).filter(
            UsageEvent.tenant_id == tenant_id,
            UsageEvent.idempotency_key == idempotency_key
        ).first()

    @staticmethod
    def record_usage_event(
        db: Session,
        tenant_id: str,
        usage_type: str,
        quantity: int,
        idempotency_key: str,
        input_tokens: int = 0,
        cached_input_tokens: int = 0,
        output_tokens: int = 0,
        reasoning_tokens: int = 0,
        response_payload: Optional[Dict[str, Any]] = None
    ) -> Tuple[UsageEvent, bool]:
        """
        Record a usage event idempotently with token category breakdown and micro-cents cost calculation.
        Returns Tuple[UsageEvent, is_new_event]
        """
        # 1. Fast path: Check existing event
        existing = MeterService.get_existing_event(db, tenant_id, idempotency_key)
        if existing:
            logger.info(f"Idempotency match found: tenant={tenant_id}, key={idempotency_key}. Returning original cached result.")
            return existing, False

        # 2. Calculate Cost in Micro-Cents
        cost_micro_cents = CostCalculator.calculate_token_cost_micro_cents(
            input_tokens=input_tokens,
            cached_input_tokens=cached_input_tokens,
            output_tokens=output_tokens,
            reasoning_tokens=reasoning_tokens
        )

        # 3. Record new event
        payload_str = json.dumps(response_payload) if response_payload else None
        event = UsageEvent(
            tenant_id=tenant_id,
            usage_type=usage_type,
            quantity=quantity,
            idempotency_key=idempotency_key,
            input_tokens=input_tokens,
            cached_input_tokens=cached_input_tokens,
            output_tokens=output_tokens,
            reasoning_tokens=reasoning_tokens,
            cost_micro_cents=cost_micro_cents,
            response_payload=payload_str
        )

        try:
            db.add(event)
            db.commit()
            db.refresh(event)
            logger.info(f"Recorded new usage event: tenant={tenant_id}, type={usage_type}, qty={quantity}, cost_micro={cost_micro_cents}")
            return event, True
        except IntegrityError:
            db.rollback()
            existing = MeterService.get_existing_event(db, tenant_id, idempotency_key)
            if existing:
                return existing, False
            raise

    @staticmethod
    def get_monthly_usage_summary(
        db: Session, tenant_id: str, year: int, month: int
    ) -> Dict[str, Any]:
        """Calculate total API calls, AI tokens, category breakdowns, and total cost in micro-cents"""
        results = db.query(
            UsageEvent.usage_type,
            func.coalesce(func.sum(UsageEvent.quantity), 0).label("total_quantity"),
            func.coalesce(func.sum(UsageEvent.input_tokens), 0).label("total_input"),
            func.coalesce(func.sum(UsageEvent.cached_input_tokens), 0).label("total_cached"),
            func.coalesce(func.sum(UsageEvent.output_tokens), 0).label("total_output"),
            func.coalesce(func.sum(UsageEvent.reasoning_tokens), 0).label("total_reasoning"),
            func.coalesce(func.sum(UsageEvent.cost_micro_cents), 0).label("total_cost_micro")
        ).filter(
            UsageEvent.tenant_id == tenant_id,
            extract("year", UsageEvent.timestamp) == year,
            extract("month", UsageEvent.timestamp) == month
        ).group_by(UsageEvent.usage_type).all()

        summary = {
            "api_call": 0,
            "ai_tokens": 0,
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
            "total_cost_micro_cents": 0
        }

        for usage_type, total_qty, input_t, cached_t, output_t, reasoning_t, cost_micro in results:
            if usage_type in summary:
                summary[usage_type] = int(total_qty)
            summary["input_tokens"] += int(input_t)
            summary["cached_input_tokens"] += int(cached_t)
            summary["output_tokens"] += int(output_t)
            summary["reasoning_tokens"] += int(reasoning_t)
            summary["total_cost_micro_cents"] += int(cost_micro)

        return summary
