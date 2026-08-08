import json
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from database import get_db, init_db
from models import Tenant, Subscription, Plan, UsageEvent
from schemas import (
    GenerateRequest, GenerateResponse, UsageRollupResponse,
    UsageItem, ErrorEnvelope, ErrorDetail
)
from metering_service import MeterService
from quota_service import QuotaService, QuotaDecision
from stripe_service import StripeService

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s")
logger = logging.getLogger("BillingEngine")

app = FastAPI(
    title="Usage Metering & Billing Engine API",
    description="Idempotent, multi-tenant usage metering, quota enforcement, and Stripe-integrated billing service.",
    version="1.0.0"
)


@app.on_event("startup")
def startup_event():
    init_db()
    logger.info("Database initialized successfully.")


@app.get("/")
def read_root():
    return {
        "service": "Usage Metering & Billing Engine API",
        "status": "online",
        "docs": "/docs"
    }


@app.post(
    "/api/v1/generate",
    response_model=GenerateResponse,
    responses={
        200: {"model": GenerateResponse, "description": "Billable action executed successfully."},
        400: {"model": ErrorEnvelope, "description": "Missing required headers or malformed payload."},
        402: {"model": ErrorEnvelope, "description": "Subscription lapsed or payment required."},
        429: {"model": ErrorEnvelope, "description": "Usage quota exceeded."}
    }
)
def generate_response(
    request: GenerateRequest,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db)
):
    """
    Billable action endpoint.
    Meters usage idempotently based on (X-Tenant-ID, Idempotency-Key).
    Enforces subscription quotas and returns honest HTTP 429 / 402 responses.
    """
    if not x_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required header: X-Tenant-ID"
        )
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required header: Idempotency-Key"
        )

    # 1. Fast Path: Check if this idempotency key was already processed for this tenant
    existing_event = MeterService.get_existing_event(db, x_tenant_id, idempotency_key)
    if existing_event:
        if existing_event.response_payload:
            cached_data = json.loads(existing_event.response_payload)
            cached_data["is_cached_deduplicated"] = True
            logger.info(f"Returning cached deduplicated payload for tenant={x_tenant_id}, key={idempotency_key}")
            return JSONResponse(status_code=status.HTTP_200_OK, content=cached_data)

    # 2. Total Tokens Requested Calculation
    # Note: Reasoning tokens count as output tokens (§ 4)
    metered_output_tokens = request.output_tokens + request.reasoning_tokens
    total_tokens_requested = request.input_tokens + request.cached_input_tokens + metered_output_tokens

    # 3. Quota Enforcement Check
    decision, error_msg, metrics = QuotaService.evaluate_request(
        db=db,
        tenant_id=x_tenant_id,
        requested_api_calls=1,
        requested_tokens=total_tokens_requested
    )

    if decision == QuotaDecision.PAYMENT_REQUIRED:
        error_payload = {
            "error": {
                "code": "payment_required",
                "message": error_msg,
                "details": metrics
            }
        }
        return JSONResponse(status_code=status.HTTP_402_PAYMENT_REQUIRED, content=error_payload)

    if decision == QuotaDecision.EXCEEDED_QUOTA:
        error_payload = {
            "error": {
                "code": "quota_exceeded",
                "message": error_msg,
                "details": metrics
            }
        }
        headers = {"Retry-After": "3600"}
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=error_payload,
            headers=headers
        )

    # 4. Generate Response Payload
    simulated_content = f"Generated AI response for prompt: '{request.prompt[:30]}...'"
    response_data = {
        "status": "allowed",
        "message": "Billable action executed successfully.",
        "generated_content": simulated_content,
        "api_calls_metered": 1,
        "total_tokens_metered": total_tokens_requested,
        "is_cached_deduplicated": False
    }

    # 5. Atomically Meter Usage Events
    # Record API call event
    MeterService.record_usage_event(
        db=db,
        tenant_id=x_tenant_id,
        usage_type="api_call",
        quantity=1,
        idempotency_key=f"{idempotency_key}_api",
        response_payload=response_data
    )

    # Record AI tokens event using original idempotency key
    event, is_new = MeterService.record_usage_event(
        db=db,
        tenant_id=x_tenant_id,
        usage_type="ai_tokens",
        quantity=total_tokens_requested,
        idempotency_key=idempotency_key,
        response_payload=response_data
    )

    return JSONResponse(status_code=status.HTTP_200_OK, content=response_data)


@app.get("/api/v1/usage", response_model=UsageRollupResponse)
def get_usage(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    db: Session = Depends(get_db)
):
    """
    Usage Rollup endpoint.
    Returns current calendar month usage, plan limits, and estimated cost for the tenant.
    """
    if not x_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required header: X-Tenant-ID"
        )

    tenant = db.query(Tenant).filter(Tenant.id == x_tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{x_tenant_id}' not found."
        )

    subscription = db.query(Subscription).filter(Subscription.tenant_id == x_tenant_id).first()
    plan_id = subscription.plan_id if subscription else "free"
    sub_status = subscription.status if subscription else "none"

    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        plan = Plan(id="free", name="Free Plan", monthly_api_limit=1000, monthly_token_limit=100000, price_cents=0)

    now = datetime.now(timezone.utc)
    summary = MeterService.get_monthly_usage_summary(db, x_tenant_id, now.year, now.month)

    api_used = summary.get("api_call", 0)
    tokens_used = summary.get("ai_tokens", 0)

    # Cost rollup calculation
    # Base plan cost in cents
    cost_cents = plan.price_cents

    return {
        "tenant_id": x_tenant_id,
        "plan_id": plan.id,
        "subscription_status": sub_status,
        "period": f"{now.year:04d}-{now.month:02d}",
        "api_calls": UsageItem(used=api_used, limit=plan.monthly_api_limit),
        "ai_tokens": UsageItem(used=tokens_used, limit=plan.monthly_token_limit),
        "estimated_cost_cents": cost_cents
    }


@app.post("/api/v1/checkout/session")
def create_checkout_session(
    plan_id: str = "pro",
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    db: Session = Depends(get_db)
):
    """
    Creates a Stripe Checkout Session in Test Mode for upgrading tenant plan.
    """
    if not x_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required header: X-Tenant-ID"
        )

    session_info = StripeService.create_checkout_session(db, x_tenant_id, plan_id)
    return session_info


@app.post("/api/v1/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature"),
    db: Session = Depends(get_db)
):
    """
    Stripe Webhook Handler.
    Reads raw bytes body, verifies HMAC signature, deduplicates event ID, and syncs tenant plan.
    """
    raw_body = await request.body()
    event_dict = StripeService.verify_webhook_signature(raw_body, stripe_signature)

    is_processed, message = StripeService.process_webhook_event(db, event_dict)
    return {
        "status": "success",
        "processed": is_processed,
        "message": message,
        "event_id": event_dict.get("id"),
        "event_type": event_dict.get("type")
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
