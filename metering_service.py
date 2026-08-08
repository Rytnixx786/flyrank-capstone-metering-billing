import json
import logging
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, extract

from models import UsageEvent, Tenant, Subscription, Plan

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
        response_payload: Optional[Dict[str, Any]] = None
    ) -> Tuple[UsageEvent, bool]:
        """
        Record a usage event idempotently.
        Returns Tuple[UsageEvent, is_new_event]
        If duplicate key exists, returns existing event and is_new_event=False.
        """
        # 1. Fast path: Check existing event
        existing = MeterService.get_existing_event(db, tenant_id, idempotency_key)
        if existing:
            logger.info(f"Idempotency match found: tenant={tenant_id}, key={idempotency_key}. Returning original cached result.")
            return existing, False

        # 2. Record new event
        payload_str = json.dumps(response_payload) if response_payload else None
        event = UsageEvent(
            tenant_id=tenant_id,
            usage_type=usage_type,
            quantity=quantity,
            idempotency_key=idempotency_key,
            response_payload=payload_str
        )

        try:
            db.add(event)
            db.commit()
            db.refresh(event)
            logger.info(f"Recorded new usage event: tenant={tenant_id}, type={usage_type}, qty={quantity}, key={idempotency_key}")
            return event, True
        except IntegrityError:
            db.rollback()
            # Race condition handling: re-query existing event
            existing = MeterService.get_existing_event(db, tenant_id, idempotency_key)
            if existing:
                return existing, False
            raise

    @staticmethod
    def get_monthly_usage_summary(
        db: Session, tenant_id: str, year: int, month: int
    ) -> Dict[str, int]:
        """Calculate total API calls and AI tokens used by a tenant in a given calendar month"""
        results = db.query(
            UsageEvent.usage_type,
            func.coalesce(func.sum(UsageEvent.quantity), 0).label("total_quantity")
        ).filter(
            UsageEvent.tenant_id == tenant_id,
            extract("year", UsageEvent.timestamp) == year,
            extract("month", UsageEvent.timestamp) == month
        ).group_by(UsageEvent.usage_type).all()

        summary = {"api_call": 0, "ai_tokens": 0}
        for usage_type, total_qty in results:
            if usage_type in summary:
                summary[usage_type] = int(total_qty)

        return summary
