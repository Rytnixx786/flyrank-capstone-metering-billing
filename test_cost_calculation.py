import pytest
from pricing_config import CostCalculator, PricingConfig


# ====================================================================
# PROBE 5: Pinned Pricing Rules for Cached Inputs & Reasoning Tokens
# ====================================================================
def test_probe_5_pinned_pricing_rules_and_reasoning_tokens(client):
    """
    PROBE 5: Run pinned pricing tests -> cached-input (discounted) and reasoning-token (output rate)
    rules produce exact expected totals; GET /usage matches.
    """
    headers = {
        "X-Tenant-ID": "test_tenant_1",
        "Idempotency-Key": "ik_cost_probe_5"
    }

    # Request payload:
    # 1000 fresh input @ 150/1k = 150 micro-cents
    # 2000 cached input @ 75/1k  = 150 micro-cents (50% discount)
    # 500 output tokens @ 600/1k = 300 micro-cents
    # 500 reasoning    @ 600/1k = 300 micro-cents (priced at output rate)
    # Expected total = 150 + 150 + 300 + 300 = 900 micro-cents
    payload = {
        "prompt": "Probe 5 token cost calculation test",
        "input_tokens": 1000,
        "cached_input_tokens": 2000,
        "output_tokens": 500,
        "reasoning_tokens": 500
    }

    response = client.post("/api/v1/generate", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()

    assert data["cost_micro_cents"] == 900, f"PROBE 5 FAILED: Expected 900 micro-cents, got {data['cost_micro_cents']}"
    assert data["total_tokens_metered"] == 4000  # 1000+2000+500+500

    # Verify GET /api/v1/usage returns matching token breakdown and cost
    usage_res = client.get("/api/v1/usage", headers={"X-Tenant-ID": "test_tenant_1"})
    assert usage_res.status_code == 200
    usage_data = usage_res.json()

    breakdown = usage_data["token_breakdown"]
    assert breakdown["input_tokens"] == 1000
    assert breakdown["cached_input_tokens"] == 2000
    assert breakdown["output_tokens"] == 500
    assert breakdown["reasoning_tokens"] == 500
    assert usage_data["usage_cost_micro_cents"] == 900


def test_pinned_pricing_constants_unit():
    """Verify pinned pricing calculator math deterministically"""
    # 1k input (150) + 1k cached (75) + 1k output (600) + 1k reasoning (600) = 1425 micro-cents
    cost = CostCalculator.calculate_token_cost_micro_cents(
        input_tokens=1000,
        cached_input_tokens=1000,
        output_tokens=1000,
        reasoning_tokens=1000
    )
    assert cost == 1425

    # Test ceiling rounding cents conversion
    cents = CostCalculator.micro_cents_to_cents(1425)
    assert cents == 2  # 1425 micro-cents rounds to 2 cents
