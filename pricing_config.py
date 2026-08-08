from typing import Dict, Any


class PricingConfig:
    """
    Pinned AI Token Pricing Constants in Micro-Cents per 1,000 tokens.
    1 Cent = 10,000 Micro-Cents.
    1 Dollar = 100 Cents = 1,000,000 Micro-Cents.
    """
    # $0.0015 / 1k tokens = 0.15 cents / 1k = 150 micro-cents / 1k
    INPUT_TOKEN_MICRO_CENTS_PER_1K: int = 150

    # $0.00075 / 1k tokens = 0.075 cents / 1k = 75 micro-cents / 1k (50% discount)
    CACHED_INPUT_TOKEN_MICRO_CENTS_PER_1K: int = 75

    # $0.0060 / 1k tokens = 0.60 cents / 1k = 600 micro-cents / 1k
    OUTPUT_TOKEN_MICRO_CENTS_PER_1K: int = 600

    # Reasoning/thinking tokens are priced at standard output token rate (§ 4)
    REASONING_TOKEN_MICRO_CENTS_PER_1K: int = 600


class CostCalculator:

    @staticmethod
    def calculate_token_cost_micro_cents(
        input_tokens: int = 0,
        cached_input_tokens: int = 0,
        output_tokens: int = 0,
        reasoning_tokens: int = 0
    ) -> int:
        """
        Calculate total cost in micro-cents for a given token breakdown.
        Formula:
        (input_tokens * 150 + cached_input_tokens * 75 + output_tokens * 600 + reasoning_tokens * 600) / 1000
        """
        cost_input = (input_tokens * PricingConfig.INPUT_TOKEN_MICRO_CENTS_PER_1K) // 1000
        cost_cached = (cached_input_tokens * PricingConfig.CACHED_INPUT_TOKEN_MICRO_CENTS_PER_1K) // 1000
        cost_output = (output_tokens * PricingConfig.OUTPUT_TOKEN_MICRO_CENTS_PER_1K) // 1000
        cost_reasoning = (reasoning_tokens * PricingConfig.REASONING_TOKEN_MICRO_CENTS_PER_1K) // 1000

        total_micro_cents = cost_input + cost_cached + cost_output + cost_reasoning
        return total_micro_cents

    @staticmethod
    def micro_cents_to_cents(micro_cents: int) -> int:
        """Convert micro-cents to integer cents (ceiling rounding to prevent undercharging)"""
        if micro_cents == 0:
            return 0
        return (micro_cents + 999) // 1000
