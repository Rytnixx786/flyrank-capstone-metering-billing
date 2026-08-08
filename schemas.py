from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    """Payload for billable action POST /api/v1/generate"""
    prompt: str = Field(..., description="Prompt text or input payload")
    input_tokens: int = Field(default=0, ge=0, description="Fresh input token count")
    cached_input_tokens: int = Field(default=0, ge=0, description="Cached input token count")
    output_tokens: int = Field(default=0, ge=0, description="Generated output token count")
    reasoning_tokens: int = Field(default=0, ge=0, description="Reasoning/thinking token count")


class GenerateResponse(BaseModel):
    """Successful billable action response payload"""
    status: str = Field(default="allowed")
    message: str = Field(default="Billable action executed successfully.")
    generated_content: str = Field(..., description="Simulated generated response text")
    api_calls_metered: int = Field(default=1)
    total_tokens_metered: int = Field(..., description="Total metered token quantity")
    cost_micro_cents: int = Field(..., description="Calculated event cost in micro-cents")
    is_cached_deduplicated: bool = Field(default=False, description="True if response was returned via idempotency key match")


class UsageItem(BaseModel):
    used: int
    limit: int


class TokenBreakdown(BaseModel):
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_tokens: int


class UsageRollupResponse(BaseModel):
    """Payload for GET /api/v1/usage"""
    tenant_id: str
    plan_id: str
    subscription_status: str
    period: str
    api_calls: UsageItem
    ai_tokens: UsageItem
    token_breakdown: TokenBreakdown
    usage_cost_micro_cents: int
    estimated_cost_cents: int


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ErrorEnvelope(BaseModel):
    error: ErrorDetail
