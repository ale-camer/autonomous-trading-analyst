PRICING_TABLE = {
    "gpt-4o": {"prompt": 5.0, "completion": 15.0},
    "gpt-4o-mini": {"prompt": 0.150, "completion": 0.600},
    "claude-3-5-sonnet-20240620": {"prompt": 3.0, "completion": 15.0},
    "claude-3-5-sonnet-latest": {"prompt": 3.0, "completion": 15.0},
    "claude-3-5-haiku-20241022": {"prompt": 0.25, "completion": 1.25},
    "gemini-1.5-pro": {"prompt": 3.5, "completion": 10.5},
    "gemini-1.5-flash": {"prompt": 0.075, "completion": 0.3},
}


def calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate the USD cost of an API call based on token usage."""
    rates = PRICING_TABLE.get(model)
    if not rates:
        return 0.0
    prompt_cost = (prompt_tokens * rates["prompt"]) / 1_000_000
    completion_cost = (completion_tokens * rates["completion"]) / 1_000_000
    return prompt_cost + completion_cost
