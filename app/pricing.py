import os


def estimate_cost_usd_micros(
    input_tokens: int | None,
    output_tokens: int | None,
) -> int | None:
    """
    Estimate cost in USD micros (1 USD = 1,000,000 micros).
    Prices are configurable via env to avoid hardcoding.
    """
    if input_tokens is None or output_tokens is None:
        return None

    # Default to some reasonable placeholders; override via env for your model.
    prompt_per_1k = float(os.getenv("COST_PROMPT_PER_1K_USD", "0.15"))
    completion_per_1k = float(os.getenv("COST_COMPLETION_PER_1K_USD", "0.60"))

    cost = (input_tokens / 1000.0) * prompt_per_1k + (
        output_tokens / 1000.0
    ) * completion_per_1k
    return int(cost * 1_000_000)
